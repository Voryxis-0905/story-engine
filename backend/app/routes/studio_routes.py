from fastapi import APIRouter, HTTPException
import json
import os
import time
import uuid

from app.storage import (
    require_world, read_world_file, write_world_file,
    read_world_canon, write_world_canon,
    _get_effective_extractor_cross_check,
)
from app.engine import (
    call_llm, parse_llm_json, LLMCallError,
    EXTRACTOR_SYSTEM_PROMPT,
)

router = APIRouter()


def _canon_fact_key(fact: dict) -> str:
    return fact.get("fact_id", "")


def _ensure_fact_fields(fact: dict) -> dict:
    if "is_pinned" not in fact:
        fact["is_pinned"] = False
    if "revision_history" not in fact:
        fact["revision_history"] = []
    if "created_at" not in fact:
        fact["created_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if "updated_at" not in fact:
        fact["updated_at"] = fact["created_at"]
    return fact


@router.get("/worlds/{world_name}/studio/canon-log")
def get_canon_log(world_name: str):
    world_path = require_world(world_name)
    canon_store = read_world_canon(world_path)
    facts = canon_store.get("facts", [])

    enriched = []
    for f in facts:
        if not isinstance(f, dict):
            continue
        _ensure_fact_fields(f)
        enriched.append({
            "fact_id": f.get("fact_id", ""),
            "statement": f.get("statement", ""),
            "category": f.get("category", "lore"),
            "source_checkpoint_id": f.get("source_checkpoint_id"),
            "immutable": f.get("immutable", True),
            "is_pinned": f.get("is_pinned", False),
            "created_at": f.get("created_at", ""),
            "updated_at": f.get("updated_at", ""),
            "revision_count": len(f.get("revision_history", [])),
            "revision_history": f.get("revision_history", []),
        })

    return {
        "world": world_name,
        "facts": enriched,
        "total": len(enriched),
    }


@router.post("/worlds/{world_name}/studio/canon-log/{fact_id}/revert")
def revert_canon_fact(world_name: str, fact_id: str, revision_index: int = -1):
    world_path = require_world(world_name)
    canon_store = read_world_canon(world_path)
    facts = canon_store.get("facts", [])

    target = None
    for f in facts:
        if isinstance(f, dict) and f.get("fact_id") == fact_id:
            target = f
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Fact '{fact_id}' not found")

    _ensure_fact_fields(target)

    history = target.get("revision_history", [])
    if not history:
        raise HTTPException(status_code=400, detail="No revision history to revert to")

    if revision_index < 0:
        revision_index = len(history) - 1
    if revision_index < 0 or revision_index >= len(history):
        raise HTTPException(
            status_code=400,
            detail=f"revision_index {revision_index} out of range (0-{len(history)-1})"
        )

    current_statement = target.get("statement", "")
    history.append({
        "statement": current_statement,
        "reverted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    target["statement"] = history[revision_index]["statement"]
    target["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    write_world_canon(world_path, canon_store)
    return {
        "message": "Fact reverted",
        "fact_id": fact_id,
        "previous_statement": current_statement,
        "restored_statement": target["statement"],
    }


@router.post("/worlds/{world_name}/studio/canon-log/{fact_id}/pin")
def toggle_pin_canon_fact(world_name: str, fact_id: str):
    world_path = require_world(world_name)
    canon_store = read_world_canon(world_path)
    facts = canon_store.get("facts", [])

    target = None
    for f in facts:
        if isinstance(f, dict) and f.get("fact_id") == fact_id:
            target = f
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"Fact '{fact_id}' not found")

    _ensure_fact_fields(target)

    target["is_pinned"] = not target.get("is_pinned", False)
    target["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    write_world_canon(world_path, canon_store)
    return {
        "message": "Pin toggled",
        "fact_id": fact_id,
        "is_pinned": target["is_pinned"],
    }
