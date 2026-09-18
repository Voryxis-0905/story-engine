"""Templates responsibilities for Story Engine."""
from typing import Dict
from typing import List

# Bump when the persisted world/save shape changes, and add a matching
# migration step in app/world/schema.py. Worlds without the field are v1.
SCHEMA_VERSION = 6

STYLE_CARD_TEMPLATE = {
    "perspective": "third_person_limited",
    "voice": "narrative",
    "pacing": "moderate",
    "tone": "balanced",
    "prose_guidelines": [],
    "taboo_words": [],
    "custom_instructions": ""
}


TEMPLATES = {
    "world_config.json": {
        "schema_version": SCHEMA_VERSION,
        "display_name": "",
        "genre": "",
        "power_system": "",
        "tone": "",
        "fixed_rules": [],
        "current_checkpoint_id": "",
        "completed_checkpoints": [],
        "branched_from": None,
        "lore_rag_max_tokens": None,
        "opening_mode": "ai_generate",
        "opening_text": "",
        "protagonist_id": "",
        "pacing_level": "Balanced",
        "output_length": "Standard",
        "pov_angle": "3rd_person_limited",
        "prelude_enabled": False,
        "prelude_confirmed": False,
        "language": "en",
        "story_clock": {
            "year": 1,
            "month": 1,
            "day": 1,
            "time_of_day": "morning",
            "season": "spring",
            "tick": 0
        },
        "foreshadowing_tracker": [],
        "linter_notification_enabled": True,
        "linter_auto_run": False,
        "keyword_auto_retry": False,
        "open_threads": [],
        "story_mode": "endless",
        "lifecycle_status": "active",
        "world_flags": {},
        "target_ending_scenario": None,
        "quest_board_enabled": False,
        "allow_unchecked_commit": False,
        "revision": 0,
        "pre_turn_snapshot": None,
        "active_journey": None
    },
    "card_registry.json": {
        "cards": []
    },
    "canon_timeline.json": {
        "checkpoints": []
    },
    "character_state.json": {
        "characters": {}
    },
    "chapters.json": {
        "chapters": [],
        "running_summary": "",
        "memorable_beats": []
    },
    "world_canon_store.json": {
        "facts": []
    },
    "branch_local_delta.json": {
        "overrides": {}
    },
    "location_map.json": {
        "locations": []
    },
    "world_events.json": {
        "events": []
    },
    "discovery.json": {
        "discoveries": []
    },
    "style_card.json": STYLE_CARD_TEMPLATE
}


def make_card(card_id: str, card_type: str, name: str, content: str,
              unlock_checkpoint_id: str = None, status: str = "locked",
              entity_id: str = None, aliases: list = None,
              scope: str = None, entity_status: str = "active"):
    return {
        "id": card_id,
        "type": card_type,
        "name": name,
        "content": content,
        "unlock_checkpoint_id": unlock_checkpoint_id,
        "status": status,
        "entity_id": entity_id,
        "aliases": aliases or [],
        "scope": scope,
        "entity_status": entity_status
    }


def make_checkpoint(checkpoint_id: str, description: str,
                     required_conditions=None, cards_unlocked=None,
                     locations=None, allowed_characters=None,
                     time_window: str = "", realm_updates=None):
    return {
        "checkpoint_id": checkpoint_id,
        "description": description,
        "required_conditions": required_conditions or [],
        "cards_unlocked": cards_unlocked or [],
        "boundary": {
            "locations": locations or [],
            "allowed_characters": allowed_characters or [],
            "time_window": time_window
        },
        "realm_updates": realm_updates or {},
        "sub_beats": []
    }


def make_character(name: str, location: str = "", affinity=None,
                    realm: str = "", exp: int = 0, sub_stats=None,
                    knowledge_flags=None, inventory=None, karma: int = 0,
                    alive: bool = True,
                    relationships: Dict[str, str] = None, age: str = "",
                    known_skills: List[str] = None,
                    appearance: str = "", personality: str = "",
                    backstory: str = "", abilities_and_limits: str = "",
                    speech_style: str = "", secrets: str = ""):
    return {
        "name": name,
        "location": location,
        "affinity": affinity or {},
        "power_stat": {
            "realm": realm,
            "exp": exp,
            "sub_stats": sub_stats or {},
            "known_skills": known_skills or []
        },
        "knowledge_flags": knowledge_flags or [],
        "inventory": inventory or [],
        "karma": karma,
        "alive": alive,
        "relationships": relationships or {},
        "age": age,
        "appearance": appearance,
        "personality": personality,
        "backstory": backstory,
        "abilities_and_limits": abilities_and_limits,
        "speech_style": speech_style,
        "secrets": secrets
    }
