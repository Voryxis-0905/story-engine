# Task 6 — Language-detection for boundary rejection

## Problem

`world_config` had no explicit `language` field. `detect_story_language()` in `engine.py` always fell through to heuristic keyword-sniffing against `VI_COMMON_WORDS` (which includes the English word "do"), risking false-positive Vietnamese detection on English stories.

## Changes made

### 1. `backend/app/engine.py` — line 73

Added `"language": "en"` to `TEMPLATES["world_config.json"]` so the default is English.

### 2. `backend/app/routes/world_routes.py`

- **Line 34**: Added `detect_story_language` to the import from `app.engine`.
- **Lines 278-279**: In `create_world()`, detect language from `req.prompt` via `detect_story_language(user_input=req.prompt)` and store it in `cfg["language"]`.

## What was already working (no change needed)

`detect_story_language()` at `engine.py:1425-1430` already read `world_config.get("language", "")` and returned early if it was `"en"` or `"vi"` — the function just never received a populated value.

## Verification

- Explicit `language: "en"` in `world_config` now takes priority over Vietnamese text in `display_name`
- `raise_boundary_hard_reject()` uses the English template via `world_config` language field without any text sniffing
- All existing detection logic preserved as fallback for worlds created before this change
