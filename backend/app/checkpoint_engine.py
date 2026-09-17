import json
import logging
import math
import os
from collections import Counter
from typing import Dict, List, Optional

from fastapi import HTTPException

from app.llm_client import call_llm, LLMCallError, parse_llm_json
from app.rag import _rag_tokenize, _rag_cosine_score, estimate_tokens, select_relevant_lore_cards
from app.state_manager import DEFAULT_STORY_CLOCK, eval_condition, _apply_outcome_payload, apply_state_changes
from app.language_detection import detect_story_language

logger = logging.getLogger(__name__)

try:
    from prompts import LOCATION_MAP_GENERATOR_PROMPT
except ImportError:
    from backend.prompts import LOCATION_MAP_GENERATOR_PROMPT


TEMPLATES = {
    "world_config.json": {
        "display_name": "",
        "genre": "",
        "power_system": "",
        "tone": "",
        "fixed_rules": [],
        "current_checkpoint_id": "",
        "completed_checkpoints": [],
        "branched_from": None,
        "lore_rag_max_tokens": None,
        "opening_mode": "ai_generate",
        "opening_text": "",
        "protagonist_id": "",
        "pacing_level": "Balanced",
        "output_length": "Standard",
        "pov_angle": "3rd_person_limited",
        "prelude_enabled": False,
        "prelude_confirmed": False,
        "language": "en",
        "story_clock": {
            "year": 1,
            "month": 1,
            "day": 1,
            "time_of_day": "morning",
            "season": "spring",
            "tick": 0
        },
        "foreshadowing_tracker": [],
        "linter_notification_enabled": True,
        "linter_auto_run": False,
        "keyword_auto_retry": False,
        "open_threads": [],
        "story_mode": "endless",
        "lifecycle_status": "active",
        "world_flags": {},
        "target_ending_scenario": None,
        "quest_board_enabled": False
    },
    "card_registry.json": {
        "cards": []
    },
    "canon_timeline.json": {
        "checkpoints": []
    },
    "character_state.json": {
        "characters": {}
    },
    "chapters.json": {
        "chapters": [],
        "running_summary": "",
        "memorable_beats": []
    },
    "world_canon_store.json": {
        "facts": []
    },
    "branch_local_delta.json": {
        "overrides": {}
    },
    "location_map.json": {
        "locations": []
    }
}


def make_card(card_id: str, card_type: str, name: str, content: str,
              unlock_checkpoint_id: str = None, status: str = "locked",
              entity_id: str = None, aliases: list = None,
              scope: str = None, entity_status: str = "active"):
    return {
        "id": card_id,
        "type": card_type,
        "name": name,
        "content": content,
        "unlock_checkpoint_id": unlock_checkpoint_id,
        "status": status,
        "entity_id": entity_id,
        "aliases": aliases or [],
        "scope": scope,
        "entity_status": entity_status
    }


def make_checkpoint(checkpoint_id: str, description: str,
                     required_conditions=None, cards_unlocked=None,
                     locations=None, allowed_characters=None,
                     time_window: str = "", realm_updates=None):
    return {
        "checkpoint_id": checkpoint_id,
        "description": description,
        "required_conditions": required_conditions or [],
        "cards_unlocked": cards_unlocked or [],
        "boundary": {
            "locations": locations or [],
            "allowed_characters": allowed_characters or [],
            "time_window": time_window
        },
        "realm_updates": realm_updates or {},
        "sub_beats": []
    }


def make_character(name: str, location: str = "", affinity=None,
                    realm: str = "", exp: int = 0, sub_stats=None,
                    knowledge_flags=None, inventory=None, karma: int = 0,
                    alive: bool = True,
                    relationships: Dict[str, str] = None, age: str = "",
                    known_skills: List[str] = None,
                    appearance: str = "", personality: str = "",
                    backstory: str = "", abilities_and_limits: str = "",
                    speech_style: str = "", secrets: str = ""):
    return {
        "name": name,
        "location": location,
        "affinity": affinity or {},
        "power_stat": {
            "realm": realm,
            "exp": exp,
            "sub_stats": sub_stats or {},
            "known_skills": known_skills or []
        },
        "knowledge_flags": knowledge_flags or [],
        "inventory": inventory or [],
        "karma": karma,
        "alive": alive,
        "relationships": relationships or {},
        "age": age,
        "appearance": appearance,
        "personality": personality,
        "backstory": backstory,
        "abilities_and_limits": abilities_and_limits,
        "speech_style": speech_style,
        "secrets": secrets
    }


def find_checkpoint(checkpoints: list, checkpoint_id: str):
    for cp in checkpoints:
        if cp["checkpoint_id"] == checkpoint_id:
            return cp
    return None


