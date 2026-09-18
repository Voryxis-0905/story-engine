"""Event-grounded relationship memory (W06).

Relationships are remembered as concrete events (a promise, a debt, help, a
betrayal, a shared experience), each tied to a tick/event and to the characters
who actually know about it. Affinity may still exist, but it is a summary of
these memories, not a replacement. A character who did not witness or hear about
a betrayal has no memory of it and therefore no relationship change from it.
"""
import uuid
from typing import Dict, List, Optional

MEMORY_KINDS = ("promise", "debt", "help", "betrayal", "shared_experience", "gift", "insult")


def _new_id() -> str:
    return f"rel_{uuid.uuid4().hex[:10]}"


def _memory_list(character_state: dict, subject_id: str) -> list:
    character = character_state.get(subject_id)
    if not isinstance(character, dict):
        return []
    memories = character.setdefault("relationship_memories", [])
    if not isinstance(memories, list):
        character["relationship_memories"] = memories = []
    return memories


def make_memory(subject_id: str, other_id: str, kind: str, statement: str, *,
                event_id: str = None, tick: int = None, status: str = "open",
                weight: float = 0.5, witnesses: Optional[list] = None) -> dict:
    return {
        "memory_id": _new_id(),
        "subject": subject_id,
        "with": other_id,
        "kind": kind if kind in MEMORY_KINDS else "shared_experience",
        "statement": statement,
        "event_id": event_id,
        "tick": tick,
        "status": status,
        "weight": float(max(0.0, min(1.0, weight))),
        "known_by": list(witnesses or [subject_id]),
    }


def record_memory(character_state: dict, subject_id: str, other_id: str, kind: str,
                  statement: str, *, event_id: str = None, tick: int = None,
                  status: str = "open", weight: float = 0.5,
                  witnesses: Optional[list] = None) -> Optional[dict]:
    memories = _memory_list(character_state, subject_id)
    memory = make_memory(subject_id, other_id, kind, statement, event_id=event_id,
                         tick=tick, status=status, weight=weight, witnesses=witnesses)
    memories.append(memory)
    return memory


def record_memory_for_knowers(character_state: dict, knower_ids: list, other_id: str,
                              kind: str, statement: str, *, event_id: str = None,
                              tick: int = None, status: str = "open",
                              weight: float = 0.5) -> List[dict]:
    """Only characters who know about the event get the memory."""
    created = []
    for knower_id in knower_ids:
        memory = record_memory(
            character_state, knower_id, other_id, kind, statement,
            event_id=event_id, tick=tick, status=status, weight=weight,
            witnesses=knower_ids,
        )
        if memory:
            created.append(memory)
    return created


def memories_of(character_state: dict, subject_id: str, other_id: str = None) -> List[dict]:
    memories = [
        memory for memory in character_state.get(subject_id, {}).get("relationship_memories", [])
        if isinstance(memory, dict)
    ] if isinstance(character_state.get(subject_id), dict) else []
    if other_id is not None:
        memories = [m for m in memories if m.get("with") == other_id]
    return memories


def resolve_memory(character_state: dict, subject_id: str, memory_id: str, status: str) -> bool:
    for memory in memories_of(character_state, subject_id):
        if memory.get("memory_id") == memory_id:
            memory["status"] = status
            return True
    return False


def relevant_memories(character_state: dict, subject_id: str, other_id: str = None,
                      limit: int = 5) -> List[dict]:
    """Most relevant open/recent memories for context, bounded by weight then tick."""
    memories = [m for m in memories_of(character_state, subject_id, other_id)]
    memories.sort(key=lambda m: (m.get("status") == "open", m.get("weight", 0.0), m.get("tick") or 0),
                  reverse=True)
    return memories[:limit] if limit else memories


def build_relationship_context(character_state: dict, subject_ids, *, limit: int = 5) -> Dict[str, list]:
    context = {}
    for subject_id in subject_ids:
        context[subject_id] = {
            "memories": [
                {
                    "with": m.get("with"),
                    "kind": m.get("kind"),
                    "statement": m.get("statement"),
                    "status": m.get("status"),
                    "event_id": m.get("event_id"),
                    "tick": m.get("tick"),
                    "weight": m.get("weight"),
                }
                for m in relevant_memories(character_state, subject_id, limit=limit)
            ]
        }
    return context


def affinity_delta_from_memory(memory: dict) -> float:
    """A small, memory-driven affinity nudge (never the whole relationship)."""
    kind = memory.get("kind")
    status = memory.get("status")
    weight = memory.get("weight", 0.5)
    if kind in ("help", "gift", "shared_experience"):
        return round(weight * 0.2, 3)
    if kind in ("betrayal", "insult"):
        return round(-weight * 0.3, 3)
    if kind == "promise":
        return round(weight * 0.1, 3) if status == "kept" else round(-weight * 0.2, 3)
    if kind == "debt":
        return round(-weight * 0.05, 3)
    return 0.0
