"""Orchestration and compatibility exports; implementations live in focused modules."""
import logging
from app.checkpoint_engine import advance_checkpoint_if_ready
from app.checkpoint_engine import build_boundary_correction_note
from app.checkpoint_engine import build_map_restriction_note
from app.checkpoint_engine import check_boundary_violations
from app.checkpoint_engine import check_map_based_restrictions
from app.checkpoint_engine import find_checkpoint
from app.checkpoint_engine import get_active_cards
from app.checkpoint_engine import raise_boundary_hard_reject
from app.checkpoint_engine import tick_endgame
from app.persistence import commit_world_files
from app.persistence import locked_world
from app.psychology import apply_psychology_changes
from app.psychology import generate_perceptions_for_all_characters
from app.psychology import update_psychologies_for_all_characters
from app.rag import build_rag_context_text
from app.state_manager import DEFAULT_STORY_CLOCK
from app.state_manager import apply_state_changes
from app.state_manager import ensure_foreshadowing_consistency
from app.story.consistency import build_consistency_checker_payload
from app.story.consistency import build_consistency_correction_note
from app.story.consistency import parse_checker_response
from app.story.consistency import run_consistency_checker
from app.story.consistency import run_extractor_cross_check
from app.story.entities import _validate_imported_package
from app.story.entities import deduplicate_entity
from app.story.entities import normalize_character_dict
from app.story.generation import call_narrator_and_parse
from app.story.generation import call_planner_stage
from app.story.generation import call_writer_stage
from app.story.generation import check_anchor_keywords
from app.story.memory import _filter_memorable_beats_by_token_budget
from app.story.memory import _is_rolled
from app.story.memory import build_multi_tier_context
from app.story.memory import build_summarizer_payload
from app.story.memory import check_rolling_summary_trigger
from app.story.memory import compute_word_budget
from app.story.memory import get_unshelved_turn_count
from app.story.memory import merge_canon_and_delta
from app.story.memory import parse_summarizer_response
from app.story.memory import total_story_word_count
from app.story.memory import update_running_summary
from app.story.pacing import CHAPTER_HARD_CLOSE_TURNS
from app.story.pacing import CHAPTER_SOFT_CLOSE_TURNS
from app.story.observer import scene_participants
from app.story.views import narrative_character_view
from app.story.pacing import CHAPTER_SOFT_CLOSE_WORDS
from app.story.pacing import CHAPTER_SUMMARY_BUDGET_CEIL
from app.story.pacing import CHAPTER_SUMMARY_BUDGET_FLOOR
from app.story.pacing import CHAPTER_SUMMARY_BUDGET_RATIO
from app.story.pacing import DEFAULT_LORE_RAG_MAX_TOKENS
from app.story.pacing import MEMORABLE_BEATS_MAX
from app.story.pacing import RECENT_TURNS_CONTEXT_LIMIT
from app.story.pacing import ROLLING_SUMMARIZATION_TRIGGER_TURNS
from app.story.pacing import SUMMARY_MAX_TOKENS
from app.story.pacing import WORKING_MEMORY_TURNS
from app.story.pacing import decide_chapter_closed
from app.story.pacing import get_close_thresholds
from app.story.pacing import get_open_chapter_state
from app.story.pacing import get_output_length_config
from app.story.pacing import get_pacing_context_config
from app.story.pacing import get_recent_turns_for_context
from app.story.pacing import get_words_per_turn_target
from app.story.prelude import _generate_prelude
from app.story.prelude import build_opening_instruction
from app.story.prelude import validate_prelude_against_rules
from fastapi import HTTPException
from skill_limiter import check_skill_limiter
import json
import os
import uuid

logger = logging.getLogger(__name__)


