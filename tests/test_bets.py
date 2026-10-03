"""Decisions and tickets (tips plan 9): code-level lock at puck drop,
append-only records, merge with the GitHub copy, ticket settlement."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from dashboard import bets

START = "2026-10-03T23:00:00Z"
TIP = {"tip_id": "t1", "game_id": 1, "game_date": "2026-10-03", "start_time_utc": START,
       "player_id": 7, "player_name": "A B", "side": "under", "line": 2.5}
BEFORE = datetime(2026, 10, 3, 22, 59, tzinfo=timezone.utc)
AFTER = datetime(2026, 10, 3, 23, 0, tzinfo=timezone.utc)


def test_decisions_latest_wins_and_nothing_is_rewritten():
    bets.decide(TIP, "bet", now=BEFORE)
    bets.decide(TIP, "pending", now=BEFORE)
    bets.decide(TIP, "no", now=BEFORE)
    assert bets.current_decisions()["t1"]["decision"] == "no"
    assert len(bets.read("decisions")) == 3


def test_lock_at_puck_drop_is_in_code():
    with pytest.raises(bets.Locked):
        bets.decide(TIP, "bet", now=AFTER)
    with pytest.raises(bets.Locked):
        bets.save_bet(TIP, 2.5, 1.6, 200, "tipsport", now=AFTER)
    b = bets.save_bet(TIP, 2.5, 1.6, 200, "tipsport", now=BEFORE)
    with pytest.raises(bets.Locked):
        bets.delete_bet(b, now=AFTER)          # a lost ticket cannot be erased later
    assert len(bets.active_bets()) == 1


def test_delete_is_a_record_and_hides_the_ticket():
    b = bets.save_bet(TIP, 2.5, 1.6, 200, "tipsport", now=BEFORE)
    bets.delete_bet(b, now=BEFORE)
    assert bets.active_bets() == []
    assert [r["type"] for r in bets.read("bets")] == ["bet", "delete"]


def test_ticket_validation():
    with pytest.raises(ValueError):
        bets.save_bet(TIP, 2.5, 1.0, 200, "tipsport", now=BEFORE)
    with pytest.raises(ValueError):
        bets.save_bet(TIP, 2.5, 1.8, 0, "tipsport", now=BEFORE)


def test_settlement_at_the_tickets_own_line_and_price():
    b = {"side": "under", "line": 2.5, "price": 1.6, "stake": 200}
    assert bets.settle(b, 2, True) == ("win", pytest.approx(120.0))
    assert bets.settle(b, 3, True) == ("loss", -200)
    assert bets.settle(b, None, False) == ("void", 0.0)
    assert bets.settle({**b, "line": 2.0}, 2, True) == ("push", 0.0)
    assert bets.settle({**b, "side": "over"}, 3, True)[0] == "win"


def test_merge_is_a_union_by_id_in_time_order():
    a = json.dumps({"id": "x", "ts": "2026-10-03T10:00:00"}) + "\n"
    b = (json.dumps({"id": "y", "ts": "2026-10-03T09:00:00"}) + "\n"
         + json.dumps({"id": "x", "ts": "2026-10-03T10:00:00"}) + "\n")
    merged = bets._merge_text(a, b).splitlines()
    assert [json.loads(x)["id"] for x in merged] == ["y", "x"]


def test_no_remote_without_token_and_never_the_public_repo(monkeypatch):
    assert bets._remote() is None
    monkeypatch.setenv("NHL_DATA_TOKEN", "tok")
    monkeypatch.setenv("NHL_DB_RELEASE_REPO", "MichalCernohorsky/NHL_project")
    assert bets._remote() is None                  # public code repo refused
    monkeypatch.setenv("NHL_DB_RELEASE_REPO", "MichalCernohorsky/NHL_project-data")
    assert bets._remote() == ("tok", "MichalCernohorsky/NHL_project-data")


def test_failed_push_leaves_a_visible_marker(monkeypatch):
    monkeypatch.setenv("NHL_DATA_TOKEN", "tok")
    monkeypatch.setenv("NHL_DB_RELEASE_REPO", "MichalCernohorsky/NHL_project-data")

    def offline(*a, **k):
        raise OSError("offline")
    monkeypatch.setattr(bets, "_get_remote", offline)
    bets.decide(TIP, "bet", now=BEFORE)                # the write itself succeeds locally
    assert bets.unsynced()
    assert bets.current_decisions()["t1"]["decision"] == "bet"
