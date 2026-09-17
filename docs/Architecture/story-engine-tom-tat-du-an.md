# Story Engine — Tóm tắt dự án (tính đến hiện tại)

## 1. Mục đích dự án

Xây một hệ thống kể chuyện tương tác (interactive fiction engine) kiểu "chạy theo chap, tự do đi hướng nào cũng được miễn dắt về checkpoint" — gần với mô hình "string of pearls / funnel structure" trong interactive fiction. Đây là bản tổng quát hóa/mở rộng của một dự án AI GM (Kiến Trúc Sư Bóng Tối) đã làm trước đó.

Đặc điểm cốt lõi:
- **Sáng tạo từ đầu**: world được AI dựng mới hoàn toàn từ interview với user, không phải nhồi lore có sẵn.
- **Checkpoint làm xương sống**: giữa 2 checkpoint, user/agent tự do branch (sandbox), nhưng luôn có cơ chế "kéo" hoặc "chặn" để câu chuyện không đi chệch main canon.
- **Card-based scoped context**: mỗi chương chỉ load đúng tập nhân vật/lore được phép xuất hiện (tránh spoil, tránh tốn token, tránh AI tự bịa nhân vật không nên có mặt — ví dụ "ma vương nhảy vào chương 1").
- **Progression kiểu RPG ẩn**: sức mạnh nhân vật tăng qua 2 tầng — tầng nhỏ (exp/sub-stats) tăng tự do theo biểu hiện trong chap, tầng lớn (cảnh giới/realm) chỉ đổi tại checkpoint canon, tránh power creep.
- **2 mode**: Creator (nắm canon, duyệt/sửa mọi thứ) và User (chỉ chơi trong sandbox, bị chặn nếu phá canon).
- Deployment dạng **local web app** (giống SillyTavern): backend Python FastAPI, frontend HTML/JS đơn giản, chạy qua `localhost`. Sau này ổn định mới tính đóng gói Electron thành .exe (đã có kinh nghiệm từ dự án AI GM trước).

## 2. Kiến trúc đã thống nhất

### 2.1. Các "lớp" của hệ thống
1. **Lore/worldbook agent** — RAG-lite thuần Python đã làm (mục 5i, không cần vector store/embedding API thật ở quy mô này — xem chi tiết cách chọn lọc theo cosine similarity bag-of-words).
2. **Consistency checker** — chạy tách biệt (không chung context với narrator) để so nội dung mới generate với canon facts, tránh "đồng lõa" với lỗi vừa tạo ra.
3. **Character system** — mỗi nhân vật là 1 state object (affinity, vị trí, biết gì/chưa biết gì), update sau mỗi chap, không để LLM tự suy luận lại từ đầu.
4. **Checkpoint engine** — phần lớn là logic code thuần (không cần LLM): so state hiện tại với điều kiện checkpoint, "soft pull" (dẫn dắt tự nhiên qua narrative) khi cần, không hard-block trừ trường hợp đặc biệt.

### 2.2. Cơ chế chống lệch hướng / spoil sớm
Quyết định cuối: **scope boundary theo chap** thay vì whitelist "protected facts" phức tạp.
- Mỗi checkpoint có `boundary`: `locations` cho phép, `allowed_characters` cho phép, `time_window`.
- Trong scope → tự do hoàn toàn (max sandbox), không cần checker can thiệp.
- Ngoài scope → chặn bằng logic code (rẻ, không tốn API call riêng), rồi để narrator viết fallback message **kiểu trong truyện** (không phải lỗi hệ thống khô khan).
- Cơ chế chặn chắc nhất: **card chưa được load = nhân vật/lore "không tồn tại" trong nhận thức của agent** — đây là information-level blocking, chắc hơn cả boundary check vì chặn từ gốc.

### 2.3. Progression (RPG ẩn)
- `power_stat` tách 2 tầng: `realm` (cảnh giới lớn — hard bound, chỉ đổi tại checkpoint) và `exp` / `sub_stats` (soft — narrator agent được tự do cập nhật nhỏ theo biểu hiện trong chap).

### 2.4. Multi-agent orchestration
Đã quyết định dùng **orchestrator-worker** (không dùng shared blackboard), vì có thứ tự phụ thuộc rõ ràng: narrator generate xong → checker mới chạy được. Tránh multi-account/né rate-limit OpenRouter (vi phạm ToS, dễ bị khóa hàng loạt) — thay vào đó mix nhiều provider free-tier khác nhau (Gemini AI Studio, Groq, Featherless...).

Dự án tách biệt hoàn toàn khỏi OpenClaw (gateway đa kênh cũ) — loose coupling, sau này có thể gắn OpenClaw làm channel/interface (Discord, Telegram) cho story-engine, không ép logic story vào gateway.

## 3. Roadmap 8 bước

| Bước | Nội dung | Trạng thái |
|---|---|---|
| 0 | Setup project skeleton (backend/, frontend/, data/) | ✅ Xong — chạy uvicorn OK, frontend gọi API OK |
| 1 | State schema (4 khối JSON) | ✅ Xong — xem mục 4 |
| 2 | Backend core: route `chapter/continue` chạy full loop 1 agent | ✅ Xong — xem mục 5 |
| 3 | Frontend tối thiểu (hiển thị truyện, ô input) | ✅ Xong — xem mục 5b |
| 4 | Card loading theo chap (scoped context) | ✅ Xong — xem mục 5c |
| 5 | Consistency checker | ✅ Xong — validate schema `state_changes` (mục 5c) + agent riêng so sánh với canon facts, có quyền chặn (mục 5e) |
| 6 | Checkpoint engine + boundary fallback | ✅ Xong hoàn toàn — checkpoint engine (mục 5d) + boundary fallback thật bằng code, tự reject + gọi lại LLM (mục 5f) |
| 7 | Creator mode UI | ✅ Xong — xem mục 5g |
| 8 | Polish (multi-save, RAG-lite lore, unsaved-changes warning, UI đẹp...) | 🟨 Đang làm — multi-save (5h), RAG-lite lore + cảnh báo unsaved changes + tìm/lọc Saves (5i) đã xong cả backend lẫn frontend; chỉ còn UI đẹp hơn (cố tình để sau theo yêu cầu) |

## 4. Bước 1 — State schema (đã xong)

Cấu trúc thư mục mỗi world: `data/worlds/<world_name>/` chứa 4 file JSON (nay là 5, xem mục 5):
`world_config.json`, `card_registry.json`, `canon_timeline.json`, `character_state.json`.

### Field chi tiết đã chốt (định nghĩa trong `backend/main.py` qua 3 hàm `make_card()`, `make_checkpoint()`, `make_character()`):

**Card** (`card_registry.json`):
```json
{
  "id": "", "type": "char | lore", "name": "", "content": "",
  "unlock_checkpoint_id": "", "status": "locked | unlocked"
}
```
`status` và `unlock_checkpoint_id` tách biệt: 1 cái là trạng thái hiện tại, 1 cái là điều kiện mở.

**Checkpoint** (`canon_timeline.json`):
```json
{
  "checkpoint_id": "", "description": "",
  "required_conditions": [], "cards_unlocked": [],
  "boundary": {"locations": [], "allowed_characters": [], "time_window": ""}
}
```

**Character** (`character_state.json`):
```json
{
  "name": "", "location": "", "affinity": {},
  "power_stat": {"realm": "", "exp": 0, "sub_stats": {}},
  "knowledge_flags": [], "alive": true
}
```

### Endpoint đã có trong `main.py` (đã test end-to-end bằng FastAPI TestClient, chạy sạch):
- `GET /health`
- `GET /worlds` — list world
- `POST /worlds/{world_name}` — tạo world rỗng theo `TEMPLATES`
- `GET /worlds/{world_name}` — đọc full state 1 world
- `DELETE /worlds/{world_name}`
- `POST /worlds/{world_name}/seed-demo` — seed data mẫu thật (world xianxia test: Gu Changge / Xue Li, 5 checkpoint, 6 card, 2 character) để test pipeline. **Lưu ý: route này ghi đè nếu world đã tồn tại, không check trùng như `create_world`.**

Đã test: world tạo thường (`create_world`) vẫn rỗng đúng như cũ, không bị ảnh hưởng bởi các thay đổi thêm vào.

## 5. Bước 2 — Đã xong, đã test end-to-end bằng FastAPI TestClient

Đã quyết định: **khung hiện tại là scaffolding tay, chưa gắn API key thật**. Khi gắn API key, sẽ có 2 loại agent tách biệt:

| Agent | Chạy khi nào | Input | Output |
|---|---|---|---|
| **World-builder agent** | 1 lần lúc tạo world mới từ đầu (đã confirm: chỉ tạo mới, không patch world cũ) | Câu trả lời interview user (thể loại, power system, tone, nhân vật chính, seed conflict) | JSON full 4 khối, khớp đúng schema mục 4 |
| **Narrator agent** | Mỗi chap | State hiện tại + active cards (đã lọc theo checkpoint) + lựa chọn user | `chapter_text` + `state_changes` đề xuất |

System prompt đầy đủ cho cả 2 agent nằm trong `backend/prompts.py` (2 hằng số `WORLD_BUILDER_SYSTEM_PROMPT` và `NARRATOR_SYSTEM_PROMPT`). Cả 2 đều bắt buộc output JSON thuần, có rule chống spoil sớm, rule chặn tự ý đổi `realm`, rule không tự bịa nhân vật/địa điểm ngoài phạm vi cho phép.

