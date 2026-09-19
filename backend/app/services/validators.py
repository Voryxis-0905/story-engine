"""
Validators for story config, location map, and world bundle integrity.
Part of Cụm E – Checkpoint linter (Mục 2.2).

Chạy deterministic (không gọi LLM), phát hiện sớm lỗi cấu trúc ngay sau khi
story_config / location_map được generate trong builder flow.
Schema dựa trên codebase thực tế (xem 9.1 trong design doc v2):
  - location_map.json: "locations" là ARRAY; mỗi location có id/name/connected_to,
    unlock bằng unlock_realm / unlock_exp / unlock_checkpoint_id,
    starting location đánh dấu bằng is_starting_location: true.
  - canon_timeline.json: "checkpoints" là array; mỗi checkpoint có
    checkpoint_id / description / required_conditions (list dict {field, op, value})
    / boundary.locations (tên location) / cards_unlocked / default_next_checkpoint_id.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

VALID_OPS = {">=", "<=", "==", "!=", ">", "<", "contains", "in"}
VALID_FIELD_PREFIXES = ("story_clock.", "world_flags.")
REQUIRED_LOCATION_FIELDS = ("id", "name", "connected_to")
REQUIRED_CHECKPOINT_FIELDS = ("checkpoint_id", "description")


def _iter_locations(location_map: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Normalize location_map.locations (array) thành list dict."""
    locations = location_map.get("locations", []) if isinstance(location_map, dict) else []
    if not isinstance(locations, list):
        return []
    return [loc for loc in locations if isinstance(loc, dict)]


def validate_location_map(location_map: Dict[str, Any]) -> List[str]:
    """
    Validate location_map schema và cross-references.

    Checks:
      - "locations" phải là array
      - mỗi location có đủ id / name / connected_to
      - connected_to trỏ đến id location tồn tại, không self-reference
      - unlock_exp phải là int >= 0; unlock_realm / unlock_checkpoint_id là str hoặc null
      - ít nhất 1 location đánh dấu is_starting_location: true
    Returns list error (rỗng = valid).
    """
    errors: List[str] = []

    if not isinstance(location_map, dict):
        errors.append("location_map must be a dict")
        return errors

    locations = _iter_locations(location_map)
    if not locations and location_map.get("locations") is not None:
        errors.append("location_map.locations must be a list")
        return errors

    location_ids = {loc.get("id") for loc in locations if isinstance(loc.get("id"), str)}

    for i, loc in enumerate(locations):
        loc_id = loc.get("id")
        label = f"Location[{i}] (id={loc_id!r})" if loc_id else f"Location[{i}]"

        for field in REQUIRED_LOCATION_FIELDS:
            if field not in loc:
                errors.append(f"{label} missing required field '{field}'")

        connected = loc.get("connected_to")
        if connected is not None and not isinstance(connected, list):
            errors.append(f"{label}: 'connected_to' must be a list")
        elif isinstance(connected, list):
            for target in connected:
                target_id = target if isinstance(target, str) else (
                    target.get("to") or target.get("location_id") or target.get("id")
                    if isinstance(target, dict) else None
                )
                if not isinstance(target_id, str):
                    errors.append(f"{label}: connected_to entry needs a string target, got {target!r}")
                elif target_id not in location_ids:
                    errors.append(
                        f"{label} references non-existent location id '{target_id}' in connected_to"
                    )
                if isinstance(target, dict):
                    minutes = target.get("travel_time_minutes")
                    if minutes is not None and (not isinstance(minutes, (int, float)) or minutes <= 0):
                        errors.append(f"{label}: travel_time_minutes must be positive")
                    danger = target.get("danger")
                    if danger is not None and (not isinstance(danger, (int, float)) or not 0 <= danger <= 1):
                        errors.append(f"{label}: danger must be between 0 and 1")
            targets = [
                target if isinstance(target, str) else target.get("to") or target.get("location_id") or target.get("id")
                for target in connected if isinstance(target, (str, dict))
            ]
            if isinstance(loc_id, str) and loc_id in targets:
                errors.append(f"{label} cannot be connected to itself")

        unlock_exp = loc.get("unlock_exp")
        if unlock_exp is not None and not isinstance(unlock_exp, (int, float)):
            errors.append(f"{label}: 'unlock_exp' must be a number, got {unlock_exp!r}")
        elif isinstance(unlock_exp, (int, float)) and unlock_exp < 0:
            errors.append(f"{label}: 'unlock_exp' must be >= 0, got {unlock_exp!r}")

        unlock_realm = loc.get("unlock_realm")
        if unlock_realm is not None and not isinstance(unlock_realm, str):
            errors.append(f"{label}: 'unlock_realm' must be a string or null, got {unlock_realm!r}")

        unlock_cp = loc.get("unlock_checkpoint_id")
        if unlock_cp is not None and not isinstance(unlock_cp, str):
            errors.append(
                f"{label}: 'unlock_checkpoint_id' must be a string or null, got {unlock_cp!r}"
            )

        visibility = loc.get("discovery_status", "discovered")
        if visibility not in {"unknown", "rumored", "discovered", "visited", "creator_only"}:
            errors.append(f"{label}: invalid discovery_status {visibility!r}")

    starting = [loc for loc in locations if loc.get("is_starting_location") is True]
    if not starting:
        errors.append(
            "No starting location found (at least one location must have is_starting_location: true)"
        )

    return errors


