from fastapi import APIRouter, HTTPException
import json
import os
import shutil

from app.storage import (
    require_world, world_path_of, read_world_file, write_world_file,
    has_real_api_key, get_world_style_card, write_world_style_card,
    read_saves_index, write_saves_index, snapshot_world_state,
    build_save_entry, new_save_id, _validate_world_name
)
from app.engine import (
    TEMPLATES, call_llm, parse_llm_json, make_card, make_checkpoint,
    make_character, LLMCallError, CREATOR_ASSISTANT_PROMPT,
    get_active_cards, get_effective_fallback_chain,
    build_rag_context_text, get_recent_turns_for_context,
    DEFAULT_LORE_RAG_MAX_TOKENS, select_relevant_lore_cards
)
from app.models import (
    CardRegistryUpdate, CanonTimelineUpdate, CharacterStateUpdate,
    ForceAdvanceRequest, CreateSaveRequest, BranchRequest,
    CreatorAssistantRequest, StyleCardModel, TraitDefinition,
    ForeshadowingsUpdateReq
)

router = APIRouter()


@router.put("/worlds/{world_name}/card_registry")
def update_card_registry(world_name: str, req: CardRegistryUpdate):
    world_path = require_world(world_name)
    cards = [c.model_dump() for c in req.cards]
    ids = [c["id"] for c in cards]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="card id is duplicated, each card must have a unique id")
    write_world_file(world_path, "card_registry.json", {"cards": cards})
    return {"message": "card_registry updated", "cards": len(cards)}


@router.put("/worlds/{world_name}/canon_timeline")
def update_canon_timeline(world_name: str, req: CanonTimelineUpdate):
    world_path = require_world(world_name)
    checkpoints = [cp.model_dump() for cp in req.checkpoints]
    ids = [cp["checkpoint_id"] for cp in checkpoints]
    if len(ids) != len(set(ids)):
        raise HTTPException(status_code=400, detail="checkpoint_id is duplicated, each checkpoint must have a unique id")
    write_world_file(world_path, "canon_timeline.json", {"checkpoints": checkpoints})
    return {"message": "canon_timeline updated", "checkpoints": len(checkpoints)}


@router.put("/worlds/{world_name}/character_state")
def update_character_state(world_name: str, req: CharacterStateUpdate):
    world_path = require_world(world_name)
    characters = {cid: c.model_dump() for cid, c in req.characters.items()}
    write_world_file(world_path, "character_state.json", {"characters": characters})
    return {"message": "character_state updated", "characters": len(characters)}


@router.post("/worlds/{world_name}/checkpoint/force-advance")
def force_advance_checkpoint(world_name: str, req: ForceAdvanceRequest):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    canon_timeline = read_world_file(world_path, "canon_timeline.json")
    card_registry = read_world_file(world_path, "card_registry.json")
    character_state = read_world_file(world_path, "character_state.json")

    checkpoints = canon_timeline["checkpoints"]
    target_index = next(
        (i for i, cp in enumerate(checkpoints) if cp["checkpoint_id"] == req.target_checkpoint_id),
        None
    )
    if target_index is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find checkpoint '{req.target_checkpoint_id}' in canon_timeline"
        )

    current_id = world_config.get("current_checkpoint_id", "")
    current_index = next(
        (i for i, cp in enumerate(checkpoints) if cp["checkpoint_id"] == current_id),
        None
    )

    completed = world_config.setdefault("completed_checkpoints", [])
    unlocked_card_names = []
    realm_changes = {}

    if current_index is not None and target_index > current_index:
        for i in range(current_index, target_index):
            cp_id = checkpoints[i]["checkpoint_id"]
            if cp_id not in completed:
                completed.append(cp_id)
        for i in range(current_index + 1, target_index + 1):
            cp = checkpoints[i]
            for card in card_registry["cards"]:
                if (card["id"] in cp.get("cards_unlocked", []) or card.get("unlock_checkpoint_id") == cp["checkpoint_id"]) and card["status"] != "unlocked":
                    card["status"] = "unlocked"
                    unlocked_card_names.append(card["name"])
            for char_id, new_realm in cp.get("realm_updates", {}).items():
                if char_id in character_state["characters"]:
                    character_state["characters"][char_id]["power_stat"]["realm"] = new_realm
                    realm_changes[char_id] = new_realm

    world_config["current_checkpoint_id"] = req.target_checkpoint_id
    write_world_file(world_path, "world_config.json", world_config)
    write_world_file(world_path, "card_registry.json", card_registry)
    write_world_file(world_path, "character_state.json", character_state)

    return {
        "message": "Forced checkpoint transition",
        "from_checkpoint_id": current_id,
        "to_checkpoint_id": req.target_checkpoint_id,
        "cards_unlocked": unlocked_card_names,
        "realm_changes": realm_changes
    }