**Đã hoàn thiện trong `main.py`:**
- `find_checkpoint(checkpoints, checkpoint_id)` — tìm checkpoint hiện tại trong `canon_timeline`.
- `get_active_cards(cards)` — lọc card có `status == "unlocked"` (information-level blocking, đúng thiết kế mục 2.2).
- `call_llm(system_prompt, user_prompt, user_input_for_mock)` — gọi OpenRouter (`OPENROUTER_API_KEY` từ biến môi trường, model mặc định `deepseek/deepseek-chat`, đổi qua `OPENROUTER_MODEL`); nếu chưa có key hoặc call lỗi → tự fallback sang `mock_narrator_response()` để không chặn việc test pipeline.
- `parse_llm_json(raw_text)` — strip code fence ```json nếu LLM lỡ bọc, rồi parse.
- `apply_state_changes(characters, state_changes)` — merge delta (`affinity_delta`, `sub_stats_delta`, `exp_delta`, `knowledge_flags_add`, `location`, `alive`) vào `character_state` thật. **Không đụng vào `power_stat.realm`** — đúng rule "chỉ checkpoint engine mới đổi cảnh giới".
- Endpoint `POST /worlds/{world_name}/chapter/continue` (body: `{"user_input": ""}`):
  1. Đọc `current_checkpoint_id` từ `world_config`, tìm checkpoint tương ứng; nếu không khớp → `400` kèm message rõ nguyên nhân (world cũ thiếu field) thay vì crash.
  2. Lọc `active_cards` (unlocked) + `character_state` chỉ của nhân vật nằm trong `boundary.allowed_characters` của checkpoint hiện tại.
  3. Đóng gói context (world_config rút gọn, checkpoint hiện tại, active_cards, character_state đã lọc, 3 chap gần nhất, user_input) → gọi `call_llm` với `NARRATOR_SYSTEM_PROMPT`.
  4. Parse response, merge `state_changes` vào `character_state.json`, ghi thêm 1 record vào `chapters.json` (`chapter_index`, `checkpoint_id`, `user_input`, `chapter_text`, `notes`).
  5. Trả về response gồm `chapter`, `state_changes_applied`, và `used_mock_llm` (để frontend/dev biết đang chạy mock hay LLM thật).
- `seed_demo()` đã sync: set `current_checkpoint_id = "cp_0"` trong `world_config`, và ghi `chapters.json` rỗng (`{"chapters": []}`).

**Đã test (TestClient, không phải chạy thật trên máy user):**
- `seed-demo` → `chapter/continue` chạy full loop bằng mock LLM (chưa set `OPENROUTER_API_KEY`), trả JSON đúng schema.
- Monkeypatch `call_llm` giả lập response thật của narrator → xác nhận `apply_state_changes` cộng dồn đúng `exp_delta`, `affinity_delta`, `sub_stats_delta`, thêm `knowledge_flags`, đổi `location`; nhân vật không có trong `character_state` (do không thuộc scope) bị bỏ qua an toàn, không crash.
- World tạo thường (`create_world`, không seed) vẫn có `current_checkpoint_id: ""` như cũ, gọi `chapter/continue` trên world này trả `400` rõ ràng thay vì lỗi 500 — không phá regression bước 0/1.

**Việc CHƯA làm (để bước 2 hoàn thiện tuyệt đối, có thể làm sau hoặc gộp vào bước 5/6):**
- Chưa validate `state_changes` từ LLM theo schema chặt (Pydantic) trước khi merge — hiện chỉ dùng `.get()` nên field sai kiểu (vd. `exp_delta` là string) sẽ crash khi cộng. Có thể để consistency checker (bước 5) xử lý, hoặc thêm validate nhẹ ở đây.
- Chưa có logic tự động chuyển `current_checkpoint_id` khi `required_conditions` thỏa mãn — đó là việc của checkpoint engine thật (bước 6), hiện `chapter/continue` chỉ đọc checkpoint hiện tại, không tự nhảy checkpoint.

## 5b. Bước 3 — Frontend tối thiểu (đã xong)

File: `frontend/index.html` — 1 file HTML/CSS/JS thuần (không framework, đúng quyết định mục 1: "giống SillyTavern"), không cần build step, mở trực tiếp bằng trình duyệt hoặc serve tĩnh.

**Chức năng đã có:**
- Ô nhập "Backend URL" (mặc định `http://localhost:8000`) + đèn trạng thái gọi `/health`.
- Sidebar: tạo world rỗng (`POST /worlds/{name}`), liệt kê world (`GET /worlds`), xóa world (`DELETE /worlds/{name}`, có confirm), nút seed demo (`POST /worlds/{name}/seed-demo`).
- Chọn 1 world → gọi `GET /worlds/{name}` để lấy `world_config.display_name`, `current_checkpoint_id`, và load lại toàn bộ `chapters.chapters` đã có (refresh trang không mất lịch sử, vì đọc thẳng từ file JSON qua API).
- Khung chat kiểu feed: mỗi chapter hiển thị `chapter_index`, `checkpoint_id`, `user_input` (nếu có), `chapter_text`, `notes` (nếu có). Có escape HTML để tránh injection từ nội dung LLM trả về.
- Ô input + nút "Tiếp tục" (Enter = gửi, Shift+Enter = xuống dòng) gọi `POST /worlds/{name}/chapter/continue`, append chapter mới vào feed ngay khi có response, tự cuộn xuống cuối.
- Badge góc phải header đổi màu theo `used_mock_llm`: vàng "MOCK LLM" khi chưa gắn `OPENROUTER_API_KEY`, xanh "LLM thật" khi đã gắn — đúng yêu cầu mục 7 cũ (biết đang test mock hay thật mà không cần xem log backend).
- Toast báo lỗi khi API lỗi (network, 404, 400, 502 JSON không hợp lệ...) thay vì màn hình trắng.

**Đã test:** chạy `uvicorn main:app` thật (không phải TestClient) trong môi trường sandbox, gọi đủ chuỗi `/health` → `seed-demo` → `/worlds` → `chapter/continue` → `GET /worlds/{name}` bằng curl để xác nhận response JSON khớp đúng field mà frontend JS đang đọc (`chapter.chapter_text`, `chapter.notes`, `used_mock_llm`, `world_config.display_name`, `world_config.current_checkpoint_id`, `chapters.chapters`). Chưa test bằng trình duyệt thật trên máy user (không có môi trường browser ở đây) — cần user tự mở file và xác nhận UI/UX, đặc biệt CORS (`allow_private_network` middleware trong `main.py` đã xử lý case Chrome mới chặn `file://` gọi vào `localhost`).

**Chưa làm / để bước sau:** frontend chưa hiển thị `active_cards` hay `character_state` (không cần thiết cho bước 3, sẽ hữu ích hơn ở bước 7 — Creator mode UI, khi cần xem/sửa canon trực tiếp).

## 5c. Bước 4 — Card loading theo chap, hoàn thiện (vừa xong)

Vấn đề tồn đọng cũ: `get_active_cards()` chỉ lọc theo `status == "unlocked"`, không quan tâm checkpoint hiện tại. Hệ quả: một nhân vật đã từng unlock (vd ở cp_0) nhưng theo canon KHÔNG có mặt ở checkpoint hiện tại (không nằm trong `boundary.allowed_characters`) vẫn lọt vào context của narrator — dễ khiến agent tưởng nhân vật đó đang có mặt.

**Đã sửa:** `get_active_cards(cards, checkpoint)` nay nhận thêm `checkpoint` hiện tại:
- Card `type == "char"`: phải vừa `status == "unlocked"` VỪA có `id` nằm trong `checkpoint.boundary.allowed_characters` mới lọt vào `active_cards`.
- Card `type == "lore"`: vẫn chỉ lọc theo `status` — coi lore là kiến thức nền "sticky", một khi đã unlock thì không biến mất khỏi context (khác bản chất với sự hiện diện vật lý của nhân vật). Đây là quyết định thiết kế có chủ đích, không phải sót — nếu sau này cần lore cũng bị giới hạn theo location, sẽ cần thêm field `relevant_locations` vào card lore và lọc thêm, nhưng chưa cần thiết ở quy mô hiện tại.

Đã test bằng cách monkeypatch `call_llm` để bắt đúng `user_prompt` gửi cho narrator ở checkpoint `cp_0`, xác nhận card `char_su_phu` (locked, thuộc `cp_1`) không xuất hiện trong context dù đã tồn tại trong `card_registry`.

## 5d. Bước 6 — Checkpoint engine thật (vừa xong)

### Quyết định format `required_conditions` (thay thế string tự nhiên cũ)

```json
{"field": "char_id.duong.dan.trong.character_state", "op": "==|!=|in|contains|>=|<=|>|<", "value": "..."}
```
- `contains`: dùng khi field là list (điển hình `knowledge_flags`) — kiểm tra `value` có nằm trong list không.
- `in`: ngược lại — `value` là list, kiểm tra field hiện tại có nằm trong đó không (dùng cho `power_stat.realm in [...]`).
- Checkpoint engine luôn chỉ xét checkpoint **kế tiếp** theo đúng thứ tự trong mảng `checkpoints` so với `current_checkpoint_id` — nên **không cần** điều kiện kiểu `"checkpoint cp_X completed"` nữa, thứ tự đã ngầm định điều đó.
- Checkpoint có `required_conditions` **rỗng** ([]) → **không tự động chuyển** (chỉ chuyển tay/Creator mode ở bước 7). Tránh trường hợp world-builder agent lỡ để trống rồi truyện tự nhảy checkpoint ngay lập tức. `cp_0` luôn rỗng vì nó là điểm bắt đầu, không phải đích cần "chuyển vào".

### Vấn đề phát sinh và cách giải quyết: ai đổi `power_stat.realm`?

Rule cũ đã chốt "cảnh giới lớn chỉ đổi tại checkpoint", nhưng trước đây **không có nơi nào trong code thực sự đổi `realm`** — `apply_state_changes` (narrator) bị cấm đụng vào field này, nhưng cũng chưa có cơ chế nào khác thay thế. Đã bổ sung field mới trong checkpoint: `realm_updates: {"char_id": "realm_mới"}`, áp dụng đúng lúc checkpoint engine chuyển vào checkpoint đó. Đây là **nơi duy nhất** `power_stat.realm` được phép đổi trong toàn hệ thống.

Vì vậy điều kiện trigger để **chuyển vào** một checkpoint không được phép dựa vào `power_stat.realm` của chính checkpoint đó cấp (vì lúc kiểm tra điều kiện, realm chưa được cấp) — phải dựa vào chỉ số soft (`exp`, `sub_stats`, `knowledge_flags`). `realm` chỉ nên xuất hiện trong điều kiện của một checkpoint **sau đó**, để kiểm tra realm đã được một checkpoint **trước đó** cấp qua `realm_updates` chưa (ví dụ `cp_4` yêu cầu realm đã là Kim Đan/Nguyên Anh — cấp bởi `realm_updates` của `cp_3`). Đã sửa lại data mẫu (`seed_demo`) theo đúng logic này, và đã cập nhật rule #10, #11 trong `WORLD_BUILDER_SYSTEM_PROMPT` (`prompts.py`) để world-builder agent sinh world mới cũng tuân đúng logic, tránh tạo ra điều kiện "tự tham chiếu" không bao giờ thỏa được.

### Hàm mới trong `main.py`
- `get_nested_field(character_state, field_path)` — đọc field lồng nhau kiểu `"char_xueli.power_stat.exp"`.
- `eval_condition(condition, character_state)` — eval 1 điều kiện, không crash nếu kiểu dữ liệu không so sánh được (vd `None >= 3`), coi như chưa thỏa thay vì raise lỗi.
- `checkpoint_conditions_met(checkpoint, character_state)` — AND tất cả điều kiện; rỗng → `False` (xem quyết định ở trên).
- `advance_checkpoint_if_ready(canon_timeline, world_config, character_state, card_registry)` — chỉ xét checkpoint kế tiếp, mỗi lần gọi tối đa tiến **1 checkpoint** (không nhảy nhiều bước liên tiếp trong cùng 1 chap, tránh spoil dồn dập). Khi tiến: ghi `current_checkpoint_id` mới, thêm checkpoint cũ vào `world_config.completed_checkpoints` (field mới, thêm vào `TEMPLATES` và `seed_demo`), set `status = "unlocked"` cho các card trong `cards_unlocked` của checkpoint mới, áp `realm_updates` vào `character_state`. Trả về dict mô tả thay đổi hoặc `None`.

