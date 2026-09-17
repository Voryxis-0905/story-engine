# Sắp xếp codebase — 2026-09-18

## Thay đổi

- Tách các trách nhiệm của chapter engine vào `app/story/` và luật thế giới vào `app/world/`.
- Chia prompt theo nhiệm vụ trong `app/prompts/`, giữ import tương thích.
- Tách runtime config, discovery và dữ liệu demo khỏi world router.
- `main.py` trở thành entry point; assembly nằm ở `app/application.py`, export cũ nằm ở `app/compat.py`.
- Tách trang chơi thành hook phiên chơi và ba vùng giao diện trong `features/play/`.
- Thêm bản đồ codebase, mục lục tài liệu, hướng dẫn đóng góp, lệnh kiểm tra chung và GitHub Actions.

## Bằng chứng kiểm tra cục bộ

- 14 test hồi quy độc lập đạt; bộ kiểm tra cũ đạt 747 kiểm tra.
- Build TypeScript/Vite và lint hoàn thành. Lint còn ba cảnh báo dependency của effect; Vite còn cảnh báo bundle lớn đã có trước đợt sắp xếp.
- So sánh OpenAPI trước/sau: 55 đường dẫn và toàn bộ schema không đổi.
- So sánh SHA-256 của 21 chuỗi prompt trước/sau: không đổi.
- Kiểm tra khoảng trắng bằng Git không báo lỗi.

API, định dạng lưu và hành vi truyện không được chủ động thay đổi trong đợt này. Test dùng AI giả lập. CI được bổ sung nhưng kết quả chạy trên GitHub cần xem tại PR.

## Phần còn lại

Một số module điều phối, storage, builder và script kiểm tra cũ vẫn lớn. Các export tương thích được giữ có chủ đích; không thêm logic mới vào chúng. Chưa chọn giấy phép phát hành, chưa chuyển kho mã sang public.
