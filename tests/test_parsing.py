from nhl_tool.parsing import (et_time_to_utc, minus_minutes, saves_over_shots,
                              season_id, season_label, season_type, toi_to_seconds)


def test_toi_to_seconds():
    assert toi_to_seconds("16:03") == 963
    assert toi_to_seconds("65:00") == 3900     # goalie in overtime: minutes > 59
    assert toi_to_seconds("0:07") == 7
    assert toi_to_seconds(None) is None and toi_to_seconds("") is None
    assert toi_to_seconds(760) == 760           # stats REST already gives seconds


def test_season_roundtrip():
    assert season_label(20252026) == "2025-26"
    assert season_id("2025-26") == 20252026
    assert season_id("2009-10") == 20092010
    assert season_label(season_id("2023-24")) == "2023-24"


def test_game_types():
    assert season_type(2) == "regular" and season_type(1) == "preseason"
    assert season_type(3) == "playoffs"
    assert season_type(4) is None               # All-Star: never stored


def test_saves_over_shots():
    assert saves_over_shots("5/9") == (5, 9)
    assert saves_over_shots("0/0") == (0, 0)
    assert saves_over_shots(None) == (None, None)


def test_morning_anchor_is_dst_aware():
    # 10:00 ET is 14:00 UTC in October (EDT) and 15:00 UTC in January (EST).
    assert et_time_to_utc("2025-10-09", "10:00") == "2025-10-09T14:00:00Z"
    assert et_time_to_utc("2026-01-15", "10:00") == "2026-01-15T15:00:00Z"


def test_closing_offset_crosses_midnight():
    assert minus_minutes("2025-10-10T00:05:00Z", 10) == "2025-10-09T23:55:00Z"
