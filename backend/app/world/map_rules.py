"""Map rules responsibilities for Story Engine."""
from app.llm_client import LLMCallError
from app.llm_client import call_llm
from app.llm_client import parse_llm_json
from app.prompts import LOCATION_MAP_GENERATOR_PROMPT
import json


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
        return {"locations": locations}
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

    for char_id, changes in state_changes.get("characters", {}).items():
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