def _check_condition_fields(
    conditions: List[Any],
    checkpoint_label: str,
    character_state: Optional[Dict[str, Any]],
    errors: List[str],
) -> None:
    """Validate required_conditions (list dict {field, op, value})."""
    for j, cond in enumerate(conditions):
        if not isinstance(cond, dict):
            errors.append(
                f"{checkpoint_label}: required_condition at index {j} must be a dict"
            )
            continue

        field = cond.get("field")
        op = cond.get("op")

        if not isinstance(field, str) or not field.strip():
            errors.append(
                f"{checkpoint_label}: required_condition at index {j} missing valid 'field'"
            )
        else:
            base = field.split(".", 1)[0].strip()
            if character_state is not None:
                known = character_state.get("characters", {})
                if (
                    not field.startswith(VALID_FIELD_PREFIXES)
                    and base not in known
                ):
                    errors.append(
                        f"{checkpoint_label}: required_condition '{field}' references non-existent "
                        f"character '{base}' in character_state"
                    )

        if not isinstance(op, str) or op not in VALID_OPS:
            errors.append(
                f"{checkpoint_label}: required_condition '{field or '?'}' has invalid 'op' {op!r}. "
                f"Valid ops: {', '.join(sorted(VALID_OPS))}"
            )

        if "value" not in cond:
            errors.append(
                f"{checkpoint_label}: required_condition '{field or '?'}' missing 'value'"
            )


