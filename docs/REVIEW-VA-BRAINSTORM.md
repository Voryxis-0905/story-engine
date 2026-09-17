# Story Engine — kiểm tra và hướng phát triển

Ngày 17/09/2026. Phạm vi: đọc mã và tài liệu, cài môi trường, chạy build/lint, kiểm tra HTTP, chạy test cũ và tái hiện riêng một số lỗi bằng dữ liệu giả lập. Đây chưa phải đánh giá chất lượng văn chương với model thật hoặc kiểm toán toàn bộ hệ thống.

## Nhận định chính

Dự án có nhiều thành phần đúng hướng, nhưng các thành phần chưa khép kín thành một vòng chơi đáng tin. Ưu tiên lớn nhất là bảo đảm “điều đã xảy ra được lưu đúng, nhân vật chỉ biết điều họ có thể biết, và lựa chọn làm thay đổi tương lai”. Thêm hệ thống mới trước khi ba điều này ổn sẽ làm khó xác định lỗi hơn.

## 1. Lỗi đã tái hiện

| Ưu tiên | Phát hiện | Tác động | Bằng chứng / hướng sửa |
|---|---|---|---|
| P0 — đã sửa | Backend không import được vì dấu nháy ba bị escape ở hai prompt hồi kết | Không thể khởi động ứng dụng | `backend/prompts.py:740` và prompt tiếp theo. Bỏ escape ở dấu mở/đóng; compile backend và `/health` đã đạt. |
| P1 | Sự kiện nền được lưu là resolved nhưng fact và hiệu ứng bản đồ không được lưu | Thế giới có thể quên kết quả sự kiện ngay lượt sau | Trong `chapter_generator.py:1385`, hàm tick sửa canon/map trong RAM, chỉ lưu `world_events.json`; cuối lượt chỉ lưu nhân vật, chương, cấu hình và card. Test: lượt trả 200, event resolved, fact và tag `ruined` vẫn thiếu trên đĩa. |
| P1 | Save bỏ sót `world_events.json` | Restore/branch không tái tạo đầy đủ thế giới | `snapshot_world_state` sao chép các tên trong `TEMPLATES`; danh sách này chưa có world_events. Test tạo file event rồi snapshot: file event không có trong save. |
| P1 | Map status đọc `main_character_id`, còn dữ liệu dùng `protagonist_id` | Người chơi đủ EXP vẫn nhìn thấy khu vực bị khóa | `world_routes.py:606`. Test nhân vật 100 EXP, khu cần 10: endpoint trả khóa, hàm kiểm tra di chuyển cho phép. |
| P1 | Hai endpoint hồi kết import `app.prompts`, module không tồn tại | Gọi hồi kết lỗi ngay trước khi kiểm tra điều kiện world | `chapter_routes.py:428,476`; cả hai lời gọi tái hiện `ModuleNotFoundError: app.prompts`. |
| P1 | Xóa API key vẫn báo còn key | Người dùng tưởng đã xóa cấu hình nhưng key vẫn có thể được dùng | `clear_runtime_api_key` xóa `openrouter_api_key` và fallback, bỏ sót `api_key`; hàm đọc ưu tiên `api_key`. Test bằng chuỗi giả, không gọi nhà cung cấp. Bộ test cũ cũng dừng đúng lỗi này. |

P0/P1 ở đây là thứ tự sửa đề xuất, không phải kết quả quét bảo mật tự động.

## 2. Vấn đề đọc được trực tiếp trong mã, cần kiểm thử sâu hơn

**Phạm vi nhận thức NPC đang sai.** `chapter_generator.py:1414` chọn nhân vật bằng điều kiện `cid in active_characters_state or st.get("alive", True)`. Vì vậy nhân vật sống ngoài cảnh cũng được gửi toàn bộ văn bản cảnh cho phần tâm lý. Điều này mở đường cho biết bí mật từ xa và phát sinh hai lời gọi AI cho mỗi nhân vật được chọn. Ví dụ 20 nhân vật sống có thể tạo thêm 40 lời gọi nối tiếp, chưa kể các bước kể chuyện. Chưa đo độ trễ và chi phí với model thật.

**Một lượt chưa được lưu như một đơn vị trọn vẹn.** `atomic_write` bảo vệ từng file, không phải cả lượt gồm nhiều file. Sự kiện được ghi sớm; các file còn lại ghi lần lượt. Cần kiểm thử lỗi giữa chừng và hai yêu cầu tiếp tục đồng thời; nên có khóa theo world, mã lượt chống gửi trùng và cơ chế commit/rollback toàn lượt.

