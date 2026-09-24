"""Map rules responsibilities for Story Engine."""
from app.llm_client import LLMCallError
from app.llm_client import call_llm
from app.llm_client import parse_llm_json
from app.prompts import LOCATION_MAP_GENERATOR_PROMPT
from app.world.terrain import normalize_terrain_fields
import json
import logging

logger = logging.getLogger(__name__)

_missing_protagonist_warned = False


def reconcile_checkpoint_location_gates(location_map: dict, checkpoints: list,
                                        character_state: dict) -> dict:
    """Remove generated gates that make an event venue inaccessible on arrival.

    A checkpoint describes an event, not an EXP reward.  Its venue must be
    reachable when that checkpoint becomes current.  Explicitly edited maps
    are unaffected; this runs only on newly generated maps.
    """
    locations = location_map.get("locations", [])
    if not isinstance(locations, list):
        return location_map
    initial = next((cp for cp in checkpoints if isinstance(cp, dict)), {})
    initial_places = set(initial.get("boundary", {}).get("locations", []) or [])
    initial_places.update(
        char.get("location") for char in character_state.values()
        if isinstance(char, dict) and char.get("location")
    )
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        name = loc.get("name", "")
        serving = [cp for cp in checkpoints if isinstance(cp, dict) and
                   name in (cp.get("boundary", {}).get("locations", []) or [])]
        if name in initial_places:
            loc["unlock_realm"] = None
            loc["unlock_exp"] = 0
            loc["unlock_checkpoint_id"] = None
        elif serving:
            # A player may arrive early and change how the event unfolds.
            # A checkpoint is not an access requirement for its venue.
            loc["unlock_realm"] = None
            loc["unlock_exp"] = 0
            loc["unlock_checkpoint_id"] = None
    return location_map


def generate_location_map(world_config: dict, checkpoints: list,
                           character_state: dict, world_name: str = None) -> dict:
    from app.storage import has_real_api_key
    if not has_real_api_key(world_name):
        return {"locations": []}

    payload = json.dumps({
        "world_config": {
            "display_name": world_config.get("display_name", ""),
            "genre": world_config.get("genre", ""),
            "power_system": world_config.get("power_system", ""),
            "tone": world_config.get("tone", ""),
            "story_thesis": world_config.get("story_thesis", ""),
            "fixed_rules": world_config.get("fixed_rules", []),
        },
        "checkpoints": [
            {
                "checkpoint_id": cp.get("checkpoint_id", ""),
                "description": cp.get("description", ""),
                "boundary": cp.get("boundary", {}),
            }
            for cp in (checkpoints or [])
            if isinstance(cp, dict)
        ],
        "characters": {
            cid: {
                "name": c.get("name", ""),
                "location": c.get("location", ""),
                "power_stat": c.get("power_stat", {}),
            }
            for cid, c in (character_state or {}).items()
            if isinstance(c, dict)
        }
    }, ensure_ascii=False)

    try:
        raw = call_llm(LOCATION_MAP_GENERATOR_PROMPT, payload,
                       world_name=world_name, role="planner")
        res = parse_llm_json(raw, expected_type=dict)
        locations = res.get("locations", [])
        if not isinstance(locations, list):
            locations = []
        for loc in locations:
            if isinstance(loc, dict):
                loc["x"] = max(0, min(100, float(loc.get("x", 0))))
                loc["y"] = max(0, min(100, float(loc.get("y", 0))))
                loc["unlock_exp"] = max(0, int(loc.get("unlock_exp", 0)))
                normalize_terrain_fields(loc)
        return reconcile_checkpoint_location_gates(
            {"locations": locations}, checkpoints or [], character_state or {})
    except (LLMCallError, ValueError, json.JSONDecodeError, TypeError):
        return {"locations": []}


def _get_location_unlock_requirements(location_map: dict, location_name: str) -> dict:
    locations = location_map.get("locations", []) if isinstance(location_map, dict) else []
    loc_lower = location_name.lower().strip()
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        if loc.get("name", "").lower().strip() == loc_lower:
            return {
                "unlock_realm": loc.get("unlock_realm"),
                "unlock_exp": loc.get("unlock_exp", 0),
                "unlock_checkpoint_id": loc.get("unlock_checkpoint_id"),
            }
        if loc.get("id", "").lower() == loc_lower:
            return {
                "unlock_realm": loc.get("unlock_realm"),
                "unlock_exp": loc.get("unlock_exp", 0),
                "unlock_checkpoint_id": loc.get("unlock_checkpoint_id"),
            }
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        loc_name = loc.get("name", "").lower().strip()
        if loc_name and loc_lower.startswith(loc_name + " - "):
            return {
                "unlock_realm": loc.get("unlock_realm"),
                "unlock_exp": loc.get("unlock_exp", 0),
                "unlock_checkpoint_id": loc.get("unlock_checkpoint_id"),
            }
    return {"unlock_realm": None, "unlock_exp": 0, "unlock_checkpoint_id": None}


