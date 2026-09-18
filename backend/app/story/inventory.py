"""Backward-compatible inventory items with open-ended AI-authored metadata."""
import hashlib
import json
import re
from typing import Any


def item_key(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("name") or item.get("item_id") or item.get("instance_id") or "").strip().lower()
    return str(item or "").strip().lower()


def _safe_int(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _instance_key(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("instance_id") or "").strip().lower()


def _definition_key(item: Any) -> str:
    if not isinstance(item, dict):
        return ""
    return str(item.get("item_id") or "").strip().lower()


def _stack_signature(item: dict) -> str:
    """Only instances with the same mutable state may share a stack."""
    fields = {
        "item_id": _definition_key(item),
        "condition": item.get("condition", "intact"),
        "charges": item.get("charges"),
        "equipped": bool(item.get("equipped", False)),
        "custom_name": item.get("custom_name"),
        "item_kind": item.get("item_kind"),
        "usage": item.get("usage"),
    }
    return json.dumps(fields, sort_keys=True, ensure_ascii=False, default=str)


def normalize_item(item: Any, *, owner_id: str = "") -> dict:
    if isinstance(item, str):
        name = item.strip()
        digest = hashlib.sha1(f"{owner_id}|{name}".encode("utf-8")).hexdigest()[:12]
        return {
            "instance_id": f"legacy_{digest}", "item_id": None, "name": name,
            "category": "misc", "description": "", "attributes": {},
            "abilities": [], "tags": [], "quantity": 1, "condition": "intact",
            "stackable": False, "custom_name": None,
            "equipped": False, "charges": None, "acquired_at_tick": None,
            "acquired_from": None, "item_kind": "persistent",
            "destructibility": "normal", "usage": {"mode": "unlimited"},
            "drop_policy": "allowed", "requirements": [], "state_effects": [],
        }
    if not isinstance(item, dict):
        return normalize_item(str(item), owner_id=owner_id)
    name = str(item.get("name") or item.get("item_id") or "Unknown item").strip()
    digest = hashlib.sha1(f"{owner_id}|{name}".encode("utf-8")).hexdigest()[:12]
    try:
        quantity = max(1, int(item.get("quantity", 1) or 1))
    except (TypeError, ValueError):
        quantity = 1
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    category = str(item.get("category") or "misc")
    charges = item.get("charges")
    inferred_kind = "consumable" if ("consumable" in [str(t).lower() for t in tags] or category.lower() == "consumable") else "persistent"
    item_kind = str(item.get("item_kind") or inferred_kind)
    usage = item.get("usage") if isinstance(item.get("usage"), dict) else None
    if usage is None:
        if isinstance(charges, (int, float)):
            usage = {"mode": "charges", "remaining": max(0, int(charges))}
        elif item_kind == "consumable":
            usage = {"mode": "quantity", "remaining": quantity}
        else:
            usage = {"mode": "unlimited"}
    else:
        usage = dict(usage)
    # Quantity and legacy charges are engine-owned counters. Keep the display
    # metadata synchronized even when an older item stored a stale `remaining`.
    if usage.get("mode") == "quantity":
        usage["remaining"] = quantity
    elif usage.get("mode") == "charges" and isinstance(charges, (int, float)):
        usage["remaining"] = max(0, int(charges))
    return {
        "instance_id": str(item.get("instance_id") or f"inv_{digest}"),
        "item_id": item.get("item_id"), "name": name,
        "category": category,
        "description": str(item.get("description") or ""),
        "attributes": item.get("attributes") if isinstance(item.get("attributes"), dict) else {},
        "abilities": item.get("abilities") if isinstance(item.get("abilities"), list) else [],
        "tags": tags,
        "quantity": quantity,
        "stackable": bool(item.get("stackable", False)),
        "custom_name": item.get("custom_name"),
        "condition": str(item.get("condition") or "intact"),
        "equipped": bool(item.get("equipped", False)), "charges": charges,
        "acquired_at_tick": item.get("acquired_at_tick"),
        "acquired_from": item.get("acquired_from"),
        "item_kind": item_kind,
        "destructibility": str(item.get("destructibility") or ("protected" if item_kind == "causal_artifact" else "normal")),
        "drop_policy": str(item.get("drop_policy") or "allowed"),
        "usage": usage,
        "requirements": item.get("requirements") if isinstance(item.get("requirements"), list) else [],
        "state_effects": item.get("state_effects") if isinstance(item.get("state_effects"), list) else [],
    }


def inventory_view(items: Any, *, owner_id: str = "") -> list:
    return [normalize_item(item, owner_id=owner_id) for item in items] if isinstance(items, list) else []


def add_inventory_item(inventory: list, item: Any) -> None:
    normalized = normalize_item(item)
    instance_key = _instance_key(normalized)
    definition_key = _definition_key(normalized)
    legacy_key = item_key(normalized)
    for index, existing in enumerate(inventory):
        if isinstance(existing, str) and isinstance(item, dict):
            if item_key(existing) == legacy_key:
                inventory[index] = item
                return
            continue
        if not isinstance(existing, dict):
            continue
        existing_normalized = normalize_item(existing)
        same_instance = bool(instance_key and instance_key == _instance_key(existing_normalized))
        same_stack = bool(
            normalized.get("stackable") and existing_normalized.get("stackable")
            and definition_key and definition_key == _definition_key(existing_normalized)
            and _stack_signature(normalized) == _stack_signature(existing_normalized)
        )
        if same_instance:
            # Replaying the same concrete acquisition must be idempotent.
            return
        if same_stack:
            try:
                existing_quantity = int(existing.get("quantity", 1) or 1)
            except (TypeError, ValueError):
                existing_quantity = 1
            existing["quantity"] = max(1, existing_quantity) + normalized["quantity"]
            return
    inventory.append(item if isinstance(item, (str, dict)) else str(item))


def remove_inventory_item(inventory: list, item: Any) -> None:
    instance_key = _instance_key(item)
    definition_key = _definition_key(item)
    legacy_key = item_key(item)
    for index, existing in enumerate(inventory):
        if instance_key:
            matches = _instance_key(existing) == instance_key
        elif definition_key:
            matches = _definition_key(existing) == definition_key
        else:
            matches = item_key(existing) == legacy_key
        if not matches:
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


def find_inventory_item(inventory: Any, reference: Any):
    """Resolve UI/engine references without confusing same-named instances."""
    if not isinstance(inventory, list):
        return None
    instance_key = _instance_key(reference)
    definition_key = _definition_key(reference)
    legacy_key = item_key(reference)
    for item in inventory:
        if instance_key and _instance_key(item) == instance_key:
            return item
        if not instance_key and definition_key and _definition_key(item) == definition_key:
            return item
        if not instance_key and not definition_key and item_key(item) == legacy_key:
            return item
    return None


def resolve_inventory_action(user_input: str, inventory: Any, character: dict = None):
    """Resolve explicit inventory commands; prose remains the writer's job."""
    match = re.match(r"^(inspect|use|equip|unequip|drop)\s+(.+?)[.!]?$", str(user_input or "").strip(), re.I)
    if not match:
        return None
    operation = match.group(1).lower()
    requested = match.group(2).strip().strip("\"'")
    item = find_inventory_item(inventory, requested)
    if item is None:
        return {"status": "failed", "operation": operation, "requested_item": requested,
                "reason": "item_not_owned", "continuation": "The character can choose another approach."}
    normalized = normalize_item(item)
    if operation == "drop" and normalized.get("drop_policy") == "bound":
        return {"status": "failed", "operation": operation, "item": normalized,
                "reason": "item_is_bound", "continuation": "Its bond must be resolved before it can be left behind."}
    if operation == "equip" and normalized.get("equipped"):
        return {"status": "failed", "operation": operation, "item": normalized,
                "reason": "already_equipped", "continuation": "The character can still use or inspect it."}
    if operation == "unequip" and not normalized.get("equipped"):
        return {"status": "failed", "operation": operation, "item": normalized,
                "reason": "not_equipped", "continuation": "The character can equip or use it instead."}
    if operation == "use" and isinstance(normalized.get("charges"), (int, float)) and normalized["charges"] <= 0:
        return {"status": "failed", "operation": operation, "item": normalized,
                "reason": "no_charges", "continuation": "The character can seek another resource."}
    if operation == "use" and normalized.get("requirements"):
        from app.story.capabilities import find_capability
        missing = [req for req in normalized["requirements"] if not find_capability(character or {}, req)]
        if missing:
            return {"status": "failed", "operation": operation, "item": normalized,
                    "reason": "capability_required", "missing_capabilities": missing,
                    "continuation": "Learn, recall, or find another way to use it."}
    return {"status": "resolved", "operation": operation, "item": normalized, "reason": "item_available"}


def apply_inventory_resolution(inventory: list, resolution: Any) -> None:
    if not isinstance(resolution, dict) or resolution.get("status") != "resolved":
        return
    operation = resolution.get("operation")
    reference = resolution.get("item", {})
    item = find_inventory_item(inventory, reference)
    if item is None:
        return
    if operation in ("equip", "unequip"):
        if isinstance(item, str):
            index = inventory.index(item)
            item = normalize_item(item)
            inventory[index] = item
        item["equipped"] = operation == "equip"
    elif operation == "drop":
        remove_inventory_item(inventory, {"instance_id": reference.get("instance_id"), "quantity": 1})
    elif operation == "use" and isinstance(item, dict):
        charges = item.get("charges")
        if isinstance(charges, (int, float)) and charges > 0:
            item["charges"] = charges - 1
        normalized = normalize_item(item)
        usage = normalized.get("usage", {})
        if usage.get("mode") == "charges" and isinstance(item.get("charges"), (int, float)):
            item.setdefault("usage", usage)
            item["usage"]["remaining"] = max(0, int(item["charges"]))
        if usage.get("mode") == "charges" and not isinstance(item.get("charges"), (int, float)):
            item.setdefault("usage", usage)
            item["usage"]["remaining"] = max(0, int(item["usage"].get("remaining", 0)) - 1)
        elif usage.get("mode") == "quantity":
            remove_inventory_item(inventory, {"instance_id": item.get("instance_id"), "quantity": 1})
            remaining = find_inventory_item(inventory, {"instance_id": item.get("instance_id")})
            if isinstance(remaining, dict):
                remaining.setdefault("usage", usage)
                remaining["usage"]["remaining"] = max(0, int(remaining.get("quantity", 1)))


def apply_item_state_effects(character: dict, resolution: Any, *, at_tick: int) -> list:
    """Apply the deliberately small, genre-neutral item effect surface.

    Items may add semantic status records. Arbitrary state paths and numeric
    character rewrites are ignored, keeping an AI-authored item from becoming a
    hidden scripting language.
    """
    if not isinstance(character, dict) or not isinstance(resolution, dict):
        return []
    if resolution.get("status") != "resolved" or resolution.get("operation") != "use":
        return []
    effects = resolution.get("item", {}).get("state_effects", [])
    applied = []
    statuses = character.setdefault("status_effects", [])
    if not isinstance(statuses, list):
        character["status_effects"] = statuses = []
    for spec in effects if isinstance(effects, list) else []:
        if not isinstance(spec, dict) or spec.get("operation", "add") != "add":
            continue
        if spec.get("path", "status_effects") != "status_effects":
            continue
        value = spec.get("value") if isinstance(spec.get("value"), dict) else None
        if not value or not (value.get("name") or value.get("effect_id")):
            continue
        value = dict(value)
        value["applied_at_tick"] = at_tick
        statuses.append(value)
        applied.append(value)
    return applied
