# Story Engine — backlog giao agent

Ngày lập: 18/09/2026. Căn cứ: code tại `fc55b72`, sau đợt sửa độ tin cậy và tách cấu trúc. Đây là kế hoạch triển khai, không phải danh sách chức năng đã tồn tại. Các đường dẫn trong tài liệu tính từ gốc repository.

## 1. Mục tiêu sản phẩm

Một thế giới kể chuyện có trạng thái bền vững: player chọn hành động, thế giới giải quyết kết quả, NPC phản ứng theo điều họ biết và lịch sử riêng. Creator cũng chơi nhưng có quyền sửa kết quả. Checkpoint định nghĩa sự việc; kết quả mở. Thất bại, bỏ lỡ hoặc can thiệp sớm đều phải có đường kể chuyện tiếp.

Mốc đầu tiên cần chứng minh điều này bằng một world nhỏ chơi được từ đầu đến cuối. Chưa ưu tiên multiplayer, marketplace, giọng nói, hình ảnh tự sinh mỗi lượt, triển khai SaaS hay mô phỏng tâm lý toàn bộ dân số.

Nguồn quyết định: [DESIGN-PRINCIPLES.md](DESIGN-PRINCIPLES.md). Bản đồ mã: [CODEBASE.md](CODEBASE.md). Hướng dẫn làm việc: [CONTRIBUTING.md](../CONTRIBUTING.md).

## 2. Nền tảng đã làm — không giao lại như tính năng mới

- [x] Khởi chạy môi trường Python/Node, cài dependency và có lockfile.
- [x] Sửa lưu fact/map của world event, snapshot sự kiện, map đọc đúng protagonist, xóa key, lưu và chặn continue sau hồi kết.
- [x] Khóa theo world trong một tiến trình; ghi nhiều file có rollback khi gặp lỗi Python/I/O. **Chưa bảo đảm phục hồi khi tiến trình chết hoặc nhiều worker.**
- [x] Tách backend story/world/prompts/routes và giao diện chơi thành feature.
- [x] 14 test hồi quy, 747 kiểm tra cũ; fixture không cần world riêng; CI backend Windows/Linux và build/lint UI đã đạt ở mốc trên.
- [x] Có save/restore/branch, psychology, world events, canon log, builder review checkpoint và epilogue ở mức hiện tại. Các task bên dưới là hoàn thiện/tích hợp, không dựng lại từ số không.

PR #1 và #2 ở lần kiểm tra trước chưa merge. Người tích hợp phải kiểm tra trạng thái mới nhất, đưa #1 rồi #2 vào nhánh nền hoặc cho agent xuất phát từ nhánh đã chứa cả hai. Không giả định `main` đã có refactor. Tài liệu này chưa tạo GitHub Issues và chưa khởi chạy agent.

## 3. Cách giao và nghiệm thu

- Trạng thái mọi task chưa đánh dấu hoàn thành: **TODO**. `D` là quyết định thiết kế; `F` nền tảng; `W` mô phỏng; `U` trải nghiệm; `Q` chất lượng/phát hành.
- Cỡ **S**: thay đổi hẹp; **M**: một luồng qua vài module; **L**: nhiều hợp đồng dữ liệu. Đây là độ phức tạp, không phải cam kết số giờ. Với L, agent phải tách phần schema, engine và tích hợp thành các PR có thể kiểm tra độc lập.
- Một agent nhận một task hoặc một phần đã chỉ rõ. Không mở rộng sang gameplay khác chỉ vì thấy tiện.
- Dependency nghĩa là hợp đồng/kết quả task đó phải có trên nhánh nền trước khi hoàn tất task sau. Có thể làm mock UI sớm, nhưng không tự sáng tác hợp đồng API khác.
- Mọi dữ liệu mới thuộc world phải đăng ký snapshot/restore/branch, có quy tắc migration và đi cùng commit lượt. Không viết sớm ở giữa pipeline.
- Task thay hành vi phải có test tình huống trước/sau; không sửa assertion cũ để che regression. Khi đổi hành vi theo thiết kế đã duyệt, ghi rõ assertion nào phải thay và vì sao.
- Nghiệm thu chung: test liên quan đạt; backend chạy runner cô lập; trước tích hợp chạy `npm run check`; cập nhật tài liệu; không commit key/save riêng. UI tương tác phải được kiểm tra bằng trình duyệt trên dữ liệu giả, build thành công không thay thế việc này.
- Không gọi AI trả phí khi chưa có ngân sách được giao. Kiểm tra bằng model thật là bước riêng, không phải điều kiện ngầm để agent tự tiêu tiền.
- Nếu baseline đã thay đổi hoặc lỗi mô tả không còn tái hiện: báo bằng chứng, chỉnh phạm vi task; không tái tạo lỗi chỉ để sửa.

