"""Discovery routes."""
from fastapi import APIRouter

from app.storage import require_world, read_world_file
from app.checkpoint_engine import check_map_based_restrictions

try:
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.skill_limiter import check_skill_limiter

router = APIRouter()



@router.get("/worlds/{world_name}/codex")
def get_world_codex(world_name: str):
    world_path = require_world(world_name)
    cards = read_world_file(world_path, "card_registry.json")
    chars = read_world_file(world_path, "character_state.json")

    unlocked_cards = [c for c in cards if c.get("status") == "unlocked"]
    return {
        "cards": unlocked_cards,
        "characters": chars
    }


@router.get("/worlds/{world_name}/location-map")
def get_world_location_map(world_name: str):
    world_path = require_world(world_name)
    try:
        location_map = read_world_file(world_path, "location_map.json")
    except FileNotFoundError:
        return {"locations": []}
    return location_map


@router.get("/worlds/{world_name}/location-map/status")
def get_world_location_map_status(world_name: str):
    world_path = require_world(world_name)
    try:
        location_map = read_world_file(world_path, "location_map.json")
    except FileNotFoundError:
        return {"locations": []}

    try:
        character_state = read_world_file(world_path, "character_state.json")
    except FileNotFoundError:
        character_state = {"characters": {}}

    try:
        world_config = read_world_file(world_path, "world_config.json")
    except FileNotFoundError:
        world_config = {}

    characters = character_state.get("characters", {})
    main_char_id = world_config.get("protagonist_id") or world_config.get("main_character_id", "")
    main_char = characters.get(main_char_id, {})
    locations = location_map.get("locations", [])
    enriched = []
    for loc in locations:
        loc_id = loc.get("id", "")
        # Use exactly the same rules as movement validation.
        location_name = loc.get("name") or loc_id
        violations = check_map_based_restrictions(
            {"characters": {main_char_id: {"location": location_name}}},
            {"locations": [loc]}, {main_char_id: main_char}, world_config
        )
        is_unlocked = not violations
        reasons = []
        for violation in violations:
            if violation["reason"] == "exp":
                reasons.append(f"Cần {violation['required']} EXP (hiện có {violation['current']})")
            elif violation["reason"] == "realm":
                reasons.append(f"Cần đạt {violation['required']}")
            else:
                reasons.append(f"Cần tới mốc {violation['required']}")

        enriched.append({
            **loc,
            "is_unlocked": is_unlocked,
            "unlock_reason_missing": "; ".join(reasons) if reasons else None,
        })

    return {"locations": enriched}


@router.get("/worlds/{world_name}/quest_board")
def get_quest_board(world_name: str):
    """
    Return active quests for the world if quest_board_enabled is true.
    Quests are derived from world_events.json pending events that are either:
    - discoverable_from_start: true, OR
    - event_id appears in open_threads
    """
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")

    if not world_config.get("quest_board_enabled", False):
        return {"quests": [], "enabled": False}

    # Load world_events
    from app.world_events import load_world_events
    world_events = load_world_events(world_path)
    events = world_events.get("events", [])

    open_threads = world_config.get("open_threads", [])
    # Flatten open_threads notes into a set for quick lookup
    thread_texts = set()
    for thread in open_threads:
        if isinstance(thread, dict):
            note = thread.get("note", "")
            if note:
                thread_texts.add(note.lower())
        elif isinstance(thread, str):
            thread_texts.add(thread.lower())

    quests = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("status") != "pending":
            continue

        event_id = event.get("event_id", "")
        discoverable = event.get("discoverable_from_start", False)

        # Check if event is known via open_threads
        event_in_threads = False
        if event_id:
            for thread_text in thread_texts:
                if event_id.lower() in thread_text or event_id in thread_text:
                    event_in_threads = True
                    break

        if not discoverable and not event_in_threads:
            continue

        # Build quest entry
        trigger_conditions = event.get("trigger_conditions", [])
        deadline_tick = None
        for cond in trigger_conditions:
            if isinstance(cond, dict) and cond.get("field") == "story_clock.tick":
                deadline_tick = cond.get("value")
                break

        quests.append({
            "quest_id": event_id,
            "title": event.get("quest_hint_title") or event.get("title", "Unknown Quest"),
            "hint": event.get("quest_hint_text") or "",
            "location_hint": event.get("location_hint"),
            "deadline_tick": deadline_tick,
            "discoverable_from_start": discoverable,
        })

    return {"quests": quests, "enabled": True}
