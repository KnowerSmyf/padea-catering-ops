from __future__ import annotations
from typing import Any
from .utils import boolish

def _notes(text: str | None) -> str:
    return (text or "").lower().strip()

def item_is_active(item: dict[str, Any]) -> bool:
    return boolish(item.get("active", True))

def item_compatible_with_notes(item: dict[str, Any], dietary_notes: str | None) -> bool:
    n = _notes(dietary_notes)
    if not n:
        return True

    reject_if_present = [
        (("no fish", "fish allergy", "seafood"), "contains_fish"),
        (("no beef", "beef allergy"), "contains_beef"),
        (("no chicken", "chicken allergy"), "contains_chicken"),
        (("no pork", "pork allergy", "halal"), "contains_pork"),
    ]
    for triggers, column in reject_if_present:
        if any(t in n for t in triggers) and boolish(item.get(column)):
            return False

    require_if_present = [
        (("gluten free", "coeliac", "celiac", "no gluten"), "is_gluten_free"),
        (("dairy free", "lactose", "no dairy"), "is_dairy_free"),
        (("nut free", "no nuts", "nut allergy"), "is_nut_free"),
    ]
    for triggers, column in require_if_present:
        if any(t in n for t in triggers) and not boolish(item.get(column)):
            return False

    if "vegetarian" in n or "vego" in n:
        has_veg = boolish(item.get("has_vegetarian_option"))
        appears_meatless = not any(boolish(item.get(c)) for c in (
            "contains_pork", "contains_beef", "contains_chicken", "contains_fish"
        ))
        if not (has_veg or appears_meatless):
            return False
    return True
