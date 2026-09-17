"""Legacy main-module exports. New code should import the owning module directly."""
import json
import os
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.storage import (
    WORLDS_DIR, RUNTIME_CONFIG_PATH, DEFAULT_OPENROUTER_MODEL,
    world_path_of, write_world_file, read_world_file,
    get_effective_api_key, get_effective_model,
    get_effective_fallback_chain, has_real_api_key,
    require_world, _validate_world_name,
    read_world_runtime_override, write_world_runtime_override,
    _world_runtime_override_path,
    build_runtime_config_status, read_runtime_config, write_runtime_config,
    _mask_api_key, _sanitize_and_preserve_fallback_chain,
    _sanitize_fallback_chain_for_status, _compute_role_assignments_effective,
    _get_effective_role_assignments, _get_effective_editor_enabled,
    _default_role_index, get_effective_fallback_chain_for_role,
    _VALID_ROLES,
    read_saves_index, write_saves_index, snapshot_world_state,
    build_save_entry, new_save_id, now_str,
    get_world_style_card, write_world_style_card,
    read_world_canon, write_world_canon,
    read_branch_delta, write_branch_delta,
)

from app.engine import (
    TEMPLATES, DEFAULT_LORE_RAG_MAX_TOKENS, DEFAULT_STORY_CLOCK,
    CHAPTER_SOFT_CLOSE_TURNS, CHAPTER_SOFT_CLOSE_WORDS,
    CHAPTER_HARD_CLOSE_TURNS, RECENT_TURNS_CONTEXT_LIMIT,
    make_card, make_checkpoint, make_character,
    find_checkpoint, get_active_cards,
    _rag_tokenize, _rag_cosine_score, estimate_tokens,
    select_relevant_lore_cards,
    build_rag_context_text, build_opening_instruction,
    mock_planner_response, mock_narrator_response, mock_prelude_response, mock_consistency_checker_response,
    LLMCallError, RateLimitError,
    _retry_after_header_seconds, get_base_url_for_provider,
    call_llm, test_llm_connection, parse_llm_json,
    apply_story_clock_changes, apply_foreshadowing_changes,
    apply_state_changes, get_nested_field,
    eval_condition, checkpoint_conditions_met, advance_checkpoint_if_ready,
    check_boundary_violations, build_boundary_correction_note,
    raise_boundary_hard_reject,
    build_consistency_checker_payload, parse_checker_response,
    run_consistency_checker, build_consistency_correction_note,
    get_open_chapter_state, decide_chapter_closed,
    get_recent_turns_for_context,
    mock_summarizer_response, build_summarizer_payload,
    parse_summarizer_response, update_running_summary,
    compute_word_budget, total_story_word_count,
    _filter_memorable_beats_by_token_budget,
    SUMMARY_MAX_TOKENS, CHAPTER_SUMMARY_BUDGET_RATIO,
    CHAPTER_SUMMARY_BUDGET_FLOOR, CHAPTER_SUMMARY_BUDGET_CEIL, MEMORABLE_BEATS_MAX,
    call_narrator_and_parse, _generate_chapter, check_anchor_keywords,
    _validate_imported_package, merge_canon_and_delta, get_pacing_context_config,
    get_words_per_turn_target,
    get_output_length_config, get_close_thresholds,
)

from app.models import (
    WorldBuilderChunk, WorldConfigUpdate, TraitDefinition,
    CheckpointBranch, WorldCreationRequest, InterviewRequest,
    InterviewRespondRequest, ImportWorldRequest, StyleCardModel,
    PowerStatModel, CreatorAssistantRequest, LintChapterRequest,
    RewriteChapterRequest, RuntimeConfigUpdate, ChapterContinueRequest,
    ChapterStartRequest, CharacterStateChange, StateChangesModel,
    CardModel, CheckpointBoundaryModel, CheckpointModel, CharacterModel,
    CardRegistryUpdate, CanonTimelineUpdate, CharacterStateUpdate,
    ForceAdvanceRequest, CreateSaveRequest, BranchRequest,
    RegenerateRequest, ForeshadowingsUpdateReq, ForkRequest,
    WorldCanonFact, BranchLocalDeltaModel,
)

from prompts import (
    WRITER_SYSTEM_PROMPT, EXTRACTOR_SYSTEM_PROMPT, PLANNER_SYSTEM_PROMPT,
    WORLD_BUILDER_SKELETON_PROMPT, WORLD_BUILDER_CARDS_PROMPT,
    WORLD_BUILDER_CHARACTERS_PROMPT, CONSISTENCY_CHECKER_SYSTEM_PROMPT,
    SUMMARIZER_SYSTEM_PROMPT, WORLD_BUILDER_INTERVIEW_PROMPT,
    CREATOR_ASSISTANT_PROMPT, LINTER_SYSTEM_PROMPT, REWRITE_SYSTEM_PROMPT,
    EDITOR_SYSTEM_PROMPT, ARC_EXTENDER_PROMPT,
    PRELUDE_WRITER_PROMPT, PRELUDE_VALIDATOR_PROMPT,
)

from skill_limiter import check_skill_limiter


__all__ = [name for name in globals() if not name.startswith("__")]
