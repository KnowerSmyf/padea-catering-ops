from __future__ import annotations

import argparse

from padea_ops.db import get_client, fetch_all, upsert_rows


def get_student(client, student_id: str):
    rows = fetch_all(client, "students", filters={"student_id": student_id}, limit=1)
    if not rows:
        raise ValueError(f"No student found with student_id={student_id}")
    return rows[0]


def get_session(client, session_id: str):
    rows = fetch_all(client, "sessions", filters={"session_id": session_id}, limit=1)
    if not rows:
        raise ValueError(f"No session found with session_id={session_id}")
    return rows[0]


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulate processing a family email reporting an absence.")
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--absence-date", required=True)
    parser.add_argument("--raw-text", default="Hi, my child will be absent from tutoring this week.")
    args = parser.parse_args()

    client = get_client()

    student = get_student(client, args.student_id)
    session = get_session(client, args.session_id)

    absence_id = f"abs_email_{args.student_id}_{args.absence_date}".replace("-", "_")

    row = {
        "absence_id": absence_id,
        "school_id": session["school_id"],
        "student_id": args.student_id,
        "student_name_raw": student.get("full_name"),
        "absence_date": args.absence_date,
        "source": "families_email_mock",
        "actionable_for_order": True,
    }

    print("\nMock family email:")
    print(args.raw_text)

    print("\nStructured absence update:")
    print(row)

    result = upsert_rows(client, "absences", [row], on_conflict="absence_id")

    print("\nUpsert result:")
    print(result)

    print("\nRerun the weekly order generator. This student should now be removed from the relevant order.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())