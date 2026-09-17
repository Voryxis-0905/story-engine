# Story Engine — Project Assessment

## Strengths

### Architecture
- **Clean separation of concerns** between backend (FastAPI), frontend (vanilla HTML/JS), and data (JSON files on disk). No build step, no framework lock-in, easy to run.
- **Multi-agent pipeline** (Writer -> Extractor -> Checker -> optional Editor/Summarizer) is modularized in `backend/app/engine.py`. Each agent has a narrow job and runs in its own context, preventing hallucination cascades. Per-role model assignment and fallback chains are fully supported.
- **Checkpoint engine** with soft bounds and hard stops provides structured interactive fiction narrative progression.
- **2-tier progression** (exp/sub-stats free-form, realm/power only at checkpoints) strikes a smart balance between player agency and narrative structure.
- **Sub-beat progression system** (`_advance_sub_beats`) allows granular pacing within checkpoints before advancing main story checkpoints.
- **Card-based scoped context** solves the token budget and spoiler problems simultaneously. Unlocking content as the story progresses is elegant.

### Code Quality & Modular Organization
- **Modular backend architecture** under `backend/app/`:
  - `backend/app/models.py`: Strongly-typed Pydantic schemas (`SubBeat`, `CardModel`, `CheckpointModel`, request/response DTOs).
  - `backend/app/engine.py`: Core pipeline orchestration (`call_llm`, `run_pipeline`, `_advance_sub_beats`, `eval_condition`, anti-OOC enforcement, role-based model fallbacks).
  - `backend/app/storage.py`: Clean I/O operations, snapshot state management, and file persistence.
  - `backend/app/routes/`: Router modules (`world_routes.py`, `chapter_routes.py`, `builder_routes.py`, `creator_routes.py`, `studio_routes.py`).
  - `backend/main.py`: Thin entry point (~50 lines) initializing FastAPI and mounting router modules.
- **Prompts are separated** from logic in `backend/prompts.py`, making prompt tuning independent of code changes.
- **Comprehensive test suite** (`backend/test_engine.py`, `backend/test_fallback.py`) covering pipeline execution, anti-OOC enforcement, sub-beat pacing, fallback chains, and localized hard-rejects.
- **Fail-open design** for checker, editor, and summarizer ensures isolated failures do not block the main story flow.

### UX
- **Creator Mode** gives full control over world data without requiring manual JSON editing, with draft approval workflows for AI-suggested entities (`entity_status: "draft"`).
- **Save/Branch system** allows experimentation without risk.
- **First message / prologue** screen gives the user a choice between AI generation and manual writing.
- **Suggested actions** chips provide flexible player guidance.

### Robustness
- **Backward compatibility** with legacy data formats (missing fields default to sensible values).
- **Per-role & per-world API key and model fallback overrides** allow granular configuration across OpenRouter/OpenAI providers.
- **Localized error messages** (e.g. boundary hard-rejects in Vietnamese/English based on context).

---

## Open Weaknesses & Technical Debt

### Code Maintenance & Cleanup
- **`test_engine.py` is monolithic** (~200KB script) containing end-to-end integration assertions. Splitting into focused `pytest` test modules under `tests/` will improve maintainability.
- **Scratch files in project root** (`fix_out_typo.py`, `patch.py`, `test_out*.txt`) are leftover artifacts that should be moved to `.gitignore` or `scratch/`.

### Error Handling & Edge Cases
- **LLM JSON parsing** uses regex-based extraction (`parse_llm_json`). A single unmatched brace or escaped quote in LLM output can require retries.
- **World creation recovery**: World creation can fail mid-pipeline if the LLM returns malformed data; status recovery relies on checking `creation_status`.
- **Input validation**: Lack of explicit unique constraint checks on card/checkpoint IDs in raw API PUT endpoints (though frontend prevents UI duplicates).

### UX Gaps
- **No onboarding walkthrough**. A new user sees an empty UI without interactive guidance for checkpoints, cards, or interaction modes.
- **Chapter feed navigation**: Finding earlier scenes in long chapters requires manual scrolling. Chapter table of contents / collapsible chapter headers are open items.
- **Settings split**: Settings are divided between global runtime config and per-world config without a visual indicator.
- **Mobile responsiveness**: Desktop-first layout requires drawer navigation and responsive tweaks for smaller viewports.
- **Dark mode**: Lacks dark mode styling for extended reading sessions.

### Security & Operations
- **API keys stored in plaintext** on disk in `world_config.json` / `runtime_config.json`.
- **Request rate limiting**: Backend routes do not currently enforce rate limiting on mutation endpoints.
- **Logging framework**: Relies on `print()` output rather than structured Python `logging` with configurable levels.

---

## User Perspective (Newcomer)

1. **First-run Experience**:
   - The user opens the app and sees "Create World" and "Import Package".
   - The creation wizard walks through prompt entry, scope selection, and chunked world generation.
2. **Onboarding Need**:
   - Guidance explaining how checkpoints branch, how cards unlock context, and how sub-beats delay checkpoint triggers would significantly lower the learning curve for non-technical users.
