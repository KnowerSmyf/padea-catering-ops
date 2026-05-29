from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from padea_ops.db import get_client, fetch_all, update_rows, upsert_rows


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_ts(value: str):
    if not value:
        return None

    text = str(value).replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def create_exception(client, order_id: str) -> None:
    row = {
        "exception_id": f"{order_id}_caterer_confirmation_overdue",
        "source": "check_confirmation_deadlines",
        "entity_type": "order",
        "entity_id": order_id,
        "severity": "high",
        "exception_type": "caterer_confirmation_overdue",
        "message": "Caterer has not confirmed the order by the confirmation deadline.",
        "status": "open",
    }

    upsert_rows(client, "exceptions", [row], on_conflict="exception_id")


def check_once(client) -> int:
    orders = fetch_all(client, "orders", filters={"status": "sent_to_caterer"})

    overdue_count = 0
    now = datetime.now(timezone.utc)

    for order in orders:
        if order.get("confirmed_at"):
            continue

        due_at = parse_ts(order.get("confirmation_due_at"))

        if due_at is None:
            continue

        if due_at <= now:
            order_id = order["order_id"]

            update_rows(
                client,
                "orders",
                {
                    "status": "confirmation_overdue",
                    "failure_reason": "No caterer confirmation received by deadline.",
                    "internal_notes": "Automatically marked overdue by confirmation deadline checker.",
                },
                {"order_id": order_id},
            )

            create_exception(client, order_id)
            overdue_count += 1

            print(f"Marked overdue: {order_id}")

    return overdue_count


def main() -> int:
    parser = argparse.ArgumentParser(description="Automatically mark unconfirmed caterer orders as overdue.")
    parser.add_argument("--watch", action="store_true", help="Run repeatedly for demo purposes.")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between checks in watch mode.")
    args = parser.parse_args()

    client = get_client()

    if not args.watch:
        count = check_once(client)
        print(f"Overdue orders marked: {count}")
        return 0

    print(f"Watching for overdue orders every {args.interval} seconds. Press Ctrl+C to stop.")

    while True:
        count = check_once(client)
        if count:
            print(f"Overdue orders marked this cycle: {count}")
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())