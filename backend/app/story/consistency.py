"""Consistency responsibilities for Story Engine."""
import logging
from app.llm_client import LLMCallError
from app.llm_client import call_llm
from app.llm_client import mock_consistency_checker_response
from app.llm_client import parse_llm_json
from app.prompts import CONSISTENCY_CHECKER_SYSTEM_PROMPT
from app.prompts import EXTRACTOR_SYSTEM_PROMPT
import json

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
                                        character_state_before: dict) -> dict:
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
        "proposed_state_changes": state_changes
    }


def parse_checker_response(raw_text: str) -> dict:
    default = {"consistent": True, "severity": "none", "issues": [], "explanation": ""}
    try:
        parsed = parse_llm_json(raw_text)
    except (json.JSONDecodeError, ValueError):
        return default
    if not isinstance(parsed, dict):
        return default
    return {
        "consistent": parsed.get("consistent", True),
        "severity": parsed.get("severity", "none"),
        "issues": parsed.get("issues", []) or [],
        "explanation": parsed.get("explanation", "")
    }


def run_consistency_checker(chapter_text: str, state_changes: dict, world_config: dict,
                             checkpoint: dict, active_cards: list,
                             character_state_before: dict, world_name: str = None) -> dict:
    payload = build_consistency_checker_payload(
        chapter_text, state_changes, world_config, checkpoint,
        active_cards, character_state_before
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
            "consistent": True,
            "severity": "none",
            "issues": [],
            "explanation": f"[CHECKER KHÔNG CHẠY ĐƯỢC — fail-open] {e}"
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
