"""World facts and per-subject knowledge with provenance.

Facts are objective canon with stable ids. Knowledge is what a subject believes,
including the source, the tick it was learned, a confidence and (when true) the
fact it links to. A rumor or guess is knowledge with no fact link, so it can be
wrong without changing objective canon. Projection turns the stored facts and
knowledge into the view a single subject is allowed to see; it is shared by the
context sent to models and by the API so both stay consistent.
"""
import uuid
from typing import Dict, Iterable, List, Optional


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def make_fact(statement: str, *, category: str = "event", source: str = None,
              event_id: str = None, tick: int = None, scope: str = "world",
              immutable: bool = True) -> dict:
    return {
        "fact_id": _new_id("fact"),
        "statement": statement,
        "category": category,
        "source": source,
        "event_id": event_id,
        "tick": tick,
        "scope": scope,
        "immutable": immutable,
    }


def make_knowledge(subject: str, statement: str, *, source_kind: str,
                   source_who: str = None, event_id: str = None, tick: int = None,
                   confidence: float = 1.0, fact_id: str = None) -> dict:
    return {
        "knowledge_id": _new_id("kn"),
        "subject": subject,
        "statement": statement,
        "fact_id": fact_id,
        "confidence": float(confidence),
        "source": {"kind": source_kind, "who": source_who, "event_id": event_id},
        "learned_at_tick": tick,
    }


def _knowledge_list(character_state: dict, subject_id: str) -> list:
    character = character_state.get(subject_id)
    if not isinstance(character, dict):
        return []
    entries = character.setdefault("knowledge", [])
    if not isinstance(entries, list):
        character["knowledge"] = entries = []
    return entries


def grant_knowledge(character_state: dict, subject_ids: Iterable[str], statement: str, *,
                    source_kind: str, source_who: str = None, event_id: str = None,
                    tick: int = None, confidence: float = 1.0, fact_id: str = None) -> None:
    if not statement:
        return
    for subject_id in subject_ids:
        entries = _knowledge_list(character_state, subject_id)
        duplicate = any(
            isinstance(entry, dict)
            and entry.get("statement") == statement
            and (entry.get("source") or {}).get("kind") == source_kind
            and (entry.get("source") or {}).get("who") == source_who
            for entry in entries
        )
        if duplicate:
            continue
        entries.append(make_knowledge(
            subject_id, statement, source_kind=source_kind, source_who=source_who,
            event_id=event_id, tick=tick, confidence=confidence, fact_id=fact_id,
        ))


def tell_knowledge(character_state: dict, from_id: str, to_id: str, statement: str, *,
                   tick: int = None, confidence: float = 0.8, fact_id: str = None) -> None:
    grant_knowledge(
        character_state, [to_id], statement, source_kind="told_by",
        source_who=from_id, tick=tick, confidence=confidence, fact_id=fact_id,
    )


def known_knowledge(character_state: dict, subject_id: str) -> list:
    character = character_state.get(subject_id)
    if not isinstance(character, dict):
        return []
    entries = character.get("knowledge", [])
    return [entry for entry in entries if isinstance(entry, dict)] if isinstance(entries, list) else []


def project_knowledge_for_subject(character_state: dict, subject_id: str,
                                  canon_facts: Optional[list] = None) -> list:
    """Return the knowledge a single subject holds, with status resolved to canon."""
    fact_index = {
        fact.get("fact_id"): fact
        for fact in (canon_facts or [])
        if isinstance(fact, dict) and fact.get("fact_id")
    }
    projected = []
    for entry in known_knowledge(character_state, subject_id):
        fact_id = entry.get("fact_id")
        if not fact_id:
            status = entry.get("status") or "uncertain"
        elif fact_id in fact_index:
            status = "true"
        else:
            status = "unknown"
        projected.append({
            "knowledge_id": entry.get("knowledge_id"),
            "statement": entry.get("statement"),
            "fact_id": fact_id,
            "confidence": entry.get("confidence", 1.0),
            "source": entry.get("source", {}),
            "learned_at_tick": entry.get("learned_at_tick"),
            "status": status,
        })
    return projected


def facts_visible_to(canon_facts: list, character_state: dict, subject_id: str) -> list:
    """Objective facts a subject may use: public facts plus facts they know."""
    known_ids = {
        entry.get("fact_id")
        for entry in known_knowledge(character_state, subject_id)
        if entry.get("fact_id")
    }
    visible = []
    for fact in canon_facts or []:
        if not isinstance(fact, dict):
            continue
        if fact.get("scope") == "public" or fact.get("fact_id") in known_ids:
            visible.append(fact)
    return visible


def build_character_knowledge(character_state: dict, subject_ids: Iterable[str],
                              canon_facts: Optional[list] = None) -> Dict[str, list]:
    return {
        subject_id: project_knowledge_for_subject(character_state, subject_id, canon_facts)
        for subject_id in subject_ids
    }
