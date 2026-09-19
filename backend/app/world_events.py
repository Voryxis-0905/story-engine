import json
import logging
from typing import Dict, List, Optional, Any

from app.state_manager import eval_condition
from app.story.knowledge import make_fact, grant_knowledge

logger = logging.getLogger(__name__)

WORLD_EVENTS_TEMPLATE = {
    "events": []
}

EVENT_RESOLUTIONS = ("resolved", "prevented", "transformed", "missed")
EVENT_CLASSES = ("organized", "contingent", "consequence")


def load_world_events(world_path: str) -> dict:
    try:
        with open(f"{world_path}/world_events.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"events": []}


def save_world_events(world_path: str, data: dict) -> None:
    with open(f"{world_path}/world_events.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_event(event: dict) -> dict:
    """Adapter for old events: fill lifecycle/class defaults without rewriting them."""
    if not isinstance(event, dict):
        return event
    event.setdefault("event_class", "organized")
    event.setdefault("status", "pending")
    event.setdefault("trigger_conditions", [])
    event.setdefault("outcomes", [])
    event.setdefault("organizer_id", None)
    event.setdefault("location_id", None)
    event.setdefault("deadline_tick", None)
    return event


def validate_event_outcome(outcome: dict) -> List[str]:
    """Schema check. Any outcome that passes is valid, even beyond sample shapes."""
    errors = []
    if not isinstance(outcome, dict):
        return ["outcome must be an object"]
    if not outcome.get("outcome_id"):
        errors.append("outcome_id is required")
    resolution = outcome.get("resolution", "resolved")
    if resolution not in EVENT_RESOLUTIONS:
        errors.append(f"resolution must be one of {EVENT_RESOLUTIONS}")
    if "condition" in outcome and outcome["condition"] is not None and not isinstance(outcome["condition"], dict):
        errors.append("condition must be an object or null")
    for list_field in ("canon_facts_add", "location_effects"):
        if list_field in outcome and not isinstance(outcome[list_field], list):
            errors.append(f"{list_field} must be a list")
    if "world_flags_set" in outcome and not isinstance(outcome["world_flags_set"], dict):
        errors.append("world_flags_set must be an object")
    return errors


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


def append_facts_to_canon(world_canon_store: dict, facts: List[str], source: str,
                          *, event_id: str = None, tick: int = None,
                          category: str = "event") -> List[dict]:
    """Append objective facts with stable ids. Returns the created fact objects."""
    created = []
    if not facts or not isinstance(world_canon_store, dict):
        return created
    existing = world_canon_store.get("facts", [])
    for statement in facts:
        if not statement or not isinstance(statement, str):
            continue
        fact = make_fact(
            statement, category=category, source=source,
            event_id=event_id, tick=tick,
        )
        existing.append(fact)
        created.append(fact)
    world_canon_store["facts"] = existing
    return created


def _event_location(event: dict, outcome: dict) -> str:
    location = event.get("location_id")
    if location:
        return str(location)
    for effect in outcome.get("location_effects", []) or []:
        if isinstance(effect, dict) and effect.get("location_id"):
            return str(effect.get("location_id"))
    return ""


def _location_exists(location_map: Optional[dict], location_id: str) -> bool:
    if not location_id or not isinstance(location_map, dict):
        return True  # cannot tell -> assume it still exists
    for loc in location_map.get("locations", []) or []:
        if isinstance(loc, dict) and (loc.get("id") == location_id or loc.get("name") == location_id):
            return True
    return False


def _organizer_alive(character_state: dict, organizer_id: str) -> bool:
    if not organizer_id:
        return True
    state = character_state.get(organizer_id)
    if not isinstance(state, dict):
        return False
    return bool(state.get("alive", True))


def _by_resolution(outcomes: List[dict], resolution: str) -> Optional[dict]:
    for outcome in outcomes:
        if isinstance(outcome, dict) and outcome.get("resolution", "resolved") == resolution:
            return outcome
    return None


def _synthetic_outcome(event_id: str, resolution: str) -> dict:
    return {"outcome_id": f"{resolution}:{event_id}", "resolution": resolution}


def choose_resolution_outcome(event: dict, outcomes: List[dict], character_state: dict,
                              location_map: Optional[dict],
                              world_config: dict = None) -> Optional[dict]:
    """Apply D01: an organized event whose premise is gone does not force a scene.

    Contingent (force-majeure) events ignore organizer/location premises and
    always resolve. A resolved event keeps its normal outcome; a missing actor
    or location prefers prevented/transformed/missed when those exist.
    """
    event_class = event.get("event_class", "organized")
    location_id = event.get("location_id")
    organizer_id = event.get("organizer_id")

    if event_class == "organized":
        if location_id and not _location_exists(location_map, location_id):
            chosen = (_by_resolution(outcomes, "transformed")
                      or _by_resolution(outcomes, "missed"))
            return chosen or _synthetic_outcome(event.get("event_id", ""), "transformed")
        if organizer_id and not _organizer_alive(character_state, organizer_id):
            chosen = (_by_resolution(outcomes, "prevented")
                      or _by_resolution(outcomes, "transformed"))
            return chosen or _synthetic_outcome(event.get("event_id", ""), "prevented")

    # A validated engine-owned action may lock the eventual branch while the
    # causal event itself still waits for its trigger. This is never read from
    # narrator output; only the action-effects whitelist can write it.
    preferred_id = event.get("preferred_outcome_id")
    if preferred_id:
        preferred = next(
            (outcome for outcome in outcomes
             if isinstance(outcome, dict) and outcome.get("outcome_id") == preferred_id),
            None,
        )
        if preferred is not None:
            return preferred

    for outcome in outcomes:
        if not isinstance(outcome, dict):
            continue
        if outcome.get("requires_actor_alive") and not _organizer_alive(character_state, organizer_id):
            continue
        if outcome.get("requires_location") and location_id and not _location_exists(location_map, location_id):
            continue
        condition = outcome.get("condition")
        if condition is None or eval_condition(condition, character_state, world_config):
            return outcome
    return outcomes[-1] if outcomes else None


def _apply_outcome(event: dict, outcome: dict, tick: int, world_config: dict,
                   world_canon_store: dict, character_state: dict,
                   location_map: Optional[dict]) -> List[dict]:
    event_id = event.get("event_id", "unknown")
    created = append_facts_to_canon(
        world_canon_store, outcome.get("canon_facts_add", []),
        f"world_event:{event_id}", event_id=event_id, tick=tick,
    )
    witnesses = _witnesses_at(
        character_state,
        _event_location(event, outcome),
        # A contingent event has no single organizing location; witnesses are the
        # characters at the first location effect (if any), never everyone.
    )
    for fact in created:
        grant_knowledge(
            character_state, witnesses, fact["statement"],
            source_kind="witnessed", event_id=event_id, tick=tick,
            fact_id=fact.get("fact_id"),
        )
    flags = outcome.get("world_flags_set", {})
    if flags and isinstance(flags, dict):
        world_flags = world_config.setdefault("world_flags", {})
        for key, value in flags.items():
            world_flags[key] = value
    effects = outcome.get("location_effects", [])
    if effects and location_map:
        apply_location_effects(location_map, effects)
    return created


def resolve_event_by_creator(event: dict, status: str, outcome_id: str,
                             tick: int, world_config: dict,
                             world_canon_store: dict, character_state: dict,
                             location_map: Optional[dict]) -> dict:
    """Resolve a pending event while preserving the same invariants as ticking.

    Terminal events cannot be rewritten in place because their facts, flags and
    location effects may already have influenced later turns. Restoring a
    pre-event snapshot is the safe way to change that history.
    """
    current = event.get("status", "pending")
    if current != "pending":
        if current == status:
            return {"changed": False, "outcome_id": event.get("resolved_outcome_id")}
        raise ValueError(
            f"event is already '{current}'; restore a pre-event snapshot before changing its resolution"
        )
    if status == "pending":
        return {"changed": False, "outcome_id": None}

    valid_outcomes = [
        outcome for outcome in event.get("outcomes", [])
        if isinstance(outcome, dict) and not validate_event_outcome(outcome)
    ]
    outcome = None
    if outcome_id:
        outcome = next((item for item in valid_outcomes if item.get("outcome_id") == outcome_id), None)
        if outcome is None:
            raise ValueError(f"unknown or invalid outcome '{outcome_id}'")
        outcome_resolution = outcome.get("resolution", "resolved")
        if outcome_resolution != status:
            raise ValueError(
                f"outcome '{outcome_id}' resolves as '{outcome_resolution}', not '{status}'"
            )
    else:
        outcome = _by_resolution(valid_outcomes, status) or _synthetic_outcome(
            event.get("event_id", ""), status
        )

    _apply_outcome(
        event, outcome, tick, world_config, world_canon_store,
        character_state, location_map,
    )
    event["status"] = status
    event["resolution"] = status
    event["resolved_outcome_id"] = outcome.get("outcome_id")
    event["resolved_at_tick"] = tick
    return {"changed": True, "outcome_id": outcome.get("outcome_id")}


def _witnesses_at(character_state: dict, location: str) -> List[str]:
    if not location:
        return []
    target = location.strip().lower()
    return [
        char_id for char_id, state in character_state.items()
        if isinstance(state, dict) and str(state.get("location", "")).strip().lower() == target
    ]


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
    tick = world_config.get("story_clock", {}).get("tick", 0)
    resolved_ids = []
    for raw_event in events:
        if not isinstance(raw_event, dict):
            continue
        event = normalize_event(raw_event)
        if event.get("status") != "pending":
            continue
        trigger_conditions = event.get("trigger_conditions", [])
        if not trigger_conditions:
            continue

        triggered = eval_condition({"all": trigger_conditions}, character_state, world_config)
        if not triggered:
            deadline = event.get("deadline_tick")
            if deadline is not None and event.get("event_class", "organized") == "organized":
                try:
                    past_deadline = int(tick) > int(deadline)
                except (TypeError, ValueError):
                    past_deadline = False
                if past_deadline:
                    outcome = _synthetic_outcome(event.get("event_id", ""), "missed")
                    _apply_outcome(event, outcome, tick, world_config, world_canon_store,
                                   character_state, location_map)
                    event["status"] = "missed"
                    event["resolution"] = "missed"
                    event["resolved_outcome_id"] = outcome["outcome_id"]
                    event["resolved_at_tick"] = tick
                    resolved_ids.append(event.get("event_id", ""))
            continue

        outcomes = [o for o in event.get("outcomes", []) if isinstance(o, dict)]
        # Engine-owned result must be a valid outcome, not an arbitrary model blob.
        outcomes = [o for o in outcomes if not validate_event_outcome(o)]
        outcome = choose_resolution_outcome(event, outcomes, character_state, location_map, world_config)
        if not outcome:
            continue

        _apply_outcome(event, outcome, tick, world_config, world_canon_store,
                       character_state, location_map)
        resolution = outcome.get("resolution", "resolved")
        event["status"] = resolution
        event["resolution"] = resolution
        event["resolved_outcome_id"] = outcome.get("outcome_id")
        event["resolved_at_tick"] = tick
        resolved_ids.append(event.get("event_id", ""))
    return resolved_ids