## 4. Các quyết định cần chốt

Các mặc định dưới đây là **đề xuất**, không được âm thầm biến thành luật cứng. Agent có thể đọc code, viết ví dụ và đề xuất schema trước; chỉ phần triển khai phụ thuộc quyết định mới phải chờ.

### D01 — Checkpoint khi tiền đề đã mất · M

**Đầu ra:** `docs/decisions/checkpoint-semantics.md`, kèm bảng sự kiện → can thiệp → kết quả hợp lệ.

**Cần chốt:** sự việc bắt buộc xuất hiện dưới hình thức nào nếu player đã ngăn nguyên nhân? Đề xuất phân biệt sự kiện do tác nhân tổ chức và biến cố bất khả kháng; `prevented`, `transformed`, `missed` là cách giải quyết có nguyên nhân, không ép xảy ra cảnh phi lý. Không hiểu “kết quả mở” là player gõ gì cũng thành thật.

**Nghiệm thu:** mô tả ít nhất sáu tình huống: tham gia, bỏ qua, đến muộn, ngăn sớm, tác nhân chết, địa điểm biến mất. Nêu rõ đâu là luật thế giới, đâu là mục tiêu kể chuyện. Chủ dự án chọn quy tắc trước W03.

### D02 — Ai được thấy thông tin gì · M

**Đầu ra:** `docs/decisions/visibility.md`, ma trận world/NPC/player/creator.

**Cần chốt:** player được biết hơn nhân vật đến đâu qua quest/map/log? Đề xuất: player có thông tin tổng quan được cho phép, nhưng bí mật động cơ/danh tính không tự lộ; NPC vẫn chỉ dùng tri thức của họ. Creator có chế độ xem toàn cảnh riêng. UI mode chưa phải cơ chế phân quyền nhiều người dùng.

**Nghiệm thu:** sáu ví dụ có bí mật, tin đồn sai, nghe kể, sự kiện xa, quest deadline và suy nghĩ NPC; mỗi ví dụ chỉ rõ thông tin được lưu và được trả ở từng API. Chủ dự án duyệt trước W01/W05/U03.

### D03 — Giải quyết hành động đa thể loại · M

**Đầu ra:** `docs/decisions/action-resolution.md`.

**Cần chốt:** đánh giá theo năng lực, công cụ, tiếp cận, môi trường, đối kháng và đánh đổi; dùng luật xác định hay xác suất có seed? Không áp một thang sức mạnh cho mọi thể loại. Nhân vật có thể thay đổi tính cách đến đâu sau trải nghiệm?

**Nghiệm thu:** cùng một kiểu hành động trong trinh thám, đời thường và fantasy đều giải thích được; phân biệt bất khả thi, có điều kiện, thành công một phần và thất bại; thống nhất trường dữ liệu cùng lý do kết quả. Phần biến đổi tính cách có thể hoãn, profile vẫn được dùng ngay.

### D04 — Creator sửa lịch sử như thế nào · S

**Đầu ra:** `docs/decisions/creator-edits.md`.

**Cần chốt:** sửa tại tick hiện tại, quay lại nhánh cũ hay viết lại quá khứ? Đề xuất mặc định sửa hiện tại có revision và ghi chú; sửa quá khứ tạo nhánh từ mốc tương ứng. Không tự động tái viết mọi chương đã đọc. Chốt ứng xử với ký ức/tóm tắt mâu thuẫn sau sửa.

**Nghiệm thu:** ví dụ cứu người đã chết, đổi kết quả event, bỏ một lời hứa; nêu snapshot nào còn hợp lệ và UI báo gì. Dùng cho W07.

## 5. Nền tảng có thể giao ngay

### F01 — Tách trạng thái cấu hình khỏi bí mật · M · Ưu tiên 0

**Phụ thuộc:** không.

**Hiện trạng:** `build_runtime_config_status` trả `api_key` nguyên văn; UI có kiểu dữ liệu tương ứng. Không được chỉ xóa field backend rồi làm hỏng Settings.

**Phạm vi:** `backend/app/storage.py`, `routes/runtime_routes.py`, `ui/src/api/client.ts`, `pages/SettingsPage.tsx`. GET chỉ trả trạng thái/giá trị che. PUT biểu đạt rõ giữ key, thay key và xóa key; vẫn giữ thứ tự override world/app đã sửa. Không ghi secret vào log, thông báo lỗi hay response kiểm tra kết nối.

