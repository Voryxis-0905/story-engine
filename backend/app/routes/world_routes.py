from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Optional, Any, List
import os
import json
import re
import time
import shutil

from app.storage import (
    WORLDS_DIR, RUNTIME_CONFIG_PATH, DEFAULT_OPENROUTER_MODEL, _VALID_ROLES,
    read_runtime_config, write_runtime_config, read_world_runtime_override,
    write_world_runtime_override, build_runtime_config_status,
    _sanitize_and_preserve_fallback_chain, require_world, world_path_of,
    read_world_file, write_world_file, get_effective_api_key, has_real_api_key,
    read_saves_index, write_saves_index, snapshot_world_state, build_save_entry,
    new_save_id, now_str, get_world_style_card, write_world_style_card,
    _validate_world_name
)
from app.engine import (
    TEMPLATES, DEFAULT_STORY_CLOCK, find_checkpoint, make_card, make_checkpoint,
    make_character, _generate_chapter, call_llm, parse_llm_json,
    CONSISTENCY_CHECKER_SYSTEM_PROMPT, SUMMARIZER_SYSTEM_PROMPT,
    WORLD_BUILDER_INTERVIEW_PROMPT, CREATOR_ASSISTANT_PROMPT,
    LINTER_SYSTEM_PROMPT, REWRITE_SYSTEM_PROMPT, test_llm_connection,
    mock_narrator_response, mock_consistency_checker_response,
    LLMCallError, RateLimitError, _validate_imported_package,
    build_opening_instruction, get_open_chapter_state, decide_chapter_closed,
    get_recent_turns_for_context, update_running_summary,
    advance_checkpoint_if_ready, get_active_cards,
    build_rag_context_text, DEFAULT_LORE_RAG_MAX_TOKENS,
    select_relevant_lore_cards, check_boundary_violations,
    build_boundary_correction_note, raise_boundary_hard_reject,
    detect_story_language, run_consistency_checker, build_consistency_correction_note,
    apply_state_changes, call_narrator_and_parse, generate_location_map,
    _get_location_unlock_requirements
)
from app.models import (
    WorldConfigUpdate, WorldCreationRequest, InterviewRequest,
    InterviewRespondRequest, ImportWorldRequest, CreatorAssistantRequest,
    StyleCardModel, LintChapterRequest, RewriteChapterRequest,
    RuntimeConfigUpdate, CardRegistryUpdate, CanonTimelineUpdate,
    CharacterStateUpdate, ForceAdvanceRequest, CreateSaveRequest,
    BranchRequest, ChapterContinueRequest, ChapterStartRequest,
    ForeshadowingsUpdateReq, ForkRequest, RegenerateRequest,
    TraitDefinition, CardModel, CheckpointBoundaryModel, CheckpointModel,
    CharacterModel, PowerStatModel
)

try:
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.skill_limiter import check_skill_limiter

router = APIRouter()


@router.get("/runtime-config")
def get_runtime_config():
    return build_runtime_config_status()


