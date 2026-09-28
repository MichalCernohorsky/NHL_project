"""Season schedule from api-web.nhle.com/v1/schedule/{date}.

One call returns a whole week (`gameWeek`, 7 days) plus the season's
boundaries, so a season is ~30 requests. Teams are taken from the games
themselves: no separate team list to keep in sync when a franchise moves
(Arizona -> Utah) or renames.
"""
from __future__ import annotations

from datetime import date, timedelta

from .parsing import default_name, season_label, season_type

FINISHED_STATES = ("OFF", "FINAL")


def season_probe_date(label: str) -> str:
    """A date that is inside the regular season of every NHL year: the
    schedule response for it carries the season's start and end dates."""
    return f"{label[:4]}-10-15"


def season_bounds(payload: dict, include_playoffs: bool = False,
                  include_preseason: bool = False) -> tuple[str, str]:
    start = payload["preSeasonStartDate"] if include_preseason \
        else payload["regularSeasonStartDate"]
    end = payload["playoffEndDate"] if include_playoffs \
        else payload["regularSeasonEndDate"]
    return start, end


def week_starts(start: str, end: str) -> list[str]:
    d, stop = date.fromisoformat(start), date.fromisoformat(end)
    out = []
    while d <= stop:
        out.append(d.isoformat())
        d += timedelta(days=7)
    return out


def _team(side: dict) -> dict:
    place = default_name(side.get("placeName")) or ""
    common = default_name(side.get("commonName")) or ""
    return {"team_id": int(side["id"]), "abbreviation": side["abbrev"],
            "full_name": f"{place} {common}".strip() or side["abbrev"]}


def parse_week(payload: dict, season: str) -> tuple[dict, list[dict]]:
    """-> ({team_id: team_row}, [game_row]) for games of `season` only
    (a week at a season boundary can hold games of two seasons)."""
    teams, games = {}, []
    for day in payload.get("gameWeek", []):
        for g in day.get("games", []):
            stype = season_type(g["gameType"])
            if stype is None or season_label(g["season"]) != season:
                continue
            home, away = _team(g["homeTeam"]), _team(g["awayTeam"])
            teams[home["team_id"]] = home
            teams[away["team_id"]] = away
            outcome = (g.get("gameOutcome") or {}).get("lastPeriodType")
            finished = g.get("gameState") in FINISHED_STATES
            games.append({
                "game_id": int(g["id"]),
                "season": season,
                "season_type": stype,
                "game_date": day["date"],
                "start_time_utc": g.get("startTimeUTC"),
                "home_team_id": home["team_id"],
                "away_team_id": away["team_id"],
                "home_score": g["homeTeam"].get("score") if finished else None,
                "away_score": g["awayTeam"].get("score") if finished else None,
                "last_period_type": outcome if finished else None,
                "game_state": g.get("gameState"),
                "schedule_state": g.get("gameScheduleState"),
                "neutral_site": int(bool(g.get("neutralSite"))),
            })
    return teams, games


def upsert_teams(conn, teams: dict):
    conn.executemany(
        """INSERT INTO teams (team_id, abbreviation, full_name)
           VALUES (:team_id, :abbreviation, :full_name)
           ON CONFLICT(team_id) DO UPDATE SET
               abbreviation = excluded.abbreviation,
               full_name = excluded.full_name""",
        list(teams.values()))


def upsert_games(conn, games: list[dict]):
    """Schedule rows are refreshed on every sync (postponements move dates
    and start times). Scores and OT/SO are only ever set, never cleared:
    a later, poorer payload must not erase a result."""
    conn.executemany(
        """INSERT INTO games (game_id, season, season_type, game_date,
                              start_time_utc, home_team_id, away_team_id,
                              home_score, away_score, last_period_type,
                              game_state, schedule_state, neutral_site)
           VALUES (:game_id, :season, :season_type, :game_date,
                   :start_time_utc, :home_team_id, :away_team_id,
                   :home_score, :away_score, :last_period_type,
                   :game_state, :schedule_state, :neutral_site)
           ON CONFLICT(game_id) DO UPDATE SET
               game_date = excluded.game_date,
               start_time_utc = excluded.start_time_utc,
               home_score = COALESCE(excluded.home_score, games.home_score),
               away_score = COALESCE(excluded.away_score, games.away_score),
               last_period_type = COALESCE(excluded.last_period_type,
                                           games.last_period_type),
               game_state = excluded.game_state,
               schedule_state = excluded.schedule_state,
               neutral_site = excluded.neutral_site""",
        games)
