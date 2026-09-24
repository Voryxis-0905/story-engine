"""Hidden places must not leak through the map or the travel preview.

The engine routes over the *full* location map: real travel legitimately passes
through a place the protagonist has not discovered, and the journey still has to
be described. What must never happen is the player reading that place's name.

The failure these tests pin down: `POST /travel/preview` used to return
`route: ["Start", "Hidden Vault", "City"]` for a known destination behind an
`unknown` waypoint. The destination check alone did not prevent it, because the
leak was in the *intermediate* stop - and the same names appeared in `legs`.

Contract under test:
  * the visible map never contains a hidden place, nor an edge naming one;
  * a preview may pass through a hidden place (truthful availability), but the
    response must not contain its name, description or tags;
  * an undiscovered destination stays blocked;
  * the map and the preview agree, so the player is never told a journey is
    impossible when the engine would actually allow it.
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
from app import storage
from app.routes import world_routes
from app.world.travel import (
    find_route,
    is_hidden,
    preview_travel,
    scrub_preview_for_player,
    visible_location_map,
)

HIDDEN_NAME = "Hidden Vault"


def _location(loc_id, name, x, y, links, discovery="discovered", **extra):
    return {
        "id": loc_id, "name": name, "x": x, "y": y,
        "connected_to": links, "discovery_status": discovery,
        "is_unlocked": True, "tags": extra.pop("tags", ["indoor"]),
        **extra,
    }


def chain_map():
    """Start -> Hidden Vault -> City, plus a sealed branch off the vault.

    Both extra places are hidden, so a single leak source is not enough to pass:
    the route goes through one and the vault connects to the other.
    """
    return {"locations": [
        _location("start", "Start", 10, 50, ["vault"], tags=["safe"]),
        _location("vault", HIDDEN_NAME, 50, 50, ["city", "reliquary"],
                  discovery="unknown", tags=["secret"], description="A vault of secrets."),
        _location("reliquary", "Reliquary", 50, 85, ["vault"],
                  discovery="creator_only", tags=["secret"]),
        _location("city", "City", 90, 50, ["vault"], tags=["urban"]),
    ]}


class TravelPreviewPrivacy(unittest.TestCase):
    """Pure-function level: the projection and the scrubber."""

    def test_visible_map_drops_hidden_places_and_their_edges(self):
        visible = visible_location_map(chain_map(), "Start")
        ids = {loc["id"] for loc in visible["locations"]}
        self.assertEqual(ids, {"start", "city"})

        # A surviving place must not keep an edge pointing at a hidden one, or
        # the routing layer could step onto it and narrate its name.
        kept_edges = {edge for loc in visible["locations"] for edge in loc["connected_to"]}
        self.assertEqual(kept_edges, set())

    def test_the_place_the_protagonist_stands_in_is_kept_even_when_hidden(self):
        # A character always knows where they are; hiding their own room would
        # be a bug in the other direction.
        world = {"locations": [
            _location("start", "Start", 10, 50, [], discovery="discovered"),
            _location("pocket", "Pocket Realm", 50, 50, ["start"], discovery="unknown"),
        ]}
        visible = visible_location_map(world, "Pocket Realm")
        self.assertEqual({loc["id"] for loc in visible["locations"]}, {"start", "pocket"})

    def test_scrubber_keeps_the_journey_but_removes_the_route_shape(self):
        world = chain_map()
        result = preview_travel(world, "Start", "City")
        # The engine really does route through the vault - this is the truth the
        # preview is not allowed to contradict.
        self.assertEqual(result["status"], "available")
        self.assertIn(HIDDEN_NAME, result["route"])

        scrubbed = scrub_preview_for_player(result, world)
        self.assertEqual(scrubbed["status"], "available")
        self.assertNotIn(HIDDEN_NAME, scrubbed["route"])

        # Redacting the *names* is not enough. `["Start", "Unknown location",
        # "City"]` still tells the player there is exactly one uncharted stop,
        # and the per-leg tags carried `secret_tunnel`. The shape is withheld.
        self.assertTrue(scrubbed["route_redacted"])
        self.assertEqual(scrubbed["route"], [])
        self.assertEqual(scrubbed["legs"], [])

        # Timing is not a secret and must survive: a player deciding whether to
        # travel needs the cost, not the waypoint's name.
        self.assertEqual(scrubbed["elapsed_minutes"], result["elapsed_minutes"])

        blob = json.dumps(scrubbed, ensure_ascii=False)
        self.assertNotIn(HIDDEN_NAME, blob)
        self.assertNotIn("Reliquary", blob)
        self.assertNotIn("A vault of secrets.", blob)
        self.assertNotIn("secret", blob)

    def test_one_and_two_hidden_stops_look_identical_to_the_player(self):
        # The stop count is itself information. If a one-stop route and a
        # two-stop route produced differently shaped responses, the player could
        # count hidden places without ever learning a name.
        one = scrub_preview_for_player(preview_travel(chain_map(), "Start", "City"), chain_map())

        two_world = {"locations": [
            _location("start", "Start", 5, 50, ["v1"], discovery="discovered"),
            _location("v1", "Vault One", 30, 50, ["start", "v2"], discovery="unknown"),
            _location("v2", "Vault Two", 60, 50, ["v1", "city"], discovery="creator_only"),
            _location("city", "City", 95, 50, ["v2"], discovery="discovered"),
        ]}
        two = scrub_preview_for_player(preview_travel(two_world, "Start", "City"), two_world)

        for field in ("route", "legs"):
            self.assertEqual(one[field], [], f"{field} must be empty for a redacted route")
            self.assertEqual(two[field], [], f"{field} must be empty for a redacted route")
        self.assertEqual(len(one["route"]), len(two["route"]))
        self.assertEqual(len(one["legs"]), len(two["legs"]))
        self.assertEqual(one["route_redacted"], two["route_redacted"])
        blob = json.dumps(two, ensure_ascii=False)
        for secret in ("Vault One", "Vault Two", "v1", "v2"):
            self.assertNotIn(secret, blob, f"{secret} leaked: {blob}")

    def test_edge_tags_of_a_hidden_route_are_withheld(self):
        # Tags describe the ground being crossed. `secret_tunnel` names the kind
        # of hidden route, so it is metadata about the hidden place even though
        # no place name appears in it.
        world = {"locations": [
            {"id": "start", "name": "Start", "x": 10, "y": 50, "discovery_status": "discovered",
             "connected_to": [{"location_id": "vault", "travel_time_minutes": 30,
                               "tags": ["secret_tunnel"]}]},
            {"id": "vault", "name": "Hidden Vault", "x": 50, "y": 50, "discovery_status": "unknown",
             "connected_to": [{"location_id": "city", "travel_time_minutes": 40,
                               "tags": ["hidden_passage"], "danger": 0.9}]},
            {"id": "city", "name": "City", "x": 95, "y": 50, "discovery_status": "discovered",
             "connected_to": []},
        ]}
        scrubbed = scrub_preview_for_player(preview_travel(world, "Start", "City"), world)

        self.assertTrue(scrubbed["route_redacted"])
        self.assertEqual(scrubbed["legs"], [])
        self.assertEqual(scrubbed["risk"]["known_tags"], [])
        blob = json.dumps(scrubbed, ensure_ascii=False)
        for tag in ("secret_tunnel", "hidden_passage"):
            self.assertNotIn(tag, blob, f"hidden edge tag leaked: {blob}")
        # The player still learns the trip is dangerous - that is their business,
        # not the hidden place's.
        self.assertEqual(scrubbed["risk"]["level"], "high")

    def test_scrubber_leaves_an_all_visible_preview_untouched(self):
        world = {"locations": [
            _location("a", "A", 10, 50, ["b"]),
            _location("b", "B", 60, 50, ["a"]),
        ]}
        result = preview_travel(world, "A", "B")
        self.assertEqual(scrub_preview_for_player(result, world), result)
        # A visible route keeps its stop-by-stop preview.
        self.assertEqual(result["route"], ["A", "B"])
        self.assertNotIn("route_redacted", result)

    def test_a_secret_place_cannot_be_routed_to_at_all(self):
        # The projection removes it, so no route can reach it - the map and the
        # preview agree that it is not a destination.
        visible = visible_location_map(chain_map(), "Start")
        self.assertIsNone(find_route(visible, "start", "vault"))
        self.assertIsNone(find_route(visible, "start", "reliquary"))


class TravelPreviewRouteEndpoints(unittest.TestCase):
    """Endpoint level: what the client actually receives."""

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

        self.world = "leaky_case"
        path = worlds / self.world
        path.mkdir(parents=True, exist_ok=True)
        protagonist = {
            "name": "Tester", "location": "Start", "affinity": {},
            "power_stat": {"realm": "", "exp": 0, "sub_stats": {}, "known_skills": []},
            "knowledge_flags": [], "inventory": [], "karma": 0, "alive": True,
            "relationships": {}, "age": "", "traits": {}, "status_effects": [],
        }
        files = {
            "world_config.json": {
                "protagonist_id": "pc", "current_checkpoint_id": "cp_0",
                "language": "en", "story_clock": {"tick": 0},
                "travel_tick_minutes": 60, "story_mode": "endless",
            },
            "character_state.json": {"characters": {"pc": protagonist}},
            "location_map.json": chain_map(),
            "canon_timeline.json": {"checkpoints": [{
                "checkpoint_id": "cp_0", "description": "start",
                "boundary": {"locations": ["Start", "City", HIDDEN_NAME],
                             "allowed_characters": ["pc"]},
            }]},
            "card_registry.json": {"cards": []},
            "chapters.json": {"chapters": [], "running_summary": ""},
        }
        for filename, data in files.items():
            (path / filename).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.client = TestClient(main.app)

    def _preview(self, destination):
        response = self.client.post(
            f"/worlds/{self.world}/travel/preview", json={"destination": destination}
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_preview_through_an_unknown_waypoint_does_not_name_it(self):
        payload = self._preview("City")

        # Truthful: the journey is possible, because real travel performs it.
        self.assertEqual(payload["status"], "available")
        self.assertEqual(payload["destination"], "City")

        blob = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(HIDDEN_NAME, blob, f"hidden name leaked: {blob}")
        self.assertNotIn("Reliquary", blob)

        # The route's shape must not be reported at all: the old assertion here
        # (`["Start", "Unknown location", "City"]`) was itself the leak, because
        # it announced one hidden waypoint and spelled out each leg.
        self.assertTrue(payload["route_redacted"], f"expected redaction: {blob}")
        self.assertEqual(payload["route"], [])
        self.assertEqual(payload["legs"], [])
        self.assertGreater(payload["elapsed_minutes"], 0, "the trip cost is still the player's business")

    def test_map_status_does_not_leak_the_route_it_previews(self):
        # The map endpoint must obey the same rule as /travel/preview. A route
        # hidden in one place and published in the other is not hidden.
        response = self.client.get(f"/worlds/{self.world}/location-map/status")
        self.assertEqual(response.status_code, 200)
        payload = response.json()

        city = next(loc for loc in payload["locations"] if loc.get("name") == "City")
        self.assertEqual(city["route_preview"], [], "a redacted route must not be itemised here either")
        if city.get("route_redacted") is not None:
            self.assertNotIn(HIDDEN_NAME, json.dumps(city, ensure_ascii=False))

        blob = json.dumps(payload, ensure_ascii=False)
        self.assertNotIn(HIDDEN_NAME, blob, f"hidden name leaked from map status: {blob}")
        self.assertNotIn("Reliquary", blob)
        # No filled-in stop list may survive anywhere in the payload.
        for loc in payload["locations"]:
            self.assertNotIn("Unknown location", json.dumps(loc, ensure_ascii=False),
                             "a placeholder stop still reveals that a stop exists")

    def test_an_undiscovered_destination_stays_blocked_and_unnamed(self):
        payload = self._preview(HIDDEN_NAME)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["destination"], "Unknown location")
        self.assertEqual(payload["route"], [])
        self.assertEqual(payload["legs"], [])
        self.assertNotIn(HIDDEN_NAME, json.dumps(payload, ensure_ascii=False))

    def test_the_map_endpoint_hides_the_same_places(self):
        response = self.client.get(f"/worlds/{self.world}/location-map/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        blob = json.dumps(body, ensure_ascii=False)

        self.assertNotIn(HIDDEN_NAME, blob)
        self.assertNotIn("Reliquary", blob)
        names = {loc["name"] for loc in body["locations"]}
        self.assertEqual(names, {"Start", "City"})

    def test_preview_and_map_do_not_contradict_on_a_reachable_destination(self):
        """The bug this guards: map says go, preview says no (or the reverse)."""
        body = self.client.get(f"/worlds/{self.world}/location-map/status").json()
        city = next(loc for loc in body["locations"] if loc["name"] == "City")
        preview = self._preview("City")
        self.assertTrue(city["is_reachable"])
        self.assertEqual(preview["status"], "available")


if __name__ == "__main__":
    unittest.main()
