import json
import logging
import os
import re
import uuid
from typing import List, Optional

from fastapi import HTTPException
from pydantic import ValidationError

from app.llm_client import (
    call_llm, LLMCallError, RateLimitError, parse_llm_json,
    mock_planner_response, mock_narrator_response, mock_prelude_response,
    mock_consistency_checker_response, mock_summarizer_response,
    _VALID_ROLES,
)
from app.rag import estimate_tokens, select_relevant_lore_cards, build_rag_context_text
from app.state_manager import (
    DEFAULT_STORY_CLOCK, apply_state_changes, apply_story_clock_changes,
    apply_foreshadowing_changes, ensure_foreshadowing_consistency,
    eval_condition,
)
from app.checkpoint_engine import (
    TEMPLATES, make_card, make_checkpoint, make_character,
    find_checkpoint, get_active_cards, checkpoint_conditions_met,
    sanitize_required_conditions, advance_checkpoint_if_ready,
    check_boundary_violations, build_boundary_correction_note,
    raise_boundary_hard_reject, generate_location_map,
    check_map_based_restrictions, build_map_restriction_note,
    _get_location_unlock_requirements, tick_endgame,
)
from app.language_detection import detect_story_language
from app.models import StateChangesModel
from app.persistence import commit_world_files, locked_world
from app.psychology import (
    generate_perceptions_for_all_characters,
    update_psychologies_for_all_characters,
    apply_psychology_changes,
    PsychologyState,
)

logger = logging.getLogger(__name__)

try:
    from prompts import (
        WRITER_SYSTEM_PROMPT, EXTRACTOR_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT,
        WORLD_BUILDER_SKELETON_PROMPT,
        WORLD_BUILDER_CARDS_PROMPT, WORLD_BUILDER_CHARACTERS_PROMPT,
        CONSISTENCY_CHECKER_SYSTEM_PROMPT, SUMMARIZER_SYSTEM_PROMPT,
        WORLD_BUILDER_INTERVIEW_PROMPT, CREATOR_ASSISTANT_PROMPT,
        LINTER_SYSTEM_PROMPT, REWRITE_SYSTEM_PROMPT, EDITOR_SYSTEM_PROMPT,
        ARC_EXTENDER_PROMPT,
        PRELUDE_WRITER_PROMPT, PRELUDE_VALIDATOR_PROMPT,
        LOCATION_MAP_GENERATOR_PROMPT
    )
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.prompts import (
        WRITER_SYSTEM_PROMPT, EXTRACTOR_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT,
        WORLD_BUILDER_SKELETON_PROMPT,
        WORLD_BUILDER_CARDS_PROMPT, WORLD_BUILDER_CHARACTERS_PROMPT,
        CONSISTENCY_CHECKER_SYSTEM_PROMPT, SUMMARIZER_SYSTEM_PROMPT,
        WORLD_BUILDER_INTERVIEW_PROMPT, CREATOR_ASSISTANT_PROMPT,
        LINTER_SYSTEM_PROMPT, REWRITE_SYSTEM_PROMPT, EDITOR_SYSTEM_PROMPT,
        ARC_EXTENDER_PROMPT,
        PRELUDE_WRITER_PROMPT, PRELUDE_VALIDATOR_PROMPT,
        LOCATION_MAP_GENERATOR_PROMPT
    )
    from backend.skill_limiter import check_skill_limiter


DEFAULT_LORE_RAG_MAX_TOKENS = 2000

CHAPTER_SOFT_CLOSE_TURNS = 5
CHAPTER_SOFT_CLOSE_WORDS = 900
CHAPTER_HARD_CLOSE_TURNS = 8
RECENT_TURNS_CONTEXT_LIMIT = 2
WORKING_MEMORY_TURNS = RECENT_TURNS_CONTEXT_LIMIT
ROLLING_SUMMARIZATION_TRIGGER_TURNS = 5
SUMMARY_MAX_TOKENS = 500
CHAPTER_SUMMARY_BUDGET_RATIO = 0.03
CHAPTER_SUMMARY_BUDGET_FLOOR = 100
CHAPTER_SUMMARY_BUDGET_CEIL = 500
MEMORABLE_BEATS_MAX = 100


def get_pacing_context_config(pacing_level: str = "Balanced") -> dict:
    key = (pacing_level or "Balanced").strip().lower()
    configs = {
        "slowburn": {"recent_turns": 4, "summary_budget_ratio": 0.05},
        "balanced": {"recent_turns": 3, "summary_budget_ratio": 0.03},
        "fast": {"recent_turns": 2, "summary_budget_ratio": 0.02},
    }
    return configs.get(key, configs["balanced"])


def get_output_length_config(output_length: str = "Standard") -> dict:
    key = (output_length or "Standard").strip().lower()
    configs = {
        "concise": {
            "words_per_turn_ratio": 0.65,
            "soft_close_words_ratio": 0.7,
            "soft_close_turns_offset": -1,
            "hard_close_turns_offset": -2,
        },
        "standard": {
            "words_per_turn_ratio": 1.0,
            "soft_close_words_ratio": 1.0,
            "soft_close_turns_offset": 0,
            "hard_close_turns_offset": 0,
        },
        "detailed": {
            "words_per_turn_ratio": 1.5,
            "soft_close_words_ratio": 1.6,
            "soft_close_turns_offset": 2,
            "hard_close_turns_offset": 2,
        },
    }
    return configs.get(key, configs["standard"])


def get_words_per_turn_target(pacing_level: str = "Balanced", output_length: str = "Standard") -> int:
    pacing_key = (pacing_level or "Balanced").strip().lower()
    pacing_targets = {
        "slowburn": 300,
        "balanced": 200,
        "fast": 130,
    }
    base = pacing_targets.get(pacing_key, pacing_targets["balanced"])
    ol_config = get_output_length_config(output_length)
    return max(50, int(base * ol_config["words_per_turn_ratio"]))


def get_close_thresholds(output_length: str = "Standard", pacing_level: str = "Balanced") -> dict:
    ol_config = get_output_length_config(output_length)
    pacing_config = get_pacing_context_config(pacing_level)
    soft_close_turns = max(2, CHAPTER_SOFT_CLOSE_TURNS + ol_config["soft_close_turns_offset"])
    hard_close_turns = max(3, CHAPTER_HARD_CLOSE_TURNS + ol_config["hard_close_turns_offset"])
    return {
        "soft_close_turns": soft_close_turns,
        "soft_close_words": max(200, int(CHAPTER_SOFT_CLOSE_WORDS * ol_config["soft_close_words_ratio"])),
        "hard_close_turns": hard_close_turns,
    }


