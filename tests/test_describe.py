"""Descriptive statistics on the Hráč / Týmy pages (docs/tips_plan.md
section 11): a gap is labelled by the 95% interval of the difference, and
the 60-minute team numbers leave out games without play-by-play counts."""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dashboard import data, describe  # noqa: E402
from test_dashboard import _build_db  # noqa: E402


def test_mean_ci_and_small_samples():
    m, half, n = describe.mean_ci([1, 2, 3, 4, 5])
    assert (m, n) == (3.0, 5)
    assert half == pytest.approx(1.96 * pd.Series([1, 2, 3, 4, 5]).std(ddof=1) / 5 ** 0.5)
    assert describe.mean_ci([7]) == (7.0, None, 1)
    assert describe.mean_ci([]) == (None, None, 0)
    assert describe.mean_ci([2, None, 4])[2] == 2


def test_diff_ci_is_welch():
    a, b = [3, 4, 5, 4, 3, 5], [1, 2, 1, 2, 2, 1]
    d, half = describe.diff_ci(a, b)
    sa, sb = pd.Series(a), pd.Series(b)
    assert d == pytest.approx(sa.mean() - sb.mean())
    assert half == pytest.approx(1.96 * (sa.var(ddof=1) / 6 + sb.var(ddof=1) / 6) ** 0.5)
    assert describe.diff_ci([1], [2, 3]) == (None, None)


def test_split_table_labels_noise_as_noise():
    clear = pd.DataFrame({"doma": [1] * 20 + [0] * 20, "s": [5, 6] * 10 + [1, 2] * 10})
    noise = pd.DataFrame({"doma": [1, 0] * 20, "s": [1, 1, 5, 5, 2, 2, 4, 4] * 5})
    few = pd.DataFrame({"doma": [1, 0, 0], "s": [3, 2, 4]})
    spec = [("doma", "doma", "venku")]
    assert describe.split_table(clear, "s", spec)["čtení"][0] == "rozdíl větší než náhoda"
    row = describe.split_table(noise, "s", spec).iloc[0]
    assert row["čtení"] == "v rámci náhody" and row["rozdíl"] == "+0,00"
    assert describe.split_table(few, "s", spec)["čtení"][0] == "málo zápasů"
    assert describe.split_table(clear, "s", [("chybi", "a", "b")]).empty
    assert "(20 z.)" in describe.split_table(clear, "s", spec)["první"][0]


def test_over_table():
    t = describe.over_table([("vše", pd.Series([28, 30, 32, 34])), ("nic", pd.Series([], dtype=float))],
                            [29.5, 33.5])
    assert t["přes 29,5"].tolist() == ["75 %", "–"] and t["přes 33,5"][0] == "25 %"
    assert t["zápasů"].tolist() == [4, 0]


@pytest.fixture
def small_db(tmp_path, monkeypatch):
    path = tmp_path / "nhl.db"
    _build_db(path, True)
    monkeypatch.setenv("NHL_DASHBOARD_DB", str(path))
    return path


def test_team_60_matches_the_skaters_and_skips_uncounted_games(small_db):
    import sqlite3
    t = data.team_table_60("2025-26")
    assert len(t) == 2 and set(t["zapasu_60"]) == {1}
    conn = sqlite3.connect(small_db)
    want = dict(conn.execute("""SELECT tm.abbreviation, SUM(p.sog_reg) FROM player_game_logs p
                                JOIN teams tm ON tm.team_id = p.team_id GROUP BY p.team_id"""))
    got = dict(zip(t["tym"], t["strely_pro_60"]))
    assert got == pytest.approx(want)
    a, b = t.iloc[0], t.iloc[1]
    assert a["strely_proti_60"] == pytest.approx(b["strely_pro_60"])
    assert a["pousti_utocnikum"] + a["pousti_obrancum"] == pytest.approx(a["strely_proti_60"])
    g = data.team_games_60(a["tym"], "2025-26")
    assert len(g) == 1 and g["strely_pro_60"][0] == a["strely_pro_60"] and g["b2b"][0] == 0
    # one skater without 60-minute counts -> the whole game is left out, not undercounted
    conn.execute("""UPDATE player_game_logs SET sog_reg = NULL WHERE rowid =
                    (SELECT MIN(rowid) FROM player_game_logs)""")
    conn.commit()
    conn.close()
    assert data.team_table_60("2025-26").empty


def test_player_views_and_default_season(small_db):
    sk = data.skaters("2025-26")
    pid = int(sk.iloc[0]["player_id"])
    g = data.player_games(pid, "2025-26")
    assert {"doma", "b2b", "tym_strely_60", "toi_60", "tm"} <= set(g.columns)
    assert g["tym_strely_60"][0] >= g["strely_60"][0]
    ps = data.player_seasons(pid)
    assert ps["sezona"].tolist() == ["2025-26"] and ps["zapasu"][0] == 1
    assert ps["na_60_ledu"][0] == pytest.approx(g["strely_60"][0] / g["toi_60"][0] * 60)
    shooters = data.team_shooters(sk.iloc[0]["tym"], "2025-26")
    assert shooters["strely_60"].is_monotonic_decreasing and pid in set(sk["player_id"])
    tips = data.player_tips(8477429)                      # Andrew Copp, fixture tip "a"
    assert len(tips) == 1 and tips["outcome"][0] == "win" and tips["arm_top"][0] == 1
    # one game day is too little to describe a season -> fall back to the first listed
    assert data.default_season_index(data.seasons()) == 0
    # the live season has no box score yet -> open on the newest season that has enough
    assert data.default_season_index(["2026-27", "2025-26"], min_game_days=1) == 1