@router.put("/runtime-config")
def update_runtime_config(req: RuntimeConfigUpdate):
    cfg = read_runtime_config()
    api_key_val = req.api_key if req.api_key is not None else req.openrouter_api_key
    if api_key_val is not None:
        cfg["openrouter_api_key"] = api_key_val.strip()
        cfg["api_key"] = api_key_val.strip()
    
    model_val = req.model_name if req.model_name is not None else req.openrouter_model
    if model_val is not None:
        cfg["openrouter_model"] = model_val.strip()
        cfg["model_name"] = model_val.strip()

    if req.llm_provider is not None:
        cfg["llm_provider"] = req.llm_provider.strip()

    if req.base_url is not None:
        cfg["base_url"] = req.base_url.strip()

    if req.temperature is not None:
        cfg["temperature"] = req.temperature
    # Keep fallback_chain in sync with top-level key/model/provider
    eff_key = cfg.get("api_key") or cfg.get("openrouter_api_key") or ""
    eff_model = cfg.get("model_name") or cfg.get("openrouter_model") or ""
    eff_provider = cfg.get("llm_provider", "openrouter")
    eff_base_url = cfg.get("base_url", "")

    if req.fallback_chain is not None:
        cfg["fallback_chain"] = _sanitize_and_preserve_fallback_chain(req.fallback_chain, cfg.get("fallback_chain", []))
    elif eff_key:
        cfg["fallback_chain"] = [{
            "provider": eff_provider,
            "model": eff_model,
            "api_key": eff_key,
            "base_url": eff_base_url
        }]
    if req.creator_mode_enabled is not None:
        cfg["creator_mode_enabled"] = req.creator_mode_enabled
    if req.role_assignments is not None:
        invalid_keys = [k for k in req.role_assignments if k not in _VALID_ROLES]
        if invalid_keys:
            raise HTTPException(status_code=400, detail=f"role_assignments chi nhan key: planner, writer, extractor, editor, checker, summarizer. Key khong hop le: {invalid_keys}")
        invalid_vals = [k for k, v in req.role_assignments.items() if v is not None and (not isinstance(v, int) or v < 0)]
        if invalid_vals:
            raise HTTPException(status_code=400, detail=f"role_assignments value phai la null hoac int >= 0. Key loi: {invalid_vals}")
        existing_ra = cfg.get("role_assignments", {"planner": None, "writer": None, "extractor": None, "editor": None, "checker": None, "summarizer": None})
        existing_ra.update(req.role_assignments)
        cfg["role_assignments"] = existing_ra
    if req.editor_enabled is not None:
        cfg["editor_enabled"] = req.editor_enabled
    if req.enable_extractor_cross_check is not None:
        cfg["enable_extractor_cross_check"] = req.enable_extractor_cross_check
    write_runtime_config(cfg)
    return build_runtime_config_status()


@router.delete("/runtime-config/api-key")
def clear_runtime_api_key():
    cfg = read_runtime_config()
    cfg["openrouter_api_key"] = ""
    cfg["fallback_chain"] = []
    write_runtime_config(cfg)
    return build_runtime_config_status()


@router.post("/runtime-config/test-connection")
@router.post("/test-llm-connection")
def runtime_config_test_connection(node_index: int = 0):
    return test_llm_connection(node_index=node_index)


@router.get("/worlds/{world_name}/runtime-config")
def get_world_runtime_config(world_name: str):
    require_world(world_name)
    return build_runtime_config_status(world_name)


@router.put("/worlds/{world_name}/runtime-config")
def update_world_runtime_config(world_name: str, req: RuntimeConfigUpdate):
    require_world(world_name)
    cfg = read_world_runtime_override(world_name)
    if req.openrouter_api_key is not None:
        cfg["openrouter_api_key"] = req.openrouter_api_key.strip()
    if req.openrouter_model is not None:
        cfg["openrouter_model"] = req.openrouter_model.strip()
    if req.fallback_chain is not None:
        cfg["fallback_chain"] = _sanitize_and_preserve_fallback_chain(req.fallback_chain, cfg.get("fallback_chain", []))
    if req.role_assignments is not None:
        invalid_keys = [k for k in req.role_assignments if k not in _VALID_ROLES]
        if invalid_keys:
            raise HTTPException(status_code=400, detail=f"role_assignments chi nhan key: planner, writer, extractor, editor, checker, summarizer. Key khong hop le: {invalid_keys}")
        invalid_vals = [k for k, v in req.role_assignments.items() if v is not None and (not isinstance(v, int) or v < 0)]
        if invalid_vals:
            raise HTTPException(status_code=400, detail=f"role_assignments value phai la null hoac int >= 0. Key loi: {invalid_vals}")
        existing_ra = cfg.get("role_assignments", {"planner": None, "writer": None, "extractor": None, "editor": None, "checker": None, "summarizer": None})
        existing_ra.update(req.role_assignments)
        cfg["role_assignments"] = existing_ra
    if req.editor_enabled is not None:
        cfg["editor_enabled"] = req.editor_enabled
    if req.enable_extractor_cross_check is not None:
        cfg["enable_extractor_cross_check"] = req.enable_extractor_cross_check
    write_world_runtime_override(world_name, cfg)
    return build_runtime_config_status(world_name)


@router.delete("/worlds/{world_name}/runtime-config/api-key")
def clear_world_runtime_api_key(world_name: str):
    require_world(world_name)
    cfg = read_world_runtime_override(world_name)
    cfg["openrouter_api_key"] = ""
    cfg["fallback_chain"] = []
    write_world_runtime_override(world_name, cfg)
    return build_runtime_config_status(world_name)


