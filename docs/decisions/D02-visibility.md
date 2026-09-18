# D02 — Ai được thấy thông tin gì

Trạng thái: **ĐÃ DUYỆT 18/09/2026** theo các mặc định đề xuất (chủ dự án chốt). W01/W05/U03 có thể triển khai.

Căn cứ: [DESIGN-PRINCIPLES.md](../DESIGN-PRINCIPLES.md), [../AGENT-BACKLOG.md](../AGENT-BACKLOG.md) mục D02.

## 1. Bốn góc nhìn

| Chủ thể | Thấy gì | Không thấy gì |
| --- | --- | --- |
| **World** (sự thật khách quan) | Toàn bộ fact, event, vị trí, nhân quả | — |
| **NPC** | Fact/ký ức họ đã chứng kiến hoặc được kể, với nguồn và độ chắc chắn | Điều player biết mà NPC không biết; suy nghĩ NPC khác; fact chưa truyền tới |
| **Player (protagonist)** | Những gì protagonist trực tiếp trải/quan sát, quest/map/log đã mở, thông tin tổng quan được phép | Bí mật động cơ/danh tính chưa được tiết lộ; suy nghĩ nội tâm người khác |
| **Creator** | Toàn cảnh + công cụ sửa (D04) | Không tự động hợp nhất quan điểm của NPC; sửa qua luồng có revision |

Player mode và Creator mode là hai **chế độ xem** trên cùng một world. UI mode không phải
cơ chế xác thực nhiều người dùng trong bản local.

## 2. Mức độ tin cậy của tri thức

- `fact` — sự thật khách quan, có ID ổn định, không đổi nếu không có creator edit.
- `knowledge` — mệnh đề mà một chủ thể tin, kèm `source`, `tick/at`, `confidence`, và
  `fact_id` (khi đúng với sự thật).
- `rumor` / `belief` — tin đồn/suy đoán **có thể sai**; lưu riêng, không sửa fact gốc.
- `perception` — phần sự kiện một NPC thực sự thấy/nghe trong một lượt.

Nguyên tắc: *tin nhiều người tin không làm điều sai thành đúng.* Chỉ `fact` mới là canon.

## 3. Sáu ví dụ (lưu gì — trả ở API nào)

1. **Bí mật động cơ**
   - Lưu: `world_fact` "Tể tướng là kẻ chủ mưu", `knowledge` của Tể tướng (source=self) và
     của player chỉ khi phát hiện; `secrets` của NPC không trả qua API thường.
   - API: `/codex` (creator/player tuỳ unlock), `/play-state` không trả `secrets` NPC khác.
2. **Tin đồn sai**
   - Lưu: `rumor` "X phản bội" gắn người tin + nguồn; fact gốc "X trung thành".
   - API: `/discovery` trả rumor trong log/quest của player; `/codex` vẫn chỉ fact.
3. **Nghe kể lại**
   - Lưu: `knowledge` cho B với `source = {kind: "told_by", who: A, tick}`; A có
     `perception` trực tiếp.
   - API: payload context gửi model của B có knowledge đó; không gửi transcript gốc.
4. **Sự kiện ở xa**
   - Lưu: event diễn biến theo tick; player chỉ nhận `discovery` khi có đường truyền tin.
   - API: `/world-events` (creator) thấy toàn bộ; player chỉ thấy phần đã khám phá (W05).
5. **Quest deadline**
   - Lưu: quest gắn `event_id`, `deadline_tick` chỉ khi player biết; nếu chưa biết thì
     `deadline: unknown`.
   - API: `/quests` trả `status`, `deadline_known`; không suy deadline từ điều kiện bất kỳ.
6. **Suy nghĩ NPC**
   - Lưu: `psychology`/`internal_state` của NPC, tách khỏi `knowledge`.
   - API: không trả nội tâm NPC khác cho player; creator xem qua chế độ toàn cảnh.

## 4. Quy tắc projection

- **Một chính sách projection dùng chung** cho cả context model và API, tránh hai nguồn
  sự thật (W01).
- Payload gửi model của một NPC chỉ chứa fact/knowledge/perception của chính NPC đó, cộng
  thông tin công khai (thời tiết, địa hình, sự việc ai cũng thấy).
- Không dựa vào câu "đừng spoil" trong prompt thay cho lọc dữ liệu.
- Player context: protagonist knowledge + thông tin tổng quan được thiết kế, không tự lộ
  bí mật động cơ/danh tính.

## 5. Hệ quả cho W01/W05/U03

- W01: thêm `subject`, `source`, `at`, `confidence`, `fact_id` cho knowledge; rumor tách
  khỏi canon; save cũ chuyển đổi mà không biến tri thức thế giới thành tri thức mọi NPC.
- W05: discovery record có `event_id` + nguồn; quest là góc nhìn của player lên cơ hội.
- U03: UI phân biệt "đã biết", "tin đồn", "chưa rõ"; không lộ secret qua tiêu đề/graph/
  tooltip/payload API.

## 6. Câu hỏi chờ chốt

1. Player có được thấy bảng quan hệ/affinity tổng quan mà protagonist "cảm nhận" không,
   hay chỉ thấy mức đã trải nghiệm? Đề xuất: chỉ mức đã trải nghiệm + ước lượng mơ hồ.
2. Creator xem toàn cảnh có được phép thấy `secrets` NPC ngay cả khi chưa unlock không?
   Đề xuất: có trong Creator mode, tách nhãn rõ "chỉ creator".
