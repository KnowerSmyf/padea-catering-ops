from __future__ import annotations
import argparse
from padea_ops.config import load_settings
from padea_ops.db import get_client
from padea_ops.order_generation import generate_for_session, get_sessions_for_window, replace_generated_outputs
from padea_ops.email_templates import write_email_draft, write_distribution_sheet
from padea_ops.utils import parse_date, date_window

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly catering orders from Supabase state.")
    parser.add_argument("--start", required=True, help="Start date, YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true", help="Do not write generated orders to Supabase.")
    parser.add_argument("--write", action="store_true", help="Write generated orders to Supabase.")
    parser.add_argument("--replace", action="store_true", help="Replace deterministic generated order IDs.")
    args = parser.parse_args()

    if args.dry_run and args.write:
        raise ValueError("Use either --dry-run or --write, not both.")

    settings = load_settings()
    client = get_client()
    start, end = date_window(parse_date(args.start), args.days)

    sessions = get_sessions_for_window(client, start, end)
    print(f"Found {len(sessions)} active sessions from {start} to {end}")

    generated_orders = []
    for session in sessions:
        generated = generate_for_session(client, session)
        generated_orders.append(generated)

        email_path = write_email_draft(client, generated, settings.output_dir / "email_drafts")
        distribution_path = write_distribution_sheet(generated, settings.output_dir / "distribution_sheets")

        # session = generated.email_context.get("session") or {}
        school_id = session.get("school_id", "[school missing]")

        print()
        print(f"{generated.order['delivery_date']} | {school_id} | {generated.order['caterer_id']}")
        # print(f"{generated.order['delivery_date']} | {generated.order['school_id']} | {generated.order['caterer_id']}")
        print(f"  status: {generated.order['status']}")
        print(f"  meals: {sum(line['quantity'] for line in generated.order_lines)}")
        print(f"  order lines: {len(generated.order_lines)}")
        print(f"  student map: {len(generated.student_map)}")
        print(f"  exceptions: {len(generated.exceptions)}")
        print(f"  email: {email_path}")
        print(f"  distribution: {distribution_path}")

    if args.write:
        replace_generated_outputs(client, generated_orders)
        print("\nWrote generated outputs to Supabase.")
    else:
        print("\nDry run only. Use --write to save orders/exceptions to Supabase.")

    print("\nSummary")
    print("-------")
    print(f"orders: {len(generated_orders)}")
    print(f"meals: {sum(sum(line['quantity'] for line in g.order_lines) for g in generated_orders)}")
    print(f"exceptions: {sum(len(g.exceptions) for g in generated_orders)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
