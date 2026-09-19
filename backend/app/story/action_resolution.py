"""Context-aware action resolution (D03).

The engine confirms what the character can actually attempt before the narrator
writes it: capability, tools, skills, access, environment and opposition. The
result is a committed outcome the writer must not change. Only genuinely
uncertain, opposed actions use probability, and that probability is seeded and
logged so it can be reproduced — an LLM's invented number is never treated as an
objective measurement.

Worlds without ``action_rules`` keep the old free-narration behaviour through an
adapter (an unclassified action resolves to plain success with no checks).
"""
import hashlib
import random
from typing import Any, Dict, List, Optional

ACTION_RESULTS = ("impossible", "conditional", "partial", "success", "failure")


def _zone_match(location: str, allowed: str) -> bool:
    location = (location or "").strip().lower()
    allowed = (allowed or "").strip().lower()
    if not allowed:
        return False
    return location == allowed or location.startswith(allowed + " - ")


def _access_ok(location: str, checkpoint: dict) -> bool:
    allowed = (checkpoint or {}).get("boundary", {}).get("locations", [])
    if not allowed:
        return True
    return any(_zone_match(location, item) for item in allowed)


def _inventory(character: dict) -> set:
    from app.story.inventory import item_key
    items = character.get("inventory", [])
    return {item_key(item) for item in items if item_key(item)}


def _skills(character: dict) -> set:
    power_stat = character.get("power_stat", {}) if isinstance(character.get("power_stat"), dict) else {}
    skills = power_stat.get("known_skills", [])
    return {str(skill).strip().lower() for skill in skills if isinstance(skill, str)}


def _seed_for(world_name: str, turn_index: int, intent: str, provided: Optional[int]) -> Optional[int]:
    if provided is not None:
        return int(provided)
    if turn_index is None:
        return None
    digest = hashlib.sha256(f"{world_name}|{turn_index}|{intent}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _base_result(action_id: str, intent: str, checks: List[dict], result: str,
                 reason: str, *, consequences: List[Any] = None,
                 alternatives: List[str] = None, seed: Optional[int] = None,
                 probability: Optional[float] = None) -> dict:
    return {
        "action_id": action_id,
        "intent": intent,
        "checks": checks,
        "result": result,
        "reason": reason,
        "consequences": consequences or [],
        "alternatives": alternatives or [],
        "continuation": "",
        "seed": seed,
        "probability": probability,
    }


def _match_rule(intent: str, rules: list) -> Optional[dict]:
    text = (intent or "").lower()
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        keywords = rule.get("keywords", [])
        if keywords and any(str(k).lower() in text for k in keywords):
            return rule
    return None


