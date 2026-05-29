from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any
from supabase import Client
from .db import fetch_all, upsert_rows, delete_rows
from .email_templates import planned_delivery_time
from .meal_selection import choose_meal_for_student
from .utils import iso_now, boolish

@dataclass
class GeneratedOrder:
    order: dict[str, Any]
    order_lines: list[dict[str, Any]]
    student_map: list[dict[str, Any]]
    exceptions: list[dict[str, Any]]
    email_context: dict[str, Any]

def _session_id(s): return s.get("session_id") or s.get("id")
def _session_date(s): return s.get("session_date") or s.get("date")
def _school_id(s): return s.get("school_id")
def _caterer_id(s): return s.get("caterer_id")
def _student_id(s): return s.get("student_id") or s.get("id")

def _parse_year_levels(value: str | None) -> set[int]:
    if not value:
        return set()

    levels = set()

    for part in str(value).replace("Years", "").replace("Year", "").split(","):
        part = part.strip()
        if part.isdigit():
            levels.add(int(part))

    return levels

def min_required_for_order(caterer: dict, distinct_items: int) -> int | None:
    if distinct_items <= 4:
        return caterer.get("min_qty_4_items")
    if distinct_items == 5:
        return caterer.get("min_qty_5_items")
    return caterer.get("min_qty_6_items")

