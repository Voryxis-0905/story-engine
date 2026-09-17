import os
import json
import sys

# Mock read_runtime_config and read_world_runtime_override BEFORE importing backend.main
import backend.main

def mock_read_runtime_config():
    return {"fallback_chain": [{"provider": "openrouter", "api_key": "app_key", "model": "model_1"}]}

def mock_read_world_override(world_name):
    if world_name == "override_world":
        return {"fallback_chain": [{"provider": "groq", "api_key": "world_key", "model": "model_2"}]}
    return {}

backend.main.read_runtime_config = mock_read_runtime_config
backend.main.read_world_runtime_override = mock_read_world_override

from backend.main import get_effective_fallback_chain, CharacterModel, WorldConfigUpdate, CharacterStateChange

def run_tests():
    print("Testing CharacterModel schema...")
    char = CharacterModel(name="Hero")
    assert char.relationships == {}
    assert char.age == ""
    
    char = CharacterModel(name="Hero", relationships={"Villain": "Enemy"}, age="25")
    assert char.relationships["Villain"] == "Enemy"
    assert char.age == "25"

    print("Testing WorldConfigUpdate schema...")
    update = WorldConfigUpdate(story_clock={"day": 2, "time": "Night"}, foreshadowing_tracker=["Hint 1"])
    assert update.story_clock["day"] == 2
    assert "Hint 1" in update.foreshadowing_tracker

    print("Testing CharacterStateChange schema...")
    change = CharacterStateChange(relationships_update={"Ally": "Friend"}, age="26")
    assert change.relationships_update["Ally"] == "Friend"
    assert change.age == "26"

    print("Testing effective_fallback_chain...")
    chain = get_effective_fallback_chain()
    assert len(chain) == 1
    assert chain[0]["api_key"] == "app_key"
    
    chain = get_effective_fallback_chain("override_world")
    assert len(chain) == 1
    assert chain[0]["api_key"] == "world_key"
    
    chain = get_effective_fallback_chain("no_override")
    assert len(chain) == 1
    assert chain[0]["api_key"] == "app_key"

    print("All tests passed!")

if __name__ == "__main__":
    run_tests()
