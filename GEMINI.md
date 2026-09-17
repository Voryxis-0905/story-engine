# Story Engine — Testing & Debugging Rules

> **Scope**: These rules apply to all sessions within this project.
> They govern agent behavior specifically in the **tester role** (playing, exploring, and quality-assessing the story engine).

## 1. Never Use `force-advance` to Mask Bugs
When a checkpoint does not advance automatically, investigate the root cause
in `engine.py` (`checkpoint_conditions_met`, `advance_checkpoint_if_ready`).
Never call `POST /worlds/{id}/checkpoint/force-advance` as a workaround for
a systemic bug. Always find and fix the underlying issue first.

## 2. Verify Code Fixes Programmatically Before Trusting Server Behavior
After editing `engine.py`, always run a direct Python one-liner to confirm the
function behaves correctly before relying on HTTP responses or server logs:
```
python -c "import sys; sys.path.append('backend'); from app.engine import read_world_file, advance_checkpoint_if_ready; ..."
```
Do not assume a code edit worked just because the server restarted without errors.

## 3. Slowburn Pacing — No Rushing Story Turns
When playing a `pacing_level: "Slowburn"` world, never rush checkpoints or
story beats. Each turn should contain one focused, deliberate action. Let
chapters close naturally through narrative momentum. The tester's role is to
*experience* the story, not speed-run it for the sake of showing progress.

## 4. Language Consistency — All Fields in English
World language is `"en"`. All AI-generated fields in `character_state.json`
(realm, known_skills, status_effects, speech_style, personality, etc.) must be
in English. Flag and report any non-English strings found during testing.
Do not silently "normalize" them — report and fix the root cause in the
extraction or generation prompt.

## 5. Never Skip or Hide Details — Note Everything and Report Honestly
As a tester, every anomaly — no matter how small — must be:
- **Noted** at the moment it is observed
- **Reported** to the user with full context (what was expected vs. what happened)
- **Not concealed** by workarounds, silent patches, or misleading status updates

Examples of forbidden behavior:
- Announcing "checkpoint advanced" when it has not
- Using `force-advance` to paper over a failing condition check
- Silently fixing a Vietnamese string without reporting it was there
- Claiming a code fix worked before verifying it programmatically

If a bug or inconsistency is found, **stop, document it, and surface it to the user first**.
Fixes come after honest reporting, never before.
