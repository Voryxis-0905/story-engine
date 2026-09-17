# Story Engine — chạy trên máy này

**Cập nhật 18/09/2026:** đã hoàn thành đợt sửa độ tin cậy đầu tiên; 14 test mới và 747 kiểm tra cũ đạt. Chi tiết trong `docs/Tasks_and_Reports/reliability-pass-1.md`. Các mục kiểm tra bên dưới là kết quả lịch sử của lần cài đặt 17/09.

Đã chuẩn bị ngày 17/09/2026 từ bản ZIP người dùng cung cấp.

- Mở `Start-StoryEngine.cmd`, giữ cửa sổ đó mở, truy cập http://localhost:5173.
- Nhấn Ctrl+C trong cửa sổ chạy để dừng cả backend và giao diện.
- Không chạy thêm một phiên nếu ứng dụng đã mở ở cổng 8000/5173.
- Python được cài thư viện trong `.venv`, dựa trên Python 3.12 đi kèm runtime Codex của máy này. Không cần Python trong PATH toàn hệ thống. Môi trường này phụ thuộc runtime gốc; khi chuyển máy cần tạo lại `.venv`.
- Node.js của máy: v24.19.0; npm: 11.17.0. Thư viện giao diện đã cài bằng `npm ci` theo `ui/package-lock.json`.
- `requirements.lock.txt` ghi lại chính xác phiên bản Python đã cài. `requirements.txt` gốc được giữ nguyên.

## Kiểm tra đã thực hiện

- Python dependency check: không có xung đột.
- Biên dịch kiểm tra cú pháp toàn backend: đạt sau khi sửa hai cặp dấu nháy của prompt hồi kết trong `backend/prompts.py`.
- Frontend build: đạt. Có cảnh báo gói JavaScript hơn 500 kB.
- Frontend lint: không lỗi, còn 3 cảnh báo dependency của React hooks.
- Backend `/health`, `/worlds`: HTTP 200. Frontend tại cổng 5173: HTTP 200.
- Một lượt truyện với AI giả lập trong bản thử nghiệm riêng: HTTP 200.
- Bộ test cũ: 110 kiểm tra đạt, dừng ở lỗi xóa API key. Không tuyên bố cả bộ test đạt.
- Chưa kiểm thử chất lượng truyện với model thật, chưa thực hiện lời gọi AI trả phí.
- Chưa hoàn tất kiểm tra giao diện bằng mắt: bước trình duyệt đầu tiên bị duyệt tự động chặn; công cụ Windows đúng quy định mở được Edge nhưng gặp hộp thoại tài khoản/đồng bộ, nên không thao tác tiếp.

## Thay đổi trong lần chuẩn bị này

Chỉ sửa lỗi cú pháp ngăn backend khởi động trong `backend/prompts.py`; thêm launcher, hướng dẫn và bản khóa dependency. Frontend được build lại. Các lỗi logic còn lại được mô tả trong `../REVIEW-VA-BRAINSTORM.md`.

Các world và cấu hình từ ZIP được giữ lại. Test thay đổi dữ liệu chạy trong thư mục thử nghiệm riêng, không chạy trên world người dùng trong project này.

## Cài lại khi cần

Trong thư mục project, dùng Python 3.12 để tạo `.venv`, rồi chạy `.venv\Scripts\python.exe -m pip install -r requirements.lock.txt`. Trong thư mục `ui`, chạy `npm ci`. Không sao chép `.venv` giữa các máy.
