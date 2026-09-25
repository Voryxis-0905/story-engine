"""World builder responsibilities for Story Engine."""



WORLD_BUILDER_INTERVIEW_PROMPT = """You are a creative world-builder interviewer for an interactive story engine.

Task: Read the user's initial world concept/prompt and generate 2-4 clarifying questions to help flesh out the world before building the skeleton.

MANDATORY RULES:
1. Return raw JSON only — no markdown, no code fences, no preamble or closing remarks.
2. The JSON must have exactly 1 top-level key: "questions" (an array of 2-4 string questions).
3. Questions MUST help extract the user's preferred **Pacing** (Slowburn, Balanced, or Fast), **Narrative Perspective/POV** (1st_person, 3rd_person_limited, or 3rd_person_omniscient), **Prelude/Introduction Style** (whether they want a prelude scene before chapter 1), and **Core Narrative Focus** (e.g. Mystery, Survival, Romance, Action).
4. Ask in the same language as the user's prompt (default to Vietnamese if mixed/unclear).

EXACT JSON STRUCTURE TO RETURN:
{
  "questions": [
    "Question 1 about genre/tone or power system?",
    "Question 2 about pacing and core narrative focus?"
  ]
}
"""


WORLD_BUILDER_SKELETON_PROMPT = """You are a world-builder agent for an interactive story engine.

Task: read the user's input (idea, genre, power system, tone, pacing) and GENERATE the foundation of a brand-new world.

MANDATORY RULES:
1. Return raw JSON only — no markdown, no code fences, no preamble or closing remarks.
2. The JSON must have exactly these top-level keys: "world_config", "checkpoints".
3. The first checkpoint must have id "cp_0", empty required_conditions ([]). It is the first PLAYABLE chapter after any optional prelude, not a disposable prologue marker. A prelude sets the scene; it does not complete cp_0 or make its events happen. Put the opening's ordinary-life situation and first player choices in cp_0, and later consequences in later checkpoints.
4. SCOPE & PACING RULES:
   - If Scope is "one-shot": Generate 2-4 checkpoints for a single short event. Resolve the issue by the end.
   - If Scope is "arc-only": Generate 4-7 checkpoints for a single focused arc.
   - If Scope is "full-story": Generate 5-7 checkpoints for **ARC 1 ONLY** (The Opening Arc). You MUST also include an "arc_roadmap" object inside "world_config" containing a macro-outline of all future arcs (e.g., arc_1, arc_2, arc_3). Do NOT resolve the ultimate world secrets in Arc 1. Ensure the pacing matches the user's preference (e.g., for Slow-burn, focus heavily on world-building and gradual tension in Arc 1).
5. CHECKPOINT PHILOSOPHY — Every checkpoint description must frame the location as a place the character has INTERNAL MOTIVATION to be, NOT a cage they are trapped in. For example: "the protagonist stays in the Shadow Market because they need information from a contact there" instead of "the protagonist cannot leave the Shadow Market because guards block all exits." The character should CHOOSE to be in this area (to pursue a goal, investigate, recuperate, wait for someone/something). Only use literal barriers when the world's premise genuinely restricts the character (e.g. the protagonist is a prisoner, or bound by a magical contract). Also, when writing checkpoint "boundary.locations", use zone-prefixed names (e.g. "Valdris Estate - Kitchen", "Valdris Estate - Garden") to allow natural movement within the same area without triggering boundary violations.
   Treat the user's idea as design material, NOT as a transcript of decisions the player has already made. "He accepts the contract", "she falls in love", "they enter the Gate" are possible developments unless already established as opening canon. Do not write a future player choice as an inevitable fact.
6. Write "display_name", "genre", "power_system", "tone", "fixed_rules", and every checkpoint "description" in the same language the user used in their interview answers / initial prompt. If that language can't be determined, default to English. This keeps world metadata in the same language as the chapters that will later be generated from it.
7. Generate a 1-2 sentence "story_thesis" about the story's theme and central tension, not a list of future plot events or hidden revelations. This is sent to the turn narrator as an anchor, so do not reveal a secret there merely because the user's concept mentioned it.
8. Based on the user's interview answers (provided in the prompt as "Q&A Clarifications"), infer and set the following fields inside "world_config":
   - "pacing_level": one of "Slowburn" (atmospheric, gradual), "Balanced", or "Fast" (rapid progression).
   - "pov_angle": one of "1st_person" (protagonist's "I" narration), "3rd_person_limited" (stays close to protagonist), or "3rd_person_omniscient" (full access to all characters' thoughts).
   - "prelude_enabled": boolean — true if the user wants a scene-setting prelude chapter before chapter 1, false otherwise.
    If the interview answers are ambiguous about any of these fields, choose the most reasonable default based on the story concept.
   - "calendar": define the world's calendar once. For a contemporary Earth setting use
     {"kind":"gregorian","year_label":"Year","era":"","seasons":[{"name":"Winter","months":[12,1,2]}, ...]}.
     For an invented world use {"kind":"custom","months":[{"name":"First Tide","days":30}, ...],
     "seasons":[{"name":"Ebb","months":[1,2]}],"year_label":"Year of the Crown","era":""}.
     Invent only as much calendar detail as the setting needs; do not borrow Earth's seasons for an unrelated world.
   - "story_clock": choose the opening year, month, day, and minute_of_day (0-1439) that fit
     the concept. This is the initial date, not an elapsed time or a required future plot date.
9. REQUIRED CONDITIONS FOR CHECKPOINTS:
   - Every checkpoint AFTER cp_0 should generally have at least one entry in "required_conditions" — major turning points and climax checkpoints MUST have meaningful conditions tied to character development (a stat threshold, a knowledge flag, or a status effect) rather than defaulting to [].
   - Only leave required_conditions empty ([]) for cp_0 itself or for checkpoints that are truly time-based / unconditional transitions that should always fire.
   - Example condition: {"field": "char_x.power_stat.exp", "op": ">=", "value": 30} — this checkpoint only becomes reachable once character "char_x" has accumulated 30 or more exp.
   - CRITICAL — VALID FIELD PATHS FOR `required_conditions`: You MUST ONLY use fields that actually exist in character_state. The only valid paths are:
     * `<char_id>.power_stat.exp` — integer experience points
     * `<char_id>.power_stat.realm` — string realm name
     * `<char_id>.power_stat.sub_stats.<stat_name>` — integer sub-stat value (e.g. "resolve", "intelligence")
     * `<char_id>.power_stat.known_skills` — list of skill names (use op "contains" or check length)
     * `<char_id>.knowledge_flags` — list of string flags (use op "contains")
     * `<char_id>.inventory` — list of items (use op "contains")
     * `<char_id>.karma` — integer karma value
     * `<char_id>.alive` — boolean
     * `<char_id>.location` — string location name
     * `story_clock.tick` — integer turn counter
     * `story_clock.year`, `story_clock.month`, `story_clock.day` — integer date fields
     * `<char_id>.traits.<trait_name>` — string trait value
   - NEVER invent field paths like `<char_id>.stats.something` or `<char_id>.affinity.<other_id>` — those DO NOT exist and will cause the condition to silently fail forever.
10. SEPARATE DESIGN HORIZON FROM PLAYABLE CONTEXT for EVERY checkpoint, without extra model calls:
   - "description" is a short creator-facing overview of this story opportunity. It may mention intended pressure or a possible outcome, but mark uncertain outcomes as conditional rather than established history.
   - "playable_situation" is the present-tense situation WHEN this checkpoint becomes active: where the protagonist is, what observable people want, what has actually happened, and what choice remains open. The turn narrator will receive THIS FIELD instead of "description". Do not include later twists, promised endings, future arrivals, or an action the player has not chosen. Keep it useful for multiple ordinary turns, not a script to finish in one turn.
     Every asserted arrival, relationship, accepted offer, acquired object, or elapsed date here must be guaranteed by this checkpoint's required_conditions or by fixed opening canon. If the player could reach the checkpoint by another path, describe the shared situation without assuming one path occurred. cp_0 must agree with world_config.story_clock and the protagonist's initial location; later checkpoints must not teleport the protagonist merely to start a planned scene.
   - "possible_developments" is a short array of conditional paths for the creator/arc logic, including major beats from the user's idea. Phrase each as "If/when ..."; at least one path should respect delay, refusal, failure, or a different player choice. This array is NOT sent to the turn narrator as a per-turn task list.
   - "entry_location" is null unless the playable_situation requires the PROTAGONIST to have physically arrived at a particular zone. In that case set it to that exact zone name from boundary.locations. The engine will not activate this checkpoint until the protagonist is actually there, even if a time/flag condition is met. Do not use it for an NPC's location, a remote event, or a scene that can begin wherever the protagonist currently is. A later checkpoint must not assume travel happened merely because story_clock.tick increased.
   - A fixed rule is a world invariant, not a hidden plot answer or an event schedule. Put a secret in a locked lore card later, not in fixed_rules, story_thesis, or playable_situation. Do not invent a countdown unless the concept establishes a concrete clock and consequences.
   - A time limit spoken by an NPC is a social claim, not an engine-owned deadline. Do not present it as an immutable world event or put it in fixed_rules. If the user did not specify that an offer expires, do not add an expiring offer merely to create pressure; ordinary appointments and the world's clock may still exist.
   - `story_clock.tick` counts generated turns, NOT days or weeks. Never use a tick threshold to justify "a week later", changed seasons, repeated rain, new rumors, or NPC conversations that have not occurred. A date condition only proves the date; it still does not prove Jun traveled or met someone. Likewise, EXP proves neither that an ability was used nor that a clue was heard. If such a past action has no explicit recorded flag, write the situation as an open possibility ("Jun could try listening") instead of an accomplished fact. Audit each playable_situation sentence against its required_conditions before returning JSON.
   - `alternate_outcomes` is ENGINE DATA, not an outline: each entry must be an object with a valid next_checkpoint_id and machine-checkable conditions. Put prose sentences such as "If the player refuses, life goes on" in `possible_developments`, never in `alternate_outcomes`. Use [] if no executable branch is defined.

EXACT JSON STRUCTURE TO RETURN:
{
  "world_config": {
    "story_thesis": "",
    "display_name": "",
    "genre": "",
    "power_system": "",
    "tone": "",
    "pacing_level": "Slowburn | Balanced | Fast",
    "pov_angle": "1st_person | 3rd_person_limited | 3rd_person_omniscient",
    "prelude_enabled": true,
    "calendar": {"kind":"custom","months":[{"name":"First Tide","days":30}],"seasons":[{"name":"Ebb","months":[1]}],"year_label":"Year","era":""},
    "story_clock": {"year":1,"month":1,"day":1,"minute_of_day":540,"tick":0},
    "fixed_rules": [],
    "current_checkpoint_id": "cp_0",
    "trait_definitions": {},
    "titles": [],
    "protagonist_id": "",
    "arc_roadmap": {
       "arc_1": {"title": "", "core_conflict": "", "target_goal": ""},
       "arc_2": {"title": "", "core_conflict": "", "target_goal": ""}
    }
  },
  "checkpoints": [
    {
      "checkpoint_id": "",
      "description": "",
      "playable_situation": "Present-tense situation and open choices only; no future result",
      "possible_developments": ["If the player chooses this path, a consequence may follow", "If the player delays or refuses, another path remains possible"],
      "entry_location": null,
      "required_conditions": [],
      "cards_unlocked": [],
      "boundary": {
        "locations": [],
        "allowed_characters": [],
        "time_window": ""
      },
      "realm_updates": {},
      "status_effects": [],
      "alternate_outcomes": [],
      "default_next_checkpoint_id": null
    }
  ]
}
"""


