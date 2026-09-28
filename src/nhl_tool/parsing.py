"""Small pure conversions shared by every NHL API parser."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# NHL gameType -> our season_type. Anything else (All-Star = 4, special
# tournaments) is not stored.
GAME_TYPES = {1: "preseason", 2: "regular", 3: "playoffs"}


def toi_to_seconds(value) -> int | None:
    """'16:03' -> 963. Box scores print MM:SS, and MM can exceed 59
    (a goalie's '65:00'). None / '' -> None."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return int(value)
    minutes, _, seconds = str(value).partition(":")
    return int(minutes) * 60 + int(seconds or 0)


def season_label(season_id: int | str) -> str:
    """20252026 -> '2025-26'."""
    s = str(season_id)
    return f"{s[:4]}-{s[6:8]}"


def season_id(label: str) -> int:
    """'2025-26' -> 20252026."""
    start = int(label[:4])
    return start * 10000 + start + 1


def season_type(game_type: int) -> str | None:
    return GAME_TYPES.get(int(game_type))


def saves_over_shots(value) -> tuple[int | None, int | None]:
    """Box-score goalie splits come as 'saves/shots', e.g. '5/9'."""
    if not value or "/" not in str(value):
        return None, None
    saves, shots = str(value).split("/", 1)
    return int(saves), int(shots)


def default_name(obj) -> str | None:
    """NHL localised names: {'default': 'Bruins', 'fr': ...} -> 'Bruins'."""
    if isinstance(obj, dict):
        return obj.get("default")
    return obj


def et_time_to_utc(game_date: str, hhmm: str) -> str:
    """'2025-10-09', '10:00' -> UTC ISO of 10:00 US/Eastern that day.
    DST-aware; used for the morning snapshot anchor."""
    h, m = (int(x) for x in hhmm.split(":"))
    local = datetime.combine(date.fromisoformat(game_date), time(h, m), tzinfo=ET)
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def minus_minutes(iso_utc: str, minutes: int) -> str:
    """'2025-10-09T23:00:00Z' - 10 min -> '2025-10-09T22:50:00Z'."""
    t = datetime.strptime(iso_utc, "%Y-%m-%dT%H:%M:%SZ") - timedelta(minutes=minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")
