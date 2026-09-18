# D04 — Creator sửa lịch sử như thế nào

Trạng thái: **ĐÃ DUYỆT 18/09/2026** theo các mặc định đề xuất (chủ dự án chốt). W07 có thể triển khai. Mặc định: sửa tại tick hiện tại có revision và ghi chú; sửa quá khứ tạo nhánh từ mốc tương ứng.

Căn cứ: [DESIGN-PRINCIPLES.md](../DESIGN-PRINCIPLES.md), [../AGENT-BACKLOG.md](../AGENT-BACKLOG.md) mục D04,
[F05/F06 trong backlog](../AGENT-BACKLOG.md) về revision và phục hồi lượt.

## 1. Ba cách sửa

| Cách | Khi dùng | Hệ quả lên lịch sử | Snapshot |
| --- | --- | --- | --- |
| **Sửa tại tick hiện tại** (mặc định) | Đổi kết quả vừa xảy ra, thêm/sửa fact | Không viết lại các chương đã đọc; áp revision mới lên state hiện tại | Snapshot trước khi sửa + snapshot sau khi sửa |
| **Quay lại nhánh cũ** | Muốn thử kết cục khác từ mốc cũ | Tạo nhánh mới từ save/branch tương ứng; nhánh gốc giữ nguyên | Snapshot nhánh nguồn là bất biến |
| **Viết lại quá khứ** | Đổi một sự kiện đã xảy ra nhiều chương trước | Bắt buộc tạo nhánh mới từ mốc tương ứng; **không** tự tái viết mọi chương đã đọc | Snapshot trước mốc + revision ghi rõ lý do |

Nguyên tắc: *không tự động tái viết nội dung người đọc đã đọc.* Muốn đổi quá khứ phải
thành nhánh có chủ đích, để người đọc biết mình đang ở đâu.

## 2. Revision và ghi chú

Mọi lần sửa tạo một bản ghi:

```json
{
  "revision_id": "rev_0003",
  "mode": "current",
  "author": "creator",
  "reason": "cứu nhân vật bị chết oan",
  "base_tick": 12,
  "created_at": "...",
  "changes": [{"kind": "alive", "target": "char_xueli", "from": false, "to": true}],
  "snapshot_before": "save_...",
  "snapshot_after": "save_...",
  "validation": {"ok": true, "warnings": []}
}
```

- `author` phải là `creator` do **luồng lệnh** quyết định, không tin field model trả về
  để tự nâng quyền (W07).
- Revision conflict (dựa trên expected revision của F05) phải báo, không ghi đè im lặng.

## 3. Ký ức và tóm tắt mâu thuẫn sau khi sửa

Sau khi sửa, phải xử lý:
- **Ký ức NPC** liên quan: thêm/sửa/xoá knowledge gắn `event_id`/`tick`; NPC chưa từng
  biết việc bị sửa thì không được "nhớ" nó.
- **Tóm tắt dài hạn**: đánh dấu stale và dựng lại phần bị ảnh hưởng (W08), không để tóm
  tắt cũ chứa chi tiết đã bị sửa.
- **Canon log**: append bản ghi revision; không xoá lịch sử revision.

## 4. Ba ví dụ

1. **Cứu người đã chết**
   - Sửa tại tick hiện tại: `alive true`, `status_effects` sạch, thêm fact "được cứu".
   - Ký ức: NPC chứng kiến cái chết cần được cập nhật; NPC không biết thì giữ nguyên.
   - Snapshot trước/sau còn hợp lệ; UI báo "đã sửa tại lượt N, có revision rev_X".
2. **Đổi kết quả event**
   - Sửa tại tick hiện tại nếu event vừa `resolved`; nếu không, tạo nhánh từ tick event.
   - Không chạy lại event lần hai; fact/flag/world event được cập nhật đồng bộ.
   - UI báo rõ event nào bị đổi và nhánh nào bị ảnh hưởng.
3. **Bỏ một lời hứa**
   - Sửa tại tick hiện tại: xoá memory promise của các bên liên quan; NPC đã hành động dựa
     trên lời hứa cần hệ quả riêng, không tự động hoàn tác.
   - Nếu muốn "chưa từng hứa" thì phải là nhánh từ mốc trước khi hứa.

## 5. Điều KHÔNG làm

- Không dùng UI mode như auth nhiều người dùng.
- Không tự tái viết toàn bộ chương đã đọc.
- Không để state nửa vời: inventory/event/knowledge phải nhất quán sau sửa, hoặc bị chặn
  và báo lỗi.
- Không xoá revision cũ.

## 6. Câu hỏi chờ chốt

1. Sửa quá khứ mặc định tạo nhánh, nhưng có cho phép "sửa tại chỗ" nếu người đọc chưa đi
   qua mốc đó không? Đề xuất: có, miễn là không viết lại nội dung đã hiển thị.
2. Khi phát hiện tóm tắt mâu thuẫn, tự dựng lại hay hỏi creator? Đề xuất: tự dựng lại
   nhưng ghi cảnh báo để creator xem.
