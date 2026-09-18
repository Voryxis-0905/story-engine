"""Player-facing event discovery and quest view (W05).

A discovery is an explicit record that a player learned about a specific event,
and how. Quests are a view over discoveries plus the current event lifecycle, so
a resolved/missed/prevented event updates the quest instead of vanishing, a far
event stays hidden until discovered (no spoiler), and editing free-text notes can
no longer lose a quest once it has been discovered.

World time advances only through the deterministic tick policy already in the
turn pipeline; this module never reads the wall clock as game time.
"""
import json
import os
import uuid
from typing import Dict, List, Optional

DISCOVERY_FILENAME = "discovery.json"

_QUEST_STATUS = {
    "pending": "active",
    "active": "active",
    "resolved": "completed",
    "prevented": "prevented",
    "transformed": "transformed",
    "missed": "missed",
}


def load_discoveries(world_path: str) -> dict:
    path = os.path.join(world_path, DISCOVERY_FILENAME)
    if not os.path.isfile(path):
        return {"discoveries": []}
    try:
        with open(path, "r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (json.JSONDecodeError, OSError):
        return {"discoveries": []}
    if not isinstance(data, dict) or not isinstance(data.get("discoveries"), list):
        return {"discoveries": []}
    return data


def save_discoveries(world_path: str, data: dict) -> None:
    path = os.path.join(world_path, DISCOVERY_FILENAME)
    temporary = f"{path}.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def record_discovery(store: dict, event_id: str, source: dict, at_tick: int,
                     known_deadline_tick: Optional[int] = None) -> bool:
    """Record (once) that the player learned about an event. Returns changed."""
    if not event_id or not isinstance(store, dict):
        return False
    discoveries = store.setdefault("discoveries", [])
    if not isinstance(discoveries, list):
        store["discoveries"] = discoveries = []
    source_kind = (source or {}).get("kind", "unknown")
    for existing in discoveries:
        if (isinstance(existing, dict)
                and existing.get("event_id") == event_id
                and (existing.get("source") or {}).get("kind") == source_kind):
            return False
    discoveries.append({
        "discovery_id": f"disc_{uuid.uuid4().hex[:10]}",
        "event_id": event_id,
        "source": source or {"kind": "unknown"},
        "at_tick": at_tick,
        "known_deadline_tick": known_deadline_tick,
    })
    return True


def ensure_start_discoveries(store: dict, events: list, at_tick: int) -> bool:
    changed = False
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("discoverable_from_start"):
            changed |= record_discovery(
                store, event.get("event_id", ""),
                {"kind": "start", "who": None, "tick": at_tick},
                at_tick, known_deadline_tick=event.get("deadline_tick"),
            )
    return changed


def backfill_from_threads(store: dict, events: list, open_threads: list, at_tick: int) -> bool:
    """One-time bootstrap from legacy open_threads notes, then persisted.

    Once a discovery exists it no longer depends on the note text, so editing
    the prose cannot lose the quest.
    """
    changed = False
    known_ids = {d.get("event_id") for d in store.get("discoveries", []) if isinstance(d, dict)}
    notes = []
    for thread in open_threads or []:
        if isinstance(thread, dict):
            notes.append(str(thread.get("note", "")))
        elif isinstance(thread, str):
            notes.append(thread)
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id", "")
        if not event_id or event_id in known_ids:
            continue
        if any(event_id in note for note in notes):
            changed |= record_discovery(
                store, event_id,
                {"kind": "thread", "who": None, "tick": at_tick},
                at_tick, known_deadline_tick=event.get("deadline_tick"),
            )
    return changed


def quest_view(events: list, store: dict) -> List[dict]:
    """Player's view of events: only discovered ones, with lifecycle status."""
    discoveries = {
        d.get("event_id"): d
        for d in store.get("discoveries", [])
        if isinstance(d, dict) and d.get("event_id")
    }
    quests = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id", "")
        discovery = discoveries.get(event_id)
        if not discovery:
            continue
        raw_status = event.get("status", "pending")
        quests.append({
            "quest_id": event_id,
            "title": event.get("quest_hint_title") or event.get("title", "Unknown Quest"),
            "hint": event.get("quest_hint_text") or "",
            "location_hint": event.get("location_hint"),
            "status": _QUEST_STATUS.get(raw_status, raw_status),
            "event_status": raw_status,
            "resolution": event.get("resolution"),
            "deadline_tick": discovery.get("known_deadline_tick"),
            "source": discovery.get("source"),
            "discovered_at_tick": discovery.get("at_tick"),
        })
    return quests
