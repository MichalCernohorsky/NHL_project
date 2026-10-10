-- Models v2, forward confirmation (docs/models_v2_plan.md section 5): from
-- the freeze of models/team_v2.json the block A expectation is written next
-- to version 1's, at the same moment and from the same past games, so that
-- after 300 games of 2026-27 the two can be compared on data neither saw.
ALTER TABLE team_predictions ADD COLUMN mu_v2 REAL;
ALTER TABLE team_predictions ADD COLUMN model_v2 TEXT;
