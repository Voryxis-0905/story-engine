# Story Engine — Fix Round 2: Prose Quality & Pacing

Round 1 (10 tasks, `story-engine-workorder.md`) fixed correctness bugs — chapter-close logic, world-config schema, prelude generation, card unlocking, error UX. All verified working. This round is different: it targets **why the actual prose still doesn't feel satisfying to play**, even though the engine now runs correctly. These are quality/pacing issues, not correctness bugs — verified in source, still unfixed as of this file.

---

## ⚠️ HARD RULES — same as Round 1, still apply without exception

1. **STOP after every task.** One task → report → full stop. Wait for the next message.
2. **Never claim a fix without actually opening and editing the real file.** If what you find doesn't match this task's description, stop and report the mismatch — don't guess.
3. **Verification must be real and reproducible.** Run `python3 backend/test_engine.py` (or add a new check to it) and show actual output, or manually trace a concrete before/after example. "This should work now" is not verification. Prefer adding a persistent test over a throwaway manual trace — Round 1's Task 4 test suite (14 assertions saved into `test_engine.py`) is the standard to match.
4. **No fabricated line numbers or fake test runs.** Only cite what you've actually opened this session.
5. **Stay in scope.** Don't touch unrelated code. Note anything else you notice under "Noticed but not fixed."
6. **If a task is bigger or more ambiguous than described, stop and produce an implementation plan + open questions first** (like Round 1's Task 4) rather than guessing at a design and building it.
7. **Don't regress what works.** The consistency checker, checkpoint transitions, prelude flow, and the full Round 1 fix set all currently pass real tests — don't break them.

### Report format (same as Round 1)

```
## Task N — [title]
**Files/functions touched:** ...
**What I found when I opened the file:** ...
**What I changed:** (before → after, actual diff)
**How I verified it:** (real test output or real manual trace)
**Status:** ✅ Done / ⚠️ Partial / ❌ Blocked
**Noticed but not fixed:** ...
```
Then stop.

---

## 🔴 Task 11 — Context window is too narrow for coherent pacing [VERIFIED]

**File:** `backend/app/engine.py`, `RECENT_TURNS_CONTEXT_LIMIT = 2` (line 138), `CHAPTER_SUMMARY_BUDGET_RATIO = 0.03` (line 142).

Confirmed: the writer only sees the last 2 turns verbatim; everything older is compressed into a running summary capped at ~3% of total story word count. This causes event-cramming (the model writes densely because it knows context is short) and tonal drift between turns — the model is effectively re-deriving most of the story state from a heavily lossy summary of its own prior output.

**Fix:**
- Raise `RECENT_TURNS_CONTEXT_LIMIT` (test with 3–4) and re-check the summary budget ratio isn't starving `running_summary` as a result of the tradeoff.
- Make both of these **scale with `pacing_level`** — a Slowburn world benefits from more verbatim recent context (scenes unfold slower, so 2 turns back may still be mid-scene); a Fast-paced world can tolerate a smaller window since it's compressing more aggressively by design. Add a small lookup (e.g. Slowburn → 4 turns / higher budget ratio, Balanced → 3, Fast → 2) rather than a single global constant.

**Acceptance:** generate the same story premise once with `Slowburn` and once with `Fast`, and confirm the writer's context payload actually differs in verbatim turn count between the two runs (add a test or log assertion for this, not just an eyeballed read).

---

## 🔴 Task 12 — Writer prompt forces short output regardless of intended chapter length [VERIFIED]

**File:** `backend/prompts.py`, `WRITER_SYSTEM_PROMPT`, rule 8 (~line 263):

> *"This single call is one 'turn' — a short, focused beat, not a whole chapter."*

This directly trains the model toward short output on every single call, independent of `pacing_level`, independent of how many turns are left before the chapter's word/turn thresholds are met (Round 1 Task 1's fix), and independent of the new length setting from Task 13 below. Even with the close-logic bug fixed, chapters now just take more short, choppy turns to reach the same word count instead of reading as fewer, fuller ones.