def build_opening_instruction(checkpoint: dict) -> str:
    return (
        f"[This is the opening chapter (chapter 1) of the story, no prior events have occurred. "
        f"Please write a natural opening scene based on the following description of the current checkpoint: "
        f"\"{checkpoint.get('description', '')}\". Introduce the setting and relevant character(s) "
        f"within the allowed scope naturally, setting the stage for the story to continue. "
        f"Không nhắc tới việc đây là hướng dẫn hệ thống hay từ \"chương mở đầu\" trong văn bản chương.]"
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


def merge_canon_and_delta(canon_store: dict, branch_delta: dict) -> dict:
    overrides = branch_delta.get("overrides", {}) if isinstance(branch_delta, dict) else {}
    effective = {"facts": list(canon_store.get("facts", []))}
    for i, fact in enumerate(effective["facts"]):
        if not isinstance(fact, dict):
            continue
        fact_id = fact.get("fact_id", "")
        if fact_id in overrides:
            effective["facts"][i] = dict(fact)
            effective["facts"][i]["statement"] = overrides[fact_id]
    return effective


def _filter_memorable_beats_by_token_budget(beats: list, max_tokens: int,
                                              running_summary: str = "",
                                              max_beats_per_chapter: int = 2) -> list:
    summary_tokens = estimate_tokens(running_summary)
    remaining = max_tokens - summary_tokens
    if remaining <= 0:
        return []
    grouped = {}
    for beat in beats:
        m = re.match(r"\[Ch\.(\d+)\]", beat)
        key = int(m.group(1)) if m else 0
        grouped.setdefault(key, []).append(beat)
    result = []
    for ch_idx in sorted(grouped.keys(), reverse=True):
        chapter_beats = grouped[ch_idx]
        for beat in chapter_beats:
            if max_beats_per_chapter and sum(1 for r in result if r.startswith(f"[Ch.{ch_idx}]")) >= max_beats_per_chapter:
                break
            btok = estimate_tokens(beat)
            if btok > remaining:
                continue
            result.append(beat)
            remaining -= btok
        if remaining <= 0:
            break
    return result


def build_multi_tier_context(
    chapters_data: dict,
    world_config: dict,
    checkpoint: dict,
    canon_facts: list,
) -> dict:
    allowed_locations = set(
        loc.lower() for loc in checkpoint.get("boundary", {}).get("locations", [])
    )
    allowed_chars = set(
        c.lower() for c in checkpoint.get("boundary", {}).get("allowed_characters", [])
    )
    scene_anchors = allowed_locations | allowed_chars

    def _tag_in_allowed_zones(tag: str) -> bool:
        for anchor in scene_anchors:
            if tag == anchor or tag.startswith(anchor + " - "):
                return True
        return False

    filtered_facts = []
    for f in canon_facts:
        if isinstance(f, str):
            filtered_facts.append(f)
        elif isinstance(f, dict):
            statement = f.get("statement", "")
            tags = [t.lower() for t in f.get("tags", [])]
            if not scene_anchors or any(_tag_in_allowed_zones(t) for t in tags):
                filtered_facts.append(statement)

    threads = []
    for t in world_config.get("open_threads", []):
        if isinstance(t, dict):
            threads.append({
                "note": t.get("note", ""),
                "checkpoint_id": t.get("checkpoint_id", ""),
                "resolution_deadline": t.get("resolution_deadline", "ongoing"),
            })

    foreshadowing_tracker = world_config.get("foreshadowing_tracker")
    if foreshadowing_tracker is None:
        foreshadowing_tracker = world_config.get("foreshadowings", [])

    pacing_config = get_pacing_context_config(world_config.get("pacing_level", "Balanced"))

    return {
        "multi_tier_context": {
            "tier_1_working_memory": {
                "description": "Full text of the most recent turns (immediate scene context). Prioritize this for what is happening right now.",
                "recent_turns": get_recent_turns_for_context(chapters_data, limit=pacing_config["recent_turns"]),
                "max_turns": pacing_config["recent_turns"],
            },
            "tier_2_rolling_summary": {
                "description": "Compressed history of all events older than working memory. Use for long-term continuity only.",
                "summary": chapters_data.get("running_summary", ""),
            },
            "tier_2_memorable_beats": {
                "description": "Short highlights from recent chapters that survived compression. Each beat is a striking moment, line of dialogue, or vivid image.",
                "beats": _filter_memorable_beats_by_token_budget(
                    chapters_data.get("memorable_beats", []),
                    SUMMARY_MAX_TOKENS,
                    running_summary=chapters_data.get("running_summary", ""),
                    max_beats_per_chapter=2,
                ),
            },
            "tier_3_canon_filter": {
                "description": "Entity-tagged world facts filtered by active scene/location. These are canonical constraints.",
                "allowed_locations": list(allowed_locations),
                "allowed_characters": list(allowed_chars),
                "relevant_canon_facts": filtered_facts,
            },
            "tier_4_thread_ledger": {
                "description": "Active narrative threads and foreshadowing hints awaiting resolution. Advance or resolve threads within their deadlines.",
                "open_threads": threads,
                "active_thread_count": len(threads),
                "foreshadowing_tracker": foreshadowing_tracker,
            },
        }
    }


def _is_rolled(c: dict) -> bool:
    val = c.get("rolled_into_summary")
    if val is not None:
        return val
    return c.get("chapter_closed", True)


def get_unshelved_turn_count(chapters_data: dict) -> int:
    return sum(1 for c in chapters_data.get("chapters", []) if not _is_rolled(c))


def check_rolling_summary_trigger(
    chapters_data: dict,
    world_name: str = None,
    world_config: dict = None,
) -> bool:
    chapters = chapters_data.get("chapters", [])
    unshelved = [c for c in chapters if not _is_rolled(c)]

    pacing_config = get_pacing_context_config(world_config.get("pacing_level") if world_config else None)
    recent_turns_limit = pacing_config["recent_turns"]

    if len(unshelved) <= recent_turns_limit:
        return False

    turns_to_roll = unshelved[:-recent_turns_limit]

    by_chapter = {}
    for c in turns_to_roll:
        idx = c["chapter_index"]
        if idx not in by_chapter:
            by_chapter[idx] = []
        by_chapter[idx].append(c)

    for ch_idx in sorted(by_chapter.keys()):
        same_chapter = sorted(by_chapter[ch_idx], key=lambda x: x["turn_index"])
        full_text = "\n\n".join(t.get("chapter_text", "") for t in same_chapter)
        title = same_chapter[0].get("chapter_title") or f"Chapter {ch_idx}"

        result = update_running_summary(chapters_data, ch_idx, title, world_name)
        chapters_data["running_summary"] = result["running_summary"]

        for t in same_chapter:
            t["rolled_into_summary"] = True

    return True


def build_summarizer_payload(previous_summary: str, chapter_title: str, chapter_text: str,
                              word_budget: int = 100) -> dict:
    return {
        "previous_summary": previous_summary,
        "chapter_title": chapter_title,
        "chapter_text": chapter_text,
        "word_budget": word_budget
    }


def parse_summarizer_response(raw_text: str, fallback: str) -> dict:
    default_res = {"running_summary": fallback, "tension_level": 5, "mood": "", "memorable_beats": []}
    try:
        parsed = parse_llm_json(raw_text)
    except (json.JSONDecodeError, ValueError):
        return default_res
    if not isinstance(parsed, dict):
        return default_res
    new_summary = parsed.get("running_summary")
    if not isinstance(new_summary, str) or not new_summary.strip():
        new_summary = fallback
    else:
        new_summary = new_summary.strip()
    beats = parsed.get("memorable_beats", [])
    if not isinstance(beats, list) or not beats:
        beats = []
    else:
        beats = [str(b).strip() for b in beats if isinstance(b, str) and str(b).strip()]
    return {
        "running_summary": new_summary,
        "tension_level": parsed.get("tension_level", 5),
        "mood": parsed.get("mood", ""),
        "memorable_beats": beats
    }


def total_story_word_count(chapters_data: dict) -> int:
    return sum(len(c.get("chapter_text", "").split()) for c in chapters_data.get("chapters", []))


def compute_word_budget(total_words: int, pacing_level: str = "Balanced") -> int:
    config = get_pacing_context_config(pacing_level)
    budget = int(total_words * config["summary_budget_ratio"])
    return max(CHAPTER_SUMMARY_BUDGET_FLOOR, min(CHAPTER_SUMMARY_BUDGET_CEIL, budget))


def update_running_summary(chapters_data: dict, closed_chapter_index: int, chapter_title: str,
                            world_name: str = None, world_config: dict = None) -> dict:
    previous_summary = chapters_data.get("running_summary", "")
    same_chapter_turns = sorted(
        (c for c in chapters_data.get("chapters", []) if c["chapter_index"] == closed_chapter_index),
        key=lambda c: c["turn_index"]
    )
    full_chapter_text = "\n\n".join(c.get("chapter_text", "") for c in same_chapter_turns)
    total_words = total_story_word_count(chapters_data)
    word_budget = compute_word_budget(total_words, world_config.get("pacing_level") if world_config else None)
    payload = build_summarizer_payload(previous_summary, chapter_title, full_chapter_text, word_budget)
    try:
        raw = call_llm(
            SUMMARIZER_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            mock_response=mock_summarizer_response(chapter_title),
            world_name=world_name,
            role="summarizer"
        )
    except LLMCallError:
        return {"running_summary": previous_summary, "tension_level": 5, "mood": "", "memorable_beats": []}
    result = parse_summarizer_response(raw, fallback=previous_summary)
    new_beats = result.get("memorable_beats", [])
    if new_beats:
        existing = chapters_data.get("memorable_beats", [])
        checkpoint_id = same_chapter_turns[0].get("checkpoint_id", "") if same_chapter_turns else ""
        cp_tag = f"[{checkpoint_id}]" if checkpoint_id else ""
        tagged = [f"[Ch.{closed_chapter_index}]{cp_tag} {b}" for b in new_beats]
        chapters_data["memorable_beats"] = tagged + existing
    return result


def check_anchor_keywords(chapter_text: str, anchor_keywords: List[str]) -> List[str]:
    text_lower = chapter_text.lower()
    missing = []
    for kw in anchor_keywords:
        if not kw or not kw.strip():
            continue
        if kw.lower() not in text_lower:
            missing.append(kw)
    return missing


def call_planner_stage(payload: dict, user_input_for_mock: str, world_name: str = None) -> dict:
    try:
        planner_raw = call_llm(
            PLANNER_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            user_input_for_mock=user_input_for_mock,
            world_name=world_name,
            role="planner"
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"OpenRouter is rate-limiting planner agent: {e}",
                "retry_after": e.retry_after
            }
        )
    except LLMCallError as e:
        raise HTTPException(status_code=503, detail=f"Failed to call planner agent: {e}")

    try:
        planner_parsed = parse_llm_json(planner_raw)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Planner returned invalid JSON, could not parse."
        )

    scene_outline = planner_parsed.get("scene_outline", "")
    facts_this_turn = planner_parsed.get("facts_this_turn", [])
    if not isinstance(facts_this_turn, list):
        facts_this_turn = []
    state_changes = planner_parsed.get("state_changes", {"characters": {}, "notes": ""})

    try:
        StateChangesModel(**state_changes)
    except ValidationError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Planner returned malformed state_changes schema, cannot merge safely: {e}"
        )

    raw_suggested = planner_parsed.get("suggested_actions", [])
    suggested_actions = raw_suggested if isinstance(raw_suggested, list) else []
    suggested_actions = [s for s in suggested_actions if isinstance(s, str) and s.strip()][:4]

    anchor_keywords = planner_parsed.get("anchor_keywords", [])
    if not isinstance(anchor_keywords, list):
        anchor_keywords = []
    open_threads_update = planner_parsed.get("open_threads_update", "")
    if not isinstance(open_threads_update, str):
        open_threads_update = ""

    is_ooc = bool(planner_parsed.get("is_ooc", False))
    action_translation = planner_parsed.get("action_translation", "")
    if not isinstance(action_translation, str):
        action_translation = ""
    effective_user_input = action_translation if (is_ooc and action_translation.strip()) else user_input_for_mock

    return {
        "scene_outline": scene_outline,
        "facts_this_turn": facts_this_turn,
        "state_changes": state_changes,
        "suggested_actions": suggested_actions,
        "anchor_keywords": anchor_keywords,
        "open_threads_update": open_threads_update,
        "is_ooc": is_ooc,
        "action_translation": action_translation,
        "effective_user_input": effective_user_input,
    }


