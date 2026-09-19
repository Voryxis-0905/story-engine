"""Genre-neutral, evidence-backed character capability helpers."""
import re
from typing import Any


def _key(value: Any) -> str:
    return re.sub(r"[^\w]+", " ", str(value or "").casefold().replace("_", " "), flags=re.UNICODE).strip()


def capability_evidence(character: dict) -> list[dict]:
    """Return explicit evidence plus a compatibility view of known skills.

    Prose fields stay evidence for the narrator, but are deliberately not parsed
    into hard permissions: worlds should declare important capabilities once,
    with their source, instead of relying on a brittle number or title guess.
    """
    if not isinstance(character, dict):
        return []
    result = []
    for entry in character.get("capabilities", []) or []:
        if isinstance(entry, str):
            entry = {"capability_id": _key(entry).replace(" ", "_"), "statement": entry}
        if not isinstance(entry, dict):
            continue
        statement = str(entry.get("statement") or entry.get("name") or entry.get("capability_id") or "").strip()
        if not statement:
            continue
        result.append({
            "capability_id": str(entry.get("capability_id") or _key(statement).replace(" ", "_")),
            "statement": statement,
            "proficiency": str(entry.get("proficiency") or "trained"),
            "sources": [str(x) for x in (entry.get("sources") or []) if str(x).strip()],
            "limits": [str(x) for x in (entry.get("limits") or []) if str(x).strip()],
            "tags": [str(x) for x in (entry.get("tags") or []) if str(x).strip()],
        })
    power = character.get("power_stat") if isinstance(character.get("power_stat"), dict) else {}
    for skill in power.get("known_skills", []) or []:
        if isinstance(skill, str) and skill.strip():
            result.append({
                "capability_id": _key(skill).replace(" ", "_"), "statement": skill.strip(),
                "proficiency": "known", "sources": ["power_stat.known_skills"],
                "limits": [], "tags": ["legacy_skill"],
            })
    return result


def find_capability(character: dict, requirement: Any):
    wanted = _key(requirement.get("capability_id") or requirement.get("name")) if isinstance(requirement, dict) else _key(requirement)
    if not wanted:
        return None
    wanted_tokens = set(wanted.split())
    for evidence in capability_evidence(character):
        haystack = _key(" ".join([
            evidence.get("capability_id", ""), evidence.get("statement", ""),
            *evidence.get("tags", []),
        ]))
        if wanted == _key(evidence.get("capability_id")) or wanted == _key(evidence.get("statement")):
            return evidence
        if wanted_tokens and wanted_tokens.issubset(set(haystack.split())):
            return evidence
    return None