@router.post("/worlds/{world_name}/runtime-config/test-connection")
def world_runtime_config_test_connection(world_name: str, node_index: int = 0):
    require_world(world_name)
    return test_llm_connection(world_name, node_index=node_index)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/worlds")
def list_worlds():
    if not os.path.isdir(WORLDS_DIR):
        return {"worlds": []}
    result = []
    for name in sorted(os.listdir(WORLDS_DIR)):
        world_path = world_path_of(name)
        if not os.path.isdir(world_path):
            continue
        try:
            cfg = read_world_file(world_path, "world_config.json")
            status = cfg.get("creation_status", "complete")
        except (FileNotFoundError, json.JSONDecodeError):
            status = "complete"
        result.append({"name": name, "status": status})
    return {"worlds": result}


@router.put("/worlds/{world_name}/world_config")
def update_world_config(world_name: str, req: WorldConfigUpdate):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    updates = req.dict(exclude_unset=True)
    if updates.get("lore_rag_max_tokens") is not None and updates["lore_rag_max_tokens"] < 0:
        raise HTTPException(
            status_code=400,
            detail="lore_rag_max_tokens must be >= 0 (0 = unlimited, empty = system default)."
        )
    if updates.get("opening_mode") is not None and updates["opening_mode"] not in ("ai_generate", "user_defined"):
        raise HTTPException(
            status_code=400,
            detail=f"opening_mode '{updates['opening_mode']}' not h\u1ee3p l\u1ec7 "
                   f"(only nh\u1eadn 'ai_generate' either 'user_defined')."
        )
    if updates.get("protagonist_id"):
        char_state = read_world_file(world_path, "character_state.json")
        if updates["protagonist_id"] not in char_state.get("characters", {}):
            raise HTTPException(
                status_code=400,
                detail=f"protagonist_id '{updates['protagonist_id']}' not t\u1ed3n t\u1ea1i in character_state. "
                       f"T\u1ea1o nh\u00e2n v\u1eadt tr\u01b0\u1edbc in tab Characters then quay l\u1ea1i \u0111\u00e2y."
            )
    world_config.update(updates)
    write_world_file(world_path, "world_config.json", world_config)
    return {"message": "world_config updated", "world_config": world_config}


@router.get("/worlds/{world_name}")
def get_world(world_name: str):
    world_path = require_world(world_name)
    result = {}
    for filename in TEMPLATES.keys():
        file_path = os.path.join(world_path, filename)
        key = filename.replace(".json", "")
        if os.path.exists(file_path):
            result[key] = read_world_file(world_path, filename)
    result["saves"] = list(reversed(read_saves_index(world_path)))
    return result


@router.delete("/worlds/{world_name}")
def delete_world(world_name: str):
    world_path = require_world(world_name)
    shutil.rmtree(world_path)
    return {"message": "World deleted", "world_name": world_name}


@router.post("/worlds/import")
def import_world(req: ImportWorldRequest):
    pkg = req.package_data
    full_cfg, card_reg, timeline, char_state = _validate_imported_package(pkg, TEMPLATES)

    raw_name = req.world_name or full_cfg.get("display_name") or "imported_world"
    target_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_name).strip('_') or "imported_world"

    world_path = world_path_of(target_name)
    if os.path.exists(world_path):
        target_name = f"{target_name}_{int(time.time())}"
        world_path = world_path_of(target_name)

    os.makedirs(world_path)
    write_world_file(world_path, "world_config.json", full_cfg)
    write_world_file(world_path, "card_registry.json", card_reg)
    write_world_file(world_path, "canon_timeline.json", timeline)
    write_world_file(world_path, "character_state.json", char_state)

    chapters_data = pkg.get("chapters")
    if not chapters_data or not isinstance(chapters_data, dict):
        chapters_data = {"chapters": [], "running_summary": "", "memorable_beats": []}
    elif "memorable_beats" not in chapters_data:
        chapters_data["memorable_beats"] = []
    write_world_file(world_path, "chapters.json", chapters_data)

    if "runtime_override" in pkg and isinstance(pkg["runtime_override"], dict):
        write_world_runtime_override(target_name, pkg["runtime_override"])

    if "style_card" in pkg and isinstance(pkg["style_card"], dict):
        write_world_style_card(target_name, pkg["style_card"])

    return {"message": "World imported successfully", "world_name": target_name}


