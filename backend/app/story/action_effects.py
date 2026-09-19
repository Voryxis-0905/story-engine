"""Whitelist bridge from declared action consequences to committed world state.

The model may narrate these effects, but cannot invent executable state paths.
Only consequences authored in ``world_config.action_rules`` and normalized here
can mutate the world.
"""
import re
from typing import Any

_SAFE_KEY = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")
_RESULTS = {"success", "partial", "failure", "conditional", "impossible"}


def _allowed_for_result(spec: dict, result: str) -> bool:
    apply_on = spec.get("apply_on")
    if apply_on is None:
        return result == "success"
    if isinstance(apply_on, str):
        apply_on = [apply_on]
    return isinstance(apply_on, list) and result in apply_on


def _target_id(spec: dict, protagonist_id: str, characters: dict) -> str:
    target = str(spec.get("character_id") or protagonist_id)
    return target if target in characters else ""


def compile_action_effects(resolution: dict, protagonist_id: str,
                           characters: dict, world_events: dict) -> dict:
    result = str((resolution or {}).get("result") or "")
    consequences = (resolution or {}).get("consequences", [])
    if result not in _RESULTS or not isinstance(consequences, list):
        return {"effects": [], "rejected": []}
    event_index = {
        e.get("event_id"): e for e in (world_events or {}).get("events", [])
        if isinstance(e, dict) and e.get("event_id")
    }
    effects, rejected = [], []
    for index, raw in enumerate(consequences):
        if not isinstance(raw, dict):
            rejected.append({"index": index, "reason": "effect_must_be_object"})
            continue
        if not _allowed_for_result(raw, result):
            continue
        kind = str(raw.get("type") or raw.get("kind") or "")
        default_visibility = "hidden" if kind == "event_influence" else "observable"
        visibility = str(raw.get("visibility") or default_visibility)
        if visibility not in ("hidden", "observable"):
            rejected.append({"index": index, "type": kind, "reason": "invalid_visibility"})
            continue
        effect = {"type": kind, "visibility": visibility}
        if kind == "world_flag_set":
            key = str(raw.get("key") or "")
            if not _SAFE_KEY.fullmatch(key):
                rejected.append({"index": index, "type": kind, "reason": "invalid_flag_key"})
                continue
            effect.update(key=key, value=raw.get("value", True))
        elif kind == "world_flags_set":
            values = raw.get("values")
            if not isinstance(values, dict) or not values or any(not _SAFE_KEY.fullmatch(str(k)) for k in values):
                rejected.append({"index": index, "type": kind, "reason": "invalid_flag_values"})
                continue
            effect["values"] = dict(values)
        elif kind == "event_influence":
            event_id = str(raw.get("event_id") or "")
            event = event_index.get(event_id)
            key = str(raw.get("key") or "intervened")
            outcome_id = raw.get("outcome_id")
            outcome_ids = {o.get("outcome_id") for o in (event or {}).get("outcomes", []) if isinstance(o, dict)}
            if not event or event.get("status", "pending") != "pending":
                rejected.append({"index": index, "type": kind, "reason": "event_not_pending", "event_id": event_id})
                continue
            if not _SAFE_KEY.fullmatch(key) or (outcome_id and outcome_id not in outcome_ids):
                rejected.append({"index": index, "type": kind, "reason": "invalid_event_influence", "event_id": event_id})
                continue
            effect.update(event_id=event_id, key=key, value=raw.get("value", True))
            if outcome_id:
                effect["outcome_id"] = outcome_id
        elif kind == "knowledge_flag_add":
            target = _target_id(raw, protagonist_id, characters)
            flag = str(raw.get("flag") or "").strip()
            if not target or not flag or len(flag) > 160:
                rejected.append({"index": index, "type": kind, "reason": "invalid_knowledge_flag"})
                continue
            effect.update(character_id=target, flag=flag)
        elif kind == "status_effect_add":
            target = _target_id(raw, protagonist_id, characters)
            value = raw.get("effect") if isinstance(raw.get("effect"), dict) else None
            if not target or not value or not (value.get("name") or value.get("effect_id")):
                rejected.append({"index": index, "type": kind, "reason": "invalid_status_effect"})
                continue
            effect.update(character_id=target, effect=dict(value))
        elif kind in ("inventory_add", "inventory_remove"):
            target = _target_id(raw, protagonist_id, characters)
            item = raw.get("item")
            if not target or not isinstance(item, (str, dict)):
                rejected.append({"index": index, "type": kind, "reason": "invalid_inventory_effect"})
                continue
            effect.update(character_id=target, item=item)
        else:
            rejected.append({"index": index, "type": kind, "reason": "unsupported_effect_type"})
            continue
        effect["source_index"] = index
        effects.append(effect)
    return {"effects": effects, "rejected": rejected}


