"""Synthetic inputs for legacy progression tests; never reads a player's world."""
import json
from pathlib import Path


def write_progression_fixture(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)

    def condition(field, op, value):
        return {"field": "kaelen_vane." + field, "op": op, "value": value}

    def checkpoint(identifier, **extra):
        return dict(checkpoint_id=identifier, description="Regression fixture",
                    required_conditions=[], cards_unlocked=[], realm_updates={},
                    boundary={"locations": [], "allowed_characters": [], "time_window": ""},
                    **extra)

    beats = [{"beat_id": "sb_arrive", "required_conditions": []}]
    for beat, field, flag in [
        ("sb_examine_corpse", "knowledge_flags", "da_kham_nghiem_thi_the"),
        ("sb_interview_witnesses", "knowledge_flags", "da_phong_van_nhan_chung"),
        ("sb_retrieve_chip", "knowledge_flags", "da_thu_hoi_chip_linh_hon"),
        ("sb_find_decryptor", "inventory", "bo_giai_ma_linh_hon"),
        ("sb_play_hologram", "knowledge_flags", "da_xem_doan_ghi_hinh"),
    ]:
        beats.append({"beat_id": beat, "required_conditions": [condition(field, "contains", flag)]})

    def outcome(target, conditions, flag, stats=None, **payload):
        return {"to_checkpoint_id": target, "conditions": conditions, "apply": {
            "knowledge_flags": [flag],
            "stat_deltas": {"kaelen_vane.power_stat.sub_stats." + k: v for k, v in (stats or {}).items()},
            **payload,
        }}

    combat = [
        outcome("cp_4", [condition("power_stat.sub_stats.perception", ">=", 4)],
                "phat_hien_phuc_kich", {"perception": 1, "necromancy": 1},
                inventory_add=["nhat_ky_linh_hon_cua_linh_occult"]),
        outcome("cp_4", [condition("power_stat.sub_stats.necromancy", ">=", 2)],
                "da_chien_dau_voi_linh_occult", {"necromancy": 1, "perception": -1},
                inventory_remove=["Bộ dụng cụ trích xuất linh hồn"]),
        outcome("cp_combat_fail", [], "that_bai_combat_occult", {"perception": -2, "necromancy": -1},
                inventory_remove=["Kính lúp", "Bộ dụng cụ trích xuất linh hồn"],
                appearance_append="VAI PHẢI QUẤN BĂNG VẾT THƯƠNG", abilities_append="ĐIỂM YẾU NGHIÊM TRỌNG"),
    ]
    social = [
        outcome("cp_6", [condition("power_stat.sub_stats.charisma", ">=", 3)],
                "lian_chen_da_hop_tac", {"charisma": 1},
                inventory_add=["ma_khoa_giai_ma_delta_gateway_tu_lian"],
                relationships={"lian_chen": "Đồng minh tin cậy – cô đã thú nhận và cung cấp mã giải mã Delta-Gateway"}),
        outcome("cp_social_fail", [], "lian_chen_tu_choi_hop_tac", {"perception": -1},
                appearance_append="KHUÔN MẶT CĂNG THẲNG",
                abilities_append="lòng tin với đồng đội đã bị tổn hại",
                relationships={"lian_chen": "Rạn nứt – cô từ chối hợp tác và giữ khoảng cách sau cuộc đối chất"}),
    ]
    cp1 = checkpoint("cp_1")
    cp1.update(required_conditions=[condition("knowledge_flags", "contains", "con_chip_da_on_dinh")],
               cards_unlocked=["machine_scanner"])
    files = {
        "canon_timeline.json": {"checkpoints": [checkpoint("cp_0", sub_beats=beats), cp1,
            checkpoint("cp_3b_combat", alternate_outcomes=combat), checkpoint("cp_4"),
            checkpoint("cp_5b_social", alternate_outcomes=social), checkpoint("cp_6"),
            checkpoint("cp_combat_fail"), checkpoint("cp_social_fail")]},
        "world_config.json": {"protagonist_id": "kaelen_vane", "current_checkpoint_id": "cp_0",
                              "completed_checkpoints": [], "sub_beats_progress": {}},
        "character_state.json": {"characters": {"kaelen_vane": {
            "name": "Fixture detective", "power_stat": {"sub_stats": {"perception": 4, "necromancy": 0, "charisma": 0}},
            "knowledge_flags": [], "inventory": ["Kính lúp", "Bộ dụng cụ trích xuất linh hồn"], "relationships": {},
        }}},
        "card_registry.json": {"cards": [{"id": "machine_scanner", "name": "Máy quét Soul-Tech", "type": "lore", "status": "locked"}]},
    }
    for name, value in files.items():
        (destination / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