def check_map_based_restrictions(state_changes: dict, location_map: dict,
                                  character_state: dict, world_config: dict) -> list:
    if not location_map or not isinstance(location_map, dict):
        return []
    locations = location_map.get("locations", [])
    if not locations:
        return []
    violations = []
    completed_checkpoints = set(world_config.get("completed_checkpoints", []) or [])
    current_cp_id = world_config.get("current_checkpoint_id", "")

    # Map progression gates describe the player's access, so only the protagonist
    # is checked: NPCs need no protagonist EXP to attend events.
    protagonist_id = world_config.get("protagonist_id") or world_config.get("main_character_id", "")
    if not protagonist_id:
        # Without a protagonist every character would be skipped, silently
        # disabling every gate. Say so once instead of appearing to check.
        global _missing_protagonist_warned
        if not _missing_protagonist_warned:
            _missing_protagonist_warned = True
            logger.warning(
                "world_config has neither 'protagonist_id' nor 'main_character_id'; "
                "map progression restrictions cannot be evaluated and are skipped."
            )
        return []

    for char_id, changes in state_changes.get("characters", {}).items():
        if char_id != protagonist_id:
            continue
        loc = changes.get("location")
        if not loc:
            continue
        req = _get_location_unlock_requirements(location_map, loc)
        if not req:
            continue

        char_data = None
        if isinstance(character_state, dict):
            char_data = character_state.get(char_id)
        if not isinstance(char_data, dict):
            continue

        power_stat = char_data.get("power_stat", {}) or {}
        char_realm = str(power_stat.get("realm", "") or "")
        char_exp = int(power_stat.get("exp", 0) or 0)

        unlock_realm = req.get("unlock_realm")
        unlock_exp = req.get("unlock_exp", 0)
        unlock_cp_id = req.get("unlock_checkpoint_id")

        if unlock_realm and char_realm.lower() != unlock_realm.lower():
            violations.append({
                "character_id": char_id,
                "attempted_location": loc,
                "reason": "realm",
                "required": unlock_realm,
                "current": char_realm,
            })
            continue
        if unlock_exp > 0 and char_exp < unlock_exp:
            violations.append({
                "character_id": char_id,
                "attempted_location": loc,
                "reason": "exp",
                "required": unlock_exp,
                "current": char_exp,
            })
            continue
        if unlock_cp_id and unlock_cp_id not in completed_checkpoints and unlock_cp_id != current_cp_id:
            violations.append({
                "character_id": char_id,
                "attempted_location": loc,
                "reason": "checkpoint",
                "required": unlock_cp_id,
                "current": current_cp_id,
            })
            continue

    return violations


def build_map_restriction_note(violations: list) -> str:
    if not violations:
        return ""
    lines = []
    for v in violations:
        reason = v.get("reason", "")
        if reason == "realm":
            lines.append(
                f"- Character '{v['character_id']}' attempts to move to '{v['attempted_location']}', "
                f"which requires realm '{v['required']}' (current: '{v['current']}')"
            )
        elif reason == "exp":
            lines.append(
                f"- Character '{v['character_id']}' attempts to move to '{v['attempted_location']}', "
                f"which requires {v['required']} EXP (current: {v['current']})"
            )
        elif reason == "checkpoint":
            lines.append(
                f"- Character '{v['character_id']}' attempts to move to '{v['attempted_location']}', "
                f"which requires reaching checkpoint '{v['required']}' "
                f"(current: '{v['current']}')"
            )
        else:
            lines.append(
                f"- Character '{v['character_id']}' attempts to move to '{v['attempted_location']}', "
                f"but has not met the requirements"
            )
    return (
        "MAP RESTRICTION: The following characters attempted to move to locations "
        "that are locked behind progression gates:\n"
        + "\n".join(lines)
        + "\nPlease REWRITE the state_changes to keep characters within areas they have already unlocked."
    )