**Nghiệm thu:** key giả có sentinel không xuất hiện trong GET app/world, lỗi hoặc export; lưu model với ô key trống không vô tình xóa key; thao tác xóa thực sự xóa; thay key dùng được qua mock provider. Test API và luồng Settings.

### F02 — An toàn nội dung và truy cập ứng dụng local · M · Ưu tiên 0

**Phụ thuộc:** không; phối hợp F01 tại cấu hình.

**Hiện trạng:** `application.py` cho mọi origin; `PlayNarrative.tsx` đưa output vào HTML trực tiếp. Cần kiểm tra cả export HTML và các renderer khác.

**Phạm vi:** giới hạn origin local cấu hình được; xác định kiểm tra origin/host hoặc token phiên cho API thay đổi trạng thái local nếu cần, vì CORS một mình không phải xác thực. Hiển thị truyện dạng text/Markdown có xử lý HTML an toàn; escape bản xuất. Không xây hệ thống tài khoản trong task này.

**Nghiệm thu:** nội dung như `<img onerror=...>`/`<script>` không thực thi trong màn chơi và export; định dạng xuống dòng vẫn đúng; origin local hợp lệ hoạt động, origin lạ không được đọc/thay đổi state qua trình duyệt theo mô hình đã chọn; có test chính sách và kiểm tra browser.

### F03 — Sửa vòng tương tác màn chơi · M · Ưu tiên 0

**Phụ thuộc:** không.

**Phạm vi:** `features/play/usePlaySession.ts`, các view và API client. Giữ bản nhập khi gửi lỗi; không đè phần người dùng vừa gõ; chặn nhấn gửi liên tiếp ở UI; reload map/quan hệ/inventory theo state đã commit; nối output length vào cấu hình backend thực sự; hủy/bỏ kết quả tải của world cũ khi đổi trang. Không thay luật độ dài truyện.

**Nghiệm thu:** lỗi mạng giữ đúng bản nhập, retry gửi đúng một lần ở UI; đổi world lúc request cũ đang chạy không hiển thị nhầm; chọn độ dài được backend nhận và khôi phục sau reload; map/quan hệ cập nhật sau turn/restore/regenerate. Bổ sung kiểm tra UI cho các tình huống này.

### F04 — Version dữ liệu và danh mục state của world · M · Ưu tiên 1

**Phụ thuộc:** không.

**Phạm vi:** `storage.py`, `world/templates.py`, `services/validators.py`, `models.py`, các route import/save. Tạo schema version và migration có kiểm soát; tập trung danh mục file state để tính năng mới không bị bỏ khỏi save. Phân biệt dữ liệu cốt lõi và cache có thể dựng lại. Giữ JSON hiện tại, không tự chuyển sang database.

**Nghiệm thu:** world/save cũ mở được; migration lặp lại không đổi kết quả; bản version mới chưa hỗ trợ bị từ chối có giải thích; dữ liệu gốc có backup khi migration; file thiếu/tệp JSON hỏng không bị âm thầm ghi đè. Fixture cũ/mới round-trip save/export/import.

### F05 — Mã lượt chống xử lý trùng và kiểm tra revision · L · Ưu tiên 1

**Phụ thuộc:** F04.

**Phạm vi:** `models.py`, `routes/chapter_routes.py`, `chapter_generator.py`, persistence, API client. Mỗi hành động có request ID và expected revision; lưu receipt với commit kết quả. Request trùng cùng nội dung trả lại kết quả đã có; cùng ID khác nội dung báo conflict; revision cũ không ghi đè. UI retry giữ ID, hành động mới tạo ID mới. Kiểm tra mọi đường ghi world cạnh tranh: continue, creator, restore, regenerate, builder.

**Nghiệm thu:** hai request đồng thời cùng ID chỉ tạo một lượt/tick và một lượt gọi pipeline; response bị mất sau commit rồi retry không gọi AI lại; request revision cũ không thay state; receipt không bị dùng nhầm khi restore/branch. Nêu rõ phạm vi chống trùng trong một tiến trình và qua restart, không hứa exactly-once với nhà cung cấp AI bên ngoài.

### F06 — Phục hồi lượt bị gián đoạn giữa lúc ghi · L · Ưu tiên 1

**Phụ thuộc:** F04, F05.

**Phạm vi:** `persistence.py`, application startup và registry state. Đề xuất trước cơ chế journal/commit manifest hoặc cơ chế tương đương; phục hồi trước khi phục vụ world. Bảo vệ lượt truyện, receipt và các file hệ quả như một đơn vị. Giữ chế độ một server worker; nhiều worker chỉ được hỗ trợ nếu thực sự có khóa liên tiến trình và test.

