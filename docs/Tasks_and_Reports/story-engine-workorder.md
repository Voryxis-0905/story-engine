# Story Engine — Fix & Upgrade Work Order

You are picking up confirmed bugs and one new feature request on "story-engine", verified by directly reading the actual source in this codebase (not just trusting a tester's report). Each task below has been checked against real file/line references before being written down. Your job is to work through them **one at a time**, in order, following the hard rules below without exception.

---

## ⚠️ HARD RULES — apply to every single task, no exceptions

1. **STOP after every task.** Finish exactly one numbered task, report on it using the format in "How to report" below, then **stop and wait for the next instruction.** Do not proceed to the next task on your own, even if it seems obvious or related. Do not batch multiple tasks together "for efficiency." One task → report → full stop.

2. **Never claim something is fixed without having actually read and edited the real file.** Before writing any fix, `view`/`grep`/open the exact file and function named in the task and confirm the described code is actually there, at roughly the described location. If what you find doesn't match the task's description, **stop and report the mismatch instead of guessing** — do not invent a plausible-sounding fix for code you haven't actually seen.

3. **Never report a task as done based on what a fix "should" do.** A task is only done when you have actually made the edit AND verified it — by running the relevant test file (`test_engine.py`, `test_fallback.py`, `patch_tests.py`, etc.), or by tracing through the exact code path manually and showing the before/after behavior with real inputs. "This should now work" is not verification.

4. **Do not fabricate line numbers, function names, or file paths in your report.** Only cite locations you have personally opened and confirmed in this session. If you're unsure, say so.

5. **Do not touch code outside the scope of the current task.** No "while I was in there I also cleaned up X." If you notice something else that looks broken while working, note it briefly in your report under "Noticed but not fixed" — do not fix it without being asked.

6. **If a task turns out bigger or more ambiguous than described, stop and ask rather than partially fixing it and calling it done.** A half-fix reported as complete is worse than an honest "this needs a design decision from you first."

7. **Do not regress working functionality.** The consistency checker's boundary rejection, the checkpoint auto-transition logic, and the overall planner→writer→checker→summarizer pipeline structure currently work correctly — don't refactor these away as a side effect of a fix.

### How to report (use this exact structure for every task)

```
## Task N — [title]
**Files/functions touched:** ...
**What I found when I opened the file:** (confirm it matched the task description, or note the discrepancy)
**What I changed:** (before → after, in plain language, plus the actual diff)
**How I verified it:** (test run output, or manual trace with real example input/output)
**Status:** ✅ Done / ⚠️ Partially done (explain what's left) / ❌ Blocked (explain why)
**Noticed but not fixed:** (optional, anything unrelated you spotted)
```

Then stop. Wait for the next message before starting the next task.

---

## 🔴 Task 1 — Fix chapter soft-close ignoring word count [VERIFIED]

**File:** `backend/app/engine.py`, function `decide_chapter_closed()`, ~line 1434–1450.

Confirmed in source: `total_turns >= CHAPTER_SOFT_CLOSE_TURNS` (line 1444, currently 5) returns `True` on its own, completely independent from the word-count check at line 1448 (`total_words >= CHAPTER_SOFT_CLOSE_WORDS`, currently 900). This means chapters always close at 5 turns regardless of word count, making the word threshold unreachable in practice.

**Fix:** make soft-close require both conditions:
```python
if total_turns >= CHAPTER_SOFT_CLOSE_TURNS and total_words >= CHAPTER_SOFT_CLOSE_WORDS:
    return True
```
Keep `CHAPTER_HARD_CLOSE_TURNS` (line 1442, currently 8) as a true independent ceiling — but reassess whether 8 is still reasonable once soft-close can run longer; note your reasoning in the report rather than silently changing the constant.

**Acceptance:** trace through a scenario with `total_turns = 5` and `total_words = 600` — chapter should NOT close. Then `total_turns = 6, total_words = 950` — chapter SHOULD close.

---

## 🔴 Task 2 — `pacing_level`, `pov_angle`, `prelude_enabled` are never written into generated worlds [VERIFIED]

**File:** `backend/prompts.py`, `WORLD_BUILDER_SKELETON_PROMPT`.

Confirmed in source: the exact JSON output schema this prompt instructs the LLM to return does **not include** `pacing_level`, `pov_angle`, or `prelude_enabled` as keys anywhere in `world_config`. Meanwhile `backend/app/engine.py` (`TEMPLATES["world_config.json"]`, ~lines 67–69) hardcodes defaults (`"Balanced"`, `"3rd_person_limited"`, `False`). Since the generation schema never asks for these fields, **the defaults always win regardless of what the user answered in the interview.**

**Fix:** add `pacing_level`, `pov_angle`, and `prelude_enabled` to the exact JSON structure block in `WORLD_BUILDER_SKELETON_PROMPT`, with an instruction telling the model to infer them from the user's interview answers (which arrive as free text in the payload — check `world_builder_interview_respond` in `backend/app/routes/builder_routes.py` for how Q&A gets folded into the prompt payload). Valid values per `backend/app/models.py`: `pacing_level` ∈ `{"Slowburn", "Balanced", "Fast"}`, `pov_angle` ∈ `{"1st_person", "3rd_person_limited", "3rd_person_omniscient"}`, `prelude_enabled` is boolean.

**Acceptance:** run a world creation with interview answers that unambiguously state Slowburn + 1st person + wants a prelude, and confirm the resulting `world_config.json` has those exact values, not the defaults.

---

## 🔴 Task 3 — `required_conditions` is structurally supported but never meaningfully populated [VERIFIED]

**File:** `backend/prompts.py`, `WORLD_BUILDER_SKELETON_PROMPT`; reference implementation in `backend/app/routes/world_routes.py` (seed-demo world, ~lines 336–383).

Confirmed: `checkpoint_conditions_met()` in `engine.py` (~line 1004) is a real, working gate — it supports stat thresholds (`{"field": "char_x.power_stat.exp", "op": ">=", "value": 30}`), flag containment (`"op": "contains"`), set membership (`"op": "in"`), and `all`/`any` composites. The seed-demo world (`char_xueli`/`char_gu_changge`) uses this correctly. But `WORLD_BUILDER_SKELETON_PROMPT`'s example schema shows `"required_conditions": []` with no guidance on when to populate it — so AI-generated worlds leave it empty on every checkpoint, meaning checkpoints always auto-pass regardless of character state.

**Fix:** add guidance to `WORLD_BUILDER_SKELETON_PROMPT` (near the existing "SCOPE & PACING RULES" section) instructing the model: checkpoints representing a major turning point or climax should generally have at least one `required_conditions` entry tied to character state (a stat threshold, a knowledge flag, or a status effect) rather than defaulting to `[]`; only truly time-based/unconditional transitions should stay empty. Include one short example condition in the prompt (can adapt from the seed-demo pattern) so the model has a concrete template to follow.

**Acceptance:** generate a checkpoint chain of 4+ checkpoints and confirm at least the later/climax checkpoints have a non-empty, semantically sensible `required_conditions` entry — not just copy-pasted boilerplate.

---

## 🟠 Task 4 — Build a real "Chapter 0" / prelude generation path [NEW FEATURE]

**Files:** likely `backend/app/engine.py` + `backend/app/routes/` (wherever chapter/opening generation is triggered) + `backend/prompts.py`.

Confirmed: `prelude_enabled` is currently a fully dead field — it's asked about in the interview prompt (`prompts.py` line ~55), stored in `world_config`, and forwarded in the writer payload every turn (`engine.py` ~line 2094) — but **no code path anywhere reads it to actually change generation behavior.** There is no `chapter_index = 0` concept anywhere in the codebase; everything starts at `chapter_index = 1`.

**What to build:** when `prelude_enabled` is `true`, generate a distinct prelude chapter (`chapter_index = 0` or an equivalent marker — check how `chapters_data` structures are read elsewhere before deciding) automatically as part of world creation completion, before the player's first real turn. This prelude should:
- Introduce the world/premise from a narrator or non-protagonist vantage point (poetic/scene-setting, not player-interactive)
- Close by transitioning ("cutting") to the protagonist's actual current scene/setting, so chapter 1 can pick up naturally from there
- Be clearly distinguishable in the UI/data from chapter 1 (don't just silently prepend it to chapter 1's text)

This is a genuinely new prompt + generation step, not a one-line fix. If it's bigger than a single task can reasonably cover, **stop after producing a concrete implementation plan (what functions/routes/prompts need to change) and wait for confirmation before writing the actual generation logic.**

---

## 🟠 Task 5 — Card `status: "locked"` silently excludes allowed characters from AI context [VERIFIED]

**File:** `backend/app/engine.py`, function `get_active_cards()`, ~lines 222–237.

Confirmed: this function skips any card where `status != "unlocked"` (line 227) *before* even checking `allowed_characters`. In the playtested world, `Kaito_Reeves` has `status: "locked"` in `card_registry.json` while already listed in `allowed_characters` for checkpoints cp_2 and cp_4's boundary — meaning when he's narratively allowed to appear, **his character card content (personality, backstory) is never actually fed to the writer**, degrading how he's written.

**Fix:** find wherever card `status` is supposed to transition from `"locked"` to `"unlocked"` (likely tied to `unlock_checkpoint_id` matching the current/completed checkpoint) and confirm that transition is actually firing when a checkpoint's `allowed_characters` includes a still-locked card. Either the unlock trigger is missing for this case, or `unlock_checkpoint_id` isn't being cross-checked against `allowed_characters` consistently — trace the actual unlock logic before deciding which.

**Acceptance:** create a scenario where a checkpoint's `allowed_characters` includes a character card, and confirm that card's `status` becomes `"unlocked"` by the time that checkpoint is active, and that `get_active_cards()` includes it.

---

## 🟡 Task 6 — Language-detection for boundary rejection errors is a fragile heuristic [VERIFIED, but re-scoped from earlier report]

**File:** `backend/app/engine.py`, `detect_story_language()` (~line 1268) and `BOUNDARY_HARD_REJECT_TEMPLATES` (~line 1314).

Note: an earlier report claimed this was "hardcoded Vietnamese with no English option" — that's **not accurate**, both `"en"` and `"vi"` templates exist and `"en"` is the fallback default. The real issue: `world_config` has **no explicit `language` field** (confirmed absent from `TEMPLATES["world_config.json"]`), so detection always falls back to keyword-sniffing recent text against `VI_COMMON_WORDS`, a small set that includes at least one common English word ("do"), creating a real (if not yet reproduced) risk of false-positive Vietnamese detection on English stories.

**Fix:** add an explicit `language` field to `world_config` (populated at world-creation time based on the interview language, similar to how other metadata is set), and have `detect_story_language()` check and trust that field first before falling back to heuristics. This removes the guessing for the common case entirely.

**Acceptance:** confirm a world created in English gets `world_config["language"] = "en"` explicitly, and that `raise_boundary_hard_reject()` uses the English template without needing to sniff any text.

---

## 🟢 Task 7 — Foreshadowing tracker can desync from `open_threads` [LIKELY PROMPT-DISCIPLINE ISSUE, re-scoped]

**File:** `backend/prompts.py` (planner prompt output instructions) + `backend/app/engine.py`, `apply_foreshadowing_changes()` (~lines 790–839).

Note: an earlier hypothesis assumed the write-back mechanism was missing — it isn't. `apply_foreshadowing_changes()` correctly sets `payoff_chapter` when it receives a `foreshadowing_tracker_add` item with matching `id` and status `"revealed"`/`"resolved"`. The likely real cause: the planner LLM sometimes describes a payoff in free-text `open_threads_update` without also emitting the matching structured `foreshadowing_tracker_add` entry for that `id`, so the write-back never triggers even though the narrative clearly resolved it.

**Fix:** strengthen the planner prompt's instructions (in the section covering `tier_4_thread_ledger` / foreshadowing) to explicitly require: whenever a foreshadowing payoff is narrated, the model MUST also emit a matching `foreshadowing_tracker_add` entry with the correct `id` and `status`. Consider whether a lint/consistency check should flag it when `open_threads_update` text mentions payoff language for a thread but no matching tracker update was emitted in the same turn — this would catch future drift instead of relying purely on prompt compliance.

**Acceptance:** run a turn where a planted foreshadowing thread pays off, and confirm both `open_threads` and `foreshadowing_tracker` reflect it consistently in the same turn.

---

## 🟡 Task 8 — No user-visible error feedback on generation failure [FROM TESTER REPORT — confirm against actual frontend code before fixing]

The tester reported that when a 409 (boundary rejection) or other generation failure occurs, the relevant button just silently re-enables with no toast/banner — the failure text exists in the HTTP response but isn't surfaced. Before fixing, actually inspect the relevant frontend handler (`frontend/app.js`) for how it currently handles non-200 responses from chapter/world-generation endpoints, and confirm this is really happening as described.

**Fix (if confirmed):** add a visible, non-blocking error toast on generation failure showing the HTTP status and a short human-readable reason (the `detail` field already contains a full explanation server-side, per Task 6's templates — just needs to reach the UI).

---

## 🟡 Task 9 — No retry/edit affordance after a 409 rejection [FROM TESTER REPORT — confirm against actual frontend code before fixing]

The rejection message tells the user their input "is NOT lost, please try again," but reportedly there's no actual retry button or pre-filled input — the user must manually re-type. Confirm this against the actual input-handling code in `frontend/app.js` before fixing. If confirmed, add a retry action that re-populates the input box with the user's last submitted text so they can edit and resubmit without retyping from scratch.

---

## 🟢 Task 10 — Minor UX polish [FROM TESTER REPORT — confirm each before fixing]

- Suggested-action chips reportedly stay visible after one is clicked/selected — should clear/hide after selection or submission.
- The input placeholder text reportedly hardcodes an old demo world's character names ("e.g. 'Xue Li steps closer to Gu Changge...'") regardless of the actual current world — should be generic or dynamically reference the current protagonist if easy.

Treat each of these as its own sub-task with its own report — don't fix both silently in one pass without separate verification.

---

Start with **Task 1**. Report using the format above, then stop.
