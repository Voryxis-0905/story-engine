"""Entities responsibilities for Story Engine."""
from app.checkpoint_engine import make_card
from app.checkpoint_engine import make_character
from app.checkpoint_engine import make_checkpoint
from fastapi import HTTPException
from typing import Optional


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


# Core state files an import package may carry in addition to the required four.
# They are part of CORE_STATE_FILES, so they get snapshotted and schema-scanned
# like any other world state: a package that ships one with the wrong collection
# type must be rejected at the boundary, not left to fail later inside a turn.
OPTIONAL_IMPORTED_CORE_FILES = (
    ("world_events", "world_events.json"),
    ("location_map", "location_map.json"),
)


def validate_imported_optional_core_files(pkg: dict, templates: dict) -> dict:
    """Return {filename: content} for the optional core files present in pkg.

    Expected collection fields are read from the template, so this stays correct
    when a template gains a new list field.
    """
    normalized = {}
    for package_key, filename in OPTIONAL_IMPORTED_CORE_FILES:
        raw = pkg.get(package_key)
        if raw is None:
            continue
        if not isinstance(raw, dict):
            raise HTTPException(
                status_code=400,
                detail=f"Import package error: '{package_key}' must be a valid object",
            )
        template = templates[filename]
        merged = {**template, **raw}
        for field, template_value in template.items():
            if isinstance(template_value, list) and not isinstance(merged.get(field), list):
                raise HTTPException(
                    status_code=400,
                    detail=f"Import package error: '{package_key}.{field}' must be an array",
                )
        normalized[filename] = merged
    return normalized


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
