import sqlite3

DB_PATH = "data/experiment.db"
EXPERIMENT_ID = "checkout_one_page_v1"

connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()

query = """
WITH user_variant_counts AS (
    SELECT user_id,
           COUNT(DISTINCT variant) AS variant_count
    FROM assignments
    WHERE experiment_id = ?
    GROUP BY user_id
),
valid_assignments AS (
    SELECT a.user_id,
           a.variant,
           MIN(a.assigned_ts) AS assigned_ts
    FROM assignments a
    JOIN user_variant_counts v
      ON a.user_id = v.user_id
    JOIN users u
      ON a.user_id = u.user_id
    WHERE a.experiment_id = ?
      AND v.variant_count = 1
      AND u.is_bot = 0
    GROUP BY a.user_id, a.variant
),
user_outcomes AS (
    SELECT
        a.user_id,
        a.variant,
        a.assigned_ts,
        EXISTS (
            SELECT 1
            FROM orders o
            WHERE o.user_id = a.user_id
              AND o.order_ts >= a.assigned_ts
              AND o.order_ts < datetime(a.assigned_ts, '+72 hours')
        ) AS converted,
        (
            SELECT COUNT(*)
            FROM orders o
            WHERE o.user_id = a.user_id
              AND o.order_ts >= a.assigned_ts
              AND o.order_ts < datetime(a.assigned_ts, '+72 hours')
        ) AS order_count,
        (
            SELECT COUNT(*)
            FROM orders o
            WHERE o.user_id = a.user_id
              AND o.order_ts >= a.assigned_ts
              AND o.order_ts < datetime(a.assigned_ts, '+72 hours')
              AND o.refunded = 1
        ) AS refunded_order_count
    FROM valid_assignments a
)
SELECT
    variant,
    COUNT(*) AS assigned_users,
    SUM(converted) AS converted_users,
    ROUND(100.0 * SUM(converted) / COUNT(*), 3) AS conversion_rate_pct,
    SUM(order_count) AS orders_within_72h,
    SUM(refunded_order_count) AS refunded_orders_within_72h
FROM user_outcomes
GROUP BY variant
ORDER BY variant;
"""

print("72-HOUR CHECKOUT A/B TEST RESULTS")
print("Bots and cross-variant users excluded")
print("=" * 75)

for row in cursor.execute(query, (EXPERIMENT_ID, EXPERIMENT_ID)):
    print(
        f"Variant: {row[0]}\n"
        f"  Eligible users: {row[1]:,}\n"
        f"  Converted users: {row[2]:,}\n"
        f"  Conversion rate: {row[3]}%\n"
        f"  Orders within 72 hours: {row[4]:,}\n"
        f"  Refunded orders within 72 hours: {row[5]:,}\n"
    )

connection.close()
