-- Build the analysis population: one row per eligible, correctly-assigned user.
--
-- Exclusion rules (fixed in docs/experiment_plan.md before looking at outcomes):
--   1. exact duplicate assignment events are collapsed
--   2. users logged in BOTH arms (logging bug) are dropped: we can't tell
--      which experience they saw
--   3. users flagged by the bot-detection job are dropped
-- A user's assignment time is their first assignment event.

DROP TABLE IF EXISTS clean_assignments;

CREATE TABLE clean_assignments AS
WITH dedup AS (
    SELECT DISTINCT user_id, variant, assigned_ts
    FROM assignments
    WHERE experiment_id = 'checkout_one_page_v1'
),
conflicted AS (
    SELECT user_id
    FROM dedup
    GROUP BY user_id
    HAVING COUNT(DISTINCT variant) > 1
),
first_assignment AS (
    SELECT user_id, variant, MIN(assigned_ts) AS assigned_ts
    FROM dedup
    GROUP BY user_id, variant
)
SELECT
    f.user_id,
    f.variant,
    f.assigned_ts,
    DATE(f.assigned_ts) AS assigned_date,
    u.platform,
    u.country
FROM first_assignment AS f
JOIN users AS u USING (user_id)
WHERE u.is_bot = 0
  AND f.user_id NOT IN (SELECT user_id FROM conflicted);

CREATE UNIQUE INDEX idx_clean_user ON clean_assignments(user_id);
