# Review Đợt A — 18/09/2026

## Kết luận tái kiểm tra lần 4 — đóng các finding của vòng review

Đã đọc `submitAction`, `handleRetryDraft` và binding nút Retry: retry dùng trực tiếp `draft.userInput`, giữ nguyên ô nhập, dùng chung khóa gửi và token world, xóa draft khi commit thành công. Hai test hook mới phủ reload với input rỗng và input đang chứa hành động khác; test component xác nhận đúng callback.

Reviewer chạy lại `npm run test:ui` (19 test đạt) và `npm run build` (đạt, còn cảnh báo bundle lớn). Backend không chạy lại ở lượt này vì bản sửa được kiểm tra chỉ thuộc UI; kết quả 41 backend test/legacy ở lần trước vẫn là bằng chứng gần nhất của reviewer. E2E lượt này là kết quả agent báo cáo, không ghi là reviewer vừa chạy lại.

Không còn finding mở trong phạm vi review R01–R06 và draft retry đã nêu. Có thể chuyển sang bước chuẩn bị commit/PR tích hợp, nhưng chưa có commit/merge nào do reviewer thực hiện. Đây không phải chứng nhận mọi task tương lai hoặc mọi đường chạy đều không còn lỗi. Hai cảnh báo effect, giới hạn draft theo phiên tab và quyết định D01–D04 vẫn giữ nguyên trạng thái trước.

Các mục bên dưới là lịch sử phát hiện và tái kiểm tra, không phải danh sách lỗi còn mở.

---

## Tái kiểm tra lần 3 — world config và draft UI

Hai lỗi world override trong lần review trước đã qua tái hiện: bật editor giữ provider/URL custom; replace key làm key mới trở thành key hiệu lực. `npm run check` hoàn thành ở bản này (41 backend test, legacy, 17 UI test, build/lint; hai cảnh báo effect cũ).

**Còn một lỗi P2 trong luồng draft mới:** `ui/src/features/play/PlayNarrative.tsx:84` nối nút Retry action vào `handleSend`, nhưng `usePlaySession.ts:233` lấy nội dung ô nhập thay vì `draft.userInput`. Sau reload, draft được phục hồi còn ô nhập rỗng; bấm Retry không gọi API. Nếu đã gõ hành động khác, nút Retry lại gửi hành động mới đó, không phải hành động tạo draft. Test hook bổ sung phục hồi draft có `userInput='open the door'`, gọi đúng callback của nút và kỳ vọng gửi hành động này đã thất bại: số lời gọi API bằng 0.

Hướng sửa: callback retry riêng truyền trực tiếp hành động trong draft vào hàm gửi chung; không dùng chuỗi setInput rồi handleSend vì closure có thể vẫn giữ input cũ. Bảo toàn phần đang gõ khi retry draft. Nghiệm thu bằng test reload → Retry và đang gõ hành động mới → Retry; cả hai phải gửi đúng hành động draft, có khóa chống gửi trùng và không xóa bản nhập khác. Nếu muốn người chơi chỉnh hành động trước khi thử lại, đổi thành thao tác nạp vào ô nhập có nhãn rõ thay vì tự gửi.

File test tạm đã được xóa, log giữ ngoài repo. Không sửa implementation hoặc commit. SessionStorage chỉ giữ draft trong phiên tab, không tương đương save world bền vững; đây là giới hạn cần ghi rõ, không phải yêu cầu chuyển sang database ở đợt này.

---

## Tái kiểm tra sau bản sửa R01–R06

Đã chạy lại `npm run check`: 39 backend test, legacy, 14 UI test, build/lint đạt (vẫn hai cảnh báo effect và cảnh báo bundle). Playwright 1 test đạt. Test race bổ sung của reviewer nay cũng đạt. Các tình huống cũ R02–R06 đã được sửa trong phạm vi tái kiểm tra; R01 ở app config cũng đổi model hiệu lực đúng.

**Chưa đóng R01:** còn hai lỗi ở `backend/app/routes/runtime_routes.py` trong nhánh world override:

1. **P1 — Thay key nhưng chain vẫn dùng key cũ (dòng 163).** Tạo world chain một node có key giả OLD, sau đó PUT `api_key_action=replace, openrouter_api_key=NEW`. `get_effective_fallback_chain(world)[0].api_key` vẫn là OLD do biểu thức ưu tiên key trong node. Cần xử lý keep/replace/delete trên nguồn secret thực dùng; test phải xác nhận header provider nhận key mới. Không in key thật ra log.
2. **P1 — Sửa tùy chọn không liên quan làm mất provider riêng của world (dòng 161–162).** Tạo world chain một node custom với URL local, rồi chỉ PUT `editor_enabled=true`. Node bị chuyển sang provider app `openrouter`, URL thành rỗng. Điều này có thể làm lời gọi sau gửi key/ngữ cảnh world sang nhà cung cấp ngoài ý định. Không suy ra một node luôn là bản sao cấu hình app; chỉ cập nhật field được yêu cầu, bảo toàn target của override khi sửa editor/role/model riêng. Thêm test bật editor và đổi role không đổi provider/URL/key của chain.

