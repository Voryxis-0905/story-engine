from fastapi import APIRouter, HTTPException
import json
import os

from app.storage import (
    require_world, world_path_of, read_world_file, write_world_file,
    has_real_api_key
)
from app.engine import (
    TEMPLATES, DEFAULT_STORY_CLOCK, find_checkpoint, _generate_chapter,
    _generate_prelude, build_opening_instruction, get_open_chapter_state,
    call_llm, parse_llm_json,
    LINTER_SYSTEM_PROMPT, REWRITE_SYSTEM_PROMPT, get_world_style_card,
    LLMCallError
)
from app.models import (
    ChapterContinueRequest, ChapterStartRequest, LintChapterRequest,
    RewriteChapterRequest
)

try:
    from prompts import LINTER_SYSTEM_PROMPT as _LSP
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.skill_limiter import check_skill_limiter

router = APIRouter()


@router.post("/worlds/{world_name}/chapter/continue")
def chapter_continue(world_name: str, req: ChapterContinueRequest):
    return _generate_chapter(world_name, narrator_input=req.user_input)


@router.post("/worlds/{world_name}/chapter/start")
def chapter_start(world_name: str, req: ChapterStartRequest):
    world_path = world_path_of(world_name)
    if not os.path.isdir(world_path):
        raise HTTPException(status_code=404, detail="World not found")

    chapters_data = read_world_file(world_path, "chapters.json")
    non_prelude_chapters = [c for c in chapters_data["chapters"] if c.get("chapter_index") != 0]
    if non_prelude_chapters:
        raise HTTPException(
            status_code=400,
            detail="This world already has chapters -- /chapter/start is only for the first chapter, "
                   "use /chapter/continue to write further."
        )

    world_config = read_world_file(world_path, "world_config.json")
    if world_config.get("prelude_enabled") and not world_config.get("prelude_confirmed"):
        raise HTTPException(
            status_code=400,
            detail="This world has prelude_enabled=True but the prelude has not been generated and confirmed yet. "
                   "Use /chapter/generate-prelude first, then /chapter/confirm-prelude before starting Chapter 1."
        )
    effective_mode = req.opening_mode or world_config.get("opening_mode", "ai_generate")
    if effective_mode not in ("ai_generate", "user_defined"):
        raise HTTPException(
            status_code=400,
            detail=f"opening_mode '{effective_mode}' is invalid (only accepts 'ai_generate' or 'user_defined')."
        )

    if effective_mode == "user_defined":
        opening_text = (req.opening_text or world_config.get("opening_text", "")).strip()
        if not opening_text:
            raise HTTPException(
                status_code=400,
                detail="opening_mode is 'user_defined' but ch\u01b0a c\u00f3 opening_text "
                       "(g\u1eedi k\u00e8m in request either set s\u1eb5n in world_config)."
            )
        chapter_record = {
            "chapter_index": 1,
            "turn_index": 1,
            "chapter_closed": True,
            "chapter_title": None,
            "checkpoint_id": world_config.get("current_checkpoint_id", ""),
            "user_input": "",
            "chapter_text": opening_text,
            "notes": "Opening chapter written by user (opening_mode: user_defined), "
                     "bypassed narrator/consistency checker.",
            "boundary_correction": None,
            "consistency_check": {
                "severity": "none",
                "issues": [],
                "explanation": "Skipped check because this content is user-written, bypassed narrator.",
                "triggered_rewrite": False
            }
        }
        chapters_data["chapters"] = [chapter_record]
        write_world_file(world_path, "chapters.json", chapters_data)
        return {
            "chapter": chapter_record,
            "state_changes_applied": {"characters": {}, "notes": ""},
            "used_mock_llm": False,
            "checkpoint_advanced": False,
            "lore_rag_filter": None
        }

    canon_timeline = read_world_file(world_path, "canon_timeline.json")
    current_checkpoint_id = world_config.get("current_checkpoint_id", "")
    checkpoint = find_checkpoint(canon_timeline["checkpoints"], current_checkpoint_id)
    if checkpoint is None:
        raise HTTPException(
            status_code=400,
            detail=f"current_checkpoint_id '{current_checkpoint_id}' khong khop checkpoint nao "
                   f"in canon_timeline (world co the la data cu, chua co field nay -- "
                   f"chay lai seed-demo hoac set thu cong)."
        )
    synthetic_instruction = build_opening_instruction(checkpoint)
    return _generate_chapter(world_name, narrator_input=synthetic_instruction, display_input="")


