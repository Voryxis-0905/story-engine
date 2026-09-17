# Story Engine — Master Plan: Redesign & Remaining Fixes

Tài liệu này tổng hợp toàn bộ những gì đã bàn: bug còn tồn đọng cần fix, và hướng redesign để giải quyết tận gốc vấn đề "bị bó" trong lối chơi. Chia làm 4 nhóm theo mức độ ưu tiên.

---

## Nhóm 1 — Bug tồn đọng, cần fix trước (không phụ thuộc redesign)

### 1.1 — Revert `checkpoint_conditions_met()` bị gutted về `return True`
Hàm này đã bị comment out logic thật, thay bằng `return True` cứng — vô hiệu hóa hoàn toàn Task 3 (Round 1). Cần revert lại logic gốc.

### 1.2 — Root cause thật của việc "kẹt checkpoint": field path ma trong `required_conditions`
AI generate world đôi khi tự bịa field không tồn tại (ví dụ `kaius_dravith.stats.shadow_power` trong khi schema thật chỉ có `power_stat.exp`, `power_stat.realm`). Cần:
- Sửa `WORLD_BUILDER_SKELETON_PROMPT`: liệt kê rõ các field hợp lệ trong `character_state` (`power_stat.exp`, `power_stat.realm`, `knowledge_flags`, `karma`, `inventory`), cấm bịa field mới.
- Thêm bước validate sau khi world generate xong: kiểm tra từng `required_conditions` field path có thật sự resolve được không, nếu không thì tự sửa/cảnh báo thay vì để checkpoint kẹt vĩnh viễn không rõ lý do.

### 1.3 — Safety net: chặn sớm khi checkpoint boundary rỗng hoàn toàn
Nếu checkpoint hiện tại có `locations: []` VÀ `allowed_characters: []` (kiểu checkpoint chuyển tiếp/backstory, không có gì để tương tác) — chặn ngay từ đầu, KHÔNG gọi LLM, trả lỗi tức thì giải thích rõ lý do. Tránh tình huống đốt token vô ích qua nhiều lần retry writer stage khi chắc chắn sẽ fail.

### 1.4 — Auto-advance `current_checkpoint_id` sau khi confirm prelude
`chapter_confirm_prelude()` hiện chỉ set `prelude_confirmed = True`, không đẩy `current_checkpoint_id` từ cp_0 (nội dung đã dùng cho prelude) sang checkpoint kế tiếp thật sự (nơi có boundary/nhân vật hợp lệ để chơi). Đây chính là nguyên nhân trực tiếp gây ra bug 1.3 xảy ra ngay từ turn đầu tiên sau prelude.

### 1.5 — `relationships` bị lưu thành object lồng nhau → hiện `[object Object]`
Bước "characters" trong world creation không ép kiểu string cho từng value trong `relationships`, khác với runtime path (`relationships_update`) đã làm đúng. Cần: (a) sửa `WORLD_BUILDER_CHARACTERS_PROMPT` cho ví dụ rõ value phải là string, (b) thêm dòng ép kiểu phòng thủ trong `builder_routes.py`.

### 1.6 — Codex "Affinity Network" đọc sai field, không bao giờ vẽ được đường nối
Frontend đọc `c.affinity` (luôn rỗng `{}` trong thực tế) thay vì `c.relationships` (nơi dữ liệu quan hệ thật sự nằm). Sửa lại đúng field, và đổi cách vẽ đường nối dựa theo có tồn tại quan hệ (thay vì dựa vào giá trị số như hiện tại thiết kế cho `affinity`).

---

## Nhóm 2 — Đổi triết lý checkpoint (không cần đổi kiến trúc dữ liệu, chỉ đổi cách viết prompt)

**Vấn đề gốc:** checkpoint hiện tại là "cái lồng" — AI bị buộc phải bịa lý do (hộ vệ chặn đường, chướng ngại giả) để giữ nhân vật trong phạm vi cho phép, kể cả khi nhân vật (ví dụ 1 Thiên Ma toàn năng) đáng lẽ không có gì thực sự cản được. Điều này mâu thuẫn trực tiếp với premise của nhiều world (power fantasy, nhân vật chủ động).

**Hướng sửa:**
- Sửa `WORLD_BUILDER_SKELETON_PROMPT`: khi viết mô tả checkpoint, checkpoint nên là **mục tiêu nhân vật có động lực nội tại để theo đuổi** (vd "hắn CHỌN ở lại vì cần ổn định thân xác trước khi ra tay"), không phải nơi bị nhốt vô lý do.
- Sửa `check_boundary_violations()`: thay vì so khớp string y hệt cho `locations`, dùng so khớp theo tiền tố/khu vực (vd `"Valdris Estate - Kitchen"` nên được coi là hợp lệ nếu `allowed_locations` có `"Valdris Estate - Servant Quarters"`, vì cùng thuộc `"Valdris Estate"`) — tránh việc di chuyển hợp lý trong cùng khu vực lớn bị coi là vi phạm.
- Sửa `build_boundary_correction_note()`: bớt hướng dẫn AI "bịa chướng ngại vật" — chỉ dùng cách này khi thực sự cần thiết (world có premise nhân vật yếu/bị giam giữ), không áp dụng mù quáng cho mọi world.

