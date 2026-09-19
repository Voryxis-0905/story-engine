from fastapi import APIRouter, HTTPException
import json
import logging
import os
import re
import time

logger = logging.getLogger(__name__)

from app.storage import (
    require_world, world_path_of, read_world_file, write_world_file,
    has_real_api_key, get_effective_model, read_world_runtime_override,
    write_world_runtime_override, bump_world_revision, mark_builder_manual
)
from app.engine import (
    TEMPLATES, call_llm, parse_llm_json, make_card, make_checkpoint,
    make_character, LLMCallError, RateLimitError, sanitize_required_conditions,
    WORLD_BUILDER_SKELETON_PROMPT, WORLD_BUILDER_CARDS_PROMPT,
    WORLD_BUILDER_CHARACTERS_PROMPT, WORLD_BUILDER_INTERVIEW_PROMPT,
    ARC_EXTENDER_PROMPT,
    generate_location_map,
    normalize_character_dict,
)
from app.models import (
    InterviewRequest, InterviewRespondRequest, WorldCreationRequest,
    ImportWorldRequest
)
from app.services.validators import validate_world_bundle

try:
    from prompts import WORLD_BUILDER_INTERVIEW_PROMPT as _WBI
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.skill_limiter import check_skill_limiter

router = APIRouter()


@router.post("/builder/interview")
def world_builder_interview(req: InterviewRequest):
    prompt = req.prompt.strip()
    scope = req.scope_type or "arc-only"
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt cannot be empty")

    if not has_real_api_key(None):
        return {
            "questions": [
                "What is the main tone of this world (dark, humorous, formal)?",
                "What role will the protagonist play and what is their initial goal?",
                "What is the power system or the most special rule of the world?"
            ]
        }

    try:
        payload = f"User Concept: {prompt}\nScope: {scope}"
        raw = call_llm(WORLD_BUILDER_INTERVIEW_PROMPT, payload, world_name=None)
        res = parse_llm_json(raw, expected_type=dict)
        raw_q = res.get("questions", [])
        questions = [str(q).strip() for q in raw_q if isinstance(q, (str, int, float)) and str(q).strip()]
        if not questions:
            questions = [
                "What is the main tone of this world (dark, humorous, formal)?",
                "What role will the protagonist play and what is their initial goal?",
                "What is the power system or the most special rule of the world?"
            ]
        return {"questions": questions}
    except Exception:
        return {
            "questions": [
                "What is the main tone of this world (dark, humorous, formal)?",
                "What role will the protagonist play and what is their initial goal?",
                "What is the power system or the most special rule of the world?"
            ]
        }


@router.post("/builder/interview/respond")
def world_builder_interview_respond(req: InterviewRespondRequest):
    prompt = req.prompt.strip()
    answers = [a.strip() for a in req.answers if a.strip()]

    refined = prompt
    if answers:
        refined += "\n\nQ&A Clarifications:\n" + "\n".join(f"- {a}" for a in answers)

    res = {"refined_prompt": refined}
    if hasattr(req, "scope_type") and req.scope_type:
        res["scope_type"] = req.scope_type
    return res


