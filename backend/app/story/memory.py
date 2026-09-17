"""Memory responsibilities for Story Engine."""
from app.llm_client import LLMCallError
from app.llm_client import call_llm
from app.llm_client import mock_summarizer_response
from app.llm_client import parse_llm_json
from app.prompts import SUMMARIZER_SYSTEM_PROMPT
from app.rag import estimate_tokens
from app.story.pacing import CHAPTER_SUMMARY_BUDGET_CEIL
from app.story.pacing import CHAPTER_SUMMARY_BUDGET_FLOOR
from app.story.pacing import SUMMARY_MAX_TOKENS
from app.story.pacing import get_pacing_context_config
from app.story.pacing import get_recent_turns_for_context
import json
import re


def merge_canon_and_delta(canon_store: dict, branch_delta: dict) -> dict:
    overrides = branch_delta.get("overrides", {}) if isinstance(branch_delta, dict) else {}
    effective = {"facts": list(canon_store.get("facts", []))}
    for i, fact in enumerate(effective["facts"]):
        if not isinstance(fact, dict):
            continue
        fact_id = fact.get("fact_id", "")
        if fact_id in overrides:
            effective["facts"][i] = dict(fact)
            effective["facts"][i]["statement"] = overrides[fact_id]
    return effective


def _filter_memorable_beats_by_token_budget(beats: list, max_tokens: int,
                                              running_summary: str = "",
                                              max_beats_per_chapter: int = 2) -> list:
    summary_tokens = estimate_tokens(running_summary)
    remaining = max_tokens - summary_tokens
    if remaining <= 0:
        return []
    grouped = {}
    for beat in beats:
        m = re.match(r"\[Ch\.(\d+)\]", beat)
        key = int(m.group(1)) if m else 0
        grouped.setdefault(key, []).append(beat)
    result = []
    for ch_idx in sorted(grouped.keys(), reverse=True):
        chapter_beats = grouped[ch_idx]
        for beat in chapter_beats:
            if max_beats_per_chapter and sum(1 for r in result if r.startswith(f"[Ch.{ch_idx}]")) >= max_beats_per_chapter:
                break
            btok = estimate_tokens(beat)
            if btok > remaining:
                continue
            result.append(beat)
            remaining -= btok
        if remaining <= 0:
            break
    return result


def build_multi_tier_context(
    chapters_data: dict,
    world_config: dict,
    checkpoint: dict,
    canon_facts: list,
) -> dict:
    allowed_locations = set(
        loc.lower() for loc in checkpoint.get("boundary", {}).get("locations", [])
    )
    allowed_chars = set(
        c.lower() for c in checkpoint.get("boundary", {}).get("allowed_characters", [])
    )
    scene_anchors = allowed_locations | allowed_chars

    def _tag_in_allowed_zones(tag: str) -> bool:
        for anchor in scene_anchors:
            if tag == anchor or tag.startswith(anchor + " - "):
                return True
        return False

    filtered_facts = []
    for f in canon_facts:
        if isinstance(f, str):
            filtered_facts.append(f)
        elif isinstance(f, dict):
            statement = f.get("statement", "")
            tags = [t.lower() for t in f.get("tags", [])]
            if not scene_anchors or any(_tag_in_allowed_zones(t) for t in tags):
                filtered_facts.append(statement)

    threads = []
    for t in world_config.get("open_threads", []):
        if isinstance(t, dict):
            threads.append({
                "note": t.get("note", ""),
                "checkpoint_id": t.get("checkpoint_id", ""),
                "resolution_deadline": t.get("resolution_deadline", "ongoing"),
            })

    foreshadowing_tracker = world_config.get("foreshadowing_tracker")
    if foreshadowing_tracker is None:
        foreshadowing_tracker = world_config.get("foreshadowings", [])

    pacing_config = get_pacing_context_config(world_config.get("pacing_level", "Balanced"))

    return {
        "multi_tier_context": {
            "tier_1_working_memory": {
                "description": "Full text of the most recent turns (immediate scene context). Prioritize this for what is happening right now.",
                "recent_turns": get_recent_turns_for_context(chapters_data, limit=pacing_config["recent_turns"]),
                "max_turns": pacing_config["recent_turns"],
            },
            "tier_2_rolling_summary": {
                "description": "Compressed history of all events older than working memory. Use for long-term continuity only.",
                "summary": chapters_data.get("running_summary", ""),
            },
            "tier_2_memorable_beats": {
                "description": "Short highlights from recent chapters that survived compression. Each beat is a striking moment, line of dialogue, or vivid image.",
                "beats": _filter_memorable_beats_by_token_budget(
                    chapters_data.get("memorable_beats", []),
                    SUMMARY_MAX_TOKENS,
                    running_summary=chapters_data.get("running_summary", ""),
                    max_beats_per_chapter=2,
                ),
            },
            "tier_3_canon_filter": {
                "description": "Entity-tagged world facts filtered by active scene/location. These are canonical constraints.",
                "allowed_locations": list(allowed_locations),
                "allowed_characters": list(allowed_chars),
                "relevant_canon_facts": filtered_facts,
            },
            "tier_4_thread_ledger": {
                "description": "Active narrative threads and foreshadowing hints awaiting resolution. Advance or resolve threads within their deadlines.",
                "open_threads": threads,
                "active_thread_count": len(threads),
                "foreshadowing_tracker": foreshadowing_tracker,
            },
        }
    }