def apply_partial_exclusions(
    client: Client,
    session: dict[str, Any],
    attendees: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = fetch_all(
        client,
        "exclusions",
        filters={"school_id": _school_id(session)},
    )

    session_date = str(session.get("session_date"))[:10]
    excluded_years = set()

    for row in rows:
        if (
            str(row.get("exclusion_date"))[:10] == session_date
            and str(row.get("scope", "")).lower() == "partial"
        ):
            excluded_years |= _parse_year_levels(row.get("year_levels"))

    if not excluded_years:
        return attendees

    return [
        student
        for student in attendees
        if student.get("year_level") is None
        or int(student["year_level"]) not in excluded_years
    ]

def get_sessions_for_window(client: Client, start: date, end: date) -> list[dict[str, Any]]:
    sessions = fetch_all(client, "sessions")
    out = []
    for s in sessions:
        d = _session_date(s)
        if d and start.isoformat() <= d <= end.isoformat() and boolish(s.get("active", True)):
            out.append(s)
    return sorted(out, key=lambda s: (_session_date(s), _school_id(s) or ""))

def get_active_students_for_session(client: Client, session: dict[str, Any]) -> list[dict[str, Any]]:
    session_id = _session_id(session)
    school_id = _school_id(session)
    try:
        enrollments = fetch_all(client, "student_sessions", filters={"session_id": session_id})
        active_ids = {e.get("student_id") for e in enrollments if boolish(e.get("active", True))}
        students = fetch_all(client, "students")
        return [s for s in students if _student_id(s) in active_ids and boolish(s.get("active", True))]
    except Exception:
        students = fetch_all(client, "students")
        return [s for s in students if boolish(s.get("active", True)) and s.get("school_id") == school_id]

def get_absent_student_ids(client: Client, session: dict[str, Any]) -> set[str]:
    try:
        rows = fetch_all(client, "absences", filters={"school_id": _school_id(session), "absence_date": _session_date(session)})
    except Exception:
        return set()
    return {r.get("student_id") for r in rows if r.get("student_id") and boolish(r.get("actionable_for_order", True))}

def get_full_exclusion(client: Client, session: dict[str, Any]) -> dict[str, Any] | None:
    try:
        rows = fetch_all(client, "exclusions", filters={"school_id": _school_id(session), "exclusion_date": _session_date(session)})
    except Exception:
        return None
    for r in rows:
        if str(r.get("scope", "")).lower() == "all":
            return r
    return None

def generate_for_session(client: Client, session: dict[str, Any]) -> GeneratedOrder:
    session_id = _session_id(session)
    session_date = _session_date(session)
    school_id = _school_id(session)
    caterer_id = _caterer_id(session)
    order_id = f"order_{session_date}_{session_id}".replace("-", "_")
    exceptions = []

    if planned_delivery_time(session) is None:
        exceptions.append({
            "exception_id": f"{order_id}_missing_dinner_time",
            "source": "generate_weekly_orders",
            "entity_type": "order",
            "entity_id": order_id,
            "severity": "high",
            "exception_type": "missing_dinner_time",
            "message": "Cannot infer requested delivery time because dinner_time is missing or invalid.",
            "status": "open",
        })

    def get_one(table, key, value):
        try:
            return (fetch_all(client, table, filters={key: value}, limit=1) or [None])[0]
        except Exception:
            return None

    school = get_one("schools", "school_id", school_id)
    caterer = get_one("caterers", "caterer_id", caterer_id)
    contacts = []
    try:
        contacts = fetch_all(client, "caterer_contacts", filters={"caterer_id": caterer_id})
    except Exception:
        contacts = []

    to_contacts = [
        c for c in contacts
        if c.get("email") and str(c.get("email_routing", "")).lower() == "to"
    ]

    if not to_contacts:
        exceptions.append({
            "exception_id": f"{order_id}_missing_caterer_order_contact",
            "source": "generate_weekly_orders",
            "entity_type": "order",
            "entity_id": order_id,
            "severity": "high",
            "exception_type": "missing_caterer_order_contact",
            "message": f"No main order contact found for caterer_id={caterer_id}.",
            "status": "open",
        })

    manager = get_one("managers", "manager_id", session.get("manager_id")) if session.get("manager_id") else None

    if not session.get("manager_id"):
        exceptions.append({
            "exception_id": f"{order_id}_missing_manager_id",
            "source": "generate_weekly_orders",
            "entity_type": "order",
            "entity_id": order_id,
            "severity": "high",
            "exception_type": "missing_manager_id",
            "message": "Session has no manager_id, so caterer has no delivery contact.",
            "status": "open",
        })
    elif manager is None:
        exceptions.append({
            "exception_id": f"{order_id}_manager_not_found",
            "source": "generate_weekly_orders",
            "entity_type": "order",
            "entity_id": order_id,
            "severity": "high",
            "exception_type": "manager_not_found",
            "message": f"Session references manager_id={session.get('manager_id')}, but no manager record exists.",
            "status": "open",
        })
    elif not manager.get("mobile"):
        exceptions.append({
            "exception_id": f"{order_id}_manager_missing_mobile",
            "source": "generate_weekly_orders",
            "entity_type": "order",
            "entity_id": order_id,
            "severity": "high",
            "exception_type": "manager_missing_mobile",
            "message": f"Manager {manager.get('name') or session.get('manager_id')} has no mobile number.",
            "status": "open",
        })

    full_exclusion = get_full_exclusion(client, session)
    if full_exclusion:
        order = {"order_id": order_id, "session_id": session_id, "school_id": school_id, "caterer_id": caterer_id,
                 "delivery_date": session_date, "status": "cancelled", "generated_at": iso_now(),
                 "exception_count": 1, "internal_notes": f"Cancelled: {full_exclusion.get('reason')}"}
        return GeneratedOrder(order, [], [], [{
            "exception_id": f"{order_id}_cancelled", "source": "generate_weekly_orders",
            "entity_type": "order", "entity_id": order_id, "severity": "info",
            "exception_type": "session_cancelled", "message": f"Session cancelled: {full_exclusion.get('reason')}",
            "status": "open"}], {"session": session, "school": school, "caterer": caterer, "manager": manager})

    students = get_active_students_for_session(client, session)
    absent = get_absent_student_ids(client, session)
    attendees = [s for s in students if _student_id(s) not in absent]
    attendees = apply_partial_exclusions(client, session, attendees)

    menu_items = fetch_all(client, "menu_items", filters={"caterer_id": caterer_id})
    profiles = fetch_all(client, "student_food_profiles", filters={"caterer_id": caterer_id})
    profiles_by_student = {p.get("student_id"): p for p in profiles}

    counts = Counter()
    student_map = []

    for student in attendees:
        student_id = _student_id(student)
        decision = choose_meal_for_student(student=student, food_profile=profiles_by_student.get(student_id),
                                           menu_items=menu_items, session_caterer_id=caterer_id)
        for ex in decision.exceptions:
            exceptions.append({
                "exception_id": f"{order_id}_{student_id}_{len(exceptions)+1}",
                "source": "generate_weekly_orders",
                "entity_type": "student_order",
                "entity_id": f"{order_id}:{student_id}",
                "severity": ex["severity"],
                "exception_type": ex["exception_type"],
                "message": ex["message"],
                "status": "open",
            })
        if decision.menu_item_id:
            counts[decision.menu_item_id] += 1
            student_map.append({
                "order_student_map_id": f"{order_id}_{student_id}",
                "order_id": order_id,
                "student_id": student_id,
                "menu_item_id": decision.menu_item_id,
                "selection_reason": decision.selection_reason,
            })

    order_lines = [{"order_line_id": f"{order_id}_line_{i:03d}", "order_id": order_id,
                    "menu_item_id": mid, "quantity": qty, "notes": None}
                   for i, (mid, qty) in enumerate(counts.items(), start=1)]

    distinct_items = len(order_lines)
    total_qty = sum(line["quantity"] for line in order_lines)

    if caterer and distinct_items > 0:
        min_required = min_required_for_order(caterer, distinct_items)

        if min_required is not None and total_qty < min_required:
            exceptions.append({
                "exception_id": f"{order_id}_below_caterer_minimum",
                "source": "generate_weekly_orders",
                "entity_type": "order",
                "entity_id": order_id,
                "severity": "medium",
                "exception_type": "below_caterer_minimum",
                "message": (
                    f"Order has {total_qty} meals across {distinct_items} items, "
                    f"below caterer minimum of {min_required}."
                ),
                "status": "open",
            })
            
    status = "needs_review" if any(e["severity"] in {"critical", "high"} for e in exceptions) else "ready_for_review"
    order = {
        "order_id": order_id, 
        "session_id": session_id, 
        # "school_id": school_id, 
        "caterer_id": caterer_id,    
        "delivery_date": session_date,
        "status": status, 
        "generated_at": iso_now(),
        "exception_count": len(exceptions), 
        "internal_notes": None
    }

    return GeneratedOrder(order, order_lines, student_map, exceptions,
                          {"session": session, "school": school, "caterer": caterer, "manager": manager,
                           "students": attendees, "menu_items": menu_items})

def replace_generated_outputs(client: Client, orders: list[GeneratedOrder]) -> None:
    for g in orders:
        oid = g.order["order_id"]
        for table in ["order_student_map", "order_lines", "orders"]:
            try: delete_rows(client, table, {"order_id": oid})
            except Exception: pass
    upsert_rows(client, "orders", [g.order for g in orders], on_conflict="order_id")
    upsert_rows(client, "order_lines", [r for g in orders for r in g.order_lines], on_conflict="order_line_id")
    upsert_rows(client, "order_student_map", [r for g in orders for r in g.student_map], on_conflict="order_student_map_id")
    upsert_rows(client, "exceptions", [r for g in orders for r in g.exceptions], on_conflict="exception_id")
