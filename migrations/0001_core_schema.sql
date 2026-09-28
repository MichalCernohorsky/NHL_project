-- Core schema: teams, players, games, per-game logs (skaters, goalies,
-- teams), scratches, and backfill_state for resumable backfills.
--
-- Units: time on ice is stored in SECONDS (INTEGER). The NHL API reports
-- "MM:SS" strings in box scores and seconds in the stats REST API; one unit
-- in the database avoids a whole class of silent 60x errors.
--
-- Leakage note: everything in the *_game_logs tables is POST-GAME truth
-- (who actually started in goal, who was scratched). None of it may be read
-- as a pre-game attribute for the same game. Morning information (confirmed
-- goalie, projected lines) gets its own snapshot tables with a timestamp.

CREATE TABLE teams (
    team_id      INTEGER PRIMARY KEY,   -- NHL API team id
    abbreviation TEXT NOT NULL,         -- not UNIQUE: franchises move/rename (ARI -> UTA)
    full_name    TEXT NOT NULL
);

CREATE TABLE players (
    player_id    INTEGER PRIMARY KEY,   -- NHL API player id
    full_name    TEXT,                  -- 'John Gibson'; filled by backfill_players / TOI step
    short_name   TEXT,                  -- 'J. Gibson' as printed in box scores
    position     TEXT,                  -- C / L / R / D / G
    shoots       TEXT,                  -- L / R (shootsCatches)
    birth_date   TEXT
);
CREATE INDEX idx_players_name ON players(full_name);

CREATE TABLE games (
    game_id           INTEGER PRIMARY KEY,  -- e.g. 2025020010 (season, type 02 = regular, number)
    season            TEXT NOT NULL,        -- '2025-26'
    season_type       TEXT NOT NULL CHECK (season_type IN ('preseason', 'regular', 'playoffs')),
    game_date         TEXT NOT NULL,        -- local (US/Eastern) date as the NHL publishes it
    start_time_utc    TEXT,                 -- puck drop, ISO-8601 UTC
    home_team_id      INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id      INTEGER NOT NULL REFERENCES teams(team_id),
    home_score        INTEGER,
    away_score        INTEGER,
    -- 'REG' / 'OT' / 'SO'. Markets differ in whether they count OT and the
    -- shootout, so every settlement needs to know how the game ended.
    last_period_type  TEXT CHECK (last_period_type IN ('REG', 'OT', 'SO')),
    game_state        TEXT,                 -- FUT / PRE / LIVE / FINAL / OFF / ...
    schedule_state    TEXT,                 -- OK / PPD (postponed) / CNCL
    neutral_site      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_games_date ON games(game_date);
CREATE INDEX idx_games_season ON games(season, season_type);

CREATE TABLE player_game_logs (
    game_id         INTEGER NOT NULL REFERENCES games(game_id),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    position        TEXT,
    toi_s           INTEGER,     -- total time on ice, seconds (box score)
    ev_toi_s        INTEGER,     -- even strength (stats REST, backfill_toi)
    pp_toi_s        INTEGER,     -- power play   (stats REST, backfill_toi)
    sh_toi_s        INTEGER,     -- short-handed (stats REST, backfill_toi)
    ot_toi_s        INTEGER,     -- overtime     (stats REST, backfill_toi)
    shifts          INTEGER,
    goals           INTEGER,
    assists         INTEGER,
    points          INTEGER,
    sog             INTEGER,     -- shots on goal (box score; OT included, shootout not)
    blocked_shots   INTEGER,
    hits            INTEGER,
    pim             INTEGER,
    plus_minus      INTEGER,
    pp_goals        INTEGER,
    giveaways       INTEGER,
    takeaways       INTEGER,
    faceoff_pct     REAL,
    PRIMARY KEY (game_id, player_id)
);
CREATE INDEX idx_pgl_player ON player_game_logs(player_id, game_id);

CREATE TABLE goalie_game_logs (
    game_id         INTEGER NOT NULL REFERENCES games(game_id),
    player_id       INTEGER NOT NULL REFERENCES players(player_id),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    started         INTEGER NOT NULL,   -- POST-GAME fact, never a pre-game attribute
    toi_s           INTEGER,
    shots_against   INTEGER,
    saves           INTEGER,
    goals_against   INTEGER,
    ev_shots_against INTEGER,
    pp_shots_against INTEGER,           -- shots faced while HIS team was short-handed
    sh_shots_against INTEGER,
    decision        TEXT,               -- W / L / O / NULL
    PRIMARY KEY (game_id, player_id)
);

CREATE TABLE team_game_logs (
    game_id         INTEGER NOT NULL REFERENCES games(game_id),
    team_id         INTEGER NOT NULL REFERENCES teams(team_id),
    is_home         INTEGER NOT NULL,
    goals           INTEGER,
    sog             INTEGER,
    -- xG and PP opportunities come from MoneyPuck / right-rail in phase 1.
    xg              REAL,
    pp_opportunities INTEGER,
    PRIMARY KEY (game_id, team_id)
);

-- Healthy/injured scratches as printed on the game page (right-rail).
-- POST-GAME list: who did not dress. Not a morning lineup.
CREATE TABLE scratches (
    game_id    INTEGER NOT NULL REFERENCES games(game_id),
    team_id    INTEGER NOT NULL REFERENCES teams(team_id),
    player_id  INTEGER NOT NULL,
    full_name  TEXT,
    PRIMARY KEY (game_id, player_id)
);

CREATE TABLE backfill_state (
    task       TEXT NOT NULL,
    key        TEXT NOT NULL,
    status     TEXT NOT NULL,          -- done / missing / error
    detail     TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (task, key)
);
