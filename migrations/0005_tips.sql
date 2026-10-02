-- Tips of the live season (docs/tips_plan.md, plan amendments D5/D6).
--
-- One row per (game, player, line, side) of one odds snapshot: the best
-- book's edge for that side, as rule 6.4 prices each book separately.
-- Every candidate is stored, playable or not, and settled - the MODEL arm
-- is the paper record of all playable tips. Rows are written once and never
-- changed except for the settlement columns.
--
-- Probabilities are for 60 MINUTES (Tipsport's rule, D3): p_market is the
-- US books' de-vig converted to 60 minutes (D3.3).

CREATE TABLE tips (
    tip_id              TEXT PRIMARY KEY,   -- sha1(model|game|player|line|side|snapshot_time)
    model               TEXT NOT NULL,      -- e.g. naive_sog_v1
    game_id             INTEGER NOT NULL REFERENCES games(game_id),
    game_date           TEXT NOT NULL,
    start_time_utc      TEXT,
    player_id           INTEGER NOT NULL,
    player_name         TEXT,
    team_id             INTEGER,
    opp_id              INTEGER,
    market              TEXT NOT NULL,
    line                REAL NOT NULL,
    side                TEXT NOT NULL CHECK (side IN ('over', 'under')),
    mu_60               REAL NOT NULL,
    p_model             REAL NOT NULL,
    p_market            REAL NOT NULL,
    edge                REAL NOT NULL,
    books               INTEGER NOT NULL,   -- books quoting both sides at this line
    best_book           TEXT,
    best_price          REAL,               -- best US price for this side (information)
    tipsport_min_price  REAL,               -- 1 / (p_model - EDGE_MIN): Tipsport price needed
    sim_tipsport_price  REAL NOT NULL,      -- D1: 1 / (p_market * (1 + m))
    entry_live          INTEGER NOT NULL,
    gp_season           INTEGER,
    gp_prev             INTEGER,
    playable            INTEGER NOT NULL,   -- the tip of this (game, player): max edge >= 3 p.b. and entry
    snapshot_kind       TEXT NOT NULL,
    snapshot_time       TEXT NOT NULL,
    built_at            TEXT NOT NULL,
    actual_60           INTEGER,
    outcome             TEXT CHECK (outcome IN ('win', 'loss', 'push', 'void')),
    profit_units        REAL,               -- MODEL arm: 1 unit at sim_tipsport_price
    settled_at          TEXT
);
CREATE INDEX idx_tips_date ON tips(game_date, playable);
CREATE INDEX idx_tips_game ON tips(game_id, player_id);