@router.post("/worlds/{world_name}/chapter/generate-prelude")
def chapter_generate_prelude(world_name: str):
    world_path = world_path_of(world_name)
    if not os.path.isdir(world_path):
        raise HTTPException(status_code=404, detail="World not found")
    chapters_data = read_world_file(world_path, "chapters.json")
    existing_prelude = [c for c in chapters_data.get("chapters", []) if c.get("chapter_index") == 0]
    if existing_prelude:
        raise HTTPException(
            status_code=400,
            detail="A prelude already exists for this world. Use /chapter/regenerate-prelude to replace it."
        )
    try:
        result = _generate_prelude(world_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worlds/{world_name}/chapter/regenerate-prelude")
def chapter_regenerate_prelude(world_name: str):
    world_path = world_path_of(world_name)
    if not os.path.isdir(world_path):
        raise HTTPException(status_code=404, detail="World not found")
    chapters_data = read_world_file(world_path, "chapters.json")
    chapters = chapters_data.get("chapters", [])
    chapters[:] = [c for c in chapters if c.get("chapter_index") != 0]
    write_world_file(world_path, "chapters.json", chapters_data)
    try:
        result = _generate_prelude(world_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worlds/{world_name}/chapter/confirm-prelude")
def chapter_confirm_prelude(world_name: str):
    world_path = world_path_of(world_name)
    if not os.path.isdir(world_path):
        raise HTTPException(status_code=404, detail="World not found")
    chapters_data = read_world_file(world_path, "chapters.json")
    prelude_exists = any(c.get("chapter_index") == 0 for c in chapters_data.get("chapters", []))
    if not prelude_exists:
        raise HTTPException(status_code=400, detail="No prelude exists to confirm. Generate one first.")
    world_config = read_world_file(world_path, "world_config.json")
    
    # Idempotent Guard: if already confirmed, do not advance checkpoint again
    if world_config.get("prelude_confirmed"):
        return {"status": "prelude_confirmed"}

    world_config["prelude_confirmed"] = True

    prelude_enabled = world_config.get("prelude_enabled", False)
    if prelude_enabled:
        canon_timeline = read_world_file(world_path, "canon_timeline.json")
        checkpoints = canon_timeline.get("checkpoints", [])
        first_cp_id = checkpoints[0]["checkpoint_id"] if checkpoints else "cp_0"
        current_id = world_config.get("current_checkpoint_id", "")
        
        # Strict Anchor: Only transition checkpoint if currently at the initial prelude checkpoint (cp_0)
        if current_id == first_cp_id:
            current_cp = find_checkpoint(checkpoints, current_id)
            if current_cp:
                next_id = current_cp.get("default_next_checkpoint_id")
                if not next_id and len(checkpoints) > 1:
                    next_id = checkpoints[1]["checkpoint_id"]
                if next_id:
                    completed = world_config.setdefault("completed_checkpoints", [])
                    if current_id and current_id not in completed:
                        completed.append(current_id)
                    world_config["current_checkpoint_id"] = next_id

                    # Unlock cards for the new checkpoint
                    card_registry = read_world_file(world_path, "card_registry.json")
                    next_cp = find_checkpoint(checkpoints, next_id)
                    if card_registry and isinstance(card_registry.get("cards"), list):
                        card_updated = False
                        for card in card_registry["cards"]:
                            if next_cp and (card.get("id") in next_cp.get("cards_unlocked", []) or card.get("unlock_checkpoint_id") == next_id):
                                if card.get("status") != "unlocked":
                                    card["status"] = "unlocked"
                                    card_updated = True
                        if card_updated:
                            write_world_file(world_path, "card_registry.json", card_registry)

    write_world_file(world_path, "world_config.json", world_config)
    return {"status": "prelude_confirmed"}


@router.post("/worlds/{world_name}/chapter/regenerate")
def chapter_regenerate(world_name: str):
    world_path = require_world(world_name)
    chapters_data = read_world_file(world_path, "chapters.json")
    turns = chapters_data.get("chapters", [])

    if not turns:
        raise HTTPException(
            status_code=400,
            detail="Khong co turn nao de regenerate. World chua co chapter nao."
        )

    last_turn = turns[-1]
    original_input = last_turn.get("user_input", "")

    if last_turn.get("chapter_closed"):
        closed_chapter_idx = last_turn.get("chapter_index", 0)
        turns_before = [t for t in turns if t.get("chapter_index", 0) < closed_chapter_idx]
        chapters_data["chapters"] = turns_before
        if turns_before:
            pass
        else:
            chapters_data["running_summary"] = ""
            chapters_data["memorable_beats"] = []
    else:
        chapters_data["chapters"] = turns[:-1]

    write_world_file(world_path, "chapters.json", chapters_data)

    return _generate_chapter(world_name, narrator_input=original_input, display_input=original_input)


@router.get("/worlds/{world_name}/chapters")
def get_chapters(world_name: str):
    """Get all chapters for a world, including prelude."""
    world_path = require_world(world_name)
    chapters_data = read_world_file(world_path, "chapters.json")
    return chapters_data.get("chapters", [])


@router.get("/worlds/{world_name}/play-state")
def get_play_state(world_name: str):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    character_state = read_world_file(world_path, "character_state.json")
    card_registry = read_world_file(world_path, "card_registry.json")
    canon_timeline = read_world_file(world_path, "canon_timeline.json")

    protagonist_id = world_config.get("protagonist_id", "")
    current_cp_id = world_config.get("current_checkpoint_id", "")
    completed = world_config.get("completed_checkpoints", [])
    checkpoints = canon_timeline.get("checkpoints", [])

    story_clock = world_config.get("story_clock")
    if not isinstance(story_clock, dict):
        story_clock = dict(DEFAULT_STORY_CLOCK)
    foreshadowing_tracker = world_config.get("foreshadowing_tracker")
    if foreshadowing_tracker is None:
        foreshadowing_tracker = world_config.get("foreshadowings", [])

    protagonist_data = None
    if protagonist_id and protagonist_id in character_state.get("characters", {}):
        p = character_state["characters"][protagonist_id]
        protagonist_data = {
            "id": protagonist_id,
            "name": p.get("name", protagonist_id),
            "location": p.get("location", ""),
            "power_stat": p.get("power_stat", {}),
            "traits": p.get("traits", {}),
            "knowledge_flags": p.get("knowledge_flags", []),
            "alive": p.get("alive", True),
            "relationships": p.get("relationships", {}),
            "age": p.get("age", "")
        }

    total_checkpoints = len(checkpoints)
    current_index = 0
    for i, cp in enumerate(checkpoints):
        if cp["checkpoint_id"] == current_cp_id:
            current_index = i
            break
    arc_progress = {
        "current_checkpoint_id": current_cp_id,
        "current_index": current_index,
        "total_checkpoints": total_checkpoints,
        "completed": completed
    }

    unlocked_cards = []
    for card in card_registry.get("cards", []):
        if card.get("status") == "unlocked":
            card_info = {
                "id": card.get("id", ""),
                "type": card.get("type", ""),
                "name": card.get("name", ""),
                "content": card.get("content", "")
            }
            if card.get("type") == "char":
                char_key = card.get("id", "")
                if char_key in character_state.get("characters", {}):
                    char = character_state["characters"][char_key]
                    card_info["affinity"] = char.get("affinity", {})
                    card_info["relationships"] = char.get("relationships", {})
                    card_info["age"] = char.get("age", "")
                    card_info["power_stat"] = char.get("power_stat", {})
            unlocked_cards.append(card_info)

    return {
        "protagonist": protagonist_data,
        "arc_progress": arc_progress,
        "arc_roadmap": world_config.get("arc_roadmap", {}),
        "unlocked_cards": unlocked_cards,
        "story_clock": story_clock,
        "foreshadowing_tracker": foreshadowing_tracker,
        "foreshadowings": foreshadowing_tracker,
        "style_card": get_world_style_card(world_name)
    }


@router.post("/worlds/{world_name}/lint-chapter")
def lint_chapter(world_name: str, req: LintChapterRequest):
    world_path = require_world(world_name)
    chapters_data = read_world_file(world_path, "chapters.json")
    world_config = read_world_file(world_path, "world_config.json")
    character_state = read_world_file(world_path, "character_state.json")

    chapter_turns = sorted(
        (c for c in chapters_data.get("chapters", []) if c["chapter_index"] == req.chapter_index),
        key=lambda c: c["turn_index"]
    )
    if not chapter_turns:
        raise HTTPException(status_code=404, detail="Chapter not found")

    full_chapter_text = "\n\n".join(c.get("chapter_text", "") for c in chapter_turns)

    relationships = {}
    for char_id, state in character_state.get("characters", {}).items():
        if state.get("relationships"):
            relationships[char_id] = state["relationships"]

    payload = {
        "chapter_text": full_chapter_text,
        "running_summary": chapters_data.get("running_summary", ""),
        "story_clock": world_config.get("story_clock", {}),
        "foreshadowing_tracker": world_config.get("foreshadowing_tracker", []),
        "relationships": relationships
    }

    try:
        raw = call_llm(
            LINTER_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            world_name=world_name
        )
        parsed = parse_llm_json(raw)
        return parsed
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worlds/{world_name}/chapter/rewrite")
def rewrite_chapter(world_name: str, req: RewriteChapterRequest):
    world_path = require_world(world_name)
    chapters_data = read_world_file(world_path, "chapters.json")

    chapter_turns = sorted(
        (c for c in chapters_data.get("chapters", []) if c["chapter_index"] == req.chapter_index),
        key=lambda c: c["turn_index"]
    )
    if not chapter_turns:
        raise HTTPException(status_code=404, detail="Chapter not found")

    full_chapter_text = "\n\n".join(c.get("chapter_text", "") for c in chapter_turns)

    payload = {
        "original_text": full_chapter_text,
        "linter_suggestions": req.linter_suggestions
    }

    try:
        raw = call_llm(
            REWRITE_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            world_name=world_name
        )
        parsed = parse_llm_json(raw)
        rewritten_text = parsed.get("rewritten_text", full_chapter_text)

        first_turn_index = chapter_turns[0]["turn_index"]
        chapters_data["chapters"] = [
            t for t in chapters_data["chapters"]
            if not (t["chapter_index"] == req.chapter_index and t["turn_index"] != first_turn_index)
        ]

        for t in chapters_data["chapters"]:
            if t["chapter_index"] == req.chapter_index and t["turn_index"] == first_turn_index:
                t["chapter_text"] = rewritten_text

        write_world_file(world_path, "chapters.json", chapters_data)
        return {"message": "success", "rewritten_text": rewritten_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/worlds/{world_name}/chapter/endgame-status")
def get_endgame_status(world_name: str):
    from app.storage import read_world_file, require_world
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    lifecycle = world_config.get("lifecycle_status", "active")
    story_mode = world_config.get("story_mode", "endless")
    target = world_config.get("target_ending_scenario")
    return {
        "story_mode": story_mode,
        "lifecycle_status": lifecycle,
        "endgame_ready": lifecycle == "endgame_pending" and story_mode == "fixed_ending",
        "target_ending_summary": target.get("summary") if target else None,
        "is_fallback": target.get("used_fallback", False) if target else False,
        "lifecycle_status_completed": lifecycle == "completed",
    }


@router.post("/worlds/{world_name}/chapter/generate-epilogue-choices")
def generate_epilogue_choices(world_name: str):
    from app.engine import call_llm, parse_llm_json
    from app.prompts import EPILOGUE_CHOICES_PROMPT
    from app.storage import read_world_file, require_world, write_world_file
    import json

    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")

    if world_config.get("story_mode") != "fixed_ending":
        raise HTTPException(status_code=400, detail="Epilogue only available for fixed_ending worlds")

    if world_config.get("lifecycle_status") != "endgame_pending":
        raise HTTPException(status_code=400, detail="Endgame not ready yet")

    target = world_config.get("target_ending_scenario")
    if not target:
        raise HTTPException(status_code=400, detail="No target ending scenario configured")

    character_state = read_world_file(world_path, "character_state.json")
    chapters_data = read_world_file(world_path, "chapters.json")
    running_summary = chapters_data.get("running_summary", "")
    relationships = character_state.get("characters", {})

    is_fallback = target.get("used_fallback", False)
    payload = {
        "ending_summary": target.get("summary", ""),
        "fallback_summary": target.get("fallback_summary", "A fateful conclusion to the story."),
        "relationships": relationships,
        "is_fallback": is_fallback,
    }

    try:
        raw = call_llm(
            EPILOGUE_CHOICES_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            world_name=world_name
        )
        parsed = parse_llm_json(raw)
        choices = parsed.get("choices", [])
        if not choices or not isinstance(choices, list):
            choices = ["Accept the ending as it comes.", "Fight against fate.", "Seek a new path."]
        return {"choices": choices}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/worlds/{world_name}/chapter/generate-epilogue")
def generate_epilogue(world_name: str, req: dict):
    from app.engine import call_llm, parse_llm_json
    from app.prompts import EPILOGUE_GENERATOR_PROMPT
    from app.storage import read_world_file, require_world, write_world_file
    import json

    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    target = world_config.get("target_ending_scenario")
    if not target:
        raise HTTPException(status_code=400, detail="No target ending scenario")

    chosen_choice = req.get("chosen_choice", "")
    if not chosen_choice:
        raise HTTPException(status_code=400, detail="Missing chosen_choice")

    character_state = read_world_file(world_path, "character_state.json")
    chapters_data = read_world_file(world_path, "chapters.json")
    running_summary = chapters_data.get("running_summary", "")
    relationships = character_state.get("characters", {})
    output_length = world_config.get("output_length", "Standard")

    is_fallback = target.get("used_fallback", False)
    payload = {
        "chosen_choice": chosen_choice,
        "ending_summary": target.get("summary", ""),
        "fallback_summary": target.get("fallback_summary", "A fateful conclusion."),
        "is_fallback": is_fallback,
        "relationships": relationships,
        "running_summary": running_summary,
        "output_length": output_length,
    }

    try:
        raw = call_llm(
            EPILOGUE_GENERATOR_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            world_name=world_name
        )
        parsed = parse_llm_json(raw)
        epilogue = parsed.get("epilogue", "The story comes to a close...")

        # Mark world as completed
        world_config["lifecycle_status"] = "completed"
        write_world_file(world_path, "world_config.json", world_config)

        return {"epilogue": epilogue, "lifecycle_status": "completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
