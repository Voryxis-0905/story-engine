"""Small, optional terrain vocabulary for text-generated maps.

These fields describe only what the world states. They never affect movement,
unlocking or coordinates; an unknown value is safer than invented geography.
"""

TERRAINS = frozenset({
    "unknown", "coast", "water", "plain", "forest", "desert",
    "mountain", "wetland", "urban",
})
LAYERS = frozenset({"unknown", "surface", "underground", "sky"})


def normalize_terrain_fields(location: dict) -> None:
    """Keep malformed LLM terrain output from becoming a false map claim."""
    terrain = location.get("terrain", "unknown")
    location["terrain"] = terrain if isinstance(terrain, str) and terrain in TERRAINS else "unknown"
    layer = location.get("layer", "unknown")
    location["layer"] = layer if isinstance(layer, str) and layer in LAYERS else "unknown"
    elevation = location.get("elevation")
    location["elevation"] = (
        elevation if type(elevation) is int and -2 <= elevation <= 2 else None
    )