def call_writer_stage(payload: dict, scene_outline: str, facts_this_turn: list,
                      state_changes: dict, suggested_actions: list,
                      anchor_keywords: list, open_threads_update: str,
                      is_ooc: bool, action_translation: str,
                      effective_user_input: str,
                      world_name: str = None, editor_enabled: bool = False):
    writer_payload = dict(payload)
    writer_payload["scene_outline"] = scene_outline
    writer_payload["facts_this_turn"] = facts_this_turn

    try:
        writer_raw = call_llm(
            WRITER_SYSTEM_PROMPT,
            json.dumps(writer_payload, ensure_ascii=False),
            user_input_for_mock=effective_user_input,
            world_name=world_name,
            role="writer"
        )
    except RateLimitError as e:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"OpenRouter is rate-limiting writer agent: {e}",
                "retry_after": e.retry_after
            }
        )
    except LLMCallError as e:
        raise HTTPException(status_code=503, detail=f"Failed to call writer agent: {e}")

    try:
        writer_parsed = parse_llm_json(writer_raw)
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(
            status_code=502,
            detail="Writer returned invalid JSON, could not parse."
        )

    chapter_text = writer_parsed.get("chapter_text", "")
    chapter_end = bool(writer_parsed.get("chapter_end", False))
    chapter_title = writer_parsed.get("chapter_title") or None

    draft_entities = writer_parsed.get("draft_entities", [])
    if not isinstance(draft_entities, list):
        draft_entities = []

    writer_state_changes = writer_parsed.get("state_changes", None)
    if writer_state_changes is not None and isinstance(writer_state_changes, dict):
        state_changes = writer_state_changes

    keyword_missing = check_anchor_keywords(chapter_text, anchor_keywords)
    if keyword_missing:
        logger.warning(
            "Anchor keywords missing from chapter_text (world=%s): %s",
            world_name, keyword_missing
        )
        auto_retry = payload.get("world_config", {}).get("keyword_auto_retry", False)
        if auto_retry and anchor_keywords:
            for attempt in range(1, 3):
                retry_payload = dict(writer_payload)
                retry_payload["correction_note"] = (
                    f"The previous chapter_text was missing these required anchor keywords: "
                    f"{keyword_missing}. Please rewrite the chapter_text ensuring every one of these "
                    f"keywords appears naturally in the prose."
                )
                try:
                    retry_raw = call_llm(
                        WRITER_SYSTEM_PROMPT,
                        json.dumps(retry_payload, ensure_ascii=False),
                        user_input_for_mock=effective_user_input,
                        world_name=world_name,
                        role="writer"
                    )
                    retry_parsed = parse_llm_json(retry_raw)
                    retry_text = retry_parsed.get("chapter_text", "")
                    if retry_text:
                        chapter_text = retry_text
                        chapter_end = bool(retry_parsed.get("chapter_end", chapter_end))
                        chapter_title = retry_parsed.get("chapter_title") or chapter_title
                        keyword_missing = check_anchor_keywords(chapter_text, anchor_keywords)
                        if not keyword_missing:
                            logger.info("Keyword auto-retry succeeded on attempt %d/2", attempt)
                            break
                        logger.warning(
                            "Keyword auto-retry attempt %d/2 still missing: %s", attempt, keyword_missing
                        )
                except (LLMCallError, json.JSONDecodeError, ValueError):
                    logger.warning("Keyword auto-retry attempt %d/2 failed with exception", attempt)
                    break

    editor_polished = False
    if editor_enabled:
        style_card = payload.get("style_card", {})
        editor_payload = json.dumps(
            {"chapter_text": chapter_text, "style_card": style_card},
            ensure_ascii=False
        )
        try:
            editor_raw = call_llm(
                EDITOR_SYSTEM_PROMPT,
                editor_payload,
                mock_response=json.dumps({"polished_text": chapter_text}, ensure_ascii=False),
                world_name=world_name,
                role="editor"
            )
            editor_parsed = parse_llm_json(editor_raw)
            polished = editor_parsed.get("polished_text", "")
            if polished and isinstance(polished, str) and polished.strip():
                editor_polished = (polished.strip() != chapter_text.strip())
                chapter_text = polished.strip()
        except (LLMCallError, json.JSONDecodeError, ValueError, KeyError):
            pass

    steps = writer_parsed.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    variants = writer_parsed.get("variants", [])
    if not isinstance(variants, list):
        variants = []
    perception_data = writer_parsed.get("perception_data", {})
    if not isinstance(perception_data, dict):
        perception_data = {}

    return chapter_text, state_changes, chapter_end, chapter_title, suggested_actions, draft_entities, editor_polished, anchor_keywords, open_threads_update, is_ooc, action_translation, keyword_missing, steps, variants, perception_data