**Nghiệm thu:** tiến trình con bị dừng tại các điểm ghi rồi khởi động lại: world hoàn toàn trước hoặc sau lượt, không lai; receipt đúng với state; phục hồi chạy lại an toàn; xử lý thiếu dung lượng/quyền ghi không xóa bản tốt cuối cùng. Agent phải ghi phạm vi bảo đảm thực tế; không gọi đây là chống mất điện nếu chưa kiểm chứng điều kiện filesystem.

### F07 — Checker phân biệt chưa kiểm tra và đã đạt · M · Ưu tiên 1

**Phụ thuộc:** không.

**Hiện trạng:** `story/consistency.py` coi lỗi gọi checker là consistent; bản writer sửa sau lỗi lớn chưa được kiểm tra lại.

**Phạm vi:** thêm trạng thái `passed/failed/unavailable`; kiểm tra lại bản sửa trong giới hạn retry; lỗi schema/luật xác định luôn chặn commit. Chế độ cho phép lưu bản chưa kiểm tra là chính sách rõ ràng, có cảnh báo, không giả thành passed; mặc định mới đề xuất giữ draft khi unavailable, cần ghi rõ tác động tương thích.

**Nghiệm thu:** timeout, JSON hỏng, lỗi lớn cả hai lần, sửa thành công đều cho trạng thái đúng; draft không tăng tick hay áp dụng hậu quả; không có vòng retry vô hạn; UI giải thích được và có đường thử lại. Mock test cho từng nhánh.

## 6. Mô phỏng thế giới và luật chơi

### W01 — Sự thật thế giới và tri thức riêng có nguồn · L · Ưu tiên 1

**Phụ thuộc:** D02, F04.

**Phạm vi:** `models.py`, `psychology.py`, `story/memory.py`, canon storage; mở rộng cấu trúc hiện có. Fact có ID ổn định; tri thức có chủ thể, nguồn, thời điểm, mức chắc chắn và liên kết fact khi biết được. Tin đồn/suy đoán có thể sai mà không sửa sự thật khách quan. Chính sách projection dùng chung cho context và API.

**Nghiệm thu:** NPC A chứng kiến, B nghe kể sau, C chưa biết; ba góc nhìn khác nhau và đúng qua save/restore; tin đồn sai không đổi canon; save cũ được chuyển mà không biến toàn bộ kiến thức thế giới thành kiến thức mọi NPC. Test kiểm tra payload thực gửi vào model, không chỉ response API.

### W02 — Chọn NPC và ngữ cảnh theo khả năng quan sát · M · Ưu tiên 1

**Phụ thuộc:** W01.

**Hiện trạng:** điều kiện `active or alive` ở `chapter_generator.py` đưa cả NPC sống ngoài cảnh vào xử lý tâm lý.

**Phạm vi:** scene participants/observers, nguồn truyền tin và việc ngoài cảnh; perception chỉ nhận phần sự kiện được thấy/nghe; tâm lý dùng profile, ký ức và perception của đúng người. Giới hạn số NPC/lượt; xử lý bỏ qua hoặc lỗi tâm lý có trạng thái rõ.

**Nghiệm thu:** NPC sống ở xa không nhận transcript bí mật; NPC cùng nơi nhưng không nghe được cũng không biết; người nhận tin về sau cập nhật đúng nguồn; thêm 100 NPC không liên quan không tăng số lời gọi tâm lý. Không dùng model tự hứa “đừng spoil” thay cho lọc dữ liệu.

### W03 — Checkpoint là sự việc, outcome được giải quyết riêng · L · Ưu tiên 1

**Phụ thuộc:** D01, F04, W01.

**Phạm vi:** `checkpoint_engine.py`, `world_events.py`, schema, prompt planner/checker. Tách điều kiện kích hoạt, vòng đời sự việc và kết quả thực tế. Hỗ trợ kết quả đa dạng và kết quả không có trong danh sách mẫu nhưng vẫn qua luật/schema. Tương thích checkpoint cũ bằng adapter, không xóa ngay.

**Nghiệm thu:** một biến cố có các đường tham gia/bỏ lỡ/can thiệp sớm khác nhau, mỗi đường tiếp tục được; không dựng chướng ngại vô lý để ép outcome; biến cố đã giải quyết không chạy lần hai; tác nhân chết/địa điểm mất xử lý theo D01; test không buộc văn bản AI giống hệt mẫu.

### W04 — Bộ giải quyết hành động theo bối cảnh · L · Ưu tiên 1

**Phụ thuộc:** D03, W03.

