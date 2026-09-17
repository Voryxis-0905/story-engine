# Story Engine — Testing Report

**World:** echo_terminal ("The Voice in the Static")
**Arc 1:** Complete (cp_0 → cp_4, 6 chapters)
**Arc 2:** In progress (Ch. 7–8)
**Total AI output:** ~4,263 words across 8 chapters
**Backend:** uvicorn, FastAPI, localhost:8000
**Model:** deepseek-v4-flash-free via opencode.ai/zen (free tier)
**Testing language:** English

---

## Bugs

### 1. Chapter soft-close fires at 5 turns unconditionally (line 1444 of engine.py)

```python
if total_turns >= CHAPTER_SOFT_CLOSE_TURNS:  # currently 5
    return True
```

This closes the chapter after 5 turns **regardless of word count**. The 900-word soft-close at line 1448 is a separate independent trigger, not a paired condition. This means:

- Even if `CHAPTER_SOFT_CLOSE_WORDS` is raised to 2000, the chapter still closes at 5 turns with ~750-1000 words.
- The word-count threshold is effectively unreachable for most chapters because the 5-turn limit hits first.
- This is the single biggest cause of short chapters. Raising constants alone won't fix it.

**Likely intended behavior:** `if total_turns >= CHAPTER_SOFT_CLOSE_TURNS and total_words >= CHAPTER_SOFT_CLOSE_WORDS`

### 2. Boundary checker returns Vietnamese error text for English stories

When the consistency checker rejected an action (twice in cp_0), the error text was entirely in Vietnamese despite the world being set up in English. This was confusing during English-language testing.

**File:** `raise_boundary_hard_reject()` in engine.py (lines 1328–1350), templates at lines 1314–1325.

### 3. Consistency bug: Rika Tan is mentioned but never appears

The Status tab shows "Rika Tan's Erasure" as unlocked lore, with events tracking her as Kaelen's client. But in the actual story text, she is referenced only as backstory — she never has an on-screen scene or dialogue. The lore card exists, the event is logged, but the prose never delivered the beat.

This suggests the extractor/summarizer is logging events from planner output that the writer stage then skips, or that the running summary preserves facts the prose never actually depicted.

### 4. No on-screen dialogue from any character

Across 8 chapters and ~4,000+ words of AI output, there is not a single line of spoken dialogue from any character. Kaelen has internal monologue, the Signal narrates, but no human conversations occur. Whether this is a model behavior issue or a prompt framing issue is unclear, but it makes the story feel hollow.

---

## Pacing & Architecture Issues

### 5. 900-word soft-close is too low for any arc longer than a short story

- `CHAPTER_SOFT_CLOSE_WORDS = 900`
- `CHAPTER_HARD_CLOSE_TURNS = 8`
- At ~180 words/turn, that's a hard ceiling of ~1,440 words per chapter.

For an 8,000-20,000 word arc target, each of 5–8 chapters needs 1,000–4,000 words. The current thresholds cap chapters at roughly half that minimum.

### 6. Recent-turns context (2 turns) is too small for narrative coherence

`RECENT_TURNS_CONTEXT_LIMIT = 2` means the AI only sees the last 2 turns verbatim. Everything older than that is compressed into a running summary that has a 0.03 budget ratio (ceiling 500 words). The AI is effectively writing most of each turn from a heavily compressed summary of its own output, causing:

- Event density per turn is high (the AI crams because it knows context is short)
- Narrative tone drifts between turns
- The story advances plot beats faster than a human writer would

### 7. Writer prompt instructs brevity

Rule 8 of `WRITER_SYSTEM_PROMPT` says: *"This single call is one 'turn' — a short, focused beat, not a whole chapter."* This directly trains the LLM to produce short output. Combined with the 5-turn soft-close bug, the system has two independent mechanisms forcing short content.

### 8. No pacing-level differentiation in practice

The interview collects `pacing_level` (Slowburn/Balanced/Fast) and stores it in `world_config`, but:

- The planner prompt mentions it only in comments/rules for sub-beat counts
- The chapter-closing thresholds in `decide_chapter_closed()` don't consult it at all
- The writer prompt doesn't reference it

A Slowburn world and a Fast world produce identically paced output.

### 9. Arc 2 has no checkpoint structure (post-arc "null" state)

After completing all 5 checkpoints in a "Single Arc" world, the checkpoint is `null`. The story engine continues gracefully (the AI keeps writing), but there is no checkpoint boundary, no scope enforcement, and no arc-extension mechanism that generates new checkpoints. The `ARC_EXTENDER_PROMPT` exists but appears to be unused in the single-arc flow.

---

## Minor Issues

### 10. Free-tier model latency makes testing slow

Each API call takes 60–120+ seconds. Combined with the planner + writer two-stage pipeline, every turn takes 2–4 minutes. This makes iteration painful. Not a bug, but worth noting if the target audience includes free-tier users.

### 11. 409 errors have no user-friendly fallback in the UI

When the boundary checker rejects an action twice, the user gets a hard 409 with raw error text. The action text says "your action is NOT lost — please try again," but there's no UI mechanism to retry or edit the last input — the user must re-type manually.

### 12. Suggested actions use demo-world example in placeholder text

The input textbox placeholder says: *"What does your character do next? (e.g. 'Xue Li steps closer to Gu Changge and asks about his past')"* — this references characters from the seed demo world, not the user's current world.

---

## Positive (brief)

- Multi-agent architecture (planner → writer → checker → summarizer) is well-structured and extensible.
- The Status tab is genuinely useful — event log, lore codex, foreshadowing tracker, story clock.
- The running summary + memorable beats system is a thoughtful approach to context management.
- Story quality is good when given room; the concepts (Project Chimera, author/character split) are compelling.
- The interview-based world builder with pacing/POV questions is the right approach.
