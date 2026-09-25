"""A checkpoint's creator horizon must not become a turn-by-turn script."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models import CheckpointModel
from app.checkpoint_engine import advance_checkpoint_if_ready
from app.routes.builder_routes import _default_world_events, _normalize_checkpoint_branches
from app.story.checkpoint_context import playable_checkpoint_description


class CheckpointContextTests(unittest.TestCase):
    def test_new_checkpoint_uses_only_its_immediate_situation(self):
        checkpoint = {
            "description": "The Gate disaster may reveal the princess.",
            "playable_situation": "Yuto is at the station with Ren's offer unanswered.",
            "possible_developments": ["If Yuto accepts, he may enter the Gate."],
        }
        self.assertEqual(
            playable_checkpoint_description(checkpoint),
            "Yuto is at the station with Ren's offer unanswered.",
        )

    def test_legacy_world_keeps_its_existing_description(self):
        checkpoint = {"description": "Existing checkpoint text."}
        self.assertEqual(playable_checkpoint_description(checkpoint), "Existing checkpoint text.")
        checkpoint["playable_situation"] = "  "
        self.assertEqual(playable_checkpoint_description(checkpoint), "Existing checkpoint text.")

    def test_creator_update_preserves_the_new_fields(self):
        checkpoint = CheckpointModel(
            checkpoint_id="cp_0",
            description="Creator overview",
            playable_situation="A quiet morning at home.",
            possible_developments=["If the player leaves, the appointment is missed."],
            entry_location="Tokyo - Home",
        )
        serialized = checkpoint.model_dump()
        self.assertEqual(serialized["playable_situation"], "A quiet morning at home.")
        self.assertEqual(len(serialized["possible_developments"]), 1)
        self.assertEqual(serialized["entry_location"], "Tokyo - Home")

    def test_time_alone_cannot_move_protagonist_into_a_location_gated_checkpoint(self):
        timeline = {"checkpoints": [
            {"checkpoint_id": "cp_0", "description": "Morning", "sub_beats": [],
             "default_next_checkpoint_id": "cp_1"},
            {"checkpoint_id": "cp_1", "description": "Meeting", "sub_beats": [],
             "playable_situation": "The meeting can now begin.",
             "entry_location": "Tokyo - Cafe",
             "required_conditions": [{"field": "story_clock.tick", "op": ">=", "value": 3}]},
        ]}
        config = {"current_checkpoint_id": "cp_0", "protagonist_id": "pc",
                  "story_clock": {"tick": 3}}
        characters = {"pc": {"location": "Tokyo - Home"}}
        cards = {"cards": []}

        blocked = advance_checkpoint_if_ready(timeline, config, characters, cards, chapter_closed=True)
        self.assertIsNone(blocked["to_checkpoint_id"])
        self.assertEqual(config["current_checkpoint_id"], "cp_0")

        characters["pc"]["location"] = "Tokyo - Cafe - Table"
        arrived = advance_checkpoint_if_ready(timeline, config, characters, cards, chapter_closed=True)
        self.assertEqual(arrived["to_checkpoint_id"], "cp_1")
        self.assertEqual(arrived["to_checkpoint_description"], "The meeting can now begin.")
        self.assertEqual(config["current_checkpoint_id"], "cp_1")

    def test_new_checkpoint_does_not_become_a_tick_driven_canon_event(self):
        future = {"checkpoints": [{
            "checkpoint_id": "cp_1",
            "description": "The unchosen Gate disaster could unfold.",
            "playable_situation": "The offer remains unanswered.",
        }]}
        with patch('app.routes.builder_routes.read_world_file', return_value=future), \
             patch('app.world_events.load_world_events', return_value={"events": []}), \
             patch('app.world_events.save_world_events') as save_events:
            created = _default_world_events('unused', {"checkpoint_context_version": 2},
                                            {"characters": {}})
        self.assertEqual(created, 0)
        save_events.assert_not_called()

    def test_prose_alternates_become_design_ideas_not_executable_branches(self):
        checkpoint = {
            "possible_developments": ["If Jun asks, someone may answer."],
            "alternate_outcomes": [
                "If Jun does not ask, life goes on.",
                {"next_checkpoint_id": "cp_elsewhere", "conditions": []},
            ],
        }
        _normalize_checkpoint_branches(checkpoint)
        self.assertEqual(checkpoint["alternate_outcomes"], [
            {"next_checkpoint_id": "cp_elsewhere", "conditions": []},
        ])
        self.assertEqual(checkpoint["possible_developments"], [
            "If Jun asks, someone may answer.",
            "If Jun does not ask, life goes on.",
        ])

    def test_alternate_outcome_cannot_bypass_entry_location_or_apply_early(self):
        timeline = {"checkpoints": [
            {"checkpoint_id": "cp_0", "sub_beats": [],
             "alternate_outcomes": [{
                 "next_checkpoint_id": "cp_gate",
                 "apply": {"knowledge_flags": ["entered_gate"]},
             }]},
            {"checkpoint_id": "cp_gate", "entry_location": "Gate Staging Room"},
        ]}
        config = {"current_checkpoint_id": "cp_0", "protagonist_id": "pc"}
        characters = {"pc": {"location": "Home", "knowledge_flags": []}}
        cards = {"cards": []}

        blocked = advance_checkpoint_if_ready(timeline, config, characters, cards, chapter_closed=True)
        self.assertIsNone(blocked["to_checkpoint_id"])
        self.assertEqual(characters["pc"]["knowledge_flags"], [])
        self.assertEqual(config["current_checkpoint_id"], "cp_0")

        characters["pc"]["location"] = "Gate Staging Room - Entrance"
        arrived = advance_checkpoint_if_ready(timeline, config, characters, cards, chapter_closed=True)
        self.assertEqual(arrived["to_checkpoint_id"], "cp_gate")
        self.assertEqual(characters["pc"]["knowledge_flags"], ["entered_gate"])


if __name__ == "__main__":
    unittest.main()
