import json
import logging
import os
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


class CommitValidationError(Exception):
    pass


def validate_world_config(data: dict) -> list:
    errors = []
    if "fixed_rules" in data and not isinstance(data.get("fixed_rules"), list):
        errors.append("world_config.fixed_rules must be a list")
    if "completed_checkpoints" in data and not isinstance(data.get("completed_checkpoints"), list):
        errors.append("world_config.completed_checkpoints must be a list")
    if data.get("pacing_level") not in (None, "Slowburn", "Balanced", "Fast"):
        errors.append(f"world_config.pacing_level must be Slowburn/Balanced/Fast, got '{data.get('pacing_level')}'")
    if data.get("output_length") not in (None, "Concise", "Standard", "Detailed"):
        errors.append(f"world_config.output_length must be Concise/Standard/Detailed, got '{data.get('output_length')}'")
    return errors


def validate_character_state(data: dict) -> list:
    errors = []
    characters = data.get("characters", {})
    if not isinstance(characters, dict):
        errors.append("character_state.characters must be a dict")
        return errors
    for cid, char in characters.items():
        if not isinstance(char, dict):
            errors.append(f"character_state.characters['{cid}'] must be a dict")
            continue
        if not char.get("name"):
            errors.append(f"character_state.characters['{cid}'] missing 'name'")
        if not isinstance(char.get("affinity"), dict):
            errors.append(f"character_state.characters['{cid}'].affinity must be a dict")
        power_stat = char.get("power_stat", {})
        if not isinstance(power_stat, dict):
            errors.append(f"character_state.characters['{cid}'].power_stat must be a dict")
        else:
            if not isinstance(power_stat.get("sub_stats"), dict):
                errors.append(f"character_state.characters['{cid}'].power_stat.sub_stats must be a dict")
            if not isinstance(power_stat.get("known_skills"), list):
                errors.append(f"character_state.characters['{cid}'].power_stat.known_skills must be a list")
        if not isinstance(char.get("knowledge_flags"), list):
            errors.append(f"character_state.characters['{cid}'].knowledge_flags must be a list")
        if not isinstance(char.get("inventory"), list):
            errors.append(f"character_state.characters['{cid}'].inventory must be a list")
        if not isinstance(char.get("relationships"), dict):
            errors.append(f"character_state.characters['{cid}'].relationships must be a dict")
        if not isinstance(char.get("alive"), bool):
            errors.append(f"character_state.characters['{cid}'].alive must be a bool")
    return errors


def validate_chapters(data: dict) -> list:
    errors = []
    chapters = data.get("chapters", [])
    if not isinstance(chapters, list):
        errors.append("chapters.chapters must be a list")
        return errors
    for i, ch in enumerate(chapters):
        if not isinstance(ch, dict):
            errors.append(f"chapters.chapters[{i}] must be a dict")
            continue
        if "chapter_index" not in ch:
            errors.append(f"chapters.chapters[{i}] missing 'chapter_index'")
        if "chapter_text" not in ch:
            errors.append(f"chapters.chapters[{i}] missing 'chapter_text'")
    if "running_summary" not in data:
        errors.append("chapters missing 'running_summary'")
    if "memorable_beats" in data and not isinstance(data.get("memorable_beats"), list):
        errors.append("chapters.memorable_beats must be a list")
    return errors


VALIDATORS = {
    "world_config.json": validate_world_config,
    "character_state.json": validate_character_state,
    "chapters.json": validate_chapters,
}


def cross_check(filename: str, data: dict) -> list:
    validator = VALIDATORS.get(filename)
    if validator is None:
        return []
    return validator(data)


def atomic_write(filepath: str, data: dict) -> None:
    errors = cross_check(os.path.basename(filepath), data)
    if errors:
        raise CommitValidationError(
            f"Commit validation failed for '{filepath}':\n" + "\n".join(f"  - {e}" for e in errors)
        )
    fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(filepath), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
