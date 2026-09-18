"""Deliberate projections of character state for player and model consumers."""
from typing import Dict


_PUBLIC_FIELDS = frozenset({
    "name", "aliases", "alive", "location", "age", "appearance",
    "speech_style", "status_effects", "titles",
})

_NARRATIVE_FIELDS = _PUBLIC_FIELDS | frozenset({
    "personality", "goals", "abilities_and_limits", "power_stat",
})

_PROTAGONIST_PRIVATE_FIELDS = frozenset({
    "inventory", "knowledge_flags", "knowledge", "relationship_memories",
    "relationships", "karma", "psychology", "backstory",
})


def _copy_fields(character: dict, fields: frozenset) -> dict:
    if not isinstance(character, dict):
        return {}
    return {key: value for key, value in character.items() if key in fields}


def player_character_view(characters: dict, protagonist_id: str = "") -> Dict[str, dict]:
    """Return the Codex-safe view; author-only secrets stay server-side."""
    if not isinstance(characters, dict):
        return {}
    result = {}
    for character_id, character in characters.items():
        fields = _PUBLIC_FIELDS
        if character_id == protagonist_id:
            fields = fields | _PROTAGONIST_PRIVATE_FIELDS
        result[character_id] = _copy_fields(character, fields)
    return result


def narrative_character_view(characters: dict) -> Dict[str, dict]:
    """Remove raw secrets and internal memory before the shared writing payload."""
    if not isinstance(characters, dict):
        return {}
    return {
        character_id: _copy_fields(character, _NARRATIVE_FIELDS)
        for character_id, character in characters.items()
    }
