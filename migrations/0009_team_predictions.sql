-- Team markets plan, stage 2 (docs/team_markets_plan.md section 6,
-- amendment T-5): the frozen naive team models' expectation for both teams
-- of every game of the day, written ONCE before puck drop. The dashboard
-- derives P(over line) and the minimum Tipsport price from mu; the user's
-- tickets live in the bets store, not here. actual_60 is filled after the
-- game from the 60-minute counts (S-T: skaters' sog_reg; T-T: rule T-1).

CREATE TABLE team_predictions (
    game_id        INTEGER NOT NULL REFERENCES games(game_id),
    team_id        INTEGER NOT NULL,
    market         TEXT    NOT NULL CHECK (market IN ('S-T', 'T-T')),
    game_date      TEXT    NOT NULL,
    start_time_utc TEXT,
    opp_id         INTEGER NOT NULL,
    is_home        INTEGER NOT NULL,
    mu             REAL    NOT NULL,     -- expected count in 60 minutes
    model          TEXT    NOT NULL,     -- naive_team_v1 / naive_team_v1+tt_cal
    f_league       REAL,                 -- what the model used (display only)
    f_attack       REAL,
    f_defence      REAL,                 -- the opponent's defence factor
    f_n            INTEGER,              -- games of the season behind the form
    built_at       TEXT    NOT NULL,
    actual_60      INTEGER,
    settled_at     TEXT,
    PRIMARY KEY (game_id, team_id, market)
);
CREATE INDEX idx_team_predictions_date ON team_predictions(game_date);