Endpoint `chapter/continue` gọi hàm này ngay sau khi merge `state_changes` của narrator, trả thêm field `checkpoint_advanced` trong response (chứa `from_checkpoint_id`, `to_checkpoint_id`, `to_checkpoint_description`, `cards_unlocked`, `realm_changes`, hoặc `null` nếu chưa đủ điều kiện). `world_config.json` và `card_registry.json` chỉ được ghi lại khi thực sự có chuyển checkpoint (tránh ghi file thừa mỗi chap).

**Frontend (`index.html`) đã cập nhật theo:** khi `checkpoint_advanced` khác `null`, hiện toast (7s, cho phép xuống dòng) báo checkpoint mới + card vừa mở khóa, đồng thời cập nhật dòng "checkpoint hiện tại" ở header world mà không cần reload trang.

### Validate `state_changes` bằng Pydantic (nốt phần còn lại của bước 5 cũ)
Thêm 2 model `CharacterStateChange` / `StateChangesModel` trong `main.py`. Trước khi merge, `chapter_continue` validate `state_changes` bằng model này; nếu LLM trả sai kiểu (vd `exp_delta` là string) → trả `502` kèm message rõ nguyên nhân, **không merge một phần** và **không ghi file** — tránh state bị hỏng nửa chừng.

### File test mới: `backend/test_engine.py`
Test end-to-end bằng `fastapi.testclient.TestClient` (không phải test chính thức CI, chỉ để tự kiểm tra khi sửa code sau này). Chạy bằng `python3 test_engine.py` từ thư mục `backend/` (cần `pip install fastapi pydantic requests httpx --break-system-packages`). Đã test và PASS toàn bộ:
- Card filtering đúng ở `cp_0` (card locked không lọt context).
- Đẩy `exp` Xue Li đủ ngưỡng → tự động chuyển `cp_0 → cp_1`, unlock đúng card.
- Đẩy tiếp `exp` → chuyển `cp_1 → cp_2`, `realm` được set thành "Trúc Cơ" qua `realm_updates` (không phải do narrator tự đổi).
- `state_changes` sai kiểu dữ liệu → trả `502`, state không bị merge một phần.
- Regression: world tạo thường (chưa seed) vẫn trả `400` rõ ràng như cũ, không crash.

Đã test thêm 1 lần bằng `uvicorn` thật + `curl` (giống quy trình bước 3) để xác nhận response JSON qua HTTP thật khớp đúng, không chỉ đúng qua `TestClient`.

## 5e. Bước 5 — Consistency checker thật (vừa xong)

**Quyết định đã chốt** (khác với để mở ở bản tóm tắt trước): checker **có quyền chặn** — khi phát hiện mâu thuẫn nghiêm trọng (`severity: "major"`), tự động yêu cầu narrator viết lại **1 lần**, sau đó chấp nhận kết quả (không check lại vòng 2, tránh vòng lặp vô hạn/tốn chi phí API).

