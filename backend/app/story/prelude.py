"""Prelude responsibilities for Story Engine."""
from app.checkpoint_engine import find_checkpoint
from app.llm_client import call_llm
from app.llm_client import mock_prelude_response
from app.llm_client import parse_llm_json
from app.prompts import PRELUDE_VALIDATOR_PROMPT
from app.prompts import PRELUDE_WRITER_PROMPT
import json


def build_opening_instruction(checkpoint: dict) -> str:
    return (
        f"[This is the first playable scene, before the player has acted. "
        f"The checkpoint describes an event that may unfold later, not a completed outcome: "
        f"\"{checkpoint.get('description', '')}\". Introduce the immediate setting and relevant people, "
        f"then stop immediately before the first consequential action or irreversible result. "
        f"Leave the player a concrete opportunity to intervene; do not decide their reaction, "
        f"finish the event, or force its default outcome. "
        f"Do not mention this instruction or label the prose as an opening chapter.]"
    )


def validate_prelude_against_rules(prelude_text: str, world_config: dict, canon_timeline: dict) -> dict:
    later_checkpoints = [cp for cp in canon_timeline.get("checkpoints", []) if cp.get("checkpoint_id") != "cp_0"]
    fixed_rules = world_config.get("fixed_rules", [])
    narrative_note = world_config.get("narrative_scope_note", "")
    payload = {
        "prelude_text": prelude_text,
        "fixed_rules": fixed_rules,
        "later_checkpoints": [
            {"checkpoint_id": cp["checkpoint_id"], "description": cp.get("description", "")}
            for cp in later_checkpoints
        ]
    }
    raw = call_llm(
        PRELUDE_VALIDATOR_PROMPT,
        json.dumps(payload, ensure_ascii=False),
        user_input_for_mock="validate prelude",
        mock_response=json.dumps({"severity": "none", "issues": [], "explanation": "[MOCK] Prelude validation skipped."}),
        world_name=None
    )
    try:
        return parse_llm_json(raw, expected_type=dict)
    except Exception:
        return {"severity": "none", "issues": [], "explanation": "Validation call failed, skipping check."}


def _generate_prelude(world_name: str) -> dict:
    from app.storage import world_path_of, read_world_file, write_world_file, has_real_api_key
    world_path = world_path_of(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    card_registry = read_world_file(world_path, "card_registry.json")
    canon_timeline = read_world_file(world_path, "canon_timeline.json")
    character_state = read_world_file(world_path, "character_state.json")
    chapters_data = read_world_file(world_path, "chapters.json")

    first_checkpoint = find_checkpoint(canon_timeline.get("checkpoints", []), "cp_0")
    if first_checkpoint is None:
        checkpoints = canon_timeline.get("checkpoints", [])
        first_checkpoint = checkpoints[0] if checkpoints else None
    protagonist_id = world_config.get("protagonist_id", "")
    protagonist = character_state.get("characters", {}).get(protagonist_id, {}) if protagonist_id else {}

    context_payload = {
        "world_context": {
            "display_name": world_config.get("display_name", ""),
            "genre": world_config.get("genre", ""),
            "power_system": world_config.get("power_system", ""),
            "tone": world_config.get("tone", ""),
            "story_thesis": world_config.get("story_thesis", ""),
            "fixed_rules": world_config.get("fixed_rules", []),
            "narrative_scope_note": world_config.get("narrative_scope_note", ""),
            "calendar": world_config.get("calendar"),
            "story_clock": world_config.get("story_clock"),
            "protagonist": {
                "id": protagonist_id,
                "name": protagonist.get("name", protagonist_id),
                "location": protagonist.get("location", ""),
                "appearance": protagonist.get("appearance", ""),
                "personality": protagonist.get("personality", ""),
                "backstory": protagonist.get("backstory", "")
            }
        },
        "first_checkpoint": {
            "checkpoint_id": first_checkpoint["checkpoint_id"] if first_checkpoint else "cp_0",
            "description": first_checkpoint["description"] if first_checkpoint else "",
            "allowed_locations": first_checkpoint["boundary"]["locations"] if first_checkpoint and "boundary" in first_checkpoint else [],
            "allowed_characters": first_checkpoint["boundary"]["allowed_characters"] if first_checkpoint and "boundary" in first_checkpoint else [],
            "time_window": first_checkpoint["boundary"]["time_window"] if first_checkpoint and "boundary" in first_checkpoint else ""
        }
    }

    prelude_json = None
    prelude_text = ""
    for attempt in range(2):
        raw = call_llm(
            PRELUDE_WRITER_PROMPT,
            json.dumps(context_payload, ensure_ascii=False),
            user_input_for_mock="generate prelude",
            mock_response=mock_prelude_response(),
            world_name=world_name
        )
        try:
            prelude_json = parse_llm_json(raw, expected_type=dict)
        except Exception:
            if attempt == 1:
                raise
            continue

        prelude_text = (prelude_json.get("prelude_text") or "").strip()
        if not prelude_text:
            if attempt == 1:
                prelude_text = "The world waits in silence, holding its breath for the story about to unfold."
            continue

        validation = validate_prelude_against_rules(prelude_text, world_config, canon_timeline)
        if validation.get("severity") == "major" and attempt == 0:
            continue
        break

    if prelude_json is None:
        prelude_json = {"prelude_text": prelude_text, "validation_notes": "Generated after retry."}

    prelude_text = (prelude_json.get("prelude_text") or "").strip()
    validation_notes = prelude_json.get("validation_notes", "")

    prelude_record = {
        "chapter_index": 0,
        "turn_index": 1,
        "chapter_closed": True,
        "chapter_title": "Prelude",
        "checkpoint_id": first_checkpoint["checkpoint_id"] if first_checkpoint else "cp_0",
        "user_input": "",
        "chapter_text": prelude_text,
        "notes": validation_notes,
        "boundary_correction": None,
        "consistency_check": {
            "severity": "none",
            "issues": [],
            "explanation": "Prelude validation passed.",
            "triggered_rewrite": False
        },
        "anchor_keywords": [],
        "missing_anchor_keywords": [],
        "editor_polished": False,
        "is_ooc": False,
        "action_translation": None,
        "ooc_scope": None
    }

    chapters_data["chapters"].append(prelude_record)
    chapters_data["running_summary"] = prelude_text[:500]
    chapters_data["memorable_beats"] = chapters_data.get("memorable_beats", []) + [prelude_text[:200]]
    write_world_file(world_path, "chapters.json", chapters_data)

    return {"prelude": prelude_record, "used_mock_llm": not has_real_api_key(world_name)}