def checkpoint_linter(
    canon_timeline: Dict[str, Any],
    location_map: Dict[str, Any],
    character_state: Optional[Dict[str, Any]] = None,
    card_registry: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Validate canon_timeline consistency.

    Checks:
      - "checkpoints" phải là array
      - mỗi checkpoint có checkpoint_id / description, không trùng id
      - boundary.locations trỏ đến location tồn tại (match theo name hoặc id)
      - cards_unlocked trỏ đến card id tồn tại (nếu truyền card_registry)
      - default_next_checkpoint_id trỏ đến checkpoint tồn tại (nếu không null)
      - required_conditions: field base là character tồn tại HOẶC prefix story_clock./world_flags.;
        op thuộc bộ hợp lệ; có đủ value
      - WARNING: tất cả location trong cùng checkpoint nên cùng zone-prefix
    Returns list error (rỗng = valid).
    """
    errors: List[str] = []

    checkpoints = canon_timeline.get("checkpoints") if isinstance(canon_timeline, dict) else None
    if not isinstance(checkpoints, list):
        errors.append("canon_timeline must have a 'checkpoints' list")
        return errors

    cp_ids = {cp.get("checkpoint_id") for cp in checkpoints if isinstance(cp.get("checkpoint_id"), str)}

    loc_map_by_name = {loc.get("name"): loc for loc in _iter_locations(location_map)}
    loc_map_by_id = {loc.get("id"): loc for loc in _iter_locations(location_map)}
    loc_names = set(loc_map_by_name.keys())
    loc_ids = set(loc_map_by_id.keys())

    card_ids = set()
    if isinstance(card_registry, dict):
        cards = card_registry.get("cards", [])
        if isinstance(cards, list):
            card_ids = {c.get("id") for c in cards if isinstance(c, dict) and isinstance(c.get("id"), str)}

    seen_ids = set()

    for i, cp in enumerate(checkpoints):
        if not isinstance(cp, dict):
            errors.append(f"Checkpoint at index {i} must be a dict")
            continue

        cp_id = cp.get("checkpoint_id")
        label = f"Checkpoint '{cp_id}'" if cp_id else f"Checkpoint[{i}]"

        if not isinstance(cp_id, str) or not cp_id.strip():
            errors.append(f"Checkpoint at index {i} missing valid 'checkpoint_id'")
        else:
            if cp_id in seen_ids:
                errors.append(f"Duplicate checkpoint id '{cp_id}'")
            seen_ids.add(cp_id)

        for field in REQUIRED_CHECKPOINT_FIELDS:
            if field not in cp:
                errors.append(f"{label} missing required field '{field}'")

        boundary = cp.get("boundary")
        if boundary is not None and not isinstance(boundary, dict):
            errors.append(f"{label}: 'boundary' must be a dict")
        elif isinstance(boundary, dict):
            cp_locations = boundary.get("locations", [])
            if not isinstance(cp_locations, list):
                errors.append(f"{label}: boundary.locations must be a list")
            else:
                # Track zones for warning
                zones = []
                for loc_ref in cp_locations:
                    if not isinstance(loc_ref, str):
                        errors.append(f"{label}: boundary.locations entry must be a string")
                        continue
                    if loc_ref not in loc_names and loc_ref not in loc_ids:
                        errors.append(
                            f"{label}: boundary.locations references non-existent location '{loc_ref}'"
                        )
                    # Get zone from location
                    loc = loc_map_by_name.get(loc_ref) or loc_map_by_id.get(loc_ref)
                    if loc:
                        loc_name = loc.get("name", "")
                        if " - " in loc_name:
                            zone = loc_name.split(" - ", 1)[0]
                            zones.append(zone)

                # WARNING: check zone consistency
                if len(set(zones)) > 1:
                    errors.append(
                        f"WARNING: {label}: boundary.locations contain mixed zone prefixes: {set(zones)} "
                        f"(expected all locations in same checkpoint to share same zone prefix)"
                    )

        conditions = cp.get("required_conditions")
        if conditions is not None and not isinstance(conditions, list):
            errors.append(f"{label}: 'required_conditions' must be a list")
        elif isinstance(conditions, list):
            _check_condition_fields(conditions, label, character_state, errors)

        cards_unlocked = cp.get("cards_unlocked")
        if cards_unlocked is not None and not isinstance(cards_unlocked, list):
            errors.append(f"{label}: 'cards_unlocked' must be a list")
        elif isinstance(cards_unlocked, list) and card_ids:
            for card_ref in cards_unlocked:
                if isinstance(card_ref, str) and card_ref not in card_ids:
                    errors.append(
                        f"{label}: cards_unlocked references non-existent card id '{card_ref}'"
                    )

        next_cp = cp.get("default_next_checkpoint_id")
        if next_cp is not None and next_cp not in cp_ids:
            errors.append(
                f"{label}: default_next_checkpoint_id '{next_cp}' references non-existent checkpoint"
            )

    return errors


def validate_world_bundle(
    world_config: Dict[str, Any],
    canon_timeline: Dict[str, Any],
    location_map: Dict[str, Any],
    character_state: Optional[Dict[str, Any]] = None,
    card_registry: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Validate toàn bộ world bundle, gộp tất cả validator.

    Checks:
      - world_config có display_name (hoặc name)
      - location_map valid (delegate validate_location_map)
      - canon_timeline valid (delegate checkpoint_linter)
      - character_state: characters là dict; mỗi char có name/location/power_stat
      - (nếu story_mode == "fixed_ending") target_ending_scenario phải có
        summary + endgame_conditions
    Returns list error (rỗng = valid).
    """
    errors: List[str] = []

    if not isinstance(world_config, dict):
        errors.append("world_config must be a dict")
    else:
        if not (world_config.get("display_name") or world_config.get("name")):
            errors.append("world_config must have a 'display_name' or 'name'")

    if isinstance(location_map, dict):
        errors.extend(validate_location_map(location_map))
    else:
        errors.append("location_map must be a dict")

    if isinstance(canon_timeline, dict):
        errors.extend(
            checkpoint_linter(
                canon_timeline,
                location_map,
                character_state=character_state,
                card_registry=card_registry,
            )
        )
    else:
        errors.append("canon_timeline must be a dict")

    if character_state is not None:
        if not isinstance(character_state, dict):
            errors.append("character_state must be a dict or None")
        else:
            characters = character_state.get("characters")
            if characters is not None and not isinstance(characters, dict):
                errors.append("character_state.characters must be a dict")
            elif isinstance(characters, dict):
                for cid, ch in characters.items():
                    if not isinstance(ch, dict):
                        errors.append(f"Character '{cid}' must be a dict")
                        continue
                    if not ch.get("name"):
                        errors.append(f"Character '{cid}' missing 'name'")
                    if "power_stat" not in ch or not isinstance(ch.get("power_stat"), dict):
                        errors.append(f"Character '{cid}' missing valid 'power_stat'")

    if isinstance(world_config, dict) and world_config.get("story_mode") == "fixed_ending":
        tes = world_config.get("target_ending_scenario")
        if not isinstance(tes, dict):
            errors.append(
                "world_config.story_mode is 'fixed_ending' but 'target_ending_scenario' is missing or not a dict"
            )
        else:
            if not tes.get("summary"):
                errors.append("target_ending_scenario missing required field 'summary'")
            if not isinstance(tes.get("endgame_conditions"), list) or not tes.get("endgame_conditions"):
                errors.append(
                    "target_ending_scenario must have a non-empty 'endgame_conditions' list"
                )

    return errors