@router.post("/worlds/{world_name}")
def create_world(world_name: str, req: WorldCreationRequest = None):
    _validate_world_name(world_name)
    world_path = world_path_of(world_name)
    if os.path.exists(world_path):
        raise HTTPException(status_code=400, detail="World already exists")
    os.makedirs(world_path)
    for filename, template in TEMPLATES.items():
        write_world_file(world_path, filename, template)

    cfg = read_world_file(world_path, "world_config.json")
    if req:
        if req.interaction_mode:
            cfg["interaction_mode"] = req.interaction_mode
        if req.prompt or req.scope_type:
            cfg["creation_status"] = "skeleton"
            cfg["scope_selector"] = req.scope_type
            cfg["narrative_scope_note"] = req.prompt
            if req.prompt:
                cfg["language"] = detect_story_language(user_input=req.prompt)

    write_world_file(world_path, "world_config.json", cfg)

    return {"message": "World created", "world_name": world_name}


@router.post("/worlds/{world_name}/seed-demo")
def seed_demo(world_name: str, overwrite: bool = False):
    _validate_world_name(world_name)
    world_path = world_path_of(world_name)
    if os.path.exists(world_path) and not overwrite:
        raise HTTPException(
            status_code=400,
            detail=f"World '{world_name}' already exists. Set overwrite=true to re-seed."
        )
    if not os.path.isdir(world_path):
        os.makedirs(world_path)

    world_config = {
        "display_name": "Nine Heavens Realm",
        "genre": "xianxia / cultivation",
        "power_system": "Realm: Qi Condensation -> Foundation Establishment -> Core Formation -> Nascent Soul -> Deity Transformation",
        "tone": "dark, scheming, strength-based",
        "fixed_rules": [
            "Major realm breakthrough only occurs at canon checkpoint, not spontaneously in sandbox",
            "Main characters (Gu Changge, Xue Li) cannot die outside the predefined script"
        ],
        "current_checkpoint_id": "cp_0",
        "completed_checkpoints": [],
        "branched_from": None,
        "lore_rag_max_tokens": None,
        "opening_mode": "ai_generate",
        "opening_text": "",
        "story_clock": dict(DEFAULT_STORY_CLOCK),
        "foreshadowing_tracker": []
    }

    cards = [
        make_card("char_gu_changge", "char", "Gu Changge",
                  "Peerless genius, deep scheming, has hidden motives, appears from the beginning of the story.",
                  unlock_checkpoint_id="cp_0", status="unlocked"),
        make_card("char_xueli", "char", "Xue Li (Shangguan Liqi)",
                  "Female lead, mysterious background, complex relationship with Gu Changge.",
                  unlock_checkpoint_id="cp_0", status="unlocked"),
        make_card("char_su_phu", "char", "Xue Li's Master",
                  "Guides Xue Li in the early stages, holds a secret regarding her origins.",
                  unlock_checkpoint_id="cp_1", status="locked"),
        make_card("lore_mon_phai", "lore", "Starting Sect",
                  "The sect where Xue Li cultivates in the early stages, internal rules, hierarchy.",
                  unlock_checkpoint_id="cp_0", status="unlocked"),
        make_card("lore_dai_mac", "lore", "Great Desert Forbidden Land",
                  "Dangerous area with a secret realm, only opens after character reaches Foundation Establishment.",
                  unlock_checkpoint_id="cp_2", status="locked"),
        make_card("char_ma_vuong", "char", "Demon King (major villain)",
                  "Late-stage villain, absolutely will not appear before the late checkpoint.",
                  unlock_checkpoint_id="cp_4", status="locked"),
    ]

    checkpoints = [
        make_checkpoint(
            "cp_0", "Story begins: Xue Li joins the sect, meets Gu Changge for the first time",
            required_conditions=[],
            cards_unlocked=["char_gu_changge", "char_xueli", "lore_mon_phai"],
            locations=["Starting Sect"],
            allowed_characters=["char_gu_changge", "char_xueli"],
            time_window="Entry stage"
        ),
        make_checkpoint(
            "cp_1", "Xue Li takes a master, discovers the first clue about her origins",
            required_conditions=[
                {"field": "char_xueli.power_stat.exp", "op": ">=", "value": 10}
            ],
            cards_unlocked=["char_su_phu"],
            locations=["Starting Sect", "Back mountain"],
            allowed_characters=["char_gu_changge", "char_xueli", "char_su_phu"],
            time_window="Entry stage -> tr\u01b0\u1edbc Foundation Establishment"
        ),
        make_checkpoint(
            "cp_2", "Xue Li \u0111\u1ed9t ph\u00e1 Foundation Establishment, m\u1edf kh\u00f3a Great Desert Forbidden Land",
            required_conditions=[
                {"field": "char_xueli.power_stat.exp", "op": ">=", "value": 30}
            ],
            cards_unlocked=["lore_dai_mac"],
            locations=["Starting Sect", "Great Desert Forbidden Land"],
            allowed_characters=["char_gu_changge", "char_xueli", "char_su_phu"],
            time_window="After breaking through Foundation Establishment",
            realm_updates={"char_xueli": "Foundation Establishment"}
        ),
        make_checkpoint(
            "cp_3", "First explicit conflict between Xue Li and Gu Changge",
            required_conditions=[
                {"field": "char_xueli.knowledge_flags", "op": "contains",
                 "value": "knows Gu Changge's secret"}
            ],
            cards_unlocked=[],
            locations=["Great Desert Forbidden Land"],
            allowed_characters=["char_gu_changge", "char_xueli"],
            time_window="Trong Great Desert Forbidden Land",
            realm_updates={"char_xueli": "Core Formation"}
        ),
        make_checkpoint(
            "cp_4", "Demon King appears for the first time (late stage)",
            required_conditions=[
                {"field": "char_xueli.power_stat.realm", "op": "in",
                 "value": ["Core Formation", "Nascent Soul"]}
            ],
            cards_unlocked=["char_ma_vuong"],
            locations=["Great Desert Forbidden Land", "Deep forbidden area"],
            allowed_characters=["char_gu_changge", "char_xueli", "char_ma_vuong"],
            time_window="Late stage of the story"
        ),
    ]

    characters = {
        "char_gu_changge": make_character(
            name="Gu Changge",
            location="Starting Sect",
            affinity={"char_xueli": 0},
            realm="Foundation Establishment",
            exp=0,
            sub_stats={"scheming": 3},
            knowledge_flags=["knows Xue Li has a mysterious background"],
            alive=True,
            appearance="Tall, with sharp features and an ever-present subtle smile. Wears flowing white robes embroidered with silver clouds.",
            personality="Calculating and charismatic. Projects an image of elegance and detachment while scheming in the shadows.",
            backstory="A talented disciple from a fallen noble lineage, raised in the sect with a burning desire to reclaim his family's honor.",
            abilities_and_limits="Skilled in formation magic and swordplay. Weak to direct emotional appeals that bypass his logic.",
            speech_style="Polished and indirect. Often speaks in metaphors. 'One must learn to dance in the rain without getting wet.'",
            secrets="Knows the truth behind his family's downfall and secretly seeks revenge against the sect elder responsible."
        ),
        "char_xueli": make_character(
            name="Xue Li",
            location="Starting Sect",
            affinity={"char_gu_changge": 0},
            realm="Qi Condensation",
            exp=0,
            sub_stats={"combat experience": 0},
            knowledge_flags=[],
            alive=True,
            appearance="Petite with long silver-white hair and striking crimson eyes. Wears a tattered grey cloak over simple robes.",
            personality="Timid and withdrawn, but fiercely curious about ancient artifacts and forbidden knowledge.",
            backstory="Found as an orphan near the sect gates, Xue Li has no memory of her parents. An ancient bloodline runs dormant within her.",
            abilities_and_limits="Possesses a natural affinity for ice magic that manifests under emotional duress. Physically frail.",
            speech_style="Quiet, hesitant. Often trails off mid-sentence. 'I... I don't think we should go there. It feels... wrong.'",
            secrets="Her bloodline is that of an ancient ice demon sealed away millennia ago. The seal weakens as she grows stronger."
        ),
    }

    write_world_file(world_path, "world_config.json", world_config)
    write_world_file(world_path, "card_registry.json", {"cards": cards})
    write_world_file(world_path, "canon_timeline.json", {"checkpoints": checkpoints})
    write_world_file(world_path, "character_state.json", {"characters": characters})
    write_world_file(world_path, "chapters.json", {"chapters": [], "running_summary": "", "memorable_beats": []})

    return {
        "message": "Seed demo done",
        "world_name": world_name,
        "checkpoints": len(checkpoints),
        "cards": len(cards),
        "characters": len(characters)
    }


