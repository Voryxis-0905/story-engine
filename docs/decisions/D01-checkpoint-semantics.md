# D01 — Checkpoint khi tiền đề đã mất

Trạng thái: **ĐÃ DUYỆT 18/09/2026** theo các mặc định đề xuất (chủ dự án chốt). W03 có thể triển khai.

Căn cứ: [DESIGN-PRINCIPLES.md](../DESIGN-PRINCIPLES.md), [../AGENT-BACKLOG.md](../AGENT-BACKLOG.md) mục D01.

## 1. Vấn đề

Một checkpoint/ sự kiện được định nghĩa để xảy ra. Nhưng player có thể đã ngăn nguyên
nhân, tác nhân tổ chức có thể đã chết, hoặc địa điểm đã biến mất. Ép cảnh phi lý để giữ
đúng lịch là sai. Bỏ luôn sự việc cũng sai nếu nó quan trọng với câu chuyện. Cần một
luật rõ để biến "sự việc bắt buộc" thành "kết quả mở có nguyên nhân".

## 2. Phân loại sự việc

| Loại | Ai/lực lượng tạo ra | Ví dụ | Nếu nguyên nhân mất |
| --- | --- | --- | --- |
| **Organized** (do tác nhân tổ chức) | NPC, phe phái, âm mưu có ý chí | Đại hội võ lâm, ám sát, hôn lễ | Chuyển hoá hoặc thay thế bằng một buổi khác do tác nhân còn sống tổ chức |
| **Natural / contingent** (bất khả kháng) | thời tiết, dịch bệnh, thiên tai, quy luật thế giới | Bão, núi lửa, lời nguyền cổ | Vẫn xảy ra theo luật; chỉ đổi cách player trải nghiệm |
| **Scripted consequence** (kết quả nối tiếp) | hệ quả của sự việc trước | Trả thù sau khi một NPC chết | Không kích hoạt nếu tiền đề không xảy ra; thay bằng hệ quả khác hợp lý |

Điều này cho phép phân biệt "sự việc bắt buộc xuất hiện" với "sự việc bắt buộc xuất hiện
y hệt như bản thảo". Kết quả mở không có nghĩa player gõ gì cũng thành sự thật: thế giới
vẫn phán xử theo luật ở mục 3.

## 3. Luật thế giới vs mục tiêu kể chuyện

**Luật thế giới (không thương lượng):**
- Nhân quả: không ai làm việc bất khả thi với nguồn lực/tri thức họ có.
- Hạn tri: NPC không phản ứng với điều họ không biết (xem D02).
- Cái chết và mất mát là thật; không hồi sinh ngầm để cứu một cảnh.
- Thời gian trôi một chiều trong một nhánh.

**Mục tiêu kể chuyện (điều chỉnh được):**
- Giữ nhịp và căng thẳng; biến cố quan trọng nên có dư chấn, không cần tái hiện y hệt.
- Nhân vật chính diện vẫn có đường hành động sau thất bại/bỏ lỡ.

Khi hai bên xung đột: **luật thế giới thắng**. Mục tiêu kể chuyện được thoả bằng hệ quả
thay thế hợp lý, không bằng phá luật.

## 4. Trạng thái giải quyết

- `prevented` — player/tác nhân ngăn được nguyên nhân. Sự việc không xảy ra; hệ quả nối
  tiếp bị chặn hoặc thay thế.
- `transformed` — sự việc xảy ra nhưng dưới hình thức/địa điểm/tác nhân khác do nguyên
  nhân gốc đã mất.
- `missed` — sự việc xảy ra ngoài tầm player; player chỉ biết qua tin đồn/hệ quả về sau.
- `resolved` — player tham gia và kết quả được chốt (thành công, một phần hoặc thất bại).

## 5. Bảng sự việc → can thiệp → kết quả hợp lệ

Ví dụ dùng lại một sự kiện nền: *"Ám sát Tể tướng tại lễ đăng quang ngày X"*.

| Tình huống | Can thiệp của player | Kết quả hợp lệ | Loại |
| --- | --- | --- | --- |
| **Tham gia** | Có mặt, tìm cách cứu hoặc thúc đẩy | `resolved`: cứu được / bị thương / ám sát thành công tuỳ năng lực và đối kháng | Organized |
| **Bỏ qua** | Đi nơi khác, không biết | `resolved`: ám sát thành công; player biết qua tin đồn ở tick sau | Organized |
| **Đến muộn** | Tới sau giờ G | `transformed`: hậu quả đã xảy ra, player đối mặt với hiện trường và truy vết | Organized |
| **Ngăn sớm** | Vô hiệu hoá âm mưu từ trước | `prevented`: không có án mạng; âm mưu chuyển mục tiêu hoặc kẻ chủ mưu chuyển kế hoạch khác | Organized |
| **Tác nhân chết** | Giết thích khách/kẻ chủ mưu trước ngày X | `prevented` hoặc `transformed` tuỳ còn tác nhân kế tục; nếu không còn, sự việc chuyển thành hệ quả khác (tranh chấp quyền lực) | Organized |
| **Địa điểm biến mất** | Phá/huỷ lễ đài, đóng biên giới | `transformed`: buổi lễ dời địa điểm hoặc tổ chức kín; player có thể lỡ nếu không theo kịp | Organized |

Thêm một ca bất khả kháng để đối chiếu: *"Bão lớn đổ bộ ngày X"*. Dù player ngăn được kẻ
thù hay ở xa, **bão vẫn xảy ra** (`transformed`/`missed` chỉ đổi nơi và mức thiệt hại).
Player không thể `prevented` một quy luật tự nhiên nếu không có nguồn lực được thiết lập.

## 6. Hệ quả thiết kế cho W03

- Checkpoint/sự kiện tách **điều kiện kích hoạt** khỏi **vòng đời** khỏi **kết quả**.
- Điều kiện kích hoạt thiếu dữ liệu phải trả `unknown`/lỗi rõ, không kích hoạt nhầm.
- Sự việc đã `resolved/prevented/transformed/missed` không chạy lần hai.
- `prevented` cần lưu "vì sao" (nguồn can thiệp) để hệ quả về sau mạch lạc.
- Kết quả không nằm trong danh sách mẫu vẫn hợp lệ nếu qua được schema và luật.

## 7. Câu hỏi chờ chủ dự án chốt

1. Bao nhiêu phần trăm sự kiện được phép `prevented` hoàn toàn trước khi câu chuyện mất
   xung đột chính? Đề xuất: sự kiện `major` không bị chặn vô hậu quả — `prevented` luôn
   sinh một hệ quả thay thế.
2. Có cho phép `null` checkpoint (kết thúc một nhánh quá ngắn do ngăn sớm) không? Đề
   xuất: có, nhưng phải là một kết cục hợp lệ, không phải lỗi.
