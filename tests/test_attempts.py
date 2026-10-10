"""Shot attempts and the manpower split (docs/models_v2_plan.md, step 0)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from conftest import game, load_fixture, week  # noqa: E402

from nhl_tool import attempts, boxscore  # noqa: E402
from nhl_tool.schedule import parse_week, upsert_games, upsert_teams  # noqa: E402

GID = 2025020010          # fixture game: home DET (17), away MTL (8)


def _ev(kind, shooter, code="1551", ptype="REG", shot_type="wrist"):
    det = {"eventOwnerTeamId": 0}
    if kind == "goal":
        det["scoringPlayerId"] = shooter
        if shot_type:
            det["shotType"] = shot_type
    else:
        det["shootingPlayerId"] = shooter
    return {"typeDescKey": kind, "situationCode": code,
            "periodDescriptor": {"number": 1, "periodType": ptype}, "details": det}


def test_strength_from_the_situation_code():
    assert attempts.strength("1551", True) == "ev" and attempts.strength("1441", False) == "ev"
    assert attempts.strength("1451", True) == "pp" and attempts.strength("1451", False) == "sh"
    assert attempts.strength("1541", False) == "pp" and attempts.strength("1541", True) == "sh"
    assert attempts.strength("0651", False) == "ev"          # away net empty: extra attacker, not a PP
    assert attempts.strength("1560", True) == "ev"
    assert attempts.strength(None, True) == "ev" and attempts.strength("15", True) == "ev"


def test_parse_counts_attempts_of_regulation_only():
    payload = {"plays": [
        _ev("shot-on-goal", 5), _ev("missed-shot", 5), _ev("blocked-shot", 5),
        _ev("goal", 6), _ev("goal", 6, shot_type=None),               # a goal without a shot
        _ev("shot-on-goal", 5, ptype="OT"), _ev("shot-on-goal", 5, ptype="SO"),
        {"typeDescKey": "faceoff", "periodDescriptor": {"periodType": "REG"}, "details": {}}]}
    ev = attempts.parse_attempts(payload)
    assert [(e["player_id"], e["on_goal"]) for e in ev] == [(5, True), (5, False), (5, False), (6, True)]
    assert attempts.on_goal_reg(ev) == {5: 1, 6: 1}


def test_splits_by_side_and_zero_rows_for_everyone_who_played():
    ev = [{"player_id": 5, "on_goal": True, "code": "1451"},     # home on the power play
          {"player_id": 5, "on_goal": False, "code": "1451"},
          {"player_id": 5, "on_goal": True, "code": "1551"},
          {"player_id": 9, "on_goal": True, "code": "1451"},     # away shorthanded
          {"player_id": 77, "on_goal": True, "code": "1551"}]    # a goalie: not a skater row
    got = attempts.splits(ev, {5: 17, 9: 8, 6: 17}, home_team_id=17)
    assert got[5] == {"team_id": 17, "att_reg": 3, "sog_pp_reg": 1, "att_pp_reg": 2,
                      "sog_sh_reg": 0, "att_sh_reg": 0}
    assert got[9]["sog_sh_reg"] == 1 and got[9]["att_sh_reg"] == 1 and got[9]["att_pp_reg"] == 0
    assert got[6]["att_reg"] == 0 and 77 not in got


def test_store_after_the_check(conn):
    teams, games = parse_week(week([game(GID)]), "2025-26")
    upsert_teams(conn, teams)
    upsert_games(conn, games)
    boxscore.store(conn, boxscore.parse_boxscore(load_fixture("boxscore_2025020010.json")), [])
    conn.execute("UPDATE player_game_logs SET sog_reg = 0 WHERE game_id = ?", (GID,))
    a, b = [r["player_id"] for r in conn.execute(
        "SELECT player_id FROM player_game_logs WHERE game_id = ? AND team_id = 17 ORDER BY player_id LIMIT 2",
        (GID,))]
    conn.execute("UPDATE player_game_logs SET sog_reg = 2 WHERE player_id = ?", (a,))
    ev = [{"player_id": a, "on_goal": True, "code": "1451"}, {"player_id": a, "on_goal": True, "code": "1551"},
          {"player_id": a, "on_goal": False, "code": "1551"}, {"player_id": b, "on_goal": False, "code": "1541"}]
    assert attempts.mismatches(conn, GID, ev) == []
    assert attempts.mismatches(conn, GID, ev[:1]) == [f"{a} sog_reg db=2 pbp=1"]
    n = attempts.store(conn, GID, ev)
    assert n == conn.execute("SELECT COUNT(*) FROM player_game_logs WHERE game_id = ?", (GID,)).fetchone()[0]
    assert attempts.store(conn, GID, ev) == n                                   # idempotent
    ra = conn.execute("SELECT * FROM player_shot_splits WHERE player_id = ?", (a,)).fetchone()
    assert (ra["att_reg"], ra["sog_pp_reg"], ra["att_pp_reg"]) == (3, 1, 1)
    rb = conn.execute("SELECT * FROM player_shot_splits WHERE player_id = ?", (b,)).fetchone()
    assert (rb["att_reg"], rb["att_sh_reg"], rb["sog_sh_reg"]) == (1, 1, 0)       # home, 4 skaters vs 5


def test_backfill_workflow_is_manual_free_and_locked():
    import yaml
    text = (ROOT / ".github" / "workflows" / "backfill.yml").read_text()
    wf = yaml.safe_load(text)
    trig = wf[True] if True in wf else wf["on"]
    assert set(trig) == {"workflow_dispatch"} and wf["concurrency"]["group"] == "nhl-db"
    assert "ODDS_API_KEY" not in text                                           # no credits here
    assert set(trig["workflow_dispatch"]["inputs"]["script"]["options"]) == \
        {"attempts", "penalties", "officials", "pbp"}
    for name in trig["workflow_dispatch"]["inputs"]["script"]["options"]:
        assert (ROOT / "scripts" / f"backfill_{name}.py").exists()