def call_narrator_and_parse(payload: dict, user_input_for_mock: str, world_name: str = None,
                            editor_enabled: bool = False):
    planner_out = call_planner_stage(payload, user_input_for_mock, world_name)
    return call_writer_stage(
        payload,
        planner_out["scene_outline"], planner_out["facts_this_turn"],
        planner_out["state_changes"], planner_out["suggested_actions"],
        planner_out["anchor_keywords"], planner_out["open_threads_update"],
        planner_out["is_ooc"], planner_out["action_translation"],
        planner_out["effective_user_input"],
        world_name=world_name, editor_enabled=editor_enabled
    )


def deduplicate_entity(card_registry: dict, name: str, entity_type: str) -> Optional[dict]:
    name_lower = name.strip().lower()
    for c in card_registry.get("cards", []):
        c_name = (c.get("name") or "").strip().lower()
        if c_name == name_lower:
            return c
    for c in card_registry.get("cards", []):
        aliases = c.get("aliases") or []
        if any(a.strip().lower() == name_lower for a in aliases):
            return c
    return None


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


def get_open_chapter_state(chapters_data: dict) -> tuple:
    chapters = chapters_data.get("chapters", [])
    if not chapters:
        return 1, 1
    non_prelude = [c for c in chapters if c.get("chapter_index") != 0]
    if not non_prelude:
        return 1, 1
    last = non_prelude[-1]
    if last.get("chapter_closed", True):
        return last["chapter_index"] + 1, 1
    return last["chapter_index"], last["turn_index"] + 1


def decide_chapter_closed(chapter_index: int, turn_index: int, chapters_data: dict,
                           new_chapter_text: str, narrator_flagged_end: bool,
                           output_length: str = "Standard",
                           pacing_level: str = "Balanced") -> bool:
    if narrator_flagged_end:
        return True
    thresholds = get_close_thresholds(output_length, pacing_level)
    same_chapter_turns = [
        c for c in chapters_data.get("chapters", []) if c["chapter_index"] == chapter_index
    ]
    total_turns = len(same_chapter_turns) + 1
    if total_turns >= thresholds["hard_close_turns"]:
        return True
    total_words = sum(len(c.get("chapter_text", "").split()) for c in same_chapter_turns)
    total_words += len(new_chapter_text.split())
    if total_turns >= thresholds["soft_close_turns"] and total_words >= thresholds["soft_close_words"]:
        return True
    return False


def get_recent_turns_for_context(chapters_data: dict, limit: int = RECENT_TURNS_CONTEXT_LIMIT) -> list:
    return chapters_data.get("chapters", [])[-limit:]


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


