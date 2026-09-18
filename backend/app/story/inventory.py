"""Backward-compatible inventory items with open-ended AI-authored metadata."""
import hashlib
from typing import Any


def item_key(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("item_id") or item.get("instance_id") or "").strip().lower()
    return str(item or "").strip().lower()


def normalize_item(item: Any, *, owner_id: str = "") -> dict:
    if isinstance(item, str):
        name = item.strip()
        digest = hashlib.sha1(f"{owner_id}|{name}".encode("utf-8")).hexdigest()[:12]
        return {
            "instance_id": f"legacy_{digest}", "item_id": None, "name": name,
            "category": "misc", "description": "", "attributes": {},
            "abilities": [], "tags": [], "quantity": 1, "condition": "intact",
            "equipped": False, "charges": None, "acquired_at_tick": None,
            "acquired_from": None,
        }
    if not isinstance(item, dict):
        return normalize_item(str(item), owner_id=owner_id)
    name = str(item.get("name") or item.get("item_id") or "Unknown item").strip()
    digest = hashlib.sha1(f"{owner_id}|{name}".encode("utf-8")).hexdigest()[:12]
    try:
        quantity = max(1, int(item.get("quantity", 1) or 1))
    except (TypeError, ValueError):
        quantity = 1
    return {
        "instance_id": str(item.get("instance_id") or f"inv_{digest}"),
        "item_id": item.get("item_id"), "name": name,
        "category": str(item.get("category") or "misc"),
        "description": str(item.get("description") or ""),
        "attributes": item.get("attributes") if isinstance(item.get("attributes"), dict) else {},
        "abilities": item.get("abilities") if isinstance(item.get("abilities"), list) else [],
        "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
        "quantity": quantity,
        "condition": str(item.get("condition") or "intact"),
        "equipped": bool(item.get("equipped", False)), "charges": item.get("charges"),
        "acquired_at_tick": item.get("acquired_at_tick"),
        "acquired_from": item.get("acquired_from"),
    }


def inventory_view(items: Any, *, owner_id: str = "") -> list:
    return [normalize_item(item, owner_id=owner_id) for item in items] if isinstance(items, list) else []


def add_inventory_item(inventory: list, item: Any) -> None:
    normalized = normalize_item(item)
    key = item_key(normalized)
    for index, existing in enumerate(inventory):
        if item_key(existing) != key:
            continue
        if isinstance(existing, str) and isinstance(item, dict):
            inventory[index] = item
            return
        if isinstance(existing, dict) and normalized.get("quantity", 1) > 0:
            try:
                existing_quantity = int(existing.get("quantity", 1) or 1)
            except (TypeError, ValueError):
                existing_quantity = 1
            existing["quantity"] = max(1, existing_quantity) + normalized["quantity"]
        return
    inventory.append(item if isinstance(item, (str, dict)) else str(item))


def remove_inventory_item(inventory: list, item: Any) -> None:
    key = item_key(item)
    for index, existing in enumerate(inventory):
        if item_key(existing) != key:
            continue
        try:
            quantity = int(item.get("quantity", 1) or 1) if isinstance(item, dict) else 1
        except (TypeError, ValueError):
            quantity = 1
        try:
            existing_quantity = int(existing.get("quantity", 1) or 1) if isinstance(existing, dict) else 1
        except (TypeError, ValueError):
            existing_quantity = 1
        if isinstance(existing, dict) and existing_quantity > quantity:
            existing["quantity"] = existing_quantity - quantity
        else:
            inventory.pop(index)
        return
