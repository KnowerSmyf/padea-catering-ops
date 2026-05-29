from __future__ import annotations
import argparse
from datetime import datetime, timezone
from padea_ops.db import get_client, fetch_all, update_rows

def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate a student preference update.")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--caterer-id", required=True)
    parser.add_argument("--preferred-menu-item-id", required=True)
    parser.add_argument("--backup-menu-item-id")
    args = parser.parse_args()

    client = get_client()
    filters = {"student_id": args.student_id, "caterer_id": args.caterer_id}

    print("\nBefore:")
    print(fetch_all(client, "student_food_profiles", filters=filters, limit=1))

    values = {
        "preferred_menu_item_id": args.preferred_menu_item_id,
        "preference_notes": "Demo update: preference changed through simulated form/email workflow.",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    if args.backup_menu_item_id:
        values["backup_menu_item_id"] = args.backup_menu_item_id

    print("\nUpdated:")
    print(update_rows(client, "student_food_profiles", values, filters))

    print("\nAfter:")
    print(fetch_all(client, "student_food_profiles", filters=filters, limit=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# python -m scripts.demo_update_preferences --student-id stu_alexander_johnson_indooroopilly_state_high_school --caterer-id cat_kenko_sushi_house --preferred-menu-item-id menu_kenko_sushi_house_04
# python -m scripts.demo_update_preferences --student-id stu_alexander_johnson_indooroopilly_state_high_school --caterer-id cat_kenko_sushi_house --preferred-menu-item-id menu_kenko_sushi_house_12