Hai tình huống đều tái hiện bằng world tạm và key giả; không gửi HTTP ra nhà cung cấp. Chưa sửa implementation hay commit.

Lưu ý về backlog: giao diện lưu/hiển thị draft lỗi checker là phần nối tiếp F07/luồng xử lý lỗi phiên chơi. Không mặc nhiên chuyển sang U04 (hồi kết) hay W07 (Creator) nếu chưa thống nhất lại phạm vi. Chặn commit khi failed đã đạt, nhưng trả draft trong response không đồng nghĩa draft được lưu bền vững hoặc hiện trên UI.

---

## Bản review ban đầu (giữ để đối chiếu)

Phạm vi: diff chưa commit của F01–F04, F07, Q01 trên nền refactor. Review này không sửa implementation, không commit/merge. Bản nháp D01–D04 vẫn chưa được coi là luật đã duyệt.

## Kết luận

Chưa nên nghiệm thu toàn bộ Đợt A. Bộ kiểm tra hiện có đạt, nhưng có sáu vấn đề tái hiện/đối chiếu được bên dưới. Đặc biệt, một test mới đang xác nhận hành vi commit khi checker vẫn failed; test xanh không chứng minh đáp ứng yêu cầu F07.

## R01 — P1: Đổi model/provider khi giữ key không cập nhật lựa chọn thực tế

Vị trí: `backend/app/routes/runtime_routes.py:73–82`.

Tái hiện: PUT key giả cùng model A để tạo fallback chain; tiếp tục PUT `api_key_action=keep`, model B. Response báo `model_name=B`, nhưng `get_effective_fallback_chain()[0].model` vẫn là A. Settings mới không gửi lại key nên đây là luồng đổi model thông thường. Provider/base URL cũng có cùng nguy cơ lệch với node đã lưu.

Nguyên nhân: nhánh đồng bộ fallback chain nay chỉ chạy khi replace key, trong khi LLM client ưu tiên chain. Cần xác định node nào thuộc cấu hình đơn, đồng bộ metadata mà giữ secret và không phá chain nhiều node do người dùng cấu hình.

Nghiệm thu sửa: mock lời gọi provider để xác nhận model/provider/base URL thực dùng sau khi lưu với keep; không chỉ kiểm tra JSON cấu hình trả về.

## R02 — P1: Version mới chỉ bị chặn ở một số điểm đọc, vẫn ghi được

Vị trí: `backend/app/application.py:16–25`, `backend/app/world/schema.py:120–126`; các đường ghi vẫn chỉ dùng `require_world` hoặc kiểm tra thư mục tồn tại.

Tái hiện: world mẫu đặt `schema_version=7` trong khi app hỗ trợ 2, POST chapter/continue vẫn trả 200 và tăng tick. Startup chỉ log lỗi migration rồi phục vụ ứng dụng tiếp; GET world có chặn cũng không bảo vệ endpoint được gọi trực tiếp. Restore/branch cũng chưa kiểm tra/migrate version snapshot trước khi đưa vào world.

Cần chặn world không tương thích tại cửa vào chung của thao tác đọc/ghi có diễn giải schema; validate snapshot trước restore/branch. Không làm hỏng các chức năng xem lỗi hoặc xuất bản sao nguyên trạng để phục hồi.

Nghiệm thu sửa: continue/creator/restore/branch trên version không hỗ trợ không thay một byte state, không gọi AI; save cũ được migrate theo chính sách và có bằng chứng round-trip.

## R03 — P1: Checker vẫn failed sau lần sửa nhưng lượt được commit

Vị trí: `backend/app/chapter_generator.py:370` và đoạn commit bên dưới.

Tái hiện: mock checker trả `consistent=false, severity=major` ở cả hai lần. Endpoint trả 200, tick tăng thành 1 và lưu chương. Guard chỉ chặn unavailable nên failed rơi xuống nhánh commit.

Đây là lựa chọn đã được ghi trong báo cáo agent, nhưng chưa đáp ứng yêu cầu giữ bản không đạt ở trạng thái chưa áp dụng. Cần chặn failed sau bounded retry, giữ kết quả để người dùng xử lý, không tăng tick/áp hệ quả. `allow_unchecked_commit` chỉ dành cho unavailable theo chính sách đã thống nhất, không tự cho phép lỗi đã biết.