**Phạm vi:** module mới `app/story/action_resolution.py`, model action intent/outcome, planner/writer và luật map. Player gửi ý định; engine xác nhận tài nguyên, điều kiện và quyền tiếp cận; kết quả là đầu vào cho lời kể, writer không tự đổi kết quả đã commit. Giữ cơ chế hiện có qua adapter cho world cũ.

**Nghiệm thu:** hành động cùng dữ kiện được giải thích nhất quán; không đủ công cụ mở ra đánh đổi/hướng khác; thất bại có diễn biến tiếp; world đời thường không cần realm/EXP; nếu dùng xác suất có seed/log tái hiện, không gọi xác suất do LLM tự bịa là số đo khách quan.

### W05 — Vòng đời sự kiện, khám phá và quest API · M · Ưu tiên 1

**Phụ thuộc:** W01, W03.

**Hiện trạng:** quest discovery dò event ID trong ghi chú tự do, mới trả các event pending.

**Phạm vi:** `world_events.py`, `routes/discovery_routes.py`, schema. Discovery record có event ID và nguồn; quest là góc nhìn của player lên cơ hội/sự việc. Biểu diễn đang diễn ra, hoàn tất, bỏ lỡ và thông tin deadline chỉ khi biết; thời gian thế giới tiến theo policy tick đã xác định, không âm thầm thêm đồng hồ thời gian thực.

**Nghiệm thu:** thay lời văn ghi chú không làm mất quest; event ở xa diễn biến nhưng không tự spoil; quest cập nhật sau event/restore; không suy deadline từ một điều kiện bất kỳ; điều kiện thiếu dữ liệu có lỗi/unknown rõ thay vì kích hoạt nhầm.

### W06 — Ký ức quan hệ dựa trên sự kiện cụ thể · M · Ưu tiên 2

**Phụ thuộc:** W01, W02, W03.

**Phạm vi:** `psychology.py`, `story/memory.py`, schema và graph projection. Ghi lời hứa, nợ, giúp đỡ, phản bội, trải nghiệm chung với ID sự kiện/tick và người biết. Chọn ký ức liên quan vào context; có thể giữ điểm affinity nhưng không dùng nó thay toàn bộ quan hệ.

**Nghiệm thu:** giữ lời/thất hứa tạo ký ức và phản ứng khác nhau; người không biết việc phản bội chưa đổi quan hệ vì việc đó; tóm tắt dài hạn giữ được ký ức trọng yếu; regenerate/branch không giữ món nợ ở tương lai đã bỏ. Test payload và state, đánh giá văn chương riêng.

### W07 — Creator sửa kết quả có revision và lịch sử · L · Ưu tiên 2

**Phụ thuộc:** D04, F05, W03, W06.

**Phạm vi:** `routes/creator_routes.py`, `routes/studio_routes.py`, `commit_sanitizer.py`, UI creator. Dùng lịch sử canon/revision hiện có; thêm preview thay đổi, nguồn creator, lý do, kết quả validation và snapshot phù hợp. Chọn chế độ Player/Creator ở luồng lệnh; không tin field model trả về để tự nâng quyền Creator.

**Nghiệm thu:** Player nói “kẻ địch chết ngay” không tự sửa canon; Creator có thể chủ động sửa kết quả đúng luồng; sửa không để inventory/event/knowledge mâu thuẫn âm thầm; conflict revision được báo; có thể khôi phục theo D04. Không tự xây auth multi-user trong bản local.

### W08 — Bộ nhớ dài hạn và truy xuất không rò tri thức · M · Ưu tiên 2

**Phụ thuộc:** W01, W06.

**Phạm vi:** `story/memory.py`, `rag.py`, summarizer prompt. Phân tách canon khách quan, diễn biến nhánh, tóm tắt và ký ức nhân vật; chọn ngữ cảnh có ngân sách; giữ nguồn cho mệnh đề quan trọng; có chiến lược vô hiệu hóa cache sau creator edit/restore.

**Nghiệm thu:** 50–100 lượt dữ liệu tổng hợp không làm mất lời hứa và sự kiện then chốt; token context trong giới hạn cấu hình; tóm tắt không đưa bí mật vào context NPC không biết; thay nhánh không truy xuất fact của nhánh khác. Không hứa chất lượng truyện dài chỉ từ test token.

## 7. Hoàn thiện trải nghiệm

### U01 — Restore, regenerate và branch hoàn toàn nhất quán · L · Ưu tiên 1

**Phụ thuộc:** F04, F05; tích hợp lại khi W01/W05/W06 thêm state.

**Phạm vi:** storage snapshot, creator/chapter routes, hook phiên chơi. Audit regenerate hiện có và tạo snapshot trước lượt; regenerate bắt đầu từ đó, không cộng dồn kết quả cũ. UI chọn save/branch rõ, đồng bộ tất cả bảng sau thay đổi. Không gọi đây là undo nếu chỉ xóa văn bản chương.

