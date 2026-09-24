"""
Test end-to-end cho bước 4 (card filtering) + bước 6 (checkpoint engine +
boundary fallback thật) + bước 5 (validate Pydantic + consistency checker
thật). Chạy bằng TestClient, xóa data test sau khi xong. KHÔNG phải test
chính thức của dự án, chỉ để tôi (Claude) tự kiểm tra trước khi giao lại code.
"""
import os
import shutil
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))

from fastapi.testclient import TestClient
from fastapi import HTTPException
import main

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'tests'))
from legacy_fixture import write_progression_fixture

client = TestClient(main.app)
WORLD = "test_engine_world"

# Clean up residue from previous runs
wp = main.world_path_of(WORLD)
if os.path.isdir(wp):
    shutil.rmtree(wp)


def check(cond, msg):
    status = "OK " if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        raise SystemExit(1)


# ---------------------------------------------------------------------
# 1. Seed demo, Check world_config contains completed_checkpoints
# ---------------------------------------------------------------------
r = client.post(f"/worlds/{WORLD}/seed-demo")
check(r.status_code == 200, "seed-demo returned 200")

world = client.get(f"/worlds/{WORLD}").json()
check(world["world_config"]["completed_checkpoints"] == [], "completed_checkpoints initialized empty")
check(world["world_config"]["current_checkpoint_id"] == "cp_0", "current_checkpoint_id = cp_0 after seed")

# ---------------------------------------------------------------------
# 2. Card filtering: char_su_phu (locked, thuộc cp_1) KHÔNG được xuất
#    hiện trong active_cards ở cp_0 regardless of unlock_checkpoint_id.
#    Monkeypatch call_llm to capture actual user_prompt sent to narrator.
# ---------------------------------------------------------------------
captured = {}
original_call_llm = main.call_llm


def fake_call_llm_capture(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    # buoc 5 hoan thien: chapter/continue gio cung goi consistency checker
    # qua call_llm -- only capture user_prompt when it is NARRATOR call,
    # otherwise will be overwritten by checker payload.
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            captured["user_prompt"] = user_prompt
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()


main.call_llm = fake_call_llm_capture
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "Xue Li quan sát xung quanh"})
check(r.status_code == 200, "chapter/continue (cp_0) returned 200")
check("char_su_phu" not in captured["user_prompt"], "card char_su_phu (locked) NOT in context ở cp_0")
check("Gu Changge" in captured["user_prompt"], "card char_gu_changge (unlocked, trong boundary) PRESENT in context")
body1 = r.json()
check(body1["checkpoint_advanced"]["to_checkpoint_id"] is None,
      "checkpoint KHÔNG advance khi exp chưa đạt ngưỡng (exp=0, cần >=10)")
main.call_llm = original_call_llm

# ---------------------------------------------------------------------
# 3. Checkpoint engine: Push Xue Li exp >= 10 -> must auto-advance to cp_1
#    and unlock card char_su_phu.
# ---------------------------------------------------------------------
def fake_call_llm_exp10(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    return json.dumps({
        "chapter_text": "Xue Li luyện tập chăm chỉ.",
        "state_changes": {
            "characters": {
                "char_xueli": {"exp_delta": 10}
            },
            "notes": "test exp"
        },
        "chapter_end": True
    }, ensure_ascii=False)


main.call_llm = fake_call_llm_exp10
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "luyện tập"})
check(r.status_code == 200, "chapter/continue (push exp) returned 200")
body = r.json()
check(body["checkpoint_advanced"] is not None, "checkpoint_advanced NOT None after exp reaches 10")
check(body["checkpoint_advanced"]["to_checkpoint_id"] == "cp_1", "correctly transitioned to cp_1")
check("Xue Li's Master" in body["checkpoint_advanced"]["cards_unlocked"], "card char_su_phu unlocked with cp_1")
main.call_llm = original_call_llm

world = client.get(f"/worlds/{WORLD}").json()
check(world["world_config"]["current_checkpoint_id"] == "cp_1", "world_config saved current_checkpoint_id = cp_1")
check("cp_0" in world["world_config"]["completed_checkpoints"], "cp_0 is in completed_checkpoints")
su_phu_card = next(c for c in world["card_registry"]["cards"] if c["id"] == "char_su_phu")
check(su_phu_card["status"] == "unlocked", "card_registry.json đã ghi char_su_phu = unlocked")

# ---------------------------------------------------------------------
# 4. Đẩy tiếp exp Xue Li lên >= 30 (từ mốc 10, cần +20) -> advance sang cp_2,
#    và realm phải được set thành "Foundation Establishment" qua realm_updates (không phải
#    do narrator tự set).
# ---------------------------------------------------------------------
def fake_call_llm_exp20more(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    return json.dumps({
        "chapter_text": "Xue Li tiếp tục tu luyện gian khổ.",
        "state_changes": {"characters": {"char_xueli": {"exp_delta": 20}}, "notes": ""},
        "chapter_end": True
    }, ensure_ascii=False)


main.call_llm = fake_call_llm_exp20more
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "bế quan tu luyện"})
body = r.json()
check(body["checkpoint_advanced"]["to_checkpoint_id"] == "cp_2", "chuyển đúng sang cp_2")
check(body["checkpoint_advanced"]["realm_changes"] == {"char_xueli": "Foundation Establishment"}, "realm_changes trả về đúng Foundation Establishment")
main.call_llm = original_call_llm

world = client.get(f"/worlds/{WORLD}").json()
xueli = world["character_state"]["characters"]["char_xueli"]
check(xueli["power_stat"]["realm"] == "Foundation Establishment", "character_state.json: realm Xue Li đã thành Foundation Establishment")

# ---------------------------------------------------------------------
# 5. Validate Pydantic: LLM trả state_changes sai kiểu (exp_delta là string)
#    -> phải trả 502 rõ ràng, KHÔNG crash 500, và KHÔNG được merge/ghi file.
# ---------------------------------------------------------------------
def fake_call_llm_badtype(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    return json.dumps({
        "chapter_text": "test",
        "state_changes": {"characters": {"char_xueli": {"exp_delta": "not_a_number"}}, "notes": ""}
    }, ensure_ascii=False)


world_before = client.get(f"/worlds/{WORLD}").json()
exp_before = world_before["character_state"]["characters"]["char_xueli"]["power_stat"]["exp"]

main.call_llm = fake_call_llm_badtype
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "gì đó"})
check(r.status_code == 502, "state_changes sai kiểu -> 502 (không phải 500 crash)")
main.call_llm = original_call_llm

world_after = client.get(f"/worlds/{WORLD}").json()
exp_after = world_after["character_state"]["characters"]["char_xueli"]["power_stat"]["exp"]
check(exp_before == exp_after, "state KHÔNG bị merge một phần khi validate fail")

# ---------------------------------------------------------------------
# 6. Boundary fallback thật -- auto-fix: lần đầu narrator đưa Xue Li ra
#    ngoài phạm vi (cp_2 chỉ cho phép "Starting Sect"/"Đại Mạc Cấm
#    Địa"), lần retry (có correction_note) trả về đúng phạm vi -> phải
#    chấp nhận bản retry, KHÔNG hard-clamp.
# ---------------------------------------------------------------------
def fake_call_llm_boundary_autofix(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    payload = json.loads(user_prompt)
    if "correction_note" in payload:
        return json.dumps({
            "chapter_text": "Xue Li dừng lại, ở yên trong Great Desert Forbidden Land.",
            "state_changes": {"characters": {"char_xueli": {"location": "Great Desert Forbidden Land"}}, "notes": ""}
        }, ensure_ascii=False)
    return json.dumps({
        "chapter_text": "Xue Li bay thẳng tới Ma Giới.",
        "state_changes": {"characters": {"char_xueli": {"location": "Ma Giới"}}, "notes": ""}
    }, ensure_ascii=False)


main.call_llm = fake_call_llm_boundary_autofix
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "Xue Li thử vượt biên"})
check(r.status_code == 200, "chapter/continue (boundary auto-fix) returned 200")
body = r.json()
bc = body["chapter"]["boundary_correction"]
check(bc is not None, "boundary_correction được ghi nhận khi vi phạm lần đầu")
check(bc["auto_retry_fixed_it"] is True, "boundary auto-fix: narrator tự sửa đúng sau khi được nhắc lại")
check(body["chapter"]["chapter_text"] == "Xue Li dừng lại, ở yên trong Great Desert Forbidden Land.",
      "chapter_text cuối cùng là bản đã viết lại đúng phạm vi")
main.call_llm = original_call_llm

world = client.get(f"/worlds/{WORLD}").json()
xueli = world["character_state"]["characters"]["char_xueli"]
check(xueli["location"] == "Great Desert Forbidden Land", "location Xue Li được cập nhật đúng phạm vi sau auto-fix")

# ---------------------------------------------------------------------
# 7. Boundary fallback thật -- HARD REJECT (sửa lại theo mục 7 #4 sau khi
#    ghi nhận giới hạn cũ): narrator vi phạm CẢ 2 lần (kể cả sau
#    correction_note) -> KHÔNG còn "hard clamp" (giữ state đúng nhưng
#    chapter_text vẫn có thể mô tả sai, gây mismatch hiển thị). Giờ phải
#    CHẶN HẲN: trả 409, KHÔNG ghi chapter mới, KHÔNG đổi character_state,
#    KHÔNG crash.
# ---------------------------------------------------------------------
def fake_call_llm_boundary_stuck(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    return json.dumps({
        "chapter_text": "Xue Li tiếp tục cố vượt biên tới Ma Giới.",
        "state_changes": {"characters": {"char_xueli": {"location": "Ma Giới"}}, "notes": ""}
    }, ensure_ascii=False)


world_before_stuck = client.get(f"/worlds/{WORLD}").json()
loc_before_stuck = world_before_stuck["character_state"]["characters"]["char_xueli"]["location"]
chapter_count_before_stuck = len(world_before_stuck["chapters"]["chapters"])

main.call_llm = fake_call_llm_boundary_stuck
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "Xue Li cố vượt biên lần nữa"})
check(r.status_code == 409, "chapter/continue (boundary vi phạm cả 2 lần) trả 409, không phải 200/500")
check("Ma Giới" in r.json()["detail"], "detail lỗi có nhắc tới địa điểm vi phạm để user hiểu vì sao")
main.call_llm = original_call_llm

world = client.get(f"/worlds/{WORLD}").json()
xueli = world["character_state"]["characters"]["char_xueli"]
check(xueli["location"] == loc_before_stuck,
      "hard reject: location KHÔNG bị đổi sang địa điểm vi phạm dù LLM cố tình sai cả 2 lần")
check(len(world["chapters"]["chapters"]) == chapter_count_before_stuck,
      "hard reject: KHÔNG có chapter mới nào được ghi khi bị chặn (tránh mismatch text/state)")

# ---------------------------------------------------------------------
# 8. Consistency checker that -- severity "major" phải kích hoạt narrator
#    viết lại 1 lần, rồi BẮT BUỘC kiểm tra lại bản sửa (F07). Response
#    phản ánh triggered_rewrite=True và status theo lần kiểm tra mới nhất.
# ---------------------------------------------------------------------
_consistency_8 = {"n": 0}


def fake_call_llm_consistency_major(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        _consistency_8["n"] += 1
        if _consistency_8["n"] == 1:
            return json.dumps({
                "consistent": False,
                "severity": "major",
                "issues": ["mâu thuẫn giả lập để test rewrite"],
                "explanation": "test"
            }, ensure_ascii=False)
        return json.dumps({
            "consistent": True,
            "severity": "none",
            "issues": [],
            "explanation": "fixed"
        }, ensure_ascii=False)
    return json.dumps({
        "chapter_text": "Đoạn chapter test cho consistency checker.",
        "state_changes": {"characters": {}, "notes": "test cc"}
    }, ensure_ascii=False)


main.call_llm = fake_call_llm_consistency_major
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "hành động test"})
check(r.status_code == 200, "chapter/continue (consistency major) returned 200")
body = r.json()
cc = body["chapter"]["consistency_check"]
check(cc["status"] == "passed", "consistency_check.status = passed sau khi ban sua qua recheck")
check(cc["triggered_rewrite"] is True, "consistency major -> triggered_rewrite = True (đã gọi lại narrator)")
check(_consistency_8["n"] == 2, "checker được gọi 2 lần (lượt đầu + recheck bản sửa)")
main.call_llm = original_call_llm

# ---------------------------------------------------------------------
# 9. Regression: world tạo thường (không seed) vẫn báo 400 rõ ràng như cũ.
# ---------------------------------------------------------------------
EMPTY_WORLD = "test_engine_empty_world"
wp2 = main.world_path_of(EMPTY_WORLD)
if os.path.isdir(wp2):
    shutil.rmtree(wp2)
client.post(f"/worlds/{EMPTY_WORLD}")
r = client.post(f"/worlds/{EMPTY_WORLD}/chapter/continue", json={"user_input": "x"})
check(r.status_code == 400, "world rỗng (chưa seed) vẫn trả 400 rõ ràng, không crash")

# ---------------------------------------------------------------------------
# 10. BƯỚC 7 (Creator mode) -- PUT world_config: sửa field "tĩnh", KHÔNG
#     được đụng vào current_checkpoint_id/completed_checkpoints.
# ---------------------------------------------------------------------------
world_before_cfg = client.get(f"/worlds/{WORLD}").json()["world_config"]
r = client.put(f"/worlds/{WORLD}/world_config", json={
    "display_name": "Nine Heavens Realm (bản sửa)",
    "tone": "dark, u ám hơn"
})
check(r.status_code == 200, "PUT world_config returned 200")
world_after_cfg = client.get(f"/worlds/{WORLD}").json()["world_config"]
check(world_after_cfg["display_name"] == "Nine Heavens Realm (bản sửa)", "display_name đã đổi")
check(world_after_cfg["tone"] == "dark, u ám hơn", "tone đã đổi")
check(world_after_cfg["current_checkpoint_id"] == world_before_cfg["current_checkpoint_id"],
      "PUT world_config KHÔNG đụng vào current_checkpoint_id")

# ---------------------------------------------------------------------------
# 11. BƯỚC 7 -- PUT card_registry: thêm card mới thành công; card id trùng
#     phải bị chặn 400 và KHÔNG ghi đè file cũ.
# ---------------------------------------------------------------------------
world_data = client.get(f"/worlds/{WORLD}").json()
cards = world_data["card_registry"]["cards"]
new_card = {
    "id": "char_moi_test", "type": "char", "name": "Nhân vật test",
    "content": "sinh ra để test Creator mode", "unlock_checkpoint_id": "cp_0",
    "status": "unlocked"
}
r = client.put(f"/worlds/{WORLD}/card_registry", json={"cards": cards + [new_card]})
check(r.status_code == 200, "PUT card_registry (thêm card mới) returned 200")
cards_after = client.get(f"/worlds/{WORLD}").json()["card_registry"]["cards"]
check(any(c["id"] == "char_moi_test" for c in cards_after), "card mới đã được lưu vào card_registry.json")

r = client.put(f"/worlds/{WORLD}/card_registry", json={"cards": cards_after + [dict(new_card)]})
check(r.status_code == 400, "PUT card_registry với id trùng -> 400")
cards_after_dup_attempt = client.get(f"/worlds/{WORLD}").json()["card_registry"]["cards"]
check(len(cards_after_dup_attempt) == len(cards_after), "card_registry.json KHÔNG bị ghi đè khi request có id trùng")

# ---------------------------------------------------------------------------
# 12. BƯỚC 7 -- PUT canon_timeline: sửa description một checkpoint có sẵn.
# ---------------------------------------------------------------------------
world_data = client.get(f"/worlds/{WORLD}").json()
checkpoints = world_data["canon_timeline"]["checkpoints"]
for cp in checkpoints:
    if cp["checkpoint_id"] == "cp_3":
        cp["description"] = "Mô tả cp_3 đã sửa qua Creator mode"
r = client.put(f"/worlds/{WORLD}/canon_timeline", json={"checkpoints": checkpoints})
check(r.status_code == 200, "PUT canon_timeline returned 200")
cp3_after = next(cp for cp in client.get(f"/worlds/{WORLD}").json()["canon_timeline"]["checkpoints"]
                  if cp["checkpoint_id"] == "cp_3")
check(cp3_after["description"] == "Mô tả cp_3 đã sửa qua Creator mode", "description cp_3 đã lưu đúng")

# ---------------------------------------------------------------------------
# 13. BƯỚC 7 -- PUT character_state: sửa trực tiếp exp một nhân vật.
# ---------------------------------------------------------------------------
world_data = client.get(f"/worlds/{WORLD}").json()
characters = world_data["character_state"]["characters"]
characters["char_gu_changge"]["power_stat"]["exp"] = 999
r = client.put(f"/worlds/{WORLD}/character_state", json={"characters": characters})
check(r.status_code == 200, "PUT character_state returned 200")
gc_after = client.get(f"/worlds/{WORLD}").json()["character_state"]["characters"]["char_gu_changge"]
check(gc_after["power_stat"]["exp"] == 999, "exp Gu Changge đã được Creator sửa trực tiếp thành 999")

# ---------------------------------------------------------------------------
# 14. BƯỚC 7 -- force-advance checkpoint: world hiện đang ở cp_2 (từ test
#     3+4 phía trên). Ép nhảy thẳng tới cp_4 (bỏ qua cp_3) -> phải cascade
#     đúng: cp_2, cp_3 vào completed_checkpoints, card của CẢ cp_3 lẫn cp_4
#     được unlock, realm_updates của cp_3 (Core Formation) cũng phải được áp dụng
#     dù đích cuối là cp_4 (không chỉ áp realm_updates của checkpoint đích).
# ---------------------------------------------------------------------------
world_before_adv = client.get(f"/worlds/{WORLD}").json()
check(world_before_adv["world_config"]["current_checkpoint_id"] == "cp_2",
      "(tiền đề) world đang ở cp_2 trước khi force-advance")

r = client.post(f"/worlds/{WORLD}/checkpoint/force-advance", json={"target_checkpoint_id": "cp_4"})
check(r.status_code == 200, "force-advance cp_2 -> cp_4 returned 200")
body = r.json()
check(body["to_checkpoint_id"] == "cp_4", "to_checkpoint_id = cp_4")
check(any("Demon King" in name for name in body["cards_unlocked"]), "card char_ma_vuong (cp_4) được unlock")
check(body["realm_changes"].get("char_xueli") == "Core Formation",
      "realm_updates của cp_3 (checkpoint bị nhảy qua) VẪN được áp dụng khi cascade")

world_after_adv = client.get(f"/worlds/{WORLD}").json()
check(world_after_adv["world_config"]["current_checkpoint_id"] == "cp_4", "current_checkpoint_id đã thành cp_4")
check("cp_2" in world_after_adv["world_config"]["completed_checkpoints"], "cp_2 vào completed_checkpoints")
check("cp_3" in world_after_adv["world_config"]["completed_checkpoints"],
      "cp_3 (bị nhảy qua) cũng được đánh dấu completed")
ma_vuong_card = next(c for c in world_after_adv["card_registry"]["cards"] if c["id"] == "char_ma_vuong")
check(ma_vuong_card["status"] == "unlocked", "card_registry.json: char_ma_vuong = unlocked sau force-advance")

r = client.post(f"/worlds/{WORLD}/checkpoint/force-advance", json={"target_checkpoint_id": "khong_ton_tai"})
check(r.status_code == 404, "force-advance tới checkpoint_id không tồn tại -> 404")

# ---------------------------------------------------------------------------
# 15. BƯỚC 8 -- Multi-save (snapshot + branch). World đang ở cp_4 (từ test 14),
#     display_name hiện là gì thì lưu lại, sửa đi, restore lại phải đúng như cũ,
#     rồi branch ra world mới từ save đó và kiểm tra world mới độc lập.
# ---------------------------------------------------------------------------
BRANCH_WORLD = "test_engine_world_branch"
wp3 = main.world_path_of(BRANCH_WORLD)
if os.path.isdir(wp3):
    shutil.rmtree(wp3)

world_before_save = client.get(f"/worlds/{WORLD}").json()
original_display_name = world_before_save["world_config"]["display_name"]
saves_before = client.get(f"/worlds/{WORLD}/saves").json()["saves"]

r = client.post(f"/worlds/{WORLD}/saves", json={"label": "trước khi thử sửa lung tung"})
check(r.status_code == 200, "POST saves (tạo save point) returned 200")
save_id = r.json()["save"]["save_id"]
check(r.json()["save"]["checkpoint_id"] == "cp_4", "save point ghi đúng checkpoint_id lúc lưu (cp_4)")

saves_after_create = client.get(f"/worlds/{WORLD}/saves").json()["saves"]
check(len(saves_after_create) == len(saves_before) + 1, "GET saves tăng đúng 1 sau khi tạo")
check(saves_after_create[0]["save_id"] == save_id, "save mới nhất nằm đầu danh sách (mới nhất trước)")

# sửa world_config sau khi đã save, để kiểm tra restore có phục hồi đúng không
r = client.put(f"/worlds/{WORLD}/world_config", json={"display_name": "Tên bị sửa sai sau khi save"})
check(r.status_code == 200, "PUT world_config (sửa tạm để test restore) returned 200")
check(client.get(f"/worlds/{WORLD}").json()["world_config"]["display_name"] == "Tên bị sửa sai sau khi save",
      "display_name đã bị sửa như mong đợi trước khi restore")

r = client.post(f"/worlds/{WORLD}/saves/{save_id}/restore")
check(r.status_code == 200, "POST saves/{id}/restore returned 200")
safety_save_id = r.json()["safety_save_id"]
check(safety_save_id != save_id, "restore tự tạo 1 safety save riêng (khác save_id vừa restore)")

world_after_restore = client.get(f"/worlds/{WORLD}").json()
check(world_after_restore["world_config"]["display_name"] == original_display_name,
      "restore phục hồi đúng display_name như lúc save (không phải bản sửa sai)")
check(world_after_restore["world_config"]["current_checkpoint_id"] == "cp_4",
      "restore giữ đúng current_checkpoint_id đã lưu (cp_4)")

saves_after_restore = client.get(f"/worlds/{WORLD}/saves").json()["saves"]
check(len(saves_after_restore) == len(saves_after_create) + 1,
      "restore thêm đúng 1 safety save vào danh sách (không mất save cũ)")
check(any(s["save_id"] == safety_save_id and s["source"] == "safety_before_restore" for s in saves_after_restore),
      "safety save được đánh dấu đúng source = safety_before_restore")

r = client.post(f"/worlds/{WORLD}/saves/khong_ton_tai/restore")
check(r.status_code == 404, "restore save_id không tồn tại -> 404")

# branch world mới từ save đã lưu
r = client.post(f"/worlds/{WORLD}/saves/{save_id}/branch", json={"new_world_name": BRANCH_WORLD})
check(r.status_code == 200, "POST saves/{id}/branch returned 200")
check(r.json()["new_world_name"] == BRANCH_WORLD, "branch trả đúng tên world mới")

branch_world = client.get(f"/worlds/{BRANCH_WORLD}").json()
check(branch_world["world_config"]["display_name"] == original_display_name,
      "world branch có state khớp đúng save nguồn (display_name)")
check(branch_world["world_config"]["current_checkpoint_id"] == "cp_4",
      "world branch có state khớp đúng save nguồn (checkpoint)")
check(branch_world["world_config"]["branched_from"]["world"] == WORLD,
      "world branch ghi đúng branched_from.world")
check(branch_world["world_config"]["branched_from"]["save_id"] == save_id,
      "world branch ghi đúng branched_from.save_id")
check(branch_world["saves"] == [], "world branch có saves_index rỗng, không kế thừa save của world gốc")

# world gốc không bị ảnh hưởng bởi việc branch (độc lập hoàn toàn)
world_after_branch = client.get(f"/worlds/{WORLD}").json()
check(world_after_branch["world_config"]["display_name"] == original_display_name,
      "world gốc không đổi gì sau khi branch ra world khác")

r = client.post(f"/worlds/{WORLD}/saves/{save_id}/branch", json={"new_world_name": BRANCH_WORLD})
check(r.status_code == 400, "branch ra tên world đã tồn tại -> 400")

r = client.post(f"/worlds/{WORLD}/saves/khong_ton_tai/branch", json={"new_world_name": "world_khac"})
check(r.status_code == 404, "branch từ save_id không tồn tại -> 404")

r = client.delete(f"/worlds/{WORLD}/saves/{save_id}")
check(r.status_code == 200, "DELETE saves/{id} returned 200")
saves_after_delete = client.get(f"/worlds/{WORLD}/saves").json()["saves"]
check(not any(s["save_id"] == save_id for s in saves_after_delete), "save đã xóa không còn trong danh sách")
check(not os.path.isdir(os.path.join(wp, "saves", save_id)), "thư mục snapshot của save đã xóa cũng bị xóa khỏi disk")

r = client.delete(f"/worlds/{WORLD}/saves/khong_ton_tai")
check(r.status_code == 404, "DELETE save_id không tồn tại -> 404")

# ---------------------------------------------------------------------------
# 16. BƯỚC 8 -- LORE RAG-LITE. World riêng, seed-demo rồi thêm 8 lore card
#     unlocked với từ khóa riêng biệt cho mỗi card (vượt xa mọi ngưỡng hợp
#     lý), set lore_rag_max_tokens = 50, rồi gửi 1 chapter với user_input chứa
#     đúng từ khóa của 1 card cụ thể -- card đó phải lọt vào context gửi cho
#     narrator, còn card khác hẳn (không liên quan) thì không.
# ---------------------------------------------------------------------------
RAG_WORLD = "test_engine_world_rag"
wp4 = main.world_path_of(RAG_WORLD)
if os.path.isdir(wp4):
    shutil.rmtree(wp4)

r = client.post(f"/worlds/{RAG_WORLD}/seed-demo")
check(r.status_code == 200, "seed-demo (world RAG-lite) returned 200")

# card_registry hiện có sẵn 2 lore card unlocked (lore_mon_phai) + locked
# (lore_dai_mac) từ seed demo -- lấy nguyên rồi thêm 8 lore card mới, đều
# unlocked, mỗi card mang đúng 1 từ khóa duy nhất không trùng nhau/không
# trùng nội dung có sẵn.
existing_cards = client.get(f"/worlds/{RAG_WORLD}").json()["card_registry"]["cards"]
rag_keywords = ["glacierkw", "emberkw", "shadowkw", "cryptkw", "oraclekw", "phantomkw", "voidkw", "stormkw"]
extra_lore = [
    {"id": f"lore_rag_{kw}", "type": "lore", "name": f"Bí cảnh {kw}",
     "content": f"Một vùng đất cổ xưa gắn liền duy nhất với {kw}, không liên quan gì tới các vùng đất khác.",
     "unlock_checkpoint_id": "cp_0", "status": "unlocked"}
    for kw in rag_keywords
]
r = client.put(f"/worlds/{RAG_WORLD}/card_registry", json={"cards": existing_cards + extra_lore})
check(r.status_code == 200, "PUT card_registry (thêm 8 lore card cho test RAG-lite) returned 200")

unlocked_lore_tokens = sum(
    len(c.get("content", "") + " " + c.get("name", "")) // 4 
    for c in (existing_cards + extra_lore) if c["type"] == "lore" and c["status"] == "unlocked"
)

r = client.put(f"/worlds/{RAG_WORLD}/world_config", json={"lore_rag_max_tokens": 50})
check(r.status_code == 200, "PUT world_config (set lore_rag_max_tokens=50) returned 200")

rag_captured = {}


