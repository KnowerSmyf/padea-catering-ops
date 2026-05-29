from __future__ import annotations

import argparse
from pathlib import Path

from padea_ops.db import get_client, fetch_all
from padea_ops.order_generation import generate_for_session
from padea_ops.email_templates import write_email_draft, write_distribution_sheet
from padea_ops.config import load_settings


def get_session(client, session_id: str) -> dict:
    rows = fetch_all(client, "sessions", filters={"session_id": session_id}, limit=1)
    if not rows:
        raise ValueError(f"No session found with session_id={session_id}")
    return rows[0]


def get_backup_caterers(client, school_id: str, current_caterer_id: str) -> list[dict]:
    capacity = fetch_all(
        client,
        "caterer_school_capacity",
        filters={"school_id": school_id, "relationship_type": "able_to_serve"},
    )

    backup_ids = {
        row["caterer_id"]
        for row in capacity
        if row.get("caterer_id") != current_caterer_id
    }

    caterers = fetch_all(client, "caterers")

    return [
        c for c in caterers
        if c.get("caterer_id") in backup_ids
    ]


def get_order(client, order_id: str) -> dict:
    rows = fetch_all(client, "orders", filters={"order_id": order_id}, limit=1)
    if not rows:
        raise ValueError(f"No order found with order_id={order_id}")
    return rows[0]


def students_missing_backup_profiles(client, generated_order, backup_caterer_id: str) -> list[dict]:
    profiles = fetch_all(
        client,
        "student_food_profiles",
        filters={"caterer_id": backup_caterer_id},
    )
    profile_student_ids = {p["student_id"] for p in profiles}

    students = generated_order.email_context.get("students", [])

    return [
        s for s in students
        if s.get("student_id") not in profile_student_ids
    ]