@router.post("/worlds/{world_name}/saves")
def create_save(world_name: str, req: CreateSaveRequest):
    world_path = require_world(world_name)
    save_id = new_save_id()
    snapshot_world_state(world_path, save_id, TEMPLATES)
    entry = build_save_entry(world_path, save_id, req.label.strip(), "manual")
    saves = read_saves_index(world_path)
    saves.append(entry)
    write_saves_index(world_path, saves)
    return {"message": "Created save point", "save": entry}


@router.get("/worlds/{world_name}/saves")
def list_saves(world_name: str):
    world_path = require_world(world_name)
    return {"saves": list(reversed(read_saves_index(world_path)))}


@router.post("/worlds/{world_name}/saves/{save_id}/restore")
def restore_save(world_name: str, save_id: str):
    world_path = require_world(world_name)
    saves = read_saves_index(world_path)
    if not any(s["save_id"] == save_id for s in saves):
        raise HTTPException(status_code=404, detail=f"Could not find save '{save_id}'")

    safety_id = new_save_id()
    snapshot_world_state(world_path, safety_id, TEMPLATES)
    safety_entry = build_save_entry(
        world_path, safety_id,
        f"Automatic (before restoring to '{save_id}')",
        "safety_before_restore"
    )
    saves.append(safety_entry)

    src_dir = os.path.join(world_path, "saves", save_id)
    for filename in TEMPLATES.keys():
        src = os.path.join(src_dir, filename)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(world_path, filename))

    write_saves_index(world_path, saves)
    return {
        "message": "Restored world to the selected save point",
        "restored_save_id": save_id,
        "safety_save_id": safety_id
    }


@router.delete("/worlds/{world_name}/saves/{save_id}")
def delete_save(world_name: str, save_id: str):
    world_path = require_world(world_name)
    saves = read_saves_index(world_path)
    remaining = [s for s in saves if s["save_id"] != save_id]
    if len(remaining) == len(saves):
        raise HTTPException(status_code=404, detail=f"Could not find save '{save_id}'")
    save_dir = os.path.join(world_path, "saves", save_id)
    if os.path.isdir(save_dir):
        shutil.rmtree(save_dir)
    write_saves_index(world_path, remaining)
    return {"message": "Deleted save point", "save_id": save_id}


@router.post("/worlds/{world_name}/saves/{save_id}/branch")
def branch_from_save(world_name: str, save_id: str, req: BranchRequest):
    world_path = require_world(world_name)
    saves = read_saves_index(world_path)
    if not any(s["save_id"] == save_id for s in saves):
        raise HTTPException(status_code=404, detail=f"Could not find save '{save_id}'")

    new_name = req.new_world_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Must enter a new world name to branch")
    new_world_path = world_path_of(new_name)
    if os.path.exists(new_world_path):
        raise HTTPException(status_code=400, detail=f"World '{new_name}' already exists")

    src_dir = os.path.join(world_path, "saves", save_id)
    os.makedirs(new_world_path)
    for filename, template in TEMPLATES.items():
        src = os.path.join(src_dir, filename)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(new_world_path, filename))
        else:
            write_world_file(new_world_path, filename, template)

    cfg = read_world_file(new_world_path, "world_config.json")
    cfg["branched_from"] = {"world": world_name, "save_id": save_id, "at": __import__('time').strftime("%Y-%m-%d %H:%M:%S UTC", __import__('time').gmtime())}
    write_world_file(new_world_path, "world_config.json", cfg)

    return {
        "message": f"Branched new world '{new_name}' from save '{save_id}'",
        "new_world_name": new_name,
        "source_save_id": save_id
    }


@router.post("/worlds/{world_name}/creator-assistant")
def creator_assistant(world_name: str, req: CreatorAssistantRequest):
    world_path = require_world(world_name)
    if not has_real_api_key(world_name):
        return {
            "explanation": "Default Assistant Suggestions:",
            "suggestions": [
                "Consider adding a new secret card unlocked at a later checkpoint.",
                "Define a rival character with opposing traits or exclusive titles.",
                "Add an alternate outcome to the current checkpoint based on character affinity."
            ]
        }

    cfg = read_world_file(world_path, "world_config.json")
    checkpoints_data = read_world_file(world_path, "canon_timeline.json")
    card_reg = read_world_file(world_path, "card_registry.json")
    char_state = read_world_file(world_path, "character_state.json")

    payload = json.dumps({
        "world_config": cfg,
        "checkpoints": checkpoints_data.get("checkpoints", []),
        "cards": card_reg.get("cards", []),
        "characters": char_state.get("characters", {}),
        "creator_query": req.query,
        "section": req.section or "general"
    }, ensure_ascii=False)

    try:
        raw = call_llm(CREATOR_ASSISTANT_PROMPT, payload, world_name=world_name)
        res = parse_llm_json(raw, expected_type=dict)
        explanation = res.get("explanation", "Here are design suggestions for your world.")
        suggestions = res.get("suggestions", [])
        if not suggestions or not isinstance(suggestions, list):
            suggestions = [
                "Consider adding a new secret card unlocked at a later checkpoint.",
                "Define a rival character with opposing traits or exclusive titles.",
                "Add an alternate outcome to the current checkpoint based on character affinity."
            ]
        return {"explanation": explanation, "suggestions": suggestions}
    except Exception:
        return {
            "explanation": "Default Assistant Suggestions:",
            "suggestions": [
                "Consider adding a new secret card unlocked at a later checkpoint.",
                "Define a rival character with opposing traits or exclusive titles.",
                "Add an alternate outcome to the current checkpoint based on character affinity."
            ]
        }