**Bộ kiểm tra nhất quán bỏ qua lỗi dịch vụ.** Khi checker không gọi được AI, code trả `consistent=True`, `severity=none`. Khi checker phát hiện lỗi lớn, writer viết lại nhưng không chạy checker lần hai. Nên phân biệt “đã kiểm tra”, “chưa kiểm tra”, “không đạt”; bản chưa kiểm tra có thể giữ ở trạng thái nháp theo lựa chọn của người dùng.

**Living World mới có phần chạy, chưa có chu trình tạo đầy đủ.** Không tìm thấy bước tạo `world_events.json` trong world builder hay prompt sinh events ở bản này. Quest Board có endpoint nhưng chưa thấy giao diện sử dụng. Logic nhận biết quest dựa vào việc ID sự kiện xuất hiện trong câu ghi chú tự do, nên khá mong manh. Nên dùng `discovered_event_ids` rõ ràng.

**Hồi kết chưa hoàn chỉnh ngay cả sau khi sửa import.** Hàm tạo epilogue trả văn bản rồi chỉ lưu `lifecycle_status=completed`, không ghi epilogue vào lịch sử. Luồng continue cũng chưa thấy chặn world đã completed. UI hiện chưa có flow endgame tương ứng. Cần một chu trình: đủ điều kiện → lựa chọn cuối → cao trào → hậu truyện lưu được → đọc lại hoặc chủ động mở phần tiếp theo.

**Một số điều khiển UI chưa tác động đến engine.** `outputLength` ở `PlayPage.tsx` chỉ cập nhật state của giao diện, không gửi cấu hình về backend. Sau một lượt, trang chỉ tải lại play state, chưa tải lại map/đồ thị quan hệ. Nội dung người dùng nhập bị xóa trước khi gửi, nhưng khi lỗi chưa được phục hồi. Đây là các sửa nhỏ nhưng ảnh hưởng trải nghiệm hằng lượt.

**Cấu hình khóa cần được thống nhất.** `build_runtime_config_status` vừa trả bản che key vừa trả `api_key` nguyên văn; CORS hiện cho mọi origin. Nên tách API lưu bí mật khỏi API đọc trạng thái, chỉ trả bản che ở trạng thái, giới hạn origin dùng cho local app. Đây là hành vi thấy trong mã, chưa thử khai thác qua trình duyệt.

## 3. Những quyết định thiết kế nên chốt

### A. Người chơi điều khiển hành động hay cả kết quả?

Hiện input mẫu có cả hành động lẫn kết quả áp đặt, còn luật OOC/checkpoint có thể diễn giải lại ý người chơi. Đề xuất chọn rõ khi tạo world:

- **Nhập vai:** người chơi quyết định ý định/hành động; engine giải quyết kết quả bằng luật thế giới.
- **Đồng tác giả:** người dùng có thể định hướng cảnh, nhịp, biến cố; AI giữ tính nhất quán và chỉ rõ khi cần sửa canon.

Không tự động coi câu “bỏ qua đoạn này” là phá nhập vai trong chế độ đồng tác giả. Các lệnh ngoài truyện nên được nhận diện bằng giao diện hoặc kênh điều khiển rõ ràng.

### B. Checkpoint là cơ hội hay kết quả bắt buộc?

Thiết kế mới muốn thế giới tự trôi, nhưng planner vẫn được yêu cầu dựng chướng ngại để giữ người chơi trong scope. Nên tách ba khái niệm: luật bất biến của thế giới, sự kiện có điều kiện, và mục tiêu kể chuyện. Mục tiêu có thể bị bỏ lỡ hoặc thay bằng một hướng tương đương; luật bất biến mới là phần cần giữ chặt.

Ví dụ: băng cướp đánh làng khi đủ thời gian. Người chơi giúp phòng thủ, đến muộn cứu người, hoặc bỏ qua đều tạo những nhánh hợp lệ. Cơ hội và hậu quả thay đổi; engine không cần đưa lính gác vô cớ để ép main tới làng.

### C. Thế giới biết gì, nhân vật biết gì, người chơi biết gì?

Cần lưu sự thật khách quan tách khỏi tri thức của từng người. Mỗi tri thức nên có nguồn (chứng kiến/nghe kể/suy đoán), thời điểm và độ chắc chắn. Sự kiện ở xa chỉ được người chơi biết khi nhận tin hoặc tới hiện trường. Codex của người chơi chỉ hiện thông tin đã khám phá; Creator có thể xem toàn bộ.

### D. Cảnh giới là thứ bậc hay tên điều kiện chính xác?