ARC_EXTENDER_PROMPT = """You are an Arc Extender agent for an interactive story engine.

Task: The player has just completed the current Arc. You must generate the checkpoints for the NEXT Arc.

Inputs provided in your prompt:
- story_thesis: The core narrative anchor of the story. Use this to prevent genre drift.
- arc_roadmap: The original macro-outline of the entire story.
- running_summary: What ACTUALLY happened in the previous Arc based on the player's choices.
- character_state: The current status of all characters.

MANDATORY RULES:
1. Return raw JSON only — no markdown, no code fences, no preamble or closing remarks.
2. The JSON must have exactly 1 top-level key: "checkpoints".
3. Generate 5-7 checkpoints for the NEXT Arc. The first checkpoint's ID should logically follow the last completed one (e.g., if previous ended at cp_1_end, start with cp_2_0).
4. IMPORTANT: Adapt the next Arc's plot to account for what happened in the "running_summary" (e.g., if a character died, don't include them; if an alliance was made, reflect it).
5. Write every checkpoint "description" in the same language the user used. If that language can't be determined, default to English.

EXACT JSON STRUCTURE TO RETURN:
{
  "checkpoints": [
    {
      "checkpoint_id": "",
      "description": "",
      "required_conditions": [],
      "cards_unlocked": [],
      "boundary": {
        "locations": [],
        "allowed_characters": [],
        "time_window": ""
      }
    }
  ]
}
"""


