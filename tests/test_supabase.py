from padea_ops.db import get_client, fetch_all

client = get_client()

for table in ["students", "sessions", "menu_items", "student_food_profiles"]:
    print(f"\n--- {table} ---")
    rows = fetch_all(client, table, limit=3)
    for row in rows:
        print(row)
