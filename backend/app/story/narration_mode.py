"""Narration mode: which planner/writer narrative guidance a turn is written with.

Two profiles exist:

* ``classic`` (the default) - the original planner/writer guidance. A request
  that does not name a mode runs here, so an older client, a script, or a plain
  ``curl`` call keeps exactly the behaviour it had before this feature existed.
* ``experimental`` - the same engine, the same JSON contracts, the same hard
  rules, but different *narrative guidance*: a turn is not required to carry
  friction or end on a cliffhanger, length follows the scene instead of a word
  target, and present NPCs are planned with their own separate motives.

Two deliberate properties:

1. The mode is carried by the generation request itself and is **never written
   to a world's files**. A saved turn must stay exactly what it was, and
   flipping the switch must not touch a world's state, so the choice cannot
   live in ``world_config.json``. The UI remembers the player's choice per world
   on its own side (localStorage) and only sends it along with new turns.

2. The mode changes *which prompt* is sent, never *how many* calls are made.
   Planner and writer each still run exactly once (plus their existing bounded
   retries, which keep using the same prompt as the first attempt).
"""
from app.prompts import EXPERIMENTAL_PLANNER_SYSTEM_PROMPT
from app.prompts import EXPERIMENTAL_WRITER_SYSTEM_PROMPT
from app.prompts import PLANNER_SYSTEM_PROMPT
from app.prompts import WRITER_SYSTEM_PROMPT

NARRATION_MODE_CLASSIC = "classic"
NARRATION_MODE_EXPERIMENTAL = "experimental"

NARRATION_MODES = (NARRATION_MODE_CLASSIC, NARRATION_MODE_EXPERIMENTAL)


def normalize_narration_mode(value) -> str:
    """Return the mode to run.

    Anything that is not a recognized experimental request - a missing field, a
    blank string, an unexpected type - resolves to ``classic``. The HTTP layer
    rejects unknown *values* explicitly (422) so a typo is never silently
    downgraded; this function is the last line of defence for internal callers
    and for requests that predate the field.
    """
    if not isinstance(value, str):
        return NARRATION_MODE_CLASSIC
    key = value.strip().lower()
    if key == NARRATION_MODE_EXPERIMENTAL:
        return NARRATION_MODE_EXPERIMENTAL
    return NARRATION_MODE_CLASSIC


def is_experimental(value) -> bool:
    return normalize_narration_mode(value) == NARRATION_MODE_EXPERIMENTAL


def select_planner_prompt(narration_mode=None) -> str:
    if is_experimental(narration_mode):
        return EXPERIMENTAL_PLANNER_SYSTEM_PROMPT
    return PLANNER_SYSTEM_PROMPT


def select_writer_prompt(narration_mode=None) -> str:
    if is_experimental(narration_mode):
        return EXPERIMENTAL_WRITER_SYSTEM_PROMPT
    return WRITER_SYSTEM_PROMPT
