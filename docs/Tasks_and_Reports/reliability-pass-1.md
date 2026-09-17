# Đợt 1 — độ tin cậy của trạng thái thế giới

Ngày 18/09/2026. Nhánh `fix/world-state-reliability`.

## Hành vi đã sửa

- Một lượt thành công tăng `story_clock.tick` đúng một lần bằng engine, độc lập với ngày/giờ trong truyện do model đề xuất. Lượt thất bại không lưu bước tăng này.
- Event đến hạn, fact về hậu quả, cờ thế giới và hiệu ứng trên bản đồ được lưu cùng các file của lượt. Event đã resolved không sinh hậu quả lặp lại ở lượt sau.
- Dữ liệu event lỗi JSON không còn bị âm thầm biến thành danh sách rỗng.
- Ghi lượt kiểm tra và chuẩn bị tất cả file trước khi thay thế. Nếu có lỗi I/O trong quá trình thay thế, khôi phục các byte cũ và bỏ file mới của lượt. Nếu chính rollback cũng lỗi, giữ bản sao để phục hồi thủ công và báo lỗi.
- Hai lời gọi sinh lượt cùng world được tuần tự hóa trong một tiến trình, tránh cùng đọc một trạng thái rồi ghi đè nhau. Save, restore, branch từ save và epilogue dùng cùng khóa.
- Save/restore/branch bao gồm `world_events.json`. Restore save cũ thiếu file phụ dùng dữ liệu mặc định, không giữ lại trạng thái tương lai; safety save giữ bản trước restore.
- Map status lấy đúng `protagonist_id` (hỗ trợ tên cũ khi thiếu) và dùng chung kiểm tra mở khóa với hành động di chuyển. Giữ luật cũ của world hiện có, chưa đưa ra mô hình năng lực mới.
- Hai endpoint hồi kết import đúng prompt. Epilogue phải có nội dung hợp lệ, được lưu vào lịch sử cùng trạng thái completed. Gửi lại trả bản đã lưu, không gọi AI và không thêm chương trùng. Continue trên world completed trả 409; người dùng có thể restore hoặc branch từ save trước hồi kết.
- Xóa API key chung xóa cả hai tên trường và chuỗi dự phòng; giữ cấu hình model. Key riêng của world được ưu tiên hơn chuỗi dự phòng chung.
- Runner test tạo kho dữ liệu tạm qua `STORY_ENGINE_DATA_DIR` và chặn HTTP thực đến nhà cung cấp AI.

## Kiểm tra đã chạy

```powershell
.\.venv\Scripts\python.exe backend/run_tests.py
.\.venv\Scripts\python.exe backend/run_tests.py --legacy
```

- 14 test unittest mới đạt: sự kiện đến hạn/lưu một lần, lỗi muộn, rollback khi thay file, validation trước ghi, save/restore/branch, save cũ, map và luật di chuyển, key, epilogue, hai lượt đồng thời.
- Script legacy: 747 kiểm tra `[OK]`, kết thúc mã 0 và thông báo toàn bộ test đạt.
- Không gọi AI trả phí; không chạy test trên world cá nhân.

## Giới hạn và bước sau

- Cơ chế rollback bảo vệ lỗi phát sinh trong chương trình, **chưa bảo đảm phục hồi sau mất điện/tiến trình bị kill**. Khóa chỉ có hiệu lực trong một server process. Không chạy nhiều worker để ghi cùng kho JSON.
- Chưa đồng bộ khóa cho mọi thao tác Creator/import/delete và mọi đường đọc nhiều file. Chưa có mã yêu cầu chống gửi trùng cho lượt continue; hai yêu cầu riêng vẫn tạo hai lượt hợp lệ.
- Chưa đổi triết lý checkpoint hoặc đánh giá năng lực; không áp một thứ bậc chung cho mọi thể loại.
- Chưa sửa phạm vi nhận thức NPC, luồng tạo world events, giao diện quest/endgame và việc che key trong API trạng thái. Đây là các nhóm công việc tiếp theo.
- Chưa đánh giá chất lượng văn chương bằng model thật. Không có thay đổi giao diện trong đợt này; không coi backend tests là kiểm tra trải nghiệm trình duyệt.