**Nghiệm thu:** lượt đổi đồ, tick, fact, event, map, ký ức và summary; regenerate/restore khôi phục đầy đủ, không áp hai lần; branch mới độc lập với nguồn; lỗi khi sinh lại giữ bản cũ đọc được và không mất nhánh. So sánh state trước/sau theo registry, trừ metadata có chủ đích.

### U02 — World builder có duyệt, tiếp tục và tạo sự kiện · L · Ưu tiên 1

**Phụ thuộc:** D01–D03, F04, F05, W03, W05.

**Phạm vi:** `routes/builder_routes.py`, `prompts/world_builder.py`, `WorldBuilderModal.tsx`. Mở rộng bước confirm-checkpoints hiện có thành concept → luật/góc nhìn → NPC/địa điểm → sự kiện → kiểm tra toàn gói → bắt đầu. Lưu draft từng bước, chỉnh một phần và resume; sinh `world_events` có schema và ID hợp lệ.

**Nghiệm thu:** lỗi model giữa bước không mất phần đã duyệt; reload tiếp tục đúng bước; retry không nhân đôi NPC/event; không đánh dấu complete khi tham chiếu sai; world mới thực sự tạo được quest/event; sửa concept làm rõ phần cần sinh lại, không tự ghi đè chỉnh sửa tay.

### U03 — Quest, nhật ký hệ quả, túi đồ và bản đồ · L · Ưu tiên 1

**Phụ thuộc:** D02, F03, W01, W05; bổ sung ký ức từ W06 sau.

**Phạm vi:** `features/play`, `InventoryGrid.tsx`, `LocationMap.tsx`, discovery API; tái dùng panel hiện có. Thêm Quest Board và feed nhật ký từ sự kiện đã commit có ID/tick/nguồn. Phân biệt inventory của ai, thông tin đã biết và điều chưa rõ. Nhật ký thế giới phải ghi cả sự việc ngoài lựa chọn trực tiếp khi player được biết.

**Nghiệm thu:** một lượt cứu NPC cập nhật quest, log, vị trí và đồ nhất quán; bỏ lỡ hiện hậu quả đúng lúc được biết; không lộ secret qua tiêu đề, graph, tooltip hay payload API; empty/loading/error hoạt động; mobile không che ô nhập; bàn phím mở/đóng panel được. Không dựng hệ thống giao dịch/crafting mới trong task này.

### U04 — Luồng hồi kết và đọc tiếp · M · Ưu tiên 2

**Phụ thuộc:** F03, U01; dùng W03 khi kết cục lấy từ sự kiện mới.

**Phạm vi:** chapter API client, `world/endgame.py`, play feature. Nối UI điều kiện kết thúc → lựa chọn cuối → epilogue đã lưu → đọc lại hoặc tạo nhánh/phần tiếp theo có chủ đích. Backend đã lưu epilogue/idempotent, phải tái dùng.

**Nghiệm thu:** reload vẫn thấy hồi kết; nhấn hai lần không sinh hai epilogue; world completed không hiện ô continue có thể gửi được; lỗi AI không đóng world; endless không tự đóng vì hết số lượt; thất bại có thể là kết cục hợp lệ.

### U05 — Tiến độ, token và giới hạn chi phí · L · Ưu tiên 2

**Phụ thuộc:** F05, F07, W02.

**Phạm vi:** `llm_client.py`, orchestration, endpoint tiến độ và menu nhỏ UI. Ghi stage, thời gian, số call, retry, token provider báo; cost chỉ tính khi có giá/đơn vị/model rõ. Chọn polling hoặc stream sau khi có contract. Giới hạn call/token/lượt và tổng phiên cấu hình được; giữ kết quả job khi mất kết nối.

**Nghiệm thu:** UI thấy planner/writer/checker đang chạy; usage có cả retry/tâm lý, thiếu dữ liệu hiện unknown chứ không 0; vượt ngân sách dừng ở ranh giới an toàn không commit nửa lượt; hủy không cam kết hoàn tiền lời gọi đã gửi; reconnect lấy được trạng thái/kết quả. Mock hoàn toàn khi test.

## 8. Chất lượng và chuẩn bị public

### Q01 — Hạ tầng test giao diện và bộ hành trình đầu tiên · M · Ưu tiên 1

**Phụ thuộc:** không; phối hợp F03 trên mock API.