def write_backup_outreach(
    *,
    output_dir: Path,
    session: dict,
    backup_caterer: dict,
    missing_students: list[dict],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    path = output_dir / f"backup_outreach_{session['session_id']}_{backup_caterer['caterer_id']}.md"

    lines = [
        f"# Backup caterer preference request",
        "",
        f"Session: {session['session_id']}",
        f"School: {session['school_id']}",
        f"Date: {str(session['session_date'])[:10]}",
        f"Backup caterer: {backup_caterer['name']}",
        "",
        "The following students do not yet have a stored food profile for this backup caterer.",
        "In production, send these families a one-off prefilled preference form.",
        "",
    ]

    for student in missing_students:
        lines.append(f"- {student.get('full_name')} | parent: {student.get('parent_email')}")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# def main() -> int:
#     parser = argparse.ArgumentParser(description="Simulate primary caterer failure and backup caterer flow.")
#     parser.add_argument("--order-id", help="Existing overdue/backup-required order ID.")
#     parser.add_argument("--session-id", help="Session ID, if running backup flow directly from a session.")
#     parser.add_argument("--backup-caterer-id", help="Optional. If omitted, use first available backup.")
#     args = parser.parse_args()

#     if not args.order_id and not args.session_id:
#         raise ValueError("Provide either --order-id or --session-id.")

#     settings = load_settings()
#     client = get_client()

#     if args.order_id:
#         original_order = get_order(client, args.order_id)
#         original_session = get_session(client, original_order["session_id"])
#         current_caterer_id = original_order["caterer_id"]
#         original_order_id = original_order["order_id"]
#     else:
#         original_order = None
#         original_session = get_session(client, args.session_id)
#         current_caterer_id = original_session["caterer_id"]
#         original_order_id = None
        
#     school_id = original_session["school_id"]

#     backups = get_backup_caterers(client, school_id, current_caterer_id)

#     print(f"Primary caterer: {current_caterer_id}")
#     print(f"Backup candidates for {school_id}:")
#     for c in backups:
#         print(f"  - {c['caterer_id']} | {c['name']}")

#     if not backups:
#         print("No backup caterers available.")
#         return 0

#     if args.backup_caterer_id:
#         selected = next((c for c in backups if c["caterer_id"] == args.backup_caterer_id), None)
#         if selected is None:
#             raise ValueError(f"{args.backup_caterer_id} is not an available backup for {school_id}")
#     else:
#         selected = backups[0]

#     print(f"\nSelected backup caterer: {selected['name']}")

#     backup_session = dict(original_session)
#     backup_session["caterer_id"] = selected["caterer_id"]

#     generated = generate_for_session(client, backup_session)

#     for i, line in enumerate(generated.order_lines, start=1):
#         line["order_id"] = generated.order["order_id"]
#         line["order_line_id"] = f"{generated.order['order_id']}_line_{i:03d}"

#     missing = students_missing_backup_profiles(client, generated, selected["caterer_id"])

#     if missing:
#         print(f"\n{len(missing)} students missing backup profiles. Creating outreach list.")
#         outreach = write_backup_outreach(
#             output_dir=settings.output_dir / "backup_outreach",
#             session=backup_session,
#             backup_caterer=selected,
#             missing_students=missing,
#         )
#         print(f"Backup outreach list: {outreach}")
#     else:
#         print("\nAll students have backup caterer profiles. Generated backup order:")
#         email = write_email_draft(client, generated, settings.output_dir / "backup_email_drafts")
#         dist = write_distribution_sheet(generated, settings.output_dir / "backup_distribution_sheets")
#         print(f"Email draft: {email}")
#         print(f"Distribution sheet: {dist}")

#     print("\nBackup flow complete.")
#     return 0

def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate primary caterer failure and backup caterer flow.")
    parser.add_argument("--order-id", help="Existing overdue/backup-required order ID.")
    parser.add_argument("--session-id", help="Session ID, if running backup flow directly from a session.")
    parser.add_argument("--backup-caterer-id", help="Optional. If omitted, use first available backup.")
    parser.add_argument("--write", action="store_true", help="Write backup order to Supabase.")
    args = parser.parse_args()

    if not args.order_id and not args.session_id:
        raise ValueError("Provide either --order-id or --session-id.")

    settings = load_settings()
    client = get_client()

    if args.order_id:
        original_order = get_order(client, args.order_id)
        original_session = get_session(client, original_order["session_id"])
        current_caterer_id = original_order["caterer_id"]
        original_order_id = original_order["order_id"]
    else:
        original_order = None
        original_session = get_session(client, args.session_id)
        current_caterer_id = original_session["caterer_id"]
        original_order_id = None

    school_id = original_session["school_id"]

    backups = get_backup_caterers(client, school_id, current_caterer_id)

    print(f"Primary caterer: {current_caterer_id}")
    print(f"Backup candidates for {school_id}:")
    for c in backups:
        print(f"  - {c['caterer_id']} | {c['name']}")

    if not backups:
        print("No backup caterers available.")
        return 0

    if args.backup_caterer_id:
        selected = next((c for c in backups if c["caterer_id"] == args.backup_caterer_id), None)
        if selected is None:
            raise ValueError(f"{args.backup_caterer_id} is not an available backup for {school_id}")
    else:
        selected = backups[0]

    print(f"\nSelected backup caterer: {selected['name']}")

    backup_session = dict(original_session)
    backup_session["caterer_id"] = selected["caterer_id"]

    generated = generate_for_session(client, backup_session)

    # If this backup is attached to a failed primary order, give it a real backup identity.
    if original_order_id:
        backup_order_id = f"{original_order_id}_backup_{selected['caterer_id']}"

        generated.order["order_id"] = backup_order_id
        generated.order["backup_for_order_id"] = original_order_id
        generated.order["status"] = "ready_for_review"
        generated.order["failure_reason"] = None
        generated.order["internal_notes"] = f"Backup order drafted because {original_order_id} required escalation."

        for i, line in enumerate(generated.order_lines, start=1):
            line["order_id"] = backup_order_id
            line["order_line_id"] = f"{backup_order_id}_line_{i:03d}"

        for i, ex in enumerate(generated.exceptions, start=1):
            ex["entity_id"] = backup_order_id
            ex["exception_id"] = f"{backup_order_id}_exception_{i:03d}"

    missing = students_missing_backup_profiles(client, generated, selected["caterer_id"])

    if missing:
        print(f"\n{len(missing)} students missing backup profiles. Creating outreach list.")
        outreach = write_backup_outreach(
            output_dir=settings.output_dir / "backup_outreach",
            session=backup_session,
            backup_caterer=selected,
            missing_students=missing,
        )
        print(f"Backup outreach list: {outreach}")
        print("TODO production extension: send SMS/email preference form to affected families.")
    else:
        print("\nAll students have backup caterer profiles. Generated backup order:")
        email = write_email_draft(client, generated, settings.output_dir / "backup_email_drafts")
        dist = write_distribution_sheet(generated, settings.output_dir / "backup_distribution_sheets")
        print(f"Email draft: {email}")
        print(f"Distribution sheet: {dist}")

    if args.write:
        from padea_ops.db import upsert_rows

        upsert_rows(client, "orders", [generated.order], on_conflict="order_id")
        upsert_rows(client, "order_lines", generated.order_lines, on_conflict="order_line_id")
        upsert_rows(client, "exceptions", generated.exceptions, on_conflict="exception_id")

        print(f"\nWrote backup order to Supabase: {generated.order['order_id']}")
    else:
        print("\nDry run only. Use --write to save backup order to Supabase.")

    print("\nBackup flow complete.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# python -m scripts.demo_backup_caterer --session-id sess_macgregor_state_high_school_monday --backup-caterer-id cat_guzman_y_gomez

# primary caterer unavailable
# → find backup caterers able to serve school
# → choose backup
# → check student preference profiles for backup caterer
# → either generate backup order or produce family outreach list