Nghiệm thu sửa: failed hai lần không commit; failed rồi passed commit đúng một lần; unavailable với/không opt-in được phân biệt. Sửa test đang coi commit failed là thành công và ghi rõ lý do.

## R04 — P1: JSON checker thiếu trường hoặc sai kiểu vẫn được xem là passed

Vị trí: `backend/app/story/consistency.py:95–103`.

Tái hiện trực tiếp: `{}` trả passed; `{"consistent":"false","severity":"unknown","issues":42}` cũng trả passed. Bộ parse chỉ yêu cầu object rồi mặc định các trường còn thiếu thành kết quả tốt; kiểm tra `consistent is False` không bắt chuỗi sai kiểu.

Cần schema xác thực kết quả checker: boolean thật, severity thuộc enum, issues đúng cấu trúc và quy tắc các trường nhất quán. Đầu ra thiếu/sai schema phải unavailable, không passed. Đừng chỉ thêm một test JSON không parse được.

Nghiệm thu sửa: empty object, field sai kiểu/enum, đầu ra mâu thuẫn đều không được passed; response hợp lệ vẫn hoạt động.

## R05 — P1: Request world cũ mở khóa gửi của world mới

Vị trí: `ui/src/features/play/usePlaySession.ts:231–234`; tương tự các finally ở start/regenerate/confirm.

Tái hiện bằng test hook với promise điều khiển: gửi A đang chờ → đổi sang B → gửi B đang chờ → trả kết quả A. Dù nhánh try bỏ qua response cũ bằng token, finally vẫn đặt `sendingRef=false` và `loading=false`. Test kỳ vọng B còn loading thất bại (nhận false). Người chơi có thể gửi thêm khi request B chưa xong.

Cần gắn cả cleanup với token/operation sở hữu request, reset trạng thái khi đổi world; không để request cũ thay đổi lock mới. `handleGeneratePrelude` cũng chưa có token nên cần đưa vào cùng audit request khi đổi world.

Nghiệm thu sửa: A kết thúc không thay loading/lock/data/error của B; B đang chờ thì lần nhấn tiếp không gửi thêm; lỗi và thành công đều được thử. Test hiện có chỉ kiểm tra response tải world cũ chưa phủ tình huống này.

## R06 — P2: Migration thiếu world_config tạo một config chỉ có version

Vị trí: `backend/app/world/schema.py:116–118, 136–155`.

Tái hiện: thư mục có character_state hợp lệ nhưng thiếu world_config; `ensure_current_schema` báo migrated thành công. Vòng tạo file thiếu có viết template, nhưng cuối hàm ghi đè bằng `config={}` cộng schema_version. Kết quả chỉ là `{"schema_version":2}`. Lần chạy sau thấy version hiện hành và trả sớm nên không sửa thiếu dữ liệu.

Cần phân biệt world cũ hợp lệ với world bị mất core file. Nếu chính sách là không tự phục hồi thì báo lỗi và giữ nguyên; nếu cho tạo mặc định thì dùng bản sao template đầy đủ và báo việc phục hồi, không chứng nhận một config rỗng là hợp lệ.

Nghiệm thu sửa: thiếu config không kết thúc bằng config chỉ có version; migration lỗi không ghi đè file gốc; thử lại vẫn giữ backup gốc phù hợp.

## Kiểm tra đã thực hiện

- `npm run check`: 33 backend test, legacy suite, 12 UI test, build và lint hoàn thành; còn hai cảnh báo effect và cảnh báo bundle lớn.
- `npm --prefix ui run test:e2e`: 1 Playwright test đạt với API mock.
- Tái hiện backend trên thư mục tạm, chặn HTTP provider; không đọc/sửa world cá nhân trong các kịch bản tái hiện.
- Test race bổ sung: 7 test hook có sẵn đạt, 1 test race mới thất bại. File test tạm đã xóa sau chạy; không sửa test người dùng.

Các script/log kiểm tra riêng được giữ ngoài repository trong thư mục `work/` của task. Đây là review các thay đổi và đường lỗi liên quan, không phải kiểm toán bảo mật toàn bộ hay đánh giá truyện với AI thật.

## Thứ tự sửa đề xuất

R01, R02, R03/R04 và R05 là các nhóm có thể giao độc lập theo module; R06 giao cùng R02. Sau khi sửa, thêm regression vào bộ test chính, chạy lại check/E2E và review diff trước khi commit. Chưa chuyển sang W01/W03 dựa trên giả định Đợt A đã hoàn tất.