@router.get("/worlds/{world_name}/style-card")
def get_world_style_card_endpoint(world_name: str):
    require_world(world_name)
    return get_world_style_card(world_name)


@router.put("/worlds/{world_name}/style-card")
def update_world_style_card_endpoint(world_name: str, req: StyleCardModel):
    require_world(world_name)
    data = req.model_dump()
    write_world_style_card(world_name, data)
    return {"message": "style_card updated", "style_card": data}


@router.get("/worlds/{world_name}/traits")
def get_traits(world_name: str):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    traits = world_config.get("trait_definitions", {})
    return list(traits.values())


@router.post("/worlds/{world_name}/traits")
def create_trait(world_name: str, trait: TraitDefinition):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    if "trait_definitions" not in world_config:
        world_config["trait_definitions"] = {}
    if trait.name in world_config["trait_definitions"]:
        raise HTTPException(status_code=400, detail="Trait already exists")
    world_config["trait_definitions"][trait.name] = trait.model_dump()
    write_world_file(world_path, "world_config.json", world_config)
    return {"status": "created", "trait": trait.name}


@router.put("/worlds/{world_name}/traits/{trait_name}")
def update_trait(world_name: str, trait_name: str, trait: TraitDefinition):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    traits = world_config.get("trait_definitions", {})
    if trait_name not in traits:
        raise HTTPException(status_code=404, detail="Trait not found")
    traits[trait_name] = trait.model_dump()
    world_config["trait_definitions"] = traits
    write_world_file(world_path, "world_config.json", world_config)
    return {"status": "updated", "trait": trait_name}


@router.delete("/worlds/{world_name}/traits/{trait_name}")
def delete_trait(world_name: str, trait_name: str):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    traits = world_config.get("trait_definitions", {})
    if trait_name not in traits:
        raise HTTPException(status_code=404, detail="Trait not found")
    del traits[trait_name]
    world_config["trait_definitions"] = traits
    write_world_file(world_path, "world_config.json", world_config)
    return {"status": "deleted", "trait": trait_name}


@router.get("/worlds/{world_name}/graph")
def get_checkpoint_graph(world_name: str):
    world_path = world_path_of(world_name)
    if not os.path.isdir(world_path):
        raise HTTPException(status_code=404, detail="World not found")
    canon = read_world_file(world_path, "canon_timeline.json")

    graph = {}
    checkpoints = canon.get("checkpoints", [])

    for i, cp in enumerate(checkpoints):
        cp_id = cp["checkpoint_id"]
        next_ids = []

        alt_ids = []
        for outcome in cp.get("alternate_outcomes", []):
            if outcome.get("next_checkpoint_id"):
                alt_ids.append(outcome.get("next_checkpoint_id"))

        default_next = cp.get("default_next_checkpoint_id")
        if not default_next and i + 1 < len(checkpoints):
            default_next = checkpoints[i + 1]["checkpoint_id"]

        graph[cp_id] = {
            "default": default_next,
            "alternates": alt_ids
        }

    return {"graph": graph}


@router.get("/worlds/{world_name}/foreshadowings")
def get_foreshadowings(world_name: str):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    tracker = world_config.get("foreshadowing_tracker", world_config.get("foreshadowings", []))
    return {
        "foreshadowing_tracker": tracker,
        "foreshadowings": tracker
    }


@router.put("/worlds/{world_name}/foreshadowings")
def update_foreshadowings(world_name: str, req: ForeshadowingsUpdateReq):
    world_path = require_world(world_name)
    world_config = read_world_file(world_path, "world_config.json")
    items = req.foreshadowing_tracker if req.foreshadowing_tracker is not None else req.foreshadowings
    if items is None:
        raise HTTPException(status_code=400, detail="Missing foreshadowing_tracker or foreshadowings field")
    world_config["foreshadowing_tracker"] = items
    write_world_file(world_path, "world_config.json", world_config)
    return {
        "message": "foreshadowings updated",
        "foreshadowing_tracker": items,
        "foreshadowings": items
    }
