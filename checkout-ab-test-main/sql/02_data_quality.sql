-- Funnel from raw assignment events to the analysis population, by arm.
-- Run this BEFORE looking at any outcome metric.

WITH raw_events AS (
    SELECT variant, COUNT(*) AS n
    FROM assignments
    GROUP BY variant
),
distinct_events AS (
    SELECT variant, COUNT(*) AS n
    FROM (SELECT DISTINCT user_id, variant, assigned_ts FROM assignments)
    GROUP BY variant
),
user_arms AS (
    SELECT user_id, MIN(variant) AS variant, COUNT(DISTINCT variant) AS n_arms
    FROM assignments
    GROUP BY user_id
),
all_users AS (
    SELECT a.variant, a.n_arms, u.is_bot
    FROM user_arms AS a
    JOIN users AS u USING (user_id)
)
SELECT 'raw assignment events'      AS step, variant, n FROM raw_events
UNION ALL
SELECT 'after de-duplication',            variant, n FROM distinct_events
UNION ALL
SELECT 'users assigned to both arms',     'both', COUNT(*) FROM all_users WHERE n_arms > 1
UNION ALL
SELECT 'bot users (single arm)',          variant, COUNT(*) FROM all_users WHERE n_arms = 1 AND is_bot = 1 GROUP BY variant
UNION ALL
SELECT 'analysis population',             variant, COUNT(*) FROM clean_assignments GROUP BY variant
ORDER BY step, variant;
