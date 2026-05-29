from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .compat import item_compatible_with_notes, item_is_active

@dataclass
class MealDecision:
    student_id: str
    menu_item_id: str | None
    selection_reason: str
    exceptions: list[dict[str, Any]]

def _ex(severity: str, exception_type: str, message: str) -> dict[str, Any]:
    return {"severity": severity, "exception_type": exception_type, "message": message}

def choose_default_safe(menu_items: list[dict[str, Any]], dietary_notes: str | None) -> dict[str, Any] | None:
    candidates = [m for m in menu_items if item_is_active(m)]
    candidates.sort(key=lambda m: (
        not bool(m.get("is_nut_free")),
        not bool(m.get("is_dairy_free")),
        not bool(m.get("is_gluten_free")),
        str(m.get("item_name", "")),
    ))
    for item in candidates:
        if item_compatible_with_notes(item, dietary_notes):
            return item
    return None

def choose_meal_for_student(*, student: dict[str, Any], food_profile: dict[str, Any] | None,
                            menu_items: list[dict[str, Any]], session_caterer_id: str) -> MealDecision:
    student_id = student.get("student_id") or student.get("id")
    student_name = student.get("full_name") or student.get("name") or student_id
    exceptions: list[dict[str, Any]] = []
    menu_by_id = {m["menu_item_id"]: m for m in menu_items if m.get("menu_item_id")}

    if food_profile is None:
        exceptions.append(_ex("high", "missing_food_profile",
                              f"{student_name} has no food profile for caterer {session_caterer_id}."))
        default = choose_default_safe(menu_items, None)
        return MealDecision(student_id, default.get("menu_item_id") if default else None,
                            "default_no_profile" if default else "unresolved", exceptions)

    dietary_notes = food_profile.get("dietary_notes")

    for field, reason in [("preferred_menu_item_id", "preferred"), ("backup_menu_item_id", "backup")]:
        item_id = food_profile.get(field)
        if not item_id:
            continue
        item = menu_by_id.get(item_id)
        if not item:
            exceptions.append(_ex("medium", f"{reason}_item_missing",
                                  f"{student_name}'s {reason} item {item_id} is not on this caterer's menu."))
            continue
        if not item_is_active(item):
            exceptions.append(_ex("medium", f"{reason}_item_inactive",
                                  f"{student_name}'s {reason} item {item_id} is inactive."))
            continue
        if item.get("caterer_id") != session_caterer_id:
            exceptions.append(_ex("medium", f"{reason}_wrong_caterer",
                                  f"{student_name}'s {reason} item belongs to {item.get('caterer_id')}, not {session_caterer_id}."))
            continue
        if not item_compatible_with_notes(item, dietary_notes):
            exceptions.append(_ex("high", f"{reason}_dietary_conflict",
                                  f"{student_name}'s {reason} item conflicts with dietary notes: {dietary_notes}."))
            continue
        return MealDecision(student_id, item_id, reason, exceptions)

    default = choose_default_safe(menu_items, dietary_notes)
    if default:
        exceptions.append(_ex("medium", "used_default_safe_meal",
                              f"{student_name} was assigned a default safe meal because preferred/backup could not be used."))
        return MealDecision(student_id, default["menu_item_id"], "default_safe", exceptions)

    exceptions.append(_ex("critical", "no_safe_menu_item",
                          f"{student_name} has no safe available menu item for caterer {session_caterer_id}."))
    return MealDecision(student_id, None, "unresolved", exceptions)