@router.get("/worlds/{world_name}/export")
def export_world(world_name: str):
    world_path = require_world(world_name)
    pkg = {
        "export_version": "1.0",
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "world_config": read_world_file(world_path, "world_config.json"),
        "card_registry": read_world_file(world_path, "card_registry.json"),
        "canon_timeline": read_world_file(world_path, "canon_timeline.json"),
        "character_state": read_world_file(world_path, "character_state.json")
    }

    override = read_world_runtime_override(world_name)
    if override:
        pkg["runtime_override"] = override

    style_card_path = os.path.join(world_path, "style_card.json")
    if os.path.isfile(style_card_path):
        try:
            with open(style_card_path, "r", encoding="utf-8") as f:
                pkg["style_card"] = json.load(f)
        except Exception:
            pass

    return pkg


@router.post("/worlds/{world_name}/fork")
def fork_timeline_at_checkpoint(world_name: str, req: ForkRequest):
    _validate_world_name(req.new_world_name)
    src_path = require_world(world_name)
    dest_path = world_path_of(req.new_world_name)

    if os.path.exists(dest_path):
        raise HTTPException(status_code=400, detail="New world name already exists.")

    import shutil
    shutil.copytree(src_path, dest_path)

    chapters_data = read_world_file(dest_path, "chapters.json")
    chapters = chapters_data.get("chapters", [])

    cutoff_idx = len(chapters)
    for i, ch in enumerate(chapters):
        if ch.get("checkpoint_id") == req.checkpoint_id:
            cutoff_idx = i
            break

    chapters_data["chapters"] = chapters[:cutoff_idx]
    write_world_file(dest_path, "chapters.json", chapters_data)

    config = read_world_file(dest_path, "world_config.json")
    config["current_checkpoint_id"] = req.checkpoint_id
    if "completed_checkpoints" in config and req.checkpoint_id in config["completed_checkpoints"]:
        idx = config["completed_checkpoints"].index(req.checkpoint_id)
        config["completed_checkpoints"] = config["completed_checkpoints"][:idx]
    write_world_file(dest_path, "world_config.json", config)

    return {"status": "ok", "new_world_name": req.new_world_name}


