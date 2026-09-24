"""Discovery routes."""
from fastapi import APIRouter

from app.storage import require_world, read_world_file
from app.checkpoint_engine import check_map_based_restrictions
from app.language_detection import detect_story_language
from app.story.views import player_character_view
from app.models import TravelPreviewRequest
from app.world.travel import (
    HIDDEN_DISCOVERY_STATES,
    find_location,
    find_route,
    is_hidden,
    preview_travel,
    scrub_preview_for_player,
    visible_location_map,
)

try:
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.skill_limiter import check_skill_limiter

router = APIRouter()


MAP_ACCESS_MESSAGES = {
    "en": {
        "exp": "Requires {required} EXP (currently {current})",
        "realm": "Requires {required}",
        "checkpoint": "Requires checkpoint {required}",
        "unreachable": "No route connects to this location from your current position",
        "undiscovered": "This location has not been discovered yet",
    },
    "vi": {
        "exp": "Cần {required} EXP (hiện có {current})",
        "realm": "Cần đạt {required}",
        "checkpoint": "Cần tới mốc {required}",
        "unreachable": "Không có tuyến đường nối từ vị trí hiện tại",
        "undiscovered": "Chưa khám phá địa điểm này",
    },
}


def map_access_message(language: str, reason: str, **values: object) -> str:
    """Return a player-facing map access message in the story language."""
    templates = MAP_ACCESS_MESSAGES.get(language, MAP_ACCESS_MESSAGES["en"])
    return templates[reason].format(**values)



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
    story_language = detect_story_language(world_config=world_config)

    characters = character_state.get("characters", {})
    main_char_id = world_config.get("protagonist_id") or world_config.get("main_character_id", "")
    main_char = characters.get(main_char_id, {})
    current_location = main_char.get("location", "")
    current_on_map = find_location(location_map, current_location)
    # One definition of "the player's map", shared with the travel preview.
    # Iterating this - not the raw list - is what keeps a hidden place out of the
    # response entirely. Scrubbing the name while still sending the entry would
    # leak its id, its exact position and a nameless node the player cannot
    # explain, which is worse than a name.
    player_location_map = visible_location_map(location_map, current_location)
    visible_ids = {loc.get("id") for loc in player_location_map.get("locations", [])}

    def _edge_target(edge):
        if isinstance(edge, str):
            return edge
        if isinstance(edge, dict):
            for key in ("location_id", "to", "id"):
                if edge.get(key):
                    return str(edge[key])
        return ""

    def _visible_edges(loc):
        kept = []
        for edge in loc.get("connected_to", []) or []:
            target = find_location(location_map, _edge_target(edge))
            if target and target.get("id") in visible_ids:
                kept.append(edge)
        return kept

    enriched = []
    for loc in player_location_map.get("locations", []):
        loc_id = loc.get("id", "")
        # Use exactly the same rules as movement validation.
        location_name = loc.get("name") or loc_id
        violations = check_map_based_restrictions(
            {"characters": {main_char_id: {"location": location_name}}},
            {"locations": [loc]}, {main_char_id: main_char}, world_config
        )
        visibility = "visited" if current_on_map and loc_id == current_on_map.get("id") else loc.get("discovery_status", "discovered")
        hidden = visibility in HIDDEN_DISCOVERY_STATES
        # Reachability must agree with what travel would actually do, so the
        # route is searched on the engine's full map - a journey that passes
        # through an undiscovered place is still a journey. Only the *names* are
        # restricted, by scrubbing the preview below.
        route = find_route(location_map, current_location, loc_id or location_name) if current_on_map and not hidden else None
        is_reachable = route is not None if current_on_map else True
        is_unlocked = not violations and is_reachable and not hidden
        reasons = []
        for violation in violations:
            if violation["reason"] == "exp":
                reasons.append(map_access_message(
                    story_language, "exp", required=violation["required"], current=violation["current"]
                ))
            elif violation["reason"] == "realm":
                reasons.append(map_access_message(story_language, "realm", required=violation["required"]))
            else:
                reasons.append(map_access_message(story_language, "checkpoint", required=violation["required"]))
        if not is_reachable:
            reasons.append(map_access_message(story_language, "unreachable"))
        if hidden:
            reasons = [map_access_message(story_language, "undiscovered")]

        # The engine's route is the reader of truth for "can I get there"; the
        # player-facing stop list is scrubbed of hidden names.
        public_location = dict(loc)
        if hidden:
            public_location.update(name="Unknown location", description="", tags=[], connected_to=[])
        else:
            public_location["connected_to"] = _visible_edges(loc)

        route_names = [
            item.get("name") or item.get("id") for item in route
        ] if route else []
        route_redacted = False
        if route_names:
            scrubbed = scrub_preview_for_player({"route": route_names}, location_map)
            route_names = scrubbed.get("route") or []
            # A route through uncharted ground comes back deliberately empty.
            # Publishing even the *count* would tell the player how many hidden
            # stops lie between here and there, so the client is told only that
            # the route exists and is redacted.
            route_redacted = bool(scrubbed.get("route_redacted"))

        enriched.append({
            **public_location,
            "discovery_status": visibility,
            "is_unlocked": is_unlocked,
            "is_reachable": is_reachable,
            "route_preview": route_names,
            "route_redacted": route_redacted,
            "unlock_reason_missing": "; ".join(reasons) if reasons else None,
        })

    return {"locations": enriched}


@router.post("/worlds/{world_name}/travel/preview")
def preview_world_travel(world_name: str, request: TravelPreviewRequest):
    """Return an engine-owned route preview without rolling or writing state.

    Computed on the engine's full map, because real travel really does pass
    through undiscovered places - reporting a journey as unreachable merely
    because a stop is hidden would contradict the rules that will actually run.
    The response is then scrubbed so the hidden name never reaches the client:
    the player learns a journey is possible and how long it takes, not where
    the unnamed stop is.
    """
    world_path = require_world(world_name)
    location_map = read_world_file(world_path, "location_map.json")
    character_state = read_world_file(world_path, "character_state.json")
    world_config = read_world_file(world_path, "world_config.json")
    characters = character_state.get("characters", {})
    protagonist_id = world_config.get("protagonist_id") or world_config.get("main_character_id", "")
    protagonist = characters.get(protagonist_id, {})
    current_location = protagonist.get("location", "")
    result = preview_travel(
        location_map, current_location, request.destination,
        tick_minutes=int(world_config.get("travel_tick_minutes", 60) or 60),
    )
    destination = find_location(location_map, request.destination)
    if destination and is_hidden(destination):
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
    # Last gate: nothing leaves the server carrying a hidden place's name.
    return scrub_preview_for_player(result, location_map)


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
    """Character relationships for the Codex; geography belongs to the map."""
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

    # A relationship may name an NPC who has not appeared yet. A graph edge
    # needs both ends to exist, so drop dangling and self-referential links.
    edges = [
        edge for edge in edges
        if edge["target"] in seen_nodes and edge["source"] != edge["target"]
    ]

    return {"nodes": nodes, "edges": edges}