WORLD_BUILDER_CARDS_PROMPT = """You are a world-builder agent for an interactive story engine.

Task: Based on the provided world Skeleton (world_config and checkpoints), GENERATE the lore and character cards for the world.

MANDATORY RULES:
1. Return raw JSON only — no markdown, no code fences, no preamble or closing remarks.
2. The JSON must have exactly 1 top-level key: "cards".
3. Every card must have an unlock_checkpoint_id pointing to a real checkpoint_id from the provided Skeleton.
4. ONLY cards whose unlock_checkpoint_id == "cp_0" may have status = "unlocked". Every other card MUST be "locked".
5. Write "name" and "content" for every card in the same language as the world's skeleton (world_config.display_name, genre, tone in the provided payload). If that language can't be determined, default to English.

EXACT JSON STRUCTURE TO RETURN:
{
  "cards": [
    {
      "id": "",
      "type": "char | lore",
      "name": "",
      "content": "",
      "unlock_checkpoint_id": "",
      "status": "locked | unlocked"
    }
  ]
}
"""


WORLD_BUILDER_CHARACTERS_PROMPT = """You are a world-builder agent for an interactive story engine.

Task: Based on the provided world Skeleton and Cards, GENERATE the initial character states.

MANDATORY RULES:
1. Return raw JSON only — no markdown, no code fences, no preamble or closing remarks.
2. The JSON must have exactly 1 top-level key: "characters".
3. Every character in "characters" must start power_stat.realm at the lowest tier of the power_system (unless the user explicitly asked for that).
4. Keys in "characters" must match the character IDs used in the Cards and Checkpoints.
5. Write "name" and any free-text field in the same language as the world's skeleton (world_config.display_name, genre, tone in the provided payload). If that language can't be determined, default to English.
6. For every character, also generate the 6 SillyTavern-style rich definition fields: appearance (visual description), personality (behavioral traits and psychology), backstory (origin and key life events), abilities_and_limits (capabilities and weaknesses), speech_style (tone, vocabulary, and 1-2 dialogue examples), and secrets (hidden information and agendas). These fields must be non-empty strings. Also generate `capabilities` as qualitative evidence records derived from identity, training, backstory, titles, and known skills. Each record has capability_id, statement, proficiency, sources, limits, and tags. Do not convert them into universal levels or percentages.

EXACT JSON STRUCTURE TO RETURN:
{
  "characters": {
    "character_id": {
      "name": "",
      "location": "",
      "affinity": {},
      "power_stat": {"realm": "", "exp": 0, "sub_stats": {}, "known_skills": []},
      "knowledge_flags": [],
      "inventory": [],
      "karma": 0,
      "alive": true,
      "relationships": {"other_character_id": "short string description of the relationship"},
      "age": "",
      "traits": {},
      "status_effects": [],
      "appearance": "",
      "personality": "",
      "backstory": "",
      "abilities_and_limits": "",
      "capabilities": [{"capability_id": "example", "statement": "What they can demonstrably do", "proficiency": "trained", "sources": ["backstory"], "limits": [], "tags": []}],
      "speech_style": "",
      "secrets": ""
    }
  ]
}
"""


