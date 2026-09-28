import sqlite3

import pytest


def test_migrations_are_idempotent(conn):
    from migrate import apply_migrations, applied_versions, migration_files
    apply_migrations(conn)                    # second run: no-op, no error
    assert applied_versions(conn) == {p.stem for p in migration_files()}


def _odds(conn, kind):
    conn.execute(
        """INSERT INTO odds (event_id, market, side, line, price, bookmaker,
                             snapshot_time, snapshot_kind, player_name_raw)
           VALUES ('e1', 'player_shots_on_goal', 'over', 2.5, 1.9, 'draftkings',
                   '2025-10-09T22:50:00Z', ?, 'Andrew Copp')""", (kind,))


def test_every_odds_row_must_name_its_snapshot(conn):
    _odds(conn, "closing")
    with pytest.raises(sqlite3.IntegrityError):
        _odds(conn, None)
    with pytest.raises(sqlite3.IntegrityError):
        _odds(conn, "whenever")


def test_game_outcome_is_constrained(conn):
    conn.execute("INSERT INTO teams VALUES (1, 'AAA', 'A'), (2, 'BBB', 'B')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("""INSERT INTO games (game_id, season, season_type, game_date,
                            home_team_id, away_team_id, last_period_type)
                        VALUES (1, '2025-26', 'regular', '2025-10-09', 1, 2, 'SO2')""")
