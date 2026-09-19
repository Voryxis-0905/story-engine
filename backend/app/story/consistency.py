"""Consistency responsibilities for Story Engine."""
import logging
from app.llm_client import LLMCallError
from app.llm_client import call_llm
from app.llm_client import mock_consistency_checker_response
from app.llm_client import parse_llm_json
from app.prompts import CONSISTENCY_CHECKER_SYSTEM_PROMPT
from app.prompts import EXTRACTOR_SYSTEM_PROMPT
import json
from app.world.calendar_clock import advance_story_clock, normalize_elapsed_time

logger = logging.getLogger(__name__)


def run_extractor_cross_check(
    world_name: str,
    chapter_text: str,
    existing_facts: list,
    world_config: dict,
) -> dict:
    payload = json.dumps({
        "chapter_text": chapter_text,
        "existing_canon_facts": existing_facts,
        "world_config": {
            "genre": world_config.get("genre", ""),
            "fixed_rules": world_config.get("fixed_rules", []),
            "tone": world_config.get("tone", ""),
        }
    }, ensure_ascii=False)
    try:
        raw = call_llm(
            EXTRACTOR_SYSTEM_PROMPT,
            payload,
            world_name=world_name,
            role="extractor"
        )
        result = parse_llm_json(raw, expected_type=dict)
        issues = result.get("issues", []) if isinstance(result, dict) else []
        if not isinstance(issues, list):
            issues = []
        return {
            "checked": True,
            "issue_count": len(issues),
            "issues": issues,
            "extractor_output": result,
        }
    except (LLMCallError, ValueError, json.JSONDecodeError) as e:
        logger.warning("Extractor cross-check skipped for world=%s: %s", world_name, e)
        return {
            "checked": False,
            "issue_count": 0,
            "issues": [],
            "error": str(e),
        }


def build_consistency_checker_payload(chapter_text: str, state_changes: dict,
                                        world_config: dict, checkpoint: dict,
                                        active_cards: list,
                                        character_state_before: dict,
                                        engine_outcomes: dict = None) -> dict:
    outcomes = engine_outcomes or {}
    start_clock = world_config.get("story_clock", {})
    end_clock = dict(start_clock) if isinstance(start_clock, dict) else {}
    if world_config.get("timekeeping_mode") == "duration" and end_clock:
        travel = outcomes.get("travel_resolution") or {}
        skip = outcomes.get("time_skip_resolution") or {}
        if travel and travel.get("status") in ("arrived", "interrupted"):
            elapsed = {"total_seconds": int(travel.get("elapsed_minutes", 0) or 0) * 60}
        elif skip:
            elapsed = {"total_seconds": int(skip.get("granted_minutes", 0) or 0) * 60}
        elif outcomes.get("opening_setup"):
            elapsed = {"total_seconds": 0}
        else:
            elapsed = normalize_elapsed_time(
                (state_changes or {}).get("elapsed_time"), fallback_minutes=5,
                max_minutes=360,
            )
        advance_story_clock(end_clock, elapsed, world_config.get("calendar"))
    before_characters = character_state_before if isinstance(character_state_before, dict) else {}
    protagonist_id = world_config.get("protagonist_id", "")
    protagonist_before = before_characters.get(protagonist_id, {})
    proposed_characters = (state_changes or {}).get("characters", {})
    protagonist_after = proposed_characters.get(protagonist_id, {}) if isinstance(proposed_characters, dict) else {}
    travel = outcomes.get("travel_resolution") or {}
    expected_location = (travel.get("destination") if travel.get("status") == "arrived"
                         else travel.get("stopped_at") if travel.get("status") == "interrupted"
                         else protagonist_after.get("location") if isinstance(protagonist_after, dict)
                         else None)
    return {
        "fixed_rules": world_config.get("fixed_rules", []),
        "trait_definitions": world_config.get("trait_definitions", {}),
        "titles": world_config.get("titles", []),
        "current_checkpoint_description": checkpoint.get("description", ""),
        "active_cards": [
            {"id": c["id"], "type": c["type"], "name": c["name"], "content": c["content"]}
            for c in active_cards
        ],
        "character_state_before_chapter": character_state_before,
        "chapter_text": chapter_text,
        "proposed_state_changes": state_changes,
        "engine_committed_outcomes": outcomes,
        "temporal_spatial_alignment": {
            "clock_at_turn_start": start_clock,
            "clock_after_proposed_turn": end_clock,
            "calendar": world_config.get("calendar"),
            "protagonist_location_before": protagonist_before.get("location") if isinstance(protagonist_before, dict) else None,
            "protagonist_location_after_proposed_turn": expected_location or (
                protagonist_before.get("location") if isinstance(protagonist_before, dict) else None
            ),
        },
    }


