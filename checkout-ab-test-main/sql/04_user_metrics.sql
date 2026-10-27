-- One row per analysis user: outcomes in a fixed 7-day window after
-- assignment, plus pre-period covariates from the 28 days BEFORE assignment
-- (used for CUPED variance reduction; they can't be affected by treatment).
--
-- A fixed per-user window means users who enrolled late aren't
-- under-counted relative to users who enrolled early.

WITH experiment_orders AS (
    SELECT
        o.user_id,
        COUNT(*)                                          AS orders,
        SUM(o.revenue_usd)                                AS revenue,
        SUM(o.refunded)                                   AS refunded_orders,
        SUM(CASE WHEN o.refunded = 0 THEN o.revenue_usd ELSE 0 END) AS net_revenue
    FROM orders AS o
    JOIN clean_assignments AS a USING (user_id)
    WHERE o.order_ts >= a.assigned_ts
      AND o.order_ts <  DATETIME(a.assigned_ts, '+7 days')
    GROUP BY o.user_id
),
experiment_sessions AS (
    SELECT s.user_id, COUNT(*) AS sessions
    FROM sessions AS s
    JOIN clean_assignments AS a USING (user_id)
    WHERE s.session_start_ts >= a.assigned_ts
      AND s.session_start_ts <  DATETIME(a.assigned_ts, '+7 days')
    GROUP BY s.user_id
),
pre_orders AS (
    SELECT o.user_id, COUNT(*) AS pre_orders, SUM(o.revenue_usd) AS pre_revenue
    FROM orders AS o
    JOIN clean_assignments AS a USING (user_id)
    WHERE o.order_ts <  a.assigned_ts
      AND o.order_ts >= DATETIME(a.assigned_ts, '-28 days')
    GROUP BY o.user_id
),
pre_sessions AS (
    SELECT s.user_id, COUNT(*) AS pre_sessions
    FROM sessions AS s
    JOIN clean_assignments AS a USING (user_id)
    WHERE s.session_start_ts <  a.assigned_ts
      AND s.session_start_ts >= DATETIME(a.assigned_ts, '-28 days')
    GROUP BY s.user_id
)
SELECT
    a.user_id,
    a.variant,
    a.assigned_date,
    a.platform,
    a.country,
    CASE WHEN COALESCE(ps.pre_sessions, 0) = 0 THEN 'new' ELSE 'returning' END AS user_type,
    COALESCE(ps.pre_sessions, 0)       AS pre_sessions,
    COALESCE(po.pre_orders, 0)         AS pre_orders,
    COALESCE(po.pre_revenue, 0)        AS pre_revenue,
    COALESCE(es.sessions, 0)           AS sessions,
    COALESCE(eo.orders, 0)             AS orders,
    CASE WHEN eo.orders > 0 THEN 1 ELSE 0 END AS converted,
    COALESCE(eo.revenue, 0)            AS revenue,
    COALESCE(eo.net_revenue, 0)        AS net_revenue,
    COALESCE(eo.refunded_orders, 0)    AS refunded_orders
FROM clean_assignments AS a
LEFT JOIN experiment_orders   AS eo USING (user_id)
LEFT JOIN experiment_sessions AS es USING (user_id)
LEFT JOIN pre_orders          AS po USING (user_id)
LEFT JOIN pre_sessions        AS ps USING (user_id)
ORDER BY a.user_id;