def _default_world_events(world_path: str, cfg: dict, character_state: dict) -> int:
    """Create valid background events for a freshly built world (idempotent).

    Events are derived deterministically from the checkpoints/locations so a new
    world actually has quests/events without another model call. Re-running never
    duplicates them.
    """
    from app.world_events import load_world_events, save_world_events, validate_event_outcome
    existing = load_world_events(world_path)
    if existing.get("events"):
        return 0

    canon = read_world_file(world_path, "canon_timeline.json")
    checkpoints = [cp for cp in canon.get("checkpoints", []) if isinstance(cp, dict)]
    characters = character_state.get("characters", {}) if isinstance(character_state, dict) else {}
    protagonist = cfg.get("protagonist_id", "")
    organizer = next(
        (cid for cid in characters if cid != protagonist and characters[cid].get("alive", True)),
        "",
    )
    events = []
    for index, cp in enumerate(checkpoints):
        cp_id = cp.get("checkpoint_id") or f"cp_{index}"
        boundary_locations = (cp.get("boundary") or {}).get("locations", [])
        location_id = boundary_locations[0] if boundary_locations else ""
        description = cp.get("description") or f"Checkpoint {cp_id}"
        trigger = cp.get("required_conditions") or [
            {"field": "story_clock.tick", "op": ">=", "value": index + 1}
        ]
        outcomes = [
            {"outcome_id": f"{cp_id}_happens", "resolution": "resolved",
             "canon_facts_add": [f"{description} unfolds."]},
            {"outcome_id": f"{cp_id}_missed", "resolution": "missed"},
        ]
        if organizer:
            outcomes.insert(1, {"outcome_id": f"{cp_id}_prevented", "resolution": "prevented",
                                "canon_facts_add": [f"The plan at {description} was stopped."]})
        event = {
            "event_id": f"ev_{cp_id}",
            "event_class": "organized",
            "organizer_id": organizer or None,
            "location_id": location_id or None,
            "status": "pending",
            "discoverable_from_start": index == 0,
            "trigger_conditions": trigger,
            "outcomes": [o for o in outcomes if not validate_event_outcome(o)],
        }
        if event["outcomes"]:
            events.append(event)

    if not events:
        return 0
    save_world_events(world_path, {"events": events})
    return len(events)


@router.get("/worlds/{world_name}/builder/status")
def builder_status(world_name: str):
    """Draft/resume cursor: where the build stopped and what already exists."""
    world_path = require_world(world_name)
    cfg = read_world_file(world_path, "world_config.json")
    status = cfg.get("creation_status", "complete")
    order = ["skeleton", "checkpoint_review", "cards", "characters", "complete"]
    index = order.index(status) if status in order else len(order) - 1
    from app.world_events import load_world_events
    return {
        "creation_status": status,
        "next_step": order[index + 1] if index + 1 < len(order) else None,
        "steps_done": order[:index + 1],
        "has_checkpoints": bool(read_world_file(world_path, "canon_timeline.json").get("checkpoints")),
        "has_cards": bool(read_world_file(world_path, "card_registry.json").get("cards")),
        "has_characters": bool(read_world_file(world_path, "character_state.json").get("characters")),
        "has_events": bool(load_world_events(world_path).get("events")),
    }


@router.post("/worlds/{world_name}/builder/events")
def builder_generate_events(world_name: str):
    """Generate/ensure background events for the world draft (idempotent)."""
    world_path = require_world(world_name)
    cfg = read_world_file(world_path, "world_config.json")
    character_state = read_world_file(world_path, "character_state.json")
    created = _default_world_events(world_path, cfg, character_state)
    if created:
        bump_world_revision(world_path)
    return {"status": "ok", "events_created": created}


# Builder steps that own an artifact a creator may have edited by hand.
_BUILDER_MANUAL_STEPS = ("skeleton", "cards", "characters", "events")
_CONCEPT_STEPS = ("skeleton", "cards", "characters", "events")


def _builder_meta(cfg: dict) -> dict:
    builder = cfg.get("builder")
    if not isinstance(builder, dict):
        builder = {}
    builder.setdefault("concept", cfg.get("narrative_scope_note", ""))
    builder.setdefault("scope_type", cfg.get("scope_selector", "arc-only"))
    manual = builder.get("manual_steps")
    builder["manual_steps"] = manual if isinstance(manual, list) else []
    stale = builder.get("stale_steps")
    builder["stale_steps"] = stale if isinstance(stale, list) else []
    return builder


