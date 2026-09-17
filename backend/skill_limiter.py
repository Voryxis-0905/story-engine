"""
backend/skill_limiter.py
Code-level boundary check module for skill usage and learning.
Prevents characters (specifically the protagonist) from executing or acquiring skills
that are not in their known_skills list without proper unlock/learning events.
"""
from typing import Dict, List, Any, Optional

def extract_known_skills(character_state: Dict[str, Any], protagonist_id: Optional[str] = None) -> List[str]:
    """Extract list of known skills for the protagonist or all characters."""
    chars = character_state.get("characters", character_state) if isinstance(character_state, dict) else {}
    known_skills = []

    if protagonist_id and protagonist_id in chars:
        protagonist = chars[protagonist_id]
        power_stat = protagonist.get("power_stat", {}) if isinstance(protagonist, dict) else {}
        known_skills = power_stat.get("known_skills", [])
    else:
        for c in chars.values():
            if isinstance(c, dict):
                pstat = c.get("power_stat", {})
                known_skills.extend(pstat.get("known_skills", []))
                
    return [s for s in known_skills if isinstance(s, str)]

def check_skill_limiter(
    chapter_text: str,
    character_state: Dict[str, Any],
    protagonist_id: Optional[str] = None,
    skill_cards: Optional[List[Dict[str, Any]]] = None,
    user_input: Optional[str] = None,
    state_changes: Optional[Dict[str, Any]] = None,
    skills_used: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Pure Python boundary check for skills on LLM generated output (and user intent).
    
    Inspects:
    1. Direct skills_used field if provided by Narrator response.
    2. Chapter text execution patterns by protagonist.
    3. User input intent (only if protagonist is explicitly commanded to execute/cast the skill).
    
    Returns structured boundary violation object:
    {
        "violated": bool,
        "boundary_violated": bool,
        "unlearned_skill": str or None,
        "reason": str
    }
    """
    known_skills = extract_known_skills(character_state, protagonist_id)
    known_skills_set = set(s.lower().strip() for s in known_skills)
    
    def is_skill_learned(skill_id: str, skill_name: str) -> bool:
        if skill_id and skill_id.lower().strip() in known_skills_set:
            return True
        if skill_name and skill_name.lower().strip() in known_skills_set:
            return True
        return False

    # 1. Check explicit skills_used list if returned by LLM / pipeline
    if skills_used and isinstance(skills_used, list):
        for skill in skills_used:
            if isinstance(skill, str) and skill.strip():
                if not is_skill_learned(skill, skill):
                    return {
                        "violated": True,
                        "boundary_violated": True,
                        "unlearned_skill": skill.strip(),
                        "reason": f"Protagonist attempted to execute unlearned skill '{skill.strip()}'"
                    }

    # Gather available skill cards and keywords
    skill_map = []
    if skill_cards:
        for card in skill_cards:
            if not isinstance(card, dict):
                continue
            card_type = card.get("type", "")
            if card_type and card_type not in ("skill", "skill_card") and "skills" not in card:
                continue
            
            s_name = card.get("name", card.get("id", ""))
            s_id = card.get("id", "")
            keywords = card.get("keywords", [])
            if isinstance(keywords, str):
                keywords = [keywords]
            
            terms = [t for t in [s_name, s_id] + list(keywords) if t and len(t) > 1]
            if s_name or s_id:
                skill_map.append({
                    "id": s_id,
                    "name": s_name,
                    "terms": terms
                })

    # 2. Check chapter_text for protagonist execution of unlearned skills
    if chapter_text and chapter_text.strip() and skill_map:
        text_lower = chapter_text.lower()
        for skill_info in skill_map:
            s_id = skill_info["id"]
            s_name = skill_info["name"]
            if is_skill_learned(s_id, s_name):
                continue  # Skill is learned, OK!
            
            # Check if any skill term appears in chapter_text
            for term in skill_info["terms"]:
                term_lower = term.lower()
                if term_lower in text_lower:
                    execution_verbs = ["thi triển", "suất tiên", "vung", "bật", "dùng", "sử dụng", "gồng", "chiêu", "tùng", "cast", "use", "execute", "invoke", "unleash", "activate", "wield", "shoot", "channel"]
                    
                    idx = text_lower.find(term_lower)
                    window = text_lower[max(0, idx - 60):min(len(text_lower), idx + 60)]
                    
                    has_execution = any(verb in window for verb in execution_verbs)
                    
                    if has_execution:
                        return {
                            "violated": True,
                            "boundary_violated": True,
                            "unlearned_skill": s_name or s_id,
                            "reason": f"Protagonist executed unlearned skill '{s_name or s_id}' in chapter"
                        }

    # 3. Refined user_input pre-check: Only trigger if user explicitly commands protagonist to cast/use unlearned skill
    if user_input and user_input.strip() and skill_map:
        user_lower = user_input.lower()
        
        cast_triggers = ["thi triển", "dùng ", "sử dụng ", "tung ", "gồng ", "bắn ", "cast ", "use ", "invoke ", "unleash ", "activate ", "shoot "]
        passive_triggers = ["hỏi", "là gì", "về", "tìm hiểu", "nghe nói", "thấy", "nhìn", "ai", "địch", "kẻ địch", "ask", "what is", "about", "investigate", "hear", "see", "look", "who", "enemy"]

        for skill_info in skill_map:
            s_id = skill_info["id"]
            s_name = skill_info["name"]
            if is_skill_learned(s_id, s_name):
                continue
            
            for term in skill_info["terms"]:
                term_lower = term.lower()
                if term_lower in user_lower:
                    is_query = any(p in user_lower for p in passive_triggers)
                    is_active_cast = any(c in user_lower for c in cast_triggers)
                    
                    if is_active_cast and not is_query:
                        return {
                            "violated": True,
                            "boundary_violated": True,
                            "unlearned_skill": s_name or s_id,
                            "reason": f"User commanded protagonist to execute unlearned skill '{s_name or s_id}'"
                        }

    return {
        "violated": False,
        "boundary_violated": False,
        "unlearned_skill": None,
        "reason": ""
    }