- Prompt mới `CONSISTENCY_CHECKER_SYSTEM_PROMPT` (`prompts.py`): nhận `fixed_rules`, `current_checkpoint_description`, `active_cards`, `character_state_before_chapter`, `chapter_text` + `proposed_state_changes` vừa được narrator sinh ra. Trả về `{"consistent": bool, "severity": "none|minor|major", "issues": [...], "explanation": ""}`. Rule quan trọng: chỉ chấm "major" khi mâu thuẫn **rõ ràng và trực tiếp** (vd nhân vật `alive: false` nhưng vẫn hành động, hoặc dùng knowledge_flag chưa từng có) — cấm suy đoán/chê văn phong để tránh chặn nhầm chương hợp lệ.
- Chạy **tách biệt hoàn toàn** với narrator (gọi `call_llm` riêng, context riêng, đúng quyết định kiến trúc mục 2.1 #2 — "tránh đồng lõa với lỗi vừa tạo ra").
- **Fail-open**: nếu checker trả JSON hỏng/thiếu field → mặc định coi là `severity: "none"`, không chặn pipeline chính vì đây là lớp an toàn phụ, lỗi của nó không được làm hỏng trải nghiệm chính.
- Khi `severity == "major"`: gọi lại narrator 1 lần kèm `correction_note` mô tả rõ từng mâu thuẫn (`build_consistency_correction_note`), rồi dùng bản viết lại làm bản cuối. Bản viết lại này cũng được chạy lại `check_boundary_violations` (không tốn thêm API call) để chắc chắn narrator không vô tình vi phạm boundary khi sửa.
- Response `chapter/continue` và `chapter_record` (lưu trong `chapters.json`) đều có thêm field `consistency_check: {severity, issues, explanation, triggered_rewrite}` — để Creator mode (bước 7) xem lại sau nếu cần.
- `call_llm` được refactor thêm tham số `mock_response` tùy chọn, vì checker cần mock riêng (`mock_consistency_checker_response`, trả về `severity: "none"` mặc định) khác hẳn schema mock của narrator.

## 5f. Bước 6 — Boundary fallback thật (vừa xong)

**Quyết định đã chốt**: không chỉ dựa vào prompt — thêm hẳn logic code detect qua `state_changes.characters.*.location`, tự động reject + gọi lại LLM 1 lần, và có **lớp phòng thủ cuối (hard clamp)** nếu narrator vẫn vi phạm sau khi được nhắc.

- `check_boundary_violations(state_changes, checkpoint)`: so từng `location` được đề xuất trong `state_changes` với `checkpoint.boundary.locations` hiện tại — đây là field DUY NHẤT trong `state_changes` có thể đưa nhân vật ra khỏi boundary vật lý, nên chỉ cần kiểm tra field này (không cần kiểm tra nhân vật lạ, vì schema Pydantic + `apply_state_changes` đã tự bỏ qua nhân vật không tồn tại trong `character_state`).
- Nếu có vi phạm: gọi lại narrator 1 lần kèm `correction_note` mô tả chính xác nhân vật/địa điểm vi phạm + danh sách `allowed_locations` hiện tại (`build_boundary_correction_note`), yêu cầu viết lại bằng một tình huống hợp lý trong truyện.
- Nếu **sau retry vẫn còn vi phạm** → `apply_boundary_hard_clamp`: tự động xóa field `location` vi phạm khỏi `state_changes` trước khi merge (giữ nguyên vị trí cũ của nhân vật). Đây là lớp phòng thủ độc lập với chất lượng LLM — đảm bảo `character_state` **không bao giờ** bị ghi sai boundary dù mô hình "cãi lời" cả 2 lần. (Giới hạn đã biết: `chapter_text` hiển thị cho user vẫn có thể mô tả nhân vật ở nơi bị chặn nếu cả 2 lần đều sai — state được bảo vệ tuyệt đối, nhưng văn bản thì không; cân nhắc cải thiện thêm ở bước sau nếu cần.)
- Response và `chapter_record` có thêm field `boundary_correction`: `null` nếu không có vi phạm, hoặc `{detected, auto_retry_fixed_it, violations, note}` nếu có (kể cả khi đã tự sửa thành công).
- Prompt narrator (`NARRATOR_SYSTEM_PROMPT`) được thêm rule #7: giải thích ý nghĩa field `correction_note` khi xuất hiện trong payload, yêu cầu viết lại toàn bộ `chapter_text` + `state_changes` cho đúng.
- Thứ tự xử lý trong `chapter/continue`: gọi narrator → validate schema → **boundary check + retry nếu cần** → **consistency checker + retry nếu major** (kèm re-check boundary rẻ trên bản viết lại do checker yêu cầu) → merge state → checkpoint engine. Tổng tối đa 3 lần gọi narrator/chapter (gốc + boundary-retry + consistency-retry), 1 lần gọi checker — đủ chặt để không vượt quá chi phí API mà vẫn có 2 lớp bảo vệ độc lập.
- `frontend/index.html` đã cập nhật hiển thị: mỗi chapter-card giờ hiện thêm dòng cảnh báo nhỏ (viền vàng nếu đang có vấn đề/đã sửa, viền xanh nếu tự sửa thành công) khi có `boundary_correction` hoặc `consistency_check.severity != "none"`.

**Đã test (`test_engine.py`, PASS toàn bộ 9 nhóm test):**
- Boundary auto-fix: vi phạm lần đầu, narrator tự sửa đúng ở lần retry → `auto_retry_fixed_it: true`, state được cập nhật đúng vị trí mới.
- Boundary hard clamp: vi phạm cả 2 lần → `auto_retry_fixed_it: false`, `character_state.location` giữ nguyên như trước chapter, không crash.
- Consistency checker major → `triggered_rewrite: true`, có gọi lại narrator.
- Regression: card filtering (bước 4), checkpoint engine + realm_updates (bước 6 cũ), validate Pydantic sai kiểu → 502 (bước 5 cũ), world rỗng → 400 — tất cả vẫn đúng như trước, không bị phá bởi thay đổi mới.
- Đã test thêm 1 lần bằng `uvicorn` thật + `curl` (seed-demo → chapter/continue) để xác nhận response JSON qua HTTP thật có đủ field mới (`boundary_correction`, `consistency_check`) đúng như narrator/checker mock trả về.

> **CẬP NHẬT sau này (xem mục 7 #4)**: phần "hard clamp" mô tả ở dòng 215/223 phía trên **đã bị thay thế** bằng "hard reject" (`raise_boundary_hard_reject`, HTTP 409, không ghi gì cả) để giải quyết đúng giới hạn đã ghi nhận ở đây (mismatch `chapter_text`/state khi vi phạm cả 2 lần). Giữ nguyên đoạn trên làm lịch sử quyết định gốc, chi tiết bản sửa nằm ở mục 7 #4.

## 5g. Bước 7 — Creator mode UI (vừa xong)

**Quyết định kiến trúc chính**: dùng pattern "replace toàn bộ file" cho mọi thao tác sửa (giống `write_world_file` đã dùng ở mọi nơi khác trong code), thay vì PATCH từng field lẻ tẻ. Frontend load toàn bộ list/dict hiện có, cho sửa trong bảng, rồi gửi lại **toàn bộ** một lần qua PUT. Đơn giản hơn nhiều so với thiết kế PATCH chi tiết, và khớp với cách `card_registry.json`/`canon_timeline.json`/`character_state.json` vốn đã được ghi đè toàn bộ mỗi lần.

### Backend (`main.py`)
5 endpoint mới:
- `PUT /worlds/{world}/world_config` — chỉ sửa field "tĩnh" (`display_name`, `genre`, `power_system`, `tone`, `fixed_rules`). **Cố tình KHÔNG cho sửa** `current_checkpoint_id`/`completed_checkpoints` ở đây — 2 field này bắt buộc đi qua force-advance để đảm bảo card unlock + realm_updates luôn được áp dụng đồng bộ, không bao giờ bị lệch khỏi checkpoint engine thật.
- `PUT /worlds/{world}/card_registry`, `PUT /worlds/{world}/canon_timeline`, `PUT /worlds/{world}/character_state` — nhận toàn bộ list/dict mới, validate bằng Pydantic model (`CardModel`, `CheckpointModel`, `CharacterModel` — mirror đúng field của `make_card()`/`make_checkpoint()`/`make_character()`), chặn `id`/`checkpoint_id` trùng nhau bằng `400` **trước khi ghi file** (không ghi đè một phần).
- `POST /worlds/{world}/checkpoint/force-advance` — ép chuyển checkpoint bằng tay. Nếu đích nằm SAU checkpoint hiện tại (theo thứ tự trong `canon_timeline`), tự **cascade qua từng checkpoint bị nhảy cóc**: đánh dấu completed, unlock card, và áp dụng `realm_updates` của TẤT CẢ checkpoint trên đường đi (không chỉ checkpoint đích) — tránh bỏ sót nếu Creator nhảy nhiều checkpoint một lúc. Đi lùi (undo) chỉ đổi `current_checkpoint_id`, không tự khóa lại card/hạ realm (Creator tự sửa `card_registry`/`character_state` riêng nếu cần undo thật).

`required_conditions` trong `CheckpointModel` giữ dạng `List[Dict]` thay vì Pydantic model chặt, vì field `value` bên trong đổi kiểu tùy theo `op` (str/int/list) — ép 1 kiểu cứng sẽ làm sai lệch dữ liệu khi Creator lưu.

### Frontend (`index.html`)
Thêm 2 tab lớn ở world view: **📖 Chơi truyện** (giao diện cũ, không đổi) và **🛠️ Creator Mode**, với 5 sub-tab: World Config, Checkpoints, Cards, Characters, Lịch sử can thiệp.

- **World Config**: form sửa field tĩnh + ô "Ép chuyển checkpoint" (dropdown chọn checkpoint đích trong `canon_timeline` + nút xác nhận).
- **Cards / Checkpoints / Characters**: mỗi entity hiện thành 1 "item card" với input trực tiếp cho field đơn giản (text/select/number/checkbox); field lồng nhau phức tạp (`required_conditions`, `realm_updates`, `affinity`, `power_stat.sub_stats`) sửa dạng **JSON thô** trong textarea — hợp lý vì đây là công cụ kỹ thuật, Creator (chính là user) vốn đã quen thao tác trực tiếp với JSON schema của dự án này. Field dạng list ngắn (`cards_unlocked`, `boundary.locations`, `knowledge_flags`...) dùng input text phân tách bằng dấu phẩy cho gọn hơn JSON.
- **Xóa** = gọi API ngay lập tức (có `confirm()`, giống nút xóa world ở sidebar đã có sẵn). **Sửa field** = gom tất cả dòng đang hiển thị (kể cả dòng mới thêm) lại thành 1 mảng/dict, bấm "💾 Lưu tất cả" mới gửi lên — tránh gọi API liên tục mỗi lần gõ phím.
- **Lịch sử can thiệp**: lọc các chapter có `boundary_correction != null` hoặc `consistency_check.severity != "none"`, hiện dạng danh sách rút gọn (không phải xem lại từng chapter card đầy đủ) để dễ đánh giá LLM free-tier có hay vi phạm/mâu thuẫn hay không theo thời gian.
- Toàn bộ giá trị input được gán qua thuộc tính DOM `.value`/`.textContent` (không nhét trực tiếp vào chuỗi HTML) để tránh lỗi khi nội dung card/checkpoint chứa dấu `"` hoặc `<...>` — quan trọng vì `content` của card hay `description` của checkpoint là text tự do do Creator/AI world-builder viết ra, không kiểm soát được ký tự.
- `currentWorldData` (toàn bộ world) được giữ ở biến JS toàn cục, refresh sau mỗi lần sửa qua Creator mode hoặc sau khi gửi chapter mới (không cần reload trang), để tab đang mở luôn khớp dữ liệu mới nhất.

### Đã kiểm tra (trong giới hạn sandbox, xem mục 7 để biết phần còn thiếu)
Do sandbox hiện tại không có mạng nên không cài được `fastapi` để chạy `test_engine.py` thật — đã thay bằng 2 cách kiểm tra gián tiếp:
- Backend: rà soát logic bằng tay + `ast.parse()` xác nhận cú pháp hợp lệ; đã viết thêm **5 nhóm test mới (10-14)** vào `test_engine.py` (PUT world_config không đụng current_checkpoint_id, PUT card_registry chặn id trùng và không ghi đè một phần, PUT canon_timeline, PUT character_state, force-advance cascade qua nhiều checkpoint + áp đúng realm_updates dọc đường + 404 khi target không tồn tại) — **cần chạy lại `python3 test_engine.py` trên máy thật để xác nhận PASS**, vì tôi chưa tự chạy được.
- Frontend: dựng 1 DOM shim tối giản bằng Node (`vm` module) để smoke-test toàn bộ hàm render Creator mode ngoài trình duyệt thật — xác nhận cả 5 tab render không lỗi, nút "+ Thêm" hoạt động, và dữ liệu (kể cả tiếng Việt có dấu, dấu ngoặc kép, thẻ giả `<tag>`) round-trip đúng qua các hàm `_readCard`/`_readCheckpoint`/`_readCharacter`. Đây **không thay thế được việc mở thật trên Chrome** — vẫn cần Rinn tự mở `frontend/index.html` để xác nhận CSS/layout hiển thị đúng và không có lỗi JS nào lọt qua shim đơn giản này.

## 5h. Bước 8 (phần multi-save) — Backend đã có sẵn nhưng chưa ghi vào tài liệu, giờ đã nối UI

**Phát hiện khi rà soát lại `main.py`/`test_engine.py`**: phần backend cho multi-save (snapshot/restore/branch) **đã được code và test PASS từ trước** (block `# BUOC 8: MULTI-SAVE` trong `main.py`, ~180 dòng, cùng 5 nhóm test cuối trong `test_engine.py`), nhưng bản tóm tắt này chưa từng ghi nhận — có khoảng lệch giữa code thật và tài liệu. Mục này bổ sung lại cho khớp, đồng thời ghi nhận phần frontend vừa làm thêm để nối UI vào.

### Kiến trúc (đã có sẵn trong code, ghi lại ở đây theo đúng comment gốc trong `main.py`)
- **save** = bản copy nguyên 5 file JSON của world tại 1 thời điểm, lưu ở `data/worlds/<world>/saves/<save_id>/` — dùng lại đúng pattern "copy nguyên file" đã dùng khi tạo world từ `TEMPLATES`, không cần schema riêng.
- Metadata các save tách riêng ra `saves_index.json` ở gốc world (list JSON, ghi đè toàn bộ mỗi lần đổi — cùng kiểu với `card_registry.json`/`canon_timeline.json`) để list nhanh, không phải đọc lại từng snapshot.
- **Restore** là thao tác phá hủy (ghi đè state hiện tại) nên trước khi restore, hệ thống **tự động tạo 1 "safety save"** của state hiện tại (`source: "safety_before_restore"`) — đúng nguyên tắc "thao tác nguy hiểm phải có lưới an toàn riêng, không chỉ dựa vào `confirm()` ở frontend" đã dùng xuyên suốt dự án (giống hard-reject boundary ở mục 7 #4).
- **Branch** tạo world MỚI hoàn toàn từ 1 save có sẵn (không phải từ bất kỳ chapter nào) — đúng ý "branch build trên snapshot". World mới không kế thừa `saves_index` của world gốc (list save riêng, sạch), nhưng có field `world_config.branched_from` để truy vết nguồn gốc (world + save_id + thời điểm).
- Cố tình **không auto-snapshot** mỗi lần checkpoint đổi — tránh phình dung lượng ngầm và đổi hành vi của `chapter/continue` (hot path) khi chưa được yêu cầu rõ.

### Endpoint (`main.py`, đã có sẵn)
- `POST /worlds/{world}/saves` — tạo save point (body: `{"label": ""}`, label tùy chọn).
- `GET /worlds/{world}/saves` — list save, mới nhất trước (cũng được nhúng sẵn vào `GET /worlds/{world}` dưới field `saves`, nên frontend không cần gọi endpoint riêng).
- `POST /worlds/{world}/saves/{save_id}/restore` — khôi phục, tự tạo safety-save trước, trả về `restored_save_id` + `safety_save_id`.
- `DELETE /worlds/{world}/saves/{save_id}` — xóa save (xóa cả thư mục snapshot trên disk).
- `POST /worlds/{world}/saves/{save_id}/branch` — tạo world mới từ save (body: `{"new_world_name": ""}`).

**Test (`test_engine.py`, PASS toàn bộ, đã tự chạy lại bằng `python3 test_engine.py` trong sandbox lần này — có mạng, không cần chờ Rinn chạy):** tạo save → đúng metadata; restore → tự tạo safety-save, không mất save cũ, phục hồi đúng field đã sửa sai trước đó; branch → world mới đúng state nguồn, world gốc không đổi, chặn trùng tên (400) và save_id không tồn tại (404); xóa save → mất khỏi index lẫn khỏi disk.

### Frontend (`index.html`) — phần MỚI làm hôm nay
Thêm sub-tab thứ 6 trong Creator Mode: **💾 Saves & Nhánh** (`renderSavesTab`), cạnh 5 sub-tab cũ (World Config, Checkpoints, Cards, Characters, Lịch sử can thiệp):
- Khu vực tạo save mới: ô nhập nhãn tùy chọn + nút "💾 Tạo save point".
- Danh sách save (mới nhất trước, lấy thẳng từ `currentWorldData.saves` đã có sẵn trong response `GET /worlds/{world}`, không gọi thêm API): mỗi save hiện thành 1 item-card với tag tên (label hoặc save_id nếu không đặt tên), tag riêng màu vàng (`item-tag.safety`, dùng lại biến CSS `--warn` có sẵn) cho safety-save để phân biệt trực quan với save tay, dòng chi tiết (thời gian tạo, checkpoint lúc lưu, số chapter).
- 3 nút hành động mỗi save: **↺ Restore** (confirm có nhắc rõ sẽ tự tạo safety-save trước khi ghi đè), **⑂ Branch** (prompt nhập tên world mới, gọi xong tự `refreshWorlds()` để world mới hiện ngay ở sidebar), **🗑 Xóa** (confirm, không hoàn tác được).
- Toàn bộ nhãn/label dùng qua `mkEl`/`.textContent` như các tab khác trong Creator Mode (không nhét thẳng vào chuỗi HTML) — an toàn khi label chứa dấu `"` hay `<...>` do Creator tự đặt tự do.
- Dùng lại đúng `currentWorldData` toàn cục có sẵn, refresh qua `refreshCurrentWorld()`/`refreshWorlds()` sau mỗi hành động — không cần reload trang, khớp pattern đã dùng ở các tab khác.

### Đã kiểm tra
- Backend: chạy `python3 test_engine.py` thật trong sandbox (có mạng lần này) — **PASS toàn bộ**, bao gồm cả 9 nhóm test cũ lẫn nhóm test multi-save có sẵn từ trước, không có regression.
- Frontend: dựng DOM thật bằng `jsdom` (Node) — không phải shim tối giản như lần trước, mà chạy toàn bộ `index.html` thật với `runScripts: "dangerously"` — xác nhận: render đúng 3 save-item với dữ liệu mẫu (kể cả label chứa tiếng Việt có dấu, dấu `"`, và chuỗi `<script>` cố tình để test — xác nhận không lọt vào DOM thật vì set qua `.textContent`), tag safety tô đúng màu, đủ 9 nút hành động (3 save × 3 nút), dispatcher `renderCreatorTab("saves")` gọi đúng hàm, render đúng empty-state khi chưa có save, và **không crash** khi `currentWorldData.saves` bị thiếu (world cũ tạo trước khi có tính năng này). Đây thay thế được việc mở Chrome thật ở mức tốt hơn lần trước (jsdom chạy đúng script thật của trang, không phải code viết lại), nhưng **vẫn nên** Rinn tự mở thử 1 lần trên trình duyệt để xác nhận CSS/layout hiển thị đúng, đặc biệt là khu vực nút hành động 3 nút trên 1 hàng có bị vỡ dòng xấu ở màn hình hẹp không.



- `backend/main.py` — code chính. Đã test bước 0+1+2 bằng FastAPI TestClient, bước 2 lại bằng uvicorn thật + curl khi làm bước 3, bước 4+6 (card filtering + checkpoint engine) bằng cả TestClient lẫn uvicorn thật + curl, bước 5+6 hoàn thiện (consistency checker + boundary fallback thật) cũng bằng cả 2 cách, 5 endpoint Creator mode (bước 7, mục 5g), và phần multi-save (bước 8, mục 5h) — tất cả đã **tự chạy `python3 test_engine.py` thật trong sandbox và PASS toàn bộ**. Riêng phần RAG-lite lore card (mục 5i, nhóm test 16) làm ở sandbox KHÔNG có mạng nên chưa tự chạy `test_engine.py` thật được lần này — đã bù bằng kiểm tra logic độc lập (xem mục 5i), nhưng Rinn cần tự chạy lại 1 lần để xác nhận cuối bằng FastAPI TestClient thật.
- `backend/prompts.py` — 3 system prompt: world-builder agent, narrator agent (đã có rule #7 xử lý `correction_note`), và `CONSISTENCY_CHECKER_SYSTEM_PROMPT` (xem mục 5e). Không đổi ở bước 7+8.
- `backend/test_engine.py` — script test end-to-end (không phải CI chính thức), có **16 nhóm test** (9 nhóm cũ + 5 nhóm Creator mode + multi-save trong nhóm 15 + nhóm 16 RAG-lite mới thêm ở mục 5i, xem lưu ý chưa tự chạy được ở mục 5i/7). 
- `frontend/index.html` — bước 3 (khung chat) + toast báo checkpoint tự động chuyển (mục 5d) + hiển thị cảnh báo boundary/consistency ngay dưới mỗi chapter (mục 5f) + Creator Mode UI (mục 5g): giờ có **6 sub-tab** (World Config, Checkpoints, Cards, Characters, 💾 Saves & Nhánh — mới thêm mục 5h, Lịch sử can thiệp).
- Cấu trúc thư mục thật trên máy user: `C:\story-engine\backend`, `C:\story-engine\data\worlds\`, `C:\story-engine\frontend`.

## 5i. Bước 8 (phần "còn thiếu" cuối) — RAG-lite lore card, cảnh báo unsaved changes, tìm/lọc Saves

Làm tiếp đúng 3 việc còn lại liệt kê ở mục 7 #5 (bỏ qua khoản "UI đẹp hơn" theo yêu cầu — không đụng gì tới CSS/styling, chỉ thêm chức năng còn thiếu).

### 1. RAG-lite cho lore card (mục 2.1 #1)
**Vấn đề cũ**: card `type: "lore"` một khi unlock là "sticky" — nhồi thẳng hết vào context mỗi chapter, không giới hạn. Ở quy mô demo (1-2 lore card) không sao, nhưng world lớn dần (chục lore card) sẽ tốn token và loãng sự chú ý của narrator vào lore không liên quan chapter hiện tại.

**Quyết định**: chưa cần vector store/embedding API thật (tránh phụ thuộc mạng ngoài + API key riêng cho RAG, đi ngược tinh thần "local app đơn giản" của dự án). Thay vào đó dùng 1 lớp **RAG-lite thuần Python, không thêm dependency ngoài** (chỉ dùng `re`/`math`/`collections.Counter` có sẵn trong Python):
- Tokenize đơn giản (unicode-aware, bỏ số/dấu câu, bỏ 1 tập stopword VI+EN nhỏ).
- Xếp hạng lore card theo **cosine similarity bag-of-words** giữa nội dung card và "ngữ cảnh gần đây" (vài chapter gần nhất ghép với `user_input` hiện tại).
- **Chỉ áp dụng khi vượt ngưỡng**: nếu số lore card đã unlock ≤ `lore_rag_max_cards` thì giữ nguyên hành vi cũ (nhồi hết) — world nhỏ như seed-demo không bị ảnh hưởng gì.

Field mới `world_config.lore_rag_max_cards` (3 trạng thái):
- `null`/để trống → dùng mặc định hệ thống (`DEFAULT_LORE_RAG_MAX_CARDS = 6`).
- `0` → Creator chủ động tắt hẳn, không giới hạn (hành vi cũ 100%).
- số dương → giới hạn thật đúng số đó.

`get_active_cards()` nhận thêm 2 tham số optional `context_text`/`max_lore_cards` (mặc định `""`/`None` = không đổi hành vi cũ, các lời gọi cũ 2 tham số vẫn chạy y hệt trước). Hàm mới: `_rag_tokenize`, `_rag_cosine_score`, `select_relevant_lore_cards`, `build_rag_context_text`. `chapter_continue` tính `context_text` từ 3 chapter gần nhất + `user_input`, và **consistency checker dùng lại đúng `active_cards` đã lọc** (không tính lại riêng) nên checker và narrator luôn thấy cùng 1 tập lore.

Response của `POST /chapter/continue` có thêm field `lore_rag_filter` (object nếu filter thật sự có tác dụng chapter đó, `null` nếu không) để Creator biết filter có chạy hay không — frontend hiện 1 toast ngắn khi có.

**Frontend**: thêm 1 field số trong tab World Config (`lore_rag_max_cards`, placeholder gợi ý giá trị mặc định hệ thống), kèm 1 dòng hint giải thích. `PUT /world_config` validate giá trị âm → 400.

### 2. Cảnh báo "unsaved changes" khi rời Creator Mode
Theo dõi dirty-state chỉ ở 4 vùng có nút "Lưu" riêng (World Config, Cards, Checkpoints, Characters — đánh dấu class `dirty-tracked`), KHÔNG theo dõi tab Saves/Lịch sử (hành động ở đó thực thi ngay, không có bước sửa-rồi-lưu-sau). Cơ chế: 1 listener `input`/`change` delegate trên `#creatorPanelBody`, set cờ `creatorDirty=true` + hiện chữ "● có thay đổi chưa lưu" cạnh các sub-tab. Cờ tự tắt mỗi khi `renderCreatorTab()` render lại (bất kỳ lý do gì — lưu thành công, xóa 1 dòng, chuyển tab — DOM cũ mất thì dữ liệu sửa dở cũng mất theo, dirty phải về `false` đúng lúc đó).

3 điểm chặn điều hướng, đều gọi chung `confirmLeaveCreatorIfDirty()` (hỏi `confirm()`, hủy điều hướng nếu người dùng bấm Hủy):
- Chuyển sub-tab trong Creator Mode.
- Bấm nút "Chơi truyện" để rời Creator Mode (không chặn chiều ngược lại — vào Creator Mode không mất gì).
- Chọn world khác ở sidebar.

Ngoài ra có `window.addEventListener("beforeunload", ...)` chặn đóng/tải lại tab trình duyệt khi đang dirty — đúng nghĩa đen "cảnh báo khi rời trang" như yêu cầu gốc.

### 3. Tìm kiếm/lọc trong tab Saves
Khi danh sách save dài: thêm 1 ô tìm theo nhãn (`label`, không phân biệt hoa/thường) + 1 dropdown lọc theo `checkpoint_id` (danh sách option tự sinh từ các checkpoint đã từng save). Lọc trực tiếp trên dữ liệu đã có sẵn (`currentWorldData.saves`), không gọi thêm API.

### Đã kiểm tra
Sandbox **lần này không có mạng** (khác lần làm mục 5h) — không cài được `fastapi`/`pydantic`/`uvicorn` nên **không tự chạy được `test_engine.py` thật** như các lần trước. Đã bù lại bằng 3 cách:
1. `ast.parse()` xác nhận `main.py` và `test_engine.py` không lỗi cú pháp.
2. Trích riêng logic RAG-lite (tokenize + cosine + chọn top-N) chạy độc lập ngoài FastAPI với đúng dữ liệu của test mới thêm (nhóm 16 trong `test_engine.py`) — xác nhận đúng thứ hạng thật (card khớp `user_input` lên hạng 1, card trùng tên nhân vật lên hạng 2 do overlap "Xue Li", card không liên quan bị loại đúng như kỳ vọng) trước khi chốt assertion trong test.
3. **Playwright + Chromium thật** (có sẵn trong sandbox, không cần mạng) load thẳng `frontend/index.html`, mock toàn bộ API bằng `page.route()`, và tương tác thật trên DOM: xác nhận field `lore_rag_max_cards` hiện đúng, sửa field → indicator dirty hiện ra, chuyển tab lúc dirty → đúng 1 hộp thoại `confirm()` với đúng nội dung, bấm Lưu không bị hỏi confirm và gửi đúng payload `{"lore_rag_max_cards": 0}`, tab Saves có ô tìm kiếm + dropdown đúng option, lọc theo checkpoint và theo nhãn đều ra đúng số lượng save còn lại. Tất cả PASS.

**Rinn vẫn cần tự chạy `python3 test_engine.py` thật trên máy (có mạng/đã cài `fastapi`) để xác nhận nhóm test 16 (RAG-lite) PASS bằng FastAPI TestClient thật** — đây là lần đầu tiên từ bước 5g tới giờ mà việc này chưa tự làm được trong sandbox, cần nói rõ để không hiểu nhầm là đã test như các bước trước.

## 5j. Bước 0 (mục 2 + 3 roadmap mới) — Retry-with-backoff cho 429 + API key/model UI trong Creator Mode (vừa xong)

Rinn tự làm xong UI (mục 1 của roadmap mới), giao lại làm tiếp đúng 2 việc còn lại trước phần tự chơi thử: retry-with-backoff khi bị rate-limit và API key UI. Không đụng gì tới UI/CSS đã có sẵn ngoài phần thêm mới cho 2 việc này.

### 1. Retry-with-backoff cho 429 + báo lỗi rõ ràng thay vì treo im lặng
`class LLMCallError(Exception)` mới: đại diện cho lỗi gọi OpenRouter **thật sự** trong lúc đã có API key thật (khác hẳn trường hợp chưa có key nào, vẫn fallback mock như cũ để test/dev không tốn token). `call_llm` giờ tự retry tối đa `MAX_RATE_LIMIT_RETRIES = 3` lần khi gặp `429`, chờ theo `_rate_limit_wait_seconds()` (ưu tiên header `Retry-After` của OpenRouter nếu có, không thì backoff mù 2s/4s/8s). Hết lượt retry, lỗi mạng (`requests.exceptions.RequestException`), hoặc response sai định dạng (thiếu `choices`/`message`/`content`) → raise `LLMCallError` thay vì âm thầm trả về mock — đây chính là vấn đề cũ mà roadmap gọi là "treo im lặng" (thực ra không phải treo thật, mà là hiện nhầm nội dung mock khiến Rinn tưởng đang xem output LLM thật).

2 nơi gọi `call_llm` xử lý `LLMCallError` khác nhau, đúng vai trò từng agent:
- `call_narrator_and_parse` (narrator — bắt buộc): bắt lỗi, raise `HTTPException(503, detail=...)` với message cụ thể (429/lỗi mạng/key sai/response sai) → frontend hiện toast cảnh báo ngay, **không ghi chapter nào** (tránh state nửa vời — chapter text và state_changes phải luôn đi cùng nhau).
- `run_consistency_checker` (checker — phụ, đã có nguyên tắc fail-open từ bước 5e): bắt lỗi, trả về `{"severity": "none", ...}` như các trường hợp fail-open khác, nhưng `explanation` ghi rõ `"[CHECKER KHÔNG CHẠY ĐƯỢC — fail-open] <lý do>"` để phân biệt với "đã kiểm tra và thật sự nhất quán" — quan trọng vì 2 trường hợp này nhìn giống nhau ở `severity: "none"` nhưng ý nghĩa khác hẳn.

`get_effective_api_key()`/`get_effective_model()` (xem mục 2 bên dưới) thay thế trực tiếp `os.environ.get("OPENROUTER_API_KEY"/"OPENROUTER_MODEL")` trong `call_llm` — không đổi hành vi cũ nếu Rinn chưa dùng UI mới, chỉ thêm 1 nguồn cấu hình ưu tiên cao hơn.

### 2. API key + model UI trong Creator Mode
File mới `data/runtime_config.json` (global — dùng chung mọi world, giữ đúng bản chất cũ của biến môi trường, KHÔNG phải setting riêng từng world) lưu `openrouter_api_key`/`openrouter_model`. Helper: `read_runtime_config`/`write_runtime_config`/`get_effective_api_key`/`get_effective_model`/`has_real_api_key`/`_mask_api_key`/`build_runtime_config_status`. Ưu tiên: **giá trị lưu qua UI > `.env`/biến môi trường** — nếu UI chưa từng set gì thì fallback y hệt hành vi cũ.

3 endpoint mới, đều trả `build_runtime_config_status()` (không bao giờ trả key thật dạng plain text, chỉ trả bản mask kiểu `sk-o…abcd` qua `_mask_api_key`, tránh lộ key qua network log/devtools):
- `GET /runtime-config` — xem trạng thái hiện tại (có key chưa, nguồn `ui`/`env`/`none`, model đang dùng).
- `PUT /runtime-config` — body `{openrouter_api_key?, openrouter_model?}`, field nào `None`/không gửi thì giữ nguyên, gửi chuỗi rỗng `""` thì xoá/reset field đó.
- `DELETE /runtime-config/api-key` — xoá riêng key đã lưu qua UI (không đụng model), quay về dùng `.env` nếu có, hoặc mock nếu không.

Frontend: sub-tab mới **🔑 API & Model** trong Creator Mode (cạnh Saves & Branches) — `renderApiKeyTab`/`buildApiKeyForm` trong `app.js`. Khác các tab khác (World Config/Cards/Checkpoints/Characters): đây là config **toàn cục**, không nằm sẵn trong `currentWorldData` nên phải tự `apiFetch("/runtime-config")` riêng khi vào tab; và **không** nằm trong dirty-tracking (giống tab Saves) vì mỗi nút tự lưu ngay, không có bước "sửa rồi Lưu tất cả" gộp lại. Có ô nhập key mới (`type="password"`) + model, nút "💾 Save key & model" (bỏ qua field nào để trống — không ép phải nhập cả 2 mỗi lần), nút "🗑 Clear saved key" tự `disabled` khi key hiện tại không phải lưu qua UI (tránh hiểu nhầm là xoá được cả key trong `.env`). Đổi có hiệu lực ngay từ tin nhắn kế tiếp, không cần restart server hay F5 lại trang. Badge "MOCK LLM" ở header world (đã có từ trước) đổi text trỏ thẳng tới tab mới thay vì chỉ nhắc chung chung về biến môi trường.

### Đã kiểm tra
Sandbox lần này **có mạng** — cài được `fastapi`/`pydantic`/`requests`/`httpx`/`uvicorn`, tự chạy được `test_engine.py` thật bằng FastAPI TestClient (không phải suy luận qua `ast.parse` như mục 5i):
1. **Chạy lại toàn bộ 16 nhóm test cũ trước khi sửa gì** — PASS hết, xác nhận baseline sạch.
2. Thêm **nhóm test 17** (7 phần a–g) test riêng phần vừa làm: `GET/PUT/DELETE /runtime-config` (mask đúng, persist đúng file, xoá key không đụng model); `call_llm` monkeypatch `requests.post` giả 429 2 lần rồi thành công lần 3 → xác nhận gọi lại đúng 3 lần + `time.sleep` đúng 2 lần (đã monkeypatch `time.sleep` thành no-op để test chạy nhanh, không chờ thật); 429 hết sạch lượt retry → xác nhận raise đúng `LLMCallError`; `chapter/continue` khi narrator lỗi thật → đúng `503` + **không ghi chapter nào**; khi checker lỗi thật → vẫn `200`, `severity: "none"` fail-open, `explanation` ghi đúng lý do. **Chạy lại toàn bộ 17 nhóm (cũ + mới) — PASS hết, không regression.**
3. Frontend: viết 1 script Node dùng `jsdom` (mock `window.fetch`, load thật `index.html`+`app.js`, không phải suy luận đọc code) — chọn world, chuyển Creator Mode, bấm sang tab "🔑 API & Model" mới, xác nhận hiện đúng trạng thái MOCK LLM ban đầu, nhập key+model rồi bấm Lưu → gửi đúng payload `PUT /runtime-config`, UI cập nhật ngay thành "Live LLM" không cần reload; bấm "Clear saved key" (có mock `confirm()` trả `true`) → gọi đúng `DELETE /runtime-config/api-key`, UI quay lại "MOCK LLM" ngay. Tất cả PASS.
4. Xác nhận thư mục `data/` không còn rác sau khi chạy test (test tự backup/khôi phục `runtime_config.json` thật nếu có, tự xoá world test tạo ra).

**Việc CHƯA làm / để dành sau (không bắt buộc cho bước 0, phát sinh khi làm mục này):**
- `runtime_config.json` lưu key dạng plain text trên đĩa — chấp nhận được cho local app cá nhân (giống `.env` vốn cũng plain text), nhưng cần xem lại nếu sau này đóng gói chia sẻ/multi-user.
- Config hiện là global, chưa hỗ trợ key/model riêng theo từng world — nếu Rinn cần chạy song song nhiều world với provider khác nhau thì đây là việc thêm sau, không phải thiếu sót của yêu cầu gốc.
- **Chưa test được với OpenRouter thật** (sandbox không có mạng tới `openrouter.ai`) — retry logic mới chỉ được test qua monkeypatch `requests.post` giả lập 429, chưa xác nhận hành vi thật với rate-limit thật từ OpenRouter (vd header `Retry-After` thật trả về đúng định dạng gì). Đây là việc mục 4 dưới đây (Rinn tự chơi thử) sẽ tự nhiên phát hiện nếu có sai khác.

## 5k. Chapter mở đầu / "first message" kiểu SillyTavern (roadmap mới mục 15, 05/07/2026)

**Vấn đề phát hiện lúc Rinn playtest thật:** world mới/rỗng không có gì tương đương "greeting message" — chapter 1 thực chất là do Rinn tự gõ tay hành động đầu tiên rồi mới đưa qua narrator, không phải app tự sinh ra gì.

**Backend:** tách phần thân dùng chung của pipeline (build payload → narrator → boundary fallback → consistency checker → merge state → save chapter → advance checkpoint) ra hàm riêng `_generate_chapter(world_name, narrator_input, display_input=None)` — `/chapter/continue` giờ chỉ còn 1 dòng gọi lại hàm này. `narrator_input` (gửi LLM thật) và `display_input` (lưu vào `chapter_record["user_input"]`, hiện lên UI) tách riêng, vì chế độ tự sinh cần gửi 1 câu instruction hệ thống cho narrator nhưng KHÔNG hiện câu đó lên UI như user vừa gõ.

Endpoint mới `POST /worlds/{world_name}/chapter/start` (chỉ dùng được khi `chapters.json` còn rỗng, gọi lại khi đã có chapter → `400`), 2 chế độ qua `world_config.opening_mode`:
- `ai_generate` (mặc định): `build_opening_instruction(checkpoint)` soạn instruction dựa trên mô tả checkpoint hiện tại, chạy đủ pipeline thật (boundary + consistency checker) như 1 chapter bình thường.
- `user_defined`: ghi thẳng `opening_text` (Creator tự viết/dán) thành chapter 1, **không gọi narrator/checker**, không tốn API call.

`opening_mode`/`opening_text` nằm ngay trong `world_config.json` — dùng chung cho **mọi save/branch** của world đó (đúng bản chất "first message" gắn với world/nhân vật, không gắn với 1 phiên chơi cụ thể), khác `chapters.json`/`character_state.json` vốn có bản riêng theo từng save.

**Frontend:** panel "bắt đầu truyện" khi chưa có chapter nào (2 lựa chọn: AI tự viết / tự viết tay), Creator Mode → World Config có thêm field `opening_mode` (dropdown) + `opening_text` (textarea) để set sẵn mặc định cho world.

**Test:** `test_engine.py` nhóm 18 (7 case) — PASS toàn bộ, không regression.

**Giới hạn đã biết:** `build_opening_instruction()` viết cứng tiếng Việt (world demo hiện tại toàn tiếng Việt) — nếu sau này Rinn tạo world tiếng Anh và dùng `ai_generate`, cảnh mở đầu nhiều khả năng vẫn ra tiếng Việt. Cố tình để dành, chưa đáng làm cho 1 world duy nhất hiện có.

## 5l. Tầng Turn/Chapter (roadmap mới mục 1, 07/07/2026)

**Vấn đề:** trước đây 1 lần gọi narrator = luôn = 1 `chapter_record`, gây 2 cực đoan: tương tác nhỏ dồn thành feed vụn vặt như nhật ký, hoặc ép narrator viết dài mỗi lượt (tốn token, dễ bị 429).

**Tách 2 khái niệm:**
- **Turn**: 1 lần gọi narrator, đoạn ngắn. `turn_index` **reset về 1 mỗi khi sang chapter mới** (không cộng dồn toàn world) — để Rinn dễ trỏ tay khi cần regenerate 1 đoạn cụ thể.
- **Chapter**: gom nhiều turn liên tiếp, đóng theo ngưỡng mềm (`CHAPTER_SOFT_CLOSE_TURNS=5` turn, hoặc `CHAPTER_SOFT_CLOSE_WORDS=900` từ cộng dồn) hoặc narrator tự báo `chapter_end: true`, có `CHAPTER_HARD_CLOSE_TURNS=8` làm rào an toàn cuối cùng phòng model free-tier bỏ qua cả 2 cơ chế trên.
- **Checkpoint vẫn là Arc**, không đổi gì.

`chapters.json` **giữ nguyên list phẳng** (không lồng `turns` trong `chapters`) — mỗi phần tử giờ là 1 TURN record, thêm 3 field mới `turn_index`, `chapter_closed`, `chapter_title` (chỉ có giá trị khi turn đó đóng chapter của nó). **Tương thích ngược 100%** với world cũ: thiếu `chapter_closed` được coi mặc định `True` (đã đóng) → turn tiếp theo tự bắt đầu chapter mới, đúng y hệt hành vi cũ, không cần migration script.

`recent_chapters_for_context` (lấy `[-3:]` theo CHAPTER) đổi thành `get_recent_turns_for_context()` — payload gửi narrator đổi key `recent_chapters` → `recent_turns`. `build_save_entry`: `chapter_count` giờ = `chapter_index` của turn cuối cùng (không còn `len(list)`), thêm `turn_count` riêng = tổng số turn.

**Frontend:** 1 chapter render thành 1 khối `.chapter-card` duy nhất chứa nhiều `.turn-block` chảy liền bên trong (chỉ 1 header "Chapter N" mỗi chapter).

**Test:** `test_engine.py` nhóm 19 (7 test con) — PASS toàn bộ.

## 5m. Sliding window + running summary cho context (roadmap mới mục 2, 08/07/2026)

**Vấn đề:** cửa sổ turn thô gửi narrator (mục 5l) vẫn rớt hoàn toàn mọi thứ trước cửa sổ đó — story càng dài narrator càng "quên" chapter cũ.

**2 quyết định của Rinn:**
- **Cách tóm tắt: LLM tóm tắt riêng** — agent thứ 3 `SUMMARIZER_SYSTEM_PROMPT`, chạy **chỉ khi 1 chapter vừa đóng lại**, nhận `previous_summary` + toàn văn chapter vừa đóng → trả về 1 summary MỚI **đã tích hợp** (không nối chuỗi vô hạn, tự nén mạnh hơn phần cũ mỗi lần thêm mới, giữ ~100-250 từ bất kể truyện dài bao nhiêu chapter).
- **Cửa sổ turn nguyên văn: giảm 5 → 2** (`RECENT_TURNS_CONTEXT_LIMIT`).

`running_summary` (string) nằm ở **cấp top-level của `chapters.json`**, ngang hàng `"chapters"` — tự động snapshot theo save/branch giống 4 file JSON còn lại, world cũ thiếu field đọc mặc định rỗng. **Fail-open** y hệt consistency checker: lỗi gọi summarizer → giữ nguyên `running_summary` cũ, không chặn/làm hỏng chapter vừa sinh.

`running_summary` được đưa vào cả payload narrator (`base_payload["running_summary"]`, kèm rule 12 mới trong `NARRATOR_SYSTEM_PROMPT` dặn dùng làm bối cảnh nền, không trích nguyên văn) lẫn `build_rag_context_text` (để RAG-lite chọn lore không mất độ chính xác do cửa sổ thô co lại).

**Test:** `test_engine.py` nhóm 20 (13 test con) — PASS toàn bộ, cover mock/parse fail-open, nội dung payload gửi summarizer, thứ tự gọi (chỉ khi đóng chapter), fail-open không chặn chapter, running_summary có mặt đúng trong payload narrator.

**Giới hạn đã biết:** nếu 1 chapter đang MỞ tích luỹ nhiều turn (tối đa 8 turn trước khi bị ép đóng), các turn ở giữa (vượt cửa sổ 2 turn nhưng chapter chưa đóng nên summarizer chưa chạy) tạm thời không nằm trong cả cửa sổ thô lẫn running_summary — có thể mất vài chi tiết giữa chừng cho tới khi chapter đó đóng lại. Chấp nhận đánh đổi này ở bản đầu, để playtest quyết định bước tiếp theo.



**Cập nhật trạng thái 08/07/2026 (mới nhất) — thay cho danh sách 04/07 bên dưới đã lỗi thời:**

1. ✅ Chapter mở đầu / "first message" (roadmap mới mục 15) — xong 05/07, xem mục 5k.
2. ✅ Tầng Turn/Chapter (roadmap mới mục 1) — xong 07/07, xem mục 5l.
3. ✅ Sliding window + running summary cho context (roadmap mới mục 2) — xong 08/07, xem mục 5m.
4. ✅ Tách Settings (API key/Model) ra khỏi Creator Mode + override riêng theo world (roadmap mới mục 0.6 #3) — xong 21/07, xem mục 5n.
5. Lưu ý chung: cả 4 mục trên đều chưa có bước Rinn tự chơi thử thật trên máy (sandbox chỉ test được qua TestClient/mock, không có mạng thật tới OpenRouter) — nên để ý khi playtest thật: chapter mở đầu tiếng Anh có bị lệch tiếng Việt không (giới hạn đã biết ở 5k), nhịp đóng chapter (turn/chapter tier) có hợp lý không, running_summary có thực sự giữ được mạch truyện dài không (giới hạn đã biết ở 5m), và layout mới của tab ⚙️ Settings (chưa mở Chrome thật, xem mục 5n).

## 5n. Tách Settings (API key/Model) ra khỏi Creator Mode + override riêng theo world (roadmap mới mục 0.6 #3, 21/07/2026)

**Vấn đề:** tab "🔑 API & Model" cũ nằm trong Creator Mode — 2 thứ khác bản chất bị gộp chung: cấu hình vận hành (key/model, không spoil gì, nên luôn truy cập được) vs công cụ GM thật (sửa card/checkpoint/state, cần khoá khi đang chơi để tránh spoil chính mình).

**Thiết kế đã chốt cùng Rinn trước khi làm (3 câu hỏi nhanh):**
1. **Vị trí:** Settings thành mode-tab thứ 3 ngang hàng "📖 Play Story"/"🛠️ Creator Mode" khi đang mở 1 world (luôn bấm được, không cần mở khoá Creator Mode) — **cộng thêm** 1 nút "⚙️ Settings" riêng ở sidebar, luôn bấm được kể cả **chưa mở world nào** (World Config/Cards/Checkpoints/Characters đều cần world, nhưng key/model app-default thì không).
2. **Override riêng world lưu ở đâu:** file riêng `data/worlds/<world>/runtime_override.json`, **tách hẳn** khỏi `world_config.json` — không phải state/canon truyện, không đi theo save/branch/export world sau này.
3. **Thứ tự ưu tiên khi cả 3 đều có giá trị:** world override > app default (UI) > `.env`.

**Backend (`main.py`):**
- `read_world_runtime_override()`/`write_world_runtime_override()` — đọc/ghi file override riêng world, cùng shape với `runtime_config.json` (`openrouter_api_key`/`openrouter_model`), rỗng nếu world chưa từng set.
- `get_effective_api_key(world_name=None)`/`get_effective_model(world_name=None)`/`has_real_api_key(world_name=None)` — thêm tham số `world_name` optional, ưu tiên override world > app default (UI) > `.env`. Không truyền `world_name` (hành vi cũ, dùng ở `/runtime-config` app-level) thì y hệt trước — không phá gì.
- `call_llm()`, `test_llm_connection()`, `run_consistency_checker()`, `call_narrator_and_parse()`, `update_running_summary()` đều thêm `world_name=None` optional, truyền xuyên suốt từ `_generate_chapter(world_name, ...)` — narrator/checker/summarizer của 1 world giờ tự động dùng đúng override của world đó nếu có set, không cần sửa gì thêm ở endpoint `/chapter/continue`/`/chapter/start`.
- `build_runtime_config_status(world_name=None)` — mở rộng response: field top-level (`has_api_key`/`api_key_source`/`model`/...) là trạng thái **hiệu lực thật sự** (đã tính override nếu có); thêm 2 field mới `app_default` (luôn là lớp UI/env, không bao giờ tính override) và `world_override` (chỉ khác `None` khi có `world_name`) — để Settings UI vẽ được RIÊNG 2 khối "App default" vs "Override cho world này" thay vì chỉ 1 con số gộp chung.
- Endpoint mới, cùng shape với `/runtime-config` cũ nhưng theo world: `GET/PUT /worlds/{world}/runtime-config`, `DELETE /worlds/{world}/runtime-config/api-key`, `POST /worlds/{world}/runtime-config/test-connection` — dùng lại `require_world()` sẵn có nên world không tồn tại tự động trả 404 giống các endpoint world khác.
- `/runtime-config` (không world) giữ nguyên hành vi cũ 100% — chỉ cộng thêm 2 field `app_default`/`world_override` (`world_override` luôn `None` ở endpoint này).

**Frontend (`index.html`/`app.js`):**
- Bỏ hẳn sub-tab "🔑 API & Model" khỏi `creatorSubTabs` — Creator Mode giờ chỉ còn World Config/Checkpoints/Cards/Characters/Saves/Intervention Log (đúng công cụ GM thật).
- `modeTabs` trong world view thêm nút thứ 3 "⚙️ Settings" (`modeSettingsBtn`) + pane mới `settingsModeView`/`settingsPanelBody`, dùng chung logic bật/tắt với Play/Creator hiện có (`switchMode("settings")`).
- Sidebar thêm nút `settingsSidebarBtn` — có world đang mở thì đưa thẳng vào tab Settings CỦA world đó (đủ cả app default + override riêng); chưa mở world nào thì hiện view độc lập mới `standaloneSettingsView`/`standaloneSettingsBody` (chỉ app default, không có world nào để override).
- `renderSettingsPanel(container, worldName)` — hàm dùng chung cho cả 2 chỗ gọi trên, fetch `/runtime-config` (worldName null) hoặc `/worlds/{world}/runtime-config`, luôn hiện dòng "Effective status" (trạng thái hiệu lực thật sự) ở đầu, rồi 1 section "App default (all worlds)" luôn có, cộng thêm section "Override for this world" nếu có `worldName`.
- `buildRuntimeConfigForm(section, statusData, opts)` — form dùng chung (thay `buildApiKeyForm` cũ), tham số hoá qua `opts.putPath/deletePath/testPath/isOverride` nên 1 bộ code phục vụ cả app-default lẫn world-override — vẫn giữ nguyên UX cũ đã có (toggle 👁 hiện/ẩn key, nút Test connection phân loại lỗi rõ, nút Clear disable đúng lúc, không dirty-tracked vì mỗi hành động tự lưu ngay giống trước).
- Text badge "MOCK LLM" ở header world đổi hướng dẫn từ "Creator Mode → 🔑 API & Model" sang "⚙️ Settings".

**Việc CHƯA làm / giới hạn đã biết:**
- Chưa có UI để Creator "xoá hẳn" file `runtime_override.json` khỏi world (chỉ xoá được key qua nút Clear, model override vẫn có thể còn sót lại riêng lẻ — đúng hành vi 2 field độc lập nhau như app default cũ, không phải thiếu sót).
- Chưa mở Chrome thật để xem layout/CSS thật của mode-tab thứ 3 + view độc lập mới (2 section xếp dọc, responsive khi màn hẹp) — chỉ mới xác nhận qua `jsdom` (DOM/JS đúng, chưa xác nhận đẹp/lệch layout).
- Rinn nên tự test tay ít nhất 1 lần: set app default, mở 1 world set thêm override riêng, xác nhận Effective status đổi đúng, sau đó xoá override và xác nhận quay lại dùng app default — trước khi coi mục này là đóng hẳn.

**Test:** `test_engine.py` nhóm 21 (9 nhóm con, ~25 assertion) — GET/PUT/DELETE/test-connection world-scoped đều đúng, world không tồn tại → 404, ưu tiên world override > app default đúng cả ở `get_effective_api_key()`/`call_llm()` lẫn qua HTTP, world khác không bị rò rỉ override của world khác, override lưu tách biệt khỏi `world_config.json`. Đã tự chạy, **PASS toàn bộ 21 nhóm** (20 nhóm cũ + nhóm mới), không có regression — kèm sửa lại chữ ký 18 hàm `fake_call_llm_*` có sẵn trong `test_engine.py` để nhận thêm `world_name=None` (tương thích với `call_llm()` giờ có thêm tham số này). Frontend: smoke-test bằng `jsdom` (mock `fetch`) cho cả 2 luồng — sidebar Settings khi chưa mở world nào (chỉ hiện app default) và tab Settings trong 1 world đang mở (hiện cả app default + override) — PASS, không giữ lại làm file chính thức trong project (đúng cách làm cũ ở các mục trước).



**Cập nhật trạng thái 04/07/2026 (sau mục 5j) — thay cho danh sách cũ bên dưới đã lỗi thời ở vài chỗ:**

1. ✅ UI giao diện — Rinn đã tự làm xong bản pastel March 7th (blush pink/ice blue/cream white, Baloo 2 + Nunito) trước khi giao lại phần này, KHÔNG đụng gì thêm tới CSS/layout ở mục 5j.
2. ✅ Retry-with-backoff cho 429 + API key/model UI trong Creator Mode — xong ở mục 5j, đã tự test kỹ (17 nhóm `test_engine.py` bằng FastAPI TestClient thật + smoke-test `jsdom` cho frontend), xem chi tiết ở mục 5j và roadmap mục 0.1.
3. ⬜ **Việc còn lại duy nhất theo roadmap mới: Rinn tự chơi thử world Xue Li / Gu Changge với API key thật**, ghi lại bug/chỗ khó dùng thật. Giờ đổi key/model không cần sửa `.env` + restart nữa (vào Creator Mode → tab 🔑 API & Model). Cụ thể nên để ý:
   - Chất lượng JSON thật từ model free-tier (vd DeepSeek V3 qua OpenRouter) có ổn định không, đặc biệt checker có tránh chặn nhầm (false positive "major") không.
   - Đường lỗi mới khi thật sự bị rate-limit/lỗi mạng: có thấy toast cảnh báo rõ ràng (503) thay vì bị "treo" hay thấy nhầm nội dung mock không.
   - Layout tab "🔑 API & Model" mới — mới chỉ test qua `jsdom` (DOM thật nhưng không phải mở tay Chrome), chưa xác nhận CSS/responsive thật khớp theme pastel.
   Sandbox không truy cập được `openrouter.ai` (ngoài whitelist mạng) nên phần có-kết-nối-thật-tới-OpenRouter này bắt buộc phải làm trên máy Rinn.

Danh sách gốc trước mục 5j (để tham khảo lịch sử, vài ý đã lỗi thời — xem bản cập nhật ở trên):

1. ✅ **Đã chạy `python3 test_engine.py` thật** (sandbox lúc đó có mạng) — **PASS toàn bộ 14 nhóm test cũ**, kể cả phần multi-save (mục 5h). Không có regression.
2. User tự mở `frontend/index.html` trên máy (song song chạy `uvicorn main:app` từ `C:\story-engine\backend`), xác nhận UI hoạt động đúng thực tế — ngoài các phần cũ, giờ cần test thêm:
   - **Creator Mode** (mục 5g): chuyển qua lại 2 mode tab, sửa/thêm/xóa card-checkpoint-character, ép chuyển checkpoint (thử cả trường hợp nhảy nhiều checkpoint 1 lúc), tab lịch sử can thiệp, JSON thô nhập sai cú pháp.
   - **Saves & Nhánh** (mục 5h): tạo vài save point có/không nhãn, restore về 1 save cũ rồi xác nhận safety-save tự xuất hiện, branch ra world mới rồi xác nhận world mới hiện đúng ở sidebar và state khớp save nguồn, xóa save. Layout 3 nút hành động (Restore/Branch/Xóa) mới chỉ test qua `jsdom`/Playwright (DOM thật nhưng không phải mở tay trên Chrome), chưa xác nhận CSS responsive thật.
   - **RAG-lite lore card** (mục 5i, MỚI): seed 1 world rồi thêm tay > 6 lore card unlocked (qua tab Cards), set `lore_rag_max_cards` = 2-3 ở World Config, gửi vài chapter và quan sát toast "RAG-lite: chọn N/M lore card..." có xuất hiện đúng lúc không, thử set về `0` để tắt hẳn xem có nhồi lại đủ hết lore không.
   - **Cảnh báo unsaved changes** (mục 5i, MỚI): sửa 1 field ở World Config/Cards/Checkpoints/Characters mà KHÔNG bấm Lưu, rồi thử: chuyển sub-tab, bấm "Chơi truyện", chọn world khác, và tải lại trang (F5)/đóng tab — cả 4 đều phải hỏi xác nhận trước khi mất dữ liệu.
   - **Tìm/lọc Saves** (mục 5i, MỚI): tạo đủ nhiều save (khác checkpoint, có/không nhãn) rồi thử gõ vào ô tìm kiếm và đổi dropdown checkpoint, xác nhận danh sách lọc đúng.
   World cũ tạo trước khi có `completed_checkpoints`/`realm_updates`/`saves`/`lore_rag_max_cards` vẫn đọc được (field mới đều có default an toàn qua `.get()`), nhưng nên seed-demo lại nếu muốn test đầy đủ.
3. ✅ (đã dễ hơn nhiều từ mục 5j) Set thử API key thật giờ làm qua tab 🔑 API & Model, không cần sửa `.env` + restart nữa — nội dung xác nhận chất lượng JSON thật vẫn còn nguyên, xem mục cập nhật ở trên.
4. ✅ Đã giải quyết giới hạn hard-clamp cũ (đổi sang hard-reject 409) — xem chi tiết đầy đủ ở lịch sử, không cần làm lại.
5. ✅ Bước 8 — RAG-lite lore card, cảnh báo unsaved changes, tìm/lọc Saves: **đã làm xong ở mục 5i**, chỉ còn thiếu bước Rinn tự chạy `test_engine.py` thật (mục 2 ở trên) để xác nhận nhóm test 16 PASS, vì sandbox lần đó không có mạng để cài `fastapi`.
6. ✅ **UI đẹp hơn**: Rinn đã tự làm xong (bản pastel March 7th) trước khi giao lại phần bước 0 mục 2+3 ở mục 5j.

## 5o. Cập nhật các tính năng mới theo Roadmap (22/07/2026)

1. **World Creation Interview & Checkpoint Review Wizard (Mục 1 & Giai đoạn E)**:
   - Backend: Thêm `WORLD_BUILDER_INTERVIEW_PROMPT` + 2 endpoint `/builder/interview` và `/builder/interview/respond`. Thêm bước `checkpoint_review` vào state machine sinh world và endpoint `/worlds/{world}/builder/confirm-checkpoints`.
   - Frontend: Wizard Modal 5 bước hỗ trợ phỏng vấn làm rõ ý tưởng và duyệt/sửa danh sách Checkpoint trước khi sinh Cards & Characters.

2. **Export / Import World Package (Giai đoạn G #1)**:
   - Backend: Endpoint `GET /worlds/{world}/export` và `POST /worlds/import`.
   - Frontend: Nút `📥 Import World Package` ở Sidebar và `📦 Export Package` trong Creator Mode.

3. **Mode nhập vai tương tác `interaction_mode` (Mục 0.3 #14)**:
   - Thêm field `interaction_mode` (`narrative` vs `interactive`) truyền sang Narrator Agent.
   - Frontend: Dropdown chọn mode trong Creator Mode -> World Config.

4. **World Design Assistant trong Creator Mode (Mục 0.6 #10)**:
   - Backend: Thêm `CREATOR_ASSISTANT_PROMPT` + endpoint `POST /worlds/{world}/creator-assistant`.
   - Frontend: Sub-tab mới **💡 AI Assistant** trong Creator Mode.

5. **Test Suite**:
   - Thêm các nhóm test 22, 23, 24 trong `test_engine.py`. Tất cả **24 nhóm test** đều **PASS 100%**.