def get_active_cards(cards: list, checkpoint: dict, context_text: str = "",
                      max_lore_tokens: Optional[int] = None) -> list:
    allowed_chars = set(checkpoint["boundary"]["allowed_characters"])
    qualifying = []
    for c in cards:
        if c["status"] != "unlocked":
            continue
        if c["type"] == "char" and c["id"] not in allowed_chars:
            continue
        qualifying.append(c)

    lore_cards = [c for c in qualifying if c["type"] == "lore"]
    selected_lore = select_relevant_lore_cards(lore_cards, context_text, max_lore_tokens)
    selected_lore_ids = {c["id"] for c in selected_lore}

    return [c for c in qualifying if c["type"] != "lore" or c["id"] in selected_lore_ids]


def checkpoint_conditions_met(checkpoint: dict, character_state: dict, world_config: dict = None) -> bool:
    conditions = checkpoint.get("required_conditions", [])
    if not conditions:
        return True
    completed = []
    if world_config and isinstance(world_config, dict):
        completed = world_config.get("completed_checkpoints", []) or []
    results = []
    for c in conditions:
        if isinstance(c, str):
            results.append(c in completed)
        else:
            results.append(eval_condition(c, character_state, world_config))
    return all(results)


def sanitize_required_conditions(checkpoints: list, character_state: dict, world_config: dict = None) -> list:
    sanitized = []
    for cp in checkpoints:
        if not isinstance(cp, dict):
            continue
        conditions = cp.get("required_conditions", [])
        if not conditions:
            sanitized.append({
                "checkpoint_id": cp.get("checkpoint_id", "?"),
                "valid": True,
                "removed": []
            })
            continue

        valid_conditions = []
        removed = []
        for cond in conditions:
            if isinstance(cond, str):
                valid_conditions.append(cond)
                continue
            if not isinstance(cond, dict):
                removed.append(str(cond))
                continue
            field = cond.get("field", "")
            if not field or not isinstance(field, str):
                removed.append(str(cond))
                continue
            parts = field.split(".")
            if len(parts) < 2:
                removed.append(field)
                continue

            # story_clock.* and world_flags.* are always valid (they resolve at runtime)
            if parts[0] in ("story_clock", "world_flags"):
                valid_conditions.append(cond)
                continue

            char_id = parts[0]
            if char_id not in character_state:
                removed.append(field)
                continue
            cur = character_state[char_id]
            valid = True
            for key in parts[1:]:
                if isinstance(cur, dict):
                    if key not in cur:
                        valid = False
                        break
                    cur = cur[key]
                elif isinstance(cur, list):
                    try:
                        idx = int(key)
                        cur = cur[idx]
                    except (ValueError, IndexError):
                        valid = False
                        break
                else:
                    valid = False
                    break
            if valid:
                valid_conditions.append(cond)
            else:
                removed.append(field)

        sanitized.append({
            "checkpoint_id": cp.get("checkpoint_id", "?"),
            "valid": len(removed) == 0,
            "removed": removed
        })

    return sanitized


def _advance_sub_beats(current_checkpoint: dict, world_config: dict,
                        character_state: dict) -> list:
    sub_beats = current_checkpoint.get("sub_beats", [])
    if not sub_beats:
        return []

    current_id = current_checkpoint["checkpoint_id"]
    sub_beats_progress = world_config.setdefault("sub_beats_progress", {})
    completed_ids = set(sub_beats_progress.get(current_id, []))

    completed_this_turn = []
    for sub_beat in sub_beats:
        if not isinstance(sub_beat, dict):
            continue
        beat_id = sub_beat.get("beat_id", "")
        if not beat_id or beat_id in completed_ids:
            continue

        conditions = sub_beat.get("required_conditions", [])
        if conditions and not all(eval_condition(c, character_state, world_config) for c in conditions):
            continue

        completed_ids.add(beat_id)
        completed_this_turn.append(beat_id)
        break

    if completed_this_turn:
        sub_beats_progress[current_id] = list(completed_ids)

    return completed_this_turn


