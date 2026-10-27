import sqlite3
import pandas as pd

DB_PATH = "data/experiment.db"
EXPERIMENT_ID = "checkout_one_page_v1"

query = """
WITH variant_counts AS (
    SELECT user_id, COUNT(DISTINCT variant) AS variants
    FROM assignments
    WHERE experiment_id = ?
    GROUP BY user_id
),
cohort AS (
    SELECT
        a.user_id,
        a.variant,
        MIN(a.assigned_ts) AS assigned_ts,
        u.platform,
        u.country
    FROM assignments a
    JOIN variant_counts vc ON vc.user_id = a.user_id
    JOIN users u ON u.user_id = a.user_id
    WHERE a.experiment_id = ?
      AND vc.variants = 1
      AND u.is_bot = 0
    GROUP BY a.user_id, a.variant, u.platform, u.country
),
user_metrics AS (
    SELECT
        c.user_id,
        c.variant,
        c.assigned_ts,
        c.platform,
        c.country,
        COUNT(o.order_id) AS order_count,
        SUM(CASE WHEN o.order_id IS NOT NULL
                 AND o.refunded = 1 THEN 1 ELSE 0 END)
            AS refunded_order_count,
        COALESCE(SUM(o.revenue_usd), 0) AS revenue_usd,
        COALESCE(SUM(
            CASE WHEN o.refunded = 1
                 THEN o.revenue_usd ELSE 0 END
        ), 0) AS flagged_refund_revenue_usd
    FROM cohort c
    LEFT JOIN orders o
      ON o.user_id = c.user_id
     AND o.order_ts >= c.assigned_ts
     AND o.order_ts < datetime(c.assigned_ts, '+72 hours')
    GROUP BY
        c.user_id, c.variant, c.assigned_ts,
        c.platform, c.country
)
SELECT
    *,
    CASE WHEN order_count > 0 THEN 1 ELSE 0 END AS converted,
    revenue_usd - flagged_refund_revenue_usd
        AS revenue_excluding_flagged_refunds_usd
FROM user_metrics
ORDER BY variant, user_id
"""

with sqlite3.connect(DB_PATH) as conn:
    users = pd.read_sql_query(
        query, conn, params=(EXPERIMENT_ID, EXPERIMENT_ID)
    )

users["assigned_ts"] = pd.to_datetime(users["assigned_ts"])

summary = users.groupby("variant", as_index=False).agg(
    eligible_users=("user_id", "nunique"),
    converted_users=("converted", "sum"),
    total_orders=("order_count", "sum"),
    refunded_orders=("refunded_order_count", "sum"),
    total_revenue_usd=("revenue_usd", "sum"),
    revenue_excluding_flagged_refunds_usd=(
        "revenue_excluding_flagged_refunds_usd", "sum"
    )
)

summary["conversion_rate"] = (
    summary["converted_users"] / summary["eligible_users"]
)
summary["revenue_per_user_usd"] = (
    summary["total_revenue_usd"] / summary["eligible_users"]
)
summary["average_order_value_usd"] = (
    summary["total_revenue_usd"] / summary["total_orders"]
)
summary["order_refund_rate"] = (
    summary["refunded_orders"] / summary["total_orders"]
)

users.to_csv("experiment_user_metrics.csv", index=False)
summary.to_csv("experiment_variant_summary.csv", index=False)

print("Power BI exports created successfully.")
print(f"User-level rows: {len(users):,}")
print("\nVariant summary:")
print(summary.to_string(index=False))
print("\nFiles:")
print(" - experiment_user_metrics.csv")
print(" - experiment_variant_summary.csv")
print(
    "\nNote: Refund-adjusted revenue is provisional until the "
    "refund flag's business meaning is confirmed."
)
