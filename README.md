# Story Engine

Ứng dụng kể chuyện tương tác chạy cục bộ, với backend Python/FastAPI và giao diện React/TypeScript.

Người chơi quyết định hành động và tác động đến kết quả. Thế giới giữ lịch sử, luật vận hành và thông tin riêng của từng nhân vật. Creator cũng là người chơi, nhưng có quyền sửa kết quả và trạng thái thế giới.

## Trạng thái

MVP đang phát triển. Mốc nhập mã đầu tiên giữ các lỗi đã phát hiện để xử lý có lịch sử rõ ràng. Xem [báo cáo đánh giá](docs/REVIEW-VA-BRAINSTORM.md) và [nguyên tắc thiết kế](docs/DESIGN-PRINCIPLES.md).

Đã sửa lỗi cú pháp ở hai prompt hồi kết để backend khởi động. Frontend build đạt; bộ kiểm tra backend cũ dừng sau 110 kiểm tra đạt tại lỗi xóa API key. Chưa xác nhận toàn bộ chức năng hoặc chất lượng truyện với AI thật.

## Cài đặt

Cần Python 3.12 và Node.js 24 (các phiên bản đã dùng khi kiểm tra bản này).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
npm --prefix ui ci
```

Trên Windows, mở `Start-StoryEngine.cmd`, sau đó truy cập http://localhost:5173. Backend chạy tại http://127.0.0.1:8000. Để dừng, nhấn Ctrl+C ở cửa sổ chạy.

Trên hệ điều hành khác, kích hoạt môi trường Python rồi chạy `npm run dev`.

Thiết lập nhà cung cấp/model trong Settings khi cần sử dụng AI. Cấu hình thực tế, API key, world cá nhân và save nằm ngoài Git. Kho mã không kèm dữ liệu chơi cá nhân; ứng dụng tự tạo thư mục dữ liệu khi khởi động.

## Kiểm tra

```powershell
npm --prefix ui run build
npm --prefix ui run lint
.\.venv\Scripts\python.exe -m compileall -q backend
```

**Bộ test cũ `backend/test_engine.py` thay đổi/xóa world có tên test và sửa runtime config. Chỉ chạy trên bản sao thử nghiệm với dữ liệu riêng, không chạy trên thư mục đang chơi.** Cần cải tổ test để cô lập dữ liệu tự động.

## Thư mục

- `backend/`: API, engine, luật, bộ nhớ và pipeline AI.
- `ui/`: giao diện web.
- `docs/`: thiết kế, đánh giá và lịch sử công việc.
- `data/`: được tạo cục bộ; không đưa vào Git.

Các tài liệu cũ có thể mô tả tính năng dự kiến hoặc trạng thái đã lỗi thời. Ưu tiên nguyên tắc thiết kế mới và kết quả kiểm tra có bằng chứng trong báo cáo.
