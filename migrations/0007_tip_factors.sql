-- What the model used for a tip, stored with it so the game page ("Rozbor
-- zápasu") explains the very numbers the tip was built from:
--   mu_60 = rate * toi_l10 * opp_factor
ALTER TABLE tips ADD COLUMN f_rate_60 REAL;        -- shrunk shots per 60 min of ice
ALTER TABLE tips ADD COLUMN f_prior_60 REAL;       -- prior rate (last season or position)
ALTER TABLE tips ADD COLUMN f_season_shots REAL;   -- regulation shots this season before the game
ALTER TABLE tips ADD COLUMN f_season_toi_min REAL; -- regulation ice time this season, minutes
ALTER TABLE tips ADD COLUMN f_toi_l10_min REAL;    -- mean regulation TOI, last 10 games
ALTER TABLE tips ADD COLUMN f_opp_factor REAL;     -- opponent factor o
ALTER TABLE tips ADD COLUMN f_opp_mean REAL;       -- shots the opponent allowed per game (L20)
ALTER TABLE tips ADD COLUMN f_opp_n INTEGER;       -- games in that window
ALTER TABLE tips ADD COLUMN pos_group TEXT;        -- F / D