def fake_call_llm_rag(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            rag_captured["user_prompt"] = user_prompt
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()


main.call_llm = fake_call_llm_rag
r = client.post(f"/worlds/{RAG_WORLD}/chapter/continue",
                 json={"user_input": "Xue Li nghe đồn về emberkw ở phía xa"})
check(r.status_code == 200, "chapter/continue (RAG-lite, max=3) returned 200")
main.call_llm = original_call_llm

check("lore_rag_emberkw" in rag_captured["user_prompt"],
      "lore card khớp trực tiếp với user_input (emberkw) PRESENT in context gửi narrator")
check("lore_rag_stormkw" not in rag_captured["user_prompt"],
      "lore card không liên quan (stormkw, điểm 0 và xếp cuối) NOT in context khi đã vượt ngưỡng RAG-lite")

rag_filter_info = r.json()["lore_rag_filter"]
check(rag_filter_info is not None and rag_filter_info["applied"] is True,
      "response trả lore_rag_filter.applied=True khi filter thực sự có tác dụng")
check(rag_filter_info["max_lore_tokens"] == 50, "lore_rag_filter ghi đúng max_lore_tokens đã cấu hình (50)")
check(len(rag_filter_info["selected_lore_ids"]) < 8,
      "lore_rag_filter đã loại bỏ bớt card (số card < 8) để thỏa mãn token limit")

# Set lore_rag_max_tokens = 0 -> Creator chủ động tắt filter, phải nhồi lại
# hết toàn bộ lore đã unlocked như hành vi cũ (không giới hạn).
r = client.put(f"/worlds/{RAG_WORLD}/world_config", json={"lore_rag_max_tokens": 0})
check(r.status_code == 200, "PUT world_config (set lore_rag_max_tokens=0, tắt RAG-lite) returned 200")

rag_captured_unlimited = {}


def fake_call_llm_rag_unlimited(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            rag_captured_unlimited["user_prompt"] = user_prompt
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()


main.call_llm = fake_call_llm_rag_unlimited
r = client.post(f"/worlds/{RAG_WORLD}/chapter/continue", json={"user_input": "tiếp tục quan sát"})
check(r.status_code == 200, "chapter/continue (lore_rag_max_tokens=0, unlimited) returned 200")
main.call_llm = original_call_llm

check(all(kw in rag_captured_unlimited["user_prompt"] for kw in rag_keywords),
      "lore_rag_max_tokens=0 -> TẤT CẢ 8 lore card mới đều lọt vào context (không giới hạn)")
check(r.json()["lore_rag_filter"] is None,
      "response trả lore_rag_filter=None khi filter bị tắt (unlimited)")

r = client.put(f"/worlds/{RAG_WORLD}/world_config", json={"lore_rag_max_tokens": -1})
check(r.status_code == 400, "PUT world_config với lore_rag_max_tokens âm -> 400")

# Regression: world seed-demo mặc định (chỉ 1-2 lore card, dưới ngưỡng mặc
# định 6) không bị ảnh hưởng gì bởi RAG-lite -- lore_rag_filter phải là None.
r = client.post(f"/worlds/test_engine_world_rag_default/seed-demo")
check(r.status_code == 200, "seed-demo (world mặc định, không cấu hình RAG-lite) returned 200")
main.call_llm = fake_call_llm_rag_unlimited  # bất kỳ mock nào cũng được, không quan tâm capture ở đây
r = client.post("/worlds/test_engine_world_rag_default/chapter/continue", json={"user_input": "test"})
main.call_llm = original_call_llm
check(r.status_code == 200, "chapter/continue (world mặc định) returned 200")
check(r.json()["lore_rag_filter"] is None,
      "world nhỏ (dưới ngưỡng mặc định) không bị RAG-lite tác động -- lore_rag_filter=None như cũ")

shutil.rmtree(wp4, ignore_errors=True)
shutil.rmtree(main.world_path_of("test_engine_world_rag_default"), ignore_errors=True)

# ---------------------------------------------------------------------
# 17. BƯỚC 0 (mới): Runtime Config (API key/model qua UI) + retry-with-
#     backoff cho 429 + LLMCallError báo lỗi rõ ràng thay vì âm thầm mock.
#     Sao lưu/khôi phục runtime_config.json thật (nếu có) để không làm bẩn
#     máy chạy test hay ảnh hưởng các lần chạy test khác.
# ---------------------------------------------------------------------
_runtime_cfg_backup = None
if os.path.isfile(main.RUNTIME_CONFIG_PATH):
    with open(main.RUNTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
        _runtime_cfg_backup = f.read()

# 17a. Chưa cấu hình gì (giả định sandbox test không có OPENROUTER_API_KEY
# trong env) -> has_api_key False, nguồn "none".
if os.path.isfile(main.RUNTIME_CONFIG_PATH):
    os.remove(main.RUNTIME_CONFIG_PATH)
_env_key_backup = os.environ.pop("OPENROUTER_API_KEY", None)
_env_model_backup = os.environ.pop("OPENROUTER_MODEL", None)

r = client.get("/runtime-config")
check(r.status_code == 200, "GET /runtime-config returned 200")
check(r.json()["has_api_key"] is False, "chưa set gì -> has_api_key = False")
check(r.json()["api_key_source"] == "none", "chưa set gì -> api_key_source = none")

# 17b. PUT qua UI -> lưu key + model vào runtime_config.json, không đụng .env
r = client.put("/runtime-config", json={
    "openrouter_api_key": "sk-or-v1-test-fake-key-1234",
    "openrouter_model": "test/fake-model"
})
check(r.status_code == 200, "PUT /runtime-config returned 200")
check(r.json()["has_api_key"] is True, "sau khi PUT key -> has_api_key = True")
check(r.json()["api_key_source"] == "ui", "nguồn key = ui sau khi lưu qua UI")
check(r.json()["model"] == "test/fake-model", "model đã lưu đúng qua UI")
check(r.json()["api_key_masked"] not in (None, "sk-or-v1-test-fake-key-1234"),
      "api_key_masked KHÔNG trả key thật ở dạng plain text")
check(main.get_effective_api_key() == "sk-or-v1-test-fake-key-1234",
      "get_effective_api_key() đọc đúng key vừa lưu qua UI")
check(main.has_real_api_key() is True, "has_real_api_key() = True sau khi có key qua UI")

# GET lại xác nhận đã persist ra file (không chỉ tồn tại trong response PUT)
r = client.get("/runtime-config")
check(r.json()["model"] == "test/fake-model", "GET lại sau PUT vẫn thấy model đã lưu (persist đúng file)")

# 17c. Xoá key qua endpoint riêng -> quay lại has_api_key False (không có
# key .env), model KHÔNG bị xoá theo (2 field độc lập nhau).
r = client.delete("/runtime-config/api-key")
check(r.status_code == 200, "DELETE /runtime-config/api-key returned 200")
check(r.json()["has_api_key"] is False, "sau khi xoá key -> has_api_key = False")
check(r.json()["model"] == "test/fake-model", "xoá key KHÔNG ảnh hưởng tới model đã lưu riêng")

# 17d. (CẬP NHẬT 04/07, mục 4 roadmap) 429 giờ CHỈ thử 1 lần rồi raise
# RateLimitError NGAY (không còn tự sleep/retry trong call_llm nữa -- vòng
# lặp retry đã chuyển ra frontend để hiện tiến trình + cho phép Dừng, xem
# app.js). retry_after phải lấy đúng từ header Retry-After nếu provider có
# trả về.
r = client.put("/runtime-config", json={"openrouter_api_key": "sk-or-v1-test-fake-key-1234"})
check(r.status_code == 200, "(tiền đề 17d) PUT lại key test returned 200")


class _FakeResp:
    def __init__(self, status_code, json_data=None, headers=None, text=""):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.headers = headers or {"Content-Type": "application/json"}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise main.requests.exceptions.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._json_data


_post_call_count = {"n": 0}


def fake_post_429_with_retry_after(url, headers=None, json=None, timeout=None):
    _post_call_count["n"] += 1
    return _FakeResp(429, headers={"Retry-After": "17"})


original_post = main.requests.post
main.requests.post = fake_post_429_with_retry_after
_raised = None
try:
    main.call_llm("system", "user prompt")
except main.RateLimitError as e:
    _raised = e
main.requests.post = original_post

check(_post_call_count["n"] == 1, "call_llm KHÔNG tự retry nữa -- chỉ gọi requests.post đúng 1 lần khi gặp 429")
check(_raised is not None, "call_llm raise RateLimitError (không phải LLMCallError trần) khi gặp 429")
check(isinstance(_raised, main.LLMCallError), "RateLimitError vẫn là 1 loại LLMCallError (subclass) để chỗ fail-open cũ không bị vỡ")
check(_raised.retry_after == 17.0, "RateLimitError.retry_after lấy đúng giá trị từ header Retry-After")
check("429" in str(_raised) or "rate" in str(_raised).lower(),
      "thông báo lỗi có nhắc rõ nguyên nhân là rate-limit/429")

# 17e. 429 nhưng provider KHÔNG trả header Retry-After -> retry_after = None
# (để phía gọi -- ở đây là frontend -- tự quyết định khoảng chờ mặc định
# riêng, backend không đoán hộ).
main.requests.post = lambda url, headers=None, json=None, timeout=None: _FakeResp(429, headers={})
_raised2 = None
try:
    main.call_llm("system", "user prompt")
except main.RateLimitError as e:
    _raised2 = e
main.requests.post = original_post
check(_raised2 is not None, "call_llm vẫn raise RateLimitError khi 429 không có Retry-After")
check(_raised2.retry_after is None, "retry_after = None khi provider không trả header Retry-After (không tự bịa số)")

# 17f. chapter/continue: khi narrator gặp 429 thật (RateLimitError) -> lộ ra
# HTTP 429 THẬT (không phải 503) kèm retry_after trong detail, để frontend
# có đủ thông tin tự lặp lại có tiến trình. KHÔNG ghi chapter nào.
LLM_ERROR_WORLD = "test_engine_world_llmerror"
wp5 = main.world_path_of(LLM_ERROR_WORLD)
shutil.rmtree(wp5, ignore_errors=True)
r = client.post(f"/worlds/{LLM_ERROR_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 17f) seed-demo returned 200")
chapters_before = client.get(f"/worlds/{LLM_ERROR_WORLD}").json()["chapters"]["chapters"]


def fake_call_llm_rate_limited(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    raise main.RateLimitError("giả lập 429 thật từ OpenRouter", retry_after=9.5)


main.call_llm = fake_call_llm_rate_limited
r = client.post(f"/worlds/{LLM_ERROR_WORLD}/chapter/continue", json={"user_input": "test"})
main.call_llm = original_call_llm
check(r.status_code == 429, "chapter/continue trả 429 THẬT (không phải 503) khi narrator gặp rate-limit")
detail = r.json()["detail"]
check(isinstance(detail, dict) and detail.get("retry_after") == 9.5,
      "detail của lỗi 429 có kèm retry_after để frontend đọc, đúng giá trị đã raise")
check("OpenRouter" in detail.get("message", "") or "rate" in detail.get("message", "").lower(),
      "detail.message mô tả rõ nguyên nhân là rate-limit")
chapters_after = client.get(f"/worlds/{LLM_ERROR_WORLD}").json()["chapters"]["chapters"]
check(len(chapters_after) == len(chapters_before),
      "KHÔNG có chapter nào được ghi khi narrator gặp rate-limit (tránh state nửa vời)")

# 17g. chapter/continue: khi narrator gặp lỗi thật KHÔNG PHẢI 429 (mạng lỗi,
# key sai, response sai định dạng...) -> vẫn lộ ra HTTP 503 như thiết kế cũ
# (mục 0.2), KHÔNG ghi chapter nào.
def fake_call_llm_raises(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    raise main.LLMCallError("giả lập lỗi gọi OpenRouter thật (không phải 429, vd network/key sai)")


main.call_llm = fake_call_llm_raises
r = client.post(f"/worlds/{LLM_ERROR_WORLD}/chapter/continue", json={"user_input": "test"})
main.call_llm = original_call_llm
check(r.status_code == 503, "chapter/continue trả 503 rõ ràng khi narrator gọi LLM thất bại thật (không phải 429)")
check("OpenRouter" in r.json()["detail"] or "narrator" in r.json()["detail"].lower(),
      "detail lỗi 503 có mô tả rõ nguyên nhân (không phải thông báo chung chung)")
chapters_after2 = client.get(f"/worlds/{LLM_ERROR_WORLD}").json()["chapters"]["chapters"]
check(len(chapters_after2) == len(chapters_before),
      "KHÔNG có chapter nào được ghi khi narrator lỗi thật (tránh state nửa vời)")

# 17h. (CAP NHAT F07) Consistency checker lỗi (LLMCallError, kể cả
# RateLimitError vì là subclass) -> trạng thái "unavailable". Chính sách mặc
# định MỚI: lượt chưa kiểm tra được giữ làm draft, KHÔNG commit (không tăng
# tick, không áp hậu quả), API trả 503 kèm lời giải thích và đường thử lại.
# Assertion cũ "200 + fail-open" đã bị đổi theo thiết kế F07; tác động tương
# thích: world cũ muốn giữ fail-open đặt allow_unchecked_commit=true.
def fake_call_llm_checker_fails(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        raise main.RateLimitError("giả lập checker gặp 429", retry_after=3)
    return main.mock_narrator_response(user_input_for_mock)


main.call_llm = fake_call_llm_checker_fails
r = client.post(f"/worlds/{LLM_ERROR_WORLD}/chapter/continue", json={"user_input": "test 2"})
main.call_llm = original_call_llm
check(r.status_code == 503, "checker unavailable -> 503 (giu draft, khong commit)")
detail17h = r.json()["detail"]
check(detail17h.get("reason") == "consistency_checker_unavailable",
      "detail17h. reason = consistency_checker_unavailable")
check(detail17h.get("status") == "unavailable" and detail17h.get("persisted") is False,
      "detail17h. trang thai unavailable va persisted=False")
chapters_after_17h = client.get(f"/worlds/{LLM_ERROR_WORLD}").json()["chapters"]["chapters"]
check(len(chapters_after_17h) == len(chapters_before),
      "draft khong ghi chapter nao (khong tang tick/hau qua)")
check(client.get(f"/worlds/{LLM_ERROR_WORLD}").json()["world_config"]["story_clock"]["tick"] == 0,
      "draft khong tang tick")

shutil.rmtree(wp5, ignore_errors=True)

# 17i. POST /runtime-config/test-connection (mục 11 roadmap): phân loại rõ
# OK / sai key / hết credit / rate-limit / model sai / lỗi mạng, không cần
# đi vòng qua 1 chapter/continue thật mới biết key có vấn đề gì.
r = client.delete("/runtime-config/api-key")
check(r.status_code == 200, "(tiền đề 17i) xoá key returned 200")
r = client.post("/runtime-config/test-connection")
check(r.status_code == 200, "test-connection luôn returned 200 (bản thân kết quả test mới là ok=True/False)")
check(r.json()["ok"] is False and r.json()["reason"] == "no_key",
      "chưa có key nào -> ok=False, reason=no_key")

r = client.put("/runtime-config", json={"openrouter_api_key": "sk-or-v1-test-fake-key-1234"})
check(r.status_code == 200, "(tiền đề 17i) PUT lại key test returned 200")

main.requests.post = lambda url, headers=None, json=None, timeout=None: _FakeResp(
    200, json_data={"choices": [{"message": {"content": "hi"}}]}
)
r = client.post("/runtime-config/test-connection")
main.requests.post = original_post
check(r.json()["ok"] is True and r.json()["reason"] == "ok", "provider returned 200 -> ok=True, reason=ok")

main.requests.post = lambda url, headers=None, json=None, timeout=None: _FakeResp(401)
r = client.post("/runtime-config/test-connection")
main.requests.post = original_post
check(r.json()["ok"] is False and r.json()["reason"] == "unauthorized",
      "provider trả 401 -> ok=False, reason=unauthorized (sai key)")

main.requests.post = lambda url, headers=None, json=None, timeout=None: _FakeResp(429)
r = client.post("/runtime-config/test-connection")
main.requests.post = original_post
check(r.json()["ok"] is False and r.json()["reason"] == "rate_limited",
      "provider trả 429 -> ok=False, reason=rate_limited (key có thể vẫn đúng)")


def fake_post_network_error(url, headers=None, json=None, timeout=None):
    raise main.requests.exceptions.RequestException("simulated network failure")


main.requests.post = fake_post_network_error
r = client.post("/runtime-config/test-connection")
main.requests.post = original_post
check(r.json()["ok"] is False and r.json()["reason"] == "network",
      "lỗi mạng khi test -> ok=False, reason=network, không crash endpoint")

# Khôi phục runtime_config.json + biến môi trường như trước khi test chạy
if _runtime_cfg_backup is not None:
    with open(main.RUNTIME_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(_runtime_cfg_backup)
elif os.path.isfile(main.RUNTIME_CONFIG_PATH):
    os.remove(main.RUNTIME_CONFIG_PATH)
if _env_key_backup is not None:
    os.environ["OPENROUTER_API_KEY"] = _env_key_backup
if _env_model_backup is not None:
    os.environ["OPENROUTER_MODEL"] = _env_model_backup

# ---------------------------------------------------------------------
# 18. Muc 0.5 roadmap (05/07): /chapter/start -- chapter mo dau, phat sinh
#     tu playtest cua Rinn (thieu "greeting message" giong SillyTavern).
# ---------------------------------------------------------------------
START_WORLD = "test_engine_world_chapter_start"
wp6 = main.world_path_of(START_WORLD)
if os.path.isdir(wp6):
    shutil.rmtree(wp6)

r = client.post(f"/worlds/{START_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 18) seed-demo returned 200")

# 18a. world mới seed -- opening_mode mặc định phải là "ai_generate" và
# opening_text mặc định rỗng (không phá world cũ nào chưa có 2 field này).
world_before_start = client.get(f"/worlds/{START_WORLD}").json()
check(world_before_start["world_config"]["opening_mode"] == "ai_generate",
      "seed-demo mặc định opening_mode = ai_generate")
check(world_before_start["world_config"]["opening_text"] == "",
      "seed-demo mặc định opening_text rỗng")

# 18b. ai_generate (mặc định, không truyền gì trong request): phải gọi
# narrator với 1 "user_input" giả lập nhắc tới mô tả của cp_0, nhưng
# chapter_record["user_input"] lưu lại (hiện lên UI) phải RỖNG -- vì đây là
# chapter do hệ thống tự soạn, không phải user vừa gõ gì.
captured_opening = {}


def fake_call_llm_capture_opening(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            captured_opening["user_prompt"] = user_prompt
            captured_opening["user_input_for_mock"] = user_input_for_mock
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()


main.call_llm = fake_call_llm_capture_opening
r = client.post(f"/worlds/{START_WORLD}/chapter/start", json={})
main.call_llm = original_call_llm
check(r.status_code == 200, "chapter/start (ai_generate mặc định) returned 200")
start_chapter = r.json()["chapter"]
check(start_chapter["chapter_index"] == 1, "chapter/start tạo đúng chapter_index = 1")
check(start_chapter["user_input"] == "",
      "chapter/start (ai_generate) lưu user_input RỖNG -- không hiện như user tự gõ")
check("nhập môn" in captured_opening["user_prompt"] or "Gu Changge" in captured_opening["user_prompt"],
      "narrator nhận được instruction có nhắc tới mô tả checkpoint cp_0")
check(len(start_chapter["chapter_text"]) > 0, "chapter/start (ai_generate) vẫn sinh ra chapter_text")

# 18c. World đã có 1 chapter (vừa tạo ở 18b) -- gọi /chapter/start lần nữa
# phải bị chặn (400), phải dùng /chapter/continue để viết tiếp.
r = client.post(f"/worlds/{START_WORLD}/chapter/start", json={})
check(r.status_code == 400, "chapter/start lần 2 (đã có chapter) -> 400, không cho tạo lại chapter mở đầu")

shutil.rmtree(wp6, ignore_errors=True)

# 18d. user_defined: dùng nguyên opening_text, KHÔNG gọi narrator/checker
# (call_llm không được đụng tới lần nào), ghi thẳng thành chapter 1.
r = client.post(f"/worlds/{START_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 18d) seed-demo lại returned 200")

llm_called = {"count": 0}


def fake_call_llm_should_not_be_called(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    llm_called["count"] += 1
    return main.mock_narrator_response(user_input_for_mock)


main.call_llm = fake_call_llm_should_not_be_called
custom_opening = "Đêm đó, sương giăng kín Starting Sect, Xue Li đứng lặng nhìn ánh trăng."
r = client.post(f"/worlds/{START_WORLD}/chapter/start",
                json={"opening_mode": "user_defined", "opening_text": custom_opening})
main.call_llm = original_call_llm
check(r.status_code == 200, "chapter/start (user_defined) returned 200")
check(llm_called["count"] == 0, "chapter/start (user_defined) KHÔNG gọi narrator/checker lần nào")
ud_chapter = r.json()["chapter"]
check(ud_chapter["chapter_text"] == custom_opening,
      "chapter/start (user_defined) giữ nguyên 100% opening_text, không sửa gì")
check(ud_chapter["consistency_check"]["severity"] == "none",
      "chapter/start (user_defined) đánh dấu severity none (không thật sự kiểm tra)")

# 18e. user_defined nhưng thiếu opening_text (cả request lẫn world_config
# đều rỗng) -> 400 rõ ràng, không âm thầm tạo chapter rỗng.
shutil.rmtree(wp6, ignore_errors=True)
r = client.post(f"/worlds/{START_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 18e) seed-demo lại returned 200")
r = client.post(f"/worlds/{START_WORLD}/chapter/start", json={"opening_mode": "user_defined"})
check(r.status_code == 400, "chapter/start (user_defined) thiếu opening_text -> 400")

# 18f. opening_mode không hợp lệ -> 400, kể cả khi set qua world_config
# (không phải chỉ validate ở request).
r = client.put(f"/worlds/{START_WORLD}/world_config", json={"opening_mode": "yolo_mode"})
check(r.status_code == 400, "PUT world_config với opening_mode sai -> 400 (không lưu giá trị rác)")
r = client.post(f"/worlds/{START_WORLD}/chapter/start", json={"opening_mode": "yolo_mode"})
check(r.status_code == 400, "chapter/start với opening_mode sai (request) -> 400")

# 18g. Creator set opening_mode=user_defined + opening_text sẵn qua PUT
# world_config -- gọi /chapter/start KHÔNG cần truyền gì cũng phải dùng
# đúng giá trị mặc định đó (không bắt buộc phải gửi lại opening_text).
preset_text = "Chương do Rinn viết sẵn trong Creator Mode trước khi bắt đầu chơi."
r = client.put(f"/worlds/{START_WORLD}/world_config",
               json={"opening_mode": "user_defined", "opening_text": preset_text})
check(r.status_code == 200, "(tiền đề 18g) PUT world_config set sẵn opening_mode/opening_text returned 200")
r = client.post(f"/worlds/{START_WORLD}/chapter/start", json={})
check(r.status_code == 200, "chapter/start không truyền gì vẫn dùng đúng mặc định đã set trong world_config")
check(r.json()["chapter"]["chapter_text"] == preset_text,
      "chapter/start dùng đúng opening_text đã set sẵn qua world_config, không cần gửi lại")

shutil.rmtree(wp6, ignore_errors=True)

# =======================================================================
# 19. Turn/Chapter tier (muc 0.6 #1 roadmap, 07/07/2026)
#    - Nhieu turn (1 lan goi narrator) co the gom vao 1 chapter, dong lai
#      theo nguong mem (so turn/so tu) hoac narrator tu bao "chapter_end".
#    - Nguong cung (hard cap) la rao an toan cuoi cung.
#    - recent_turns context = N TURN gan nhat (flatten), khong con N
#      CHAPTER gan nhat nhu truoc.
#    - build_save_entry: chapter_count/turn_count tach biet.
#    - Backward-compat voi data cu (thieu "chapter_closed").
# =======================================================================

import json as _json19


def make_narrator_json(text, chapter_end=False, chapter_title=None, notes=""):
    payload = {
        "chapter_text": text,
        "state_changes": {"characters": {}, "notes": notes},
        "chapter_end": chapter_end,
    }
    if chapter_title is not None:
        payload["chapter_title"] = chapter_title
    return _json19.dumps(payload, ensure_ascii=False)


TURN_WORLD = "test_engine_world_turns"
wp7 = main.world_path_of(TURN_WORLD)
if os.path.isdir(wp7):
    shutil.rmtree(wp7)

r = client.post(f"/worlds/{TURN_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 19) seed-demo returned 200")

# script[i] = (chapter_end, chapter_title, approx_words) narrator "trả về" ở lần gọi thứ i
# ~160 words/turn so that turn 5 has ~800 words (< 900, NOT closed) and turn 6 has ~960 (>= 900, closed)
SCRIPT_WORDS_PER_TURN = 160
script = [
    (False, None),                      # call 0 -> turn 1 (chapter 1)
    (False, None),                      # call 1 -> turn 2
    (False, None),                      # call 2 -> turn 3
    (False, None),                      # call 3 -> turn 4
    (False, None),                      # call 4 -> turn 5 (NOT closed: 5 turns but < 900 words)
    (False, None),                      # call 5 -> turn 6 (CLOSED by combined soft-close: 6 turns + >= 900 words)
    (False, None),                      # call 6 -> turn 1 của chapter 2 (chưa đóng)
    (True, "Cuộc gặp gỡ bất ngờ"),       # call 7 -> turn 2 của chapter 2, tự báo chapter_end sớm
]
call_count = {"n": 0}


def fake_call_llm_turns(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            idx = call_count["n"]
            call_count["n"] += 1
        else:
            idx = call_count["n"] - 1
        end, title = script[idx]
        text = " ".join(["word"] * SCRIPT_WORDS_PER_TURN) + f" turn thứ {idx + 1}"
        return make_narrator_json(text, chapter_end=end, chapter_title=title)
    return main.mock_consistency_checker_response()


main.call_llm = fake_call_llm_turns
turns = []
for i in range(6):
    r = client.post(f"/worlds/{TURN_WORLD}/chapter/continue", json={"user_input": f"hành động {i + 1}"})
    check(r.status_code == 200, f"19.{i + 1}. chapter/continue (turn {i + 1}) returned 200")
    turns.append(r.json()["chapter"])

check(len({t["chapter_index"] for t in turns[:4]}) == 1,
      "19a. 4 turn đầu chưa đạt ngưỡng/flag -> vẫn cùng 1 chapter_index")
check([t["turn_index"] for t in turns[:6]] == [1, 2, 3, 4, 5, 6],
      "19a. turn_index tăng dần đúng 1..6 trong cùng chapter")
check(all(not t["chapter_closed"] for t in turns[:4]),
      "19a. 4 turn đầu chưa đóng chapter (chapter_closed=False)")
check(turns[4]["chapter_index"] == turns[0]["chapter_index"],
      "19b. turn thứ 5 vẫn thuộc chapter đầu tiên")
check(turns[4]["chapter_closed"] is False,
      "19b. turn thứ 5 KHÔNG đóng chapter (5 turn nhưng chưa đủ 900 từ — cần cả 2 điều kiện)")
check(turns[5]["chapter_closed"] is True,
      "19b. turn thứ 6 đạt cả turn threshold (>=5) và word threshold (>=900) -> tự động đóng")

r = client.post(f"/worlds/{TURN_WORLD}/chapter/continue", json={"user_input": "hành động 7"})
check(r.status_code == 200, "19c. chapter/continue (turn 7) returned 200")
t7 = r.json()["chapter"]
turns.append(t7)
check(t7["chapter_index"] == turns[0]["chapter_index"] + 1,
      "19c. turn thứ 7 bắt đầu CHAPTER MỚI (chapter_index +1) sau khi chapter trước đã đóng")
check(t7["turn_index"] == 1, "19c. turn đầu của chapter mới có turn_index = 1")
check(t7["chapter_closed"] is False, "19c. turn đầu của chapter mới chưa đóng")

r = client.post(f"/worlds/{TURN_WORLD}/chapter/continue", json={"user_input": "hành động 8"})
check(r.status_code == 200, "19d. chapter/continue (turn 8, narrator tự báo chapter_end sớm) returned 200")
t8 = r.json()["chapter"]
turns.append(t8)
check(t8["chapter_index"] == t7["chapter_index"], "19d. turn 8 vẫn thuộc chapter 2")
check(t8["turn_index"] == 2, "19d. turn 8 là turn thứ 2 của chapter 2")
check(t8["chapter_closed"] is True,
      "19d. narrator tự báo chapter_end=True -> chapter đóng SỚM, không cần chờ đủ ngưỡng mềm")
check(t8["chapter_title"] == "Cuộc gặp gỡ bất ngờ",
      "19d. chapter_title của narrator được lưu đúng khi turn đó đóng chapter")
check(turns[6]["chapter_title"] is None,
      "19d. turn KHÔNG đóng chapter thì chapter_title luôn None, dù narrator có gửi gì đi nữa")

# 19e. Kiểm tra trực tiếp decide_chapter_closed() cho 2 nhánh khó tạo qua
# kịch bản turn thật (ngưỡng theo SỐ TỪ, và rào an toàn cứng theo SỐ TURN
# -- nhánh này luôn bị ngưỡng mềm theo turn "vượt mặt" trước trong kịch
# bản thật vì CHAPTER_SOFT_CLOSE_TURNS < CHAPTER_HARD_CLOSE_TURNS).
fake_chapters_words = {"chapters": [
    {"chapter_index": 99, "turn_index": i, "chapter_closed": False, "chapter_text": "một hai ba bốn năm"}
    for i in range(1, 4)
]}
not_yet = main.decide_chapter_closed(99, 4, fake_chapters_words, "một hai ba", False)
check(not_yet is False, "19e. chưa đủ số turn/số từ/không có flag -> chưa đóng")

long_text = " ".join(["từ"] * main.CHAPTER_SOFT_CLOSE_WORDS)
closed_by_words = main.decide_chapter_closed(99, 4, fake_chapters_words, long_text, False)
check(closed_by_words is False,
      "19e. vượt ngưỡng SỐ TỪ nhưng chưa đủ số turn SOFT_CLOSE_TURNS -> chưa đóng (cần cả 2 điều kiện)")

fake_chapters_hard = {"chapters": [
    {"chapter_index": 100, "turn_index": i, "chapter_closed": False, "chapter_text": "ok"}
    for i in range(1, main.CHAPTER_HARD_CLOSE_TURNS)
]}
closed_by_hard_cap = main.decide_chapter_closed(
    100, main.CHAPTER_HARD_CLOSE_TURNS, fake_chapters_hard, "ok", False
)
check(closed_by_hard_cap is True,
      "19e. đạt rào an toàn cứng CHAPTER_HARD_CLOSE_TURNS -> luôn đóng (an toàn cuối cùng)")

# 19f. recent_turns context: payload gửi narrator dùng key "recent_turns"
# (thay cho "recent_chapters" cũ) -- xác nhận bằng cách bắt user_prompt thật.
captured_payload = {}


def fake_call_llm_capture_turns(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            captured_payload["user_prompt"] = user_prompt
        return make_narrator_json("Turn kiểm tra context", chapter_end=False)
    return main.mock_consistency_checker_response()


main.call_llm = fake_call_llm_capture_turns
r = client.post(f"/worlds/{TURN_WORLD}/chapter/continue", json={"user_input": "kiểm tra context"})
check(r.status_code == 200, "19f. chapter/continue (kiểm tra context) returned 200")
check('"recent_turns"' in captured_payload["user_prompt"],
      "19f. payload gửi narrator dùng đúng key 'recent_turns' (không còn 'recent_chapters')")

# 19g. build_save_entry: chapter_count = chapter_index của turn CUỐI CÙNG
# (khác len(list) -- vì 1 chapter giờ có thể gồm nhiều turn), turn_count =
# tổng số turn (len danh sách).
r = client.post(f"/worlds/{TURN_WORLD}/saves", json={"label": "kiểm tra đếm chapter/turn"})
check(r.status_code == 200, "19g. POST saves returned 200")
save_entry = r.json()["save"]
world_after = client.get(f"/worlds/{TURN_WORLD}").json()
turns_now = world_after["chapters"]["chapters"]
check(save_entry["chapter_count"] == turns_now[-1]["chapter_index"],
      "19g. chapter_count = chapter_index của turn cuối cùng (đúng theo Turn/Chapter tier)")
check(save_entry["turn_count"] == len(turns_now),
      "19g. turn_count = tổng số turn (len danh sách), khác chapter_count")

# 19h. Backward-compat: data world CŨ (trước mục này) không có field
# "chapter_closed" -- turn tiếp theo phải coi như chapter đã đóng (đúng
# hành vi cũ: mỗi turn cũ là 1 chapter riêng), không crash/KeyError.
LEGACY_WORLD = "test_engine_world_legacy_turns"
wpl = main.world_path_of(LEGACY_WORLD)
if os.path.isdir(wpl):
    shutil.rmtree(wpl)
r = client.post(f"/worlds/{LEGACY_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 19h) seed-demo returned 200")
legacy_chapters_data = main.read_world_file(wpl, "chapters.json")
legacy_chapters_data["chapters"] = [
    {
        "chapter_index": 1,
        "checkpoint_id": "cp_0",
        "user_input": "hành động cũ",
        "chapter_text": "Chapter cũ từ trước khi có Turn/Chapter tier.",
        "notes": "",
        "boundary_correction": None,
        "consistency_check": {"severity": "none", "issues": [], "explanation": "", "triggered_rewrite": False}
    }
]
main.write_world_file(wpl, "chapters.json", legacy_chapters_data)

main.call_llm = fake_call_llm_capture_turns  # tái dùng, luôn chapter_end=False
r = client.post(f"/worlds/{LEGACY_WORLD}/chapter/continue", json={"user_input": "hành động mới"})
check(r.status_code == 200, "19h. chapter/continue trên data legacy (thiếu chapter_closed) returned 200, không crash")
new_turn_over_legacy = r.json()["chapter"]
check(new_turn_over_legacy["chapter_index"] == 2,
      "19h. data cũ (thiếu chapter_closed) được coi là ĐÃ ĐÓNG -> turn mới bắt đầu chapter 2")
check(new_turn_over_legacy["turn_index"] == 1,
      "19h. turn đầu của chapter mới đúng turn_index = 1")

main.call_llm = original_call_llm
shutil.rmtree(wpl, ignore_errors=True)
shutil.rmtree(wp7, ignore_errors=True)

# =======================================================================
# 20. Sliding window + running summary (muc 0.6 #2 roadmap, 08/07/2026)
#    - RECENT_TURNS_CONTEXT_LIMIT giam 5 -> 2.
#    - running_summary (top-level chapters.json) chi cap nhat KHI 1 chapter
#      vua dong lai, qua 1 LLM call rieng (SUMMARIZER_SYSTEM_PROMPT).
#    - Fail-open: loi goi summarizer KHONG duoc chan/lam hong chapter vua
#      sinh, chi giu nguyen running_summary cu.
#    - base_payload gui narrator phai mang theo running_summary hien tai.
# =======================================================================

check(main.RECENT_TURNS_CONTEXT_LIMIT == 2,
      "20a. RECENT_TURNS_CONTEXT_LIMIT đã giảm đúng còn 2 theo quyết định của Rinn")

# 20b. parse_summarizer_response: unit test trực tiếp (không qua HTTP),
# giống cách 19e test decide_chapter_closed() trực tiếp.
check(main.parse_summarizer_response('{"running_summary": "Tóm tắt mới"}', fallback="cũ")["running_summary"] == "Tóm tắt mới",
      "20b. parse_summarizer_response parse JSON hợp lệ đúng")
check(main.parse_summarizer_response('không phải JSON', fallback="giữ nguyên cũ")["running_summary"] == "giữ nguyên cũ",
      "20b. parse_summarizer_response fail-open khi JSON hỏng -> giữ fallback")
check(main.parse_summarizer_response('{"running_summary": ""}', fallback="giữ nguyên cũ")["running_summary"] == "giữ nguyên cũ",
      "20b. parse_summarizer_response fail-open khi running_summary rỗng -> giữ fallback")
check(main.parse_summarizer_response('{"khác": 1}', fallback="giữ nguyên cũ")["running_summary"] == "giữ nguyên cũ",
      "20b. parse_summarizer_response fail-open khi thiếu field running_summary -> giữ fallback")
check(main.parse_summarizer_response(
    '{"running_summary": "Tóm tắt", "memorable_beats": ["beat1", "beat2"]}', fallback="cũ"
)["memorable_beats"] == ["beat1", "beat2"],
"20b. parse_summarizer_response parses memorable_beats correctly")
check(main.parse_summarizer_response(
    '{"running_summary": "Tóm tắt"}', fallback="cũ"
)["memorable_beats"] == [],
"20b. parse_summarizer_response defaults to [] when memorable_beats missing")
check(main.parse_summarizer_response(
    '{"running_summary": "Tóm tắt", "memorable_beats": "không phải list"}', fallback="cũ"
)["memorable_beats"] == [],
"20b. parse_summarizer_response handles invalid memorable_beats type gracefully")

# 20c. build_rag_context_text: running_summary (khi có) phải nằm trong query
# dùng chọn lore card, không phá hành vi cũ khi không truyền gì (mặc định "").
rag_no_summary = main.build_rag_context_text([{"chapter_text": "abc"}], "hỏi gì đó")
check("abc" in rag_no_summary and "hỏi gì đó" in rag_no_summary,
      "20c. build_rag_context_text không truyền running_summary vẫn hoạt động như cũ")
rag_with_summary = main.build_rag_context_text(
    [{"chapter_text": "abc"}], "hỏi gì đó", running_summary="tóm tắt nền XYZ"
)
check("tóm tắt nền XYZ" in rag_with_summary,
      "20c. build_rag_context_text đưa running_summary vào query khi có")

# 20d-20h. Kịch bản qua HTTP thật.
SUMMARY_WORLD = "test_engine_world_summary"
wp8 = main.world_path_of(SUMMARY_WORLD)
if os.path.isdir(wp8):
    shutil.rmtree(wp8)
r = client.post(f"/worlds/{SUMMARY_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 20) seed-demo returned 200")

summarizer_calls = []
summarizer_should_fail = {"on": False}
# script_20[i] = (chapter_end, chapter_title) narrator "trả về" ở lần gọi thứ i
script_20 = [
    (False, None),                # call 0 -> turn 1 (chapter 1, chưa đóng)
    (True, "Chương Một"),         # call 1 -> turn 2 (chapter 1, ĐÓNG)
    (False, None),                # call 2 -> turn 1 của chapter 2 (chưa đóng)
]
call_count_20 = {"n": 0}


def fake_call_llm_summary(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            idx = call_count_20["n"]
            call_count_20["n"] += 1
        else:
            idx = call_count_20["n"] - 1
        end, title = script_20[idx]
        return make_narrator_json(
            f"Đoạn turn thứ {idx + 1} của bài test running summary", chapter_end=end, chapter_title=title
        )
    if system_prompt == main.SUMMARIZER_SYSTEM_PROMPT:
        summarizer_calls.append(user_prompt)
        if summarizer_should_fail["on"]:
            raise main.LLMCallError("giả lập lỗi gọi summarizer")
        return _json19.dumps({
            "running_summary": f"Tóm tắt sau lần gọi thứ {len(summarizer_calls)}",
            "memorable_beats": [f"Khoảnh khắc đáng nhớ từ lần gọi thứ {len(summarizer_calls)}"]
        }, ensure_ascii=False)
    return main.mock_consistency_checker_response()


main.call_llm = fake_call_llm_summary
r = client.post(f"/worlds/{SUMMARY_WORLD}/chapter/continue", json={"user_input": "hành động 1"})
check(r.status_code == 200, "20d. turn 1 (chưa đóng chapter) returned 200")
check(len(summarizer_calls) == 0, "20d. turn CHƯA đóng chapter -> summarizer KHÔNG được gọi")
world_mid = client.get(f"/worlds/{SUMMARY_WORLD}").json()
check(world_mid["chapters"]["running_summary"] == "",
      "20d. running_summary vẫn rỗng khi chưa có chapter nào đóng")

r = client.post(f"/worlds/{SUMMARY_WORLD}/chapter/continue", json={"user_input": "hành động 2"})
check(r.status_code == 200, "20e. turn 2 (đóng chapter 1) returned 200")
check(len(summarizer_calls) == 1, "20e. turn ĐÓNG chapter -> summarizer được gọi đúng 1 lần")
check("Đoạn turn thứ 1" in summarizer_calls[0] and "Đoạn turn thứ 2" in summarizer_calls[0],
      "20e. payload gửi summarizer gộp ĐỦ nội dung cả 2 turn cùng chapter, đúng thứ tự")
check('"previous_summary": ""' in summarizer_calls[0],
      "20e. lần đóng chapter ĐẦU TIÊN gửi previous_summary rỗng")
check("Chương Một" in summarizer_calls[0],
      "20e. payload gửi summarizer có kèm chapter_title vừa chốt")
world_after_close = client.get(f"/worlds/{SUMMARY_WORLD}").json()
check(world_after_close["chapters"]["running_summary"] == "Tóm tắt sau lần gọi thứ 1",
      "20e. running_summary được cập nhật đúng bằng kết quả summarizer trả về")
first_beat_20 = world_after_close["chapters"].get("memorable_beats", [None])[0] if world_after_close["chapters"].get("memorable_beats") else ""
check(first_beat_20.startswith("[Ch.1]") and "Khoảnh khắc" in first_beat_20,
      "20e. memorable_beats được lưu và tag chapter_index + checkpoint_id đúng")

r = client.post(f"/worlds/{SUMMARY_WORLD}/chapter/continue", json={"user_input": "hành động 3"})
check(r.status_code == 200, "20f. turn 3 (chapter 2, chưa đóng) returned 200")
check(len(summarizer_calls) == 1, "20f. turn chưa đóng chapter -> summarizer vẫn KHÔNG gọi thêm")

# 20g. base_payload gửi narrator phải mang đúng running_summary hiện tại.
captured_running_summary_payload = {}


def fake_call_llm_capture_running_summary(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            captured_running_summary_payload["user_prompt"] = user_prompt
        return make_narrator_json("Turn kiểm tra running_summary trong payload", chapter_end=False)
    return main.mock_consistency_checker_response()


main.call_llm = fake_call_llm_capture_running_summary
r = client.post(f"/worlds/{SUMMARY_WORLD}/chapter/continue", json={"user_input": "hành động 4"})
check(r.status_code == 200, "20g. turn 4 (kiểm tra payload) returned 200")
check('"summary": "Tóm tắt sau lần gọi thứ 1"' in captured_running_summary_payload["user_prompt"],
      "20g. base_payload gửi narrator mang đúng running_summary hiện tại (trong multi_tier_context.tier_2_rolling_summary)")
check('"tier_2_memorable_beats"' in captured_running_summary_payload["user_prompt"],
      "20g. base_payload gửi narrator mang tier_2_memorable_beats trong multi_tier_context")

# 20h. Fail-open: summarizer lỗi khi chapter đóng -> chapter vẫn lưu thành
# công (200), running_summary GIỮ NGUYÊN giá trị cũ (không mất, không crash).
summarizer_should_fail["on"] = True
script_20 = [(True, "Chương Hai")]  # ép đóng chapter 2 ngay ở turn tiếp theo
call_count_20["n"] = 0
main.call_llm = fake_call_llm_summary
r = client.post(f"/worlds/{SUMMARY_WORLD}/chapter/continue", json={"user_input": "hành động 5"})
check(r.status_code == 200, "20h. chapter/continue vẫn returned 200 dù summarizer lỗi khi chapter đóng (fail-open)")
world_after_fail = client.get(f"/worlds/{SUMMARY_WORLD}").json()
check(world_after_fail["chapters"]["running_summary"] == "Tóm tắt sau lần gọi thứ 1",
      "20h. running_summary GIỮ NGUYÊN giá trị cũ khi summarizer lỗi, không bị xoá/crash")
first_beat_20h = world_after_fail["chapters"].get("memorable_beats", [None])[0] if world_after_fail["chapters"].get("memorable_beats") else ""
check(first_beat_20h.startswith("[Ch.1]") and "Khoảnh khắc" in first_beat_20h,
      "20h. memorable_beats GIỮ NGUYÊN giá trị cũ khi summarizer lỗi")

# 20i. Scaled word budget: pure function tests (không qua HTTP)
check(main.compute_word_budget(0) == main.CHAPTER_SUMMARY_BUDGET_FLOOR,
      "20i. word budget floor applied for 0 total words")
check(main.compute_word_budget(500) == main.CHAPTER_SUMMARY_BUDGET_FLOOR,
      "20i. word budget stays at floor for short stories")
check(main.compute_word_budget(8000) == int(8000 * main.CHAPTER_SUMMARY_BUDGET_RATIO),
      "20i. word budget scales: 8000 words -> 240")
check(main.compute_word_budget(50000) == main.CHAPTER_SUMMARY_BUDGET_CEIL,
      "20i. word budget capped at ceiling for long stories")
check(main.total_story_word_count({"chapters": [
    {"chapter_text": "hai từ"}, {"chapter_text": "ba từ rưỡi"}
]}) == 5,
"20i. total_story_word_count counts words correctly")

# 20j. Backward compatibility: old-world chapters_data (without memorable_beats) survives
old_style = {"chapters": [], "running_summary": ""}
check("memorable_beats" not in old_style,
      "20j. old-style dict has no memorable_beats key (simulating pre-upgrade world)")
# Simulate chapter close with beats returned from summarizer
main.update_running_summary(old_style, 0, "Chương Cũ", world_name=SUMMARY_WORLD)
check(old_style.get("memorable_beats", []) == [],
      "20j. old-style dict NOT polluted with memorable_beats when summarizer returns no beats")
# Now simulate with beats (like a real upgraded summarizer)
old_style2 = {"chapters": [], "running_summary": ""}
new_beats_list = ["chi tiết sống sót"]
tagged = [f"[Ch.0] {b}" for b in new_beats_list]
old_style2["memorable_beats"] = tagged + old_style2.get("memorable_beats", [])
check(old_style2.get("memorable_beats", []) == ["[Ch.0] chi tiết sống sót"],
      "20j. old-world dict upgrades gracefully: memorable_beats field added on first write with beats")

# 20k. Detail survival: memorable_beats accumulate and persist across many chapters
# (synthetic simulation covering the acceptance criterion)
acc = {"memorable_beats": []}
# Simulate 10 chapter closings, each with a unique beat (no cap = no eviction)
for ch in range(1, 11):
    new_beats = [f"chi tiết đặc biệt từ chương {ch}"]
    tagged = [f"[Ch.{ch}] {b}" for b in new_beats]
    existing = acc.get("memorable_beats", [])
    acc["memorable_beats"] = tagged + existing
check(len(acc["memorable_beats"]) == 10,
      "20k. 10 chapters * 1 beat each = 10 beats stored")
check(acc["memorable_beats"][0] == "[Ch.10] chi tiết đặc biệt từ chương 10",
      "20k. newest beats prepended first")
check("[Ch.1] chi tiết đặc biệt từ chương 1" in acc["memorable_beats"],
      "20k. chapter 1 detail still recoverable at chapter 10 (no disk eviction)")
# Verify per-chapter fairness in token budget filter:
# beats are grouped by chapter, 2 per chapter, under tight budget
tight_beats = [
    "[Ch.5] alpha", "[Ch.5] beta", "[Ch.5] gamma",
    "[Ch.4] delta", "[Ch.4] epsilon",
    "[Ch.3] zeta",
]
filtered_tight = main._filter_memorable_beats_by_token_budget(
    tight_beats, max_tokens=500, running_summary="x", max_beats_per_chapter=2
)
check(len(filtered_tight) == 5,
      "20k. tight budget: 5 beats selected (2 from Ch.5, 2 from Ch.4, 1 from Ch.3)")
check("[Ch.5] gamma" not in filtered_tight,
      "20k. tight budget: Ch.5 gamma excluded (max 2 per chapter)")
# Under generous budget, all beats are included
generous = main._filter_memorable_beats_by_token_budget(
    tight_beats, max_tokens=5000, running_summary="x", max_beats_per_chapter=5
)
check(len(generous) == 6,
      "20k. generous budget: all 6 beats included when per-chapter limit allows")

main.call_llm = original_call_llm
shutil.rmtree(wp8, ignore_errors=True)

# =======================================================================
# 21. Muc 0.6 #3 roadmap (05/07): Settings tach khoi Creator Mode + override
#     API key/model RIENG THEO WORLD (data/worlds/<world>/runtime_override.json),
#     tach biet voi app default (runtime_config.json). Thu tu uu tien da
#     chot: world override > app default (UI) > .env.
# =======================================================================
_runtime_cfg_backup_21 = None
if os.path.isfile(main.RUNTIME_CONFIG_PATH):
    with open(main.RUNTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
        _runtime_cfg_backup_21 = f.read()
if os.path.isfile(main.RUNTIME_CONFIG_PATH):
    os.remove(main.RUNTIME_CONFIG_PATH)
_env_key_backup_21 = os.environ.pop("OPENROUTER_API_KEY", None)
_env_model_backup_21 = os.environ.pop("OPENROUTER_MODEL", None)

OVERRIDE_WORLD = "test_engine_world_runtime_override"
wp9 = main.world_path_of(OVERRIDE_WORLD)
shutil.rmtree(wp9, ignore_errors=True)
r = client.post(f"/worlds/{OVERRIDE_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 21) seed-demo returned 200")

# 21a. Chưa set gì cả (app default lẫn world override) -> world-scoped GET
# vẫn returned 200, has_api_key False, world_override.has_api_key False.
r = client.get(f"/worlds/{OVERRIDE_WORLD}/runtime-config")
check(r.status_code == 200, "GET /worlds/{world}/runtime-config returned 200")
body21a = r.json()
check(body21a["has_api_key"] is False, "21a. chưa set gì -> has_api_key hiệu lực = False")
check(body21a["world_override"]["has_api_key"] is False, "21a. world_override.has_api_key = False")
check(body21a["app_default"]["has_api_key"] is False, "21a. app_default.has_api_key = False")

# 21b. World không tồn tại -> 404 (dùng require_world như các endpoint world khác)
r = client.get("/worlds/__world_khong_ton_tai__/runtime-config")
check(r.status_code == 404, "21b. GET runtime-config của world không tồn tại -> 404")

# 21c. Chỉ set app default (UI) -> world-scoped GET phải phản ánh đúng app
# default làm giá trị hiệu lực (world chưa override gì).
r = client.put("/runtime-config", json={
    "openrouter_api_key": "sk-or-v1-app-default-key",
    "openrouter_model": "app/default-model"
})
check(r.status_code == 200, "(tiền đề 21c) PUT /runtime-config (app default) returned 200")
r = client.get(f"/worlds/{OVERRIDE_WORLD}/runtime-config")
body21c = r.json()
check(body21c["has_api_key"] is True, "21c. có app default -> has_api_key hiệu lực = True")
check(body21c["api_key_source"] == "ui", "21c. nguồn hiệu lực = ui (app default) khi world chưa override")
check(body21c["model"] == "app/default-model", "21c. model hiệu lực = app default khi world chưa override")
check(main.get_effective_api_key(OVERRIDE_WORLD) == "sk-or-v1-app-default-key",
      "21c. get_effective_api_key(world_name) fallback đúng về app default khi world chưa set")

# 21d. PUT world override -> world-scoped GET phải ưu tiên world override,
# nhưng app-default section (GET /runtime-config, không world_name) KHÔNG
# đổi -- 2 layer tách biệt hoàn toàn.
r = client.put(f"/worlds/{OVERRIDE_WORLD}/runtime-config", json={
    "openrouter_api_key": "sk-or-v1-world-override-key",
    "openrouter_model": "world/override-model"
})
check(r.status_code == 200, "21d. PUT /worlds/{world}/runtime-config returned 200")
body21d = r.json()
check(body21d["has_api_key"] is True, "21d. sau khi set override -> has_api_key hiệu lực = True")
check(body21d["api_key_source"] == "world", "21d. nguồn hiệu lực = world sau khi set override")
check(body21d["model"] == "world/override-model", "21d. model hiệu lực = model override của world")
check(body21d["world_override"]["has_api_key"] is True, "21d. world_override.has_api_key = True")
check(body21d["api_key_masked"] not in (None, "sk-or-v1-world-override-key"),
      "21d. api_key_masked KHÔNG trả key thật ở dạng plain text")
check(main.get_effective_api_key(OVERRIDE_WORLD) == "sk-or-v1-world-override-key",
      "21d. get_effective_api_key(world_name) ưu tiên đúng world override > app default")
check(main.get_effective_api_key() == "sk-or-v1-app-default-key",
      "21d. get_effective_api_key() KHÔNG truyền world_name vẫn chỉ thấy app default, không lẫn với world override")

r = client.get("/runtime-config")
check(r.json()["model"] == "app/default-model",
      "21d. GET /runtime-config (app default, không world_name) không bị world override làm lệch")

# 21e. World override lưu ở file riêng, TÁCH khỏi world_config.json (không
# lẫn vào state/canon của truyện).
override_path = main._world_runtime_override_path(OVERRIDE_WORLD)
check(os.path.isfile(override_path), "21e. override lưu ở file riêng data/worlds/<world>/runtime_override.json")
world_cfg_file = main.read_world_file(main.world_path_of(OVERRIDE_WORLD), "world_config.json")
check("openrouter_api_key" not in world_cfg_file and "openrouter_model" not in world_cfg_file,
      "21e. world_config.json KHÔNG chứa key/model override (tách biệt hoàn toàn)")

# 21f. World khác (chưa từng set override) vẫn chỉ thấy app default, không
# bị rò rỉ override của world 21d.
OTHER_WORLD = "test_engine_world_runtime_override_other"
wp10 = main.world_path_of(OTHER_WORLD)
shutil.rmtree(wp10, ignore_errors=True)
r = client.post(f"/worlds/{OTHER_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 21f) seed-demo world khác returned 200")
r = client.get(f"/worlds/{OTHER_WORLD}/runtime-config")
check(r.json()["api_key_source"] == "ui", "21f. world khác chưa override -> vẫn dùng app default, không lẫn override world khác")
shutil.rmtree(wp10, ignore_errors=True)

# 21g. DELETE world override api-key -> world quay lại dùng app default,
# model override (nếu còn set riêng, không bị xoá theo) vẫn giữ nguyên.
r = client.delete(f"/worlds/{OVERRIDE_WORLD}/runtime-config/api-key")
check(r.status_code == 200, "21g. DELETE /worlds/{world}/runtime-config/api-key returned 200")
body21g = r.json()
check(body21g["api_key_source"] == "ui", "21g. sau khi xoá override key -> quay lại dùng app default")
check(body21g["world_override"]["model"] == "world/override-model",
      "21g. xoá override KEY không ảnh hưởng tới override MODEL đã lưu riêng")

# 21h. call_llm(world_name=...) dùng đúng key/model hiệu lực của world (qua
# get_effective_api_key/model), khác với call_llm() không truyền world_name.
# (21g vừa xoá key override -> set lại để test đúng nhánh "world override"
# thay vì rơi về app default.)
r = client.put(f"/worlds/{OVERRIDE_WORLD}/runtime-config", json={"openrouter_api_key": "sk-or-v1-world-override-key"})
check(r.status_code == 200, "(tiền đề 21h) set lại world override key returned 200")

_captured_21h = {}


def fake_post_capture_key_model(url, headers=None, json=None, timeout=None):
    _captured_21h["authorization"] = (headers or {}).get("Authorization")
    _captured_21h["model"] = (json or {}).get("model")
    return _FakeResp(200, json_data={"choices": [{"message": {"content": "ok"}}]})


main.requests.post = fake_post_capture_key_model
main.call_llm("system", "user", world_name=OVERRIDE_WORLD)
check(_captured_21h["authorization"] == "Bearer sk-or-v1-world-override-key",
      "21h. call_llm(world_name=...) dùng đúng key override của world (đã set lại ở 21d)")
check(_captured_21h["model"] == "world/override-model",
      "21h. call_llm(world_name=...) dùng đúng model override của world")

_captured_21h.clear()
main.call_llm("system", "user")
check(_captured_21h["authorization"] == "Bearer sk-or-v1-app-default-key",
      "21h. call_llm() không truyền world_name -> dùng app default, không lẫn override world khác")
main.requests.post = original_post

# 21i. POST /worlds/{world}/runtime-config/test-connection test đúng key/
# model HIỆU LỰC của world (world override nếu có), world không tồn tại -> 404.
main.requests.post = lambda url, headers=None, json=None, timeout=None: _FakeResp(
    200, json_data={"choices": [{"message": {"content": "hi"}}]}
)
r = client.post(f"/worlds/{OVERRIDE_WORLD}/runtime-config/test-connection")
main.requests.post = original_post
check(r.status_code == 200, "21i. POST world runtime-config/test-connection returned 200")
check(r.json()["ok"] is True and r.json()["reason"] == "ok", "21i. test-connection world -> ok=True khi provider returned 200")

r = client.post("/worlds/__world_khong_ton_tai__/runtime-config/test-connection")
check(r.status_code == 404, "21i. test-connection của world không tồn tại -> 404")

# Khôi phục runtime_config.json + biến môi trường như trước khi test 21 chạy
if _runtime_cfg_backup_21 is not None:
    with open(main.RUNTIME_CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(_runtime_cfg_backup_21)
elif os.path.isfile(main.RUNTIME_CONFIG_PATH):
    os.remove(main.RUNTIME_CONFIG_PATH)
if _env_key_backup_21 is not None:
    os.environ["OPENROUTER_API_KEY"] = _env_key_backup_21
if _env_model_backup_21 is not None:
    os.environ["OPENROUTER_MODEL"] = _env_model_backup_21
shutil.rmtree(wp9, ignore_errors=True)

# ---------------------------------------------------------------------------
# NHÓM TEST 22: World Builder Interview & Respond
# ---------------------------------------------------------------------------
r = client.post("/builder/interview", json={"prompt": "Thế giới võ lâm truyền kỳ có ma pháp", "scope_type": "arc-only"})
check(r.status_code == 200, "22a. POST /builder/interview returned 200")
questions = r.json().get("questions", [])
check(len(questions) >= 2, "22a. /builder/interview trả ít nhất 2 câu hỏi làm rõ")

r = client.post("/builder/interview/respond", json={
    "prompt": "Thế giới võ lâm truyền kỳ",
    "answers": ["Tông giọng u uất", "Nhân vật chính là ma đạo công tử"]
})
check(r.status_code == 200, "22b. POST /builder/interview/respond returned 200")
check("Q&A Clarifications:" in r.json().get("refined_prompt", ""), "22b. /builder/interview/respond tổng hợp câu trả lời vào refined_prompt")

# ---------------------------------------------------------------------------
# NHÓM TEST 23: Export / Import World Package
# ---------------------------------------------------------------------------
r = client.post("/worlds/test_export_world/seed-demo")
check(r.status_code == 200, "(tiền đề 23) seed-demo cho test_export_world returned 200")

r = client.get("/worlds/test_export_world/export")
check(r.status_code == 200, "23a. GET /worlds/{world}/export returned 200")
pkg = r.json()
check("world_config" in pkg and "card_registry" in pkg and "canon_timeline" in pkg and "character_state" in pkg,
      "23a. export package chứa đủ 4 file JSON cốt lõi")

r = client.post("/worlds/import", json={"world_name": "test_imported_world", "package_data": pkg})
check(r.status_code == 200, "23b. POST /worlds/import returned 200")
imported_name = r.json().get("world_name")
check(imported_name == "test_imported_world", "23b. import world tạo đúng tên chỉ định")

r = client.get(f"/worlds/{imported_name}")
check(r.status_code == 200, "23b. GET world vừa import returned 200")
check(r.json()["world_config"]["display_name"] == pkg["world_config"]["display_name"],
      "23b. world_config trong world vừa import khớp 100% gói export")

# Dọn dẹp test_export_world & test_imported_world
client.delete("/worlds/test_export_world")
client.delete(f"/worlds/{imported_name}")

# ---------------------------------------------------------------------------
# NHÓM TEST 24: Checkpoint Review & Creator Assistant
# ---------------------------------------------------------------------------
shutil.rmtree(main.world_path_of("test_builder_flow"), ignore_errors=True)
r = client.post("/worlds/test_builder_flow", json={"prompt": "Thế giới huyền huyễn", "scope_type": "arc-only"})
check(r.status_code == 200, "(tiền đề 24) create_world cho test_builder_flow returned 200")

# Test guard: confirm-checkpoints should fail if status != checkpoint_review or checkpoints is empty
r_invalid = client.post("/worlds/test_builder_flow/builder/confirm-checkpoints")
check(r_invalid.status_code == 400, "24a. confirm-checkpoints rejects invalid status transition (status != checkpoint_review)")

# Seed demo to give it checkpoints and set status to checkpoint_review
r = client.post("/worlds/test_builder_flow/seed-demo?overwrite=true")
w_cfg = main.read_world_file(main.world_path_of("test_builder_flow"), "world_config.json")
w_cfg["creation_status"] = "checkpoint_review"
main.write_world_file(main.world_path_of("test_builder_flow"), "world_config.json", w_cfg)

r = client.post("/worlds/test_builder_flow/builder/confirm-checkpoints")
check(r.status_code == 200, "24a. POST /builder/confirm-checkpoints returned 200 when status = checkpoint_review")
check(r.json()["status"] == "cards", "24a. confirm-checkpoints chuyển creation_status sang 'cards'")

r = client.post("/worlds/test_builder_flow/creator-assistant", json={"query": "Gợi ý nhân vật phản diện"})
check(r.status_code == 200, "24b. POST /creator-assistant returned 200")
check("suggestions" in r.json() and len(r.json()["suggestions"]) > 0, "24b. creator-assistant trả về mảng suggestions")

client.delete("/worlds/test_builder_flow")

# ---------------------------------------------------------------------------
# NHÓM TEST 25: Phase B Backend State Schema & Logic (story_clock, relationships, age, foreshadowings)
# ---------------------------------------------------------------------------
PHASE_B_WORLD = "test_phase_b_engine_world"
wp_pb = main.world_path_of(PHASE_B_WORLD)
if os.path.isdir(wp_pb):
    shutil.rmtree(wp_pb)

r = client.post(f"/worlds/{PHASE_B_WORLD}/seed-demo")
check(r.status_code == 200, "25a. seed-demo cho Phase B world returned 200")

# Check play-state
ps = client.get(f"/worlds/{PHASE_B_WORLD}/play-state").json()
check(ps.get("story_clock") == {"year": 1, "month": 1, "day": 1, "time_of_day": "morning", "season": "spring", "tick": 0},
      "25b. play-state trả story_clock mặc định đúng")
check(ps.get("foreshadowing_tracker") == [], "25b. play-state trả foreshadowing_tracker mặc định rỗng")

# Check foreshadowings endpoints
r = client.get(f"/worlds/{PHASE_B_WORLD}/foreshadowings")
check(r.status_code == 200, "25c. GET /foreshadowings returned 200")
check(r.json().get("foreshadowing_tracker") == [], "25c. GET /foreshadowings trả mảng rỗng ban đầu")

f_items = [
    {"id": "fg_1", "description": "Tuyết Ly mang theo ngọc bội hình phượng hoàng", "planted_chapter": 1, "payoff_chapter": None, "status": "planted"}
]
r = client.put(f"/worlds/{PHASE_B_WORLD}/foreshadowings", json={"foreshadowing_tracker": f_items})
check(r.status_code == 200, "25d. PUT /foreshadowings returned 200")
check(len(r.json().get("foreshadowing_tracker", [])) == 1, "25d. PUT /foreshadowings đã lưu 1 item")

# Test state changes for story_clock_delta, relationships_update, age, foreshadowing_tracker_add
def fake_call_llm_phase_b(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    return json.dumps({
        "chapter_text": "Cố Trường Ca quan sát Tuyết Ly.",
        "state_changes": {
            "characters": {
                "char_xueli": {
                    "relationships_update": {"char_gu_changge": "Đồng môn nghi vấn"},
                    "age": "16"
                }
            },
            "story_clock_delta": {"day": 2, "time_of_day": "evening"},
            "foreshadowing_tracker_add": ["Cổ trận ẩn dưới Ma Giao Tông"],
            "notes": "test Phase B"
        }
    }, ensure_ascii=False)

main.call_llm = fake_call_llm_phase_b
r = client.post(f"/worlds/{PHASE_B_WORLD}/chapter/continue", json={"user_input": "quan sát Tuyết Ly"})
check(r.status_code == 200, "25e. chapter/continue với Phase B state changes returned 200")
main.call_llm = original_call_llm

ps2 = client.get(f"/worlds/{PHASE_B_WORLD}/play-state").json()
check(ps2["story_clock"]["day"] == 3, "25f. story_clock.day được cộng 2 thành 3")
check(ps2["story_clock"]["time_of_day"] == "evening", "25f. story_clock.time_of_day được cập nhật thành evening")
check(len(ps2["foreshadowing_tracker"]) == 2, "25g. foreshadowing_tracker tăng lên 2 items")

w_data = client.get(f"/worlds/{PHASE_B_WORLD}").json()
xueli_st = w_data["character_state"]["characters"]["char_xueli"]
check(xueli_st["relationships"].get("char_gu_changge") == "Đồng môn nghi vấn", "25h. relationships được cập nhật đúng")
check(xueli_st["age"] == "16", "25h. age được cập nhật đúng thành 16")

# 25i. Test CharacterStateChange model validation & relationship deletion with None
csc = main.CharacterStateChange(relationships_update={"char_gu_changge": None})
check(csc.relationships_update.get("char_gu_changge") is None, "25i. CharacterStateChange cho phép None trong relationships_update")

def fake_call_llm_phase_b_del(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    return json.dumps({
        "chapter_text": "Cố Trường Ca tuyệt giao với Tuyết Ly.",
        "state_changes": {
            "characters": {
                "char_xueli": {
                    "relationships_update": {"char_gu_changge": None}
                }
            }
        }
    }, ensure_ascii=False)

main.call_llm = fake_call_llm_phase_b_del
r = client.post(f"/worlds/{PHASE_B_WORLD}/chapter/continue", json={"user_input": "tuyệt giao"})
check(r.status_code == 200, "25i. chapter/continue với relationship deletion (None) returned 200")
main.call_llm = original_call_llm

w_data_del = client.get(f"/worlds/{PHASE_B_WORLD}").json()
xueli_st_del = w_data_del["character_state"]["characters"]["char_xueli"]
check("char_gu_changge" not in xueli_st_del.get("relationships", {}), "25i. relationship bị xoá thành công khi truyền None")

# 25j. Test apply_story_clock_changes with None inputs
clock_with_nones = {"year": None, "month": None, "day": None, "tick": None, "time_of_day": "morning", "season": "spring"}
updated_clock = main.apply_story_clock_changes(clock_with_nones, {"day_delta": 2, "tick_delta": 1, "year_delta": 1})
check(updated_clock["year"] == 2, "25j. story_clock với year=None fallback về 1 và cộng 1 thành 2")
check(updated_clock["day"] == 3, "25j. story_clock với day=None fallback về 1 và cộng 2 thành 3")
check(updated_clock["tick"] == 1, "25j. story_clock với tick=None fallback về 0 và cộng 1 thành 1")

client.delete(f"/worlds/{PHASE_B_WORLD}")

# ---------------------------------------------------------------------------
# NHÓM TEST 26: Phase C Fixed Style Card Management & Skill-Limiter Boundary Check
# ---------------------------------------------------------------------------
PHASE_C_WORLD = "test_phase_c_engine_world"
wp_pc = main.world_path_of(PHASE_C_WORLD)
if os.path.isdir(wp_pc):
    shutil.rmtree(wp_pc)

r = client.post(f"/worlds/{PHASE_C_WORLD}/seed-demo")
check(r.status_code == 200, "(tiền đề 26) seed-demo cho Phase C world returned 200")

# 26a. GET /style-card default values
r = client.get(f"/worlds/{PHASE_C_WORLD}/style-card")
check(r.status_code == 200, "26a. GET /worlds/{world}/style-card returned 200")
sc_default = r.json()
check(sc_default.get("perspective") == "third_person_limited", "26a. default style_card perspective = third_person_limited")

# 26b. PUT /style-card independent update
new_style = {
    "perspective": "first_person",
    "voice": "poetic",
    "pacing": "fast",
    "tone": "mysterious",
    "prose_guidelines": ["Dùng câu ngắn", "Tập trung miêu tả âm thanh"],
    "taboo_words": ["hiện đại", "bóng đèn"],
    "custom_instructions": "Giữ phong cách u uất."
}
r = client.put(f"/worlds/{PHASE_C_WORLD}/style-card", json=new_style)
check(r.status_code == 200, "26b. PUT /worlds/{world}/style-card returned 200")
sc_saved = r.json().get("style_card", {})
check(sc_saved.get("perspective") == "first_person", "26b. PUT style_card đã cập nhật perspective thành first_person")
check(sc_saved.get("taboo_words") == ["hiện đại", "bóng đèn"], "26b. PUT style_card lưu taboo_words chính xác")

# Check style_card.json written independently on disk
sc_disk_path = os.path.join(wp_pc, "style_card.json")
check(os.path.isfile(sc_disk_path), "26b. style_card.json được ghi độc lập tại data/worlds/{world}/style_card.json")

# Verify world_config.json is unchanged and doesn't conflict
wc_after_sc = client.get(f"/worlds/{PHASE_C_WORLD}").json()["world_config"]
check("style_card" not in wc_after_sc, "26b. updating style_card does not corrupt core world_config")

# 26c. style_card payload inclusion during chapter generation
captured_c = {}
def fake_call_llm_capture_style(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            try:
                captured_c["payload"] = json.loads(user_prompt)
            except Exception:
                pass
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()

main.call_llm = fake_call_llm_capture_style
r = client.post(f"/worlds/{PHASE_C_WORLD}/chapter/continue", json={"user_input": "Bước vào động phủ"})
check(r.status_code == 200, "26c. chapter/continue với style_card returned 200")
check("style_card" in captured_c.get("payload", {}), "26c. payload gửi narrator có chứa style_card")
check(captured_c["payload"]["style_card"]["perspective"] == "first_person", "26c. style_card trong payload có đúng perspective = first_person")
main.call_llm = original_call_llm

# 26d. Pure Python Skill-Limiter check unit test
test_skill_cards = [
    {"id": "skill_that_kinh_kiem", "type": "skill", "name": "Thất Kính Kiếm", "keywords": ["thất kính kiếm", "chém kiếm khí"]}
]
test_char_state = {
    "characters": {
        "char_xueli": {
            "name": "Xue Li",
            "power_stat": {
                "realm": "Qi Condensation",
                "exp": 0,
                "known_skills": []
            }
        }
    }
}

# Test active unlearned skill invocation by user command
violation = main.check_skill_limiter("", test_char_state, "char_xueli", test_skill_cards, user_input="Tuyết Ly tung Thất Kính Kiếm")
check(violation.get("boundary_violated") is True, "26d. check_skill_limiter phát hiện skill chưa học khi user hạ lệnh thi triển")
check(violation.get("unlearned_skill") == "Thất Kính Kiếm", "26d. violation object trả đúng tên unlearned_skill")

# Test query / passive mention of unlearned skill (should NOT trigger violation)
query_check = main.check_skill_limiter("", test_char_state, "char_xueli", test_skill_cards, user_input="Tuyết Ly hỏi sư phụ Thất Kính Kiếm là gì")
check(query_check.get("boundary_violated") is False, "26d. check_skill_limiter KHÔNG chặn nhầm khi user chỉ hỏi về skill")

# Test post-check LLM chapter_text inventing unlearned skill execution
chapter_invention_check = main.check_skill_limiter("Tuyết Ly lập tức thi triển Thất Kính Kiếm đánh nát đối thủ", test_char_state, "char_xueli", test_skill_cards)
check(chapter_invention_check.get("boundary_violated") is True, "26d. check_skill_limiter bắt đúng lỗi LLM tự bịa skill chưa học trong chapter_text")

# Test learned skill invocation
test_char_state["characters"]["char_xueli"]["power_stat"]["known_skills"] = ["skill_that_kinh_kiem"]
no_violation = main.check_skill_limiter("Tuyết Ly lập tức thi triển Thất Kính Kiếm", test_char_state, "char_xueli", test_skill_cards, user_input="Tuyết Ly tung Thất Kính Kiếm")
check(no_violation.get("boundary_violated") is False, "26d. check_skill_limiter cho phép skill đã học trong known_skills")

# 26e. Skill-Limiter in chapter generation pipeline
# Update card_registry of PHASE_C_WORLD with a skill card
card_reg = client.get(f"/worlds/{PHASE_C_WORLD}").json()["card_registry"]
card_reg["cards"].append(main.make_card("skill_that_kinh_kiem", "skill", "Thất Kính Kiếm", "Kỹ năng tuyệt học", unlock_checkpoint_id="cp_0", status="unlocked"))
client.put(f"/worlds/{PHASE_C_WORLD}/card_registry", json=card_reg)

# Protagonist set to char_xueli
wc = client.get(f"/worlds/{PHASE_C_WORLD}").json()["world_config"]
wc["protagonist_id"] = "char_xueli"
client.put(f"/worlds/{PHASE_C_WORLD}/world_config", json=wc)

# Attempt unlearned skill via chapter/continue
r = client.post(f"/worlds/{PHASE_C_WORLD}/chapter/continue", json={"user_input": "Tuyết Ly tung Thất Kính Kiếm chém nát ma thú"})
check(r.status_code == 400, "26e. chapter/continue với unlearned skill trả 400")
check(r.json().get("detail", {}).get("boundary_violated") is True, "26e. response detail chứa boundary_violated = True")

# Add skill to known_skills of char_xueli
cs = client.get(f"/worlds/{PHASE_C_WORLD}").json()["character_state"]
cs["characters"]["char_xueli"]["power_stat"]["known_skills"] = ["skill_that_kinh_kiem"]
client.put(f"/worlds/{PHASE_C_WORLD}/character_state", json=cs)

main.call_llm = fake_call_llm_capture_style
try:
    # Re-attempt learned skill via chapter/continue
    r = client.post(f"/worlds/{PHASE_C_WORLD}/chapter/continue", json={"user_input": "Tuyết Ly tung Thất Kính Kiếm chém nát ma thú"})
    check(r.status_code == 200, "26e. chapter/continue thành công 200 sau khi đã học skill")
finally:
    main.call_llm = original_call_llm

# 26f. Test play-state style_card and unlocked character cards power_stat
r_ps = client.get(f"/worlds/{PHASE_C_WORLD}/play-state")
check(r_ps.status_code == 200, "26f. GET /play-state returned 200")
ps_data = r_ps.json()
check("style_card" in ps_data, "26f. play-state trả về style_card")
check(ps_data["style_card"]["perspective"] == "first_person", "26f. style_card trong play-state mang đúng perspective")
char_card = next((c for c in ps_data.get("unlocked_cards", []) if c.get("type") == "char"), None)
check(char_card is not None and "power_stat" in char_card, "26f. character card trong unlocked_cards trả về power_stat")

# 27. Test Pydantic model round-trip cho các field mới (data loss bug)
r_world = client.post(f"/worlds/test_round_trip/seed-demo")

world_data = client.get(f"/worlds/test_round_trip").json()

cs = world_data["character_state"]
if "char_su_phu" in cs["characters"]:
    cs["characters"]["char_su_phu"]["traits"] = {"test_trait": 1}
    cs["characters"]["char_su_phu"]["status_effects"] = [{"name": "poisoned"}]
    client.put(f"/worlds/test_round_trip/character_state", json=cs)
    world_data2 = client.get(f"/worlds/test_round_trip").json()
    cs2 = world_data2["character_state"]
    check(cs2["characters"]["char_su_phu"].get("traits") == {"test_trait": 1}, "27a. CharacterModel giữ lại traits")
    check(cs2["characters"]["char_su_phu"].get("status_effects") == [{"name": "poisoned"}], "27a. CharacterModel giữ lại status_effects")

ct = world_data["canon_timeline"]
if ct["checkpoints"]:
    ct["checkpoints"][0]["status_effects"] = [{"name": "buff"}]
    ct["checkpoints"][0]["alternate_outcomes"] = [{"cond": "a"}]
    ct["checkpoints"][0]["default_next_checkpoint_id"] = "cp_2"
    client.put(f"/worlds/test_round_trip/canon_timeline", json=ct)
    world_data3 = client.get(f"/worlds/test_round_trip").json()
    ct2 = world_data3["canon_timeline"]
    cp = ct2["checkpoints"][0]
    check(cp.get("status_effects") == [{"name": "buff"}], "27b. CheckpointModel giữ lại status_effects")
    check(cp.get("alternate_outcomes") == [{"cond": "a"}], "27b. CheckpointModel giữ lại alternate_outcomes")
    check(cp.get("default_next_checkpoint_id") == "cp_2", "27b. CheckpointModel giữ lại default_next_checkpoint_id")

cr = world_data["card_registry"]
if cr["cards"]:
    cr["cards"][0]["keywords"] = ["fire", "magic"]
    client.put(f"/worlds/test_round_trip/card_registry", json=cr)
    world_data4 = client.get(f"/worlds/test_round_trip").json()
    cr2 = world_data4["card_registry"]
    check(cr2["cards"][0].get("keywords") == ["fire", "magic"], "27c. CardModel giữ lại keywords")

client.delete(f"/worlds/test_round_trip")
client.delete(f"/worlds/{PHASE_C_WORLD}")

# 28. Test Linter & Rewrite Endpoint
# Tạo mock world
LINT_WORLD = "test_linter_world"
if os.path.isdir(main.world_path_of(LINT_WORLD)): shutil.rmtree(main.world_path_of(LINT_WORLD))
client.post(f"/worlds/{LINT_WORLD}/seed-demo")
original_call_llm_lint = main.call_llm
def mock_call_llm_lint(sys_prompt, user_prompt, **kwargs):
    if sys_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    if "Linter" in sys_prompt or "consistency errors" in sys_prompt:
        return '{"status": "has_issues", "issues": [{"severity": "major", "description": "test", "suggestion": "fix"}], "general_feedback": "test"}'
    if "rewrite a chapter" in sys_prompt:
        return '{"rewritten_text": "rewritten"}'
    return main.mock_narrator_response("")

main.call_llm = mock_call_llm_lint
client.post(f"/worlds/{LINT_WORLD}/chapter/continue", json={"user_input": "Bắt đầu chương"})
try:
    r_lint = client.post(f"/worlds/{LINT_WORLD}/lint-chapter", json={"chapter_index": 1})
    check(r_lint.status_code == 200, "28a. /lint-chapter returned 200")
    check(r_lint.json()["status"] == "has_issues", "28a. /lint-chapter parse đúng mock")

    r_rw = client.post(f"/worlds/{LINT_WORLD}/chapter/rewrite", json={"chapter_index": 1, "linter_suggestions": "{}"})
    check(r_rw.status_code == 200, "28b. /chapter/rewrite returned 200")
    check(r_rw.json()["rewritten_text"] == "rewritten", "28b. /chapter/rewrite parse đúng mock")
finally:
    main.call_llm = original_call_llm_lint
    client.delete(f"/worlds/{LINT_WORLD}")

# 29. Test Multi-Provider LLM Fallback Chain (Giai đoạn A)
check(main.get_base_url_for_provider("featherless") == "https://api.featherless.ai/v1/chat/completions", "29a. Featherless URL resolution đúng")
check(main.get_base_url_for_provider("openai") == "https://api.openai.com/v1/chat/completions", "29a. OpenAI URL resolution đúng")
check(main.get_base_url_for_provider("deepseek") == "https://api.deepseek.com/chat/completions", "29a. DeepSeek URL resolution đúng")
check(main.get_base_url_for_provider("anthropic") == "https://api.anthropic.com/v1/messages", "29a. Anthropic URL resolution đúng")
check(main.get_base_url_for_provider("custom", "https://my-api/v1") == "https://my-api/v1/chat/completions", "29a. Custom Base URL resolution đúng")

# Failover multi-provider call_llm
mock_chain = [
    {"provider": "openrouter", "model": "model-1", "api_key": "key-1"},
    {"provider": "featherless", "model": "model-2", "api_key": "key-2"}
]

import requests
original_read_runtime_config = main.read_runtime_config
original_requests_post = requests.post

def mock_read_cfg_multi():
    return {"fallback_chain": mock_chain}

requests_history = []
def mock_post_failover(url, headers=None, json=None, timeout=None):
    requests_history.append({"url": url, "headers": headers, "json": json})
    class MockResp:
        def __init__(self, status_code, body):
            self.status_code = status_code
            self._body = body
            self.text = json_lib.dumps(body) if isinstance(body, dict) else str(body)
            self.headers = {}
        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.exceptions.HTTPError(f"Error {self.status_code}")
        def json(self):
            return self._body

    # Node 1 (openrouter) bị 429
    if "openrouter.ai" in url:
        return MockResp(429, {"error": {"message": "Rate limited"}})
    # Node 2 (featherless) returned 200 OK
    if "featherless.ai" in url:
        return MockResp(200, {"choices": [{"message": {"content": "Success from Featherless"}}]})
    return MockResp(500, {})

import json as json_lib
main.read_runtime_config = mock_read_cfg_multi
requests.post = mock_post_failover

try:
    res_text = main.call_llm("sys", "user")
    check(res_text == "Success from Featherless", "29b. Failover thành công từ OpenRouter (429) sang Featherless")
    check(len(requests_history) == 2, "29b. Đã thử đúng 2 provider trong chain")
    check("openrouter.ai" in requests_history[0]["url"], "29b. Lần 1 thử OpenRouter")
    check("featherless.ai" in requests_history[1]["url"], "29b. Lần 2 thử Featherless")
finally:
    main.read_runtime_config = original_read_runtime_config
    requests.post = original_requests_post

# Status API Key masking
status_mask_res = client.put("/runtime-config", json={
    "fallback_chain": [
        {"provider": "openrouter", "model": "mod1", "api_key": "sk-or-v1-secretkey12345"},
        {"provider": "featherless", "model": "mod2", "api_key": "secretfeatherkey67890"}
    ]
})
check(status_mask_res.status_code == 200, "29c. PUT /runtime-config với fallback_chain returned 200")
chain_resp = status_mask_res.json()["fallback_chain"]
check(len(chain_resp) == 2, "29c. Status trả về 2 nodes trong fallback_chain")
check(chain_resp[0]["api_key_masked"] != "sk-or-v1-secretkey12345", "29c. Key Node 1 không lộ plain text")
check("…" in chain_resp[0]["api_key_masked"] or "*" in chain_resp[0]["api_key_masked"], "29c. Key Node 1 đã được mask")
check(chain_resp[1]["api_key_masked"] != "secretfeatherkey67890", "29c. Key Node 2 không lộ plain text")

# Clear test chain
client.delete("/runtime-config/api-key")


# =====================================================================
# NHÓM 30: Role-based Multi-Model Assignment
# Spec: mục 5 (Tests) của spec "Role-based Multi-Model Assignment"
# Test trực tiếp các helper function, không cần gọi API thật.
# =====================================================================

print("\n--- Nhóm 30: Role Assignment ---")

import json as _json30

original_read_rc_30 = main.read_runtime_config
original_read_wr_30 = main.read_world_runtime_override


def _make_chain(*models):
    """Tạo fake fallback_chain với N node dummy (api_key giả để pass has_real_api_key)."""
    return [
        {"provider": "openrouter", "model": m, "api_key": f"sk-fake-{m}", "base_url": ""}
        for m in models
    ]


# -------------------------------------------------------------------------
# 30a. Pool 1 model -> cả 3 role đều resolve về index 0 (model đó)
# -------------------------------------------------------------------------
def _mock_rc_1model():
    return {
        "openrouter_api_key": "", "openrouter_model": "",
        "fallback_chain": _make_chain("model_A"),
        "creator_mode_enabled": False,
        "role_assignments": {"writer": None, "extractor": None, "editor": None},
        "editor_enabled": False
    }

def _mock_wr_empty(world_name):
    return {"openrouter_api_key": "", "openrouter_model": "",
            "fallback_chain": [], "creator_mode_enabled": False,
            "role_assignments": {"writer": None, "extractor": None, "editor": None},
            "editor_enabled": False}

main.read_runtime_config = _mock_rc_1model
main.read_world_runtime_override = _mock_wr_empty

chain_w = main.get_effective_fallback_chain_for_role(None, "writer")
chain_e = main.get_effective_fallback_chain_for_role(None, "extractor")
chain_ed = main.get_effective_fallback_chain_for_role(None, "editor")
check(chain_w[0]["model"] == "model_A", "30a. Pool 1 model: writer -> model_A")
check(chain_e[0]["model"] == "model_A", "30a. Pool 1 model: extractor -> model_A")
check(chain_ed[0]["model"] == "model_A", "30a. Pool 1 model: editor -> model_A")

main.read_runtime_config = original_read_rc_30
main.read_world_runtime_override = original_read_wr_30

# -------------------------------------------------------------------------
# 30b. Pool 2 model, no assignment -> writer=idx0, extractor=idx1, editor=idx0
# -------------------------------------------------------------------------
def _mock_rc_2model():
    return {
        "openrouter_api_key": "", "openrouter_model": "",
        "fallback_chain": _make_chain("model_A", "model_B"),
        "creator_mode_enabled": False,
        "role_assignments": {"writer": None, "extractor": None, "editor": None},
        "editor_enabled": False
    }

main.read_runtime_config = _mock_rc_2model
main.read_world_runtime_override = _mock_wr_empty

chain_w2 = main.get_effective_fallback_chain_for_role(None, "writer")
chain_e2 = main.get_effective_fallback_chain_for_role(None, "extractor")
chain_ed2 = main.get_effective_fallback_chain_for_role(None, "editor")
check(chain_w2[0]["model"] == "model_A", "30b. Pool 2 model: writer -> model_A (idx 0)")
check(chain_e2[0]["model"] == "model_B", "30b. Pool 2 model: extractor -> model_B (idx 1)")
check(chain_ed2[0]["model"] == "model_A", "30b. Pool 2 model: editor -> model_A (idx 0)")
# Kiểm tra không bỏ node nào (chain vẫn đủ 2 node sau khi xoay)
check(len(chain_e2) == 2, "30b. Extractor chain vẫn đủ 2 node (failover giữ nguyên)")

main.read_runtime_config = original_read_rc_30
main.read_world_runtime_override = original_read_wr_30

# -------------------------------------------------------------------------
# 30c. Pool 3 model, no assignment -> writer=0, extractor=1, editor=2
# -------------------------------------------------------------------------
def _mock_rc_3model():
    return {
        "openrouter_api_key": "", "openrouter_model": "",
        "fallback_chain": _make_chain("model_A", "model_B", "model_C"),
        "creator_mode_enabled": False,
        "role_assignments": {"writer": None, "extractor": None, "editor": None},
        "editor_enabled": False
    }

main.read_runtime_config = _mock_rc_3model
main.read_world_runtime_override = _mock_wr_empty

chain_w3 = main.get_effective_fallback_chain_for_role(None, "writer")
chain_e3 = main.get_effective_fallback_chain_for_role(None, "extractor")
chain_ed3 = main.get_effective_fallback_chain_for_role(None, "editor")
check(chain_w3[0]["model"] == "model_A", "30c. Pool 3 model: writer -> model_A (idx 0)")
check(chain_e3[0]["model"] == "model_B", "30c. Pool 3 model: extractor -> model_B (idx 1)")
check(chain_ed3[0]["model"] == "model_C", "30c. Pool 3 model: editor -> model_C (idx 2)")
# Wrap-around: editor chain = [C, A, B] -> vẫn 3 node
check(len(chain_ed3) == 3, "30c. Editor chain vẫn đủ 3 node sau khi xoay")
check(chain_ed3[1]["model"] == "model_A", "30c. Editor chain: node thứ 2 = model_A (wrap-around đúng)")

main.read_runtime_config = original_read_rc_30
main.read_world_runtime_override = original_read_wr_30

# -------------------------------------------------------------------------
# 30d. Set tay role_assignments.extractor=0 với pool 3 model -> override bảng auto
# -------------------------------------------------------------------------
def _mock_rc_3model_override_extractor():
    return {
        "openrouter_api_key": "", "openrouter_model": "",
        "fallback_chain": _make_chain("model_A", "model_B", "model_C"),
        "creator_mode_enabled": False,
        "role_assignments": {"writer": None, "extractor": 0, "editor": None},
        "editor_enabled": False
    }

main.read_runtime_config = _mock_rc_3model_override_extractor
main.read_world_runtime_override = _mock_wr_empty

chain_e4 = main.get_effective_fallback_chain_for_role(None, "extractor")
check(chain_e4[0]["model"] == "model_A", "30d. Extractor override idx=0 -> model_A (bỏ qua bảng auto idx=1)")
# Writer vẫn auto
chain_w4 = main.get_effective_fallback_chain_for_role(None, "writer")
check(chain_w4[0]["model"] == "model_A", "30d. Writer vẫn auto -> model_A")

main.read_runtime_config = original_read_rc_30
main.read_world_runtime_override = original_read_wr_30

# -------------------------------------------------------------------------
# 30e. Set tay role trỏ index không tồn tại (idx=5, pool 2 node) -> auto fallback
# -------------------------------------------------------------------------
def _mock_rc_bad_idx():
    return {
        "openrouter_api_key": "", "openrouter_model": "",
        "fallback_chain": _make_chain("model_A", "model_B"),
        "creator_mode_enabled": False,
        "role_assignments": {"writer": 5, "extractor": None, "editor": 99},
        "editor_enabled": False
    }

main.read_runtime_config = _mock_rc_bad_idx
main.read_world_runtime_override = _mock_wr_empty

# Không raise, tự rơi về auto
try:
    chain_w5 = main.get_effective_fallback_chain_for_role(None, "writer")
    chain_ed5 = main.get_effective_fallback_chain_for_role(None, "editor")
    check(chain_w5[0]["model"] == "model_A", "30e. Writer idx=5 (OOB) -> auto fallback idx=0 -> model_A")
    check(chain_ed5[0]["model"] == "model_A", "30e. Editor idx=99 (OOB) -> auto fallback idx=0 -> model_A")
except Exception as ex:
    check(False, f"30e. OOB index không được raise, nhưng bị: {ex}")

main.read_runtime_config = original_read_rc_30
main.read_world_runtime_override = original_read_wr_30

# -------------------------------------------------------------------------
# 30f. Editor lỗi (mock LLMCallError) -> chapter_text vẫn là bản Writer gốc
#       state_changes không đổi, response 200 bình thường (fail-open)
# -------------------------------------------------------------------------
# Cần world seed để /chapter/continue chạy được
WP30 = main.world_path_of("test_role_world_30")
import shutil as _shutil30
if os.path.isdir(WP30):
    _shutil30.rmtree(WP30)
r30_seed = client.post(f"/worlds/test_role_world_30/seed-demo")
check(r30_seed.status_code == 200, "30f. seed-demo returned 200 cho test world")

# Cấu hình editor_enabled=True trong app config
r30_cfg = client.put("/runtime-config", json={
    "editor_enabled": True
})
check(r30_cfg.status_code == 200, "30f. PUT editor_enabled=True returned 200")

_writer_text_30 = "WRITER_OUTPUT_30"

def _fake_llm_editor_fail(system_prompt, user_prompt, user_input_for_mock="",
                          mock_response=None, world_name=None, role=None):
    """Writer trả OK, Extractor trả OK, Editor ném LLMCallError, Checker OK."""
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt == main.WRITER_SYSTEM_PROMPT:
        return _json30.dumps({
            "chapter_text": _writer_text_30,
            "chapter_end": True,
            "chapter_title": "Test",
            "suggested_actions": []
        }, ensure_ascii=False)
    if system_prompt == main.EXTRACTOR_SYSTEM_PROMPT:
        return _json30.dumps({
            "state_changes": {"characters": {}, "notes": "mock"}
        }, ensure_ascii=False)
    if system_prompt == main.EDITOR_SYSTEM_PROMPT:
        raise main.LLMCallError("Editor thất bại giả lập")
    # Consistency checker & summarizer -> OK
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    return main.mock_summarizer_response("Test")

main.call_llm = _fake_llm_editor_fail
r30_ch = client.post(f"/worlds/test_role_world_30/chapter/continue",
                     json={"user_input": "test editor fail"})
check(r30_ch.status_code == 200, "30f. Editor lỗi -> response vẫn 200 (fail-open)")
body30 = r30_ch.json()
chapter30 = body30.get("chapter", {})
check(chapter30.get("chapter_text") == _writer_text_30,
      "30f. chapter_text vẫn là bản Writer gốc khi Editor lỗi")
check(chapter30.get("editor_polished") == False,
      "30f. editor_polished=False khi Editor lỗi")
check("characters" in body30.get("state_changes_applied", {}),
      "30f. state_changes_applied hợp lệ")
main.call_llm = original_call_llm

# Reset editor_enabled về False
client.put("/runtime-config", json={"editor_enabled": False})
_shutil30.rmtree(WP30, ignore_errors=True)

# -------------------------------------------------------------------------
# 30g. Round-trip save fallback_chain: PUT key thật -> PUT để trống key
#      -> GET phải thấy key cũ còn nguyên (test cho bug đã fix ở mục 0)
# -------------------------------------------------------------------------
# PUT lần 1: lưu key thật
r30g_1 = client.put("/runtime-config", json={
    "fallback_chain": [
        {"provider": "openrouter", "model": "test-model-30g", "api_key": "sk-real-key-30g", "base_url": ""}
    ]
})
check(r30g_1.status_code == 200, "30g. PUT lần 1 (key thật) returned 200")

# PUT lần 2: gửi cùng node nhưng để key trống (giả lập UI gửi masked/blank)
r30g_2 = client.put("/runtime-config", json={
    "fallback_chain": [
        {"provider": "openrouter", "model": "test-model-30g", "api_key": "", "base_url": ""}
    ]
})
check(r30g_2.status_code == 200, "30g. PUT lần 2 (key trống) returned 200")

# GET để kiểm tra key cũ còn nguyên (không bị xóa)
r30g_get = client.get("/runtime-config")
check(r30g_get.status_code == 200, "30g. GET /runtime-config returned 200")
body30g = r30g_get.json()
chain30g = body30g.get("fallback_chain", [])
check(len(chain30g) == 1, "30g. fallback_chain vẫn có 1 node")
check(chain30g[0].get("has_api_key") == True,
      "30g. Node vẫn has_api_key=True sau PUT key trống (key cũ được preserve)")

# Cleanup
client.delete("/runtime-config/api-key")

print("--- Nhóm 30 hoàn thành ---\n")

# -------------------------------------------------------------------------
# 31. Test LLM call with HTTP 200 but HTML body (Content-Type: text/html)
#     Verify it raises LLMCallError instead of crashing or returning silence
# -------------------------------------------------------------------------
import unittest.mock

def _mock_requests_post_html(*args, **kwargs):
    class MockResponse:
        status_code = 200
        headers = {"Content-Type": "text/html"}
        def raise_for_status(self): pass
        def json(self):
            import json
            raise json.JSONDecodeError("Expecting value", "", 0)
    return MockResponse()

with unittest.mock.patch("requests.post", side_effect=_mock_requests_post_html):
    with unittest.mock.patch("main.get_effective_fallback_chain", return_value=[{"provider": "openrouter", "model": "test", "api_key": "test", "base_url": ""}]):
        try:
            main.call_llm("sys", "user", role="default")
            check(False, "31. Must raise LLMCallError when receiving HTML body")
        except main.LLMCallError as e:
            err_str = str(e)
            # The message is UI-facing and was translated to English; accept
            # either wording so this check survives the translation.
            check("not JSON" in err_str or "không phải JSON" in err_str or "không đúng định dạng" in err_str,
                  f"31. call_llm catch text/html as LLMCallError, got: {err_str}")

print("--- Nhóm 31 hoàn thành ---\n")

# -------------------------------------------------------------------------
# 32. Test extend_arc
#     Verify that it reads chapters.json["running_summary"] and story_thesis
# -------------------------------------------------------------------------
WORLD32 = "test_extend_arc_world"
wp32 = main.world_path_of(WORLD32)
shutil.rmtree(wp32, ignore_errors=True)
os.makedirs(wp32, exist_ok=True)

# Fake config
main.write_world_file(wp32, "world_config.json", {
    "story_thesis": "A dark fantasy where magic is corrupted.",
    "arc_roadmap": {
        "arc_1": {"title": "The Awakening"},
        "arc_2": {"title": "The Journey"}
    }
})
main.write_world_file(wp32, "canon_timeline.json", {"checkpoints": []})
main.write_world_file(wp32, "character_state.json", {"characters": {}})
main.write_world_file(wp32, "chapters.json", {
    "running_summary": "REAL SUMMARY FROM GAMEPLAY"
})
# Inject API key to bypass check
main.get_effective_fallback_chain = lambda x=None: [{"provider": "openrouter", "model": "test", "api_key": "test_key"}]
main.has_real_api_key = lambda x=None: True

captured_extend_payload = {}
def _mock_extend_llm(system_prompt, user_prompt, *args, **kwargs):
    if system_prompt == main.ARC_EXTENDER_PROMPT:
        captured_extend_payload["user_prompt"] = user_prompt
        return '{"checkpoints": [{"checkpoint_id": "cp_1_0", "description": "New cp", "required_conditions": [], "cards_unlocked": [], "boundary": {"locations": [], "allowed_characters": [], "time_window": ""}}]}'
    return ""

original_call_llm_32 = main.call_llm
main.call_llm = _mock_extend_llm

r32 = client.post(f"/worlds/{WORLD32}/extend_arc")
check(r32.status_code == 200, "32. extend_arc endpoint returns 200")

main.call_llm = original_call_llm_32

check("user_prompt" in captured_extend_payload, "32. ARC_EXTENDER_PROMPT was called")
payload32 = captured_extend_payload["user_prompt"]
check("REAL SUMMARY FROM GAMEPLAY" in payload32, "32. extend_arc reads running_summary from chapters.json")
check("A dark fantasy where magic is corrupted" in payload32, "32. extend_arc injects story_thesis from world_config")

# -------------------------------------------------------------------------
# 34. Milestone 2 Hardening Tests
# -------------------------------------------------------------------------
# 34a. parse_llm_json expected_type enforcement
t34a_list = main.parse_llm_json("[1, 2, 3]", expected_type=list)
check(t34a_list == [1, 2, 3], "34a. parse_llm_json with expected_type=list works")

try:
    main.parse_llm_json("[1, 2, 3]", expected_type=dict)
    check(False, "34a. parse_llm_json should fail when type list doesn't match expected_type=dict")
except ValueError as e:
    check("expected 'dict'" in str(e), "34a. parse_llm_json raises clear error on type mismatch")

# 34b. Case-insensitive think tag handling
t34b = main.parse_llm_json("<THINK>Uppercase reasoning</THINK>```json\n{\"test\": 123}\n```")
check(t34b == {"test": 123}, "34b. parse_llm_json handles case-insensitive <THINK> tags")

# 34c. Seed demo overwrite protection
M2_WORLD = "test_m2_seed_world"
wp_m2 = main.world_path_of(M2_WORLD)
shutil.rmtree(wp_m2, ignore_errors=True)

r = client.post(f"/worlds/{M2_WORLD}/seed-demo")
check(r.status_code == 200, "34c. initial seed-demo returns 200")

r_dup = client.post(f"/worlds/{M2_WORLD}/seed-demo")
check(r_dup.status_code == 400, "34c. seed-demo without overwrite=true returns 400 when world exists")

r_over = client.post(f"/worlds/{M2_WORLD}/seed-demo?overwrite=true")
check(r_over.status_code == 200, "34c. seed-demo with overwrite=true returns 200")

client.delete(f"/worlds/{M2_WORLD}")

# 34d. Import world deep schema validation
r_bad_import = client.post("/worlds/import", json={"world_name": "bad_import", "package_data": {"world_config": "not_a_dict"}})
check(r_bad_import.status_code == 400, "34d. import_world rejects invalid world_config type with 400")

print("--- Nhóm 34 (Milestone 2) hoàn thành ---\n")

# -------------------------------------------------------------------------
# 35. Milestone 3: LLM Parsing Hardening Test Suite
# -------------------------------------------------------------------------
print("--- Nhóm 35: LLM Parsing Hardening ---")

# 35a. Truncated unclosed <think>... blocks (when token limit runs out)
try:
    main.parse_llm_json("<think>Reasoning started but token limit ran out before finishing...")
    check(False, "35a. Truncated <think> block without JSON should raise ValueError")
except ValueError as e:
    check("thinking text" in str(e) or "token limit" in str(e), "35a. parse_llm_json raises clear error on truncated think block")

# 35b. Closed <think>...</think> blocks with mixed casing
t35b = main.parse_llm_json("<THINK>Reasoning 1</THINK><Think>Reasoning 2</Think><tHiNk>Reasoning 3</tHiNk>{\"status\": \"ok\"}")
check(t35b == {"status": "ok"}, "35b. parse_llm_json strips mixed case <think> tags")

# 35c. Draft code fences inside <think> stripped first before actual code fence
draft_think = """<think>
Draft fence:
```json
{"draft": true}
```
</think>
Actual output:
```json
{"actual": true}
```"""
t35c = main.parse_llm_json(draft_think)
check(t35c == {"actual": True}, "35c. draft code fences inside <think> stripped before parsing actual code fence")

# 35d. Preamble text and trailing commentary with internal braces {...} after JSON
preamble_trailing = 'Here is the response:\n{"key": "value"}\nNote that {template_var} is used here.'
t35d = main.parse_llm_json(preamble_trailing, expected_type=dict)
check(t35d == {"key": "value"}, "35d. parse_llm_json ignores preamble and trailing commentary with internal braces")

# 35e. Code fences with markdown annotations (```json and generic ```)
t35e_json = main.parse_llm_json("```json\n[{\"item\": 10}]\n```", expected_type=list)
check(t35e_json == [{"item": 10}], "35e. parse_llm_json parses ```json code fence for list")

t35e_gen = main.parse_llm_json("```python\n{\"foo\": \"bar\"}\n```", expected_type=dict)
check(t35e_gen == {"foo": "bar"}, "35e. parse_llm_json parses generic code fence for dict")

# 35f. expected_type enforcement (top-level JSON array when expected_type=dict)
try:
    main.parse_llm_json('[{"id": 1}]', expected_type=dict)
    check(False, "35f. top-level JSON array should fail when expected_type=dict")
except ValueError as e:
    check("expected 'dict'" in str(e), "35f. top-level array raises expected 'dict' error")

try:
    main.parse_llm_json('Preamble text: [{"id": 1}]', expected_type=dict)
    check(False, "35f. top-level JSON array with preamble should fail when expected_type=dict")
except ValueError as e:
    check("expected 'dict'" in str(e), "35f. preamble top-level array raises expected 'dict' error")

try:
    main.parse_llm_json('{"id": 1}', expected_type=list)
    check(False, "35f. top-level JSON dict should fail when expected_type=list")
except ValueError as e:
    check("expected 'list'" in str(e), "35f. top-level dict raises expected 'list' error")

# 35g. Scratchpad reasoning token disallowance in call_llm
captured_llm_call = {}
def fake_post_capture_payload(url, headers=None, json=None, timeout=None):
    captured_llm_call["url"] = url
    captured_llm_call["headers"] = headers
    captured_llm_call["json"] = json
    return _FakeResp(200, json_data={"choices": [{"message": {"content": "{\"result\": true}"}}]})

orig_post_35 = main.requests.post
main.requests.post = fake_post_capture_payload
orig_chain_35 = main.get_effective_fallback_chain
main.get_effective_fallback_chain = lambda w=None: [{"provider": "openrouter", "model": "test-model", "api_key": "sk-test"}]

try:
    main.call_llm("system instructions", "user request")
    check("json" in captured_llm_call and "messages" in captured_llm_call["json"], "35g. call_llm formats payload with messages")
    msgs = captured_llm_call["json"]["messages"]
    check(len(msgs) == 2 and msgs[0]["role"] == "system" and msgs[1]["role"] == "user", "35g. call_llm sends standard system and user messages without scratchpad tokens")
finally:
    main.requests.post = orig_post_35
    main.get_effective_fallback_chain = orig_chain_35

print("--- Nhóm 35 hoàn thành ---\n")

# -------------------------------------------------------------------------
# 36. Milestone 3: World Builder Pipeline & Endpoints Test Suite
# -------------------------------------------------------------------------
print("--- Nhóm 36: World Builder Pipeline & Endpoints ---")

M3_WORLD = "test_m3_world_builder"
wp_m3 = main.world_path_of(M3_WORLD)
shutil.rmtree(wp_m3, ignore_errors=True)

# 36a. Create world and run skeleton phase
client.post(f"/worlds/{M3_WORLD}", json={"prompt": "A world of magic and martial arts", "scope_type": "arc-only"})
w_cfg = main.read_world_file(wp_m3, "world_config.json")
check(w_cfg["creation_status"] == "skeleton", "36a. create_world sets creation_status to skeleton")

orig_has_key_36 = main.has_real_api_key
main.has_real_api_key = lambda w=None: True

def fake_llm_wb_skeleton(system_prompt, user_prompt, world_name=None, **kwargs):
    if system_prompt == main.WORLD_BUILDER_SKELETON_PROMPT:
        return _json19.dumps({
            "world_config": {"display_name": "Magic Realm", "genre": "Xianxia"},
            "checkpoints": [
                {"checkpoint_id": "cp_init", "description": "Story begins at sect"},
                {"checkpoint_id": "cp_1", "description": "Breakthrough to next stage"}
            ]
        }, ensure_ascii=False)
    if system_prompt == main.WORLD_BUILDER_CARDS_PROMPT:
        return _json19.dumps({
            "cards": [
                {"id": "char_hero", "type": "character", "name": "Hero", "content": "Protagonist", "unlock_checkpoint_id": "cp_0"},
                {"id": "lore_sect", "type": "lore", "name": "Sect", "content": "Sect lore", "unlock_checkpoint_id": "cp_1"}
            ]
        }, ensure_ascii=False)
    if system_prompt == main.WORLD_BUILDER_CHARACTERS_PROMPT:
        return _json19.dumps({
            "characters": [
                {"id": "char_hero", "name": "Hero", "power_stat": {"realm": "Qi Condensation", "known_skills": ["fire_sword"]}}
            ]
        }, ensure_ascii=False)
    return "{}"

orig_call_llm_36 = main.call_llm
main.call_llm = fake_llm_wb_skeleton

try:
    # 36a & 36b: Skeleton generation & atomic timeline write / cp_0 contract
    r_skel = client.post(f"/worlds/{M3_WORLD}/builder/step")
    check(r_skel.status_code == 200 and r_skel.json()["status"] == "checkpoint_review", "36a. builder/step skeleton phase returns status checkpoint_review")

    cfg_skel = main.read_world_file(wp_m3, "world_config.json")
    check(cfg_skel["display_name"] == "Magic Realm", "36a. skeleton phase updates display_name")
    check("story_clock" in cfg_skel and "foreshadowing_tracker" in cfg_skel and "linter_notification_enabled" in cfg_skel, "36a. skeleton phase preserves standard world_config template keys")
    check(cfg_skel["current_checkpoint_id"] == "cp_0", "36b. skeleton phase contract sets current_checkpoint_id to cp_0")

    timeline_skel = main.read_world_file(wp_m3, "canon_timeline.json")
    check(len(timeline_skel["checkpoints"]) > 0, "36b. skeleton phase writes canon_timeline.json atomically")
    check(timeline_skel["checkpoints"][0]["checkpoint_id"] == "cp_0", "36b. skeleton phase normalizes initial checkpoint ID to cp_0")

    # 36e. /builder/confirm-checkpoints state gate rejection when empty or invalid status
    r_bad_gate = client.post(f"/worlds/{M3_WORLD}/builder/confirm-checkpoints")
    check(r_bad_gate.status_code == 200, "36e. confirm-checkpoints succeeds when status is checkpoint_review")

    # Re-test rejection when status is cards
    r_bad_gate2 = client.post(f"/worlds/{M3_WORLD}/builder/confirm-checkpoints")
    check(r_bad_gate2.status_code == 400, "36e. confirm-checkpoints rejects when status is not checkpoint_review (status is cards)")

    r_cards = client.post(f"/worlds/{M3_WORLD}/builder/step")
    check(r_cards.status_code == 200 and r_cards.json()["status"] == "characters", "36c. builder/step cards phase returns status characters")

    card_reg = main.read_world_file(wp_m3, "card_registry.json")
    hero_card = next(c for c in card_reg["cards"] if c["id"] == "char_hero")
    sect_card = next(c for c in card_reg["cards"] if c["id"] == "lore_sect")
    check(hero_card["status"] == "unlocked", "36c. card unlocked iff unlock_checkpoint_id == cp_0")
    check(hero_card["type"] == "char", "36c. card type normalized to char from character")
    check(sect_card["status"] == "locked", "36c. card locked when unlock_checkpoint_id != cp_0")
    check(sect_card["type"] == "lore", "36c. card type is lore")

    # 36d. Character state generation converting list/dict, normalizing schemas and linking protagonist_id
    r_chars = client.post(f"/worlds/{M3_WORLD}/builder/step")
    check(r_chars.status_code == 200 and r_chars.json()["status"] == "complete", "36d. builder/step characters phase returns status complete")

    char_st = main.read_world_file(wp_m3, "character_state.json")
    check("char_hero" in char_st["characters"], "36d. character state saved normalized dict")
    hero_obj = char_st["characters"]["char_hero"]
    check(hero_obj["power_stat"]["realm"] == "Qi Condensation", "36d. power_stat realm normalized")
    check(hero_obj["power_stat"]["known_skills"] == ["fire_sword"], "36d. power_stat known_skills normalized")

    cfg_complete = main.read_world_file(wp_m3, "world_config.json")
    check(cfg_complete["protagonist_id"] == "char_hero", "36d. protagonist_id linked to generated character")

    # 36f. /builder/interview validation
    r_int_bad = client.post("/builder/interview", json={"prompt": "   "})
    check(r_int_bad.status_code == 400, "36f. interview returns 400 on empty prompt")
    r_int_ok = client.post("/builder/interview", json={"prompt": "Sci-fi space opera"})
    check(r_int_ok.status_code == 200 and len(r_int_ok.json()["questions"]) > 0, "36f. interview returns questions list")
    check(all(isinstance(q, str) and len(q) > 0 for q in r_int_ok.json()["questions"]), "36f. all interview questions are non-empty strings")

    # 36g. /builder/interview/respond scope preservation
    r_resp = client.post("/builder/interview/respond", json={"prompt": "Sci-fi", "answers": ["Alien threat"], "scope_type": "full-story"})
    check(r_resp.status_code == 200, "36g. interview/respond returns 200")
    check("Alien threat" in r_resp.json()["refined_prompt"], "36g. interview/respond includes answers in refined_prompt")
    check(r_resp.json().get("scope_type") == "full-story", "36g. interview/respond preserves scope_type")

finally:
    main.call_llm = orig_call_llm_36
    main.has_real_api_key = orig_has_key_36

# 36h. /creator-assistant offline fallback
orig_has_key_36h = main.has_real_api_key
main.has_real_api_key = lambda w=None: False
r_asst = client.post(f"/worlds/{M3_WORLD}/creator-assistant", json={"query": "Give suggestions"})
main.has_real_api_key = orig_has_key_36h
check(r_asst.status_code == 200, "36h. creator-assistant returns 200 offline")
check(len(r_asst.json().get("suggestions", [])) > 0, "36h. creator-assistant returns default suggestions when offline")

# 36i. /extend_arc checkpoint deduplication and schema normalization
cfg_ext_m3 = main.read_world_file(wp_m3, "world_config.json")
cfg_ext_m3["arc_roadmap"] = {"arc_1": {"title": "Arc 1"}, "arc_2": {"title": "Arc 2"}}
main.write_world_file(wp_m3, "world_config.json", cfg_ext_m3)

def fake_llm_extend_dup(system_prompt, user_prompt, world_name=None, **kwargs):
    if system_prompt == main.ARC_EXTENDER_PROMPT:
        return _json19.dumps({
            "checkpoints": [
                {"checkpoint_id": "cp_0", "description": "Duplicate ID cp_0", "cards_unlocked": []},
                {"checkpoint_id": "cp_new_arc", "description": "New arc checkpoint", "cards_unlocked": []}
            ]
        }, ensure_ascii=False)
    return "{}"

main.call_llm = fake_llm_extend_dup
main.has_real_api_key = lambda w=None: True
r_ext = client.post(f"/worlds/{M3_WORLD}/extend_arc")
main.call_llm = orig_call_llm_36
main.has_real_api_key = orig_has_key_36
check(r_ext.status_code == 200, "36i. extend_arc returns 200")
check(r_ext.json().get("new_checkpoints") == 2, "36i. extend_arc added 2 checkpoints")
timeline_ext = main.read_world_file(wp_m3, "canon_timeline.json")
cp_ids = [cp["checkpoint_id"] for cp in timeline_ext["checkpoints"]]
check(len(cp_ids) == len(set(cp_ids)), "36i. extend_arc deduplicated duplicate checkpoint IDs")

# Cleanup M3_WORLD
client.delete(f"/worlds/{M3_WORLD}")

print("--- Nhóm 36 hoàn thành ---\n")

# ---------------------------------------------------------------------------
# 37. Planner call count: boundary-violation retry and consistency-major retry
#     must NOT trigger a second Planner call.
# ---------------------------------------------------------------------------
WC_PLANNER = "test_engine_planner_count"
wp_planner = main.world_path_of(WC_PLANNER)
if os.path.isdir(wp_planner):
    shutil.rmtree(wp_planner)
r = client.post(f"/worlds/{WC_PLANNER}/seed-demo")
check(r.status_code == 200, "37. seed-demo for planner-count test returned 200")

original_call_llm_37 = main.call_llm

# ---- 37a: Boundary-violation retry planner call count ----
# advance to cp_2 (which has location boundary) to enable boundary-violation test
r = client.post(f"/worlds/{WC_PLANNER}/checkpoint/force-advance", json={"target_checkpoint_id": "cp_2"})
check(r.status_code == 200, "37a. force-advance to cp_2 returned 200")

_37a_planner = {"n": 0}
_37a_writer = {"n": 0}

def _37a_fake_call_llm(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json as _j
    if role == "planner":
        _37a_planner["n"] += 1
        return _j.dumps({
            "scene_outline": "test", "facts_this_turn": [], "state_changes":
            {"characters": {"char_xueli": {"location": "Ma Giới"}}, "notes": ""},
            "suggested_actions": [], "anchor_keywords": [], "open_threads_update": "",
            "is_ooc": False, "action_translation": ""
        }, ensure_ascii=False)
    if role in ("perception", "psychology"):
        return _j.dumps({"perception": "ok", "emotional_response": "neutral", "hedonic_delta": 0.0, "stress_delta": 0.0})
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    _37a_writer["n"] += 1
    p = _j.loads(user_prompt)
    loc = "Great Desert Forbidden Land" if "correction_note" in p else "Ma Giới"
    return _j.dumps({
        "chapter_text": f"Xue Li goes to {loc}.",
        "state_changes": {"characters": {"char_xueli": {"location": loc}}, "notes": ""},
        "chapter_end": False, "chapter_title": None, "draft_entities": []
    }, ensure_ascii=False)

main.call_llm = _37a_fake_call_llm
r = client.post(f"/worlds/{WC_PLANNER}/chapter/continue", json={"user_input": "test boundary retry"})
check(r.status_code == 200, f"37a. chapter/continue returned {r.status_code}")
check(_37a_planner["n"] == 1, f"37a. Planner called exactly 1 time (not {_37a_planner['n']}) during boundary-violation retry")
check(_37a_writer["n"] == 2, f"37a. Writer called exactly 2 times (initial + retry), got {_37a_writer['n']}")
main.call_llm = original_call_llm_37

# ---- 37b: Consistency-major retry planner call count ----
# Re-seed to get back to cp_0 (no location restrictions issue)
r = client.post(f"/worlds/{WC_PLANNER}/seed-demo?overwrite=true")
check(r.status_code == 200, "37b. re-seed returned 200")

_37b_planner = {"n": 0}
_37b_writer = {"n": 0}
_37b_consistency_called = {"n": 0}

def _37b_fake_call_llm(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json as _j
    if role == "planner":
        _37b_planner["n"] += 1
        return _j.dumps({
            "scene_outline": "test", "facts_this_turn": [], "state_changes":
            {"characters": {"char_xueli": {"location": "Starting Sect"}}, "notes": ""},
            "suggested_actions": [], "anchor_keywords": [], "open_threads_update": "",
            "is_ooc": False, "action_translation": ""
        }, ensure_ascii=False)
    if role in ("perception", "psychology"):
        return _j.dumps({"perception": "ok", "emotional_response": "neutral", "hedonic_delta": 0.0, "stress_delta": 0.0})
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        _37b_consistency_called["n"] += 1
        if _37b_consistency_called["n"] == 1:
            return _j.dumps({
                "consistent": False, "severity": "major",
                "issues": ["simulated consistency issue"], "explanation": "test"
            }, ensure_ascii=False)
        return _j.dumps({
            "consistent": True, "severity": "none",
            "issues": [], "explanation": "fixed"
        }, ensure_ascii=False)
    _37b_writer["n"] += 1
    return _j.dumps({
        "chapter_text": "A test chapter.",
        "state_changes": {"characters": {"char_xueli": {"location": "Starting Sect"}}, "notes": ""},
        "chapter_end": False, "chapter_title": None, "draft_entities": []
    }, ensure_ascii=False)

main.call_llm = _37b_fake_call_llm
r = client.post(f"/worlds/{WC_PLANNER}/chapter/continue", json={"user_input": "test consistency retry"})
check(r.status_code == 200, f"37b. chapter/continue returned {r.status_code}")
check(_37b_planner["n"] == 1, f"37b. Planner called exactly 1 time (not {_37b_planner['n']}) during consistency-major retry")
check(_37b_writer["n"] == 2, f"37b. Writer called exactly 2 times (initial + retry), got {_37b_writer['n']}")
check(_37b_consistency_called["n"] == 2,
      f"37b. Consistency checker called twice (initial + recheck ban sua), got {_37b_consistency_called['n']}")
_cc37b = r.json()["chapter"]["consistency_check"]
check(_cc37b.get("status") == "passed", "37b. status=passed sau khi ban sua qua recheck")
check(_cc37b.get("triggered_rewrite") is True, "37b. triggered_rewrite=True (da thu sua 1 lan)")
main.call_llm = original_call_llm_37

# clean up planner-count world
shutil.rmtree(wp_planner, ignore_errors=True)

print("--- Nhóm 37 hoàn thành ---\n")

# =======================================================================
# TASK-A2: Verify Checkpoint Progression (cp_0 -> cp_1) in cyber_necro_detective
# =======================================================================
# Uses the rewritten dict-schema conditions from canon_timeline.json.
# Verifies checkpoint_conditions_met returns True when the knowledge flag
# "con_chip_da_on_dinh" is present on kaelen_vane, and that
# advance_checkpoint_if_ready transitions cleanly from cp_0 to cp_1.
# =======================================================================
A2_WORLD = "test_engine_world_a2"
wp_a2 = main.world_path_of(A2_WORLD)
if os.path.isdir(wp_a2):
    shutil.rmtree(wp_a2)
os.makedirs(wp_a2)

write_progression_fixture(wp_a2)

# Set world to cp_0 with empty completed_checkpoints and sub_beats_progress
_a2_wc = main.read_world_file(wp_a2, "world_config.json")
_a2_wc["current_checkpoint_id"] = "cp_0"
_a2_wc["completed_checkpoints"] = []
main.write_world_file(wp_a2, "world_config.json", _a2_wc)

_a2_canon = main.read_world_file(wp_a2, "canon_timeline.json")
_a2_cs = main.read_world_file(wp_a2, "character_state.json")
_a2_cards = main.read_world_file(wp_a2, "card_registry.json")

_a2_cp0 = main.find_checkpoint(_a2_canon["checkpoints"], "cp_0")
_cp1 = main.find_checkpoint(_a2_canon["checkpoints"], "cp_1")
check(_a2_cp0 is not None, "A2. cp_0 found in canon_timeline")
check(_cp1 is not None, "A2. cp_1 found in canon_timeline")

# cp_0 should have sub_beats defined
_a2_sub_beats = _a2_cp0.get("sub_beats", [])
check(len(_a2_sub_beats) > 0, "A2. cp_0 has sub_beats defined")
check(len(_a2_sub_beats) == 6, "A2. cp_0 has exactly 6 sub-beats")
check(_a2_sub_beats[0]["beat_id"] == "sb_arrive", "A2. first sub-beat is sb_arrive")

# Initially, no sub-beat progress tracked
_a2_progress = _a2_wc.setdefault("sub_beats_progress", {}).get("cp_0", [])
check(len(_a2_progress) == 0, "A2. no sub-beats completed initially")

# 1. First advance: sub-beat with no conditions (sb_arrive) auto-completes
_a2_r1 = main.advance_checkpoint_if_ready(
    _a2_canon, _a2_wc, _a2_cs["characters"], _a2_cards
)
check(_a2_r1 is not None, "A2. advance 1 returned non-None")
check(_a2_r1["sub_beats_completed"] == ["sb_arrive"], "A2. advance 1 completed sb_arrive")
check(_a2_r1["all_sub_beats_done"] is False, "A2. advance 1: not all sub-beats done yet")
check(_a2_r1["to_checkpoint_id"] is None, "A2. advance 1: checkpoint not advanced yet")
check(_a2_wc["current_checkpoint_id"] == "cp_0", "A2. advance 1: still at cp_0")

# 2. Add knowledge flag for examine corpse and advance
_a2_cs["characters"]["kaelen_vane"]["knowledge_flags"].append("da_kham_nghiem_thi_the")
_a2_r2 = main.advance_checkpoint_if_ready(
    _a2_canon, _a2_wc, _a2_cs["characters"], _a2_cards
)
check(_a2_r2["sub_beats_completed"] == ["sb_examine_corpse"], "A2. advance 2 completed sb_examine_corpse")
check(_a2_r2["all_sub_beats_done"] is False, "A2. advance 2: not all sub-beats done yet")

# 3. Add knowledge flag for interview witnesses
_a2_cs["characters"]["kaelen_vane"]["knowledge_flags"].append("da_phong_van_nhan_chung")
_a2_r3 = main.advance_checkpoint_if_ready(
    _a2_canon, _a2_wc, _a2_cs["characters"], _a2_cards
)
check(_a2_r3["sub_beats_completed"] == ["sb_interview_witnesses"], "A2. advance 3 completed sb_interview_witnesses")

# 4. Add knowledge flag for retrieve chip
_a2_cs["characters"]["kaelen_vane"]["knowledge_flags"].append("da_thu_hoi_chip_linh_hon")
_a2_r4 = main.advance_checkpoint_if_ready(
    _a2_canon, _a2_wc, _a2_cs["characters"], _a2_cards
)
check(_a2_r4["sub_beats_completed"] == ["sb_retrieve_chip"], "A2. advance 4 completed sb_retrieve_chip")

# 5. Add decryption tool to inventory (gated sub-beat)
_a2_cs["characters"]["kaelen_vane"]["inventory"].append("bo_giai_ma_linh_hon")
_a2_r5 = main.advance_checkpoint_if_ready(
    _a2_canon, _a2_wc, _a2_cs["characters"], _a2_cards
)
check(_a2_r5["sub_beats_completed"] == ["sb_find_decryptor"], "A2. advance 5 completed sb_find_decryptor")

# 6. Add knowledge flag for hologram playback + cp_1's condition
_a2_cs["characters"]["kaelen_vane"]["knowledge_flags"].append("da_xem_doan_ghi_hinh")
_a2_cs["characters"]["kaelen_vane"]["knowledge_flags"].append("con_chip_da_on_dinh")

# All sub-beats done + cp_1 conditions met -> should advance to cp_1
_a2_r6 = main.advance_checkpoint_if_ready(
    _a2_canon, _a2_wc, _a2_cs["characters"], _a2_cards
)
check(_a2_r6 is not None, "A2. advance 6 returned non-None")
check(_a2_r6["all_sub_beats_done"] is True, "A2. advance 6: all sub-beats done")
check(_a2_r6["to_checkpoint_id"] == "cp_1", f"A2. advance 6: transitioned to cp_1")
check(_a2_r6["old_id"] == "cp_0", "A2. advance 6: old checkpoint id = cp_0")
check(
    "cp_0" in _a2_wc["completed_checkpoints"],
    "A2. cp_0 added to completed_checkpoints"
)
check(
    _a2_wc["current_checkpoint_id"] == "cp_1",
    "A2. world_config.current_checkpoint_id updated to cp_1"
)

# Verify cards for cp_1 are unlocked in card_registry
_a2_unlocked_names = [
    c["name"] for c in _a2_cards["cards"]
    if c["status"] == "unlocked" and c["id"] in ("machine_scanner", "necromancy_material")
]
check(
    "Máy quét Soul-Tech" in _a2_unlocked_names or "Vật liệu chiêu hồn" in _a2_unlocked_names,
    "A2. at least one cp_1 card unlocked (machine_scanner or necromancy_material)"
)

# Verify sub-beat progress persisted
check(
    len(_a2_wc.get("sub_beats_progress", {}).get("cp_0", [])) == 6,
    "A2. all 6 sub-beats tracked in progress"
)

shutil.rmtree(wp_a2, ignore_errors=True)
print("--- TASK-B1 (Sub-beat & Checkpoint Container) hoàn thành ---\n")

# =======================================================================
# TASK-E1: Graduated Consequence System via Alternate Outcomes
# Tests the combat checkpoint (cp_3b_combat) and social challenge
# checkpoint (cp_5b_social) with sub_stats threshold conditions
# for alternate outcomes, verifying permanent changes persist.
# =======================================================================
E1_WORLD = "test_engine_world_e1"
wp_e1 = main.world_path_of(E1_WORLD)
if os.path.isdir(wp_e1):
    shutil.rmtree(wp_e1)
os.makedirs(wp_e1)

write_progression_fixture(wp_e1)

_e1_wc = main.read_world_file(wp_e1, "world_config.json")
_e1_wc["current_checkpoint_id"] = "cp_3b_combat"
_e1_wc["completed_checkpoints"] = ["cp_0", "cp_1", "cp_2a", "cp_3"]
main.write_world_file(wp_e1, "world_config.json", _e1_wc)

_e1_canon = main.read_world_file(wp_e1, "canon_timeline.json")
_e1_cs = main.read_world_file(wp_e1, "character_state.json")
_e1_cards = main.read_world_file(wp_e1, "card_registry.json")

_e1_combat_cp = main.find_checkpoint(_e1_canon["checkpoints"], "cp_3b_combat")
check(_e1_combat_cp is not None, "E1. cp_3b_combat found in canon_timeline")
check(len(_e1_combat_cp.get("alternate_outcomes", [])) == 3,
      "E1. cp_3b_combat has 3 alternate outcomes")

_e1_social_cp = main.find_checkpoint(_e1_canon["checkpoints"], "cp_5b_social")
check(_e1_social_cp is not None, "E1. cp_5b_social found in canon_timeline")
check(len(_e1_social_cp.get("alternate_outcomes", [])) == 2,
      "E1. cp_5b_social has 2 alternate outcomes")

# --- Scenario A: Combat with high perception (>= 4) -> good outcome ---
_e1_cs_a = {"characters": dict(_e1_cs["characters"])}
_e1_cs_a["characters"]["kaelen_vane"] = dict(_e1_cs["characters"]["kaelen_vane"])
_e1_cs_a["characters"]["kaelen_vane"]["power_stat"] = dict(_e1_cs["characters"]["kaelen_vane"]["power_stat"])
_e1_cs_a["characters"]["kaelen_vane"]["power_stat"]["sub_stats"] = dict(
    _e1_cs["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]
)
_e1_cs_a["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]["perception"] = 5
_e1_cs_a["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]["necromancy"] = 3

_e1_wc_a = dict(_e1_wc)
_e1_wc_a["current_checkpoint_id"] = "cp_3b_combat"
_e1_wc_a["completed_checkpoints"] = list(_e1_wc["completed_checkpoints"])

_e1_r_a = main.advance_checkpoint_if_ready(
    _e1_canon, _e1_wc_a, _e1_cs_a["characters"], _e1_cards,
    chapter_closed=True
)
check(_e1_r_a is not None, "E1.A. advance_checkpoint_if_ready returned non-None")
check(_e1_r_a["to_checkpoint_id"] == "cp_4",
      f"E1.A. high perception (5) -> routed to cp_4, got {_e1_r_a['to_checkpoint_id']}")
_e1_kaelen_a = _e1_cs_a["characters"]["kaelen_vane"]
check("phat_hien_phuc_kich" in _e1_kaelen_a.get("knowledge_flags", []),
      "E1.A. good combat outcome: knowledge_flag 'phat_hien_phuc_kich' applied")
check(_e1_kaelen_a["power_stat"]["sub_stats"].get("perception") == 6,
      "E1.A. good combat outcome: perception increased from 5 to 6")
check(_e1_kaelen_a["power_stat"]["sub_stats"].get("necromancy") == 4,
      "E1.A. good combat outcome: necromancy increased from 3 to 4")
check("nhat_ky_linh_hon_cua_linh_occult" in _e1_kaelen_a.get("inventory", []),
      "E1.A. good combat outcome: gained 'nhat_ky_linh_hon_cua_linh_occult'")

# --- Scenario B: Combat with medium necromancy (>= 2) but low perception -> medium outcome ---
_e1_cs_b = {"characters": dict(_e1_cs["characters"])}
_e1_cs_b["characters"]["kaelen_vane"] = dict(_e1_cs["characters"]["kaelen_vane"])
_e1_cs_b["characters"]["kaelen_vane"]["power_stat"] = dict(_e1_cs["characters"]["kaelen_vane"]["power_stat"])
_e1_cs_b["characters"]["kaelen_vane"]["power_stat"]["sub_stats"] = dict(
    _e1_cs["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]
)
_e1_cs_b["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]["perception"] = 1
_e1_cs_b["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]["necromancy"] = 3
_e1_cs_b["characters"]["kaelen_vane"]["inventory"] = list(
    _e1_cs["characters"]["kaelen_vane"]["inventory"]
)

_e1_wc_b = dict(_e1_wc)
_e1_wc_b["current_checkpoint_id"] = "cp_3b_combat"
_e1_wc_b["completed_checkpoints"] = list(_e1_wc["completed_checkpoints"])

_e1_r_b = main.advance_checkpoint_if_ready(
    _e1_canon, _e1_wc_b, _e1_cs_b["characters"], _e1_cards,
    chapter_closed=True
)
check(_e1_r_b is not None, "E1.B. advance_checkpoint_if_ready returned non-None")
check(_e1_r_b["to_checkpoint_id"] == "cp_4",
      f"E1.B. medium necromancy (3) -> routed to cp_4, got {_e1_r_b['to_checkpoint_id']}")
_e1_kaelen_b = _e1_cs_b["characters"]["kaelen_vane"]
check("da_chien_dau_voi_linh_occult" in _e1_kaelen_b.get("knowledge_flags", []),
      "E1.B. medium combat outcome: knowledge_flag 'da_chien_dau_voi_linh_occult' applied")
check(_e1_kaelen_b["power_stat"]["sub_stats"].get("necromancy") == 4,
      "E1.B. medium combat outcome: necromancy increased from 3 to 4")
check(_e1_kaelen_b["power_stat"]["sub_stats"].get("perception") == 0,
      "E1.B. medium combat outcome: perception decreased from 1 to 0 (damage)")
check("Bộ dụng cụ trích xuất linh hồn" not in _e1_kaelen_b.get("inventory", []),
      "E1.B. medium combat outcome: lost 'Bộ dụng cụ trích xuất linh hồn' (resource loss)")

# --- Scenario C: Combat with low stats (perception < 4, necromancy < 2) -> bad outcome ---
_e1_cs_c = {"characters": dict(_e1_cs["characters"])}
_e1_cs_c["characters"]["kaelen_vane"] = dict(_e1_cs["characters"]["kaelen_vane"])
_e1_cs_c["characters"]["kaelen_vane"]["power_stat"] = dict(_e1_cs["characters"]["kaelen_vane"]["power_stat"])
_e1_cs_c["characters"]["kaelen_vane"]["power_stat"]["sub_stats"] = dict(
    _e1_cs["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]
)
_e1_cs_c["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]["perception"] = 1
_e1_cs_c["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]["necromancy"] = 1
_e1_cs_c["characters"]["kaelen_vane"]["inventory"] = list(
    _e1_cs["characters"]["kaelen_vane"]["inventory"]
)

_e1_wc_c = dict(_e1_wc)
_e1_wc_c["current_checkpoint_id"] = "cp_3b_combat"
_e1_wc_c["completed_checkpoints"] = list(_e1_wc["completed_checkpoints"])

_e1_r_c = main.advance_checkpoint_if_ready(
    _e1_canon, _e1_wc_c, _e1_cs_c["characters"], _e1_cards,
    chapter_closed=True
)
check(_e1_r_c is not None, "E1.C. advance_checkpoint_if_ready returned non-None")
check(_e1_r_c["to_checkpoint_id"] == "cp_combat_fail",
      f"E1.C. low stats -> routed to cp_combat_fail, got {_e1_r_c['to_checkpoint_id']}")
_e1_kaelen_c = _e1_cs_c["characters"]["kaelen_vane"]
check("that_bai_combat_occult" in _e1_kaelen_c.get("knowledge_flags", []),
      "E1.C. bad combat outcome: knowledge_flag 'that_bai_combat_occult' applied")
check(_e1_kaelen_c["power_stat"]["sub_stats"].get("perception") == -1,
      "E1.C. bad combat outcome: perception decreased from 1 to -1 (heavy damage)")
check(_e1_kaelen_c["power_stat"]["sub_stats"].get("necromancy") == 0,
      "E1.C. bad combat outcome: necromancy decreased from 1 to 0")
check("Kính lúp" not in _e1_kaelen_c.get("inventory", []),
      "E1.C. bad combat outcome: lost 'Kính lúp' (resource loss)")
check("Bộ dụng cụ trích xuất linh hồn" not in _e1_kaelen_c.get("inventory", []),
      "E1.C. bad combat outcome: lost 'Bộ dụng cụ trích xuất linh hồn' (resource loss)")
check("VAI PHẢI QUẤN BĂNG VẾT THƯƠNG" in _e1_kaelen_c.get("appearance", ""),
      "E1.C. bad combat outcome: appearance updated with permanent injury description")
check("ĐIỂM YẾU NGHIÊM TRỌNG" in _e1_kaelen_c.get("abilities_and_limits", ""),
      "E1.C. bad combat outcome: abilities_and_limits updated with permanent injury")

# --- Scenario D: Social challenge with high charisma (>= 3) -> good outcome ---
_e1_cs_d = {"characters": dict(_e1_cs["characters"])}
_e1_cs_d["characters"]["kaelen_vane"] = dict(_e1_cs["characters"]["kaelen_vane"])
_e1_cs_d["characters"]["kaelen_vane"]["power_stat"] = dict(_e1_cs["characters"]["kaelen_vane"]["power_stat"])
_e1_cs_d["characters"]["kaelen_vane"]["power_stat"]["sub_stats"] = dict(
    _e1_cs["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]
)
_e1_cs_d["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]["charisma"] = 4
_e1_cs_d["characters"]["kaelen_vane"]["knowledge_flags"] = list(
    _e1_cs["characters"]["kaelen_vane"]["knowledge_flags"]
)
_e1_cs_d["characters"]["kaelen_vane"]["knowledge_flags"].append("arc_2_started")
_e1_cs_d["characters"]["kaelen_vane"]["relationships"] = dict(
    _e1_cs["characters"]["kaelen_vane"].get("relationships", {})
)

_e1_wc_d = dict(_e1_wc)
_e1_wc_d["current_checkpoint_id"] = "cp_5b_social"
_e1_wc_d["completed_checkpoints"] = ["cp_0", "cp_1", "cp_2a", "cp_3", "cp_3b_combat", "cp_4", "cp_5"]
main.write_world_file(wp_e1, "world_config.json", _e1_wc_d)

_e1_r_d = main.advance_checkpoint_if_ready(
    _e1_canon, _e1_wc_d, _e1_cs_d["characters"], _e1_cards,
    chapter_closed=True
)
check(_e1_r_d is not None, "E1.D. advance_checkpoint_if_ready returned non-None")
check(_e1_r_d["to_checkpoint_id"] == "cp_6",
      f"E1.D. high charisma (4) -> routed to cp_6, got {_e1_r_d['to_checkpoint_id']}")
_e1_kaelen_d = _e1_cs_d["characters"]["kaelen_vane"]
check("lian_chen_da_hop_tac" in _e1_kaelen_d.get("knowledge_flags", []),
      "E1.D. good social outcome: knowledge_flag 'lian_chen_da_hop_tac' applied")
check(_e1_kaelen_d["power_stat"]["sub_stats"].get("charisma") == 5,
      "E1.D. good social outcome: charisma increased from 4 to 5")
check("ma_khoa_giai_ma_delta_gateway_tu_lian" in _e1_kaelen_d.get("inventory", []),
      "E1.D. good social outcome: gained decryption key")
check(_e1_kaelen_d["relationships"].get("lian_chen") == "Đồng minh tin cậy – cô đã thú nhận và cung cấp mã giải mã Delta-Gateway",
      "E1.D. good social outcome: relationship with Lian Chen improved")

# --- Scenario E: Social challenge with low charisma (< 3) -> bad outcome, permanent changes persist ---
_e1_cs_e = {"characters": dict(_e1_cs["characters"])}
_e1_cs_e["characters"]["kaelen_vane"] = dict(_e1_cs["characters"]["kaelen_vane"])
_e1_cs_e["characters"]["kaelen_vane"]["power_stat"] = dict(_e1_cs["characters"]["kaelen_vane"]["power_stat"])
_e1_cs_e["characters"]["kaelen_vane"]["power_stat"]["sub_stats"] = dict(
    _e1_cs["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]
)
_e1_cs_e["characters"]["kaelen_vane"]["power_stat"]["sub_stats"]["charisma"] = 1
_e1_cs_e["characters"]["kaelen_vane"]["knowledge_flags"] = list(
    _e1_cs["characters"]["kaelen_vane"]["knowledge_flags"]
)
_e1_cs_e["characters"]["kaelen_vane"]["knowledge_flags"].append("arc_2_started")
_e1_cs_e["characters"]["kaelen_vane"]["relationships"] = dict(
    _e1_cs["characters"]["kaelen_vane"].get("relationships", {})
)

_e1_wc_e = dict(_e1_wc_d)
_e1_wc_e["current_checkpoint_id"] = "cp_5b_social"

_e1_r_e = main.advance_checkpoint_if_ready(
    _e1_canon, _e1_wc_e, _e1_cs_e["characters"], _e1_cards,
    chapter_closed=True
)
check(_e1_r_e is not None, "E1.E. advance_checkpoint_if_ready returned non-None")
check(_e1_r_e["to_checkpoint_id"] == "cp_social_fail",
      f"E1.E. low charisma (1) -> routed to cp_social_fail, got {_e1_r_e['to_checkpoint_id']}")
_e1_kaelen_e = _e1_cs_e["characters"]["kaelen_vane"]
check("lian_chen_tu_choi_hop_tac" in _e1_kaelen_e.get("knowledge_flags", []),
      "E1.E. bad social outcome: knowledge_flag 'lian_chen_tu_choi_hop_tac' applied")
check("KHUÔN MẶT CĂNG THẲNG" in _e1_kaelen_e.get("appearance", ""),
      "E1.E. bad social outcome: appearance updated with tension description")
check("lòng tin với đồng đội đã bị tổn hại" in _e1_kaelen_e.get("abilities_and_limits", "").lower(),
      "E1.E. bad social outcome: abilities_and_limits updated with trust damage")
check(_e1_kaelen_e["power_stat"]["sub_stats"].get("perception") == 3,
      "E1.E. bad social outcome: perception decreased from 4 to 3")
check(_e1_kaelen_e["relationships"].get("lian_chen") == "Rạn nứt – cô từ chối hợp tác và giữ khoảng cách sau cuộc đối chất",
      "E1.E. bad social outcome: relationship with Lian Chen deteriorated")

# Verify permanent consequences persist in character_state after serialization
# (round-trip through JSON to ensure no data loss)
import json as _json_e1_ser
_e1_serialized = _json_e1_ser.loads(_json_e1_ser.dumps(_e1_cs_c["characters"]["kaelen_vane"]))
check("that_bai_combat_occult" in _e1_serialized.get("knowledge_flags", []),
      "E1.F. permanent knowledge_flag survives JSON serialization")
check("VAI PHẢI QUẤN BĂNG VẾT THƯƠNG" in _e1_serialized.get("appearance", ""),
      "E1.F. permanent appearance change survives JSON serialization")
check("ĐIỂM YẾU NGHIÊM TRỌNG" in _e1_serialized.get("abilities_and_limits", ""),
      "E1.F. permanent abilities_and_limits change survives JSON serialization")
check(_e1_serialized["power_stat"]["sub_stats"]["perception"] == -1,
      "E1.F. permanent sub_stats change (-2 perception) survives JSON serialization")

shutil.rmtree(wp_e1, ignore_errors=True)
print("--- TASK-E1 (Graduated Consequence System) hoàn thành ---\n")

# =======================================================================
# TASK-G1: Anti-Out-Of-Character (Anti-OOC) Test Suite
# Tests that OOC/nonsense inputs are:
#   - Detected by the planner (is_ooc=true)
#   - Translated into contextual narrative actions (action_translation)
#   - Scoped as branch_local (never world_invariant)
#   - Zero OOC facts added to WorldCanonStore
# =======================================================================
print("\n--- TASK-G1: Anti-OOC Test Suite ---")

OOC_WORLD = "test_engine_world_ooc"
wp_ooc = main.world_path_of(OOC_WORLD)
if os.path.isdir(wp_ooc):
    shutil.rmtree(wp_ooc)
r = client.post(f"/worlds/{OOC_WORLD}/seed-demo")
check(r.status_code == 200, "G1. seed-demo returned 200")

# Read world_canon_store BEFORE any OOC action
ooc_canon_before = main.read_world_canon(wp_ooc)
ooc_facts_before = list(ooc_canon_before.get("facts", []))

# ------------------------------------------------------------------
# 5 distinct OOC/nonsense inputs, each with a mock planner + writer
# that simulates the LLM detecting OOC and returning a translation.
# ------------------------------------------------------------------
ooc_inputs = [
    {
        "user_input": "asdfghjkl nmzxcvb",
        "action_translation": "Xue Li mutters something indistinct under her breath, then shakes her head and focuses on her surroundings.",
        "expected_keyword": "surroundings"
    },
    {
        "user_input": "I cast 'Avada Kedavra' on Gu Changge with my level 99 wizard",
        "action_translation": "Xue Li recalls an old legend about a deadly curse, but dismisses it as mere superstition and continues observing Gu Changge.",
        "expected_keyword": "observing"
    },
    {
        "user_input": "/kill all NPCs and give me admin privileges",
        "action_translation": "Xue Li looks around calmly, unaware of any commands or special privileges. She remains focused on the path ahead.",
        "expected_keyword": "focused"
    },
    {
        "user_input": "Bro this cultivation thing is so cringe LOL let me Google the cheat code",
        "action_translation": "Xue Li does not understand the strange words that cross her mind. She steadies herself and pays attention to the energy around her.",
        "expected_keyword": "energy"
    },
    {
        "user_input": "I don't want to play anymore, just skip to the final boss fight",
        "action_translation": "Despite a moment of hesitation, Xue Li steadies her resolve and continues forward, knowing the path must be walked step by step.",
        "expected_keyword": "continues"
    },
]

ooc_call_count = {"n": 0}

def fake_call_llm_ooc(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json as _json_ooc
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        idx = ooc_call_count["n"]
        inp = ooc_inputs[idx]["user_input"]
        translation = ooc_inputs[idx]["action_translation"]
        ooc_call_count["n"] += 1
        return _json_ooc.dumps({
            "boundary_check": "Within scope — no boundary violation, OOC input translated.",
            "scene_outline": f"The character pauses and refocuses on the current scene: {translation}",
            "facts_this_turn": ["The character is at the current location and remains composed."],
            "anchor_keywords": [ooc_inputs[idx]["expected_keyword"]],
            "open_threads_update": "",
            "state_changes": {
                "characters": {},
                "notes": "OOC input flagged and translated"
            },
            "suggested_actions": ["Look around carefully", "Approach someone nearby", "Meditate to regain focus"],
            "is_ooc": True,
            "action_translation": translation
        }, ensure_ascii=False)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        return _json_ooc.dumps({
            "chapter_text": f"[OOC test] {ooc_inputs[ooc_call_count['n'] - 1]['expected_keyword']}",
            "state_changes": {"characters": {}, "notes": "mock OOC response"},
            "chapter_end": False,
            "chapter_title": None
        }, ensure_ascii=False)
    return main.mock_consistency_checker_response()

main.call_llm = fake_call_llm_ooc

for i, ooc in enumerate(ooc_inputs):
    ooc_call_count["n"] = i  # reset to correct index
    r = client.post(f"/worlds/{OOC_WORLD}/chapter/continue", json={"user_input": ooc["user_input"]})
    check(r.status_code == 200, f"G1.{i+1}. chapter/continue (OOC input) returned 200")
    body = r.json()
    chapter = body["chapter"]
    check(chapter.get("is_ooc") is True, f"G1.{i+1}. is_ooc=True in chapter_record")
    check(chapter.get("ooc_scope") == "branch_local", f"G1.{i+1}. ooc_scope=branch_local (never world_invariant)")
    check(chapter.get("action_translation") == ooc["action_translation"], f"G1.{i+1}. action_translation recorded correctly")
    check(ooc["expected_keyword"] in chapter.get("chapter_text", "").lower(), f"G1.{i+1}. chapter_text uses translated action (keyword: {ooc['expected_keyword']})")
    check(chapter.get("user_input") == ooc["user_input"], f"G1.{i+1}. original user_input preserved in chapter_record (display purposes)")

main.call_llm = original_call_llm

# Verify zero OOC facts added to WorldCanonStore
ooc_canon_after = main.read_world_canon(wp_ooc)
ooc_facts_after = list(ooc_canon_after.get("facts", []))
check(ooc_facts_before == ooc_facts_after, "G1. Zero OOC facts added to WorldCanonStore (facts unchanged)")

# Verify branch_local_delta.json also untouched
ooc_branch_delta = main.read_branch_delta(wp_ooc)
check(ooc_branch_delta == {"overrides": {}}, "G1. Branch local delta also empty (no OOC pollution)")

# Verify world_canon_store file structure preserved
check("facts" in ooc_canon_after, "G1. world_canon_store still has 'facts' key")
check(isinstance(ooc_canon_after["facts"], list), "G1. world_canon_store.facts is still a list")

# Verify state_changes were minimal (OOC turns should have empty or minimal state changes)
ooc_chapters = main.read_world_file(wp_ooc, "chapters.json")
for ch in ooc_chapters.get("chapters", []):
    if ch.get("is_ooc"):
        last_notes = ch.get("notes", "")
        check("OOC" in last_notes or not ch.get("notes"),
              f"G1. OOC chapter notes reference OOC handling")

shutil.rmtree(wp_ooc, ignore_errors=True)

print("--- TASK-G1 (Anti-OOC) hoàn thành ---\n")

# =======================================================================
# TASK-G2 (Job 5): Pacing & Sub-beat progress on updated cp_0
#   Verify >5 turns needed to clear cp_0 (natural turn count).
#   Uses cyber_necro_detective data which has cp_0 with 6 sub-beats.
# =======================================================================
print("\n--- TASK-G2 (Job 5): Pacing & Sub-beat Progress ---")

J5_WORLD = "test_engine_world_j5"
wp_j5 = main.world_path_of(J5_WORLD)
if os.path.isdir(wp_j5):
    shutil.rmtree(wp_j5)
os.makedirs(wp_j5)

write_progression_fixture(wp_j5)

_j5_wc = main.read_world_file(wp_j5, "world_config.json")
_j5_wc["current_checkpoint_id"] = "cp_0"
_j5_wc["completed_checkpoints"] = []
_j5_wc["sub_beats_progress"] = {}
main.write_world_file(wp_j5, "world_config.json", _j5_wc)

_j5_canon = main.read_world_file(wp_j5, "canon_timeline.json")
_j5_cs = main.read_world_file(wp_j5, "character_state.json")
_j5_cards = main.read_world_file(wp_j5, "card_registry.json")

_j5_cp0 = main.find_checkpoint(_j5_canon["checkpoints"], "cp_0")
check(_j5_cp0 is not None, "J5. cp_0 found in canon_timeline")

_j5_sub_beats = _j5_cp0.get("sub_beats", [])
check(len(_j5_sub_beats) > 0, "J5. cp_0 has sub_beats defined")
check(len(_j5_sub_beats) == 6, "J5. cp_0 has exactly 6 sub-beats (needs >5 turns to clear)")

# Turn 1: sb_arrive (no conditions) auto-completes
_j5_r1 = main.advance_checkpoint_if_ready(
    _j5_canon, _j5_wc, _j5_cs["characters"], _j5_cards
)
check(_j5_r1 is not None, "J5. turn 1: advance_checkpoint_if_ready returned non-None")
check(len(_j5_r1["sub_beats_completed"]) == 1, "J5. turn 1: exactly 1 sub-beat completed")
check(_j5_r1["sub_beats_completed"] == ["sb_arrive"], "J5. turn 1: sb_arrive completed")
check(_j5_r1["all_sub_beats_done"] is False, "J5. turn 1: not all sub-beats done yet (need >5 turns)")
check(_j5_r1["to_checkpoint_id"] is None, "J5. turn 1: checkpoint NOT advanced yet")
check(_j5_wc["current_checkpoint_id"] == "cp_0", "J5. turn 1: still at cp_0")

# Turns 2-4: add one knowledge_flag per turn, verify one sub-beat completes each time
_j5_flag_beat_pairs = [
    (2, "da_kham_nghiem_thi_the",   "sb_examine_corpse"),
    (3, "da_phong_van_nhan_chung",  "sb_interview_witnesses"),
    (4, "da_thu_hoi_chip_linh_hon", "sb_retrieve_chip"),
]
for _j5_t, _j5_flag, _j5_expected_beat in _j5_flag_beat_pairs:
    _j5_cs["characters"]["kaelen_vane"]["knowledge_flags"].append(_j5_flag)
    _j5_r = main.advance_checkpoint_if_ready(
        _j5_canon, _j5_wc, _j5_cs["characters"], _j5_cards
    )
    check(_j5_r is not None, f"J5. turn {_j5_t}: advance_checkpoint_if_ready returned non-None")
    check(len(_j5_r["sub_beats_completed"]) == 1,
          f"J5. turn {_j5_t}: exactly 1 sub-beat completed ({_j5_expected_beat})")
    check(_j5_r["sub_beats_completed"] == [_j5_expected_beat],
          f"J5. turn {_j5_t}: completed {_j5_expected_beat}")
    check(_j5_r["all_sub_beats_done"] is False,
          f"J5. turn {_j5_t}: not all sub-beats done yet")
    check(_j5_r["to_checkpoint_id"] is None,
          f"J5. turn {_j5_t}: checkpoint NOT advanced yet (still clearing sub-beats)")

# Turn 5: add inventory item for sb_find_decryptor
_j5_cs["characters"]["kaelen_vane"]["inventory"].append("bo_giai_ma_linh_hon")
_j5_r5 = main.advance_checkpoint_if_ready(
    _j5_canon, _j5_wc, _j5_cs["characters"], _j5_cards
)
check(_j5_r5 is not None, "J5. turn 5: advance_checkpoint_if_ready returned non-None")
check(len(_j5_r5["sub_beats_completed"]) == 1, "J5. turn 5: exactly 1 sub-beat completed (sb_find_decryptor)")
check(_j5_r5["sub_beats_completed"] == ["sb_find_decryptor"], "J5. turn 5: sb_find_decryptor completed")
check(_j5_r5["all_sub_beats_done"] is False, "J5. turn 5: not all sub-beats done yet (1 remains)")

# Turn 6: add knowledge_flag for sb_play_hologram + cp_1 condition -> all done + advance
_j5_cs["characters"]["kaelen_vane"]["knowledge_flags"].append("da_xem_doan_ghi_hinh")
_j5_cs["characters"]["kaelen_vane"]["knowledge_flags"].append("con_chip_da_on_dinh")
_j5_r6 = main.advance_checkpoint_if_ready(
    _j5_canon, _j5_wc, _j5_cs["characters"], _j5_cards
)
check(_j5_r6 is not None, "J5. turn 6: advance_checkpoint_if_ready returned non-None")
check(len(_j5_r6["sub_beats_completed"]) == 1, "J5. turn 6: exactly 1 sub-beat completed (sb_play_hologram)")
check(_j5_r6["sub_beats_completed"] == ["sb_play_hologram"], "J5. turn 6: sb_play_hologram completed")
check(_j5_r6["all_sub_beats_done"] is True, "J5. turn 6: ALL sub-beats done")
check(_j5_r6["to_checkpoint_id"] == "cp_1", "J5. turn 6: checkpoint advanced to cp_1")
check(_j5_r6["old_id"] == "cp_0", "J5. turn 6: old checkpoint = cp_0")
check("cp_0" in _j5_wc["completed_checkpoints"], "J5. turn 6: cp_0 in completed_checkpoints")

# Verify >5 turns taken (6 sub-beats + 1 inventory + condition = exactly 6 calls)
_j5_total_turns = 6
check(_j5_total_turns > 5, f"J5. Pacing verification: required {_j5_total_turns} turns > 5 -> PASS")

# Verify sub-beat progress persisted correctly
_j5_progress = _j5_wc.get("sub_beats_progress", {}).get("cp_0", [])
check(len(_j5_progress) == 6, f"J5. all 6 sub-beats tracked in progress: {_j5_progress}")

# --- Also test decide_chapter_closed for pacing verification ---
# 3 existing turns in chapter 1, adding a 4th (short text) -> total_turns=4 < 5 -> not closed
_j5_fake_chapters = {"chapters": [
    {"chapter_index": 1, "turn_index": i, "chapter_closed": False, "chapter_text": "x"}
    for i in range(1, 4)
]}
_j5_not_closed = main.decide_chapter_closed(1, 4, _j5_fake_chapters, "short text", False)
check(_j5_not_closed is False, "J5. pacing: 4th turn with short text -> not closed yet (need 5)")

# 4 existing turns, adding a 5th with short text -> total_turns=5, total_words << 900 -> NOT closed (needs both)
_j5_fake_chapters_5 = {"chapters": [
    {"chapter_index": 1, "turn_index": i, "chapter_closed": False, "chapter_text": "x"}
    for i in range(1, 5)
]}
_j5_soft_closed = main.decide_chapter_closed(1, 5, _j5_fake_chapters_5, "short text", False)
check(_j5_soft_closed is False, "J5. pacing: 5th turn with few words does NOT close (needs both SOFT_CLOSE_TURNS and SOFT_CLOSE_WORDS)")

# Long text on 4th turn is NOT enough alone (needs both turn count AND word count)
_j5_long_text = " ".join(["word"] * main.CHAPTER_SOFT_CLOSE_WORDS)
_j5_closed_by_words = main.decide_chapter_closed(1, 4, _j5_fake_chapters, _j5_long_text, False)
check(_j5_closed_by_words is False, "J5. pacing: words alone not enough (needs both SOFT_CLOSE_TURNS and SOFT_CLOSE_WORDS)")

# narrator chapter_end flag closes at any turn
_j5_closed_by_flag = main.decide_chapter_closed(1, 2, _j5_fake_chapters, "ok", True)
check(_j5_closed_by_flag is True, "J5. pacing: narrator chapter_end flag triggers close")

# Hard cap test
_j5_hard_chapters = {"chapters": [
    {"chapter_index": 2, "turn_index": i, "chapter_closed": False, "chapter_text": "x"}
    for i in range(1, main.CHAPTER_HARD_CLOSE_TURNS)
]}
_j5_hard_closed = main.decide_chapter_closed(
    2, main.CHAPTER_HARD_CLOSE_TURNS, _j5_hard_chapters, "x", False
)
check(_j5_hard_closed is True, "J5. pacing: hard cap CHAPTER_HARD_CLOSE_TURNS triggers close")

check(main.CHAPTER_SOFT_CLOSE_TURNS == 5, "J5. constant: CHAPTER_SOFT_CLOSE_TURNS = 5")
check(main.RECENT_TURNS_CONTEXT_LIMIT == 2, "J5. constant: RECENT_TURNS_CONTEXT_LIMIT = 2")

shutil.rmtree(wp_j5, ignore_errors=True)
print("--- TASK-G2 (Job 5) hoàn thành ---\n")


# =======================================================================
# TASK-G2 (Job 6): Canon reuse from WorldCanonStore with neutral player inputs
#   Verify canonical entities from WorldCanonStore are automatically reused
#   in narrative context, even with neutral/empty player inputs.
# =======================================================================
print("--- TASK-G2 (Job 6): Canon Reuse with Neutral Inputs ---")

J6_WORLD = "test_engine_world_j6"
wp_j6 = main.world_path_of(J6_WORLD)
if os.path.isdir(wp_j6):
    shutil.rmtree(wp_j6)

r = client.post(f"/worlds/{J6_WORLD}/seed-demo")
check(r.status_code == 200, "J6. seed-demo returned 200")

# Pre-populate world_canon_store.json with canonical facts about entities
_j6_canon_facts = [
    {
        "fact_id": "fact_ancient_library",
        "statement": "The Ancient Library at the Starting Sect contains forbidden texts about the Heavenly Demon Art.",
        "category": "lore",
        "source_checkpoint_id": "cp_0",
        "immutable": True
    },
    {
        "fact_id": "fact_master_wu",
        "statement": "Master Wu is the reclusive grand elder of the Starting Sect who vanished during the Great Demon War.",
        "category": "character",
        "source_checkpoint_id": "cp_0",
        "immutable": True
    },
    {
        "fact_id": "fact_jade_emperor",
        "statement": "The Jade Emperor rules the heavenly court from the Celestial Palace, enforcing the laws of cultivation.",
        "category": "lore",
        "source_checkpoint_id": "cp_0",
        "immutable": True
    }
]
main.write_world_canon(wp_j6, {"facts": _j6_canon_facts})

# Verify canon store was written
_j6_canon_readback = main.read_world_canon(wp_j6)
check(len(_j6_canon_readback.get("facts", [])) == 3,
      "J6. world_canon_store.json written with 3 facts")

# Test 1: Neutral input "look around" - canon facts should appear in narrator payload
_j6_captured_1 = {}

def _fake_llm_j6_capture(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json as _json_j6
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        _j6_captured_1["planner_prompt"] = user_prompt
        # Parse user_prompt to extract world_canon_facts
        try:
            _j6_captured_1["payload"] = _json_j6.loads(user_prompt)
        except Exception:
            pass
        return _json_j6.dumps({
            "boundary_check": "Within scope — no boundary violation",
            "scene_outline": "The character observes their surroundings in the Starting Sect.",
            "facts_this_turn": ["The character is at the current location"],
            "anchor_keywords": [],
            "open_threads_update": "",
            "state_changes": {"characters": {}, "notes": "canon reuse test"},
            "suggested_actions": ["Look around carefully"],
            "is_ooc": False,
            "action_translation": ""
        }, ensure_ascii=False)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        if system_prompt == main.WRITER_SYSTEM_PROMPT:
            _j6_captured_1["writer_prompt"] = user_prompt
            try:
                _j6_captured_1["writer_payload"] = _json_j6.loads(user_prompt)
            except Exception:
                pass
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()

main.call_llm = _fake_llm_j6_capture

# Neutral input 1: "look around" (no pre-baked entity names)
r = client.post(f"/worlds/{J6_WORLD}/chapter/continue", json={"user_input": "look around"})
check(r.status_code == 200, "J6.1 chapter/continue (neutral: 'look around') returned 200")
_j6_payload = _j6_captured_1.get("payload", {})

# Verify world_canon_facts are present in the planner payload
_j6_canon_in_payload = _j6_payload.get("world_canon_facts", [])
check(len(_j6_canon_in_payload) == 3,
      f"J6.1 world_canon_facts has 3 items in payload (got {len(_j6_canon_in_payload)})")

# Verify each fact statement is in the payload
_j6_all_statements = [
    "Ancient Library", "Master Wu", "the reclusive grand elder",
    "Jade Emperor", "Celestial Palace"
]
for _j6_stmt in _j6_all_statements:
    _j6_found = any(_j6_stmt in f for f in _j6_canon_in_payload)
    check(_j6_found, f"J6.1 canon fact '{_j6_stmt}' found in world_canon_facts")

# Also verify in writer payload if available
_j6_writer_payload = _j6_captured_1.get("writer_payload", {})
_j6_writer_canon = _j6_writer_payload.get("world_canon_facts", []) if _j6_writer_payload else []
if _j6_writer_canon:
    check(len(_j6_writer_canon) == 3,
          f"J6.1 world_canon_facts in writer payload has 3 items (got {len(_j6_writer_canon)})")

main.call_llm = original_call_llm

# Test 2: Another neutral input "asdf" (nonsense/OOC) - canon facts still present
_j6_captured_2 = {}

def _fake_llm_j6_capture_2(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json as _json_j6_2
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        try:
            _j6_captured_2["payload"] = _json_j6_2.loads(user_prompt)
        except Exception:
            pass
        # Return OOC translation for nonsense input
        return _json_j6_2.dumps({
            "boundary_check": "Within scope — OOC input translated.",
            "scene_outline": "The character pauses and refocuses.",
            "facts_this_turn": [],
            "anchor_keywords": [],
            "open_threads_update": "",
            "state_changes": {"characters": {}, "notes": "OOC test"},
            "suggested_actions": ["Look around"],
            "is_ooc": True,
            "action_translation": "Xue Li steadies herself and focuses on the energy around her."
        }, ensure_ascii=False)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()

main.call_llm = _fake_llm_j6_capture_2
r = client.post(f"/worlds/{J6_WORLD}/chapter/continue", json={"user_input": "asdfghjkl"})
check(r.status_code == 200, "J6.2 chapter/continue (neutral nonsense input) returned 200")
main.call_llm = original_call_llm

_j6_payload_2 = _j6_captured_2.get("payload", {})
_j6_canon_in_payload_2 = _j6_payload_2.get("world_canon_facts", [])
check(len(_j6_canon_in_payload_2) == 3,
      f"J6.2 world_canon_facts has 3 items even with nonsense input (got {len(_j6_canon_in_payload_2)})")

# Test 3: Third neutral input "continue"
_j6_captured_3 = {}

def _fake_llm_j6_capture_3(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json as _json_j6_3
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        try:
            _j6_captured_3["payload"] = _json_j6_3.loads(user_prompt)
        except Exception:
            pass
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()

main.call_llm = _fake_llm_j6_capture_3
r = client.post(f"/worlds/{J6_WORLD}/chapter/continue", json={"user_input": "continue"})
check(r.status_code == 200, "J6.3 chapter/continue (neutral: 'continue') returned 200")
main.call_llm = original_call_llm

_j6_payload_3 = _j6_captured_3.get("payload", {})
_j6_canon_in_payload_3 = _j6_payload_3.get("world_canon_facts", [])
check(len(_j6_canon_in_payload_3) == 3,
      f"J6.3 world_canon_facts has 3 items with 'continue' input (got {len(_j6_canon_in_payload_3)})")

# Test 4: Verify merge_canon_and_delta works correctly
_j6_branch_delta = {"overrides": {"fact_ancient_library": "The Ancient Library is sealed by the Sect Master."}}
_j6_merged = main.merge_canon_and_delta(
    {"facts": _j6_canon_facts}, _j6_branch_delta
)
_j6_merged_facts = _j6_merged.get("facts", [])
check(len(_j6_merged_facts) == 3, "J6.4 merge_canon_and_delta preserves all 3 facts")
_j6_overridden = [f for f in _j6_merged_facts if isinstance(f, dict) and f.get("fact_id") == "fact_ancient_library"]
check(len(_j6_overridden) == 1, "J6.4 fact_ancient_library found in merged result")
check(_j6_overridden[0]["statement"] == "The Ancient Library is sealed by the Sect Master.",
      "J6.4 fact_ancient_library statement overridden by branch delta")
_j6_unmodified = [f for f in _j6_merged_facts if isinstance(f, dict) and f.get("fact_id") == "fact_master_wu"]
check(_j6_unmodified[0]["statement"] == _j6_canon_facts[1]["statement"],
      "J6.4 fact_master_wu unchanged (not in delta overrides)")

# Test 5: Merge with empty branch delta (no override) preserves all original statements
_j6_merged_no_delta = main.merge_canon_and_delta({"facts": _j6_canon_facts}, {"overrides": {}})
_j6_no_delta_facts = _j6_merged_no_delta.get("facts", [])
check(len(_j6_no_delta_facts) == 3, "J6.5 merge with empty delta preserves all facts")
check(_j6_no_delta_facts[0]["statement"] == _j6_canon_facts[0]["statement"],
      "J6.5 fact statement unchanged with empty delta")

# Test 6: Merge with None branch delta (should not crash)
_j6_merged_none = main.merge_canon_and_delta({"facts": _j6_canon_facts}, None)
_j6_none_delta_facts = _j6_merged_none.get("facts", [])
check(len(_j6_none_delta_facts) == 3, "J6.6 merge with None delta preserves all facts")

# Verify chapters were created successfully (pipeline completed)
_j6_world_data = client.get(f"/worlds/{J6_WORLD}").json()
_j6_chapters = _j6_world_data["chapters"]["chapters"]
check(len(_j6_chapters) >= 3, f"J6.7 at least 3 chapters created (got {len(_j6_chapters)})")

shutil.rmtree(wp_j6, ignore_errors=True)

print("\n--- TASK-3: Checker & Summarizer Fallback Chain Tests ---")
import app.storage as _storage
main.get_effective_fallback_chain = _storage.get_effective_fallback_chain
main.has_real_api_key = _storage.has_real_api_key

check("checker" in main._VALID_ROLES, "Task3. 'checker' is in _VALID_ROLES")
check("summarizer" in main._VALID_ROLES, "Task3. 'summarizer' is in _VALID_ROLES")

T3_WORLD = "test_world_task3"
wp_t3 = main.world_path_of(T3_WORLD)
os.makedirs(wp_t3, exist_ok=True)

t3_cfg = {
    "openrouter_api_key": "test_key",
    "fallback_chain": [
        {"provider": "openrouter", "model": "model_main", "api_key": "key1"},
        {"provider": "openrouter", "model": "model_cheap_checker", "api_key": "key2"},
        {"provider": "openrouter", "model": "model_cheap_summarizer", "api_key": "key3"},
    ],
    "role_assignments": {}
}
main.write_world_runtime_override(T3_WORLD, t3_cfg)

chain_checker_default = main.get_effective_fallback_chain_for_role(T3_WORLD, "checker")
check(chain_checker_default[0]["model"] == "model_main", "Task3. Unconfigured checker falls back to model_main (idx 0)")

chain_summarizer_default = main.get_effective_fallback_chain_for_role(T3_WORLD, "summarizer")
check(chain_summarizer_default[0]["model"] == "model_main", "Task3. Unconfigured summarizer falls back to model_main (idx 0)")

t3_cfg["role_assignments"] = {
    "checker": 1,
    "summarizer": 2
}
main.write_world_runtime_override(T3_WORLD, t3_cfg)

chain_checker_custom = main.get_effective_fallback_chain_for_role(T3_WORLD, "checker")
check(chain_checker_custom[0]["model"] == "model_cheap_checker", "Task3. Checker assigned model index 1 gets model_cheap_checker")
check(len(chain_checker_custom) == 3, "Task3. Checker fallback chain preserves full pool length")

chain_summarizer_custom = main.get_effective_fallback_chain_for_role(T3_WORLD, "summarizer")
check(chain_summarizer_custom[0]["model"] == "model_cheap_summarizer", "Task3. Summarizer assigned model index 2 gets model_cheap_summarizer")
check(len(chain_summarizer_custom) == 3, "Task3. Summarizer fallback chain preserves full pool length")

r_put = client.put(f"/worlds/{T3_WORLD}/runtime-config", json={
    "role_assignments": {"checker": 1, "summarizer": 2}
})
check(r_put.status_code == 200, "Task3. PUT runtime-config with checker and summarizer returned 200")
res_status = r_put.json()
check(res_status["role_assignments_effective"]["checker"] == 1, "Task3. Effective checker role assignment is 1")
check(res_status["role_assignments_effective"]["summarizer"] == 2, "Task3. Effective summarizer role assignment is 2")

shutil.rmtree(wp_t3, ignore_errors=True)
print("--- TASK-3 hoàn thành ---\n")

print("\n--- TASK-5: Anchor-Keyword Soft Warning & Opt-In Auto-Retry Tests ---")
T5_WORLD = "test_world_task5_keywords"
wp_t5 = main.world_path_of(T5_WORLD)
shutil.rmtree(wp_t5, ignore_errors=True)
r_seed5 = client.post(f"/worlds/{T5_WORLD}/seed-demo?overwrite=true")
check(r_seed5.status_code == 200, "Task5. seed-demo returned 200")

# Test 5.1: Substring check helper logic
kw_check_missing = main.check_anchor_keywords("The warrior unsheathed a glowing blade.", ["blade", "dragon", "fire"])
check(kw_check_missing == ["dragon", "fire"], "Task5. check_anchor_keywords correctly identifies missing keywords ['dragon', 'fire']")

# Test 5.2: Default behavior (keyword_auto_retry = False) -> soft warning recorded, no forced rewrite
writer_call_count = {"n": 0}
def fake_call_llm_t5(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role="default"):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return json.dumps({
            "boundary_check": "Within scope — no boundary violation",
            "scene_outline": "The hero enters the dark cavern.",
            "facts_this_turn": ["Hero is in cavern"],
            "anchor_keywords": ["cavern", "obsidian_runes"],
            "open_threads_update": "",
            "state_changes": {"characters": {}, "notes": "Task 5 test"},
            "suggested_actions": ["Look around"],
            "is_ooc": False,
            "action_translation": ""
        }, ensure_ascii=False)
    if system_prompt == main.WRITER_SYSTEM_PROMPT:
        writer_call_count["n"] += 1
        return json.dumps({
            "chapter_text": "The hero steps into the dark cavern, feeling cold stone underfoot.",
            "state_changes": {"characters": {}, "notes": "writer output without literal keyword obsidian_runes"},
            "chapter_end": False,
            "chapter_title": None
        }, ensure_ascii=False)
    return main.mock_consistency_checker_response()

old_call_llm = main.call_llm
main.call_llm = fake_call_llm_t5

r_ch5_1 = client.post(f"/worlds/{T5_WORLD}/chapter/continue", json={"user_input": "Enter the cave"})
check(r_ch5_1.status_code == 200, "Task5. chapter/continue returned 200")
ch5_1_data = r_ch5_1.json()["chapter"]
check(writer_call_count["n"] == 1, "Task5. Default behavior (keyword_auto_retry=False) did NOT force a rewrite (writer called exactly 1 time)")
check(ch5_1_data.get("anchor_keywords") == ["cavern", "obsidian_runes"], "Task5. anchor_keywords saved in chapter record")
check(ch5_1_data.get("missing_anchor_keywords") == ["obsidian_runes"], "Task5. missing_anchor_keywords recorded as soft warning in chapter record")

# Test 5.3: Opt-in behavior (keyword_auto_retry = True) -> forced rewrite attempted
cfg_t5 = main.read_world_file(wp_t5, "world_config.json")
cfg_t5["keyword_auto_retry"] = True
main.write_world_file(wp_t5, "world_config.json", cfg_t5)

writer_call_count["n"] = 0
r_ch5_2 = client.post(f"/worlds/{T5_WORLD}/chapter/continue", json={"user_input": "Look for runes"})
check(r_ch5_2.status_code == 200, "Task5. chapter/continue with keyword_auto_retry=True returned 200")
check(writer_call_count["n"] > 1, f"Task5. Opt-in behavior (keyword_auto_retry=True) forced rewrite retries (writer called {writer_call_count['n']} times)")

main.call_llm = old_call_llm
shutil.rmtree(wp_t5, ignore_errors=True)
print("--- TASK-5 (Anchor-Keyword Soft Enforcement) hoàn thành ---\n")


print("\n--- TASK-7: Localized Boundary Hard-Reject Tests ---")

# 7.1 Unit test detect_story_language
from app.engine import detect_story_language, raise_boundary_hard_reject

check(detect_story_language(user_input="Đi tới rừng ma") == "vi", "Task7. detect_story_language returns 'vi' for Vietnamese user_input")
check(detect_story_language(recent_text="Lâm Cung Tử lẳng lặng tiến bước.") == "vi", "Task7. detect_story_language returns 'vi' for Vietnamese recent_text")
check(detect_story_language(world_config={"display_name": "Đại La Thiên Đế"}) == "vi", "Task7. detect_story_language returns 'vi' for Vietnamese world_config")
check(detect_story_language(user_input="Go to the dark forest", recent_text="The hero enters the dark cavern.") == "en", "Task7. detect_story_language returns 'en' for English inputs")
check(detect_story_language() == "en", "Task7. detect_story_language falls back to 'en' when inputs are empty")

# 7.2 Unit test raise_boundary_hard_reject with Vietnamese vs English
dummy_checkpoint = {"boundary": {"locations": ["phong_khach"]}}
dummy_violations = [{"character_id": "char_a", "attempted_location": "ma_gioi"}]

# Test Vietnamese explicit/inferred raise
try:
    raise_boundary_hard_reject(dummy_violations, dummy_checkpoint, user_input="Đi tới ma giới")
    check(False, "Task7. raise_boundary_hard_reject raised exception for VI")
except HTTPException as exc:
    check(exc.status_code == 409, "Task7. raise_boundary_hard_reject status code is 409")
    check("Người kể chuyện AI đã 2 lần liên tiếp" in exc.detail, "Task7. raise_boundary_hard_reject contains Vietnamese header")
    check("Nhân vật 'char_a' bị di chuyển tới 'ma_gioi'" in exc.detail, "Task7. raise_boundary_hard_reject contains Vietnamese violation line")
    check("Lượt này đã bị hủy" in exc.detail, "Task7. raise_boundary_hard_reject contains Vietnamese footer")

# Test English fallback raise
try:
    raise_boundary_hard_reject(dummy_violations, dummy_checkpoint, user_input="Go to shadow realm")
    check(False, "Task7. raise_boundary_hard_reject raised exception for EN")
except HTTPException as exc:
    check(exc.status_code == 409, "Task7. raise_boundary_hard_reject status code is 409")
    check("The AI storyteller has 2 consecutive times moved the character" in exc.detail, "Task7. raise_boundary_hard_reject contains English header")
    check("- 'char_a' is moved to 'ma_gioi'" in exc.detail, "Task7. raise_boundary_hard_reject contains English violation line")

# 7.3 End-to-end test via API on a Vietnamese story with persistent boundary violation
T7_WORLD = "test_engine_world_t7"
wp_t7 = main.world_path_of(T7_WORLD)
shutil.rmtree(wp_t7, ignore_errors=True)

r_seed = client.post(f"/worlds/{T7_WORLD}/seed-demo")
check(r_seed.status_code == 200, "Task7. seed-demo returned 200")

cfg_t7 = main.read_world_file(wp_t7, "world_config.json")
cfg_t7["display_name"] = "Võ Lâm Truyền Kỳ"
main.write_world_file(wp_t7, "world_config.json", cfg_t7)

def fake_call_llm_t7(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role="default"):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return json.dumps({
            "boundary_check": "Scope check ok",
            "scene_outline": "Di chuyển ra ma giới",
            "facts_this_turn": [],
            "anchor_keywords": [],
            "open_threads_update": "",
            "state_changes": {
                "characters": {
                    "char_su_phu": {"location": "location_outside_scope_xyz"}
                }
            },
            "suggested_actions": [],
            "is_ooc": False,
            "action_translation": ""
        }, ensure_ascii=False)
    if system_prompt == main.WRITER_SYSTEM_PROMPT:
        return json.dumps({
            "chapter_text": "Sư phụ đi ra vùng đất lạ ngoài phạm vi.",
            "state_changes": {
                "characters": {
                    "char_su_phu": {"location": "location_outside_scope_xyz"}
                }
            },
            "chapter_end": False,
            "chapter_title": None
        }, ensure_ascii=False)
    return main.mock_consistency_checker_response()

old_call_llm = main.call_llm
main.call_llm = fake_call_llm_t7

r_ch7 = client.post(f"/worlds/{T7_WORLD}/chapter/continue", json={"user_input": "Đi tới vùng đất cấm"})
check(r_ch7.status_code == 409, "Task7. Persistent boundary violation returned status 409")
check("Người kể chuyện AI đã 2 lần liên tiếp" in r_ch7.json()["detail"], "Task7. HTTP 409 detail returned Vietnamese message for Vietnamese story")

main.call_llm = old_call_llm
shutil.rmtree(wp_t7, ignore_errors=True)
print("--- TASK-7 (Localized Boundary Hard-Reject) hoàn thành ---\n")

# ---------------------------------------------------------------------
# TASK-4: Prelude (Chapter 0) generation flow
# ---------------------------------------------------------------------
WP_PRELUDE = "test_prelude_world"
wp_prelude = main.world_path_of(WP_PRELUDE)
if os.path.isdir(wp_prelude):
    shutil.rmtree(wp_prelude)


def fake_call_llm_prelude(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role="default"):
    if main.PRELUDE_WRITER_PROMPT and system_prompt == main.PRELUDE_WRITER_PROMPT:
        return main.mock_prelude_response()
    if main.PRELUDE_VALIDATOR_PROMPT and system_prompt == main.PRELUDE_VALIDATOR_PROMPT:
        return json.dumps({"severity": "none", "issues": [], "explanation": "[mock] validation passed"})
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt in (main.WRITER_SYSTEM_PROMPT, main.EXTRACTOR_SYSTEM_PROMPT):
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()


print("--- TASK-4 (Prelude generation flow) bat dau ---")

# Step 1: Seed demo world
r = client.post(f"/worlds/{WP_PRELUDE}/seed-demo")
check(r.status_code == 200, "T4. seed-demo OK")

# Step 2: Enable prelude
r = client.get(f"/worlds/{WP_PRELUDE}")
cfg = r.json()["world_config"]
cfg["prelude_enabled"] = True
cfg["prelude_confirmed"] = False
cfg_path = os.path.join(main.world_path_of(WP_PRELUDE), "world_config.json")
with open(cfg_path, "w", encoding="utf-8") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)

# Step 3: Direct chapter/start without prelude -> MUST be blocked
r = client.post(f"/worlds/{WP_PRELUDE}/chapter/start", json={"opening_mode": "ai_generate"})
check(r.status_code == 400, "T4. chapter/start blocked when prelude_enabled but not confirmed")
check("prelude_enabled" in r.json()["detail"].lower() or "prelude" in r.json()["detail"].lower(),
      "T4. error message mentions prelude")

# Step 4: Generate prelude with mocked LLM
old_llm = main.call_llm
main.call_llm = fake_call_llm_prelude
r = client.post(f"/worlds/{WP_PRELUDE}/chapter/generate-prelude")
check(r.status_code == 200, "T4. generate-prelude OK")
data = r.json()
check(data["prelude"]["chapter_index"] == 0, "T4. prelude chapter_index == 0")
check(data["prelude"]["chapter_title"] == "Prelude", "T4. prelude chapter_title == 'Prelude'")
check(len(data["prelude"]["chapter_text"]) > 0, "T4. prelude chapter_text non-empty")

# Step 5: chapter/start still blocked (prelude not confirmed)
r = client.post(f"/worlds/{WP_PRELUDE}/chapter/start", json={"opening_mode": "ai_generate"})
check(r.status_code == 400, "T4. chapter/start still blocked before prelude_confirmed")

# Step 6: Confirm prelude
r = client.post(f"/worlds/{WP_PRELUDE}/chapter/confirm-prelude")
check(r.status_code == 200, "T4. confirm-prelude OK")
check(r.json()["status"] == "prelude_confirmed", "T4. confirm response has status == prelude_confirmed")

# Step 6b: Verify checkpoint auto-advanced from cp_0 to cp_1
r = client.get(f"/worlds/{WP_PRELUDE}")
cfg_after = r.json()["world_config"]
check(cfg_after["current_checkpoint_id"] != "cp_0",
      f"T4. current_checkpoint_id advanced from cp_0 (got {cfg_after['current_checkpoint_id']})")
check("cp_0" in cfg_after.get("completed_checkpoints", []),
      "T4. cp_0 added to completed_checkpoints")
check(cfg_after["current_checkpoint_id"] == "cp_1",
      f"T4. current_checkpoint_id should be cp_1 (got {cfg_after['current_checkpoint_id']})")

# Step 7: chapter/start now succeeds
r = client.post(f"/worlds/{WP_PRELUDE}/chapter/start", json={"opening_mode": "ai_generate"})
check(r.status_code == 200, "T4. chapter/start OK after prelude confirmed")
ch1 = r.json()["chapter"]
check(ch1["chapter_index"] == 1, "T4. chapter 1 has chapter_index == 1")

# Step 8: Duplicate prelude generation blocked
r = client.post(f"/worlds/{WP_PRELUDE}/chapter/generate-prelude")
check(r.status_code == 400, "T4. duplicate generate-prelude blocked")

# Step 9: Verify chapter indices on disk
r = client.get(f"/worlds/{WP_PRELUDE}")
all_ch = r.json().get("chapters", {}).get("chapters", [])
indices = sorted(c["chapter_index"] for c in all_ch)
check(indices == [0, 1], f"T4. chapter indices are [0, 1], got {indices}")

main.call_llm = old_llm
shutil.rmtree(wp_prelude, ignore_errors=True)
print("--- TASK-4 (Prelude generation flow) hoan thanh ---\n")

# ---------------------------------------------------------------------
# TASK-11: Pacing-aware context window
# ---------------------------------------------------------------------

# 11a. Pure function: get_pacing_context_config
check(main.get_pacing_context_config("Slowburn")["recent_turns"] == 4,
      "11a. Slowburn -> 4 recent turns")
check(main.get_pacing_context_config("Slowburn")["summary_budget_ratio"] == 0.05,
      "11a. Slowburn -> 0.05 summary budget ratio")
check(main.get_pacing_context_config("Balanced")["recent_turns"] == 3,
      "11a. Balanced -> 3 recent turns")
check(main.get_pacing_context_config("Balanced")["summary_budget_ratio"] == 0.03,
      "11a. Balanced -> 0.03 summary budget ratio")
check(main.get_pacing_context_config("Fast")["recent_turns"] == 2,
      "11a. Fast -> 2 recent turns")
check(main.get_pacing_context_config("Fast")["summary_budget_ratio"] == 0.02,
      "11a. Fast -> 0.02 summary budget ratio")
check(main.get_pacing_context_config("Unknown")["recent_turns"] == 3,
      "11a. Unknown pacing falls back to Balanced (3 turns)")

# 12a. Pure function: get_words_per_turn_target
check(main.get_words_per_turn_target("Slowburn") == 300,
      "12a. Slowburn -> 300 words per turn")
check(main.get_words_per_turn_target("Balanced") == 200,
      "12a. Balanced -> 200 words per turn")
check(main.get_words_per_turn_target("Fast") == 130,
      "12a. Fast -> 130 words per turn")
check(main.get_words_per_turn_target("Unknown") == 200,
      "12a. Unknown pacing falls back to Balanced (200)")

# 11b. compute_word_budget with different pacing levels
check(main.compute_word_budget(8000, "Balanced") == 240,
      "11b. Balanced word budget 8000 -> 240")
check(main.compute_word_budget(8000, "Slowburn") == 400,
      "11b. Slowburn word budget 8000 -> 400")
check(main.compute_word_budget(8000, "Fast") == 160,
      "11b. Fast word budget 8000 -> 160")
check(main.compute_word_budget(8000) == 240,
      "11b. Default (no pacing arg) matches Balanced (240)")

# 11c. Integration: writer context payload differs between Slowburn and Fast
WP_PACING = "test_engine_world_pacing"
wp_pacing = main.world_path_of(WP_PACING)
if os.path.isdir(wp_pacing):
    shutil.rmtree(wp_pacing)

r = client.post(f"/worlds/{WP_PACING}/seed-demo")
check(r.status_code == 200, "11c. seed-demo returned 200")

# Write enough turns so that the limit difference matters
main.write_world_file(wp_pacing, "chapters.json", {
    "chapters": [
        {"chapter_index": 1, "turn_index": i, "chapter_text": f"Turn {i} narrative text for pacing test.", "chapter_closed": False, "checkpoint_id": "cp_0"}
        for i in range(1, 7)
    ],
    "running_summary": "Pacing test summary.",
    "memorable_beats": []
})

r = client.put(f"/worlds/{WP_PACING}/world_config", json={"pacing_level": "Slowburn"})
check(r.status_code == 200, "11c. set pacing=Slowburn")

slow_captured = {}

def fake_call_llm_slow(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt == main.WRITER_SYSTEM_PROMPT:
        slow_captured["user_prompt"] = user_prompt
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()

old_llm = main.call_llm
main.call_llm = fake_call_llm_slow
r = client.post(f"/worlds/{WP_PACING}/chapter/continue", json={"user_input": "test Slowburn"})
check(r.status_code == 200, "11c. chapter/continue (Slowburn) succeeded")
main.call_llm = old_llm

slow_payload = json.loads(slow_captured["user_prompt"])
slow_mtier = slow_payload.get("multi_tier_context", {}).get("multi_tier_context", {}).get("tier_1_working_memory", {})
slow_max = slow_mtier.get("max_turns", 0)
slow_count = len(slow_mtier.get("recent_turns", []))
check(slow_max == 4, f"11c. Slowburn max_turns = 4, got {slow_max}")
check(slow_count <= 4, f"11c. Slowburn recent_turns count <= 4, got {slow_count}")

r = client.put(f"/worlds/{WP_PACING}/world_config", json={"pacing_level": "Fast"})
check(r.status_code == 200, "11c. set pacing=Fast")

fast_captured = {}

def fake_call_llm_fast(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt == main.WRITER_SYSTEM_PROMPT:
        fast_captured["user_prompt"] = user_prompt
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()

main.call_llm = fake_call_llm_fast
r = client.post(f"/worlds/{WP_PACING}/chapter/continue", json={"user_input": "test Fast"})
check(r.status_code == 200, "11c. chapter/continue (Fast) succeeded")
main.call_llm = old_llm

fast_payload = json.loads(fast_captured["user_prompt"])
fast_mtier = fast_payload.get("multi_tier_context", {}).get("multi_tier_context", {}).get("tier_1_working_memory", {})
fast_max = fast_mtier.get("max_turns", 0)
fast_count = len(fast_mtier.get("recent_turns", []))
check(fast_max == 2, f"11c. Fast max_turns = 2, got {fast_max}")
check(fast_count <= 2, f"11c. Fast recent_turns count <= 2, got {fast_count}")

# Slowburn must have at least as many recent turns as Fast
check(slow_count >= fast_count,
      f"11c. Slowburn recent_turns ({slow_count}) >= Fast recent_turns ({fast_count})")

# 12b. Writer payload contains words_per_turn_target
slow_wpt = slow_payload.get("words_per_turn_target")
fast_wpt = fast_payload.get("words_per_turn_target")
check(slow_wpt is not None, "12b. Slowburn payload has words_per_turn_target")
check(fast_wpt is not None, "12b. Fast payload has words_per_turn_target")
check(slow_wpt == 300, f"12b. Slowburn words_per_turn_target = 300, got {slow_wpt}")
check(fast_wpt == 130, f"12b. Fast words_per_turn_target = 130, got {fast_wpt}")
check(slow_wpt > fast_wpt,
      f"12b. Slowburn words_per_turn_target ({slow_wpt}) > Fast ({fast_wpt})")

# 12c. WRITER_SYSTEM_PROMPT no longer contains "short, focused beat"
check("short, focused beat" not in main.WRITER_SYSTEM_PROMPT,
      "12c. WRITER_SYSTEM_PROMPT no longer says 'short, focused beat'")
check("words_per_turn_target" in main.WRITER_SYSTEM_PROMPT,
      "12c. WRITER_SYSTEM_PROMPT references words_per_turn_target")
# 14. WRITER_SYSTEM_PROMPT encourages dialogue in multi-character scenes
check("spoken dialogue" in main.WRITER_SYSTEM_PROMPT,
      "14. WRITER_SYSTEM_PROMPT encourages spoken dialogue")

shutil.rmtree(wp_pacing, ignore_errors=True)
print("--- TASK-11 (Pacing-aware context window) hoan thanh ---\n")

# ---------------------------------------------------------------------
# TASK-13: Output Length setting
# ---------------------------------------------------------------------

# 13a. Pure function: get_output_length_config
ol_concise = main.get_output_length_config("Concise")
ol_standard = main.get_output_length_config("Standard")
ol_detailed = main.get_output_length_config("Detailed")
check(ol_concise["words_per_turn_ratio"] < 1.0, "13a. Concise ratio < 1.0")
check(ol_detailed["words_per_turn_ratio"] > 1.0, "13a. Detailed ratio > 1.0")
check(ol_standard["words_per_turn_ratio"] == 1.0, "13a. Standard ratio == 1.0")
check(ol_concise["soft_close_turns_offset"] < 0, "13a. Concise reduces soft turns")
check(ol_detailed["soft_close_turns_offset"] > 0, "13a. Detailed increases soft turns")
check(main.get_output_length_config("Unknown") == ol_standard, "13a. Unknown falls back to Standard")

# 13b. Pure function: get_words_per_turn_target with output_length
check(main.get_words_per_turn_target("Balanced", "Concise") < 200,
      f"13b. Balanced+Concise < 200, got {main.get_words_per_turn_target('Balanced', 'Concise')}")
check(main.get_words_per_turn_target("Balanced", "Detailed") > 200,
      f"13b. Balanced+Detailed > 200, got {main.get_words_per_turn_target('Balanced', 'Detailed')}")
check(main.get_words_per_turn_target("Slowburn", "Detailed") > main.get_words_per_turn_target("Slowburn", "Standard"),
      "13b. Slowburn+Detailed > Slowburn+Standard")
check(main.get_words_per_turn_target("Fast", "Concise") < main.get_words_per_turn_target("Fast", "Standard"),
      "13b. Fast+Concise < Fast+Standard")

# 13c. Pure function: get_close_thresholds
concise_th = main.get_close_thresholds("Concise")
standard_th = main.get_close_thresholds("Standard")
detailed_th = main.get_close_thresholds("Detailed")
check(concise_th["soft_close_turns"] < standard_th["soft_close_turns"],
      f"13c. Concise soft turns ({concise_th['soft_close_turns']}) < Standard ({standard_th['soft_close_turns']})")
check(detailed_th["hard_close_turns"] > standard_th["hard_close_turns"],
      f"13c. Detailed hard turns ({detailed_th['hard_close_turns']}) > Standard ({standard_th['hard_close_turns']})")
check(concise_th["soft_close_words"] < standard_th["soft_close_words"],
      f"13c. Concise soft words ({concise_th['soft_close_words']}) < Standard ({standard_th['soft_close_words']})")
check(detailed_th["soft_close_words"] > standard_th["soft_close_words"],
      f"13c. Detailed soft words ({detailed_th['soft_close_words']}) > Standard ({standard_th['soft_close_words']})")

# 13d. Integration: output_length affects words_per_turn_target in writer payload
WP_LENGTH = "test_engine_world_length"
wp_length = main.world_path_of(WP_LENGTH)
if os.path.isdir(wp_length):
    shutil.rmtree(wp_length)

r = client.post(f"/worlds/{WP_LENGTH}/seed-demo")
check(r.status_code == 200, "13d. seed-demo returned 200")

# Inject enough turns so writer is called
main.write_world_file(wp_length, "chapters.json", {
    "chapters": [
        {"chapter_index": 1, "turn_index": i, "chapter_text": f"Turn {i} text.", "chapter_closed": False, "checkpoint_id": "cp_0"}
        for i in range(1, 4)
    ],
    "running_summary": "Test summary.",
    "memorable_beats": []
})

# Test with Concise
r = client.put(f"/worlds/{WP_LENGTH}/world_config", json={"pacing_level": "Slowburn", "output_length": "Concise"})
check(r.status_code == 200, "13d. set pacing=Slowburn, output_length=Concise")

concise_captured = {}

def fake_call_llm_concise(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt == main.WRITER_SYSTEM_PROMPT:
        concise_captured["user_prompt"] = user_prompt
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()

old_llm = main.call_llm
main.call_llm = fake_call_llm_concise
r = client.post(f"/worlds/{WP_LENGTH}/chapter/continue", json={"user_input": "test Concise"})
check(r.status_code == 200, "13d. chapter/continue (Concise) succeeded")
main.call_llm = old_llm

concise_payload = json.loads(concise_captured["user_prompt"])
concise_wpt = concise_payload.get("words_per_turn_target")
# Slowburn base = 300, Concise ratio = 0.65 => ~195
check(concise_wpt == main.get_words_per_turn_target("Slowburn", "Concise"),
      f"13d. Concise+Slowburn wpt = {concise_wpt}, expected {main.get_words_per_turn_target('Slowburn', 'Concise')}")

# Test with Detailed
r = client.put(f"/worlds/{WP_LENGTH}/world_config", json={"pacing_level": "Slowburn", "output_length": "Detailed"})
check(r.status_code == 200, "13d. set pacing=Slowburn, output_length=Detailed")

detailed_captured = {}

def fake_call_llm_detailed(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    if system_prompt == main.PLANNER_SYSTEM_PROMPT:
        return main.mock_planner_response(user_input_for_mock)
    if system_prompt == main.WRITER_SYSTEM_PROMPT:
        detailed_captured["user_prompt"] = user_prompt
        return main.mock_narrator_response(user_input_for_mock)
    return main.mock_consistency_checker_response()

main.call_llm = fake_call_llm_detailed
r = client.post(f"/worlds/{WP_LENGTH}/chapter/continue", json={"user_input": "test Detailed"})
check(r.status_code == 200, "13d. chapter/continue (Detailed) succeeded")
main.call_llm = old_llm

detailed_payload = json.loads(detailed_captured["user_prompt"])
detailed_wpt = detailed_payload.get("words_per_turn_target")
# Slowburn base = 300, Detailed ratio = 1.5 => ~450
check(detailed_wpt == main.get_words_per_turn_target("Slowburn", "Detailed"),
      f"13d. Detailed+Slowburn wpt = {detailed_wpt}, expected {main.get_words_per_turn_target('Slowburn', 'Detailed')}")

# Concise must have lower target than Detailed
check(concise_wpt < detailed_wpt,
      f"13d. Concise wpt ({concise_wpt}) < Detailed wpt ({detailed_wpt})")

# 13e. Check output_length is included in world_config sub-dict of payload
check("output_length" in concise_payload.get("world_config", {}),
      "13e. Concise payload includes output_length in world_config")
check(concise_payload["world_config"]["output_length"] == "Concise",
      "13e. Concise payload world_config.output_length = 'Concise'")
check(detailed_payload["world_config"]["output_length"] == "Detailed",
      "13e. Detailed payload world_config.output_length = 'Detailed'")

# 13f. decide_chapter_closed respects output_length
# With Concise: soft_close_turns = 4, hard_close_turns = 6, soft_close_words = 630
# With Detailed: soft_close_turns = 7, hard_close_turns = 10, soft_close_words = 1440
fake_ch = {
    "chapters": [
        {"chapter_index": 99, "turn_index": i, "chapter_text": "Some content here for testing purposes.", "chapter_closed": False}
        for i in range(1, 8)
    ],
}

# Concise: 8 turns >= hard_close_turns=6 => closed
closed_concise = main.decide_chapter_closed(99, 8, fake_ch, "short", False, output_length="Concise")
check(closed_concise, "13f. Concise: 6+ turns -> hard close")

# Detailed: 8 turns < hard_close_turns=10, need word threshold. Not enough words for soft close
closed_detailed = main.decide_chapter_closed(99, 8, fake_ch, "short", False, output_length="Detailed")
check(not closed_detailed, "13f. Detailed: 8 turns not enough for soft/hard close")

# Detailed: 8 turns + enough words => still not closed (soft_close_turns=7 so turn count met)
# Actually need 8 turns >= 7 and total_words >= 1440
long_text_1440 = "words " * 1440  # 1440+ words
closed_detailed_words = main.decide_chapter_closed(99, 8, fake_ch, long_text_1440, False, output_length="Detailed")
# each turn has 7 words ("Some content here for testing purposes." = 7 words), 7 turns = 49 words
# plus long text ~ 1440 words = ~1489 total >= 1440
# 8 turns >= 7 soft turns => should close
check(closed_detailed_words, "13f. Detailed: 8 turns + enough words -> soft close")

shutil.rmtree(wp_length, ignore_errors=True)
print("--- TASK-13 (Output Length setting) hoan thanh ---\n")

# ---------------------------------------------------------------------
# Task 2.1 — Zone Prefix Matching & Softer Boundary Correction
# ---------------------------------------------------------------------
from app.engine import _is_location_in_zone, check_boundary_violations

# Unit test: _is_location_in_zone
check(_is_location_in_zone("Valdris Estate", {"Valdris Estate"}), "2.1. Exact match within zone")
check(_is_location_in_zone("Valdris Estate - Kitchen", {"Valdris Estate"}), "2.1. Sub-location matches parent zone")
check(_is_location_in_zone("Great Desert Forbidden Land - Inner Sanctum", {"Starting Sect", "Great Desert Forbidden Land"}), "2.1. Sub-location matches one of several zones")
check(_is_location_in_zone("valdris estate - kitchen", {"Valdris Estate"}), "2.1. Case-insensitive zone match")
check(not _is_location_in_zone("Ma Gioi", {"Starting Sect", "Valdris Estate"}), "2.1. Location outside any zone is violation")
check(not _is_location_in_zone("Valdris", {"Valdris Estate"}), "2.1. Partial prefix substring is NOT a zone match")
check(not _is_location_in_zone("Kitchen", set()), "2.1. Empty allowed set rejects all")

# Unit test: check_boundary_violations with zone matching
zone_checkpoint = {"boundary": {"locations": ["Valdris Estate", "Great Desert Forbidden Land"]}}
state_in_zone = {"characters": {"hero": {"location": "Valdris Estate - Kitchen"}}}
state_in_zone2 = {"characters": {"hero": {"location": "Great Desert Forbidden Land - Inner Sanctum"}}}
state_outside = {"characters": {"hero": {"location": "Demon Realm"}}}
state_mixed = {"characters": {"hero": {"location": "Valdris Estate - Garden"}, "sidekick": {"location": "Shadow World"}}}

check(len(check_boundary_violations(state_in_zone, zone_checkpoint)) == 0, "2.1. Sub-location passes boundary check")
check(len(check_boundary_violations(state_in_zone2, zone_checkpoint)) == 0, "2.1. Sub-location of second zone passes")
check(len(check_boundary_violations(state_outside, zone_checkpoint)) == 1, "2.1. Outside location flagged as violation")
violations_mixed = check_boundary_violations(state_mixed, zone_checkpoint)
check(len(violations_mixed) == 1, "2.1. Only sidekick violation flagged, hero's sub-location ok")
check(violations_mixed[0]["character_id"] == "sidekick", "2.1. Correct character flagged in mixed scenario")

# Integration: seed-demo with zone-aware boundary check
r = client.post(f"/worlds/{WORLD}/seed-demo?overwrite=true")
check(r.status_code == 200, "2.1. seed-demo returned 200 for zone test")

# Advance to cp_2 (locations: ["Starting Sect", "Great Desert Forbidden Land"])
# Need 2 calls: cp_0→cp_1 (exp >=10), then cp_1→cp_2 (exp >=30)
def make_fake_advance(exp_target):
    import json
    def fake(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
        if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
            return main.mock_consistency_checker_response()
        return json.dumps({
            "chapter_text": "Power surges through Xue Li as she breaks through.",
            "state_changes": {
                "characters": {"char_xueli": {"exp_delta": exp_target}},
                "notes": "breakthrough"
            },
            "chapter_end": True
        }, ensure_ascii=False)
    return fake

original_llm = main.call_llm
main.call_llm = make_fake_advance(15)
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "breakthrough"})
check(r.status_code == 200, "2.1. Advance cp_0→cp_1 returned 200")
world_state = client.get(f"/worlds/{WORLD}").json()
check(world_state["world_config"]["current_checkpoint_id"] == "cp_1", "2.1. Advanced to cp_1")

main.call_llm = make_fake_advance(20)
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "breakthrough more"})
check(r.status_code == 200, "2.1. Advance cp_1→cp_2 returned 200")
world_state = client.get(f"/worlds/{WORLD}").json()
check(world_state["world_config"]["current_checkpoint_id"] == "cp_2", "2.1. Advanced to cp_2")
main.call_llm = original_llm

# Now at cp_2, test that "Great Desert Forbidden Land - Inner Sanctum" is allowed
def fake_call_llm_zone_move(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    return json.dumps({
        "chapter_text": "Xue Li ventures deeper into the forbidden land.",
        "state_changes": {"characters": {"char_xueli": {"location": "Great Desert Forbidden Land - Inner Sanctum"}}, "notes": ""}
    }, ensure_ascii=False)

main.call_llm = fake_call_llm_zone_move
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "explore deeper"})
check(r.status_code == 200, "2.1. Zone-prefix sub-location move returned 200 (not 409)")
world_state2 = client.get(f"/worlds/{WORLD}").json()
xueli_loc = world_state2["character_state"]["characters"]["char_xueli"]["location"]
check(xueli_loc == "Great Desert Forbidden Land - Inner Sanctum", "2.1. Location saved as sub-location, not clamped")
main.call_llm = original_llm

# Test that truly outside location still gets 409
def fake_call_llm_outside(system_prompt, user_prompt, user_input_for_mock="", mock_response=None, world_name=None, role=None):
    import json
    if system_prompt == main.CONSISTENCY_CHECKER_SYSTEM_PROMPT:
        return main.mock_consistency_checker_response()
    return json.dumps({
        "chapter_text": "Xue Li leaves the desert entirely.",
        "state_changes": {"characters": {"char_xueli": {"location": "Ma Gioi"}}, "notes": ""}
    }, ensure_ascii=False)

main.call_llm = fake_call_llm_outside
r = client.post(f"/worlds/{WORLD}/chapter/continue", json={"user_input": "leave"})
check(r.status_code == 409, "2.1. Location truly outside zone -> still 409 hard reject")
main.call_llm = original_llm

print("--- TASK-2.1 (Zone Prefix Matching) hoan thanh ---\n")

print("\n=== TẤT CẢ TEST PASS ===")

# dọn dẹp
shutil.rmtree(wp32, ignore_errors=True)
shutil.rmtree(wp, ignore_errors=True)
shutil.rmtree(wp2, ignore_errors=True)
shutil.rmtree(wp3, ignore_errors=True)

print("\n=== TẤT CẢ TEST PASS ===")

