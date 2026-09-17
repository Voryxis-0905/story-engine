# Đóng góp cho Story Engine

Đây là MVP đang phát triển. Bắt đầu từ [README](README.md), [nguyên tắc thiết kế](docs/DESIGN-PRINCIPLES.md) và [bản đồ codebase](docs/CODEBASE.md).

## Chuẩn bị

Dùng Python 3.12 và Node.js 24. Tạo `.venv`, cài `requirements.lock.txt` và chạy `npm --prefix ui ci` theo README. Kích hoạt môi trường Python trước khi chạy các lệnh npm kiểm tra:

```powershell
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
npm run dev
```

Trên macOS/Linux: `source .venv/bin/activate`. Nếu máy hạn chế chạy script PowerShell, có thể gọi trực tiếp `.venv\Scripts\python.exe backend/run_tests.py` thay vì kích hoạt môi trường.

## Một thay đổi tốt

1. Tạo branch cho một vấn đề cụ thể; mô tả tình huống trước/sau.
2. Sửa tại module sở hữu trách nhiệm. Tránh thêm logic mới vào các file export tương thích.
3. Với lỗi hành vi, thêm test hồi quy độc lập trong `backend/tests/`. Không thêm kịch bản phụ thuộc thứ tự vào script test cũ.
4. Cập nhật tài liệu khi đổi luồng, API hoặc định dạng dữ liệu.
5. Chạy `npm run check` rồi mở PR, ghi rõ kết quả và giới hạn kiểm tra.

`npm run check` chạy test backend, bộ kiểm tra cũ, build TypeScript/giao diện và lint. Có thể chạy riêng `npm test`, `npm run test:legacy`, `npm run build`, `npm run lint`. CI chạy cùng các bước trên Windows và Linux cho backend, Linux cho giao diện.

## Dữ liệu và thay đổi hành vi

- Không commit API key, `.env`, dữ liệu world/save cá nhân, `.venv`, `node_modules` hoặc `dist`.
- Khi cần tái hiện lỗi với dữ liệu, tạo fixture nhỏ đã loại thông tin cá nhân. Dùng `STORY_ENGINE_DATA_DIR` trỏ vào thư mục thử nghiệm riêng.
- Giữ tương thích save cũ hoặc nêu rõ cách chuyển đổi. Việc thay prompt cũng là thay đổi hành vi, cần đánh giá riêng.
- Test tự động không cần API key và không được gọi nhà cung cấp AI thật.

Kho mã chưa chốt giấy phép phát hành công khai. Trước khi public cần chọn giấy phép, rà dữ liệu mẫu và hoàn thiện hướng dẫn phát hành; tài liệu này không tự cấp quyền sử dụng mã.
