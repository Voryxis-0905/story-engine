# Codebase map

## Backend

Run the backend with `backend/main.py` or `uvicorn --app-dir backend main:app`. `app/application.py` assembles the application, middleware, and routes.

| Location | Responsibility |
| --- | --- |
| `app/routes/` | Receives HTTP requests, validates input, and calls engine or storage code. |
| `app/routes/world_routes.py` | World lifecycle, import/export, and branching. |
| `app/routes/runtime_routes.py` | Provider, model, and API-key configuration. |
| `app/routes/discovery_routes.py` | Map, quest, and codex views. |
| `app/routes/demo_routes.py` | Sample worlds. |
| `app/chapter_generator.py` | Orchestrates a turn: context, generation, checking, application, and persistence. |
| `app/story/generation.py` | Planner, writer, and editor stages. |
| `app/story/consistency.py` | Continuity checks and rewrite guidance. |
| `app/story/memory.py` | Canon, multi-tier context, and summaries. |
| `app/story/knowledge.py` | Stable facts, subject-specific knowledge, sources, confidence, and projections. |
| `app/story/observer.py` | Chooses scene participants and caps psychology calls per turn. |
| `app/story/action_resolution.py` | Validates tools, skill evidence, opposition, and deterministic action outcomes. |
| `app/story/action_effects.py` | Whitelists and applies declared action consequences. |
| `app/story/inventory.py` | Normalizes legacy and structured items, instance IDs, stacking, and engine-owned item actions. |
| `app/story/discovery.py` | Event discovery records and event-lifecycle quest views. |
| `app/story/relationship_memory.py` | Event-grounded memories such as promises, debts, and betrayals. |
| `app/story/capabilities.py` | Profile-backed capability evidence used to assess actions without genre-bound stats. |
| `app/story/pacing.py` | Turn length, pacing, and chapter closure. |
| `app/story/prelude.py` | Prelude and first playable scene generation. |
| `app/story/entities.py` | Character normalization, deduplication, and imported-package validation. |
| `app/checkpoint_engine.py` | Checkpoint conditions and progression. |
| `app/world/` | Data templates, calendars, map rules, boundaries, travel, time skips, and endgame. |
| `app/world/schema.py` | Data schema versioning, core/cache catalogues, and backup-first migrations. |
| `app/security.py` | Local browser origin policy in addition to CORS. |
| `app/prompts/` | Task-specific prompts; changes here can change AI behavior. |
| `app/models.py` | API data schemas. |
| `app/storage.py`, `app/persistence.py` | World reads/writes, locking, journaled commits, and crash recovery. |
| `app/action_guard.py` | Request receipts against duplicate processing and revisions against stale writes. |
| `app/llm_client.py` | Provider calls, failures, retries, and mock responses. |

Routes call service code, and service code uses storage or LLM modules. Small modules should not import `main`, routes, or orchestration modules in reverse. Compatibility bridges are deliberate exceptions retained to avoid breaking integrations.

### Compatibility boundaries

`app/compat.py`, `app/engine.py`, and `backend/prompts.py` preserve legacy import names. Functions moved away from chapter/checkpoint engine modules remain re-exported from their previous locations. New code should import from the owning module. `main.call_llm` and selected legacy-test patch points remain supported.

`backend/models.py` is a legacy schema module. Add new models in `app/models.py`.

## UI

`ui/src/pages/` connects pages to the router. The play flow lives in `ui/src/features/play/`:

- `usePlaySession.ts` — play-session state, loading, and player actions.
- `PlaySidebar.tsx` — chapter navigation and world timeline.
- `PlayNarrative.tsx` — narrative text and action input.
- `PlayInspector.tsx` — information drawers and creator tools.
- `types.ts` — feature-shared types.

`PlayPage.tsx` composes these pieces. Reusable cross-feature components remain in `src/components/`. As a different feature grows, give it its own hooks, components, and types in `features/<name>/`.

## Tests and limits

`backend/tests/` contains independent regression tests. `backend/test_engine.py` is a sequential legacy suite that shares state; add new tests under `backend/tests/`. Always use `backend/run_tests.py` to isolate data and block live AI calls.

The UI has two test layers: `ui/src/**/*.test.tsx` uses Vitest with jsdom and a mocked API client; `ui/e2e/` uses Playwright with mocked API routes. Run `npm run test:ui` and `npm run test:e2e`; fixtures must not need accounts, keys, or live AI services.

Automated tests use mock AI responses and do not measure prose quality with live models. Public playtesting should evaluate live generation separately.
