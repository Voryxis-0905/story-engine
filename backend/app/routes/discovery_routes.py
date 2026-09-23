"""Discovery routes."""
from fastapi import APIRouter

from app.storage import require_world, read_world_file
from app.checkpoint_engine import check_map_based_restrictions
from app.story.views import player_character_view
from app.models import TravelPreviewRequest
from app.world.travel import find_location, find_route, preview_travel

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
    # The legacy player endpoint now uses the same visibility projection as the
    # status endpoint so a fallback request cannot reveal hidden locations.
    return get_world_location_map_status(world_name)


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
    visible_locations = [loc for loc in locations if (
        loc.get("discovery_status", "discovered") not in ("unknown", "creator_only")
        or (current_on_map and loc.get("id") == current_on_map.get("id"))
    )]
    player_location_map = {"locations": visible_locations}
    enriched = []
    for loc in locations:
        loc_id = loc.get("id", "")
        # Use exactly the same rules as movement validation.
        location_name = loc.get("name") or loc_id
        violations = check_map_based_restrictions(
            {"characters": {main_char_id: {"location": location_name}}},
            {"locations": [loc]}, {main_char_id: main_char}, world_config
        )
        visibility = "visited" if current_on_map and loc_id == current_on_map.get("id") else loc.get("discovery_status", "discovered")
        hidden = visibility in ("unknown", "creator_only")
        route = find_route(player_location_map, current_location, loc_id or location_name) if current_on_map and not hidden else None
        is_reachable = route is not None if current_on_map else True
        is_unlocked = not violations and is_reachable and not hidden
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
        if hidden:
            reasons = ["Chưa khám phá địa điểm này"]

        public_location = dict(loc)
        if hidden:
            public_location.update(name="Unknown location", description="", tags=[], connected_to=[])

        enriched.append({
            **public_location,
            "discovery_status": visibility,
            "is_unlocked": is_unlocked,
            "is_reachable": is_reachable,
            "route_preview": [item.get("name") or item.get("id") for item in route] if route else [],
            "unlock_reason_missing": "; ".join(reasons) if reasons else None,
        })

    return {"locations": enriched}


@router.post("/worlds/{world_name}/travel/preview")
def preview_world_travel(world_name: str, request: TravelPreviewRequest):
    """Return an engine-owned route preview without rolling or writing state."""
    world_path = require_world(world_name)
    location_map = read_world_file(world_path, "location_map.json")
    character_state = read_world_file(world_path, "character_state.json")
    world_config = read_world_file(world_path, "world_config.json")
    characters = character_state.get("characters", {})
    protagonist_id = world_config.get("protagonist_id") or world_config.get("main_character_id", "")
    protagonist = characters.get(protagonist_id, {})
    result = preview_travel(
        location_map, protagonist.get("location", ""), request.destination,
        tick_minutes=int(world_config.get("travel_tick_minutes", 60) or 60),
    )
    destination = find_location(location_map, request.destination)
    if destination and destination.get("discovery_status", "discovered") in ("unknown", "creator_only"):
        return {"status": "blocked", "reason": "destination_undiscovered", "destination": "Unknown location",
                "route": [], "legs": [], "elapsed_minutes": 0, "estimated_ticks": 0,
                "requirements_missing": [{"reason": "undiscovered"}]}
    if destination and result.get("status") == "available":
        destination_name = destination.get("name") or destination.get("id", "")
        violations = check_map_based_restrictions(
            {"characters": {protagonist_id: {"location": destination_name}}},
            {"locations": [destination]}, {protagonist_id: protagonist}, world_config,
        )
        if violations:
            result.update(status="blocked", reason="destination_locked",
                          requirements_missing=violations)
    result.setdefault("requirements_missing", [])
    return result


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


@router.get("/worlds/{world_name}/affinity-graph")
def get_affinity_graph(world_name: str):
    world_path = require_world(world_name)
    try:
        character_state = read_world_file(world_path, "character_state.json")
    except FileNotFoundError:
        character_state = {"characters": {}}

    characters = character_state.get("characters", {}) if isinstance(character_state, dict) else {}
    nodes = []
    edges = []
    seen_nodes = set()

    for cid, cdata in characters.items():
        if not isinstance(cdata, dict):
            continue
        seen_nodes.add(cid)
        nodes.append({
            "id": cid,
            "label": cdata.get("name") or cid,
            "type": "character",
        })
        relationships = cdata.get("relationships", {})
        if isinstance(relationships, dict):
            for target_id, rel in relationships.items():
                label = ""
                if isinstance(rel, dict):
                    label = str(rel.get("label") or rel.get("dynamic") or rel.get("affinity") or "knows")
                elif rel is not None:
                    label = str(rel)
                edges.append({
                    "source": cid,
                    "target": target_id,
                    "label": label or "knows",
                })

    try:
        location_map = read_world_file(world_path, "location_map.json")
    except FileNotFoundError:
        location_map = {}

    if isinstance(location_map, dict):
        for loc in location_map.get("locations", []) or []:
            if not isinstance(loc, dict):
                continue
            lid = loc.get("id") or loc.get("name")
            if not lid or lid in seen_nodes:
                continue
            seen_nodes.add(lid)
            nodes.append({
                "id": lid,
                "label": loc.get("name") or lid,
                "type": "location",
            })
            for connected in loc.get("connected_to", []) or []:
                if isinstance(connected, dict):
                    connected = (
                        connected.get("to")
                        or connected.get("location_id")
                        or connected.get("id")
                    )
                if not isinstance(connected, str) or not connected:
                    continue
                edges.append({
                    "source": lid,
                    "target": connected,
                    "label": "connected",
                })

    # Relationships and connected_to may name characters or locations that are
    # not in the world state yet (an NPC who has not appeared, a route to a place
    # never entered). A graph edge needs both ends to exist, so drop the dangling
    # ones rather than handing the renderer an edge it cannot draw.
    edges = [
        edge for edge in edges
        if edge["target"] in seen_nodes and edge["source"] != edge["target"]
    ]

    return {"nodes": nodes, "edges": edges}