**Phạm vi:** test component/hook và E2E tối thiểu, script npm, CI. Chọn một bộ công cụ phù hợp với phiên bản React/Vite đang dùng; mock provider và dữ liệu tạm, không dùng key thật. Đừng thêm hai framework cho cùng một nhu cầu.

**Nghiệm thu:** test được nhập/gửi lỗi/retry, đổi world giữa request, restore và đọc epilogue; có cách chạy cục bộ và CI; test thất bại khi cố ý đưa regression tương ứng vào. Fixture không phụ thuộc tài khoản, dữ liệu chơi riêng hoặc dịch vụ AI.

### Q02 — World mẫu chứng minh ý tưởng · M · Ưu tiên 1

**Phụ thuộc:** W02–W05, U01–U03, Q01.

**Phạm vi:** fixture world riêng do dự án tạo: 3 NPC, 3 địa điểm, 2 sự kiện nền, một bí mật, một lời hứa và vài khả năng kết cục. Đề xuất bối cảnh trinh thám nhỏ để kiểm tra không phụ thuộc cảnh giới. Với quan hệ sâu/hồi kết UI, bổ sung W06/U04 trước nghiệm thu mở rộng.

**Nghiệm thu:** chạy sáu hành trình: NPC vắng mặt không biết, tin đồn sai, can thiệp sớm, bỏ lỡ sự kiện, thất bại mở hướng mới, save/branch giữ đúng hậu quả. Cố định dữ kiện/seed nếu có, không bắt mọi người chơi đi cùng cốt truyện hoặc đúng 20 lượt.

### Q03 — Đánh giá truyện bằng model thật có ngân sách · M · Ưu tiên 2

**Phụ thuộc:** Q02, W06, W08, U04, U05; cần ngân sách/model được chủ dự án giao.

**Phạm vi:** rubric và runner đánh giá: quyền tác động, nhất quán, hạn tri, hệ quả, nhịp, giọng nhân vật, lặp, độ trễ/chi phí. Trước khi chạy thật phải có bản dry-run và ước lượng. Lưu model/config/seed/prompt version cùng kết quả, loại secret.

**Nghiệm thu:** báo cáo có ví dụ tốt/xấu và trường hợp thất bại, so cùng kịch bản qua nhiều lần; tách luật xác định khỏi đánh giá chủ quan; không dùng LLM judge làm trọng tài duy nhất. Chủ dự án đọc mẫu để duyệt chất lượng. Chưa có ngân sách thì task dừng ở runner/rubric, không báo đạt chất lượng AI.

### Q04 — Dọn cảnh báo và tiếp tục tách module có mục tiêu · M · Ưu tiên 2

**Phụ thuộc:** F03, Q01; tránh đổi cùng module với feature đang chạy.

**Phạm vi:** sửa ba cảnh báo effect ở play hook/CreatorToolsModal/LocationMap bằng quản lý dependency đúng, không tắt rule. Lazy-load trang/bảng nặng để xử lý cảnh báo bundle dựa trên số đo. Tách storage runtime config, builder hoặc creator routes khi có ranh giới rõ; chuyển nhóm test cũ dần sang test độc lập trước khi bỏ compatibility.

**Nghiệm thu:** lint không còn ba cảnh báo; không vòng fetch vô hạn; có số bundle trước/sau và test điều hướng; các điểm import cũ có kế hoạch bỏ, không xóa làm hỏng 747 checks. Không đổi toàn bộ framework hoặc định dạng dữ liệu để “chuyên nghiệp hóa”.

### Q05 — Gói phát hành public local-first · M · Ưu tiên 3

**Phụ thuộc:** F01–F07, U01, Q01–Q04 và nghiệm thu world mẫu.

**Phạm vi:** kiểm tra clone sạch, tài liệu setup Windows/Linux, `.env.example` không có key, guide lỗi thường gặp, issue/PR template, changelog, attribution và danh sách giới hạn. Audit import/export, đường dẫn world/save ID, secrets trong lịch sử Git và dependency thực dùng; không coi đây là bằng chứng bảo mật toàn diện. Chuẩn bị bản tag/release đề xuất và checklist thao tác.

**Nghiệm thu:** người mới clone/cài/chạy/test bằng tài liệu mà không cần dữ liệu tác giả; fixture có nguồn và quyền sử dụng rõ; xác minh export không mang runtime secret; key không có trong file/commit đưa ra public. Chủ dự án chọn LICENSE và duyệt chuyển visibility/phát hành ở bước cuối. Task chuẩn bị không tự công khai repo, merge hoặc publish.

## 9. Thứ tự và cách chia agent

### Đợt A — có thể giao ngay

