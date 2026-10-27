import sqlite3

connection = sqlite3.connect("data/experiment.db")
cursor = connection.cursor()

checks = {
    "Total users": "SELECT COUNT(*) FROM users",
    "Distinct assigned users": "SELECT COUNT(DISTINCT user_id) FROM assignments",
    "Duplicate assignment rows": """
        SELECT COUNT(*) FROM (
            SELECT user_id, experiment_id
            FROM assignments
            GROUP BY user_id, experiment_id
            HAVING COUNT(*) > 1
        )
    """,
    "Users marked as bots": "SELECT COUNT(*) FROM users WHERE is_bot = 1",
    "Orders with no matching user": """
        SELECT COUNT(*) FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE u.user_id IS NULL
    """,
    "Sessions with no matching user": """
        SELECT COUNT(*) FROM sessions s
        LEFT JOIN users u ON s.user_id = u.user_id
        WHERE u.user_id IS NULL
    """,
    "Orders before assignment": """
        SELECT COUNT(*)
        FROM orders o
        JOIN assignments a ON o.user_id = a.user_id
        WHERE o.order_ts < a.assigned_ts
    """,
    "Users with multiple experiment variants": """
        SELECT COUNT(*) FROM (
            SELECT user_id
            FROM assignments
            GROUP BY user_id
            HAVING COUNT(DISTINCT variant) > 1
        )
    """
}

print("=" * 60)
print("DATA QUALITY CHECKS")
print("=" * 60)

for label, query in checks.items():
    result = cursor.execute(query).fetchone()[0]
    print(f"{label}: {result:,}")

print("\nASSIGNMENTS BY EXPERIMENT AND VARIANT")
for row in cursor.execute("""
    SELECT experiment_id, variant, COUNT(*)
    FROM assignments
    GROUP BY experiment_id, variant
    ORDER BY experiment_id, variant
"""):
    print(row)

print("\nUSERS BY PLATFORM")
for row in cursor.execute("""
    SELECT platform, COUNT(*)
    FROM users
    GROUP BY platform
    ORDER BY platform
"""):
    print(row)

print("\nREFUND FLAG COUNTS")
for row in cursor.execute("""
    SELECT refunded, COUNT(*)
    FROM orders
    GROUP BY refunded
    ORDER BY refunded
"""):
    print(row)

connection.close()
