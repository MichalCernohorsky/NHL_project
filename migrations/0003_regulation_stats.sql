-- Regulation-only (60 min, periods 1-3) counts from play-by-play.
--
-- Tipsport settles player statistics on 60 minutes WITHOUT overtime; US
-- books (FanDuel) include overtime. Box scores give full-game counts only,
-- so every Tipsport-facing settlement needs these columns
-- (docs/market_discovery_plan.md, amendment D3). NULL = play-by-play not
-- loaded yet, never "zero".

ALTER TABLE player_game_logs ADD COLUMN sog_reg INTEGER;
ALTER TABLE player_game_logs ADD COLUMN blocked_shots_reg INTEGER;
ALTER TABLE goalie_game_logs ADD COLUMN shots_against_reg INTEGER;
ALTER TABLE goalie_game_logs ADD COLUMN saves_reg INTEGER;