def advance_checkpoint_if_ready(canon_timeline: dict, world_config: dict,
                                 character_state: dict, card_registry: dict,
                                 chapter_closed: bool = False):
    checkpoints = canon_timeline.get("checkpoints", [])
    current_id = world_config.get("current_checkpoint_id", "")
    current_checkpoint = find_checkpoint(checkpoints, current_id)

    if not current_checkpoint:
        return None

    sub_beats_completed = _advance_sub_beats(
        current_checkpoint, world_config, character_state
    )

    sub_beats = current_checkpoint.get("sub_beats", [])
    sub_beats_progress = world_config.setdefault("sub_beats_progress", {})
    all_sub_beats_done = all(
        sb["beat_id"] in set(sub_beats_progress.get(current_id, []))
        for sb in sub_beats if isinstance(sb, dict) and sb.get("beat_id")
    ) if sub_beats else True

    next_id_to_advance = None

    if (not sub_beats and chapter_closed) or (sub_beats and all_sub_beats_done):
        for outcome in current_checkpoint.get("alternate_outcomes", []):
            if not isinstance(outcome, dict):
                continue
            conditions = outcome.get("conditions", [])
            if not conditions or all(eval_condition(c, character_state, world_config) for c in conditions):
                next_id_to_advance = outcome.get("next_checkpoint_id") or outcome.get("to_checkpoint_id")
                outcome_payload = outcome.get("apply") or outcome.get("state_changes", {})
                if outcome_payload:
                    _apply_outcome_payload(character_state, outcome_payload, world_config)
                break

        if not next_id_to_advance:
            default_next_id = current_checkpoint.get("default_next_checkpoint_id")

            if not default_next_id:
                current_index = next((i for i, cp in enumerate(checkpoints) if cp["checkpoint_id"] == current_id), None)
                if current_index is not None and current_index + 1 < len(checkpoints):
                    default_next_id = checkpoints[current_index + 1]["checkpoint_id"]

            if default_next_id:
                next_checkpoint = find_checkpoint(checkpoints, default_next_id)
                if next_checkpoint and checkpoint_conditions_met(next_checkpoint, character_state, world_config):
                    next_id_to_advance = default_next_id

    result = {
        "old_id": current_id,
        "sub_beats_completed": sub_beats_completed,
        "all_sub_beats_done": all_sub_beats_done,
        "to_checkpoint_id": None,
        "to_checkpoint_description": "",
        "cards_unlocked": [],
        "realm_changes": {},
        "applied_effects": []
    }

    if not next_id_to_advance:
        return result

    next_checkpoint = find_checkpoint(checkpoints, next_id_to_advance)
    if not next_checkpoint:
        return result

    completed = world_config.setdefault("completed_checkpoints", [])
    if current_id not in completed:
        completed.append(current_id)
    world_config["current_checkpoint_id"] = next_checkpoint["checkpoint_id"]

    unlocked_card_names = []
    next_cp_id = next_checkpoint["checkpoint_id"]
    for card in card_registry["cards"]:
        if card["id"] in next_checkpoint.get("cards_unlocked", []) or card.get("unlock_checkpoint_id") == next_cp_id:
            if card["status"] != "unlocked":
                card["status"] = "unlocked"
                unlocked_card_names.append(card["name"])

    realm_changes = {}
    realm_updates = next_checkpoint.get("realm_updates", {})
    if isinstance(realm_updates, dict):
        for char_id, new_realm in realm_updates.items():
            if char_id in character_state and isinstance(character_state[char_id], dict) and "power_stat" in character_state[char_id]:
                character_state[char_id]["power_stat"]["realm"] = new_realm
                realm_changes[char_id] = new_realm

    applied_effects = []
    for effect in next_checkpoint.get("status_effects", []):
        if not isinstance(effect, dict):
            continue
        char_id = effect.get("character_id")
        duration = effect.get("duration", 0)
        if not isinstance(duration, int) or duration <= 0:
            continue
        if char_id in character_state:
            char = character_state[char_id]
            if "status_effects" not in char:
                char["status_effects"] = []
            eff_name = effect.get("name", "Unknown")
            existing = next((e for e in char["status_effects"] if isinstance(e, dict) and e.get("name") == eff_name), None)
            if existing:
                existing["duration"] = duration
            else:
                char["status_effects"].append({"name": eff_name, "duration": duration})
            applied_effects.append(f"{eff_name} ({char_id})")

    result.update({
        "to_checkpoint_id": next_checkpoint["checkpoint_id"],
        "to_checkpoint_description": next_checkpoint.get("description", ""),
        "cards_unlocked": unlocked_card_names,
        "realm_changes": realm_changes,
        "applied_effects": applied_effects
    })

    return result


def _is_location_in_zone(location: str, allowed_locations: set) -> bool:
    loc_lower = location.lower().strip()
    for allowed in allowed_locations:
        allowed_lower = allowed.lower().strip()
        if loc_lower == allowed_lower:
            return True
        if loc_lower.startswith(allowed_lower + " - "):
            return True
    return False


def check_boundary_violations(state_changes: dict, checkpoint: dict) -> list:
    allowed_locations = set(checkpoint["boundary"]["locations"])
    violations = []
    for char_id, changes in state_changes.get("characters", {}).items():
        loc = changes.get("location")
        if loc and not _is_location_in_zone(loc, allowed_locations):
            violations.append({"character_id": char_id, "attempted_location": loc})
    return violations


