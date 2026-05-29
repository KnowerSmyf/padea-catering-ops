from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import csv
from .db import fetch_all
from .utils import ensure_dir, slugify

def _menu_by_id(menu_items): return {m["menu_item_id"]: m for m in menu_items if m.get("menu_item_id")}

def get_email_recipients(client, caterer_id: str) -> tuple[list[str], list[str]]:
    try:
        contacts = fetch_all(client, "caterer_contacts", filters={"caterer_id": caterer_id})
    except Exception:
        return [], []
    to, cc = [], []
    for c in contacts:
        email = c.get("email")
        routing = str(c.get("email_routing") or "").lower()
        if not email: continue
        if routing == "cc": cc.append(email)
        elif routing in {"do_not_cc", "ignore", "none"}: continue
        else: to.append(email)
    return to, cc

def planned_delivery_time(session: dict) -> str | None:
    try:
        dinner_time = session.get("dinner_time")
        if not dinner_time:
            return None

        dt = datetime.strptime(str(dinner_time), "%H:%M:%S")
        return (dt - timedelta(minutes=10)).strftime("%-I:%M%p").lower()

    except ValueError:
        return None

def render_caterer_email(client, generated) -> str:
    order, ctx = generated.order, generated.email_context
    session, school, caterer, manager = ctx.get("session") or {}, ctx.get("school") or {}, ctx.get("caterer") or {}, ctx.get("manager") or {}
    menu_lookup = _menu_by_id(ctx.get("menu_items") or [])
    to, cc = get_email_recipients(client, order["caterer_id"])
    school_name = school.get("name") or session.get("school_id") or "[school missing]"
    caterer_name = caterer.get("name") or order.get("caterer_id")
    location = ", ".join(str(x) for x in [school_name, session.get("building"), session.get("room")] if x)
    manager_line = f"{manager.get('name', '[manager missing]')} — {manager.get('mobile', '[mobile missing]')}" if manager else "Manager contact missing"
    delivery_time = planned_delivery_time(session) or "[delivery time missing]"
    lines = [f"- {menu_lookup.get(l['menu_item_id'], {}).get('item_name') or l['menu_item_id']}: {l['quantity']}" for l in generated.order_lines]
    exception_lines = [
        f"- [{e['severity'].upper()}] {e['exception_type']}: {e['message']}"
        for e in generated.exceptions
    ]
    
    return f'''# Catering order: {school_name} — {order['delivery_date']}

**To:** {", ".join(to) if to else "[missing recipient]"}  
**CC:** {", ".join(cc) if cc else ""}  
**Status:** {order['status']}

Hi {caterer_name},

Please confirm the following order for **{school_name}** on **{order['delivery_date']}**.

**Delivery time:** {delivery_time}  
**Delivery location:** {location or '[location missing]'}  
**On-site manager:** {manager_line}

## Order

{chr(10).join(lines) if lines else "- No meals ordered"}

## Instructions

- Please reply to confirm this order.
- Please contact the on-site manager if you are late or need help finding the room.
- Meals should arrive 5–10 minutes before the dinner break.

---

## Internal review notes

{chr(10).join(exception_lines) if exception_lines else "No exceptions flagged."}
'''

def write_email_draft(client, generated, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    ctx = generated.email_context
    session = ctx.get("session") or {}
    school = ctx.get("school") or {}
    caterer = ctx.get("caterer") or {}

    school_label = school.get("name") or session.get("school_id") or "school_missing"
    caterer_label = caterer.get("name") or generated.order.get("caterer_id") or "caterer_missing"

    filename = f"{generated.order['delivery_date']}_{slugify(school_label)}_{slugify(caterer_label)}.md"
    path = output_dir / filename
    path.write_text(render_caterer_email(client, generated), encoding="utf-8")
    return path

def write_distribution_sheet(generated, output_dir: Path) -> Path:
    ensure_dir(output_dir)
    ctx = generated.email_context
    students = {s.get("student_id") or s.get("id"): s for s in ctx.get("students", [])}
    menu = _menu_by_id(ctx.get("menu_items", []))
    school = ctx.get("school") or {}
    session = ctx.get("session") or {}
    school_label = school.get("name") or session.get("school_id") or "school_missing"
    filename = f"{generated.order['delivery_date']}_{slugify(school_label)}_distribution.csv"
    path = output_dir / filename
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["delivery_date", "school", "student_name", "meal", "selection_reason"])
        writer.writeheader()
        for row in generated.student_map:
            student, item = students.get(row["student_id"], {}), menu.get(row["menu_item_id"], {})
            writer.writerow({
                "delivery_date": generated.order["delivery_date"],
                "school": school.get("name") or session.get("school_id") or "[school missing]",
                "student_name": student.get("full_name") or student.get("name") or row["student_id"],
                "meal": item.get("item_name") or row["menu_item_id"],
                "selection_reason": row["selection_reason"],
            })
    return path