@router.post("/worlds/{world_name}/builder/replan")
def builder_replan(world_name: str, req: dict = None):
    """Preview what a concept change would regenerate, without overwriting.

    Returns the plan only. Hand-edited steps are preserved; the new concept is
    stored as pending until the creator explicitly applies it.
    """
    world_path = require_world(world_name)
    cfg = read_world_file(world_path, "world_config.json")
    builder = _builder_meta(cfg)
    new_concept = str((req or {}).get("concept", "")).strip()
    if not new_concept:
        raise HTTPException(status_code=400, detail="concept is required")

    manual = set(builder.get("manual_steps", []))
    # A concept change invalidates the whole authored spine; steps a creator
    # edited by hand are reported as preserved and never regenerated silently.
    regenerate = [step for step in _CONCEPT_STEPS if step not in manual]
    preserved = [step for step in _CONCEPT_STEPS if step in manual]

    builder["concept_pending"] = new_concept
    cfg["builder"] = builder
    write_world_file(world_path, "world_config.json", cfg)

    return {
        "preview": True,
        "concept": {"from": builder.get("concept", ""), "to": new_concept},
        "regenerate_steps": regenerate,
        "preserved_steps": preserved,
        "requires_confirmation": True,
        "note": "Apply to move the draft back to the first step that needs regeneration. "
                "Preserved steps are skipped so manual edits are not overwritten.",
    }


@router.post("/worlds/{world_name}/builder/apply-replan")
def builder_apply_replan(world_name: str, req: dict = None):
    """Apply a pending concept change: reset only the stale, non-manual steps."""
    world_path = require_world(world_name)
    cfg = read_world_file(world_path, "world_config.json")
    builder = _builder_meta(cfg)
    pending = builder.get("concept_pending")
    if not pending:
        raise HTTPException(status_code=400, detail="No pending concept change to apply")

    manual = set(builder.get("manual_steps", []))
    regenerate = [step for step in _CONCEPT_STEPS if step not in manual]
    preserve = [step for step in _CONCEPT_STEPS if step in manual]

    builder["concept"] = pending
    builder["concept_pending"] = None
    builder["stale_steps"] = regenerate
    cfg["builder"] = builder
    cfg["narrative_scope_note"] = pending

    # Only move the build cursor back when the first authored step must be redone.
    if "skeleton" in regenerate:
        cfg["creation_status"] = "skeleton"
    write_world_file(world_path, "world_config.json", cfg)

    return {
        "applied": True,
        "regenerate_steps": regenerate,
        "preserved_steps": preserve,
        "creation_status": cfg.get("creation_status", "complete"),
    }


@router.post("/worlds/{world_name}/builder/confirm-checkpoints")
def confirm_checkpoints(world_name: str):
    world_path = require_world(world_name)
    cfg = read_world_file(world_path, "world_config.json")
    if cfg.get("creation_status") != "checkpoint_review":
        raise HTTPException(status_code=400, detail="Invalid status transition")
    canon = read_world_file(world_path, "canon_timeline.json")
    checkpoints = canon.get("checkpoints", [])
    if not checkpoints or len(checkpoints) == 0:
        raise HTTPException(status_code=400, detail="Cannot confirm empty checkpoints timeline")
    cfg["creation_status"] = "cards"
    write_world_file(world_path, "world_config.json", cfg)
    bump_world_revision(world_path)
    return {"status": "cards"}


