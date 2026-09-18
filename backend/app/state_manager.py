from typing import Dict, Optional


DEFAULT_STORY_CLOCK = {
    "year": 1,
    "month": 1,
    "day": 1,
    "time_of_day": "morning",
    "season": "spring",
    "tick": 0
}


def get_nested_field(character_state: dict, field_path: str):
    parts = field_path.split(".")
    if not parts:
        return None
    char_id = parts[0]
    cur = character_state.get(char_id)
    for key in parts[1:]:
        if isinstance(cur, dict):
            cur = cur.get(key)
        else:
            return None
    return cur


def eval_condition(condition, character_state: dict, world_config: dict = None) -> bool:
    if not isinstance(condition, dict):
        return False

    if "all" in condition:
        sub_conditions = condition["all"]
        if not isinstance(sub_conditions, list):
            return False
        return all(
            eval_condition(sub, character_state, world_config)
            for sub in sub_conditions
        )

    if "any" in condition:
        sub_conditions = condition["any"]
        if not isinstance(sub_conditions, list):
            return False
        return any(
            eval_condition(sub, character_state, world_config)
            for sub in sub_conditions
        )

    field = condition.get("field")
    if not field or not isinstance(field, str) or not field.strip():
        return False
    op = condition.get("op", "==")
    value = condition.get("value")

    if field.startswith("story_clock."):
        sub_field = field[len("story_clock."):]
        if world_config and isinstance(world_config, dict):
            clock = world_config.get("story_clock", {})
            if not isinstance(clock, dict):
                clock = {}
            actual = get_nested_field(clock, sub_field)
        else:
            actual = None
    elif field.startswith("world_flags."):
        sub_field = field[len("world_flags."):]
        if world_config and isinstance(world_config, dict):
            flags = world_config.get("world_flags", {})
            if not isinstance(flags, dict):
                flags = {}
            actual = get_nested_field(flags, sub_field)
        else:
            actual = None
    else:
        actual = get_nested_field(character_state, field)

    try:
        if op == "==":
            return actual == value
        if op == "!=":
            return actual != value
        if op == "in":
            return actual in value
        if op == "contains":
            return isinstance(actual, list) and value in actual
        if op == ">=":
            return actual is not None and actual >= value
        if op == "<=":
            return actual is not None and actual <= value
        if op == ">":
            return actual is not None and actual > value
        if op == "<":
            return actual is not None and actual < value
    except TypeError:
        return False
    return False


def apply_story_clock_changes(story_clock: dict, delta: dict) -> dict:
    if not isinstance(story_clock, dict):
        return dict(DEFAULT_STORY_CLOCK)
    if not delta or not isinstance(delta, dict):
        return story_clock

    for field in ["year", "month", "day", "tick"]:
        delta_key = f"{field}_delta"
        val = None
        if delta_key in delta:
            val = delta[delta_key]
        elif field in delta:
            val = delta[field]

        if val is not None:
            min_val = 0 if field == "tick" else 1
            raw_val = story_clock.get(field)
            if raw_val is None:
                current_val = min_val
            else:
                try:
                    current_val = int(raw_val)
                except (ValueError, TypeError):
                    current_val = min_val

            if isinstance(val, (int, float)):
                story_clock[field] = max(min_val, current_val + int(val))
            elif isinstance(val, str) and (val.isdigit() or (val.startswith("-") and val[1:].isdigit())):
                story_clock[field] = max(min_val, current_val + int(val))

    if "time_of_day" in delta and delta["time_of_day"]:
        story_clock["time_of_day"] = str(delta["time_of_day"])
    elif "time" in delta and delta["time"]:
        story_clock["time_of_day"] = str(delta["time"])

    if "season" in delta and delta["season"]:
        story_clock["season"] = str(delta["season"])

    return story_clock


