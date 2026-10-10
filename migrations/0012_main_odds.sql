-- Models v2, block B (docs/models_v2_plan.md section 2): main lines of a
-- game - moneyline (h2h, overtime included) and total goals - from The
-- Odds API. One snapshot per game and kind: 'day' = the archive snapshot at
-- 15:00 UTC of the game day, 'live' = fetched on the game day. Rows are
-- stored only from a snapshot taken BEFORE puck drop.
--
-- A separate table from `odds` on purpose: those rows are player props with
-- their own snapshot kinds, and no reader of one may pick up the other.
-- Nothing writes here until the user's "jed".
CREATE TABLE main_odds (
    game_id        INTEGER NOT NULL REFERENCES games(game_id),
    event_id       TEXT    NOT NULL,
    bookmaker      TEXT    NOT NULL,
    market         TEXT    NOT NULL CHECK (market IN ('h2h', 'totals')),
    side           TEXT    NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    line           REAL,                    -- totals only
    price          REAL    NOT NULL,        -- decimal odds
    snapshot_time  TEXT    NOT NULL,        -- UTC timestamp of the snapshot
    snapshot_kind  TEXT    NOT NULL CHECK (snapshot_kind IN ('day', 'live')),
    PRIMARY KEY (game_id, bookmaker, market, side, snapshot_kind)
);
