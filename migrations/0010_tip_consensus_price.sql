-- The paper payout of a tip is the SIMULATED Tipsport price of plan D1:
-- 1 / (p * (1 + m)) with p = the market CONSENSUS of the tip's line and side
-- (median de-vig of the books, section 6.3), converted to 60 minutes.
-- Until 10. 10. 2026 the price was simulated from the book that gave the
-- tip its largest edge - the most favourable outlier - which overstated
-- the payout (on the phase 0 sample by ~0.04 in price, ~2 p.b. of ROI).
-- p_consensus is the corrected input; sim_price_bestbook keeps the old
-- value of tips written before the fix.
ALTER TABLE tips ADD COLUMN p_consensus REAL;
ALTER TABLE tips ADD COLUMN sim_price_bestbook REAL;