| Luồng | Task | Khu vực chính | Lưu ý |
| --- | --- | --- | --- |
| Agent A | F01 rồi phần backend F02 | Runtime config, application | Thống nhất API Settings trước khi sửa UI |
| Agent B | F03 và phần renderer F02 | Play feature | Một người sở hữu play hook trong đợt này |
| Agent C | F04 | Schema/storage registry | Không sửa runtime config mà Agent A đang đổi |
| Agent D | Q01 rồi F07 | Test UI, consistency | Với Q01 dùng mock contract thống nhất cùng B |
| Chủ dự án + agent thiết kế | D01–D04 | Chỉ tài liệu/quyết định | Có thể diễn ra song song, chưa khóa luật tùy tiện |

Nếu chỉ có một agent: F01 → F02 → F03 → F04 → F07 → Q01, đồng thời chuẩn bị bản quyết định. Đây là thứ tự đề xuất, không phải yêu cầu mở nhiều agent.

### Đợt B — nền state và hạn tri

F05 → F06 → U01; nhánh khác W01 → W02. Sau khi D01 đã chốt: W03. F05/F06/U01 đụng persistence và chapter routes nên tích hợp tuần tự. W02/W03 đụng chapter pipeline nên không giao hai agent cùng tự tích hợp lên chung thư mục.

### Đợt C — vòng chơi đúng ý tưởng

W04 và W05 sau W03; U02/U03 sau hợp đồng events/visibility; ghép Q02 thành bản chơi được. W06 rồi W08 bổ sung chiều sâu. Tiêu chí qua đợt: lựa chọn tạo hệ quả, NPC không toàn tri, bỏ lỡ/thất bại không bế tắc và restore tái tạo đúng world.

### Đợt D — công cụ tác giả, chất lượng và public

W07, U04, U05 → Q03; Q04 làm xen kẽ khi module ổn định; Q05 là cổng phát hành cuối. Không đợi public mới sửa lộ key/HTML ở F01/F02.

### Quy tắc tích hợp

- Giao trên worktree/checkout riêng nếu chạy đồng thời; một người tích hợp chịu trách nhiệm nhánh nền.
- Đặt branch theo task, ví dụ `task/F03-play-session`; PR ghi dependency và giới hạn.
- Duyệt schema/API trước khi hai agent backend/UI triển khai riêng; schema trung tâm có một người sở hữu mỗi đợt.
- Chỉ đánh dấu DONE khi đã review, kiểm tra và tích hợp vào nhánh được chọn; “agent đã gửi code” là trạng thái chờ review.
- Không tự mở mọi task cùng lúc. Bắt đầu 2–3 task độc lập, hoàn tất rồi mới tăng phạm vi.

## 10. Prompt mẫu giao agent

```text
Thực hiện task <ID — tên> trong docs/AGENT-BACKLOG.md của Story Engine.

Nhánh nền: <branch/commit đã chứa dependency>.
Phạm vi lần giao này: <toàn task hoặc phần schema/engine/UI cụ thể>.
Các quyết định đã duyệt: <đường dẫn decision + nội dung liên quan>.

Đọc AGENTS.md, CONTRIBUTING.md, docs/DESIGN-PRINCIPLES.md và docs/CODEBASE.md.
Đối chiếu code hiện tại trước khi sửa; không giả định mô tả cũ vẫn đúng.
Giữ player chọn hành động, kết quả mở, NPC hạn tri và hỗ trợ nhiều thể loại.
Không tự đổi quyết định chưa chốt hoặc mở rộng sang task khác.
Dữ liệu world mới phải có migration và đi cùng save/restore/branch/commit lượt.
Không dùng world cá nhân, không gọi AI trả phí ngoài ngân sách đã giao.

Hoàn thành các tiêu chí nghiệm thu của task; test bằng dữ liệu giả độc lập.
Với UI, kiểm tra tương tác thực, không chỉ build.
Giao lại: vấn đề → thay đổi → file chính → test đã chạy/kết quả → giới hạn
→ ảnh/ghi nhận UI nếu có → cách thử lại → PR hoặc diff để review.
Không báo DONE khi còn tiêu chí chưa đạt. Không tự merge/public/deploy.
```

## 11. Gói giao đầu tiên được đề xuất

**F03 — Sửa vòng tương tác màn chơi**, kèm Q01 ở phạm vi test cho F03, là gói đầu tiên dễ quan sát kết quả: không mất nội dung khi lỗi, chọn độ dài có tác dụng, dữ liệu bảng cập nhật đúng và đổi world không lẫn trạng thái. Có thể giao F01 song song vì ít đụng file. Chuẩn bị D01/D02 trong lúc hai gói này chạy để đợt mô phỏng không bị chặn bởi thiếu quyết định.