LOCATION_MAP_GENERATOR_PROMPT = """You are a map-generation agent for an interactive story engine.

Task: Based on the world configuration, checkpoints, and characters provided, generate a spatial location map.

The location map represents the physical geography of the story world as a 2D coordinate system (0-100 on both X and Y axes).

RULES:
1. Return raw JSON only — no markdown, no code fences, no preamble.
2. The JSON must be an object with a single key "locations" containing an array of location nodes.
3. Each location node must have these fields:
   - "id": A unique string ID (e.g. "loc_village", "loc_forest", "loc_castle")
   - "name": Display name of the location (e.g. "Whispering Village", "Shadow Forest")
   - "description": Brief 1-sentence description
   - "x": X coordinate (0.0 to 100.0) — left to right
   - "y": Y coordinate (0.0 to 100.0) — bottom to top
   - "zone": The zone/region this location belongs to (e.g. "Northern Plains", "Undercity")
   - "terrain": One of unknown, coast, water, plain, forest, desert, mountain, wetland, urban
   - "elevation": Relative height band -2 (deep basin) to 2 (high summit), or null when unstated. 0 means explicitly level ground, NOT unknown.
   - "layer": One of unknown, surface, underground, sky
   - "unlock_realm": The minimum realm required to enter this location, or null if no realm restriction
   - "unlock_exp": The minimum EXP required to enter this location (0 if no restriction)
   - "unlock_checkpoint_id": The checkpoint ID that unlocks this location, or null if available from start
   - "is_starting_location": true if this is where the protagonist begins, false otherwise
   - "connected_to": Array of location IDs, or edge objects such as {"to": "loc_forest", "travel_time_minutes": 90, "danger": 0.25, "tags": ["forest_path"]}. Prefer edge objects when travel time is known.
   - "tags": Array of tag strings (e.g. ["safe", "urban", "shop"] or ["dangerous", "wilderness", "combat"])

4. IMPORTANT — Use zone-prefixed naming consistent with the checkpoint boundary.locations. For example, if a checkpoint has boundary.locations containing "Valdris Estate", create location nodes like "Valdris Estate - Manor", "Valdris Estate - Garden", etc.

5. UNLOCK LOGIC:
   - The starting location(s) should have is_starting_location=true, unlock_exp=0, unlock_realm=null, unlock_checkpoint_id=null
   - Locations near the story's beginning (cp_0 area) should be easy to access (low or no requirements)
   - Locations tied to later checkpoints should have higher unlock_exp or unlock_realm requirements matching the expected character progression
   - Use unlock_checkpoint_id for story-gated locations that require reaching a specific checkpoint

6. COORDINATES (0-100):
   - Place locations at meaningful positions relative to each other
   - Connected locations should be closer together than unconnected ones
   - Leave some empty space for exploration / fog of war feel

7. TERRAIN AND DEPTH (compact, factual metadata; no extra prose):
   - Fill terrain/elevation/layer only when the supplied world or checkpoint text supports them. Otherwise use "unknown" or null. Do not turn genre expectations into geography: a cultivation world does not automatically contain mountains, floating islands, or caves.
   - Elevation is relative within this map, not metres or a combat statistic. Keep it consistent between nearby connected locations. An underground room uses layer="underground"; do not also assign a negative elevation unless the source establishes a deep basin.
   - Preserve named continents and large zones in "zone"; coordinates place the story's known sites, not every settlement on a continent. Do not fabricate coastlines, roads, heights, or hidden landmarks merely to make the map look complete.
   - These fields are generated once with the location map. They are visual hints only and never change route connectivity or travel times.

8. Generate 5-15 location nodes depending on the world's scope.

VALID LOCATION TAGS EXAMPLES:
safe, dangerous, urban, wilderness, dungeon, shop, temple, palace, forest, mountain,
water, underground, magical, ruined, restricted, settlement, road, landmark

EXAMPLE output format:
{
  "locations": [
    {
      "id": "loc_start_village",
      "name": "Whispering Village",
      "description": "A quiet village at the edge of the known world",
      "x": 20,
      "y": 30,
      "zone": "Frontier Lands",
      "terrain": "unknown",
      "elevation": null,
      "layer": "unknown",
      "unlock_realm": null,
      "unlock_exp": 0,
      "unlock_checkpoint_id": null,
      "is_starting_location": true,
      "connected_to": ["loc_old_forest", "loc_north_road"],
      "tags": ["safe", "settlement"]
    }
  ]
}
"""
