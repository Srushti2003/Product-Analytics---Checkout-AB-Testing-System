-- Order-level guardrails: average order value and refund rate by arm.
-- These are ratio metrics (per order, not per user), so the Python side
-- uses the delta method for their standard errors.

SELECT
    a.variant,
    COUNT(*)                          AS orders,
    ROUND(AVG(o.revenue_usd), 2)      AS avg_order_value,
    ROUND(AVG(o.refunded) * 100, 2)   AS refund_rate_pct
FROM orders AS o
JOIN clean_assignments AS a USING (user_id)
WHERE o.order_ts >= a.assigned_ts
  AND o.order_ts <  DATETIME(a.assigned_ts, '+7 days')
GROUP BY a.variant;
