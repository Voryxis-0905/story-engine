import json
import logging
from typing import Dict, List, Optional, Any
from app.state_manager import eval_condition
from app.checkpoint_engine import find_checkpoint

logger = logging.getLogger(__name__)

WORLD_EVENTS_TEMPLATE = {
    "events": []
}


def load_world_events(world_path: str) -> dict:
    try:
        with open(f"{world_path}/world_events.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"events": []}


def save_world_events(world_path: str, data: dict) -> None:
    with open(f"{world_path}/world_events.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def pick_matching_outcome(outcomes: List[dict], character_state: dict, world_config: dict) -> Optional[dict]:
    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        condition = outcome.get("condition")
        if condition is None:
            return outcome
        if eval_condition(condition, character_state, world_config):
            return outcome
    return outcomes[-1] if outcomes else None


def apply_location_effects(location_map: dict, effects: List[dict]) -> None:
    if not location_map or not isinstance(location_map, dict):
        return
    locations = location_map.get("locations", [])
    if not isinstance(locations, list):
        return
    for effect in effects:
        if not isinstance(effect, dict):
            continue
        loc_id = effect.get("location_id")
        tags_add = effect.get("tags_add", [])
        tags_remove = effect.get("tags_remove", [])
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            if loc.get("id") != loc_id and loc.get("name") != loc_id:
                continue
            tags = loc.setdefault("tags", [])
            if not isinstance(tags, list):
                loc["tags"] = []
                tags = loc["tags"]
            for tag in tags_remove:
                if tag in tags:
                    tags.remove(tag)
            for tag in tags_add:
                if tag not in tags:
                    tags.append(tag)
            break


def append_facts_to_canon(world_canon_store: dict, facts: List[str], source: str) -> None:
    if not facts or not isinstance(world_canon_store, dict):
        return
    existing = world_canon_store.get("facts", [])
    for statement in facts:
        if not statement or not isinstance(statement, str):
            continue
        existing.append({
            "statement": statement,
            "source": source
        })
    world_canon_store["facts"] = existing


def tick_world_events(
    world_events: dict,
    world_config: dict,
    character_state: dict,
    world_canon_store: dict,
    location_map: Optional[dict] = None,
) -> List[str]:
    events = world_events.get("events", [])
    if not isinstance(events, list):
        return []
    resolved_ids = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("status") != "pending":
            continue
        trigger_conditions = event.get("trigger_conditions", [])
        if not trigger_conditions:
            continue
        if not eval_condition({"all": trigger_conditions}, character_state, world_config):
            continue
        outcomes = event.get("outcomes", [])
        if not outcomes:
            continue
        outcome = pick_matching_outcome(outcomes, character_state, world_config)
        if not outcome:
            continue
        event["status"] = "resolved"
        event["resolved_outcome_id"] = outcome.get("outcome_id")
        tick = world_config.get("story_clock", {}).get("tick", 0)
        event["resolved_at_tick"] = tick
        facts = outcome.get("canon_facts_add", [])
        if facts:
            append_facts_to_canon(
                world_canon_store,
                facts,
                f"world_event:{event.get('event_id', 'unknown')}"
            )
        flags = outcome.get("world_flags_set", {})
        if flags and isinstance(flags, dict):
            world_flags = world_config.setdefault("world_flags", {})
            for key, value in flags.items():
                world_flags[key] = value
        effects = outcome.get("location_effects", [])
        if effects and location_map:
            apply_location_effects(location_map, effects)
        resolved_ids.append(event.get("event_id", ""))
    return resolved_ids