@router.get("/worlds/{world_name}/export-story")
def export_story_html(world_name: str):
    world_path = require_world(world_name)
    chapters_data = read_world_file(world_path, "chapters.json")
    chapters = chapters_data.get("chapters", [])
    config = read_world_file(world_path, "world_config.json")

    html_content = f"<html><head><meta charset='utf-8'><title>{config.get('display_name', world_name)}</title>"
    html_content += "<style>body{font-family:serif; max-width:800px; margin:40px auto; line-height:1.6; color:#333; padding: 20px;} "
    html_content += ".chapter-title {text-align:center; margin-top:2em;} .user-input {font-style:italic; color:#666; margin-bottom:1em;}</style></head><body>"
    html_content += f"<h1 style='text-align:center;'>{config.get('display_name', world_name)}</h1>"

    for ch in chapters:
        if ch.get("chapter_title"):
            html_content += f"<h2 class='chapter-title'>{ch['chapter_title']}</h2>"
        if ch.get("user_input"):
            html_content += f"<div class='user-input'>&gt; {ch['user_input']}</div>"
        text = ch.get("chapter_text", "").replace("\n", "<br>")
        html_content += f"<p>{text}</p>"
        html_content += "<hr style='border:0; border-top:1px solid #eee; margin:2em 0;'>"

    html_content += "</body></html>"
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)


@router.get("/worlds/{world_name}/codex")
def get_world_codex(world_name: str):
    world_path = require_world(world_name)
    cards = read_world_file(world_path, "card_registry.json")
    chars = read_world_file(world_path, "character_state.json")

    unlocked_cards = [c for c in cards if c.get("status") == "unlocked"]
    return {
        "cards": unlocked_cards,
        "characters": chars
    }