@router.post("/worlds/{world_name}/builder/step")
def world_builder_step(world_name: str):
    world_path = require_world(world_name)

    if not has_real_api_key(world_name):
        raise HTTPException(
            status_code=503,
            detail="World Builder requires a real API key. Go to \u2699\ufe0f Settings to configure "
                   "OpenRouter API key before creating a world with AI."
        )

    cfg = read_world_file(world_path, "world_config.json")
    status = cfg.get("creation_status", "complete")

    if status == "complete":
        return {"status": "complete"}
    if status == "checkpoint_review":
        return {"status": "checkpoint_review", "message": "Waiting for checkpoint review confirmation"}
    if status not in ("skeleton", "cards", "characters"):
        raise HTTPException(
            status_code=400,
            detail=f"creation_status '{status}' is invalid or the world is already created. "
                   f"Only supports: skeleton, cards, characters."
        )

    # A concept replan must not overwrite a step the creator edited by hand:
    # skip it and advance the cursor.
    manual_steps = cfg.get("builder", {}).get("manual_steps", []) if isinstance(cfg.get("builder"), dict) else []
    if status in manual_steps:
        next_status = {"skeleton": "checkpoint_review", "cards": "characters",
                       "characters": "complete"}.get(status)
        if next_status == "complete":
            character_state = read_world_file(world_path, "character_state.json")
            _default_world_events(world_path, cfg, character_state)
        if next_status:
            cfg["creation_status"] = next_status
            write_world_file(world_path, "world_config.json", cfg)
            return {"status": next_status, "kept_manual": True}

    prompt = cfg.get("narrative_scope_note", "")
    scope = cfg.get("scope_selector", "arc-only")
    if scope not in ("one-shot", "arc-only", "full-story"):
        scope = "arc-only"
    model = get_effective_model(world_name)

    try:
        if status == "skeleton":
            sys_prompt = WORLD_BUILDER_SKELETON_PROMPT
            payload = f"User Request: {prompt}\nScope: {scope}"
            raw = call_llm(sys_prompt, payload, world_name=world_name)
            res = parse_llm_json(raw, expected_type=dict)

            res_cfg = res.get("world_config", {})
            if not isinstance(res_cfg, dict):
                res_cfg = {}

            new_cfg = {**TEMPLATES["world_config.json"], **cfg, **res_cfg}
            new_cfg["scope_selector"] = scope
            new_cfg["narrative_scope_note"] = prompt

            if "opening_mode" in cfg:
                new_cfg["opening_mode"] = cfg["opening_mode"]
            if "opening_text" in cfg:
                new_cfg["opening_text"] = cfg["opening_text"]
            if "interaction_mode" in cfg:
                new_cfg["interaction_mode"] = cfg["interaction_mode"]

            raw_checkpoints = res.get("checkpoints", [])
            if not isinstance(raw_checkpoints, list):
                raw_checkpoints = []

            raw_checkpoints = [cp for cp in raw_checkpoints if isinstance(cp, dict)]

            if not raw_checkpoints:
                raw_checkpoints = [make_checkpoint("cp_0", "Initial world state.")]

            if raw_checkpoints[0].get("checkpoint_id") != "cp_0":
                old_id = raw_checkpoints[0].get("checkpoint_id")
                raw_checkpoints[0]["checkpoint_id"] = "cp_0"
                if old_id:
                    for cp in raw_checkpoints:
                        if cp.get("default_next_checkpoint_id") == old_id:
                            cp["default_next_checkpoint_id"] = "cp_0"

            new_cfg["current_checkpoint_id"] = "cp_0"

            timeline = {"checkpoints": raw_checkpoints}
            write_world_file(world_path, "canon_timeline.json", timeline)

            new_cfg["creation_status"] = "checkpoint_review"
            write_world_file(world_path, "world_config.json", new_cfg)
            bump_world_revision(world_path)

            return {"status": "checkpoint_review"}

        elif status == "cards":
            sys_prompt = WORLD_BUILDER_CARDS_PROMPT
            try:
                checkpoints_data = read_world_file(world_path, "canon_timeline.json")
            except FileNotFoundError:
                checkpoints_data = dict(TEMPLATES["canon_timeline.json"])
            cps = checkpoints_data.get("checkpoints", [])
            valid_checkpoint_ids = {
                cp["checkpoint_id"]
                for cp in cps if isinstance(cp, dict) and "checkpoint_id" in cp
            }
            first_cp_id = "cp_0" if "cp_0" in valid_checkpoint_ids else (next(iter(valid_checkpoint_ids)) if valid_checkpoint_ids else "cp_0")

            payload = json.dumps({
                "world_config": cfg,
                "checkpoints": cps
            }, ensure_ascii=False)
            raw = call_llm(sys_prompt, payload, world_name=world_name)
            res = parse_llm_json(raw, expected_type=dict)

            generated_raw = res.get("cards", [])
            if not isinstance(generated_raw, list):
                generated_raw = []

            normalized_cards = []
            invalid_card_ids = []

            for i, c in enumerate(generated_raw):
                if not isinstance(c, dict):
                    continue
                c_id = str(c.get("id") or f"card_{i+1}")
                c_type = str(c.get("type") or "lore").lower().strip()
                if c_type in ("character", "person", "npc", "char"):
                    c_type = "char"
                else:
                    c_type = "lore"

                c_name = str(c.get("name") or "Unnamed Card")
                c_content = str(c.get("content") or "")

                unlock_cp = c.get("unlock_checkpoint_id")
                if not unlock_cp or (valid_checkpoint_ids and unlock_cp not in valid_checkpoint_ids):
                    invalid_card_ids.append(c_id)
                    unlock_cp = first_cp_id

                status_val = "unlocked" if unlock_cp == "cp_0" else "locked"

                card_obj = make_card(
                    card_id=c_id,
                    card_type=c_type,
                    name=c_name,
                    content=c_content,
                    unlock_checkpoint_id=unlock_cp,
                    status=status_val
                )
                if "keywords" in c and isinstance(c["keywords"], list):
                    card_obj["keywords"] = c["keywords"]
                if "is_pinned" in c:
                    card_obj["is_pinned"] = bool(c["is_pinned"])

                normalized_cards.append(card_obj)

            try:
                card_reg = read_world_file(world_path, "card_registry.json")
            except FileNotFoundError:
                card_reg = dict(TEMPLATES["card_registry.json"])
            card_reg["cards"] = normalized_cards
            write_world_file(world_path, "card_registry.json", card_reg)

            cfg["creation_status"] = "characters"
            write_world_file(world_path, "world_config.json", cfg)
            bump_world_revision(world_path)

            return {"status": "characters", "fixed_cards": invalid_card_ids if invalid_card_ids else None}

        elif status == "characters":
            sys_prompt = WORLD_BUILDER_CHARACTERS_PROMPT
            try:
                checkpoints_data = read_world_file(world_path, "canon_timeline.json")
            except FileNotFoundError:
                checkpoints_data = dict(TEMPLATES["canon_timeline.json"])
            try:
                card_reg = read_world_file(world_path, "card_registry.json")
            except FileNotFoundError:
                card_reg = dict(TEMPLATES["card_registry.json"])
            payload = json.dumps({
                "world_config": cfg,
                "checkpoints": checkpoints_data.get("checkpoints", []),
                "cards": card_reg.get("cards", [])
            }, ensure_ascii=False)
            raw = call_llm(sys_prompt, payload, world_name=world_name)
            res = parse_llm_json(raw, expected_type=dict)

            chars_raw = res.get("characters", {})
            if isinstance(chars_raw, list):
                new_dict = {}
                for i, item in enumerate(chars_raw):
                    if isinstance(item, dict):
                        cid = item.get("id") or item.get("char_id") or f"char_{i+1}"
                        new_dict[cid] = item
                chars_raw = new_dict

            if not isinstance(chars_raw, dict):
                chars_raw = {}

            normalized_chars = normalize_character_dict(chars_raw)

            current_protagonist = cfg.get("protagonist_id", "")
            if current_protagonist and current_protagonist not in normalized_chars:
                cfg["protagonist_id"] = next(iter(normalized_chars)) if normalized_chars else ""
            elif not current_protagonist and normalized_chars:
                cfg["protagonist_id"] = next(iter(normalized_chars))

            try:
                char_state = read_world_file(world_path, "character_state.json")
            except FileNotFoundError:
                char_state = dict(TEMPLATES["character_state.json"])
            char_state["characters"] = normalized_chars
            write_world_file(world_path, "character_state.json", char_state)

            try:
                checkpoints_data = read_world_file(world_path, "canon_timeline.json")
            except FileNotFoundError:
                checkpoints_data = dict(TEMPLATES["canon_timeline.json"])
            cps = checkpoints_data.get("checkpoints", [])
            sanitize_result = sanitize_required_conditions(cps, char_state["characters"])
            removed_any = [r for r in sanitize_result if r.get("removed")]
            if removed_any:
                for cp in cps:
                    for result in sanitize_result:
                        if result["checkpoint_id"] == cp.get("checkpoint_id") and result["removed"]:
                            existing = cp.get("required_conditions", [])
                            cp["required_conditions"] = [
                                c for c in existing
                                if not (isinstance(c, dict) and c.get("field", "") in result["removed"])
                            ]
                write_world_file(world_path, "canon_timeline.json", checkpoints_data)
                logger.warning(
                    "Sanitized required_conditions in world '%s': %s",
                    world_name,
                    json.dumps([r for r in sanitize_result if r.get("removed")], ensure_ascii=False)
                )

            cfg["checkpoint_boundary_mode"] = "advisory"
            cfg["creation_status"] = "complete"
            write_world_file(world_path, "world_config.json", cfg)
            bump_world_revision(world_path)

            # Generate location map after world creation is complete
            try:
                canon_timeline = read_world_file(world_path, "canon_timeline.json")
                location_map = generate_location_map(
                    world_config=cfg,
                    checkpoints=canon_timeline.get("checkpoints", []),
                    character_state=char_state.get("characters", {}),
                    world_name=world_name
                )
                if location_map and location_map.get("locations"):
                    write_world_file(world_path, "location_map.json", location_map)
            except Exception:
                logger.warning("Location map generation failed for world '%s', skipping", world_name)

            # Background events: derived from checkpoints/locations so the new
            # world has quests immediately. Idempotent across retries.
            events_created = 0
            try:
                events_created = _default_world_events(world_path, cfg, char_state)
            except Exception as e:
                logger.warning("Default world events generation failed for '%s': %s", world_name, e)

            # Checkpoint linter: validate generated bundle structure (deterministic, no LLM)
            try:
                lint_errors = validate_world_bundle(
                    cfg,
                    read_world_file(world_path, "canon_timeline.json"),
                    read_world_file(world_path, "location_map.json"),
                    character_state=char_state,
                    card_registry=read_world_file(world_path, "card_registry.json"),
                )
                if lint_errors:
                    logger.warning(
                        "World bundle lint errors for world '%s': %s",
                        world_name,
                        json.dumps(lint_errors, ensure_ascii=False),
                    )
            except Exception as e:
                lint_errors = [f"lint validation failed: {e}"]
                logger.warning("World bundle lint failed for world '%s': %s", world_name, e)

            # Checkpoint description linter: warn on forced confinement phrases
            try:
                checkpoints_data = read_world_file(world_path, "canon_timeline.json")
                checkpoints = checkpoints_data.get("checkpoints", [])
                forced_phrases = [
                    "không thể rời", "bị giam", "buộc phải ở lại", "lính gác chặn",
                    "cannot leave", "trapped", "forced to stay", "guards block"
                ]
                warnings = []
                for cp in checkpoints:
                    cp_id = cp.get("checkpoint_id", "")
                    desc = cp.get("description", "")
                    for phrase in forced_phrases:
                        if phrase.lower() in desc.lower():
                            warnings.append(f"Checkpoint '{cp_id}' description contains phrase '{phrase}'")
                            break
                if warnings:
                    logger.warning("Checkpoint linter warnings for world '%s': %s", world_name, ", ".join(warnings))
            except Exception:
                pass

            return {
                "status": "complete",
                "sanitized_conditions": sanitize_result if removed_any else None,
                "lint_errors": lint_errors if lint_errors else None,
                "events_created": events_created,
            }

    except RateLimitError as e:
        headers = {"Retry-After": str(int(e.retry_after))} if e.retry_after else None
        raise HTTPException(status_code=429, detail=str(e), headers=headers)
    except LLMCallError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worlds/{world_name}/extend_arc")