**Fix:** rewrite rule 8 so "how much to write per turn" is explicitly driven by config, not a fixed philosophy baked into the prompt. At minimum, the instruction should say something like: *"Write enough prose to meaningfully advance this beat — target roughly `words_per_turn_target` words for this turn (derived from the world's pacing/length settings), not an arbitrarily short snippet. Do not pad or ramble to hit the target, but do not artificially truncate a scene that needs more room."* The actual `words_per_turn_target` value should come from Task 13's setting (see below) combined with `pacing_level`.

**Acceptance:** compare writer output length across a few turns before and after the change, holding pacing/length settings constant, and confirm turns are no longer uniformly clipped to a "short beat" regardless of the actual target.

---

## 🟠 Task 13 — Add a user-facing "Output Length" setting [NEW FEATURE — plan first, see open questions]

Currently, chapter/turn length is entirely fixed by hardcoded constants (`CHAPTER_SOFT_CLOSE_WORDS = 900`, `CHAPTER_SOFT_CLOSE_TURNS = 5`, `CHAPTER_HARD_CLOSE_TURNS = 8`) — no user control, and this is separate from `pacing_level` (which controls story rhythm, not prose density/output size). Add a real setting for how much prose the user wants per turn/chapter.

**Suggested shape** (adjust if you find a better fit once you're in the code):
- A new `world_config` field, e.g. `"output_length": "Concise" | "Standard" | "Detailed"`, following the same pattern as existing enum-style fields (`pacing_level`, `pov_angle`).
- Each preset maps to concrete values for `CHAPTER_SOFT_CLOSE_WORDS`/`CHAPTER_SOFT_CLOSE_WORDS`-equivalent-per-world and a target words-per-turn passed into the writer prompt (feeds Task 12's `words_per_turn_target`).
- Exposed in the frontend wherever other world-level settings live (Creator Mode → World Config tab, alongside `pacing_level`/`pov_angle`), not as a raw token/max_tokens number — the user thinks in terms of "how much do I want per turn," not raw LLM token counts.

**Before implementing, answer these (recommend a default, then proceed — don't block indefinitely, just flag your reasoning):**
1. Should `output_length` be settable only at world creation (interview question, like pacing/POV), or also editable later mid-story from Creator Mode? *(Recommendation: both — set a sensible default at creation, but allow changing it later since a user's taste for density may change once they're actually reading their own story.)*
2. Should the three presets scale the **hard** turn ceiling (`CHAPTER_HARD_CLOSE_TURNS`) too, or only the soft word/turn thresholds? *(Recommendation: scale both — a "Detailed" world should get more turns AND a higher word floor before a chapter is forced to close, otherwise the hard ceiling silently caps how much "Detailed" can actually achieve.)*
3. Does this interact with Task 11's context-window scaling? *(Recommendation: yes — treat pacing_level and output_length as two independent inputs that both feed into a single combined lookup for context window size + word targets, rather than layering two separate override systems that could conflict.)*

**Acceptance:** create a world with `output_length: "Detailed"` and one with `"Concise"`, same premise, and confirm actual chapter word counts differ meaningfully and predictably between them.

---

## 🟡 Task 14 — Writer prompt never actually encourages on-screen dialogue [VERIFIED — from original testing report, never addressed]

Across a full real playtest (8 chapters, ~4,000+ words), not a single line of spoken dialogue occurred — only internal monologue and narration. `WRITER_SYSTEM_PROMPT` has no instruction pushing the model toward dialogue where a scene calls for it; the only "dialogue" mentions in `prompts.py` are about *preserving* existing dialogue during summarization (line 374) or extraction fidelity (line 529) — nothing at the generation stage.

**Fix:** add explicit guidance to `WRITER_SYSTEM_PROMPT` — something like: *"When a scene involves more than one character present and aware of each other, prefer showing their exchange through actual spoken dialogue rather than only narration/internal summary of what was said. Use dialogue naturally where it serves the scene; don't force it into solitary/introspective scenes that don't call for it."* Keep it conditional (not every scene needs dialogue — e.g. a solo protagonist scene shouldn't be forced to invent someone to talk to), but currently there's zero nudge in either direction, which is why it's been completely absent even in multi-character scenes.

**Acceptance:** generate a scene you know involves two characters interacting (e.g. a checkpoint description mentioning a conversation), and confirm actual dialogue lines appear in the output where none did before.

---

Start with **Task 11**. Report using the format above, then stop.
