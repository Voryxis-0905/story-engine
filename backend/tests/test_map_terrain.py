"""Optional terrain metadata stays cheap, conservative and backward-compatible."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.prompts.world_builder import LOCATION_MAP_GENERATOR_PROMPT
from app.services.validators import validate_location_map
from app.world.map_rules import generate_location_map
from app.world.terrain import normalize_terrain_fields
from app.world.travel import visible_location_map


def map_with_place(**extra):
    return {"locations": [{
        "id": "shore", "name": "Shore", "connected_to": [],
        "is_starting_location": True, "x": 20, "y": 30,
        **extra,
    }]}


class TerrainMetadataTests(unittest.TestCase):
    def test_old_map_without_terrain_fields_remains_valid(self):
        self.assertEqual(validate_location_map(map_with_place()), [])

    def test_invalid_terrain_and_height_are_rejected_by_validation(self):
        errors = validate_location_map(map_with_place(
            terrain="volcano", elevation=True, layer="abyss",
        ))
        self.assertTrue(any("invalid terrain" in error for error in errors))
        self.assertTrue(any("elevation" in error for error in errors))
        self.assertTrue(any("invalid layer" in error for error in errors))

    def test_llm_values_are_normalized_without_an_extra_model_call(self):
        raw = json.dumps(map_with_place(
            terrain="mountain", elevation=2, layer="surface",
        ))
        with patch("app.storage.has_real_api_key", return_value=True), \
             patch("app.world.map_rules.call_llm", return_value=raw) as call:
            result = generate_location_map({}, [], {}, "test-world")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(result["locations"][0]["elevation"], 2)
        self.assertEqual(result["locations"][0]["terrain"], "mountain")
        self.assertIn('Otherwise use "unknown" or null', LOCATION_MAP_GENERATOR_PROMPT)

    def test_malformed_generated_values_do_not_claim_geography(self):
        place = {"terrain": "volcano", "elevation": True, "layer": "abyss"}
        normalize_terrain_fields(place)
        self.assertEqual(place, {"terrain": "unknown", "elevation": None, "layer": "unknown"})

    def test_hidden_place_carries_no_terrain_into_visible_map(self):
        world = {"locations": [
            {"id": "start", "name": "Start", "connected_to": ["vault"],
             "terrain": "coast", "discovery_status": "visited"},
            {"id": "vault", "name": "Vault", "connected_to": ["start"],
             "terrain": "mountain", "elevation": 2, "layer": "underground",
             "discovery_status": "unknown"},
        ]}
        visible = visible_location_map(world, "Start")
        self.assertEqual([place["id"] for place in visible["locations"]], ["start"])
        self.assertEqual(visible["locations"][0]["terrain"], "coast")
        self.assertEqual(visible["locations"][0]["connected_to"], [])


if __name__ == "__main__":
    unittest.main()
