-- Team rosters as published by the NHL API (/v1/roster/{team}/{season}),
-- one row per (season, team, player) with the first and last day it was
-- seen. Used to match sportsbook names to player ids for players who have
-- not (yet) appeared in a box score for that team: summer trades, injured
-- stars returning, rookies before their debut.
--
-- A roster is a PRE-GAME fact only in the sense of "on the team"; it says
-- nothing about who dresses tonight (scratches are post-game).

CREATE TABLE rosters (
    season      TEXT    NOT NULL,
    team_id     INTEGER NOT NULL REFERENCES teams(team_id),
    player_id   INTEGER NOT NULL,
    position    TEXT,
    first_seen  TEXT    NOT NULL,     -- ISO date of the first sync that listed him
    last_seen   TEXT    NOT NULL,
    PRIMARY KEY (season, team_id, player_id)
);
CREATE INDEX idx_rosters_player ON rosters(player_id);