_CHECKER_SEVERITIES = ("none", "minor", "major")


def _unavailable(explanation: str) -> dict:
    return {
        "status": "unavailable",
        "consistent": None,
        "severity": "none",
        "issues": [],
        "explanation": explanation
    }


def parse_checker_response(raw_text: str) -> dict:
    """Parse and validate the checker output.

    A checker answer is only trusted when it fully matches the expected schema;
    a missing field, a wrong type/enum or a self-contradictory answer counts as
    "not checked" (unavailable), never as "passed".
    """
    try:
        parsed = parse_llm_json(raw_text)
    except (json.JSONDecodeError, ValueError) as error:
        return _unavailable(f"[CHECKER TRẢ VỀ KHÔNG ĐỌC ĐƯỢC — coi như chưa kiểm tra] {error}")
    if not isinstance(parsed, dict):
        return _unavailable("[CHECKER TRẢ VỀ KHÔNG ĐÚNG ĐỊNH DẠNG — coi như chưa kiểm tra]")

    consistent = parsed.get("consistent")
    severity = parsed.get("severity")
    issues = parsed.get("issues")
    state_sync = parsed.get("state_sync", True)
    action_scope = parsed.get("action_scope", True)

    problems = []
    if not isinstance(consistent, bool):
        problems.append("'consistent' phải là boolean")
    if severity not in _CHECKER_SEVERITIES:
        problems.append(f"'severity' phải thuộc {_CHECKER_SEVERITIES}")
    if not isinstance(issues, list) or any(not isinstance(item, (str, dict)) for item in issues):
        problems.append("'issues' phải là danh sách chuỗi/đối tượng")
    if not isinstance(state_sync, bool):
        problems.append("'state_sync' phải là boolean nếu được trả về")
    if not isinstance(action_scope, bool):
        problems.append("'action_scope' phải là boolean nếu được trả về")
    if not problems:
        if severity == "major" and consistent is True:
            problems.append("'severity'=major nhưng 'consistent'=true")
        if severity in ("none", "minor") and consistent is False:
            problems.append(f"'severity'={severity} nhưng 'consistent'=false")

    if problems:
        return _unavailable(
            "[CHECKER TRẢ VỀ SAI SCHEMA — coi như chưa kiểm tra] " + "; ".join(problems)
        )

    failed = severity == "major" or consistent is False or state_sync is False or action_scope is False
    return {
        "status": "failed" if failed else "passed",
        "consistent": consistent and state_sync and action_scope,
        "severity": "major" if state_sync is False or action_scope is False else severity,
        "issues": issues,
        "explanation": parsed.get("explanation", ""),
        "state_sync": state_sync,
        "action_scope": action_scope,
    }


def run_consistency_checker(chapter_text: str, state_changes: dict, world_config: dict,
                             checkpoint: dict, active_cards: list,
                             character_state_before: dict, world_name: str = None,
                             engine_outcomes: dict = None) -> dict:
    payload = build_consistency_checker_payload(
        chapter_text, state_changes, world_config, checkpoint,
        active_cards, character_state_before, engine_outcomes
    )
    try:
        raw = call_llm(
            CONSISTENCY_CHECKER_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            mock_response=mock_consistency_checker_response(),
            world_name=world_name,
            role="checker"
        )
    except LLMCallError as e:
        return {
            "status": "unavailable",
            "consistent": None,
            "severity": "none",
            "issues": [],
            "explanation": f"[CHECKER KHÔNG CHẠY ĐƯỢC — chưa kiểm tra] {e}"
        }
    return parse_checker_response(raw)


def build_consistency_correction_note(issues: list) -> str:
    lines = "\n".join(f"- {i}" for i in issues) if issues else "- (no detailed description)"
    return (
        "IMPORTANT NOTE - CANON CONTRADICTION: The Consistency checker (running separately) "
        "detected that the PREVIOUS writing for this user_input has severe contradictions with "
        "canon:\n" + lines +
        "\nPlease completely REWRITE the chapter_text and state_changes to strictly match the given canon "
        ", try to keep the original spirit of the user_input, only fixing the exact contradicted parts."
    )
