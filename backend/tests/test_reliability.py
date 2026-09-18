"""Regression tests using temporary worlds and mocked AI only."""
import json
import os
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from fastapi.testclient import TestClient
from app import storage, persistence, engine, chapter_generator
from app.routes import world_routes
from app.checkpoint_engine import check_map_based_restrictions


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.data = Path(temporary.name)
        worlds = self.data / 'worlds'
        worlds.mkdir()
        for module, name, value in (
            (storage, 'WORLDS_DIR', str(worlds)),
            (main, 'WORLDS_DIR', str(worlds)),
            (world_routes, 'WORLDS_DIR', str(worlds)),
            (storage, 'RUNTIME_CONFIG_PATH', str(self.data / 'runtime_config.json')),
        ):
            self.enterContext(patch.object(module, name, value))
        self.enterContext(patch.dict(os.environ, {'OPENROUTER_API_KEY': ''}))
        self.enterContext(patch('requests.sessions.Session.send', side_effect=AssertionError('Real HTTP forbidden in tests')))
        self.client = TestClient(main.app)
        self.world = 'reliability_test'
        self.path = worlds / self.world
        self.assertEqual(self.client.post(f'/worlds/{self.world}/seed-demo').status_code, 200)
        self.cfg = self.read('world_config.json')
        self.cfg.update(protagonist_id='char_xueli', psychology_enabled=False)
        self.write('world_config.json', self.cfg)
        self.enterContext(patch.object(main, 'call_llm', side_effect=self.fake_llm))

    @staticmethod
    def fake_llm(system_prompt, user_prompt, user_input_for_mock='', mock_response=None, world_name=None, role=None):
        if system_prompt == main.PLANNER_SYSTEM_PROMPT:
            return main.mock_planner_response(user_input_for_mock)
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            return main.mock_narrator_response(user_input_for_mock)
        return main.mock_consistency_checker_response()

    def read(self, filename):
        return json.loads((self.path / filename).read_text(encoding='utf-8'))

    def write(self, filename, value):
        storage.write_world_file(str(self.path), filename, value)

    def post(self, endpoint, payload=None):
        return self.client.post(f'/worlds/{self.world}/{endpoint}', json=payload or {})

    def setup_event(self):
        self.write('location_map.json', {'locations': [{'id': 'village', 'name': 'Village', 'tags': ['safe']}]})
        self.write('world_canon_store.json', {'facts': []})
        self.write('world_events.json', {'events': [{
            'event_id': 'raid', 'status': 'pending',
            'trigger_conditions': [{'field': 'story_clock.tick', 'op': '>=', 'value': 1}],
            'outcomes': [{'outcome_id': 'damaged', 'canon_facts_add': ['The village was damaged.'],
                          'world_flags_set': {'raid_done': True},
                          'location_effects': [{'location_id': 'village', 'tags_add': ['ruined'], 'tags_remove': ['safe']}]}],
        }]})

    def test_event_consequences_persist_and_do_not_repeat(self):
        self.setup_event()
        for _ in range(2):
            self.assertEqual(self.post('chapter/continue', {'user_input': 'Observe quietly.'}).status_code, 200)
        self.assertEqual(self.read('world_events.json')['events'][0]['status'], 'resolved')
        self.assertEqual([f['statement'] for f in self.read('world_canon_store.json')['facts']], ['The village was damaged.'])
        self.assertEqual(self.read('location_map.json')['locations'][0]['tags'], ['ruined'])
        self.assertTrue(self.read('world_config.json')['world_flags']['raid_done'])
        self.assertEqual(self.read('world_config.json')['story_clock']['tick'], 2)
        self.assertEqual(self.read('world_events.json')['events'][0]['resolved_at_tick'], 1)

    def test_late_failure_does_not_resolve_events_or_change_world(self):
        self.setup_event()
        before = {p.name: p.read_bytes() for p in self.path.glob('*.json')}
        with patch.object(chapter_generator, 'check_rolling_summary_trigger', side_effect=RuntimeError('late failure')):
            with self.assertRaisesRegex(RuntimeError, 'late failure'):
                self.post('chapter/continue', {'user_input': 'Observe.'})
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.path.glob('*.json')})

    def test_batch_write_failure_restores_original_bytes_and_absent_files(self):
        original = (self.path / 'world_config.json').read_bytes()
        real_replace = os.replace
        def fail_one_replace(src, dest):
            if Path(dest).name == 'chapters.json':
                raise OSError('simulated replacement failure')
            return real_replace(src, dest)
        with patch.object(persistence.os, 'replace', side_effect=fail_one_replace):
            with self.assertRaises(OSError):
                persistence.commit_world_files(str(self.path), {
                    'world_config.json': {**self.cfg, 'display_name': 'changed'},
                    'new_file.json': {'value': 1},
                    'chapters.json': self.read('chapters.json'),
                })
        self.assertEqual((self.path / 'world_config.json').read_bytes(), original)
        self.assertFalse((self.path / 'new_file.json').exists())
        self.assertEqual(list(self.path.glob('*.tmp')), [])

    def test_batch_validates_all_files_before_writing(self):
        original = (self.path / 'world_config.json').read_bytes()
        with self.assertRaises(Exception):
            persistence.commit_world_files(str(self.path), {
                'world_config.json': {**self.cfg, 'display_name': 'changed'},
                'character_state.json': {'characters': {'bad': {}}},
            })
        self.assertEqual((self.path / 'world_config.json').read_bytes(), original)

    def test_save_restore_and_branch_include_events_and_consequences(self):
        self.setup_event()
        save = self.post('saves', {'label': 'before raid'}).json()['save']['save_id']
        self.assertTrue((self.path / 'saves' / save / 'world_events.json').exists())
        self.post('chapter/continue', {'user_input': 'Observe.'})
        self.assertEqual(self.post(f'saves/{save}/restore').status_code, 200)
        self.assertEqual(self.read('world_events.json')['events'][0]['status'], 'pending')
        self.assertEqual(self.read('world_canon_store.json')['facts'], [])
        self.assertEqual(self.read('location_map.json')['locations'][0]['tags'], ['safe'])
        response = self.post(f'saves/{save}/branch', {'new_world_name': 'branch_test'})
        self.assertEqual(response.status_code, 200, response.text)
        branched = json.loads((self.path.parent / 'branch_test' / 'world_events.json').read_text(encoding='utf-8'))
        self.assertEqual(branched, self.read('world_events.json'))

    def test_legacy_save_does_not_keep_future_events(self):
        self.setup_event()
        save = self.post('saves', {'label': 'legacy'}).json()['save']['save_id']
        (self.path / 'saves' / save / 'world_events.json').unlink()
        self.post('chapter/continue', {'user_input': 'Observe.'})
        response = self.post(f'saves/{save}/restore')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.read('world_events.json'), {'events': []})
        safety = response.json()['safety_save_id']
        backup = json.loads((self.path / 'saves' / safety / 'world_events.json').read_text(encoding='utf-8'))
        self.assertEqual(backup['events'][0]['status'], 'resolved')

    def test_map_status_agrees_with_movement_rules(self):
        characters = self.read('character_state.json')
        characters['characters']['char_xueli']['power_stat'].update(exp=100, realm='Expert')
        self.write('character_state.json', characters)
        for requirements, unlocked in [({'unlock_exp': 10}, True), ({'unlock_exp': 101}, False),
                                       ({'unlock_realm': 'expert'}, True),
                                       ({'unlock_checkpoint_id': 'cp_0'}, True),
                                       ({'unlock_checkpoint_id': 'cp_4'}, False), ({}, True)]:
            with self.subTest(requirements=requirements):
                location_map = {'locations': [{'id': 'gate', 'name': 'Gate', **requirements}]}
                self.write('location_map.json', location_map)
                status = self.client.get(f'/worlds/{self.world}/location-map/status').json()['locations'][0]
                violations = check_map_based_restrictions({'characters': {'char_xueli': {'location': 'Gate'}}},
                                                          location_map, characters['characters'], self.cfg)
                self.assertEqual(status['is_unlocked'], not violations)
                self.assertEqual(status['is_unlocked'], unlocked)

    def test_clear_api_key_clears_both_aliases_and_preserves_model(self):
        self.client.put('/runtime-config', json={'api_key': 'not-a-real-test-key', 'model_name': 'test/model'})
        response = self.client.delete('/runtime-config/api-key')
        self.assertFalse(response.json()['has_api_key'])
        persisted = json.loads((self.data / 'runtime_config.json').read_text(encoding='utf-8'))
        self.assertEqual(persisted['api_key'], '')
        self.assertEqual(persisted['openrouter_api_key'], '')
        self.assertEqual(persisted['fallback_chain'], [])
        self.assertEqual(persisted['model_name'], 'test/model')

    def test_world_key_takes_priority_over_app_fallback_chain(self):
        self.client.put('/runtime-config', json={'api_key': 'app-placeholder', 'model_name': 'app/model'})
        self.client.put(f'/worlds/{self.world}/runtime-config', json={
            'openrouter_api_key': 'world-placeholder', 'openrouter_model': 'world/model',
        })
        selected = storage.get_effective_fallback_chain(self.world)
        self.assertEqual(selected[0]['api_key'], 'world-placeholder')
        self.assertEqual(selected[0]['model'], 'world/model')
        self.client.delete(f'/worlds/{self.world}/runtime-config/api-key')
        self.assertEqual(storage.get_effective_fallback_chain(self.world)[0]['api_key'], 'app-placeholder')

    def prepare_ending(self):
        self.cfg.update(story_mode='fixed_ending', lifecycle_status='endgame_pending',
                        target_ending_scenario={'summary': 'A new beginning', 'status': 'ready'})
        self.write('world_config.json', self.cfg)

    def test_epilogue_choices_load_prompt(self):
        self.prepare_ending()
        with patch.object(engine, 'call_llm', return_value=json.dumps({'choices': ['Stay', 'Leave']})):
            response = self.post('chapter/generate-epilogue-choices')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['choices'], ['Stay', 'Leave'])

    def test_epilogue_persists_is_idempotent_and_stops_continuation(self):
        self.prepare_ending()
        with patch.object(engine, 'call_llm', return_value=json.dumps({'epilogue': 'They chose a new life.'})) as model:
            for _ in range(2):
                response = self.post('chapter/generate-epilogue', {'chosen_choice': 'Leave'})
                self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(model.call_count, 1)
        history = self.read('chapters.json')
        self.assertEqual(history['epilogue']['text'], 'They chose a new life.')
        self.assertEqual(sum(c.get('kind') == 'epilogue' for c in history['chapters']), 1)
        self.assertEqual(self.read('world_config.json')['lifecycle_status'], 'completed')
        self.assertEqual(self.post('chapter/continue', {'user_input': 'Continue'}).status_code, 409)

    def test_empty_epilogue_does_not_complete_story(self):
        self.prepare_ending()
        with patch.object(engine, 'call_llm', return_value='{"epilogue": ""}'):
            response = self.post('chapter/generate-epilogue', {'chosen_choice': 'Leave'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(self.read('world_config.json')['lifecycle_status'], 'endgame_pending')
        self.assertNotIn('epilogue', self.read('chapters.json'))

    def test_epilogue_requires_endgame(self):
        with patch.object(engine, 'call_llm') as model:
            self.assertEqual(self.post('chapter/generate-epilogue', {'chosen_choice': 'Leave'}).status_code, 409)
            model.assert_not_called()

    def test_concurrent_turns_do_not_overwrite_each_other(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.post('chapter/continue', {'user_input': 'Observe.'}), range(2)))
        self.assertEqual([r.status_code for r in responses], [200, 200])
        turns = self.read('chapters.json')['chapters']
        self.assertEqual(len(turns), 2)
        self.assertEqual(len({(t['chapter_index'], t['turn_index']) for t in turns}), 2)


if __name__ == '__main__':
    unittest.main()