---

## Nhóm 3 — Tính năng Map mới (giải pháp thay thế tốt hơn cho vấn đề "bị bó")

**Ý tưởng cốt lõi:** thay vì giới hạn vô hình do AI tự quyết định lúc chạy (gây cảm giác bị cấm đoán tùy tiện), làm giới hạn thành **luật chơi minh bạch, người chơi biết trước**: bản đồ hiển thị rõ khu vực nào mở/khóa, gắn với tiến trình có thể nhìn thấy (EXP/level).

### 3.1 — Data model: `location_map.json` per world
```json
{
  "locations": [
    {"id": "kingdom", "name": "Vương Quốc", "x": 50, "y": 30, "unlocked": true},
    {"id": "forest_west", "name": "Rừng Tây", "x": 25, "y": 65, "unlocked": false,
     "unlock_condition": {"field": "protagonist.power_stat.exp", "op": ">=", "value": 10}}
  ],
  "fog_of_war": true
}
```
Tọa độ chuẩn hóa thang 0-100 (không phải pixel thật) — frontend tự scale theo kích thước màn hình.

### 3.2 — Sinh map từ mô tả bằng lời (không parse hình vẽ tay)
Người dùng mô tả layout bằng câu chữ (vị trí tương đối: "khu A gần trung tâm", "khu B ở phía Nam, xa hơn") → 1 bước generate riêng (cùng pattern với `_generate_prelude()`) chuyển mô tả thành tọa độ chuẩn hóa. Không cần vẽ chính xác tỷ lệ tay.

### 3.3 — Tận dụng EXP/realm đã có sẵn, không xây hệ thống mới
`unlock_condition` map thẳng vào `power_stat.exp`/`power_stat.realm` đã tồn tại trong schema — không cần thiết kế lại cơ chế tính điểm.

### 3.4 — Boundary check dùng map thay vì bịa lý do
Khi checkpoint/action liên quan đến 1 location chưa `unlocked`, hệ thống trả lời rõ ràng "khu vực chưa mở khóa, cần đạt X" — thay cho việc ép AI viết cảnh "hộ vệ chặn đường" như hiện tại.

### 3.5 — Frontend: tab Map mới
Canvas/SVG hiển thị các node location theo tọa độ chuẩn hóa, khu chưa mở khóa hiển thị mờ/khóa (fog of war), khu đã mở hiển thị rõ — người chơi luôn biết trước giới hạn hiện tại là gì.

---

## Nhóm 4 — Cải thiện chất lượng chơi (Planner + UI)

### 4.1 — Planner cần chủ động tạo ma sát/xung đột
`PLANNER_SYSTEM_PROMPT` hiện chỉ lo giữ nhịp (pacing) và giữ logic (canon consistency), không có chỉ thị nào bắt nó phải có trở ngại/hệ quả mỗi turn. Thêm rule: hầu hết các turn (trừ khi cố ý là beat "lặng") nên có ma sát narrative — trở ngại, hệ quả ngoài ý muốn, câu hỏi mới, leo thang căng thẳng. Có thể gắn theo `pacing_level` (Fast cần friction gần như mỗi turn, Slowburn có thể xen kẽ vài turn lặng).

### 4.2 — UI: tách túi đồ và bảng trạng thái ra khỏi đống "tag" phẳng
Hiện tại protagonist info, karma, age, traits, knowledge_flags, inventory, skills đều đổ chung 1 hàng span nhỏ, phân biệt bằng emoji. Redesign thành các section riêng biệt có cấu trúc (túi đồ dạng lưới/danh sách rõ ràng, bảng trạng thái có nhóm chỉ số riêng), tận dụng lại làm nền cho Nhóm 3 (map cũng cần khu UI riêng biệt tương tự).

---

## Thứ tự đề xuất thực hiện

1. **Nhóm 1** trước tiên — đều là bug cụ thể, không phụ thuộc quyết định thiết kế lớn, an toàn để giao ngay.
2. **Nhóm 2** — chỉ là sửa prompt + 1 hàm boundary check, tương đối nhanh, nên làm sau Nhóm 1 vì có thể ảnh hưởng tới cách checkpoint mới được test.
3. **Nhóm 4.1** (planner friction) — cũng chỉ là sửa prompt, có thể làm song song với Nhóm 2.
4. **Nhóm 3** (Map system) — việc lớn nhất, nên làm sau khi Nhóm 1+2 đã ổn định, vì cần thiết kế data model mới và UI mới hoàn toàn.
5. **Nhóm 4.2** (UI túi đồ/status) — có thể làm cùng lúc với Nhóm 3 vì đều là công việc frontend, tận dụng cùng 1 đợt redesign UI.

Khi sẵn sàng giao việc, mỗi nhóm nên tách thành workorder riêng theo đúng format hard-rules đã dùng từ trước (stop sau mỗi task, báo cáo có verify thật, không tự ý mở rộng phạm vi).
