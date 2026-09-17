"""Demo routes."""
from fastapi import APIRouter, HTTPException
import os

from app.storage import world_path_of, write_world_file, _validate_world_name
from app.engine import DEFAULT_STORY_CLOCK, make_card, make_checkpoint, make_character

try:
    from skill_limiter import check_skill_limiter
except ImportError:
    from backend.skill_limiter import check_skill_limiter

router = APIRouter()



@router.post("/worlds/{world_name}/seed-demo")
def seed_demo(world_name: str, overwrite: bool = False):
    _validate_world_name(world_name)
    world_path = world_path_of(world_name)
    if os.path.exists(world_path) and not overwrite:
        raise HTTPException(
            status_code=400,
            detail=f"World '{world_name}' already exists. Set overwrite=true to re-seed."
        )
    if not os.path.isdir(world_path):
        os.makedirs(world_path)

    world_config = {
        "display_name": "Nine Heavens Realm",
        "genre": "xianxia / cultivation",
        "power_system": "Realm: Qi Condensation -> Foundation Establishment -> Core Formation -> Nascent Soul -> Deity Transformation",
        "tone": "dark, scheming, strength-based",
        "fixed_rules": [
            "Major realm breakthrough only occurs at canon checkpoint, not spontaneously in sandbox",
            "Main characters (Gu Changge, Xue Li) cannot die outside the predefined script"
        ],
        "current_checkpoint_id": "cp_0",
        "completed_checkpoints": [],
        "branched_from": None,
        "lore_rag_max_tokens": None,
        "opening_mode": "ai_generate",
        "opening_text": "",
        "story_clock": dict(DEFAULT_STORY_CLOCK),
        "foreshadowing_tracker": []
    }

    cards = [
        make_card("char_gu_changge", "char", "Gu Changge",
                  "Peerless genius, deep scheming, has hidden motives, appears from the beginning of the story.",
                  unlock_checkpoint_id="cp_0", status="unlocked"),
        make_card("char_xueli", "char", "Xue Li (Shangguan Liqi)",
                  "Female lead, mysterious background, complex relationship with Gu Changge.",
                  unlock_checkpoint_id="cp_0", status="unlocked"),
        make_card("char_su_phu", "char", "Xue Li's Master",
                  "Guides Xue Li in the early stages, holds a secret regarding her origins.",
                  unlock_checkpoint_id="cp_1", status="locked"),
        make_card("lore_mon_phai", "lore", "Starting Sect",
                  "The sect where Xue Li cultivates in the early stages, internal rules, hierarchy.",
                  unlock_checkpoint_id="cp_0", status="unlocked"),
        make_card("lore_dai_mac", "lore", "Great Desert Forbidden Land",
                  "Dangerous area with a secret realm, only opens after character reaches Foundation Establishment.",
                  unlock_checkpoint_id="cp_2", status="locked"),
        make_card("char_ma_vuong", "char", "Demon King (major villain)",
                  "Late-stage villain, absolutely will not appear before the late checkpoint.",
                  unlock_checkpoint_id="cp_4", status="locked"),
    ]

    checkpoints = [
        make_checkpoint(
            "cp_0", "Story begins: Xue Li joins the sect, meets Gu Changge for the first time",
            required_conditions=[],
            cards_unlocked=["char_gu_changge", "char_xueli", "lore_mon_phai"],
            locations=["Starting Sect"],
            allowed_characters=["char_gu_changge", "char_xueli"],
            time_window="Entry stage"
        ),
        make_checkpoint(
            "cp_1", "Xue Li takes a master, discovers the first clue about her origins",
            required_conditions=[
                {"field": "char_xueli.power_stat.exp", "op": ">=", "value": 10}
            ],
            cards_unlocked=["char_su_phu"],
            locations=["Starting Sect", "Back mountain"],
            allowed_characters=["char_gu_changge", "char_xueli", "char_su_phu"],
            time_window="Entry stage -> tr\u01b0\u1edbc Foundation Establishment"
        ),
        make_checkpoint(
            "cp_2", "Xue Li \u0111\u1ed9t ph\u00e1 Foundation Establishment, m\u1edf kh\u00f3a Great Desert Forbidden Land",
            required_conditions=[
                {"field": "char_xueli.power_stat.exp", "op": ">=", "value": 30}
            ],
            cards_unlocked=["lore_dai_mac"],
            locations=["Starting Sect", "Great Desert Forbidden Land"],
            allowed_characters=["char_gu_changge", "char_xueli", "char_su_phu"],
            time_window="After breaking through Foundation Establishment",
            realm_updates={"char_xueli": "Foundation Establishment"}
        ),
        make_checkpoint(
            "cp_3", "First explicit conflict between Xue Li and Gu Changge",
            required_conditions=[
                {"field": "char_xueli.knowledge_flags", "op": "contains",
                 "value": "knows Gu Changge's secret"}
            ],
            cards_unlocked=[],
            locations=["Great Desert Forbidden Land"],
            allowed_characters=["char_gu_changge", "char_xueli"],
            time_window="Trong Great Desert Forbidden Land",
            realm_updates={"char_xueli": "Core Formation"}
        ),
        make_checkpoint(
            "cp_4", "Demon King appears for the first time (late stage)",
            required_conditions=[
                {"field": "char_xueli.power_stat.realm", "op": "in",
                 "value": ["Core Formation", "Nascent Soul"]}
            ],
            cards_unlocked=["char_ma_vuong"],
            locations=["Great Desert Forbidden Land", "Deep forbidden area"],
            allowed_characters=["char_gu_changge", "char_xueli", "char_ma_vuong"],
            time_window="Late stage of the story"
        ),
    ]

    characters = {
        "char_gu_changge": make_character(
            name="Gu Changge",
            location="Starting Sect",
            affinity={"char_xueli": 0},
            realm="Foundation Establishment",
            exp=0,
            sub_stats={"scheming": 3},
            knowledge_flags=["knows Xue Li has a mysterious background"],
            alive=True,
            appearance="Tall, with sharp features and an ever-present subtle smile. Wears flowing white robes embroidered with silver clouds.",
            personality="Calculating and charismatic. Projects an image of elegance and detachment while scheming in the shadows.",
            backstory="A talented disciple from a fallen noble lineage, raised in the sect with a burning desire to reclaim his family's honor.",
            abilities_and_limits="Skilled in formation magic and swordplay. Weak to direct emotional appeals that bypass his logic.",
            speech_style="Polished and indirect. Often speaks in metaphors. 'One must learn to dance in the rain without getting wet.'",
            secrets="Knows the truth behind his family's downfall and secretly seeks revenge against the sect elder responsible."
        ),
        "char_xueli": make_character(
            name="Xue Li",
            location="Starting Sect",
            affinity={"char_gu_changge": 0},
            realm="Qi Condensation",
            exp=0,
            sub_stats={"combat experience": 0},
            knowledge_flags=[],
            alive=True,
            appearance="Petite with long silver-white hair and striking crimson eyes. Wears a tattered grey cloak over simple robes.",
            personality="Timid and withdrawn, but fiercely curious about ancient artifacts and forbidden knowledge.",
            backstory="Found as an orphan near the sect gates, Xue Li has no memory of her parents. An ancient bloodline runs dormant within her.",
            abilities_and_limits="Possesses a natural affinity for ice magic that manifests under emotional duress. Physically frail.",
            speech_style="Quiet, hesitant. Often trails off mid-sentence. 'I... I don't think we should go there. It feels... wrong.'",
            secrets="Her bloodline is that of an ancient ice demon sealed away millennia ago. The seal weakens as she grows stronger."
        ),
    }

    write_world_file(world_path, "world_config.json", world_config)
    write_world_file(world_path, "card_registry.json", {"cards": cards})
    write_world_file(world_path, "canon_timeline.json", {"checkpoints": checkpoints})
    write_world_file(world_path, "character_state.json", {"characters": characters})
    write_world_file(world_path, "chapters.json", {"chapters": [], "running_summary": "", "memorable_beats": []})

    return {
        "message": "Seed demo done",
        "world_name": world_name,
        "checkpoints": len(checkpoints),
        "cards": len(cards),
        "characters": len(characters)
    }
