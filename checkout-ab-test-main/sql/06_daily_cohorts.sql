-- Conversion by enrollment-day cohort, split by user type.
-- If the lift shrinks for later cohorts among RETURNING users (who know the
-- old checkout) but not among NEW users, that's a novelty effect.

WITH m AS (
    SELECT
        a.user_id,
        a.variant,
        a.assigned_date,
        CASE WHEN EXISTS (
            SELECT 1 FROM sessions AS s
            WHERE s.user_id = a.user_id
              AND s.session_start_ts <  a.assigned_ts
              AND s.session_start_ts >= DATETIME(a.assigned_ts, '-28 days')
        ) THEN 'returning' ELSE 'new' END AS user_type,
        CASE WHEN EXISTS (
            SELECT 1 FROM orders AS o
            WHERE o.user_id = a.user_id
              AND o.order_ts >= a.assigned_ts
              AND o.order_ts <  DATETIME(a.assigned_ts, '+7 days')
        ) THEN 1 ELSE 0 END AS converted
    FROM clean_assignments AS a
)
SELECT
    assigned_date,
    user_type,
    variant,
    COUNT(*)        AS users,
    SUM(converted)  AS conversions
FROM m
GROUP BY assigned_date, user_type, variant
ORDER BY assigned_date, user_type, variant;
