"""Q02: a small project-authored sample world and six journeys.

The world is a compact detective case: three NPCs, three locations, two
background events, a secret and a promise. It exists to prove the loop with no
account, no personal data and no real AI: absent NPCs stay ignorant, false
rumors do not change canon, early intervention prevents an event, a missed
event is recorded, failure opens a new direction, and save/branch keep the
consequences.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from fastapi.testclient import TestClient
from app import storage, engine, chapter_generator
from app.routes import world_routes
from app.world.templates import SCHEMA_VERSION


def _character(name, location, **extra):
    base = {
        "name": name, "location": location, "affinity": {},
        "power_stat": {"realm": "", "exp": 0, "sub_stats": {}, "known_skills": []},
        "knowledge_flags": [], "inventory": [], "karma": 0, "alive": True,
        "relationships": {}, "age": "", "traits": {}, "status_effects": [],
        "appearance": "", "personality": "", "backstory": "",
        "abilities_and_limits": "", "speech_style": "", "secrets": "",
        "knowledge": [], "relationship_memories": [],
    }
    base.update(extra)
    return base


def build_sample_world(worlds_dir: Path, name: str = "bellweather_case"):
    path = worlds_dir / name
    path.mkdir(parents=True, exist_ok=True)

    secret_fact = {
        "fact_id": "fact_ledger", "statement": "The butler hid the ledger.",
        "category": "lore", "source": "author", "event_id": None, "tick": 0,
        "scope": "world", "immutable": True,
    }
    characters = {
        "del_detective": _character("Detective Mara", "Manor", inventory=["notebook"]),
        "npc_butler": _character(
            "Hobbs the butler", "Cellar",
            knowledge=[{
                "knowledge_id": "kn_ledger", "subject": "npc_butler",
                "statement": "The butler hid the ledger.", "fact_id": "fact_ledger",
                "confidence": 1.0,
                "source": {"kind": "witnessed", "who": None, "event_id": None},
                "learned_at_tick": 0,
            }],
        ),
        "npc_maid": _character("Lily the maid", "Garden"),
    }
    characters["del_detective"]["relationship_memories"] = [{
        "memory_id": "rel_promise", "subject": "del_detective", "with": "npc_butler",
        "kind": "promise", "statement": "Mara promised to clear Hobbs' name.",
        "event_id": None, "tick": 0, "status": "open", "weight": 0.9,
        "known_by": ["del_detective"],
    }]

    files = {
        "world_config.json": {
            "schema_version": SCHEMA_VERSION, "revision": 0, "pre_turn_snapshot": None,
            "display_name": "The Bellweather Case", "genre": "detective", "language": "en",
            "protagonist_id": "del_detective", "current_checkpoint_id": "cp_0",
            "completed_checkpoints": [], "story_clock": {"tick": 0},
            "foreshadowing_tracker": [], "open_threads": [], "world_flags": {},
            "quest_board_enabled": True, "psychology_enabled": False,
            "story_mode": "endless", "lifecycle_status": "active",
            "pacing_level": "Balanced", "output_length": "Standard",
        },
        "character_state.json": {"characters": characters},
        "canon_timeline.json": {"checkpoints": [{
            "checkpoint_id": "cp_0", "description": "The case begins.",
            "required_conditions": [], "cards_unlocked": [], "realm_updates": {},
            "boundary": {"locations": ["Manor", "Garden", "Cellar"],
                         "allowed_characters": ["del_detective", "npc_butler", "npc_maid"],
                         "time_window": ""},
            "sub_beats": [],
        }]},
        "card_registry.json": {"cards": []},
        "chapters.json": {"chapters": [], "running_summary": "", "memorable_beats": []},
        "world_canon_store.json": {"facts": [secret_fact]},
        "location_map.json": {"locations": [
            {"id": "Manor", "name": "Manor", "tags": ["indoor"]},
            {"id": "Garden", "name": "Garden", "tags": ["outdoor"]},
            {"id": "Cellar", "name": "Cellar", "tags": ["dark"]},
        ]},
        "world_events.json": {"events": [
            {
                "event_id": "ev_poison", "event_class": "organized",
                "organizer_id": "npc_butler", "location_id": "Cellar",
                "status": "pending", "deadline_tick": 5,
                "trigger_conditions": [{"field": "story_clock.tick", "op": ">=", "value": 2}],
                "outcomes": [
                    {"outcome_id": "poison_done", "resolution": "resolved",
                     "canon_facts_add": ["The wine was poisoned."]},
                    {"outcome_id": "poison_prevented", "resolution": "prevented",
                     "canon_facts_add": ["The poisoning plot was stopped."]},
                ],
            },
            {
                "event_id": "ev_theft", "event_class": "organized",
                "organizer_id": "npc_maid", "location_id": "Garden",
                "status": "pending", "discoverable_from_start": True,
                "trigger_conditions": [{"field": "story_clock.tick", "op": ">=", "value": 1}],
                "outcomes": [{"outcome_id": "theft_done", "resolution": "resolved",
                              "canon_facts_add": ["A silver spoon went missing."]}],
            },
        ]},
        "discovery.json": {"discoveries": []},
        "branch_local_delta.json": {"overrides": {}},
        "style_card.json": {
            "perspective": "third_person_limited", "voice": "narrative",
            "pacing": "moderate", "tone": "tense", "prose_guidelines": [],
            "taboo_words": [], "custom_instructions": "",
        },
    }
    for filename, data in files.items():
        (path / filename).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class SampleWorldJourneys(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        worlds = self.data / "worlds"
        worlds.mkdir()
        for module, name, value in (
            (storage, "WORLDS_DIR", str(worlds)),
            (main, "WORLDS_DIR", str(worlds)),
            (world_routes, "WORLDS_DIR", str(worlds)),
            (storage, "RUNTIME_CONFIG_PATH", str(self.data / "runtime_config.json")),
        ):
            self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.dict(os.environ, {"OPENROUTER_API_KEY": ""}))
        self.world = "bellweather_case"
        self.path = build_sample_world(worlds, self.world)
        self.client = TestClient(main.app)
        self.enterContext(patch.object(main, "call_llm", side_effect=self.fake_llm))

    @staticmethod
    def fake_llm(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
        if system_prompt == main.PLANNER_SYSTEM_PROMPT:
            return main.mock_planner_response(user_input_for_mock)
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            return main.mock_narrator_response(user_input_for_mock)
        return main.mock_consistency_checker_response()

    def tick_once(self, tick):
        from app.world_events import load_world_events, tick_world_events
        world_config = json.loads((self.path / "world_config.json").read_text(encoding="utf-8"))
        world_config["story_clock"]["tick"] = tick
        characters = json.loads((self.path / "character_state.json").read_text(encoding="utf-8"))["characters"]
        canon = json.loads((self.path / "world_canon_store.json").read_text(encoding="utf-8"))
        location_map = json.loads((self.path / "location_map.json").read_text(encoding="utf-8"))
        events = load_world_events(str(self.path))
        tick_world_events(events, world_config, characters, canon, location_map)
        (self.path / "character_state.json").write_text(json.dumps({"characters": characters}), encoding="utf-8")
        (self.path / "world_canon_store.json").write_text(json.dumps(canon), encoding="utf-8")
        (self.path / "world_events.json").write_text(json.dumps(events), encoding="utf-8")
        return events, canon, characters

    def test_journey_absent_npc_stays_ignorant(self):
        from app.story import knowledge
        events, canon, characters = self.tick_once(2)
        statements = [f["statement"] for f in canon["facts"]]
        self.assertIn("The wine was poisoned.", statements)
        butler = knowledge.project_knowledge_for_subject(characters, "npc_butler", canon["facts"])
        maid = knowledge.project_knowledge_for_subject(characters, "npc_maid", canon["facts"])
        self.assertTrue(any(k["statement"] == "The wine was poisoned." for k in butler))
        self.assertFalse(any(k["statement"] == "The wine was poisoned." for k in maid))

    def test_journey_false_rumor_does_not_change_canon(self):
        from app.story import knowledge
        canon = json.loads((self.path / "world_canon_store.json").read_text(encoding="utf-8"))
        characters = json.loads((self.path / "character_state.json").read_text(encoding="utf-8"))["characters"]
        knowledge.grant_knowledge(characters, ["del_detective"], "The maid stole the spoon.",
                                  source_kind="rumor", tick=1)
        view = knowledge.project_knowledge_for_subject(characters, "del_detective", canon["facts"])
        rumor = next(k for k in view if k["statement"] == "The maid stole the spoon.")
        self.assertIsNone(rumor["fact_id"])
        self.assertEqual(rumor["status"], "uncertain")
        self.assertNotIn("The maid stole the spoon.", [f["statement"] for f in canon["facts"]])

    def test_journey_early_intervention_prevents_event(self):
        characters = json.loads((self.path / "character_state.json").read_text(encoding="utf-8"))["characters"]
        characters["npc_butler"]["alive"] = False
        (self.path / "character_state.json").write_text(json.dumps({"characters": characters}), encoding="utf-8")
        events, canon, _ = self.tick_once(2)
        poison = next(e for e in events["events"] if e["event_id"] == "ev_poison")
        self.assertEqual(poison["status"], "prevented")
        self.assertIn("The poisoning plot was stopped.", [f["statement"] for f in canon["facts"]])
        self.assertNotIn("The wine was poisoned.", [f["statement"] for f in canon["facts"]])

    def test_journey_missed_event_is_recorded(self):
        from app.world_events import tick_world_events
        event = {
            "event_id": "ev_late", "event_class": "organized",
            "organizer_id": "npc_butler", "location_id": "Cellar",
            "status": "pending", "deadline_tick": 5,
            "trigger_conditions": [{"field": "story_clock.tick", "op": ">=", "value": 10}],
            "outcomes": [{"outcome_id": "late_done", "canon_facts_add": ["The late plan happened."]}],
        }
        store = {"facts": []}
        tick_world_events({"events": [event]}, {"story_clock": {"tick": 6}}, {}, store, {"locations": []})
        self.assertEqual(event["status"], "missed")
        self.assertEqual(event["resolution"], "missed")
        self.assertEqual(store["facts"], [])

    def test_journey_failure_opens_a_new_direction(self):
        from app.story.action_resolution import resolve_action
        characters = json.loads((self.path / "character_state.json").read_text(encoding="utf-8"))["characters"]
        world_config = {"action_rules": [{
            "keywords": ["spoon"], "opposition": {"name": "the maid"},
            "success_probability": 0.0,
        }]}
        result = resolve_action("accuse the maid about the spoon", characters, "del_detective",
                                world_config, {"boundary": {"locations": ["Manor", "Garden", "Cellar"]}},
                                None, world_name=self.world, turn_index=1)
        self.assertEqual(result["result"], "failure")
        self.assertTrue(result["continuation"])
        self.assertTrue(result["alternatives"])

    def test_journey_save_and_branch_keep_consequences(self):
        # Resolve the theft (organizer at Garden, player at Manor: no discovery yet),
        # then discover it via the quest journal and save.
        self.tick_once(1)
        save = self.client.post(f"/worlds/{self.world}/saves", json={"label": "after theft"})
        save_id = save.json()["save"]["save_id"]

        branch = self.client.post(f"/worlds/{self.world}/saves/{save_id}/branch",
                                  json={"new_world_name": "bellweather_branch"})
        self.assertEqual(branch.status_code, 200, branch.text)
        branch_path = self.path.parent / "bellweather_branch"
        canon = json.loads((branch_path / "world_canon_store.json").read_text(encoding="utf-8"))
        self.assertIn("A silver spoon went missing.", [f["statement"] for f in canon["facts"]])
        events = json.loads((branch_path / "world_events.json").read_text(encoding="utf-8"))
        theft = next(e for e in events["events"] if e["event_id"] == "ev_theft")
        self.assertEqual(theft["status"], "resolved")


if __name__ == "__main__":
    unittest.main()