def _validate_imported_package(pkg: dict, templates: dict) -> tuple:
    if not isinstance(pkg, dict):
        raise HTTPException(status_code=400, detail="Invalid package format: expected JSON object")

    world_config = pkg.get("world_config")
    card_registry = pkg.get("card_registry")
    canon_timeline = pkg.get("canon_timeline")
    character_state = pkg.get("character_state")

    if not isinstance(world_config, dict):
        raise HTTPException(status_code=400, detail="Import package error: 'world_config' must be a valid object")
    if not isinstance(card_registry, dict) or "cards" not in card_registry or not isinstance(card_registry["cards"], list):
        raise HTTPException(status_code=400, detail="Import package error: 'card_registry' must contain a 'cards' array")
    if not isinstance(canon_timeline, dict) or "checkpoints" not in canon_timeline or not isinstance(canon_timeline["checkpoints"], list):
        raise HTTPException(status_code=400, detail="Import package error: 'canon_timeline' must contain a 'checkpoints' array")
    if not isinstance(character_state, dict) or "characters" not in character_state:
        raise HTTPException(status_code=400, detail="Import package error: 'character_state' must contain a 'characters' object")

    full_world_config = {**templates["world_config.json"], **world_config}

    validated_cards = []
    card_ids = set()
    for i, c in enumerate(card_registry["cards"]):
        if not isinstance(c, dict):
            raise HTTPException(status_code=400, detail=f"Import package error: card item at index {i} is not an object")
        c_id = c.get("id") or f"card_{i+1}"
        if c_id in card_ids:
            raise HTTPException(status_code=400, detail=f"Import package error: duplicate card id '{c_id}'")
        card_ids.add(c_id)
        card_obj = make_card(
            card_id=c_id,
            card_type=c.get("type", "lore"),
            name=c.get("name", f"Card {c_id}"),
            content=c.get("content", ""),
            unlock_checkpoint_id=c.get("unlock_checkpoint_id"),
            status=c.get("status", "locked"),
            entity_id=c.get("entity_id"),
            aliases=c.get("aliases") if isinstance(c.get("aliases"), list) else None,
            scope=c.get("scope"),
            entity_status=c.get("entity_status", "active")
        )
        if "keywords" in c and isinstance(c["keywords"], list):
            card_obj["keywords"] = c["keywords"]
        if "is_pinned" in c:
            card_obj["is_pinned"] = bool(c["is_pinned"])
        validated_cards.append(card_obj)

    validated_cps = []
    cp_ids = set()
    for i, cp in enumerate(canon_timeline["checkpoints"]):
        if not isinstance(cp, dict):
            raise HTTPException(status_code=400, detail=f"Import package error: checkpoint item at index {i} is not an object")
        cp_id = cp.get("checkpoint_id") or f"cp_{i}"
        if cp_id in cp_ids:
            raise HTTPException(status_code=400, detail=f"Import package error: duplicate checkpoint id '{cp_id}'")
        cp_ids.add(cp_id)
        cp_obj = make_checkpoint(
            checkpoint_id=cp_id,
            description=cp.get("description", ""),
            required_conditions=cp.get("required_conditions"),
            cards_unlocked=cp.get("cards_unlocked"),
            locations=(cp.get("boundary") or {}).get("locations") if isinstance(cp.get("boundary"), dict) else cp.get("locations"),
            allowed_characters=(cp.get("boundary") or {}).get("allowed_characters") if isinstance(cp.get("boundary"), dict) else cp.get("allowed_characters"),
            time_window=(cp.get("boundary") or {}).get("time_window", "") if isinstance(cp.get("boundary"), dict) else str(cp.get("time_window", "")),
            realm_updates=cp.get("realm_updates")
        )
        if "status_effects" in cp and isinstance(cp["status_effects"], list):
            cp_obj["status_effects"] = cp["status_effects"]
        if "alternate_outcomes" in cp and isinstance(cp["alternate_outcomes"], list):
            cp_obj["alternate_outcomes"] = cp["alternate_outcomes"]
        if "default_next_checkpoint_id" in cp:
            cp_obj["default_next_checkpoint_id"] = cp["default_next_checkpoint_id"]
        if "sub_beats" in cp and isinstance(cp["sub_beats"], list):
            cp_obj["sub_beats"] = cp["sub_beats"]
        validated_cps.append(cp_obj)

    raw_chars = character_state["characters"]
    if isinstance(raw_chars, list):
        converted = {}
        for i, item in enumerate(raw_chars):
            if isinstance(item, dict):
                cid = item.get("id") or item.get("char_id") or f"char_{i+1}"
                converted[cid] = item
        raw_chars = converted

    if not isinstance(raw_chars, dict):
        raise HTTPException(status_code=400, detail="Import package error: 'character_state.characters' must be an object or list of objects")

    validated_chars = normalize_character_dict(raw_chars)

    return full_world_config, {"cards": validated_cards}, {"checkpoints": validated_cps}, {"characters": validated_chars}


def normalize_character_dict(raw_chars: dict) -> dict:
    validated_chars = {}
    for cid, cdata in raw_chars.items():
        if not isinstance(cdata, dict):
            continue
        c_name = cdata.get("name") or cid
        c_loc = cdata.get("location") or ""
        c_aff = cdata.get("affinity") if isinstance(cdata.get("affinity"), dict) else {}
        pstat = cdata.get("power_stat") if isinstance(cdata.get("power_stat"), dict) else {}
        c_realm = pstat.get("realm") or cdata.get("realm") or ""
        c_exp = pstat.get("exp") or cdata.get("exp") or 0
        c_sub = pstat.get("sub_stats") if isinstance(pstat.get("sub_stats"), dict) else {}
        c_skills = pstat.get("known_skills") if isinstance(pstat.get("known_skills"), list) else (cdata.get("known_skills") if isinstance(cdata.get("known_skills"), list) else [])
        c_kflags = cdata.get("knowledge_flags") if isinstance(cdata.get("knowledge_flags"), list) else []
        c_inv = cdata.get("inventory") if isinstance(cdata.get("inventory"), list) else []
        c_karma = cdata.get("karma") or 0
        c_alive = cdata.get("alive") if cdata.get("alive") is not None else True
        c_rel = cdata.get("relationships") if isinstance(cdata.get("relationships"), dict) else {}
        c_age = str(cdata.get("age") or "")
        c_appearance = cdata.get("appearance", "")
        c_personality = cdata.get("personality", "")
        c_backstory = cdata.get("backstory", "")
        c_abilities_and_limits = cdata.get("abilities_and_limits", "")
        c_speech_style = cdata.get("speech_style", "")
        c_secrets = cdata.get("secrets", "")

        char_obj = make_character(
            name=c_name,
            location=c_loc,
            affinity=c_aff,
            realm=c_realm,
            exp=c_exp,
            sub_stats=c_sub,
            knowledge_flags=c_kflags,
            inventory=c_inv,
            karma=c_karma,
            alive=c_alive,
            relationships=c_rel,
            age=c_age,
            known_skills=c_skills,
            appearance=c_appearance,
            personality=c_personality,
            backstory=c_backstory,
            abilities_and_limits=c_abilities_and_limits,
            speech_style=c_speech_style,
            secrets=c_secrets
        )
        if "traits" in cdata and isinstance(cdata["traits"], dict):
            char_obj["traits"] = cdata["traits"]
        if "status_effects" in cdata and isinstance(cdata["status_effects"], list):
            char_obj["status_effects"] = cdata["status_effects"]
        validated_chars[cid] = char_obj
    return validated_chars


