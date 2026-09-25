"""The playable slice of a checkpoint, separated from its creator outline."""


def playable_checkpoint_description(checkpoint: dict) -> str:
    """Prefer the present-tense situation when a world supplies one.

    Older worlds only have ``description``. Keep their runtime context exactly
    as it was; never try to infer a new situation from a plot synopsis.
    """
    situation = checkpoint.get("playable_situation")
    if isinstance(situation, str) and situation.strip():
        return situation.strip()
    return checkpoint.get("description", "")