def resolve_action(
    intent: str,
    character_state: Dict[str, dict],
    protagonist_id: str,
    world_config: dict,
    checkpoint: dict = None,
    location_map: dict = None,
    *,
    world_name: str = "",
    turn_index: int = None,
    seed: Optional[int] = None,
    action_id: str = "act_1",
) -> dict:
    """Resolve one player intent into a committed outcome."""
    protagonist = character_state.get(protagonist_id, {}) if isinstance(character_state, dict) else {}
    if not isinstance(protagonist, dict):
        protagonist = {}

    rules = world_config.get("action_rules", []) if isinstance(world_config, dict) else []
    if not isinstance(rules, list):
        rules = []
    rule = _match_rule(intent, rules)
    if not rule:
        # Adapter: no rule -> old free narration, no deterministic veto.
        return _base_result(action_id, intent, [], "success",
                            "No declared constraint: the narrator resolves it in context.")

    checks = []
    missing_tools = [
        tool for tool in rule.get("required_tools", [])
        if str(tool).strip().lower() not in _inventory(protagonist)
    ]
    checks.append({"name": "tools", "ok": not missing_tools,
                   "detail": f"missing: {missing_tools}" if missing_tools else "ok"})

    missing_skills = [
        skill for skill in rule.get("required_skills", [])
        if str(skill).strip().lower() not in _skills(protagonist)
    ]
    checks.append({"name": "skills", "ok": not missing_skills,
                   "detail": f"missing: {missing_skills}" if missing_skills else "ok"})

    from app.story.capabilities import find_capability
    required_capabilities = rule.get("required_capabilities", []) or []
    capability_matches = []
    missing_capabilities = []
    for required in required_capabilities:
        match = find_capability(protagonist, required)
        if match:
            capability_matches.append({"required": required, "evidence": match})
        else:
            missing_capabilities.append(required)
    checks.append({
        "name": "capability_evidence", "ok": not missing_capabilities,
        "detail": (f"missing: {missing_capabilities}" if missing_capabilities else "ok"),
        "evidence": capability_matches,
    })

    location = protagonist.get("location", "")
    access_ok = _access_ok(location, checkpoint)
    checks.append({"name": "access", "ok": access_ok,
                   "detail": location if access_ok else f"cannot act from '{location}'"})

    required_tags = [str(t).strip().lower() for t in rule.get("required_location_tags", [])]
    location_tags = []
    if isinstance(location_map, dict):
        for loc in location_map.get("locations", []) or []:
            if isinstance(loc, dict) and _zone_match(location, loc.get("name", "")):
                location_tags = [str(t).strip().lower() for t in loc.get("tags", [])]
                break
    missing_tags = [tag for tag in required_tags if tag not in location_tags]
    checks.append({"name": "environment", "ok": not missing_tags,
                   "detail": f"missing tags: {missing_tags}" if missing_tags else "ok"})

    # Capability only matters when the rule asks for it, so everyday worlds need
    # no realm/EXP at all.
    capability_ok = True
    capability_detail = "no power requirement"
    requirement = rule.get("requires_power") or {}
    if requirement:
        power_stat = protagonist.get("power_stat", {}) if isinstance(protagonist.get("power_stat"), dict) else {}
        realm = str(power_stat.get("realm", ""))
        min_realm = requirement.get("min_realm")
        if min_realm and realm != min_realm:
            capability_ok = False
            capability_detail = f"needs realm {min_realm} (has '{realm}')"
        min_exp = requirement.get("min_exp")
        if capability_ok and min_exp is not None:
            exp = power_stat.get("exp", 0)
            if not isinstance(exp, (int, float)) or exp < min_exp:
                capability_ok = False
                capability_detail = f"needs exp >= {min_exp}"
    checks.append({"name": "capability", "ok": capability_ok, "detail": capability_detail})

    hard_fail = missing_tools or missing_skills or missing_capabilities or not access_ok or missing_tags or not capability_ok
    if hard_fail:
        alternatives = list(rule.get("alternatives", []))
        result = "conditional" if alternatives else "impossible"
        reason_parts = []
        if missing_tools:
            reason_parts.append(f"missing tools: {missing_tools}")
        if missing_skills:
            reason_parts.append(f"missing skills: {missing_skills}")
        if missing_capabilities:
            reason_parts.append(f"missing capability evidence: {missing_capabilities}")
        if not access_ok:
            reason_parts.append(f"cannot act from '{location}'")
        if missing_tags:
            reason_parts.append(f"wrong place: missing {missing_tags}")
        if not capability_ok:
            reason_parts.append(capability_detail)
        out = _base_result(action_id, intent, checks, result,
                           "; ".join(reason_parts) or "constraints not met",
                           consequences=rule.get("consequences", []),
                           alternatives=alternatives)
        out["continuation"] = rule.get("continuation", "The obstacle opens another approach.")
        return out

    opposition = rule.get("opposition")
    if opposition:
        probability = float(rule.get("success_probability", 0.5))
        probability = max(0.0, min(1.0, probability))
        resolved_seed = _seed_for(world_name, turn_index, intent, seed)
        roll = random.Random(resolved_seed).random()
        if roll < probability * 0.5:
            result = "partial"
        elif roll < probability:
            result = "success"
        else:
            result = "failure"
        out = _base_result(
            action_id, intent, checks, result,
            f"opposed action: roll={roll:.4f} vs p={probability:.2f}",
            consequences=rule.get("consequences", []),
            alternatives=list(rule.get("alternatives", [])),
            seed=resolved_seed, probability=probability,
        )
        if result == "failure":
            out["continuation"] = rule.get(
                "continuation", "The failure creates a new problem to deal with next.")
            if not out["alternatives"]:
                out["alternatives"] = ["try a different approach", "look for another way in"]
        elif result == "partial":
            out["continuation"] = rule.get("continuation", "The partial result leaves a loose end.")
        return out

    return _base_result(action_id, intent, checks, "success",
                        rule.get("reason", "All declared constraints are met."),
                        consequences=rule.get("consequences", []))
