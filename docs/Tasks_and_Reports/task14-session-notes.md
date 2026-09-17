# Task 14 — Session Notes

## Objective
Add explicit guidance to `WRITER_SYSTEM_PROMPT` encouraging on-screen dialogue in multi-character scenes, since a full playtest produced zero spoken dialogue lines — only internal monologue and narration.

## Files touched

### `backend/prompts.py` (line 281)
**Change:** Added rule 16 to `WRITER_SYSTEM_PROMPT`:

```
16. When a scene involves more than one character present and aware of each other,
prefer showing their exchange through actual spoken dialogue rather than only
narration or internal summary of what was said. Use dialogue naturally where it
serves the scene; do not force it into solitary or introspective scenes that do
not call for it.
```

The rule is intentionally conditional: it only applies when multiple characters are present and aware of each other. Solitary/introspective scenes are explicitly excluded.

### `backend/test_engine.py` (line ~3852)
**Change:** Added persistent assertion:
```python
check("spoken dialogue" in main.WRITER_SYSTEM_PROMPT,
      "14. WRITER_SYSTEM_PROMPT encourages spoken dialogue")
```

## Verification
- `prompts.py` compiles cleanly
- "spoken dialogue" confirmed present in `WRITER_SYSTEM_PROMPT`
- Existing 12c checks unchanged and still pass

## Noticed but not fixed
- None