def _is_rolled(c: dict) -> bool:
    val = c.get("rolled_into_summary")
    if val is not None:
        return val
    return c.get("chapter_closed", True)


def get_unshelved_turn_count(chapters_data: dict) -> int:
    return sum(1 for c in chapters_data.get("chapters", []) if not _is_rolled(c))


def check_rolling_summary_trigger(
    chapters_data: dict,
    world_name: str = None,
    world_config: dict = None,
) -> bool:
    chapters = chapters_data.get("chapters", [])
    unshelved = [c for c in chapters if not _is_rolled(c)]

    pacing_config = get_pacing_context_config(world_config.get("pacing_level") if world_config else None)
    recent_turns_limit = pacing_config["recent_turns"]

    if len(unshelved) <= recent_turns_limit:
        return False

    turns_to_roll = unshelved[:-recent_turns_limit]

    by_chapter = {}
    for c in turns_to_roll:
        idx = c["chapter_index"]
        if idx not in by_chapter:
            by_chapter[idx] = []
        by_chapter[idx].append(c)

    for ch_idx in sorted(by_chapter.keys()):
        same_chapter = sorted(by_chapter[ch_idx], key=lambda x: x["turn_index"])
        full_text = "\n\n".join(t.get("chapter_text", "") for t in same_chapter)
        title = same_chapter[0].get("chapter_title") or f"Chapter {ch_idx}"

        result = update_running_summary(chapters_data, ch_idx, title, world_name)
        chapters_data["running_summary"] = result["running_summary"]

        for t in same_chapter:
            t["rolled_into_summary"] = True

    return True


def build_summarizer_payload(previous_summary: str, chapter_title: str, chapter_text: str,
                              word_budget: int = 100) -> dict:
    return {
        "previous_summary": previous_summary,
        "chapter_title": chapter_title,
        "chapter_text": chapter_text,
        "word_budget": word_budget
    }


def parse_summarizer_response(raw_text: str, fallback: str) -> dict:
    default_res = {"running_summary": fallback, "tension_level": 5, "mood": "", "memorable_beats": []}
    try:
        parsed = parse_llm_json(raw_text)
    except (json.JSONDecodeError, ValueError):
        return default_res
    if not isinstance(parsed, dict):
        return default_res
    new_summary = parsed.get("running_summary")
    if not isinstance(new_summary, str) or not new_summary.strip():
        new_summary = fallback
    else:
        new_summary = new_summary.strip()
    beats = parsed.get("memorable_beats", [])
    if not isinstance(beats, list) or not beats:
        beats = []
    else:
        beats = [str(b).strip() for b in beats if isinstance(b, str) and str(b).strip()]
    return {
        "running_summary": new_summary,
        "tension_level": parsed.get("tension_level", 5),
        "mood": parsed.get("mood", ""),
        "memorable_beats": beats
    }


def total_story_word_count(chapters_data: dict) -> int:
    return sum(len(c.get("chapter_text", "").split()) for c in chapters_data.get("chapters", []))


def compute_word_budget(total_words: int, pacing_level: str = "Balanced") -> int:
    config = get_pacing_context_config(pacing_level)
    budget = int(total_words * config["summary_budget_ratio"])
    return max(CHAPTER_SUMMARY_BUDGET_FLOOR, min(CHAPTER_SUMMARY_BUDGET_CEIL, budget))


def update_running_summary(chapters_data: dict, closed_chapter_index: int, chapter_title: str,
                            world_name: str = None, world_config: dict = None) -> dict:
    previous_summary = chapters_data.get("running_summary", "")
    same_chapter_turns = sorted(
        (c for c in chapters_data.get("chapters", []) if c["chapter_index"] == closed_chapter_index),
        key=lambda c: c["turn_index"]
    )
    full_chapter_text = "\n\n".join(c.get("chapter_text", "") for c in same_chapter_turns)
    total_words = total_story_word_count(chapters_data)
    word_budget = compute_word_budget(total_words, world_config.get("pacing_level") if world_config else None)
    payload = build_summarizer_payload(previous_summary, chapter_title, full_chapter_text, word_budget)
    try:
        raw = call_llm(
            SUMMARIZER_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            mock_response=mock_summarizer_response(chapter_title),
            world_name=world_name,
            role="summarizer"
        )
    except LLMCallError:
        return {"running_summary": previous_summary, "tension_level": 5, "mood": "", "memorable_beats": []}
    result = parse_summarizer_response(raw, fallback=previous_summary)
    new_beats = result.get("memorable_beats", [])
    if new_beats:
        existing = chapters_data.get("memorable_beats", [])
        checkpoint_id = same_chapter_turns[0].get("checkpoint_id", "") if same_chapter_turns else ""
        cp_tag = f"[{checkpoint_id}]" if checkpoint_id else ""
        tagged = [f"[Ch.{closed_chapter_index}]{cp_tag} {b}" for b in new_beats]
        chapters_data["memorable_beats"] = tagged + existing
    return result
