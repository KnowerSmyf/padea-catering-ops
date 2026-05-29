from __future__ import annotations

import argparse
from datetime import datetime, timezone, timedelta

from padea_ops.db import get_client, fetch_all, update_rows, upsert_rows


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_order(client, order_id: str) -> dict:
    rows = fetch_all(client, "orders", filters={"order_id": order_id}, limit=1)
    if not rows:
        raise ValueError(f"No order found with order_id={order_id}")
    return rows[0]


def create_exception(
    client,
    *,
    order_id: str,
    severity: str,
    exception_type: str,
    message: str,
) -> None:
    row = {
        "exception_id": f"{order_id}_{exception_type}",
        "source": "demo_order_lifecycle",
        "entity_type": "order",
        "entity_id": order_id,
        "severity": severity,
        "exception_type": exception_type,
        "message": message,
        "status": "open",
    }

    upsert_rows(client, "exceptions", [row], on_conflict="exception_id")


def approve(client, order_id: str) -> None:
    order = get_order(client, order_id)

    if order["status"] not in {"draft", "ready_for_review", "needs_review"}:
        raise ValueError(f"Cannot approve order from status={order['status']}")

    update_rows(
        client,
        "orders",
        {
            "status": "approved",
            "approved_at": now_iso(),
            "internal_notes": "Approved during lifecycle demo.",
        },
        {"order_id": order_id},
    )


def send(client, order_id: str, confirmation_minutes: int) -> None:
    order = get_order(client, order_id)

    if order["status"] != "approved":
        raise ValueError(f"Cannot send order from status={order['status']}; approve it first.")

    due_at = datetime.now(timezone.utc) + timedelta(minutes=confirmation_minutes)

    update_rows(
        client,
        "orders",
        {
            "status": "sent_to_caterer",
            "sent_at": now_iso(),
            "confirmation_due_at": due_at.isoformat(),
            "internal_notes": f"Sent during lifecycle demo. Confirmation due in {confirmation_minutes} minutes.",
        },
        {"order_id": order_id},
    )


def mark_overdue(client, order_id: str) -> None:
    order = get_order(client, order_id)

    if order.get("confirmed_at"):
        print("Order already confirmed; not marking overdue.")
        return

    if order["status"] not in {"sent_to_caterer", "approved"}:
        raise ValueError(f"Cannot mark overdue from status={order['status']}")

    update_rows(
        client,
        "orders",
        {
            "status": "confirmation_overdue",
            "failure_reason": "No caterer confirmation received by deadline.",
            "internal_notes": "Marked overdue during lifecycle demo.",
        },
        {"order_id": order_id},
    )

    create_exception(
        client,
        order_id=order_id,
        severity="high",
        exception_type="caterer_confirmation_overdue",
        message="Caterer has not confirmed the order by the confirmation deadline.",
    )


def require_backup(client, order_id: str) -> None:
    order = get_order(client, order_id)

    if order["status"] != "confirmation_overdue":
        raise ValueError(f"Can only require backup from confirmation_overdue, got status={order['status']}")

    update_rows(
        client,
        "orders",
        {
            "status": "backup_required",
            "failure_reason": order.get("failure_reason") or "Primary caterer did not confirm.",
            "internal_notes": "Backup caterer required. TODO: trigger SMS/email preference collection if backup profiles are missing.",
        },
        {"order_id": order_id},
    )

    create_exception(
        client,
        order_id=order_id,
        severity="high",
        exception_type="backup_caterer_required",
        message=(
            "Primary caterer did not confirm. Operator should select a backup caterer. "
            "TODO extension: send SMS/email preference form to affected families if backup caterer profiles are missing."
        ),
    )


def confirm(client, order_id: str) -> None:
    order = get_order(client, order_id)

    if order["status"] not in {"sent_to_caterer", "approved"}:
        raise ValueError(f"Cannot confirm order from status={order['status']}")

    update_rows(
        client,
        "orders",
        {
            "status": "confirmed",
            "confirmed_at": now_iso(),
            "internal_notes": "Confirmed during lifecycle demo.",
        },
        {"order_id": order_id},
    )


def deliver(client, order_id: str) -> None:
    order = get_order(client, order_id)

    if order["status"] != "confirmed":
        raise ValueError(f"Cannot mark delivered from status={order['status']}")

    update_rows(
        client,
        "orders",
        {
            "status": "delivered",
            "completed_at": now_iso(),
            "internal_notes": "Delivered/completed during lifecycle demo.",
        },
        {"order_id": order_id},
    )


def show(client, order_id: str) -> None:
    order = get_order(client, order_id)
    print("\nOrder state:")
    for key, value in order.items():
        print(f"  {key}: {value}")

    exceptions = fetch_all(client, "exceptions", filters={"entity_id": order_id})
    if exceptions:
        print("\nRelated exceptions:")
        for ex in exceptions:
            print(f"  [{ex['severity']}] {ex['exception_type']}: {ex['message']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Demo order confirmation lifecycle.")
    parser.add_argument(
        "action",
        choices=[
            "show",
            "approve",
            "send",
            "mark-overdue",
            "require-backup",
            "confirm",
            "deliver",
        ],
    )
    parser.add_argument("--order-id", required=True)
    parser.add_argument("--confirmation-minutes", type=int, default=1)
    args = parser.parse_args()

    client = get_client()

    if args.action == "show":
        show(client, args.order_id)
    elif args.action == "approve":
        approve(client, args.order_id)
        show(client, args.order_id)
    elif args.action == "send":
        send(client, args.order_id, args.confirmation_minutes)
        show(client, args.order_id)
    elif args.action == "mark-overdue":
        mark_overdue(client, args.order_id)
        show(client, args.order_id)
    elif args.action == "require-backup":
        require_backup(client, args.order_id)
        show(client, args.order_id)
    elif args.action == "confirm":
        confirm(client, args.order_id)
        show(client, args.order_id)
    elif args.action == "deliver":
        deliver(client, args.order_id)
        show(client, args.order_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# 1. After clearing the DB, we generate a set of orders
# python -m scripts.generate_weekly_orders --start 2026-05-01 --days 7 --write --replace

# 2. Then we pick an order and simulate review, approval, sending, overdue, and backup 
# python -m scripts.demo_order_lifecycle show --order-id order_2026_05_01_sess_loreto_college_monday
# python -m scripts.demo_order_lifecycle approve --order-id order_2026_05_01_sess_loreto_college_monday
# python -m scripts.demo_order_lifecycle send --order-id order_2026_05_01_sess_loreto_college_monday --confirmation-minutes 1
# python -m scripts.check_confirmation_deadlines --watch --interval 5
# python -m scripts.demo_order_lifecycle mark-overdue --order-id order_2026_05_01_sess_loreto_college_monday
# python -m scripts.demo_order_lifecycle require-backup --order-id order_2026_05_01_sess_loreto_college_monday