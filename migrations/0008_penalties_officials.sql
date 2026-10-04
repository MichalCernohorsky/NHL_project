-- Team markets plan (docs/team_markets_plan.md, approved 4. 10. 2026), step 2.
--
-- Penalties are stored one row per play-by-play event, not as a count:
-- Tipsport's rules for "dvouminutové tresty" (double minor = two? bench
-- minor? 60 minutes only?) are still open (plan O1-O5), and any counting
-- rule can be applied to events without downloading again.

CREATE TABLE penalties (
    game_id        INTEGER NOT NULL REFERENCES games(game_id),
    event_id       INTEGER NOT NULL,     -- play-by-play eventId
    team_id        INTEGER NOT NULL,     -- the penalized team
    period         INTEGER NOT NULL,
    period_type    TEXT    NOT NULL,     -- REG / OT / SO
    time_in_period TEXT,                 -- mm:ss
    type_code      TEXT    NOT NULL,     -- MIN / BEN / MAJ / MIS / GAM / MAT / PS
    desc_key       TEXT,
    duration       INTEGER,              -- minutes (2, 4 = double minor, 5, 10)
    committed_by   INTEGER,              -- player id; NULL for bench penalties
    served_by      INTEGER,
    drawn_by       INTEGER,
    PRIMARY KEY (game_id, event_id)
);
CREATE INDEX idx_penalties_team ON penalties(team_id, game_id);

-- Referees and linesmen of FINISHED games (right-rail gameInfo). A post-game
-- fact; whether they are known before a game is what referee_probe measures.
CREATE TABLE game_officials (
    game_id  INTEGER NOT NULL REFERENCES games(game_id),
    role     TEXT    NOT NULL,           -- referee / linesman
    name     TEXT    NOT NULL,
    PRIMARY KEY (game_id, role, name)
);
CREATE INDEX idx_officials_name ON game_officials(name);

-- When does the NHL API know tonight's referees? One row per (game, check)
-- for games that have not started. The model may use referees only after
-- this shows them known before betting time (plan section 3).
CREATE TABLE referee_probe (
    game_id        INTEGER NOT NULL REFERENCES games(game_id),
    checked_at     TEXT    NOT NULL,     -- ISO UTC
    start_time_utc TEXT    NOT NULL,
    referees       INTEGER NOT NULL,     -- how many were listed (0 = not yet)
    names          TEXT,                 -- "A; B" when listed
    PRIMARY KEY (game_id, checked_at)
);
