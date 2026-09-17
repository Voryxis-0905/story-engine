# Suggested Improvements for Story Engine

## 1. Module Split: Refactor main.py into a Package [COMPLETED]

### Status
**DONE** — `backend/main.py` was refactored into `backend/app/`:
- `backend/app/models.py`: Strongly-typed Pydantic schemas (`SubBeat`, `CardModel`, `CheckpointModel`, DTOs).
- `backend/app/engine.py`: Engine logic, multi-agent pipeline (`call_llm`, `run_pipeline`, `_advance_sub_beats`, `eval_condition`, role model fallbacks).
- `backend/app/storage.py`: Storage operations, snapshot backups, file reading/writing.
- `backend/app/routes/`: Route handlers (`world_routes.py`, `chapter_routes.py`, `builder_routes.py`, `creator_routes.py`, `studio_routes.py`).
- `backend/main.py`: Thin entry point (~50 lines).

---

## 2. Chapter Table of Contents with Collapsed History [OPEN]

### Reasoning
The chapter feed is a single scrolling list. After 10+ chapters, finding an earlier scene requires manual scrolling. Collapsing closed chapters into a summary line with an expand-to-read toggle keeps navigation practical without losing access to past text.

### Implementation Plan
1. In `renderChapters()`, group `.chapter-card` elements by `chapter_closed` state.
2. Closed chapters render as a collapsed header bar showing title, word count, and turn count.
3. Clicking the bar expands to reveal the full chapter text.
4. Add a floating "Table of Contents" button in the feed area listing all chapters.

---

## 3. World-Level Input Guard (Undo Protection for Creator Edits) [OPEN]

### Reasoning
Creator Mode allows direct edits to `card_registry`, `canon_timeline`, `character_state`, and `world_config`. An auto-backup before PUT edits prevents accidental loss of world-building work.

### Implementation Plan
1. Before applying PUT to canon files, save auto-backup in `data/worlds/<world>/.backups/`.
2. Add "Undo last edit" button to Creator Mode.
3. Keep maximum 10 backups per world.

---

## 4. Onboarding Walkthrough [OPEN]

### Reasoning
New users open the app without explicit guidance on checkpoints, card context, or interaction modes.

### Implementation Plan
1. Detect first visit via `localStorage['onboarded']`.
2. Render overlay tooltips on key UI elements in sequence (Create World wizard, Play mode feed, Creator Mode tabs, Settings).
3. Provide "Next" / "Skip all" buttons.

---

## 5. Mobile Responsive Layout [OPEN]

### Reasoning
Fixed-width sidebar and horizontal tabs overlap or clip on viewports under 1024px.

### Implementation Plan
1. Convert sidebar to off-canvas drawer with hamburger toggle on small screens.
2. Stack Creator Mode tabs vertically on narrow viewports.
3. Adjust padding and sticky input bar layout for mobile.

---

## 6. Chapter Auto-Save [OPEN]

### Reasoning
Currently saves are manual. Auto-saving after every successful turn/chapter prevents mid-session data loss.

### Implementation Plan
1. Call `build_save_entry()` after successful turn progression.
2. Label auto-saves with `type: "autosave"`.
3. Display non-blocking "Auto-saved" toast.
