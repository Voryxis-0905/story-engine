"""Endgame responsibilities for Story Engine."""
from app.state_manager import eval_condition


def tick_endgame(world_config: dict, character_state: dict) -> dict:
    """
    Check if endgame conditions are met. Called after each turn.
    Returns dict with keys:
      - status_changed: bool
      - new_status: str | None (pending -> ready)
      - used_fallback: bool
      - message: str | None
    """
    story_mode = world_config.get("story_mode", "endless")
    if story_mode != "fixed_ending":
        return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}

    target = world_config.get("target_ending_scenario")
    if not target or not isinstance(target, dict):
        return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}

    if target.get("status") != "pending":
        return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}

    # Check timeout
    timeout_tick = target.get("timeout_tick")
    if timeout_tick is not None:
        clock = world_config.get("story_clock", {})
        current_tick = clock.get("tick", 0)
        if current_tick >= timeout_tick:
            target["status"] = "ready"
            target["used_fallback"] = True
            return {
                "status_changed": True,
                "new_status": "ready",
                "used_fallback": True,
                "message": "Endgame reached via timeout (fallback)."
            }

    # Check conditions
    conditions = target.get("endgame_conditions", [])
    if not conditions:
        return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}

    logic = target.get("endgame_conditions_logic", "all")

    if logic == "any":
        met = any(eval_condition(c, character_state, world_config) for c in conditions if isinstance(c, dict))
    else:
        met = all(eval_condition(c, character_state, world_config) for c in conditions if isinstance(c, dict))

    if met:
        target["status"] = "ready"
        return {
            "status_changed": True,
            "new_status": "ready",
            "used_fallback": False,
            "message": "Endgame conditions met."
        }

    return {"status_changed": False, "new_status": None, "used_fallback": False, "message": None}