def extend_arc(world_name: str):
    world_path = require_world(world_name)

    if not has_real_api_key(world_name):
        raise HTTPException(
            status_code=503,
            detail="Arc Extender requires a real API key. Please configure OpenRouter API key in Settings."
        )

    cfg = read_world_file(world_path, "world_config.json")
    if not cfg.get("arc_roadmap"):
        raise HTTPException(status_code=400, detail="This world does not have a multi-arc roadmap.")

    roadmap = cfg.get("arc_roadmap", {})
    canon = read_world_file(world_path, "canon_timeline.json")
    char_state = read_world_file(world_path, "character_state.json")
    chapters_data = read_world_file(world_path, "chapters.json")

    running_summary = chapters_data.get("running_summary", "")
    story_thesis = cfg.get("story_thesis", "")

    sys_prompt = ARC_EXTENDER_PROMPT
    payload = json.dumps({
        "story_thesis": story_thesis,
        "arc_roadmap": roadmap,
        "running_summary": running_summary,
        "character_state": char_state.get("characters", {})
    }, ensure_ascii=False)

    try:
        raw = call_llm(sys_prompt, payload, world_name=world_name)
        res = parse_llm_json(raw, expected_type=dict)

        new_checkpoints_raw = res.get("checkpoints", [])
        if not new_checkpoints_raw or not isinstance(new_checkpoints_raw, list):
            raise ValueError("No checkpoints generated for next Arc")

        current_cps = canon.get("checkpoints", [])
        existing_ids = {cp["checkpoint_id"] for cp in current_cps if isinstance(cp, dict) and "checkpoint_id" in cp}

        normalized_new_cps = []
        for cp in new_checkpoints_raw:
            if not isinstance(cp, dict):
                continue
            cp_id = cp.get("checkpoint_id")
            if not cp_id or cp_id in existing_ids:
                cp_id = f"cp_ext_{len(current_cps) + len(normalized_new_cps) + 1}"
            existing_ids.add(cp_id)

            norm_cp = make_checkpoint(
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
                norm_cp["status_effects"] = cp["status_effects"]
            if "alternate_outcomes" in cp and isinstance(cp["alternate_outcomes"], list):
                norm_cp["alternate_outcomes"] = cp["alternate_outcomes"]
            if "default_next_checkpoint_id" in cp:
                norm_cp["default_next_checkpoint_id"] = cp["default_next_checkpoint_id"]

            normalized_new_cps.append(norm_cp)

        if not normalized_new_cps:
            raise ValueError("No valid checkpoints generated for next Arc")

        current_cps.extend(normalized_new_cps)
        canon["checkpoints"] = current_cps
        write_world_file(world_path, "canon_timeline.json", canon)
        bump_world_revision(world_path)

        lint_errors = []
        try:
            lint_errors = validate_world_bundle(
                cfg,
                canon,
                read_world_file(world_path, "location_map.json"),
                character_state=char_state,
                card_registry=read_world_file(world_path, "card_registry.json"),
            )
            if lint_errors:
                logger.warning(
                    "World bundle lint errors after extend_arc for world '%s': %s",
                    world_name,
                    json.dumps(lint_errors, ensure_ascii=False),
                )
        except Exception as e:
            lint_errors = [f"lint validation failed: {e}"]
            logger.warning("World bundle lint failed after extend_arc for world '%s': %s", world_name, e)

        return {
            "status": "success",
            "new_checkpoints": len(normalized_new_cps),
            "lint_errors": lint_errors if lint_errors else None,
        }
    except RateLimitError as e:
        headers = {"Retry-After": str(int(e.retry_after))} if e.retry_after else None
        raise HTTPException(status_code=429, detail=str(e), headers=headers)
    except LLMCallError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
