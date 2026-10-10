-- Models v2 (docs/models_v2_plan.md, step 0): per player and game, 60
-- minutes only, from play-by-play:
--   att_reg       shot attempts = shots on goal + missed + blocked (the
--                 blocked shot belongs to the shooter); shootouts excluded
--   *_pp_reg      the part taken on the power play (the shooter's team has
--                 more skaters on the ice and both goalies are in net)
--   *_sh_reg      the part taken shorthanded
-- Even strength is the rest (sog_reg from player_game_logs minus pp, sh).
CREATE TABLE player_shot_splits (
    game_id     INTEGER NOT NULL REFERENCES games(game_id),
    player_id   INTEGER NOT NULL,
    team_id     INTEGER NOT NULL,
    att_reg     INTEGER NOT NULL,
    sog_pp_reg  INTEGER NOT NULL,
    att_pp_reg  INTEGER NOT NULL,
    sog_sh_reg  INTEGER NOT NULL,
    att_sh_reg  INTEGER NOT NULL,
    PRIMARY KEY (game_id, player_id)
);
CREATE INDEX idx_shot_splits_team ON player_shot_splits(team_id, game_id);
