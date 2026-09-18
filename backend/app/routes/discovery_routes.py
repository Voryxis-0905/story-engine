"""Discovery routes."""
from fastapi import APIRouter

from app.storage import require_world, read_world_file
from app.checkpoint_engine import check_map_based_restrictions
from app.story.views import player_character_view
from app.world.travel import find_location, find_route

try:
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.skill_limiter import check_skill_limiter

router = APIRouter()



@router.get("/worlds/{world_name}/codex")
def get_world_codex(world_name: str):
    world_path = require_world(world_name)
    card_registry = read_world_file(world_path, "card_registry.json")
    character_state = read_world_file(world_path, "character_state.json")
    world_config = read_world_file(world_path, "world_config.json")

    cards = card_registry.get("cards", []) if isinstance(card_registry, dict) else []
    unlocked_cards = [
        card for card in cards
        if isinstance(card, dict) and card.get("status") == "unlocked"
    ]
    characters = character_state.get("characters", {}) if isinstance(character_state, dict) else {}
    return {
        "cards": unlocked_cards,
        "characters": player_character_view(
            characters, world_config.get("protagonist_id", "")
        )
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
    current_location = main_char.get("location", "")
    current_on_map = find_location(location_map, current_location)
    enriched = []
    for loc in locations:
        loc_id = loc.get("id", "")
        # Use exactly the same rules as movement validation.
        location_name = loc.get("name") or loc_id
        violations = check_map_based_restrictions(
            {"characters": {main_char_id: {"location": location_name}}},
            {"locations": [loc]}, {main_char_id: main_char}, world_config
        )
        route = find_route(location_map, current_location, loc_id or location_name) if current_on_map else None
        is_reachable = route is not None if current_on_map else True
        is_unlocked = not violations and is_reachable
        reasons = []
        for violation in violations:
            if violation["reason"] == "exp":
                reasons.append(f"Cần {violation['required']} EXP (hiện có {violation['current']})")
            elif violation["reason"] == "realm":
                reasons.append(f"Cần đạt {violation['required']}")
            else:
                reasons.append(f"Cần tới mốc {violation['required']}")
        if not is_reachable:
            reasons.append("Không có tuyến đường nối từ vị trí hiện tại")

        enriched.append({
            **loc,
            "is_unlocked": is_unlocked,
            "is_reachable": is_reachable,
            "route_preview": [item.get("name") or item.get("id") for item in route] if route else [],
            "unlock_reason_missing": "; ".join(reasons) if reasons else None,
        })

    return {"locations": enriched}


@router.get("/worlds/{world_name}/quest_board")
def get_quest_board(world_name: str):
    """Player's quest view derived from explicit discovery records.

    A quest appears only for events the player has discovered, and its status
    follows the event lifecycle (active/completed/prevented/transformed/missed).
    A deadline is shown only when it was recorded at discovery time — never
    inferred from an arbitrary trigger condition. Editing free-text notes cannot
    lose a quest once it is recorded.
    """
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")

    if not world_config.get("quest_board_enabled", False):
        return {"quests": [], "enabled": False}

    from app.world_events import load_world_events
    from app.story.discovery import (
        load_discoveries, save_discoveries, ensure_start_discoveries,
        backfill_from_threads, quest_view,
    )

    events = load_world_events(world_path).get("events", [])
    tick = world_config.get("story_clock", {}).get("tick", 0)
    store = load_discoveries(world_path)
    changed = ensure_start_discoveries(store, events, tick)
    changed |= backfill_from_threads(store, events, world_config.get("open_threads", []), tick)
    if changed:
        save_discoveries(world_path, store)

    return {"quests": quest_view(events, store), "enabled": True}


@router.get("/worlds/{world_name}/journal")
def get_journal(world_name: str):
    """Consequence journal: every event the player has learned about, with the
    source and tick it was learned, and its current lifecycle status. Unlike the
    quest board this is not gated by quest_board_enabled, and it records events
    the player did not choose directly when they learned about them.
    """
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    from app.world_events import load_world_events
    from app.story.discovery import (
        load_discoveries, save_discoveries, ensure_start_discoveries,
        backfill_from_threads, quest_view,
    )
    events = load_world_events(world_path).get("events", [])
    tick = world_config.get("story_clock", {}).get("tick", 0)
    store = load_discoveries(world_path)
    changed = ensure_start_discoveries(store, events, tick)
    changed |= backfill_from_threads(store, events, world_config.get("open_threads", []), tick)
    if changed:
        save_discoveries(world_path, store)
    entries = sorted(quest_view(events, store), key=lambda q: q.get("discovered_at_tick") or 0, reverse=True)
    return {"entries": entries}
