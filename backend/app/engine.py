import json
import logging
import os
from typing import Dict, List, Optional

from app.storage import (
    get_world_style_card, get_effective_fallback_chain,
    has_real_api_key,
)

from app.llm_client import (
    call_llm, test_llm_connection, parse_llm_json,
    LLMCallError, RateLimitError,
    _retry_after_header_seconds, get_base_url_for_provider,
    mock_planner_response, mock_narrator_response,
    mock_prelude_response, mock_consistency_checker_response,
    mock_summarizer_response,
    _set_requests_module, _VALID_ROLES,
)
from app.rag import (
    _RAG_STOPWORDS,
    _rag_tokenize, _rag_cosine_score, estimate_tokens,
    select_relevant_lore_cards, build_rag_context_text,
)
from app.state_manager import (
    DEFAULT_STORY_CLOCK,
    apply_story_clock_changes, apply_foreshadowing_changes,
    ensure_foreshadowing_consistency,
    apply_state_changes, get_nested_field, eval_condition,
    _apply_outcome_payload,
)
from app.checkpoint_engine import (
    TEMPLATES,
    make_card, make_checkpoint, make_character,
    find_checkpoint, get_active_cards,
    checkpoint_conditions_met, sanitize_required_conditions,
    _advance_sub_beats, advance_checkpoint_if_ready,
    _is_location_in_zone, check_boundary_violations,
    build_boundary_correction_note,
    BOUNDARY_HARD_REJECT_TEMPLATES,
    raise_boundary_hard_reject,
    generate_location_map,
    _get_location_unlock_requirements,
    check_map_based_restrictions, build_map_restriction_note,
)
from app.language_detection import (
    VI_DIACRITICS_REGEX, VI_COMMON_WORDS,
    detect_story_language,
)
from app.chapter_generator import (
    DEFAULT_LORE_RAG_MAX_TOKENS,
    CHAPTER_SOFT_CLOSE_TURNS, CHAPTER_SOFT_CLOSE_WORDS,
    CHAPTER_HARD_CLOSE_TURNS, RECENT_TURNS_CONTEXT_LIMIT,
    WORKING_MEMORY_TURNS,
    ROLLING_SUMMARIZATION_TRIGGER_TURNS,
    SUMMARY_MAX_TOKENS,
    CHAPTER_SUMMARY_BUDGET_RATIO, CHAPTER_SUMMARY_BUDGET_FLOOR,
    CHAPTER_SUMMARY_BUDGET_CEIL, MEMORABLE_BEATS_MAX,
    get_pacing_context_config, get_output_length_config,
    get_words_per_turn_target, get_close_thresholds,
    build_opening_instruction,
    validate_prelude_against_rules, _generate_prelude,
    merge_canon_and_delta,
    _filter_memorable_beats_by_token_budget,
    build_multi_tier_context, _is_rolled, get_unshelved_turn_count,
    check_rolling_summary_trigger,
    build_summarizer_payload, parse_summarizer_response,
    total_story_word_count, compute_word_budget,
    update_running_summary, check_anchor_keywords,
    call_planner_stage, call_writer_stage, call_narrator_and_parse,
    deduplicate_entity, run_extractor_cross_check,
    _generate_chapter, _validate_imported_package,
    build_consistency_checker_payload,
    parse_checker_response, run_consistency_checker,
    build_consistency_correction_note,
    get_open_chapter_state, decide_chapter_closed,
    get_recent_turns_for_context,
    normalize_character_dict,
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
