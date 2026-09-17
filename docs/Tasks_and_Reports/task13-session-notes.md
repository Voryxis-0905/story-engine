# Session Summary — Task 13: Output Length Setting (Concise/Standard/Detailed)

## Files modified (5 files)

| File | Change |
|------|--------|
| `backend/app/models.py:33` | Added `output_length: Optional[Literal["Concise", "Standard", "Detailed"]]` to `WorldConfigUpdate` |
| `backend/app/engine.py` | Added `get_output_length_config()`, `get_close_thresholds()`, updated `get_words_per_turn_target()`, `decide_chapter_closed()`, `_generate_chapter()` |
| `backend/main.py:73` | Added `get_output_length_config`, `get_close_thresholds` to imports |
| `frontend/app.js` | Added `output_length`, `pacing_level`, `pov_angle` dropdowns to Creator Mode → World Config tab |
| `backend/test_engine.py` | 24 assertions across 6 test sub-suites (13a–13f) |

## What was built

**Problem:** The engine had `pacing_level` (Slowburn/Balanced/Fast) which controlled context-window size and summary budget ratio, but no user-facing control over **prose density per turn**. Writers always aimed for the same `words_per_turn_target` derived solely from pacing, and chapter-close thresholds (soft/hard turn counts, soft word counts) were fixed constants.

**Solution:** Introduced `output_length` — a three-level setting (`Concise`/`Standard`/`Detailed`) that scales independently from `pacing_level`. It modifies two things:

1. **Words-per-turn target**: multiplied by a ratio (0.65× / 1.0× / 1.5×) against the base target from `pacing_level`
2. **Chapter-close thresholds**: soft/hard turn counts and soft word count shifted per output_length to give more or less room per chapter

The key design choice was **independent stacking**: `pacing_level` still controls context window + summary budget, `output_length` controls prose density + close thresholds. They compose multiplicatively (e.g., Slowburn+Detailed = 300 × 1.5 = 450 words/turn).

### New functions in `engine.py`

- `get_output_length_config(output_length)` — returns ratio, turn deltas, word multiplier for a given level
- `get_close_thresholds(output_length)` — returns effective `soft_turns`, `hard_turns`, `soft_words` by applying deltas from output_length config onto base constants
- `get_words_per_turn_target()` updated to accept `output_length` parameter (default `"Standard"`)

### Frontend

- World Config tab in Creator Mode got three dropdowns: `pacing_level`, `output_length`, `pov_angle` — all included in the PUT save payload
- The frontend change also incidentally surfaced `pacing_level` and `pov_angle` which were previously only settable via direct API calls

## Notable design decisions

1. **Hard-turn ceiling scaling**: `Detailed` increases hard turns by +2 (from 8→10), `Concise` decreases by −2 (from 8→6). This prevents `Concise` from trapping the user in a very long chapter with tiny turns — fewer turns required to force-close.

2. **No prompt changes needed**: Unlike Task 12 which required rewriting `WRITER_SYSTEM_PROMPT`, Task 13 only needed the numeric `words_per_turn_target` in the payload. The prompt already references `words_per_turn_target` generically (from Task 12), so changing the value is sufficient.

3. **Default = "Standard"**: Both in `WorldConfigUpdate` (Optional, editor only sees it when set) and in `TEMPLATES["world_config.json"]` so new worlds get it by default. Mid-story edits take effect immediately (no migration needed).

4. **Test isolation**: Pure-function tests (13a–13c) run without seeding a world; integration tests (13d–13f) use seeded worlds with specific output_length set via PUT. All 24 assertions pass alongside ~3800 existing checks.

## Verification

```text
[OK ] 13a. Concise ratio < 1.0
[OK ] 13a. Detailed ratio > 1.0
[OK ] 13a. Standard ratio == 1.0
[OK ] 13a. Concise reduces soft turns
[OK ] 13a. Detailed increases soft turns
[OK ] 13a. Unknown falls back to Standard
[OK ] 13b. Balanced+Concise < 200, got 130
[OK ] 13b. Balanced+Detailed > 200, got 300
[OK ] 13b. Slowburn+Detailed > Slowburn+Standard
[OK ] 13b. Fast+Concise < Fast+Standard
[OK ] 13c. Concise soft turns (4) < Standard (5)
[OK ] 13c. Detailed hard turns (10) > Standard (8)
[OK ] 13c. Concise soft words (630) < Standard (900)
[OK ] 13c. Detailed soft words (1440) > Standard (900)
[OK ] 13d. Concise+Slowburn wpt = 195, expected 195
[OK ] 13d. Detailed+Slowburn wpt = 450, expected 450
[OK ] 13e. Concise payload includes output_length in world_config
[OK ] 13e. Detailed payload world_config.output_length = 'Detailed'
[OK ] 13f. Concise: 6+ turns -> hard close
[OK ] 13f. Detailed: 8 turns not enough for soft/hard close
[OK ] 13f. Detailed: 8 turns + enough words -> soft close
--- TASK-13 (Output Length setting) hoan thanh ---
```

## Relevant source locations

- `backend/app/engine.py:159` — `get_output_length_config()`
- `backend/app/engine.py:196` — `get_close_thresholds()`
- `backend/app/engine.py:184` — `get_words_per_turn_target()` (updated)
- `backend/app/engine.py:1684` — `decide_chapter_closed()` (updated)
- `backend/app/engine.py:2349` — `_generate_chapter()` base_payload with `output_length`
- `backend/app/engine.py:2507` — close call passing `output_length`
- `backend/app/models.py:33` — `WorldConfigUpdate` field
- `frontend/app.js:1953-1995` — World Config tab dropdowns
- `frontend/app.js:2021-2023` — save payload
- `backend/test_engine.py` — 13a through 13f tests

## Compatibility

- Existing worlds (pre-migration, no `output_length` key) fall back to `"Standard"` via `.get("output_length", "Standard")` in all consumers
- The `pacing_level` and `pov_angle` dropdowns in the World Config tab expose settings that were previously API-only; this is a net UX improvement but was incidental to the task
