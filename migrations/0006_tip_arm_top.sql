-- TOP of the day (docs/tips_plan.md section 8): at most 3 playable tips
-- with the largest edge among tips without the > 10 p.b. warning, one per
-- game. Written when the tips are built, never edited afterwards.
ALTER TABLE tips ADD COLUMN arm_top INTEGER NOT NULL DEFAULT 0;
