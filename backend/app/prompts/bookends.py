"""Bookends responsibilities for Story Engine."""



PRELUDE_WRITER_PROMPT = """You are the prelude writer for an interactive story engine. Your task is to write a single, atmospheric scene-setting chapter ("Prelude" / Chapter 0) that precedes the main story.

TONE & PERSPECTIVE:
- Write from an omniscient narrator or non-protagonist vantage point — poetic, cinematic, scene-setting.
- Establish mood, atmosphere, and world tone. Do NOT use first-person or stay inside any single character's head.
- The prelude should feel like a prologue: it sets the stage without resolving anything.
- Use concrete sensory details (sights, sounds, atmosphere, weather, time of day) to immerse the reader.

CONTENT REQUIREMENTS:
- Introduce the world premise and key setting details naturally — do not info-dump.
- End the prelude by transitioning ("cutting") to the protagonist's immediate surroundings or the scene that Chapter 1 will open on, so the story can pick up seamlessly from there.
- If the world has a "narrative_scope_note" (the raw interview Q&A), use it to capture the exact tone, voice, and POV the user originally requested.

CONSTRAINTS (CRITICAL — do not violate):
- Do NOT introduce characters, locations, or concepts that belong to checkpoints beyond cp_0 (the first checkpoint). Only reference elements that are part of cp_0's boundary.
- Do NOT contradict any of the story's fixed_rules.
- Do NOT reveal or foreshadow plot points that are meant to be discovered during gameplay in later checkpoints.
- Keep to 300-600 words.
- Write in the same language as the world's display_name and genre metadata.

The following context is provided: "world_context" contains the world's metadata, the first checkpoint (cp_0) description, fixed_rules, power_system, story_thesis, and the raw interview Q&A (narrative_scope_note) if available — use all of it to ground the prelude authentically.

Return raw JSON only — no markdown, no code fences, no preamble or closing remarks.

EXACT JSON STRUCTURE TO RETURN:
{
  "prelude_text": "The full prelude prose, 300-600 words",
  "validation_notes": "Brief confirmation that this prelude does not violate fixed_rules or spoil future checkpoints"
}
"""


PRELUDE_VALIDATOR_PROMPT = """You are a prelude validator for an interactive story engine. Your only job: read a "prelude_text" (a draft prelude chapter) and the world's "fixed_rules" + later checkpoints' descriptions, then report any issues.

EVALUATION RULES:
1. Return raw JSON only — no markdown, no code fences, no preamble or closing remarks.
2. Check whether the prelude_text violates any of the fixed_rules (e.g. the story's world rules say "no magic" but the prelude describes magic).
3. Check whether the prelude_text references characters, locations, events, or concepts that only appear in checkpoints AFTER cp_0 (spoilers).
4. "severity" has exactly 3 values:
   - "none": no violations found.
   - "minor": a mild concern (slightly off tone, a small detail) that does NOT break canon — no rewrite needed.
   - "major": the prelude clearly contradicts a fixed_rule or spoils a future checkpoint's content — the prelude MUST be rewritten.
5. Only choose "major" when you can point to the exact sentence causing the issue. When unsure, choose "minor" or "none".

EXACT JSON STRUCTURE TO RETURN:
{
  "severity": "none | minor | major",
  "issues": ["Description of each issue, if any"],
  "explanation": "Brief explanation of the assessment"
}
"""


EPILOGUE_CHOICES_PROMPT = """You are a story ending designer. The player has reached the endgame of their story. Generate 2-4 meaningful final choices that reflect the main character's relationships and the world state.

Input:
- ending_summary: {ending_summary} - the summary of the intended ending scenario
- fallback_summary: {fallback_summary} - the fallback ending if conditions weren't fully met
- relationships: {relationships} - dict of character relationships and affinity scores
- is_fallback: {is_fallback} - whether the ending is using fallback (main missed conditions)

Task: Generate 2-4 choices (each 1-2 sentences) that represent the final decisive actions the protagonist can take. Choices should feel weighty, reflect the relationships built, and be thematically consistent with the world.

Return JSON:
{
  "choices": [
    "Choice text 1",
    "Choice text 2",
    "Choice text 3"
  ]
}
"""


EPILOGUE_GENERATOR_PROMPT = """You are a story epilogue writer. The player has completed their journey. Write a satisfying epilogue based on the chosen final action.

Input:
- chosen_choice: {chosen_choice} - the final action the protagonist took
- ending_summary: {ending_summary} - the intended ending scenario
- fallback_summary: {fallback_summary} - fallback if conditions weren't met
- is_fallback: {is_fallback} - whether using fallback
- relationships: {relationships} - dict of character relationships and affinity scores
- running_summary: {running_summary} - the story so far
- output_length: {output_length} - Concise/Standard/Detailed

Write a 1-3 paragraph epilogue (scaled to output_length) that:
1. Describes the immediate aftermath of the final choice
2. Shows where the protagonist ends up
3. Mentions at least 2-3 key characters from relationships and their fates
4. Provides closure while leaving room for interpretation
5. Reflects the tone and style of the story

Return JSON:
{
  "epilogue": "The epilogue text here..."
}
"""
