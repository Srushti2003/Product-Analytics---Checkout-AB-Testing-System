import sqlite3

connection = sqlite3.connect("data/experiment.db")
cursor = connection.cursor()

checks = [
    ("User signup dates", """
        SELECT MIN(signup_ts), MAX(signup_ts) FROM users
    """),
    ("Assignment dates", """
        SELECT MIN(assigned_ts), MAX(assigned_ts)
        FROM assignments
        WHERE experiment_id = 'checkout_one_page_v1'
    """),
    ("Session dates", """
        SELECT MIN(session_start_ts), MAX(session_start_ts)
        FROM sessions
    """),
    ("Order dates", """
        SELECT MIN(order_ts), MAX(order_ts) FROM orders
    """)
]

for label, query in checks:
    print(f"\n{label}:")
    print(cursor.execute(query).fetchone())

print("\nAssignments by variant and bot status:")
query = """
    SELECT a.variant, u.is_bot, COUNT(DISTINCT a.user_id)
    FROM assignments a
    JOIN users u ON u.user_id = a.user_id
    WHERE a.experiment_id = 'checkout_one_page_v1'
    GROUP BY a.variant, u.is_bot
    ORDER BY a.variant, u.is_bot
"""
for row in cursor.execute(query):
    print(row)

connection.close()
