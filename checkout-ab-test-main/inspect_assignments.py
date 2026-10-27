import sqlite3

connection = sqlite3.connect("data/experiment.db")
cursor = connection.cursor()

queries = [
    (
        "Assignment records per user",
        """
        SELECT assignment_count, COUNT(*)
        FROM (
            SELECT user_id, COUNT(*) AS assignment_count
            FROM assignments
            GROUP BY user_id
        )
        GROUP BY assignment_count
        ORDER BY assignment_count
        """
    ),
    (
        "Duplicate rows per user and experiment",
        """
        SELECT duplicate_count, COUNT(*)
        FROM (
            SELECT user_id, experiment_id, COUNT(*) AS duplicate_count
            FROM assignments
            GROUP BY user_id, experiment_id
        )
        GROUP BY duplicate_count
        ORDER BY duplicate_count
        """
    ),
    (
        "Distinct orders before earliest assignment",
        """
        WITH first_assignment AS (
            SELECT user_id, MIN(assigned_ts) AS assigned_ts
            FROM assignments
            WHERE experiment_id = 'checkout_one_page_v1'
            GROUP BY user_id
        )
        SELECT COUNT(DISTINCT o.order_id)
        FROM orders o
        JOIN first_assignment a ON o.user_id = a.user_id
        WHERE o.order_ts < a.assigned_ts
        """
    ),
    (
        "Distinct users assigned to multiple variants",
        """
        SELECT COUNT(*)
        FROM (
            SELECT user_id
            FROM assignments
            WHERE experiment_id = 'checkout_one_page_v1'
            GROUP BY user_id
            HAVING COUNT(DISTINCT variant) > 1
        )
        """
    ),
    (
        "Assignment variants and repeated records",
        """
        SELECT variant, COUNT(*) AS rows,
               COUNT(DISTINCT user_id) AS distinct_users
        FROM assignments
        WHERE experiment_id = 'checkout_one_page_v1'
        GROUP BY variant
        ORDER BY variant
        """
    )
]

for title, query in queries:
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)
    for row in cursor.execute(query):
        print(row)

connection.close()
