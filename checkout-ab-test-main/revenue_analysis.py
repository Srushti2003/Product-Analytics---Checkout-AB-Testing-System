import sqlite3

DB_PATH = "data/experiment.db"
EXPERIMENT_ID = "checkout_one_page_v1"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

query = """
WITH variant_counts AS (
    SELECT user_id, COUNT(DISTINCT variant) AS variants
    FROM assignments
    WHERE experiment_id = ?
    GROUP BY user_id
),
cohort AS (
    SELECT a.user_id, a.variant, MIN(a.assigned_ts) AS assigned_ts
    FROM assignments a
    JOIN variant_counts v ON v.user_id = a.user_id
    JOIN users u ON u.user_id = a.user_id
    WHERE a.experiment_id = ?
      AND v.variants = 1
      AND u.is_bot = 0
    GROUP BY a.user_id, a.variant
),
outcomes AS (
    SELECT
        c.user_id,
        c.variant,
        COUNT(o.order_id) AS orders,
        COALESCE(SUM(o.revenue_usd), 0) AS recorded_revenue,
        COALESCE(SUM(
            CASE WHEN o.refunded = 1 THEN o.revenue_usd ELSE 0 END
        ), 0) AS flagged_refund_revenue,
        COALESCE(SUM(
            CASE WHEN o.refunded = 1 THEN 1 ELSE 0 END
        ), 0) AS refunded_orders
    FROM cohort c
    LEFT JOIN orders o
      ON o.user_id = c.user_id
     AND o.order_ts >= c.assigned_ts
     AND o.order_ts < datetime(c.assigned_ts, '+72 hours')
    GROUP BY c.user_id, c.variant
)
SELECT
    variant,
    COUNT(*) AS assigned_users,
    SUM(orders) AS orders,
    ROUND(SUM(recorded_revenue), 2) AS recorded_revenue_usd,
    ROUND(SUM(flagged_refund_revenue), 2) AS flagged_refund_revenue_usd,
    ROUND(
        SUM(recorded_revenue - flagged_refund_revenue), 2
    ) AS revenue_excluding_flagged_refunds_usd,
    SUM(refunded_orders) AS refunded_orders,
    ROUND(100.0 * SUM(refunded_orders) / NULLIF(SUM(orders), 0), 3)
        AS order_refund_rate_pct,
    ROUND(1.0 * SUM(recorded_revenue) / COUNT(*), 4)
        AS recorded_revenue_per_assigned_user_usd,
    ROUND(
        1.0 * SUM(recorded_revenue) / NULLIF(SUM(orders), 0), 2
    ) AS average_order_value_usd
FROM outcomes
GROUP BY variant
ORDER BY variant;
"""

print("REVENUE ANALYSIS — 72-HOUR WINDOW")
print("=" * 72)

for row in cursor.execute(query, (EXPERIMENT_ID, EXPERIMENT_ID)):
    labels = [
        "Variant",
        "Eligible users",
        "Orders",
        "Recorded revenue ($)",
        "Revenue on flagged-refund orders ($)",
        "Revenue excluding flagged-refund orders ($)",
        "Refunded orders",
        "Order refund rate (%)",
        "Revenue per assigned user ($)",
        "Average order value ($)"
    ]

    for label, value in zip(labels, row):
        if isinstance(value, (int, float)) and label != "Eligible users":
            print(f"{label}: {value:,.4f}" if isinstance(value, float)
                  else f"{label}: {value:,}")
        else:
            print(f"{label}: {value}")
    print()

connection.close()