def project_action_effects(plan: dict) -> dict:
    """Redact hidden causal links before data reaches narrator/player views."""
    visible = []
    for effect in (plan or {}).get("effects", []):
        if effect.get("visibility") == "hidden":
            visible.append({
                "type": effect.get("type"), "visibility": "hidden",
                "source_index": effect.get("source_index"),
                "narration": "This action may have consequences the viewpoint character cannot yet observe.",
            })
        else:
            visible.append(dict(effect))
    rejected = []
    for item in (plan or {}).get("rejected", []):
        if not isinstance(item, dict):
            continue
        # Rejections are useful diagnostics, but their authored event ids and
        # paths can themselves be secret creator knowledge.
        rejected.append({key: item[key] for key in ("index", "type", "reason") if key in item})
    return {"effects": visible, "rejected": rejected}


def project_action_effect_result(result: dict) -> dict:
    projected = project_action_effects({
        "effects": (result or {}).get("applied", []),
        "rejected": (result or {}).get("rejected", []),
    })
    return {"applied": projected["effects"], "rejected": projected["rejected"],
            "events_changed": bool((result or {}).get("events_changed"))}


def _set_nested_flag(flags: dict, key: str, value: Any) -> None:
    parts = key.split(".")
    cursor = flags
    for part in parts[:-1]:
        child = cursor.get(part)
        if not isinstance(child, dict):
            child = {}
            cursor[part] = child
        cursor = child
    cursor[parts[-1]] = value


def apply_action_effects(plan: dict, action_id: str, protagonist_id: str,
                         characters: dict, world_config: dict,
                         world_events: dict, *, at_tick: int) -> dict:
    from app.story.inventory import add_inventory_item, remove_inventory_item
    applied = []
    events_changed = False
    flags = world_config.setdefault("world_flags", {})
    event_index = {
        e.get("event_id"): e for e in world_events.get("events", [])
        if isinstance(e, dict) and e.get("event_id")
    }
    for effect in (plan or {}).get("effects", []):
        kind = effect.get("type")
        if kind == "world_flag_set":
            _set_nested_flag(flags, effect["key"], effect.get("value"))
        elif kind == "world_flags_set":
            for key, value in effect["values"].items():
                _set_nested_flag(flags, str(key), value)
        elif kind == "event_influence":
            event = event_index.get(effect["event_id"])
            if not event or event.get("status", "pending") != "pending":
                continue
            influence_all = flags.get("event_influence")
            if not isinstance(influence_all, dict):
                flags["event_influence"] = influence_all = {}
            influence_root = influence_all.get(effect["event_id"])
            if not isinstance(influence_root, dict):
                influence_all[effect["event_id"]] = influence_root = {}
            _set_nested_flag(influence_root, effect["key"], effect.get("value"))
            record = {
                "action_id": action_id, "tick": at_tick, "key": effect["key"],
                "value": effect.get("value"), "character_id": protagonist_id,
            }
            if effect.get("outcome_id"):
                record["outcome_id"] = effect["outcome_id"]
                event["preferred_outcome_id"] = effect["outcome_id"]
                event["preferred_outcome_action_id"] = action_id
            interventions = event.get("interventions")
            if not isinstance(interventions, list):
                event["interventions"] = interventions = []
            interventions.append(record)
            events_changed = True
        else:
            target = characters.get(effect.get("character_id"))
            if not isinstance(target, dict):
                continue
            if kind == "knowledge_flag_add":
                flags_list = target.get("knowledge_flags")
                if not isinstance(flags_list, list):
                    target["knowledge_flags"] = flags_list = []
                if effect["flag"] not in flags_list:
                    flags_list.append(effect["flag"])
            elif kind == "status_effect_add":
                value = dict(effect["effect"])
                value["applied_at_tick"] = at_tick
                statuses = target.get("status_effects")
                if not isinstance(statuses, list):
                    target["status_effects"] = statuses = []
                statuses.append(value)
            elif kind == "inventory_add":
                add_inventory_item(target.setdefault("inventory", []), effect["item"])
            elif kind == "inventory_remove":
                remove_inventory_item(target.setdefault("inventory", []), effect["item"])
        applied.append(effect)
    return {"applied": applied, "rejected": (plan or {}).get("rejected", []),
            "events_changed": events_changed}
