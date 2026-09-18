"""Deterministic time-skip preview shared by API and turn commit."""
import math

UNIT_MINUTES = {"minutes": 1, "hours": 60, "days": 1440, "weeks": 10080}


def preview_time_skip(request: dict, world_config: dict, events: list, discoveries: dict) -> dict:
    amount = max(1, int(request.get("amount", 1)))
    unit = request.get("unit", "hours")
    requested_minutes = amount * UNIT_MINUTES.get(unit, 60)
    tick_minutes = max(1, int(world_config.get("time_skip_tick_minutes") or world_config.get("travel_tick_minutes") or 60))
    clock = world_config.get("story_clock") if isinstance(world_config.get("story_clock"), dict) else {}
    start_tick = max(0, int(clock.get("tick", 0) or 0))
    requested_ticks = max(1, math.ceil(requested_minutes / tick_minutes))
    known = {
        d.get("event_id"): d for d in discoveries.get("discoveries", [])
        if isinstance(d, dict) and d.get("event_id")
    }
    warnings = []
    deadlines = []
    for event in events or []:
        if not isinstance(event, dict) or event.get("status", "pending") not in ("pending", "active"):
            continue
        discovery = known.get(event.get("event_id"))
        if not discovery:
            continue
        deadline = discovery.get("known_deadline_tick")
        if not isinstance(deadline, int) or deadline <= start_tick or deadline > start_tick + requested_ticks:
            continue
        deadlines.append(deadline)
        warnings.append({
            "kind": "known_deadline", "event_id": event.get("event_id"),
            "title": event.get("quest_hint_title") or event.get("title") or "Known event",
            "deadline_tick": deadline, "ticks_away": deadline - start_tick,
        })
    policy = request.get("interruption_policy", "important_events")
    force = bool(request.get("force", False))
    granted_ticks = requested_ticks
    stopped_reason = None
    if deadlines and not force and policy != "complete":
        # Stop one logical turn before a known deadline so the warning preserves
        # player agency: their next action can still alter the event's outcome.
        granted_ticks = max(0, min(deadlines) - start_tick - 1)
        stopped_reason = "known_deadline"
    granted_minutes = min(requested_minutes, granted_ticks * tick_minutes)
    return {
        "requested_minutes": requested_minutes, "granted_minutes": granted_minutes,
        "requested_ticks": requested_ticks, "granted_ticks": granted_ticks,
        "start_tick": start_tick, "end_tick": start_tick + granted_ticks,
        "warnings": warnings, "will_interrupt": granted_ticks < requested_ticks,
        "stopped_reason": stopped_reason, "requires_confirmation": bool(warnings),
        "blocked": granted_ticks == 0,
        "activity": str(request.get("activity") or "Pass the time"),
        "interruption_policy": policy, "forced": force,
    }


def display_time_skip(request: dict, preview: dict) -> str:
    amount, unit = request.get("amount", 1), request.get("unit", "hours")
    activity = str(request.get("activity") or "Pass the time").strip()
    suffix = " (creator override)" if preview.get("forced") else ""
    return f"Time skip {amount} {unit}: {activity}{suffix}"