@locked_world
def _generate_chapter(world_name: str, narrator_input: str, display_input: str = None) -> dict:
    from app.storage import (
        world_path_of, read_world_file, write_world_file,
        has_real_api_key, get_world_style_card,
        read_world_canon, read_branch_delta,
        _get_effective_editor_enabled, _get_effective_extractor_cross_check,
    )
    if display_input is None:
        display_input = narrator_input

    world_path = world_path_of(world_name)
    if not os.path.isdir(world_path):
        raise HTTPException(status_code=404, detail="World not found")

    world_config = read_world_file(world_path, "world_config.json")
    card_registry = read_world_file(world_path, "card_registry.json")
    canon_timeline = read_world_file(world_path, "canon_timeline.json")
    character_state = read_world_file(world_path, "character_state.json")
    chapters_data = read_world_file(world_path, "chapters.json")
    world_canon_store = read_world_canon(world_path)
    branch_delta = read_branch_delta(world_path)

    if world_config.get("lifecycle_status") == "completed":
        raise HTTPException(status_code=409, detail="This story is completed. Restore a save or create a branch to continue.")

    location_map = None
    try:
        location_map = read_world_file(world_path, "location_map.json")
    except (FileNotFoundError, json.JSONDecodeError):
        pass

    current_checkpoint_id = world_config.get("current_checkpoint_id", "")
    checkpoint = find_checkpoint(canon_timeline["checkpoints"], current_checkpoint_id)
    if checkpoint is None:
        raise HTTPException(
            status_code=400,
            detail=f"current_checkpoint_id '{current_checkpoint_id}' không khớp checkpoint nào "
                   f"in canon_timeline (world có thể là data cũ, chưa có field này -- "
                   f"chạy lại seed-demo hoặc set thủ công)."
        )

    boundary = checkpoint.get("boundary") or {}
    boundary_locations = boundary.get("locations") or []
    boundary_chars = boundary.get("allowed_characters") or []
    if not boundary_locations and not boundary_chars:
        raise HTTPException(
            status_code=400,
            detail="Checkpoint hiện tại không có phạm vi tương tác hợp lệ (locations=[] va "
                   "allowed_characters=[]). Có thể cần confirm prelude trước, hoặc world đang "
                   "kẹt ở checkpoint chuyển tiếp."
        )

    pacing_config = get_pacing_context_config(world_config.get("pacing_level", "Balanced"))
    recent_turns_for_context = get_recent_turns_for_context(chapters_data, limit=pacing_config["recent_turns"])
    running_summary = chapters_data.get("running_summary", "")
    rag_context_text = build_rag_context_text(recent_turns_for_context, narrator_input, running_summary)
    configured_max_lore = world_config.get("lore_rag_max_tokens")
    if configured_max_lore is None:
        old_cards = world_config.get("lore_rag_max_cards")
        if old_cards is not None and isinstance(old_cards, int) and old_cards >= 0:
            configured_max_lore = old_cards * 300
    if configured_max_lore is None or (isinstance(configured_max_lore, int) and configured_max_lore < 0):
        max_lore_tokens = DEFAULT_LORE_RAG_MAX_TOKENS
    elif configured_max_lore == 0:
        max_lore_tokens = None
    else:
        max_lore_tokens = configured_max_lore

    unlocked_lore_count = sum(
        1 for c in card_registry["cards"]
        if c["type"] == "lore" and c["status"] == "unlocked"
    )
    active_cards = get_active_cards(
        card_registry["cards"], checkpoint,
        context_text=rag_context_text, max_lore_tokens=max_lore_tokens
    )
    story_clock = world_config.get("story_clock")
    if not isinstance(story_clock, dict):
        story_clock = dict(DEFAULT_STORY_CLOCK)
    try:
        turn_start_tick = max(0, int(story_clock.get("tick", 0)))
    except (TypeError, ValueError):
        turn_start_tick = 0

    foreshadowing_tracker = world_config.get("foreshadowing_tracker")
    if foreshadowing_tracker is None:
        foreshadowing_tracker = world_config.get("foreshadowings", [])

    active_characters_state = {}
    allowed_chars_raw = checkpoint.get("boundary", {}).get("allowed_characters", [])
    allowed_chars_lower = {str(c).lower().strip() for c in allowed_chars_raw}
    for char_id, state in character_state.get("characters", {}).items():
        c_id_lower = str(char_id).lower().strip()
        c_name_lower = str(state.get("name", "")).lower().strip() if isinstance(state, dict) else ""
        if not allowed_chars_lower or c_id_lower in allowed_chars_lower or c_name_lower in allowed_chars_lower:
            st = dict(state) if isinstance(state, dict) else {}
            st.setdefault("relationships", {})
            st.setdefault("age", "")
            active_characters_state[char_id] = st

    selected_lore_ids = [c["id"] for c in active_cards if c["type"] == "lore"]
    selected_tokens = sum(len(c.get("content", "") + " " + c.get("name", "")) // 4 for c in active_cards if c["type"] == "lore")
    total_lore_tokens = sum(len(c.get("content", "") + " " + c.get("name", "")) // 4 for c in card_registry["cards"] if c["type"] == "lore" and c["status"] == "unlocked")
    lore_rag_filter = None
    if max_lore_tokens is not None and total_lore_tokens > max_lore_tokens:
        lore_rag_filter = {
            "applied": True,
            "unlocked_lore_count": unlocked_lore_count,
            "max_lore_tokens": max_lore_tokens,
            "selected_lore_ids": selected_lore_ids,
            "selected_tokens": selected_tokens,
            "total_tokens": total_lore_tokens
        }

    style_card = get_world_style_card(world_name)

    skill_cards = [
        c for c in card_registry.get("cards", [])
        if isinstance(c, dict) and (c.get("type") in ("skill", "skill_card") or c.get("id", "").startswith("skill_"))
    ] + card_registry.get("skills", [])
    protagonist_id = world_config.get("protagonist_id", "")
    skill_pre_violation = check_skill_limiter(
        chapter_text="",
        character_state=character_state.get("characters", {}),
        protagonist_id=protagonist_id,
        skill_cards=skill_cards,
        user_input=narrator_input
    )
    if skill_pre_violation and skill_pre_violation.get("boundary_violated"):
        raise HTTPException(
            status_code=400,
            detail={
                "boundary_violated": True,
                "reason": skill_pre_violation.get("reason", ""),
                "unlearned_skill": skill_pre_violation.get("unlearned_skill", ""),
                "skill_check": skill_pre_violation
            }
        )

    merged_canon = merge_canon_and_delta(world_canon_store, branch_delta)
    world_canon_facts = [f["statement"] for f in merged_canon.get("facts", []) if isinstance(f, dict) and f.get("statement")]

    multi_tier_context = build_multi_tier_context(
        chapters_data, world_config, checkpoint, merged_canon.get("facts", [])
    )

    base_payload = {
        "world_canon_facts": world_canon_facts,
        "world_config": {
            "genre": world_config.get("genre", ""),
            "story_thesis": world_config.get("story_thesis", ""),
            "power_system": world_config.get("power_system", ""),
            "tone": world_config.get("tone", ""),
            "fixed_rules": world_config.get("fixed_rules", []),
            "protagonist_id": world_config.get("protagonist_id", ""),
            "pacing_level": world_config.get("pacing_level", "Balanced"),
            "output_length": world_config.get("output_length", "Standard"),
            "pov_angle": world_config.get("pov_angle", "3rd_person_limited"),
            "prelude_enabled": world_config.get("prelude_enabled", False),
            "interaction_mode": world_config.get("interaction_mode", "narrative"),
            "keyword_auto_retry": world_config.get("keyword_auto_retry", False),
            "story_clock": story_clock
        },
        "words_per_turn_target": get_words_per_turn_target(
            world_config.get("pacing_level", "Balanced"),
            world_config.get("output_length", "Standard")
        ),
        "style_card": style_card,
        "story_clock": story_clock,
        "current_checkpoint": {
            "checkpoint_id": checkpoint["checkpoint_id"],
            "description": checkpoint["description"],
            "allowed_locations": checkpoint["boundary"]["locations"],
            "allowed_characters": checkpoint["boundary"]["allowed_characters"],
            "time_window": checkpoint["boundary"]["time_window"]
        },
        "active_cards": [
            {"id": c["id"], "type": c["type"], "name": c["name"], "content": c["content"]}
            for c in active_cards
        ],
        "character_state": active_characters_state,
        "multi_tier_context": multi_tier_context,
        "user_input": narrator_input
    }

    _editor_enabled = _get_effective_editor_enabled(world_name)
    planner_out = call_planner_stage(base_payload, narrator_input, world_name=world_name)
    scene_outline = planner_out["scene_outline"]
    facts_this_turn = planner_out["facts_this_turn"]
    state_changes = planner_out["state_changes"]
    suggested_actions = planner_out["suggested_actions"]
    anchor_keywords = planner_out["anchor_keywords"]
    open_threads_update = planner_out["open_threads_update"]
    is_ooc = planner_out["is_ooc"]
    action_translation = planner_out["action_translation"]
    effective_user_input = planner_out["effective_user_input"]

    foreshadowing_tracker_clean = world_config.get("foreshadowing_tracker", [])
    if not isinstance(foreshadowing_tracker_clean, list):
        foreshadowing_tracker_clean = world_config.get("foreshadowings", [])
    ft_add = state_changes.get("foreshadowing_tracker_add")
    if ft_add is not None:
        state_changes["foreshadowing_tracker_add"] = ensure_foreshadowing_consistency(
            foreshadowing_tracker_clean, open_threads_update, ft_add
        )

    chapter_text, state_changes, chapter_end, chapter_title, suggested_actions, draft_entities, _editor_polished, anchor_keywords, open_threads_update, is_ooc, action_translation, missing_anchor_keywords, steps, variants, perception_data = call_writer_stage(
        base_payload, scene_outline, facts_this_turn, state_changes,
        suggested_actions, anchor_keywords, open_threads_update,
        is_ooc, action_translation, effective_user_input,
        world_name=world_name, editor_enabled=_editor_enabled
    )

    boundary_correction = None
    violations = check_boundary_violations(state_changes, checkpoint)
    map_violations = check_map_based_restrictions(
        state_changes, location_map,
        character_state.get("characters", {}), world_config
    )
    all_violations = violations + map_violations

    if all_violations:
        correction_parts = []
        if violations:
            correction_parts.append(build_boundary_correction_note(violations, checkpoint))
        if map_violations:
            correction_parts.append(build_map_restriction_note(map_violations))
        retry_payload = dict(base_payload)
        retry_payload["correction_note"] = "\n\n".join(correction_parts)
        chapter_text, state_changes, chapter_end, chapter_title, suggested_actions, draft_entities, _editor_polished, anchor_keywords, open_threads_update, _, _, missing_anchor_keywords, steps, variants, perception_data = call_writer_stage(
            retry_payload, scene_outline, facts_this_turn, state_changes,
            suggested_actions, anchor_keywords, open_threads_update,
            is_ooc, action_translation, effective_user_input,
            world_name=world_name, editor_enabled=_editor_enabled
        )

        violations_after_retry = check_boundary_violations(state_changes, checkpoint)
        map_violations_after_retry = check_map_based_restrictions(
            state_changes, location_map,
            character_state.get("characters", {}), world_config
        )
        all_violations_after = violations_after_retry + map_violations_after_retry
        if all_violations_after:
            raise_boundary_hard_reject(
                violations_after_retry or map_violations_after_retry, checkpoint,
                user_input=narrator_input,
                recent_text=running_summary,
                world_config=world_config
            )
        else:
            boundary_correction = {
                "detected": True,
                "auto_retry_fixed_it": True,
                "violations": all_violations,
                "note": "Narrator rewrote correctly within scope after being reminded."
            }

    checker_result = run_consistency_checker(
        chapter_text, state_changes, world_config, checkpoint,
        active_cards, active_characters_state, world_name=world_name
    )
    consistency_rewritten = False
    if checker_result["severity"] == "major":
        retry_payload = dict(base_payload)
        retry_payload["correction_note"] = build_consistency_correction_note(checker_result["issues"])
        chapter_text, state_changes, chapter_end, chapter_title, suggested_actions, draft_entities, _editor_polished, anchor_keywords, open_threads_update, _, _, missing_anchor_keywords, steps, variants, perception_data = call_writer_stage(
            retry_payload, scene_outline, facts_this_turn, state_changes,
            suggested_actions, anchor_keywords, open_threads_update,
            is_ooc, action_translation, effective_user_input,
            world_name=world_name, editor_enabled=_editor_enabled
        )
        consistency_rewritten = True

        violations_after_cc = check_boundary_violations(state_changes, checkpoint)
        map_violations_after_cc = check_map_based_restrictions(
            state_changes, location_map,
            character_state.get("characters", {}), world_config
        )
        all_violations_after_cc = violations_after_cc + map_violations_after_cc
        if all_violations_after_cc:
            raise_boundary_hard_reject(
                violations_after_cc or map_violations_after_cc, checkpoint,
                user_input=narrator_input,
                recent_text=running_summary,
                world_config=world_config
            )

    this_chapter_index, this_turn_index = get_open_chapter_state(chapters_data)

    skill_post_violation = check_skill_limiter(
        chapter_text=chapter_text,
        character_state=character_state.get("characters", {}),
        protagonist_id=protagonist_id,
        skill_cards=skill_cards,
        user_input=narrator_input,
        state_changes=state_changes
    )
    if skill_post_violation and skill_post_violation.get("boundary_violated"):
        raise HTTPException(
            status_code=400,
            detail={
                "boundary_violated": True,
                "reason": skill_post_violation.get("reason", ""),
                "unlearned_skill": skill_post_violation.get("unlearned_skill", ""),
                "skill_check": skill_post_violation
            }
        )

    character_state["characters"] = apply_state_changes(
        character_state["characters"], state_changes,
        trait_definitions=world_config.get("trait_definitions"),
        exclusive_titles=world_config.get("titles", []),
        story_clock=story_clock,
        foreshadowing_tracker=foreshadowing_tracker,
        current_chapter_index=this_chapter_index
    )

    world_config["story_clock"] = story_clock
    world_config["foreshadowing_tracker"] = foreshadowing_tracker

    open_threads = world_config.get("open_threads", [])
    if not isinstance(open_threads, list):
        open_threads = []
    if open_threads_update and isinstance(open_threads_update, str) and open_threads_update.strip():
        open_threads.append({
            "chapter_index": this_chapter_index,
            "turn_index": this_turn_index,
            "note": open_threads_update.strip(),
            "checkpoint_id": current_checkpoint_id,
            "resolution_deadline": "ongoing"
        })
    world_config["open_threads"] = open_threads

    # Psychology Runtime — per-observer LLM calls
    if world_config.get("psychology_enabled", True):
        active_chars_for_psych = {
            cid: st for cid, st in character_state.get("characters", {}).items()
            if cid in active_characters_state or st.get("alive", True)
        }
        if active_chars_for_psych and len(active_chars_for_psych) > 0:
            try:
                perceptions = generate_perceptions_for_all_characters(
                    active_chars_for_psych,
                    chapter_text,
                    world_config,
                    checkpoint,
                    world_name=world_name
                )
                psych_updates = update_psychologies_for_all_characters(
                    active_chars_for_psych,
                    chapter_text,
                    perceptions,
                    world_config,
                    world_name=world_name
                )
                character_state["characters"] = apply_psychology_changes(
                    character_state["characters"],
                    psych_updates
                )
                chapter_record_perception = {
                    cid: per for cid, per in perceptions.items()
                    if cid in active_chars_for_psych
                }
                if chapter_record_perception:
                    state_changes["perception_data"] = chapter_record_perception
                if psych_updates:
                    state_changes["psychology_updates"] = psych_updates
            except Exception as e:
                logger.warning(f"Psychology runtime failed for world={world_name}: {e}")

    this_chapter_closed = decide_chapter_closed(
        this_chapter_index, this_turn_index, chapters_data, chapter_text, chapter_end,
        output_length=world_config.get("output_length", "Standard"),
        pacing_level=world_config.get("pacing_level", "Balanced")
    )

    this_ooc_scope = "branch_local" if is_ooc else None

    chapter_record = {
        "chapter_index": this_chapter_index,
        "turn_index": this_turn_index,
        "chapter_closed": this_chapter_closed,
        "chapter_title": chapter_title if this_chapter_closed else None,
        "checkpoint_id": current_checkpoint_id,
        "user_input": display_input,
        "chapter_text": chapter_text,
        "notes": state_changes.get("notes", ""),
        "boundary_correction": boundary_correction,
        "consistency_check": {
            "severity": checker_result["severity"],
            "issues": checker_result["issues"],
            "explanation": checker_result["explanation"],
            "triggered_rewrite": consistency_rewritten
        },
        "anchor_keywords": anchor_keywords,
        "missing_anchor_keywords": missing_anchor_keywords if missing_anchor_keywords else [],
        "editor_polished": _editor_polished,
        "is_ooc": is_ooc,
        "action_translation": action_translation if is_ooc else None,
        "ooc_scope": this_ooc_scope,
        "steps": steps if steps else None,
        "variants": variants if variants else None,
        "perception_data": state_changes.get("perception_data") if state_changes.get("perception_data") else perception_data
    }
    chapters_data["chapters"].append(chapter_record)

    if this_chapter_closed:
        summary_res = update_running_summary(
            chapters_data, this_chapter_index, chapter_title, world_name=world_name, world_config=world_config
        )
        chapters_data["running_summary"] = summary_res["running_summary"]
        chapter_record["tension_level"] = summary_res.get("tension_level", 5)
        chapter_record["mood"] = summary_res.get("mood", "")

    for char_id, state in character_state.get("characters", {}).items():
        if isinstance(state, dict) and "status_effects" in state and isinstance(state["status_effects"], list):
            active_effects = []
            for effect in state["status_effects"]:
                if isinstance(effect, dict):
                    dur = effect.get("duration")
                    if isinstance(dur, (int, float)):
                        effect["duration"] = int(dur) - 1
                        if effect["duration"] > 0:
                            active_effects.append(effect)
                    else:
                        active_effects.append(effect)
                else:
                    active_effects.append(effect)
            state["status_effects"] = active_effects

    checkpoint_advanced = advance_checkpoint_if_ready(
        canon_timeline, world_config, character_state["characters"], card_registry,
        chapter_closed=this_chapter_closed
    )

    # Resolve against the final turn clock, then commit consequences with the turn.
    # The engine owns logical turns; model-generated calendar time is independent.
    story_clock["tick"] = turn_start_tick + 1
    from app.world_events import tick_world_events, load_world_events
    world_events = load_world_events(world_path)
    resolved = tick_world_events(
        world_events, world_config, character_state["characters"],
        world_canon_store, location_map
    )

    # Tick endgame after checkpoint advancement and world events.
    endgame_result = tick_endgame(world_config, character_state["characters"])
    if endgame_result.get("status_changed"):
        if world_config.get("lifecycle_status", "active") == "active" and endgame_result.get("new_status") == "ready":
            world_config["lifecycle_status"] = "endgame_pending"

    if draft_entities:
        for draft in draft_entities:
            if isinstance(draft, dict) and "name" in draft and "type" in draft:
                existing = deduplicate_entity(card_registry, draft["name"], draft["type"])
                if existing is not None:
                    if draft.get("description") and not existing.get("content"):
                        existing["content"] = draft["description"]
                    draft_aliases = existing.setdefault("aliases", [])
                    dedup_alias = draft["name"]
                    if dedup_alias not in draft_aliases:
                        draft_aliases.append(dedup_alias)
                else:
                    draft_id = f"{draft['type']}_{uuid.uuid4().hex[:8]}"
                    card_registry["cards"].append({
                        "id": draft_id,
                        "type": draft["type"],
                        "name": draft["name"],
                        "content": draft.get("description", ""),
                        "unlock_checkpoint_id": None,
                        "status": "draft",
                        "entity_id": draft.get("entity_id"),
                        "aliases": draft.get("aliases", []),
                        "scope": draft.get("scope"),
                        "entity_status": "draft"
                    })

    check_rolling_summary_trigger(chapters_data, world_name=world_name, world_config=world_config)

    updates = {
        "character_state.json": character_state,
        "chapters.json": chapters_data,
        "world_config.json": world_config,
    }
    if checkpoint_advanced or draft_entities:
        updates["card_registry.json"] = card_registry
    if resolved:
        updates["world_events.json"] = world_events
        updates["world_canon_store.json"] = world_canon_store
        if location_map is not None:
            updates["location_map.json"] = location_map

    extractor_cross_check = None
    if _get_effective_extractor_cross_check(world_name):
        existing_facts = [f.get("statement", "") for f in world_canon_store.get("facts", []) if isinstance(f, dict)]
        extractor_cross_check = run_extractor_cross_check(
            world_name, chapter_text, existing_facts, world_config
        )

    commit_world_files(world_path, updates)

    return {
        "chapter": chapter_record,
        "state_changes_applied": state_changes,
        "used_mock_llm": not has_real_api_key(world_name),
        "checkpoint_advanced": checkpoint_advanced,
        "lore_rag_filter": lore_rag_filter,
        "suggested_actions": suggested_actions,
        "extractor_cross_check": extractor_cross_check,
    }