def apply_foreshadowing_changes(tracker: list, items: list, current_chapter_index: int = 1) -> list:
    if tracker is None:
        tracker = []
    if not items or not isinstance(items, list):
        return tracker

    existing_by_id = {
        item["id"]: item for item in tracker
        if isinstance(item, dict) and "id" in item
    }

    for item in items:
        if isinstance(item, str):
            existing = next((x for x in tracker if isinstance(x, dict) and x.get("description") == item), None)
            if not existing:
                new_id = f"fg_{len(tracker) + 1}"
                new_item = {
                    "id": new_id,
                    "description": item,
                    "planted_chapter": current_chapter_index,
                    "payoff_chapter": None,
                    "status": "planted"
                }
                tracker.append(new_item)
                existing_by_id[new_id] = new_item
        elif isinstance(item, dict):
            item_id = item.get("id") or item.get("foreshadowing_id")
            if item_id and item_id in existing_by_id:
                target = existing_by_id[item_id]
                if "status" in item and item["status"] in ("planted", "revealed", "resolved"):
                    target["status"] = item["status"]
                    if item["status"] in ("revealed", "resolved") and target.get("payoff_chapter") is None:
                        target["payoff_chapter"] = current_chapter_index
                if "description" in item and item["description"]:
                    target["description"] = item["description"]
                if "payoff_chapter" in item:
                    target["payoff_chapter"] = item["payoff_chapter"]
            else:
                new_id = item_id or f"fg_{len(tracker) + 1}"
                status = item.get("status", "planted")
                if status not in ("planted", "revealed", "resolved"):
                    status = "planted"
                new_item = {
                    "id": new_id,
                    "description": item.get("description", ""),
                    "planted_chapter": item.get("planted_chapter", current_chapter_index),
                    "payoff_chapter": item.get("payoff_chapter"),
                    "status": status
                }
                tracker.append(new_item)
                existing_by_id[new_id] = new_item

    return tracker


