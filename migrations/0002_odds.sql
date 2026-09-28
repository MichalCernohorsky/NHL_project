-- Odds snapshots from The Odds API.
--
-- snapshot_kind is NOT NULL from the first row (lesson from NBA migration
-- 0014): with morning and closing rows in one table, a reader that does not
-- name its snapshot silently mixes the two and picks a best-of-two price no
-- bettor ever gets. tests/test_snapshot_isolation.py enforces that every
-- reader names the kind.
--
-- Nothing writes here until the purchase in docs/market_discovery_plan.md
-- is approved ("jeď").

CREATE TABLE odds (
    odds_id          INTEGER PRIMARY KEY,
    event_id         TEXT NOT NULL,          -- The Odds API event id
    game_id          INTEGER REFERENCES games(game_id),
    player_id        INTEGER,                -- NULL when the name did not match a roster
    player_name_raw  TEXT,
    market           TEXT NOT NULL,          -- e.g. player_shots_on_goal
    side             TEXT NOT NULL CHECK (side IN ('over', 'under', 'yes', 'no')),
    line             REAL,
    price            REAL NOT NULL,          -- decimal odds
    bookmaker        TEXT NOT NULL,
    snapshot_time    TEXT NOT NULL,          -- UTC ISO the snapshot was priced at
    snapshot_kind    TEXT NOT NULL CHECK (snapshot_kind IN ('morning', 'closing', 'live')),
    UNIQUE (event_id, player_name_raw, market, side, line, bookmaker, snapshot_time)
);
CREATE INDEX idx_odds_game ON odds(game_id, market, snapshot_kind);
