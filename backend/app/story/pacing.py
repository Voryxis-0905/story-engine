"""Pacing responsibilities for Story Engine."""



DEFAULT_LORE_RAG_MAX_TOKENS = 2000


CHAPTER_SOFT_CLOSE_TURNS = 5


CHAPTER_SOFT_CLOSE_WORDS = 900


CHAPTER_HARD_CLOSE_TURNS = 8


RECENT_TURNS_CONTEXT_LIMIT = 2


WORKING_MEMORY_TURNS = RECENT_TURNS_CONTEXT_LIMIT


ROLLING_SUMMARIZATION_TRIGGER_TURNS = 5


SUMMARY_MAX_TOKENS = 500


CHAPTER_SUMMARY_BUDGET_RATIO = 0.03


CHAPTER_SUMMARY_BUDGET_FLOOR = 100


CHAPTER_SUMMARY_BUDGET_CEIL = 500


MEMORABLE_BEATS_MAX = 100


def get_pacing_context_config(pacing_level: str = "Balanced") -> dict:
    key = (pacing_level or "Balanced").strip().lower()
    configs = {
        "slowburn": {"recent_turns": 4, "summary_budget_ratio": 0.05},
        "balanced": {"recent_turns": 3, "summary_budget_ratio": 0.03},
        "fast": {"recent_turns": 2, "summary_budget_ratio": 0.02},
    }
    return configs.get(key, configs["balanced"])


def get_output_length_config(output_length: str = "Standard") -> dict:
    key = (output_length or "Standard").strip().lower()
    configs = {
        "concise": {
            "words_per_turn_ratio": 0.65,
            "soft_close_words_ratio": 0.7,
            "soft_close_turns_offset": -1,
            "hard_close_turns_offset": -2,
        },
        "standard": {
            "words_per_turn_ratio": 1.0,
            "soft_close_words_ratio": 1.0,
            "soft_close_turns_offset": 0,
            "hard_close_turns_offset": 0,
        },
        "detailed": {
            "words_per_turn_ratio": 1.5,
            "soft_close_words_ratio": 1.6,
            "soft_close_turns_offset": 2,
            "hard_close_turns_offset": 2,
        },
    }
    return configs.get(key, configs["standard"])


def get_words_per_turn_target(pacing_level: str = "Balanced", output_length: str = "Standard") -> int:
    pacing_key = (pacing_level or "Balanced").strip().lower()
    pacing_targets = {
        "slowburn": 300,
        "balanced": 200,
        "fast": 130,
    }
    base = pacing_targets.get(pacing_key, pacing_targets["balanced"])
    ol_config = get_output_length_config(output_length)
    return max(50, int(base * ol_config["words_per_turn_ratio"]))


def get_close_thresholds(output_length: str = "Standard", pacing_level: str = "Balanced") -> dict:
    ol_config = get_output_length_config(output_length)
    pacing_config = get_pacing_context_config(pacing_level)
    soft_close_turns = max(2, CHAPTER_SOFT_CLOSE_TURNS + ol_config["soft_close_turns_offset"])
    hard_close_turns = max(3, CHAPTER_HARD_CLOSE_TURNS + ol_config["hard_close_turns_offset"])
    return {
        "soft_close_turns": soft_close_turns,
        "soft_close_words": max(200, int(CHAPTER_SOFT_CLOSE_WORDS * ol_config["soft_close_words_ratio"])),
        "hard_close_turns": hard_close_turns,
    }


def get_open_chapter_state(chapters_data: dict) -> tuple:
    chapters = chapters_data.get("chapters", [])
    if not chapters:
        return 1, 1
    non_prelude = [c for c in chapters if c.get("chapter_index") != 0]
    if not non_prelude:
        return 1, 1
    last = non_prelude[-1]
    if last.get("chapter_closed", True):
        return last["chapter_index"] + 1, 1
    return last["chapter_index"], last["turn_index"] + 1


def decide_chapter_closed(chapter_index: int, turn_index: int, chapters_data: dict,
                           new_chapter_text: str, narrator_flagged_end: bool,
                           output_length: str = "Standard",
                           pacing_level: str = "Balanced") -> bool:
    if narrator_flagged_end:
        return True
    thresholds = get_close_thresholds(output_length, pacing_level)
    same_chapter_turns = [
        c for c in chapters_data.get("chapters", []) if c["chapter_index"] == chapter_index
    ]
    total_turns = len(same_chapter_turns) + 1
    if total_turns >= thresholds["hard_close_turns"]:
        return True
    total_words = sum(len(c.get("chapter_text", "").split()) for c in same_chapter_turns)
    total_words += len(new_chapter_text.split())
    if total_turns >= thresholds["soft_close_turns"] and total_words >= thresholds["soft_close_words"]:
        return True
    return False


def get_recent_turns_for_context(chapters_data: dict, limit: int = RECENT_TURNS_CONTEXT_LIMIT) -> list:
    return chapters_data.get("chapters", [])[-limit:]