@router.get("/worlds/{world_name}/location-map")
def get_world_location_map(world_name: str):
    world_path = require_world(world_name)
    try:
        location_map = read_world_file(world_path, "location_map.json")
    except FileNotFoundError:
        return {"locations": []}
    return location_map


@router.get("/worlds/{world_name}/location-map/status")
def get_world_location_map_status(world_name: str):
    world_path = require_world(world_name)
    try:
        location_map = read_world_file(world_path, "location_map.json")
    except FileNotFoundError:
        return {"locations": []}

    try:
        character_state = read_world_file(world_path, "character_state.json")
    except FileNotFoundError:
        character_state = {"characters": {}}

    try:
        world_config = read_world_file(world_path, "world_config.json")
    except FileNotFoundError:
        world_config = {}

    characters = character_state.get("characters", {})
    main_char_id = world_config.get("main_character_id", "")
    main_char = characters.get(main_char_id, {})
    main_realm = main_char.get("power_stat", {}).get("realm", "")
    main_exp = main_char.get("power_stat", {}).get("exp", 0)

    completed_checkpoints = set(world_config.get("completed_checkpoints", []) or [])
    current_cp_id = world_config.get("current_checkpoint_id", "")
    completed_checkpoints.add(current_cp_id)

    locations = location_map.get("locations", [])
    enriched = []
    for loc in locations:
        loc_id = loc.get("id", "")
        unlock_realm = loc.get("unlock_realm")
        unlock_exp = loc.get("unlock_exp", 0)
        unlock_cp = loc.get("unlock_checkpoint_id")

        is_unlocked = True
        reasons = []
        if unlock_realm and main_realm != unlock_realm:
            is_unlocked = False
            reasons.append(f"Cần đạt {unlock_realm}")
        if unlock_exp and main_exp < unlock_exp:
            is_unlocked = False
            reasons.append(f"Cần {unlock_exp} EXP (hiện có {main_exp})")
        if unlock_cp and unlock_cp not in completed_checkpoints:
            is_unlocked = False
            reasons.append(f"Cần hoàn thành checkpoint {unlock_cp}")

        enriched.append({
            **loc,
            "is_unlocked": is_unlocked,
            "unlock_reason_missing": "; ".join(reasons) if reasons else None,
        })

    return {"locations": enriched}


@router.get("/worlds/{world_name}/quest_board")
def get_quest_board(world_name: str):
    """
    Return active quests for the world if quest_board_enabled is true.
    Quests are derived from world_events.json pending events that are either:
    - discoverable_from_start: true, OR
    - event_id appears in open_threads
    """
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")

    if not world_config.get("quest_board_enabled", False):
        return {"quests": [], "enabled": False}

    # Load world_events
    from app.world_events import load_world_events
    world_events = load_world_events(world_path)
    events = world_events.get("events", [])

    open_threads = world_config.get("open_threads", [])
    # Flatten open_threads notes into a set for quick lookup
    thread_texts = set()
    for thread in open_threads:
        if isinstance(thread, dict):
            note = thread.get("note", "")
            if note:
                thread_texts.add(note.lower())
        elif isinstance(thread, str):
            thread_texts.add(thread.lower())

    quests = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("status") != "pending":
            continue

        event_id = event.get("event_id", "")
        discoverable = event.get("discoverable_from_start", False)

        # Check if event is known via open_threads
        event_in_threads = False
        if event_id:
            for thread_text in thread_texts:
                if event_id.lower() in thread_text or event_id in thread_text:
                    event_in_threads = True
                    break

        if not discoverable and not event_in_threads:
            continue

        # Build quest entry
        trigger_conditions = event.get("trigger_conditions", [])
        deadline_tick = None
        for cond in trigger_conditions:
            if isinstance(cond, dict) and cond.get("field") == "story_clock.tick":
                deadline_tick = cond.get("value")
                break

        quests.append({
            "quest_id": event_id,
            "title": event.get("quest_hint_title") or event.get("title", "Unknown Quest"),
            "hint": event.get("quest_hint_text") or "",
            "location_hint": event.get("location_hint"),
            "deadline_tick": deadline_tick,
            "discoverable_from_start": discoverable,
        })

    return {"quests": quests, "enabled": True}
