import sqlite3

connection = sqlite3.connect("data/experiment.db")
cursor = connection.cursor()

tables = cursor.execute("""
    SELECT name
    FROM sqlite_master
    WHERE type = 'table'
    ORDER BY name
""").fetchall()

for (table_name,) in tables:
    print("\n" + "=" * 60)
    print(f"TABLE: {table_name}")

    columns = cursor.execute(
        f'PRAGMA table_info("{table_name}")'
    ).fetchall()

    print("\nColumns:")
    for column in columns:
        print(f"  {column[1]} | Type: {column[2]} | Primary Key: {column[5]}")

    row_count = cursor.execute(
        f'SELECT COUNT(*) FROM "{table_name}"'
    ).fetchone()[0]

    print(f"\nTotal rows: {row_count}")

    print("\nSample records:")
    for row in cursor.execute(
        f'SELECT * FROM "{table_name}" LIMIT 3'
    ).fetchall():
        print(row)

connection.close()
