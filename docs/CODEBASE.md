# Bản đồ codebase

## Backend

Chạy bằng `backend/main.py` hoặc `uvicorn --app-dir backend main:app`. `app/application.py` lắp ráp ứng dụng, middleware và router.

| Vị trí | Trách nhiệm |
| --- | --- |
| `app/routes/` | Nhận yêu cầu HTTP, kiểm tra đầu vào và gọi engine/storage |
| `app/routes/world_routes.py` | Vòng đời world, nhập/xuất và fork |
| `app/routes/runtime_routes.py` | Cấu hình nhà cung cấp/model/API key |
| `app/routes/discovery_routes.py` | Map, quest, codex |
| `app/routes/demo_routes.py` | World mẫu |
| `app/chapter_generator.py` | Điều phối một lượt: chuẩn bị ngữ cảnh → sinh truyện → kiểm tra → áp dụng → lưu |
| `app/story/generation.py` | Planner, writer và editor |
| `app/story/consistency.py` | Kiểm tra nhất quán và hướng dẫn sửa |
| `app/story/memory.py` | Canon, ngữ cảnh nhiều tầng và tóm tắt |
| `app/story/pacing.py` | Độ dài lượt, nhịp truyện và đóng chương |
| `app/story/prelude.py` | Mở đầu truyện |
| `app/story/entities.py` | Chuẩn hóa nhân vật, loại trùng và kiểm tra gói nhập |
| `app/checkpoint_engine.py` | Điều kiện và tiến trình checkpoint |
| `app/world/` | Mẫu dữ liệu, luật bản đồ, ranh giới và endgame |
| `app/prompts/` | Prompt chia theo nhiệm vụ; thay đổi ở đây có thể đổi hành vi AI |
| `app/models.py` | Schema dữ liệu đang dùng bởi API |
| `app/storage.py`, `app/persistence.py` | Đọc/ghi dữ liệu, khóa world và lưu nhiều file |
| `app/llm_client.py` | Gọi nhà cung cấp AI, lỗi, retry và phản hồi giả lập |

Router gọi lớp xử lý; lớp xử lý dùng storage/LLM. Module nhỏ không nên import ngược `main`, router hoặc module điều phối. Các cầu nối tương thích cũ vẫn là ngoại lệ được giữ để tránh phá tích hợp.

### Tương thích đang được giữ

`app/compat.py`, `app/engine.py` và `backend/prompts.py` giữ tên import cũ. Các hàm được chuyển khỏi chapter/checkpoint engine vẫn được export lại tại vị trí cũ. Code mới nên import từ module sở hữu hàm. `main.call_llm` và một số điểm thay thế trong test cũ vẫn được hỗ trợ.

`backend/models.py` là schema cũ; không thêm model mới vào đây. Nguồn schema hiện hành là `app/models.py`.

## Giao diện

`ui/src/pages/` nối trang với router. Luồng chơi nằm ở `ui/src/features/play/`:

- `usePlaySession.ts`: trạng thái phiên chơi, tải dữ liệu và hành động người dùng.
- `PlaySidebar.tsx`: danh sách chương và điều hướng bên trái.
- `PlayNarrative.tsx`: nội dung truyện và nhập hành động.
- `PlayInspector.tsx`: các bảng thông tin và công cụ bên phải.
- `types.ts`: kiểu dữ liệu dùng chung trong tính năng.

`PlayPage.tsx` chỉ ghép các phần này. Component dùng lại giữa tính năng tiếp tục nằm trong `src/components/`; không cần chuyển toàn bộ giao diện một lần. Khi một tính năng khác lớn lên, gom hook, component và kiểu riêng vào `features/<tên>/`.

## Kiểm tra và giới hạn

`backend/tests/` chứa test hồi quy độc lập. `backend/test_engine.py` là bộ kiểm tra cũ chạy tuần tự và dùng trạng thái chung; thêm test mới vào `backend/tests/`. Luôn dùng `backend/run_tests.py` để cô lập dữ liệu và chặn gọi AI thật.

Đợt sắp xếp này giữ nguyên API, nội dung prompt và định dạng dữ liệu lưu. Chưa thay toàn bộ kiến trúc: điều phối lượt, storage, builder và một số trang khác còn lớn. Tách tiếp theo trách nhiệm khi có thay đổi thực tế và test bảo vệ, tránh tạo quá nhiều lớp chỉ để giảm số dòng.

Ba cảnh báo lint về dependency của React effect và cảnh báo bundle lớn vẫn cần xử lý ở đợt giao diện riêng. Test hiện tại dùng AI giả lập, chưa đo chất lượng truyện với model thật.
