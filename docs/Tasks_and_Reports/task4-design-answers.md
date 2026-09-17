Trả lời 4 câu hỏi design cho Task 4 — ưu tiên **chất lượng hơn tốc độ/scope gọn**, không cần tối giản quá mức:

## 1. All-at-once vs 2 bước riêng
Chọn **2 bước riêng**, không gộp chung 1 nút. Thêm 1 bước "Generate Prelude" riêng trước khi vào Chapter 1 — cho user đọc/duyệt/regenerate nếu chưa ưng, rồi mới bấm tiếp để bắt đầu Chapter 1. Dùng lại đúng pattern review-trước-khi-confirm mà hệ thống đã có sẵn ở bước checkpoint review, không phải tạo UI mới từ đầu — chỉ áp dụng lại cho prelude. Prelude là ấn tượng đầu tiên của cả câu chuyện nên đáng có bước duyệt riêng.

## 2. Nguồn nội dung prelude
Đừng dùng payload tối giản. Đưa **full context** cho LLM khi generate prelude:
- `fixed_rules` đầy đủ (không rút gọn)
- `power_system` đầy đủ
- `story_thesis`
- cp_0 description
- Nếu world có `narrative_scope_note` (câu trả lời interview gốc, dạng Q&A) thì đưa nguyên văn luôn — đây là nơi giữ đúng "giọng văn"/tone/POV mà user thực sự muốn nhất, tóm tắt lại dễ mất sắc thái.

## 3. Mock LLM support
Giữ nguyên theo đề xuất ban đầu của cậu — không ảnh hưởng chất lượng, chỉ phục vụ test, làm bình thường.

## 4. Retroactive (world cũ đã có chapter)
Đừng chặn cứng hoàn toàn. Cho phép thêm prelude sau cho world cũ, nhưng qua **1 nút riêng trong Creator Mode** (không tự động, không lẫn vào flow `/chapter/start` bình thường) — vì đây là thao tác chèn ngược cần cẩn thận, không được đụng vào `chapter_index` của các chapter đã tồn tại. Tách phần này thành sub-task riêng, đừng gộp chung vào lần code chính của Task 4 để không làm phình to quá mức.

## Một điểm cần bổ sung vào plan
Plan hiện tại chủ động bỏ qua consistency checker cho prelude ("pure prose-generation call, no boundary checking"). Đừng bỏ hẳn — giữ lại **ít nhất 1 lượt check nhẹ** để đảm bảo prelude không mâu thuẫn với `fixed_rules`, hoặc lỡ tiết lộ thông tin thuộc về checkpoint sau (spoiler). Đây là đoạn văn đầu tiên user đọc, sai sót ở đây ảnh hưởng ấn tượng nhiều hơn một turn bình thường ở giữa truyện.

Sau khi thống nhất theo hướng này, tiến hành code Task 4. Vẫn giữ nguyên các hard rule cũ: xong việc thì dừng lại, báo cáo theo đúng format, đừng tự chạy tiếp task khác.