def ensure_foreshadowing_consistency(foreshadowing_tracker: list, open_threads_update: str, foreshadowing_tracker_add: list) -> list:
    if not foreshadowing_tracker or not open_threads_update or not isinstance(open_threads_update, str):
        return foreshadowing_tracker_add or []
    if not foreshadowing_tracker_add or not isinstance(foreshadowing_tracker_add, list):
        foreshadowing_tracker_add = []

    tracker_text_lower = open_threads_update.lower()
    existing_ids = {item["id"]: item for item in foreshadowing_tracker if isinstance(item, dict) and "id" in item}
    resolved_ids_in_add = set()
    for entry in foreshadowing_tracker_add:
        if isinstance(entry, dict):
            eid = entry.get("id") or entry.get("foreshadowing_id")
            if eid and entry.get("status") in ("revealed", "resolved"):
                resolved_ids_in_add.add(eid)

    for planted in foreshadowing_tracker:
        if not isinstance(planted, dict):
            continue
        if planted.get("status") != "planted":
            continue
        pid = planted.get("id")
        if not pid or pid in resolved_ids_in_add:
            continue
        desc = planted.get("description", "")
        if not desc:
            continue
        desc_keywords = [w for w in desc.lower().split() if len(w) > 3]
        if not desc_keywords:
            continue
        match_count = sum(1 for kw in desc_keywords if kw in tracker_text_lower)
        if match_count >= max(2, len(desc_keywords) // 2):
            foreshadowing_tracker_add.append({"id": pid, "status": "revealed"})

    return foreshadowing_tracker_add


def _apply_outcome_payload(character_state: dict, payload: dict, world_config: dict = None):
    if not isinstance(payload, dict):
        return
    if "characters" in payload:
        apply_state_changes(
            character_state, payload,
            trait_definitions=world_config.get("trait_definitions") if isinstance(world_config, dict) else None,
            exclusive_titles=world_config.get("titles", []) if isinstance(world_config, dict) else []
        )
        return

    for kflag in payload.get("knowledge_flags", []):
        for char in character_state.values():
            if isinstance(char, dict) and "knowledge_flags" in char:
                if kflag not in char["knowledge_flags"]:
                    char["knowledge_flags"].append(kflag)

    for key, delta in payload.get("stat_deltas", {}).items():
        parts = key.split(".")
        char_id = parts[0]
        if char_id in character_state:
            char = character_state[char_id]
            stat_name = parts[-1]
            sub_stats = char.setdefault("power_stat", {}).setdefault("sub_stats", {})
            sub_stats[stat_name] = sub_stats.get(stat_name, 0) + delta

    for item in payload.get("inventory_add", []):
        for char in character_state.values():
            if isinstance(char, dict):
                from app.story.inventory import add_inventory_item
                add_inventory_item(char.setdefault("inventory", []), item)

    for item in payload.get("inventory_remove", []):
        for char in character_state.values():
            if isinstance(char, dict) and "inventory" in char:
                from app.story.inventory import remove_inventory_item
                remove_inventory_item(char["inventory"], item)

    app_append = payload.get("appearance_append")
    if app_append:
        target_ids = list(character_state.keys())
        if payload.get("stat_deltas"):
            target_ids = [k.split(".")[0] for k in payload["stat_deltas"] if "." in k]
        for cid in target_ids:
            char = character_state.get(cid)
            if isinstance(char, dict):
                curr = char.get("appearance", "")
                char["appearance"] = (curr + " " + app_append).strip()

    ab_append = payload.get("abilities_append")
    if ab_append:
        target_ids = list(character_state.keys())
        if payload.get("stat_deltas"):
            target_ids = [k.split(".")[0] for k in payload["stat_deltas"] if "." in k]
        for cid in target_ids:
            char = character_state.get(cid)
            if isinstance(char, dict):
                curr = char.get("abilities_and_limits", "")
                char["abilities_and_limits"] = (curr + " " + ab_append).strip()

    for rel_key, rel_val in payload.get("relationships", {}).items():
        for char in character_state.values():
            if isinstance(char, dict):
                rels = char.setdefault("relationships", {})
                rels[str(rel_key)] = str(rel_val)


def apply_state_changes(characters: dict, state_changes: dict,
                        trait_definitions: dict = None, exclusive_titles: list = None,
                        story_clock: dict = None, foreshadowing_tracker: list = None,
                        current_chapter_index: int = 1) -> dict:
    char_changes = state_changes.get("characters", {})
    for char_id, changes in char_changes.items():
        if char_id not in characters:
            continue
        char = characters[char_id]

        if "location" in changes and changes["location"]:
            char["location"] = changes["location"]

        for other_id, delta in changes.get("affinity_delta", {}).items():
            char["affinity"][other_id] = char["affinity"].get(other_id, 0) + delta

        for stat_name, delta in changes.get("sub_stats_delta", {}).items():
            char["power_stat"]["sub_stats"][stat_name] = (
                char["power_stat"]["sub_stats"].get(stat_name, 0) + delta
            )

        if changes.get("exp_delta"):
            char["power_stat"]["exp"] += changes["exp_delta"]

        for flag in changes.get("knowledge_flags_add", []):
            if flag not in char["knowledge_flags"]:
                char["knowledge_flags"].append(flag)

        from app.story.inventory import add_inventory_item, remove_inventory_item
        for item in changes.get("inventory_add", []):
            if isinstance(item, dict):
                item = dict(item)
                item.setdefault("acquired_at_tick", (story_clock or {}).get("tick"))
                item.setdefault("acquired_from", char.get("location"))
            add_inventory_item(char.setdefault("inventory", []), item)

        for item in changes.get("inventory_remove", []):
            if "inventory" in char:
                remove_inventory_item(char["inventory"], item)

        if changes.get("karma_delta"):
            char["karma"] = char.get("karma", 0) + changes["karma_delta"]

        if "alive" in changes and changes["alive"] is not None:
            char["alive"] = changes["alive"]

        if "relationships_update" in changes and isinstance(changes["relationships_update"], dict):
            if "relationships" not in char or not isinstance(char["relationships"], dict):
                char["relationships"] = {}
            for rel_key, rel_val in changes["relationships_update"].items():
                if rel_val is None or rel_val == "":
                    if rel_key in char["relationships"]:
                        del char["relationships"][rel_key]
                else:
                    char["relationships"][rel_key] = str(rel_val)

        if "age" in changes and changes["age"] is not None:
            char["age"] = str(changes["age"])

        for field in ("appearance", "personality", "backstory",
                      "abilities_and_limits", "speech_style", "secrets"):
            if field in changes and changes[field] is not None:
                char[field] = changes[field]

        for trait, val in changes.get("traits_set", {}).items():
            if trait_definitions is not None and trait not in trait_definitions:
                continue
            if "traits" not in char:
                char["traits"] = {}
            char["traits"][trait] = val
            if exclusive_titles and val in exclusive_titles:
                for other_char_id, other_char in characters.items():
                    if other_char_id == char_id:
                        continue
                    if other_char.get("traits", {}).get(trait) == val:
                        del other_char["traits"][trait]

        for trait in changes.get("traits_clear", []):
            if "traits" in char and trait in char["traits"]:
                del char["traits"][trait]

    if story_clock is not None and "story_clock_delta" in state_changes and state_changes["story_clock_delta"]:
        apply_story_clock_changes(story_clock, state_changes["story_clock_delta"])

    if foreshadowing_tracker is not None and "foreshadowing_tracker_add" in state_changes and state_changes["foreshadowing_tracker_add"]:
        apply_foreshadowing_changes(foreshadowing_tracker, state_changes["foreshadowing_tracker_add"], current_chapter_index)

    return characters
