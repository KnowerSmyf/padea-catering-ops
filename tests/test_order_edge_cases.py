from __future__ import annotations

from padea_ops.db import get_client, fetch_all
from padea_ops.order_generation import generate_for_session


def get_session(client, school_id: str, session_date: str):
    sessions = fetch_all(client, "sessions", filters={"school_id": school_id})

    for session in sessions:
        # Defensive date normalization because Supabase may return date or timestamp-ish strings.
        if str(session.get("session_date"))[:10] == session_date:
            return session

    raise ValueError(f"No session found for {school_id} on {session_date}")


def print_order_debug(label: str, generated):
    print(f"\n{'=' * 80}")
    print(label)
    print("=" * 80)

    print("Order:")
    print(generated.order)

    print("\nOrder lines:")
    for line in generated.order_lines:
        print(line)

    print("\nStudent map count:", len(generated.student_map))
    print("First 10 student mappings:")
    for row in generated.student_map[:10]:
        print(row)

    print("\nExceptions:")
    for ex in generated.exceptions:
        print(ex)


def assert_student_not_in_order(generated, student_id: str):
    present = any(row["student_id"] == student_id for row in generated.student_map)

    if present:
        raise AssertionError(f"{student_id} was present in order but should have been removed.")

    print(f"PASS: {student_id} not present in order.")


def assert_student_years_excluded(client, generated, excluded_years: set[int]):
    student_ids = [row["student_id"] for row in generated.student_map]

    if not student_ids:
        print("No students in order; cannot test year filtering.")
        return

    students = fetch_all(client, "students")
    students_by_id = {s["student_id"]: s for s in students}

    bad = []

    for student_id in student_ids:
        student = students_by_id.get(student_id)
        if not student:
            continue

        year_level = student.get("year_level")
        if year_level is not None and int(year_level) in excluded_years:
            bad.append((student_id, student.get("full_name"), year_level))

    if bad:
        raise AssertionError(
            "Students from excluded year levels were still included:\n"
            + "\n".join(str(x) for x in bad[:20])
        )

    print(f"PASS: no students from excluded years {excluded_years} were included.")


def main() -> int:
    client = get_client()

    # 1. Full exclusion: Loreto 2026-05-02 should be cancelled.
    loreto = get_session(
        client,
        "school_loreto_college",
        "2026-05-02",
    )
    loreto_order = generate_for_session(client, loreto)
    print_order_debug("FULL EXCLUSION TEST: Loreto 2026-05-02", loreto_order)

    assert loreto_order.order["status"] == "cancelled", "Loreto 2026-05-02 should be cancelled."
    assert len(loreto_order.order_lines) == 0, "Cancelled session should have zero order lines."
    assert len(loreto_order.student_map) == 0, "Cancelled session should have zero student mappings."
    print("PASS: full exclusion handled correctly.")

    # 2. Full exclusion: Indooroopilly 2026-05-04 should be cancelled.
    indro = get_session(
        client,
        "school_indooroopilly_state_high_school",
        "2026-05-04",
    )
    indro_order = generate_for_session(client, indro)
    print_order_debug("FULL EXCLUSION TEST: Indooroopilly 2026-05-04", indro_order)

    assert indro_order.order["status"] == "cancelled", "Indooroopilly 2026-05-04 should be cancelled."
    assert len(indro_order.order_lines) == 0, "Cancelled session should have zero order lines."
    assert len(indro_order.student_map) == 0, "Cancelled session should have zero student mappings."
    print("PASS: full exclusion handled correctly.")

    # 3. Absence: Noah Baker should be removed from MBBC 2026-05-02.
    mbbc = get_session(
        client,
        "school_moreton_bay_boys_college",
        "2026-05-02",
    )
    mbbc_order = generate_for_session(client, mbbc)
    print_order_debug("ABSENCE TEST: MBBC 2026-05-02", mbbc_order)

    assert_student_not_in_order(
        mbbc_order,
        "stu_noah_baker_moreton_bay_boys_college",
    )

    # 4. Partial exclusion: Cannon Hill 2026-05-03 excludes Years 10 and 12.
    cannon = get_session(
        client,
        "school_cannon_hill_anglican_college",
        "2026-05-03",
    )
    cannon_order = generate_for_session(client, cannon)
    print_order_debug("PARTIAL EXCLUSION TEST: Cannon Hill 2026-05-03", cannon_order)

    assert_student_years_excluded(client, cannon_order, {10, 12})

    print("\nAll targeted edge-case tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())