Map đang so realm bằng tên bằng nhau. Nếu ý định là “ít nhất Kim Đan”, nhân vật vượt lên Nguyên Anh có thể bị khóa trở lại. Nên xác định bảng thứ bậc riêng cho mỗi world và loại điều kiện “tối thiểu” hay “đúng cảnh giới”. Cũng cần tách cổng nội dung chưa tạo khỏi nơi nhân vật có thể đến nhưng nguy hiểm: hai loại giới hạn tạo cảm giác rất khác nhau.

## 4. Nên thêm gì để ý tưởng phát huy giá trị

1. **Nhật ký hệ quả không spoil.** Hiện những điều nhân vật đã nhận biết: “Nina tin tưởng hơn”, “tin đồn đang lan”, “cơ hội cứu làng đã qua”. Cho lựa chọn một dấu vết rõ ràng.
2. **Quan hệ có ký ức cụ thể.** Lưu lời hứa, món nợ, phản bội, ranh giới cá nhân và sự kiện chung; dùng chúng để chọn phản ứng thay vì chỉ tăng/giảm affinity.
3. **Thất bại vẫn mở truyện.** Không mở được cửa có thể kéo theo bị phát hiện, tìm đồng minh, hoặc đổi mục tiêu. Hạn chế vòng lặp “thử lại cùng điều kiện”.
4. **Hoàn tác và rẽ nhánh toàn trạng thái.** Khi regenerate một lượt, mọi biến đổi từ lượt cũ phải được hoàn lại trước; tóm tắt, ký ức, event và map phải đi cùng nhánh.
5. **Dựng world có điểm xem và sửa.** Sau concept/interview, cho xem ngắn gọn premise, luật sức mạnh, quyền người chơi và xung đột mở đầu; lưu từng bước để có thể tiếp tục khi model lỗi, không phải làm lại từ đầu.
6. **Hiển thị tiến độ và ngân sách một lượt.** Cho biết đang lên tình tiết/viết/kiểm tra, thời gian và token thực tế. Tâm lý chỉ cập nhật NPC liên quan hoặc bị tác động, có giới hạn lời gọi.
7. **Bộ cảnh đánh giá cố định.** Một bí mật mà NPC vắng mặt không được biết; một nhiệm vụ bị bỏ lỡ; một lựa chọn phản bội; một lượt bị gián đoạn; một lần save/restore; một hồi kết. Chạy lặp với cùng dữ liệu giả, rồi kiểm tra văn chương bằng model thật.

## 5. Thứ tự làm đề xuất

**Đợt 1 — vòng chơi đáng tin:** sửa các lỗi đã tái hiện; snapshot đủ file; commit toàn lượt; giữ input khi lỗi; tách test khỏi world thật. Xong khi chơi, save, restore và retry không làm state sai lệch.

**Đợt 2 — một world ngắn thể hiện đúng ý tưởng:** chọn một bối cảnh với 3 NPC, 3 địa điểm, 2 sự kiện nền và 2–3 kết cục. Chứng minh được biết/không biết, bỏ lỡ, lựa chọn có hệ quả và truyện khép lại. Có thể dùng ngân sách 20–30 lượt để đánh giá, không ép số lượt trong luật chơi.

**Đợt 3 — chiều sâu và khả năng mở rộng:** quan hệ có ký ức, world builder có duyệt, nhánh thời gian, quản lý chi phí, đo chất lượng truyện dài.

Tạm hoãn giọng nói, hình minh họa tự sinh mỗi lượt, marketplace, multiplayer và mô phỏng tâm lý mọi NPC. Chúng phù hợp về sau nhưng chưa giải quyết các điểm làm mất niềm tin vào thế giới hiện tại.

## 6. Kết quả kiểm tra và giới hạn

Dependency check đạt; frontend build đạt (cảnh báo bundle lớn); lint có 3 cảnh báo hooks; backend compile đạt sau sửa prompt; hai dịch vụ trả HTTP 200. Bộ test cũ có 110 kiểm tra đạt rồi dừng ở xóa key. Các tái hiện riêng trong mục 1 đã chạy bằng dữ liệu thử, gồm một lượt mock trả 200. Không gọi AI trả phí, không thay đổi world gốc.

Kiểm tra giao diện bằng mắt chưa hoàn tất: lần gọi công cụ trình duyệt bị duyệt tự động từ chối do yêu cầu công cụ Windows; đã dùng node_repl/@oai/sky đúng hướng dẫn nhưng Edge xuất hiện hộp thoại tài khoản/đồng bộ nên dừng thao tác. Kết quả HTTP/build không được xem là chứng minh toàn bộ UI hoạt động.