def build_boundary_correction_note(violations: list, checkpoint: dict) -> str:
    lines = [
        f"- Character '{v['character_id']}' is moved to the location '{v['attempted_location']}', "
        "but this location is NOT within the allowed_locations of the current checkpoint."
        for v in violations
    ]
    allowed = checkpoint["boundary"]["locations"]
    return (
        "IMPORTANT NOTE - BOUNDARY VIOLATION: In the previous generation for this exact "
        "user_input this, you took the story outside the allowed scope:\n"
        + "\n".join(lines)
        + f"\nCurrent allowed_locations ONLY include: {allowed}. "
        "Note: sub-locations within a zone are valid (eg. 'Valdris Estate - Kitchen' is allowed if 'Valdris Estate' is in the list). "
        "Please completely REWRITE the chapter_text and state_changes for the same user_input. "
        "Keep characters within the allowed scope using a natural in-universe reason: "
        "the character chooses to stay because they are not done here yet, they are waiting for someone or something, "
        "they need to prepare before moving on, or a meaningful obstacle arises organically from the scene itself. "
        "Avoid generic, forced barriers like 'guards block the path' or 'a wall suddenly appears' — instead, "
        "use motivations, unfinished business, or story-appropriate complications that respect the world's premise. "
        "DO NOT move characters outside allowed_locations, and DO NOT write it like a dry system error message."
    )


BOUNDARY_HARD_REJECT_TEMPLATES = {
    "en": {
        "header": "The AI storyteller has 2 consecutive times moved the character outside the allowed scope of the current checkpoint (only includes: {allowed}):\n",
        "line": "- '{char_id}' is moved to '{attempted_location}'",
        "footer": "\nThis turn has been cancelled to avoid inconsistency between the content and character states. The action you just entered is NOT lost — please try again with a different action within the current scope, or rephrase it differently."
    },
    "vi": {
        "header": "Người kể chuyện AI đã 2 lần liên tiếp di chuyển nhân vật ra ngoài phạm vi cho phép của checkpoint hiện tại (chỉ bao gồm: {allowed}):\n",
        "line": "- Nhân vật '{char_id}' bị di chuyển tới '{attempted_location}'",
        "footer": "\nLượt này đã bị hủy để tránh bất đồng bộ giữa nội dung và trạng thái nhân vật. Hành động bạn vừa nhập KHÔNG bị mất — vui lòng thử lại với hành động khác trong phạm vi cho phép, hoặc diễn đạt theo cách khác."
    }
}


def raise_boundary_hard_reject(
    violations: list,
    checkpoint: dict,
    lang: Optional[str] = None,
    user_input: str = "",
    recent_text: str = "",
    world_config: Optional[dict] = None
) -> None:
    if not lang:
        lang = detect_story_language(user_input=user_input, recent_text=recent_text, world_config=world_config)

    tmpl = BOUNDARY_HARD_REJECT_TEMPLATES.get(lang, BOUNDARY_HARD_REJECT_TEMPLATES["en"])
    allowed = checkpoint.get("boundary", {}).get("locations", []) if isinstance(checkpoint, dict) and "boundary" in checkpoint else []
    lines = [
        tmpl["line"].format(
            char_id=v.get("character_id", ""),
            attempted_location=v.get("attempted_location", "")
        )
        for v in violations if isinstance(v, dict)
    ]
    detail_msg = tmpl["header"].format(allowed=allowed) + "\n".join(lines) + tmpl["footer"]

    raise HTTPException(status_code=409, detail=detail_msg)


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


def tick_endgame(world_config: dict, character_state: dict) -> dict:
    """
    Check if endgame conditions are met. Called after each turn.
    Returns dict with keys:
      - status_changed: bool
      - new_status: str | None (pending -> ready)
      - used_fallback: bool
      - message: str | None
    """
    story_mode = world_config.get("story_mode", "endless")
    if story_mode != "fixed_ending":
        return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}

    target = world_config.get("target_ending_scenario")
    if not target or not isinstance(target, dict):
        return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}

    if target.get("status") != "pending":
        return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}

    # Check timeout
    timeout_tick = target.get("timeout_tick")
    if timeout_tick is not None:
        clock = world_config.get("story_clock", {})
        current_tick = clock.get("tick", 0)
        if current_tick >= timeout_tick:
            target["status"] = "ready"
            target["used_fallback"] = True
            return {
                "status_changed": True,
                "new_status": "ready",
                "used_fallback": True,
                "message": "Endgame reached via timeout (fallback)."
            }

    # Check conditions
    conditions = target.get("endgame_conditions", [])
    if not conditions:
        return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}

    logic = target.get("endgame_conditions_logic", "all")

    if logic == "any":
        met = any(eval_condition(c, character_state, world_config) for c in conditions if isinstance(c, dict))
    else:
        met = all(eval_condition(c, character_state, world_config) for c in conditions if isinstance(c, dict))

    if met:
        target["status"] = "ready"
        return {
            "status_changed": True,
            "new_status": "ready",
            "used_fallback": False,
            "message": "Endgame conditions met."
        }

    return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}
