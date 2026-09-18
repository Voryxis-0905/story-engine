import json
import logging
from typing import Dict, List, Optional, Any

from app.llm_client import call_llm, parse_llm_json
from app.models import CharacterModel

logger = logging.getLogger(__name__)

try:
    from prompts import PSYCHOLOGY_PERCEPTION_PROMPT, PSYCHOLOGY_UPDATE_PROMPT
except ImportError:
    from backend.prompts import PSYCHOLOGY_PERCEPTION_PROMPT, PSYCHOLOGY_UPDATE_PROMPT


class PsychologyState:
    def __init__(self):
        self.hedonic: float = 0.0
        self.stress: float = 0.0
        self.beliefs: Dict[str, float] = {}
        self.theory_of_mind: Dict[str, Dict[str, float]] = {}
        self.mood: str = "neutral"
        self.trust: Dict[str, float] = {}
        self.goals: List[str] = []

    def to_dict(self) -> dict:
        return {
            "hedonic": self.hedonic,
            "stress": self.stress,
            "beliefs": self.beliefs,
            "theory_of_mind": self.theory_of_mind,
            "mood": self.mood,
            "trust": self.trust,
            "goals": self.goals
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PsychologyState":
        if not data:
            return cls()
        state = cls()
        state.hedonic = data.get("hedonic", 0.0)
        state.stress = data.get("stress", 0.0)
        state.beliefs = data.get("beliefs", {})
        state.theory_of_mind = data.get("theory_of_mind", {})
        state.mood = data.get("mood", "neutral")
        state.trust = data.get("trust", {})
        state.goals = data.get("goals", [])
        return state


def generate_perception_for_character(
    character_id: str,
    character_state: Dict[str, Any],
    chapter_text: str,
    world_config: dict,
    checkpoint: dict,
    all_characters: Dict[str, Dict[str, Any]],
    world_name: str = None
) -> Dict[str, Any]:
    """
    Generate perception data for a single character.
    Returns: dict with fields: perception, emotional_response, noticed_threats, etc.
    """
    char_name = character_state.get("name", character_id)
    psychology = PsychologyState.from_dict(character_state.get("psychology", {}))
    from app.story.relationship_memory import relevant_memories
    relationship_memories = relevant_memories(all_characters, character_id, limit=5)

    payload = {
        "character_name": char_name,
        "character_id": character_id,
        "character_personality": character_state.get("personality", ""),
        "character_goals": character_state.get("goals", []),
        "character_knowledge": character_state.get("knowledge", []) if isinstance(character_state.get("knowledge"), list) else [],
        "relationship_memories": relationship_memories,
        "location": character_state.get("location", ""),
        "psychology": psychology.to_dict(),
        "chapter_text": chapter_text,
        "other_characters": [
            {"id": cid, "name": st.get("name", cid), "realm": st.get("power_stat", {}).get("realm", "")}
            for cid, st in all_characters.items() if cid != character_id
        ],
        "checkpoint_description": checkpoint.get("description", ""),
        "world_tone": world_config.get("tone", "neutral")
    }

    raw = call_llm(
        PSYCHOLOGY_PERCEPTION_PROMPT,
        json.dumps(payload, ensure_ascii=False),
        world_name=world_name,
        role="perception"
    )

    try:
        parsed = parse_llm_json(raw, expected_type=dict)
        return {
            "perception": parsed.get("perception", ""),
            "emotional_response": parsed.get("emotional_response", ""),
            "noticed_threats": parsed.get("noticed_threats", []),
            "noticed_opportunities": parsed.get("noticed_opportunities", []),
            "impression_of_others": parsed.get("impression_of_others", {}),
            "decision": parsed.get("decision", "observe")
        }
    except Exception as e:
        logger.warning(f"Perception generation failed for {character_id}: {e}")
        return {
            "perception": f"{char_name} observed the scene.",
            "emotional_response": "neutral",
            "noticed_threats": [],
            "noticed_opportunities": [],
            "impression_of_others": {},
            "decision": "observe"
        }


def update_psychology_for_character(
    character_id: str,
    character_state: Dict[str, Any],
    chapter_text: str,
    perception_data: Dict[str, Any],
    world_config: dict,
    world_name: str = None
) -> Dict[str, Any]:
    """
    Update psychology state based on events in the chapter.
    Returns: updated psychology fields (hedonic_delta, stress_delta, belief_updates, etc.)
    """
    psychology = PsychologyState.from_dict(character_state.get("psychology", {}))
    char_name = character_state.get("name", character_id)

    payload = {
        "character_name": char_name,
        "character_id": character_id,
        "current_psychology": psychology.to_dict(),
        "chapter_text": chapter_text,
        "perception_data": perception_data,
        "character_knowledge": character_state.get("knowledge", []) if isinstance(character_state.get("knowledge"), list) else [],
        "relationship_memories": character_state.get("relationship_memories", [])[:5] if isinstance(character_state.get("relationship_memories"), list) else [],
        "world_tone": world_config.get("tone", "neutral"),
        "personality": character_state.get("personality", ""),
        "goals": character_state.get("goals", [])
    }

    raw = call_llm(
        PSYCHOLOGY_UPDATE_PROMPT,
        json.dumps(payload, ensure_ascii=False),
        world_name=world_name,
        role="psychology"
    )

    try:
        parsed = parse_llm_json(raw, expected_type=dict)
        return {
            "hedonic_delta": parsed.get("hedonic_delta", 0.0),
            "stress_delta": parsed.get("stress_delta", 0.0),
            "belief_updates": parsed.get("belief_updates", {}),
            "theory_of_mind_updates": parsed.get("theory_of_mind_updates", {}),
            "trust_updates": parsed.get("trust_updates", {}),
            "mood": parsed.get("mood", "neutral"),
            "goal_updates": parsed.get("goal_updates", [])
        }
    except Exception as e:
        logger.warning(f"Psychology update failed for {character_id}: {e}")
        return {
            "hedonic_delta": 0.0,
            "stress_delta": 0.0,
            "belief_updates": {},
            "theory_of_mind_updates": {},
            "trust_updates": {},
            "mood": "neutral",
            "goal_updates": []
        }


def apply_psychology_changes(
    character_state: Dict[str, Any],
    psychology_updates: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Apply psychology updates to character state.
    Returns: updated character state dict.
    """
    for char_id, updates in psychology_updates.items():
        if char_id not in character_state:
            continue
        state = character_state[char_id]
        psycho = PsychologyState.from_dict(state.get("psychology", {}))

        psycho.hedonic = max(-1.0, min(1.0, psycho.hedonic + updates.get("hedonic_delta", 0.0)))
        psycho.stress = max(0.0, min(1.0, psycho.stress + updates.get("stress_delta", 0.0)))

        for belief_key, value in updates.get("belief_updates", {}).items():
            if isinstance(value, (int, float)):
                old = psycho.beliefs.get(belief_key, 0.5)
                psycho.beliefs[belief_key] = max(0.0, min(1.0, old + value))
            elif isinstance(value, bool) or value is None:
                psycho.beliefs[belief_key] = float(value) if value is not None else 0.5

        for other_id, impressions in updates.get("theory_of_mind_updates", {}).items():
            if other_id not in psycho.theory_of_mind:
                psycho.theory_of_mind[other_id] = {}
            for trait, val in impressions.items():
                if isinstance(val, (int, float)):
                    old = psycho.theory_of_mind[other_id].get(trait, 0.5)
                    psycho.theory_of_mind[other_id][trait] = max(0.0, min(1.0, old + val))

        for other_id, trust_delta in updates.get("trust_updates", {}).items():
            if isinstance(trust_delta, (int, float)):
                old = psycho.trust.get(other_id, 0.5)
                psycho.trust[other_id] = max(0.0, min(1.0, old + trust_delta))

        if updates.get("mood"):
            psycho.mood = updates["mood"]

        if updates.get("goal_updates"):
            psycho.goals = list(set(psycho.goals + updates["goal_updates"]))

        state["psychology"] = psycho.to_dict()

    return character_state


def generate_perceptions_for_all_characters(
    active_characters: Dict[str, Dict[str, Any]],
    chapter_text: str,
    world_config: dict,
    checkpoint: dict,
    world_name: str = None
) -> Dict[str, Dict[str, Any]]:
    """
    Generate perception data for all active characters.
    Returns: dict mapping character_id -> perception data
    """
    perceptions = {}
    for char_id, state in active_characters.items():
        perception = generate_perception_for_character(
            char_id, state, chapter_text, world_config, checkpoint,
            active_characters, world_name
        )
        perceptions[char_id] = perception
    return perceptions


def update_psychologies_for_all_characters(
    active_characters: Dict[str, Dict[str, Any]],
    chapter_text: str,
    perceptions: Dict[str, Dict[str, Any]],
    world_config: dict,
    world_name: str = None
) -> Dict[str, Dict[str, Any]]:
    """
    Update psychology for all active characters.
    Returns: dict mapping character_id -> psychology updates
    """
    updates = {}
    for char_id, state in active_characters.items():
        perception = perceptions.get(char_id, {})
        psych_update = update_psychology_for_character(
            char_id, state, chapter_text, perception, world_config, world_name
        )
        updates[char_id] = psych_update
    return updates