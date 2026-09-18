"""Deterministic travel planning; the narrator describes, the engine decides."""
from collections import deque
import hashlib
import math
import re


def _locations(location_map: dict) -> list:
    return [item for item in (location_map or {}).get("locations", []) if isinstance(item, dict)]


def _matches(location: dict, ref: str) -> bool:
    target = str(ref or "").strip().lower()
    return target in {str(location.get("id", "")).lower(), str(location.get("name", "")).lower()}


def find_location(location_map: dict, ref: str):
    return next((item for item in _locations(location_map) if _matches(item, ref)), None)


def extract_travel_destination(user_input: str, location_map: dict):
    text = str(user_input or "").strip()
    match = re.match(r"^(?:travel\s+to|go\s+to|đi\s+(?:đến|tới))\s+(.+?)(?:[.!]|\s+(?:via|by|bằng|theo)\s+.*)?$", text, re.I)
    if not match:
        return None
    requested = match.group(1).strip().strip("\"'")
    exact = find_location(location_map, requested)
    if exact:
        return exact
    lowered = requested.lower()
    return next((item for item in _locations(location_map)
                 if str(item.get("name", "")).lower() in lowered), None)


def _neighbors(location: dict) -> list:
    result = []
    for edge in location.get("connected_to", []) or []:
        if isinstance(edge, str):
            result.append((edge, {}))
        elif isinstance(edge, dict):
            ref = edge.get("location_id") or edge.get("to") or edge.get("id")
            if ref:
                result.append((str(ref), edge))
    return result


def find_route(location_map: dict, start_ref: str, destination_ref: str):
    start = find_location(location_map, start_ref)
    destination = find_location(location_map, destination_ref)
    if not start or not destination:
        return None
    if start.get("id") == destination.get("id"):
        return [start]
    queue = deque([(start, [start])])
    visited = {start.get("id")}
    while queue:
        current, path = queue.popleft()
        for ref, _edge in _neighbors(current):
            nxt = find_location(location_map, ref)
            if not nxt or nxt.get("id") in visited:
                continue
            next_path = path + [nxt]
            if nxt.get("id") == destination.get("id"):
                return next_path
            visited.add(nxt.get("id"))
            queue.append((nxt, next_path))
    return None


def _edge_minutes(a: dict, b: dict) -> int:
    for ref, edge in _neighbors(a):
        if _matches(b, ref) and edge.get("travel_time_minutes") is not None:
            return max(1, int(edge["travel_time_minutes"]))
    dx = float(a.get("x", 0) or 0) - float(b.get("x", 0) or 0)
    dy = float(a.get("y", 0) or 0) - float(b.get("y", 0) or 0)
    return max(10, int(round(math.hypot(dx, dy) * 3)))


def _edge_metadata(a: dict, b: dict) -> dict:
    for ref, edge in _neighbors(a):
        if _matches(b, ref):
            return edge
    return {}


def build_travel_plan(user_input: str, location_map: dict, current_location: str,
                      *, tick_minutes: int = 60, seed_key: str = ""):
    destination = extract_travel_destination(user_input, location_map)
    if not destination:
        return None
    start = find_location(location_map, current_location)
    if not start:
        return {"status": "blocked", "reason": "current_location_not_on_map",
                "destination": destination.get("name"), "elapsed_minutes": 0, "tick_advance": 1}
    route = find_route(location_map, start.get("id"), destination.get("id"))
    if not route:
        return {"status": "blocked", "reason": "no_connected_route",
                "origin": start.get("name"), "destination": destination.get("name"),
                "elapsed_minutes": 0, "tick_advance": 1, "route": []}
    legs = []
    minutes = 0
    for a, b in zip(route, route[1:]):
        metadata = _edge_metadata(a, b)
        leg_minutes = _edge_minutes(a, b)
        minutes += leg_minutes
        legs.append({
            "from": a.get("name"), "to": b.get("name"),
            "travel_time_minutes": leg_minutes,
            "danger": max(0.0, min(1.0, float(metadata.get("danger", 0) or 0))),
            "tags": metadata.get("tags", []) if isinstance(metadata.get("tags", []), list) else [],
        })
    result = {
        "status": "arrived", "reason": "route_available",
        "origin": start.get("name"), "destination": destination.get("name"),
        "destination_id": destination.get("id"),
        "route": [item.get("name") for item in route],
        "legs": legs,
        "elapsed_minutes": minutes,
        "tick_advance": max(1, math.ceil(minutes / max(1, tick_minutes))),
        "narration_mode": "brief" if minutes <= 30 else "timeskip" if minutes <= 480 else "journey",
    }
    for index, leg in enumerate(legs):
        danger = leg["danger"]
        if danger <= 0:
            continue
        digest = hashlib.sha256(f"{seed_key}|{index}|{leg['from']}|{leg['to']}".encode("utf-8")).hexdigest()
        roll = int(digest[:12], 16) / float(0xFFFFFFFFFFFF)
        if roll < danger:
            elapsed_before = sum(previous["travel_time_minutes"] for previous in legs[:index])
            elapsed = elapsed_before + max(1, leg["travel_time_minutes"] // 2)
            result.update(
                status="interrupted", reason="travel_encounter",
                destination_id=None, stopped_at=leg["from"],
                elapsed_minutes=elapsed,
                tick_advance=max(1, math.ceil(elapsed / max(1, tick_minutes))),
                interrupted_leg=leg, danger_roll=round(roll, 6),
            )
            break
    return result


def advance_clock_minutes(clock: dict, minutes: int) -> None:
    if not isinstance(clock, dict) or minutes <= 0:
        return
    current = clock.get("minute_of_day")
    if not isinstance(current, int):
        current = {"morning": 480, "afternoon": 840, "evening": 1140, "night": 1380}.get(
            str(clock.get("time_of_day", "morning")).lower(), 480
        )
    total = current + int(minutes)
    days, minute = divmod(total, 1440)
    clock["minute_of_day"] = minute
    clock["elapsed_minutes"] = int(clock.get("elapsed_minutes", 0) or 0) + int(minutes)
    day = max(1, int(clock.get("day", 1) or 1) + days)
    month = max(1, int(clock.get("month", 1) or 1))
    year = max(1, int(clock.get("year", 1) or 1))
    while day > 30:
        day -= 30
        month += 1
    while month > 12:
        month -= 12
        year += 1
    clock["day"], clock["month"], clock["year"] = day, month, year
    hour = minute // 60
    clock["time_of_day"] = "morning" if 5 <= hour < 12 else "afternoon" if hour < 17 else "evening" if hour < 22 else "night"