@locked_world
def _generate_chapter(world_name: str, narrator_input: str, display_input: str = None,
                      request_id: str = None, expected_revision: int = None,
                      regenerate: bool = False) -> dict:
    from app.storage import (
        world_path_of, read_world_file, write_world_file,
        has_real_api_key, get_world_style_card,
        read_world_canon, read_branch_delta, require_world,
        _get_effective_editor_enabled, _get_effective_extractor_cross_check,
        latest_turn_snapshot_dir, create_turn_snapshot,
    )
    from app.action_guard import (
        content_hash, lookup_receipt, check_expected_revision, build_receipts_document, bump_revision, get_revision,
    )
    if display_input is None:
        display_input = narrator_input

    world_path = require_world(world_name)

    # The on-disk config is the current (post-last-turn) state; revision checks
    # must always use it, not the snapshot's older revision.
    current_config = read_world_file(world_path, "world_config.json")

    # Regenerate must start from the state before the last turn, never accumulate
    # on top of it. If a pre-turn snapshot exists we read the turn from it, so a
    # failed regeneration leaves the old turn untouched on disk.
    using_snapshot = False
    if regenerate:
        snapshot_dir = latest_turn_snapshot_dir(world_path)
        if snapshot_dir and current_config.get("pre_turn_snapshot"):
            using_snapshot = True
            state_dir = snapshot_dir
        else:
            state_dir = world_path
    else:
        state_dir = world_path

    world_config = read_world_file(state_dir, "world_config.json")
    card_registry = read_world_file(state_dir, "card_registry.json")
    canon_timeline = read_world_file(state_dir, "canon_timeline.json")
    character_state = read_world_file(state_dir, "character_state.json")
    chapters_data = read_world_file(state_dir, "chapters.json")
    world_canon_store = read_world_canon(state_dir)
    branch_delta = read_branch_delta(state_dir)

    action_hash = content_hash({
        "kind": "regenerate" if regenerate else "continue",
        "input": narrator_input,
        "display_input": display_input,
    })
    replay = lookup_receipt(world_path, request_id, action_hash)
    if replay is not None:
        return replay
    revision_before = check_expected_revision(current_config, expected_revision)

    if regenerate and not using_snapshot:
        turns = chapters_data.get("chapters", [])
        if not turns:
            raise HTTPException(
                status_code=400,
                detail="Khong co turn nao de regenerate. World chua co chapter nao."
            )
        last_turn = turns[-1]
        if last_turn.get("chapter_closed"):
            closed_chapter_idx = last_turn.get("chapter_index", 0)
            turns_before = [t for t in turns if t.get("chapter_index", 0) < closed_chapter_idx]
            chapters_data["chapters"] = turns_before
            if not turns_before:
                chapters_data["running_summary"] = ""
                chapters_data["memorable_beats"] = []
        else:
            chapters_data["chapters"] = turns[:-1]

    if world_config.get("lifecycle_status") == "completed":
        raise HTTPException(status_code=409, detail="This story is completed. Restore a save or create a branch to continue.")

    location_map = None
    try:
        location_map = read_world_file(state_dir, "location_map.json")
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
        chapters_data, world_config, checkpoint, merged_canon.get("facts", []),
        max_context_tokens=world_config.get("context_max_tokens"),
    )

    protagonist_entry = character_state.get("characters", {}).get(protagonist_id or "", {})
    scene_location = protagonist_entry.get("location", "") if isinstance(protagonist_entry, dict) else ""
    participants = scene_participants(
        character_state, scene_location,
        protagonist_id=protagonist_id,
        allowed_ids=set(active_characters_state.keys()),
        max_observers=world_config.get("psychology_max_npc_per_turn", 6),
    )
    narrative_characters = narrative_character_view(participants)

    from app.story.knowledge import build_character_knowledge
    character_knowledge = build_character_knowledge(
        character_state.get("characters", {}),
        list(participants.keys()),
        merged_canon.get("facts", []),
    )
    from app.story.relationship_memory import build_relationship_context
    relationship_context = build_relationship_context(
        character_state.get("characters", {}), list(participants.keys())
    )

    from app.story.action_resolution import resolve_action
    action_resolution = resolve_action(
        narrator_input,
        character_state.get("characters", {}),
        protagonist_id,
        world_config,
        checkpoint=checkpoint,
        location_map=location_map,
        world_name=world_name,
        turn_index=story_clock.get("tick", 0),
        action_id=f"act_{current_checkpoint_id}_{story_clock.get('tick', 0)}",
    )

    from app.world.travel import build_travel_plan
    travel_resolution = build_travel_plan(
        narrator_input, location_map or {}, scene_location,
        tick_minutes=int(world_config.get("travel_tick_minutes", 60) or 60),
        seed_key=f"{world_name}|{story_clock.get('tick', 0)}",
    )
    if travel_resolution and travel_resolution.get("status") == "arrived":
        attempted = {"characters": {protagonist_id: {
            "location": travel_resolution.get("destination", "")
        }}}
        travel_violations = (
            check_boundary_violations(attempted, checkpoint)
            + check_map_based_restrictions(
                attempted, location_map, character_state.get("characters", {}), world_config
            )
        )
        if travel_violations:
            travel_resolution.update(
                status="blocked", reason="destination_locked",
                elapsed_minutes=0, tick_advance=1,
                violations=travel_violations,
            )

    base_payload = {
        "world_canon_facts": world_canon_facts,
        # Per-subject knowledge (what each active character believes, with source
        # and confidence). W02 uses this to keep a scene limited to observers.
        "character_knowledge": character_knowledge,
        # Event-grounded relationship memories per character (promises, debts,
        # betrayals, ...). Not a replacement for affinity, a grounding for it.
        "relationship_context": relationship_context,
        # Engine-committed outcome of the player's action. The writer must narrate
        # this result, never a different one.
        "action_resolution": action_resolution,
        "travel_resolution": travel_resolution,
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
        "character_state": narrative_characters,
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
        active_cards, narrative_characters, world_name=world_name
    )
    consistency_rewritten = False
    if checker_result["status"] == "failed":
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

        # The fixed version must be re-checked within the same bounded retry:
        # never mark a rewrite as passed without running the checker again.
        checker_result = run_consistency_checker(
            chapter_text, state_changes, world_config, checkpoint,
            active_cards, narrative_characters, world_name=world_name
        )

    unchecked_commit_allowed = (
        checker_result["status"] == "unavailable"
        and bool(world_config.get("allow_unchecked_commit", False))
    )
    if checker_result["status"] != "passed" and not unchecked_commit_allowed:
        # Explicit policy: a turn the checker could not confirm is kept as a draft
        # and NOT committed. A known failure (major contradiction after the bounded
        # rewrite) is also not applied; allow_unchecked_commit only covers the
        # "could not check at all" case, never a known-bad result. Nothing below
        # runs, so no tick/consequence is applied.
        if checker_result["status"] == "failed":
            reason = "consistency_check_failed"
            status_code = 422
            message = (
                "The consistency checker still found major contradictions after one rewrite, "
                "so this turn was kept as a draft and was NOT saved. Tick and consequences are "
                "unchanged. Adjust the action or retry."
            )
        else:
            reason = "consistency_checker_unavailable"
            status_code = 503
            message = (
                "Consistency checker did not run, so this turn was kept as a draft and was NOT saved. "
                "Tick and consequences are unchanged. Retry the action."
            )
        raise HTTPException(
            status_code=status_code,
            detail={
                "reason": reason,
                "status": checker_result["status"],
                "retryable": True,
                "persisted": False,
                "message": message,
                "consistency_check": {
                    "status": checker_result["status"],
                    "severity": checker_result["severity"],
                    "issues": checker_result["issues"],
                    "explanation": checker_result["explanation"],
                    "triggered_rewrite": consistency_rewritten,
                },
                "draft_chapter_text": chapter_text,
            }
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

    # The model narrates travel but cannot override the engine-owned destination
    # or elapsed time. A blocked route always leaves the protagonist in place.
    if travel_resolution:
        protagonist_changes = state_changes.setdefault("characters", {}).setdefault(protagonist_id, {})
        if travel_resolution.get("status") in ("arrived", "interrupted"):
            protagonist_changes["location"] = (
                travel_resolution.get("destination") if travel_resolution.get("status") == "arrived"
                else travel_resolution.get("stopped_at", scene_location)
            )
        else:
            protagonist_changes.pop("location", None)
        state_changes.pop("story_clock_delta", None)

    character_state["characters"] = apply_state_changes(
        character_state["characters"], state_changes,
        trait_definitions=world_config.get("trait_definitions"),
        exclusive_titles=world_config.get("titles", []),
        story_clock=story_clock,
        foreshadowing_tracker=foreshadowing_tracker,
        current_chapter_index=this_chapter_index
    )

    world_config["story_clock"] = story_clock
    if travel_resolution and travel_resolution.get("status") in ("arrived", "interrupted"):
        from app.world.travel import advance_clock_minutes
        advance_clock_minutes(story_clock, int(travel_resolution.get("elapsed_minutes", 0) or 0))
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

    # Psychology Runtime — only characters present and able to perceive the scene.
    # Distant NPCs never receive the transcript; they learn later through a
    # told-by/rumor channel. The number of psychology calls is capped per turn.
    psychology_status = {"status": "disabled"}
    if world_config.get("psychology_enabled", True):
        from app.story.observer import psychology_subjects
        psych_subjects = psychology_subjects(participants, protagonist_id)
        psychology_status = {
            "status": "ran" if psych_subjects else "skipped",
            "scene_location": scene_location,
            "participants": list(participants.keys()),
            "subjects": list(psych_subjects.keys()),
        }
        if psych_subjects:
            try:
                perceptions = generate_perceptions_for_all_characters(
                    psych_subjects,
                    chapter_text,
                    world_config,
                    checkpoint,
                    world_name=world_name
                )
                psych_updates = update_psychologies_for_all_characters(
                    psych_subjects,
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
                    if cid in psych_subjects
                }
                if chapter_record_perception:
                    state_changes["perception_data"] = chapter_record_perception
                if psych_updates:
                    state_changes["psychology_updates"] = psych_updates
            except Exception as e:
                psychology_status = {
                    "status": "error",
                    "reason": str(e),
                    "scene_location": scene_location,
                    "participants": list(participants.keys()),
                    "subjects": list(psych_subjects.keys()),
                }
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
        "psychology_status": psychology_status,
        "action_resolution": action_resolution,
        "travel_resolution": travel_resolution,
        "consistency_check": {
            "status": checker_result["status"],
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
    story_clock["tick"] = turn_start_tick + int(
        travel_resolution.get("tick_advance", 1) if travel_resolution else 1
    )
    from app.world_events import tick_world_events, load_world_events
    world_events = load_world_events(world_path)
    resolved = tick_world_events(
        world_events, world_config, character_state["characters"],
        world_canon_store, location_map
    )

    # Discovery: the player only learns of an event if it is discoverable from the
    # start or they were present when it resolved. Far events stay hidden (no
    # spoiler). Discovery travels with the turn commit.
    from app.story.discovery import load_discoveries, record_discovery, ensure_start_discoveries
    discovery_store = load_discoveries(world_path)
    discovery_changed = ensure_start_discoveries(
        discovery_store, world_events.get("events", []), story_clock["tick"]
    )
    protagonist_location = character_state.get("characters", {}).get(protagonist_id, {}).get("location", "")
    for event in world_events.get("events", []):
        if not isinstance(event, dict) or event.get("event_id") not in resolved:
            continue
        outcome = next(
            (o for o in event.get("outcomes", [])
             if isinstance(o, dict) and o.get("outcome_id") == event.get("resolved_outcome_id")),
            None,
        )
        event_location = event.get("location_id") or ""
        if not event_location and outcome:
            for effect in outcome.get("location_effects", []) or []:
                if isinstance(effect, dict) and effect.get("location_id"):
                    event_location = effect["location_id"]
                    break
        if event_location and (str(event_location).strip().lower()
                               == str(protagonist_location).strip().lower()):
            discovery_changed |= record_discovery(
                discovery_store, event.get("event_id", ""),
                {"kind": "witnessed", "who": protagonist_id, "tick": story_clock["tick"]},
                story_clock["tick"], known_deadline_tick=event.get("deadline_tick"),
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

    # Keep the revision monotonic even when regenerating from an older snapshot.
    world_config["revision"] = max(get_revision(world_config), revision_before)
    world_config["revision"] = bump_revision(world_config)

    # Record the pre-turn state so a later regenerate starts from here. When
    # regenerating we keep the existing snapshot (it already is that state).
    if not using_snapshot:
        create_turn_snapshot(world_path)
    world_config["pre_turn_snapshot"] = "latest"

    updates = {
        "character_state.json": character_state,
        "chapters.json": chapters_data,
        "world_config.json": world_config,
    }
    if discovery_changed:
        updates["discovery.json"] = discovery_store
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

    response = {
        "chapter": chapter_record,
        "state_changes_applied": state_changes,
        "used_mock_llm": not has_real_api_key(world_name),
        "checkpoint_advanced": checkpoint_advanced,
        "lore_rag_filter": lore_rag_filter,
        "suggested_actions": suggested_actions,
        "extractor_cross_check": extractor_cross_check,
        "revision": world_config["revision"],
    }
    # The receipt travels in the same commit as the turn (journaled as one unit),
    # so a retry with the same request_id replays it without calling the model
    # again, and a crash never leaves a committed turn without its receipt.
    receipts = build_receipts_document(world_path, request_id, action_hash, revision_before, response)
    if receipts is not None:
        updates["turn_receipts.json"] = receipts

    commit_world_files(world_path, updates)

    return response
    return response
