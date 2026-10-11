-- NHL corrections after a game (docs/models_v2_notes.md, amendment N-3):
-- live games are read again once a day for 10 days and re-downloaded when
-- the NHL changed them. Both tables are a log, never rewritten.
--
-- backfill_state gets a fourth status, 'stale': a step's result that an NHL
-- correction made obsolete. Not 'done', so the step runs again.
--
-- One row per check of a game.
--   age_days  date of the run (UTC) minus game_date
--   action    same          nothing stored differs from the NHL now
--             refreshed     something differs and the fresh feed agrees with
--                           itself: the game's steps were marked 'stale' and
--                           the same daily run downloaded it again
--             inconsistent  something differs but the fresh feed fails the
--                           usual checks (a correction in progress): nothing
--                           changed, tried again the next day
--             unfinished    the box score is no longer final
--             error         the download failed (retried at the next run)
--   n_diff    values that differ
CREATE TABLE stat_checks (
    game_id     INTEGER NOT NULL REFERENCES games(game_id),
    checked_at  TEXT    NOT NULL,     -- ISO UTC
    age_days    INTEGER NOT NULL,
    action      TEXT    NOT NULL CHECK (action IN
                    ('same', 'refreshed', 'inconsistent', 'unfinished', 'error')),
    n_diff      INTEGER NOT NULL,
    detail      TEXT,
    PRIMARY KEY (game_id, checked_at)
);

-- One row per value a refresh changed: as stored before -> as the NHL has it
-- now. field = the column (player_game_logs and player_shot_splits names
-- as they are, e.g. sog_reg; 'goalie.', 'team.', 'game.' and
-- 'penalty <event id>.' prefixes for the other tables). 'row' with the
-- same prefix ('splits.row' for player_shot_splits) = a row present on
-- one side only, 1 = present. The oldest sog_reg of a
-- player is the number his tickets were settled on (user's decision,
-- 11. 10. 2026).
CREATE TABLE stat_corrections (
    game_id     INTEGER NOT NULL REFERENCES games(game_id),
    checked_at  TEXT    NOT NULL,
    age_days    INTEGER NOT NULL,
    player_id   INTEGER,              -- NULL for team and game values
    team_id     INTEGER,
    field       TEXT    NOT NULL,
    old_value,                        -- no type on purpose: int, real or text as stored
    new_value
);
CREATE INDEX idx_corrections_game ON stat_corrections(game_id, player_id, field);
