# Story Engine — Roadmap tổng hợp (cập nhật 22/07/2026)

## 0. Mục tiêu hiện tại: có bản test được sớm

Ưu tiên tuyệt đối trước khi thêm bất kỳ feature mới nào:

1. ✅ **Hoàn thiện Step 8 UI integration** (multi-save/branching) — Rinn đã tự làm xong phần UI.
2. ✅ **Fallback retry tối giản khi gặp rate-limit (429)** từ OpenRouter — retry-with-backoff + báo lỗi rõ ràng ra UI thay vì treo im lặng. Xong, xem chi tiết mục 0.1.
3. ✅ **API key UI trong Creator Mode** — nhập/lưu key + chọn model qua UI, ghi vào config runtime thay vì `.env`. Xong, xem chi tiết mục 0.1.
4. ✅ **Tự chơi thử world Xue Li / Gu Changge**, ghi lại bug/chỗ khó dùng thật — **ĐÃ ĐÓNG (05/07/2026)**. Vòng đầu ra 11 vấn đề (mục 0.3), 5 mục 🔴 đã sửa xong (mục 0.4), Rinn chơi thêm vòng 2 xác nhận ổn trong tay mình, kể cả phần lẫn ngôn ngữ (phụ thuộc model, đã cải thiện đủ dùng). Giai đoạn 0 coi như hoàn tất.

Việc tiếp theo: xem mục 0.6 — backlog mới chốt từ phiên bàn luận 05/07/2026 (turn/chapter tier, world creation resilience, checkpoint graph phi tuyến, trait system). Đây là nguồn ưu tiên chính thức từ giờ trở đi. Mục 1 đến 8 đều đã **XONG (21/07/2026)**. Các mục mới (World Creation Interview & Checkpoint Review, Export/Import World Package, interaction_mode, AI Creator Assistant) đều đã **XONG (22/07/2026)**. **Phase F (Canon Consistency Linter, Dynamic Spawn draft, Tension/Mood tags) cũng đã hoàn thành (22/07/2026)**.

---

### 0.9. Cập nhật các tính năng mới đã hoàn thành (22/07/2026)

1. ✅ **World Generation Interview & Checkpoint Review Wizard** (Mục 1 & Giai đoạn E) — **XONG (22/07/2026)**:
   - Thêm `WORLD_BUILDER_INTERVIEW_PROMPT` + 2 endpoint `/builder/interview` & `/builder/interview/respond`.
   - Bổ sung bước `checkpoint_review` vào state machine sinh world (`skeleton` -> `checkpoint_review` -> `cards` -> `characters` -> `complete`).
   - Giao diện Modal Wizard 5 bước hỗ trợ phỏng vấn làm rõ ý tưởng và cho phép người dùng xem/duyệt danh sách Checkpoint trước khi sinh Cards & Characters.

2. ✅ **Export / Import World Package** (Giai đoạn G #1) — **XONG (22/07/2026)**:
   - Endpoint `GET /worlds/{world}/export` đóng gói 4 file JSON (`world_config`, `card_registry`, `canon_timeline`, `character_state`) + `runtime_override.json` thành 1 package JSON.
   - Endpoint `POST /worlds/import` cho phép import gói thế giới thành 1 world mới.
   - UI: Nút `📥 Import World Package` ở Sidebar và `📦 Export Package` trong Creator Mode.

3. ✅ **Mode nhập vai tương tác `interaction_mode`** (Mục 0.3 #14) — **XONG (22/07/2026)**:
   - `"narrative"` (mặc định): Narrator tự do sinh diễn biến nội tâm/hành động.
   - `"interactive"`: Narrator tạm dừng khi tới lượt nhân vật chính ra quyết định và đưa gợi ý `suggested_actions`.
   - Bổ sung dropdown chọn `interaction_mode` trong Creator Mode -> World Config.

4. ✅ **World Design Assistant trong Creator Mode** (Mục 0.6 #10 & Giai đoạn G) — **XONG (22/07/2026)**:
   - Thêm `CREATOR_ASSISTANT_PROMPT` + endpoint `POST /worlds/{world}/creator-assistant`.
   - Sub-tab mới **💡 AI Assistant** trong Creator Mode hỗ trợ Creator hỏi đáp và nhận gợi ý thiết kế lore/cards/checkpoint rẽ nhánh.

5. ✅ **Test Suite Coverage**:
   - Cập nhật `test_engine.py` thêm nhóm test **22, 23, 24**. Tất cả **24 nhóm test** đều **PASS 100%**.

6. ✅ **Mở rộng Schema State & Context Tracker (Giai đoạn B)** — **XONG (22/07/2026)**:
   - Thêm `story_clock` toàn cục (ngày, thời gian trong ngày, mùa, mốc sự kiện) vào `world_config` và runtime.
   - Bổ sung cấu trúc `relationships` (quan hệ giữa các nhân vật: type, affinity, status) và `age` vào `character_state`.
   - Xây dựng schema `foreshadowings` theo dõi phục bút / Chekhov's gun (`planted_chapter`, `payoff_chapter`, trạng thái `planted` | `revealed` | `resolved`).

7. ✅ **Rule cứng & Standalone Style Card (Giai đoạn C)** — **XONG (22/07/2026)**:
   - Tách riêng cấu hình văn phong `style_card` (ngôi kể, giọng văn, nhịp độ, tone) độc lập khỏi `world_config`.
   - Cài đặt bộ lọc kỹ năng cứng bằng code Python (`backend/skill_limiter.py`) kiểm tra đối chiếu `power_stat.known_skills`, phát hiện và từ chối hành vi tự bịa skill chưa học mà không phụ thuộc vào LLM.
   - Cập nhật `test_engine.py` lên **26 nhóm test**, **PASS 100%**.

---

## 1. World Generation flow (thiết kế, đã hoàn thành 22/07/2026) — ✅ XONG

Flow đầy đủ:

1. User nhập prompt tự do — mô tả thế giới, cốt truyện, hướng mở đầu
2. Gọi API lần 1 — AI đọc, ra bản draft sơ bộ
3. **Interview loop**: AI hỏi lại những gì còn thiếu/mơ hồ (`/builder/interview`), user trả lời, lặp lại (có nút "Skip & Tạo ngay")
4. User chờ — hệ thống bắt đầu sinh dựa trên toàn bộ nội dung interview
5. Ra **checkpoint chính** (canon event chắc chắn xảy ra) dạng tóm tắt để user đọc thử
6. **User xác nhận / chỉnh sửa checkpoint** (`checkpoint_review` step)
7. Gen tiếp các phần nhỏ hơn (character, location, power system...) dựa trên checkpoint đã chốt (`/builder/confirm-checkpoints`)

---

## 2. Backlog đầy đủ — 14 hạng mục, xếp theo giai đoạn

**Giai đoạn A — Hạ tầng chịu lỗi**
- Model fallback chain theo provider (mở rộng từ mục 0.2, đầy đủ hơn: đa provider, không chỉ retry)

**Giai đoạn B — Mở rộng schema state**
- Bảng relationship/age + story_clock toàn cục
- Chekhov's gun / foreshadowing tracker (`planted_chapter` / `payoff_chapter`)

**Giai đoạn C — Rule cứng & style cố định**
- Style-card cố định (giọng văn, ngôi kể, tone) tách khỏi world_config
- Skill-limiter cứng (`power_stat.known_skills`, boundary-check không phải LLM)

**Giai đoạn D - Tách pipeline runtime (Writer + Extractor + Editor)** - ✅ **XONG 22/07/2026**
- ✅ Writer (bắt buộc) + Extractor/Logic (bắt buộc, rẽ) + Editor (tùy chọn)
- ✅ Suggested actions (field JSON có sẵn từ Writer)
- ✅ Token/cost budget hiển thị theo từng role (bỏ qua phần UI, backend đã tách)

**Giai đoạn E — Sinh nội dung mới**
- World creation interview + sinh top-down (chi tiết ở mục 1 trên)
- ~~Sliding window + running summary cho context dài~~ — chuyển lên mục 0.6 #2, đã xong 08/07/2026

**Giai đoạn F — Rủi ro cao, để cuối** — ✅ **XONG (22/07/2026)**
- ✅ Dynamic spawn NPC/địa điểm (trạng thái `draft` chờ duyệt)
- ✅ Canon consistency linter (chạy nền định kỳ, cần schema ổn định từ Giai đoạn B trước)
- ✅ Tension/mood arc theo chapter

**Giai đoạn G — Nice-to-have**
- ~~Export/import world package~~ — ✅ **XONG 22/07/2026**
- UI polish: toggle creator mode, sidebar, tách debug flag


### 0.1. Chi tiết mục 2 + 3 đã làm (cập nhật 04/07/2026)

**Retry-with-backoff cho 429 + báo lỗi rõ ràng thay vì treo im lặng:**
- `call_llm` (`backend/main.py`) giờ tự động retry tối đa 3 lần khi OpenRouter trả 429, có backoff (ưu tiên header `Retry-After` nếu có, không thì 2s/4s/8s).
- Hết lượt retry, lỗi mạng, hoặc response sai định dạng **trong lúc đã có API key thật** → raise `LLMCallError` thay vì âm thầm rơi về mock response (mock giờ CHỈ còn dùng khi hoàn toàn chưa cấu hình key nào — đúng tinh thần cũ để test/dev không tốn token).
- Narrator (agent bắt buộc): lỗi này lộ ra thành `HTTP 503` kèm message rõ nguyên nhân → frontend hiện toast cảnh báo ngay lập tức, không ghi chapter nào (tránh state nửa vời).
- Consistency checker (agent phụ, vốn đã có nguyên tắc fail-open): lỗi này **không chặn pipeline chính**, coi như `severity: "none"` nhưng `explanation` ghi rõ "[CHECKER KHÔNG CHẠY ĐƯỢC]" để không nhầm với "đã kiểm tra và thật sự ổn".
- Test: `test_engine.py` nhóm 17 (mới) — retry 429 → thành công, retry 429 hết lượt → lỗi rõ ràng, narrator lỗi thật → 503 + không ghi chapter, checker lỗi thật → fail-open + chapter vẫn tạo bình thường. Đã tự chạy, PASS toàn bộ 17 nhóm test.

**API key UI trong Creator Mode (đổi key/model không cần sửa `.env` + restart server):**
- Backend: file mới `data/runtime_config.json` (global — dùng chung mọi world, đúng bản chất cũ của biến môi trường `OPENROUTER_API_KEY`/`OPENROUTER_MODEL`) lưu key + model. 3 endpoint mới: `GET /runtime-config`, `PUT /runtime-config`, `DELETE /runtime-config/api-key`. Ưu tiên: giá trị lưu qua UI > biến môi trường `.env` (nếu UI chưa set gì thì vẫn dùng `.env` như cũ, không phá hành vi cũ).
- `GET /runtime-config` không bao giờ trả key thật dạng plain text ra ngoài, chỉ trả bản mask (vd `sk-o…abcd`) — tránh lộ key qua network log/devtools của trình duyệt.
- Frontend: sub-tab mới **🔑 API & Model** trong Creator Mode (cạnh Saves & Branches). Nhập key mới + model, nút "💾 Save key & model" (lưu ngay, không cần cơ chế "sửa rồi Lưu tất cả" như World Config/Cards/Checkpoints/Characters — giống tab Saves, không nằm trong dirty-tracking vì mỗi hành động tự lưu ngay). Nút "🗑 Clear saved key" tự disable nếu key hiện tại không phải lưu qua UI (tránh hiểu nhầm là xoá được cả key trong `.env`). Có hiệu lực ngay từ tin nhắn tiếp theo, không cần restart server hay reload trang.
- Badge "MOCK LLM" ở header world giờ trỏ thẳng tới tab mới ("set a key in Creator Mode → 🔑 API & Model") thay vì chỉ nhắc chung chung về biến môi trường.
- Test: `test_engine.py` nhóm 17 test cả 3 endpoint (set/get/xoá, mask đúng, xoá key không đụng model đã lưu riêng). Frontend: smoke-test bằng jsdom (mock `fetch`, tương tác DOM thật giống cách đã làm với tab Saves trước đây) — render đúng trạng thái MOCK/Live, gửi đúng payload khi lưu, xoá đúng, cập nhật UI ngay không cần reload. PASS toàn bộ, nhưng Rinn vẫn nên tự mở Chrome 1 lần xác nhận layout/CSS của tab mới, giống lưu ý cũ ở các tab Creator Mode khác.

Việc CHƯA làm (phát sinh khi làm mục này, không bắt buộc cho bước 0, để dành sau nếu thấy cần):
- Chưa mã hoá `runtime_config.json` trên đĩa (lưu key dạng plain text — chấp nhận được cho local app cá nhân, giống `.env` vốn cũng plain text; cần xem lại nếu sau này đóng gói chia sẻ/multi-user).
- Config hiện là global (đúng bản chất cũ của biến môi trường), chưa hỗ trợ đổi key/model riêng theo từng world — nếu Rinn cần test song song nhiều world với provider khác nhau thì đây sẽ là việc thêm sau, không phải thiếu sót của yêu cầu gốc.

### 0.3. Kết quả playtest thật world Xue Li/Gu Changge (cập nhật 04/07/2026) — 11 vấn đề + đề xuất mức ưu tiên

Rinn tự chơi ~4-5 chapter với model free `nvidia/nemotron-3-ultra-550b-a55b:free` qua OpenRouter thật (không phải mock). Danh sách dưới đây gộp toàn bộ phát hiện, xếp theo mức ưu tiên đề xuất — **thứ tự này chỉ là đề xuất, Rinn quyết định lại nếu thấy cần**, đúng nguyên tắc "ưu tiên do bug tìm được quyết định" ở cuối file.

**🔴 Ưu tiên cao — nhỏ, rẻ, giá trị ngay, nên làm đợt tới:**
1. ✅ **Toast checkpoint đè lên nút gửi/thanh nhập** — do toast `position: fixed; bottom: 22px; right: 22px` không tính chiều cao `#inputBar` (vốn nằm cuối trang theo flow bình thường, không phải fixed). Sửa: dời toast lên góc trên-phải, hoặc cộng thêm offset bằng chiều cao input bar. Xong, xem mục 0.4.
2. ✅ **`confirm()` khi tắt `alive` trong Creator Mode** — hiện là checkbox trần trong tab Characters, nằm trong nhóm dirty-tracking (phải bấm "Lưu tất cả" mới áp dụng) nhưng không có xác nhận riêng như các hành động phá hủy khác (xoá save, restore đều có `confirm()`). Cần thêm `confirm()` khi phát hiện có nhân vật chuyển alive→dead lúc Lưu. Xong, xem mục 0.4.
3. ✅ **Chặn lẫn ngôn ngữ trong output narrator** — quan sát được nhiều lần: tiếng Hàn chèn vào ("고대", "bốc lên직", "Hắn伸出 (giơ)"). Thêm luật cấm rõ ràng vào cả `NARRATOR_SYSTEM_PROMPT` và `CONSISTENCY_CHECKER_SYSTEM_PROMPT` (không phụ thuộc model, nhưng có thể giảm khi đổi model — xem mục 11). **Làm chung 1 đợt với mục 12** vì cùng đụng vào đoạn chỉ thị ngôn ngữ trong prompt — sửa 2 lần vào cùng 1 đoạn dễ giẫm lên nhau. Xong, xem mục 0.4.
4. ✅ **Retry hiện số lần thử + nút Dừng giữa chừng** — hiện retry 429 chạy hoàn toàn im lặng ở backend (có thể tốn tới ~14s không dấu hiệu gì), lỗi khác 429 thì fail ngay lần 1. Cần chuyển vòng lặp retry từ backend sang frontend tự lặp (gọi 1 API "thử 1 lần", tự đếm/hiện/`AbortController` để hủy được) để hiện tiến trình + cho phép dừng. Xong, xem mục 0.4.
11. ✅ **(MỚI) Nút "🔌 Test connection" trong tab 🔑 API & Model** — phát sinh trực tiếp từ việc Rinn vừa gặp lỗi 401 (key sai/bị từ chối) nhưng chỉ phát hiện được khi thật sự bấm Continue một chapter. Nên có nút test riêng: gọi 1 request tối thiểu (vd 1 token) ngay sau khi lưu key, báo kết quả tại chỗ (OK / 401 sai key / 402 hết credit / model không tồn tại...) thay vì phải đi vòng qua chơi thử mới biết. Tiện thể đổi ô nhập key từ `type="password"` thuần sang có icon 👁 bật/tắt hiện — vì paste vào ô ẩn không xác nhận được đã dán đúng/đủ ký tự chưa, đúng nguyên nhân nghi vấn hàng đầu của lỗi 401 vừa gặp. Xong, xem mục 0.4.

**🟡 Ưu tiên trung bình — cần thiết kế thêm, ảnh hưởng trực tiếp tới trải nghiệm chơi:**
5. ✅ **`protagonist_id` (tùy chọn, KHÔNG bắt buộc)** — **XONG (21/07/2026)**. Đã thêm `protagonist_id` vào `world_config.json`, dropdown chọn nhân vật chính trong tab World Config, badge `(you)` cho nhân vật chính trong tab Characters, bổ sung Rule 13 trong `NARRATOR_SYSTEM_PROMPT` dặn Narrator tập trung góc nhìn/nội tâm của protagonist, và endpoint `GET /play-state` hiển thị Status sidebar trong Play mode.
6. ✅ **Nút "🔄 Viết lại chương"** (regenerate) — **XONG (21/07/2026)**. Đã thêm nút 🔄 cạnh nút Continue trên thanh input. Gọi endpoint `POST /chapter/regenerate` để xoá turn cuối cùng và gen lại với cùng `user_input`. Nếu turn bị xoá đã đóng chapter, hệ thống tự khôi phục `running_summary` trước đó để tránh trùng lặp/sai lệch.
7. ✅ **`suggested_actions`** — **XONG (21/07/2026)**. Narrator trả về 1-4 gợi ý hành động ngắn gọn (Rule 14). Frontend render thành các nút bấm dạng chip ngay trên ô nhập liệu (`#suggestedActionsContainer`), bấm vào chip sẽ tự điền text vào ô nhấp (không tự gửi), và chips tự ẩn khi user chủ động gõ text.
12. ✅ **(MỚI, đã làm rõ phạm vi 04/07) "Anh hóa" mặc định: giao diện + prompt gốc là tiếng Anh, output chuyện vẫn tự nhận diện theo input** — đã rà lại toàn bộ `frontend/` (index.html/app.js/style.css): **không còn ký tự tiếng Việt nào**, giao diện đã 100% tiếng Anh sẵn, không cần sửa gì thêm ở đây. Việc còn lại là backend `prompts.py`: cả 3 prompt gốc — `WORLD_BUILDER_SYSTEM_PROMPT`, `NARRATOR_SYSTEM_PROMPT`, `CONSISTENCY_CHECKER_SYSTEM_PROMPT` — hiện đang viết bằng tiếng Việt (cả phần chỉ thị cho LLM, không chỉ phần yêu cầu ngôn ngữ output), cần dịch sang tiếng Anh làm bản mặc định. Logic tự nhận diện ngôn ngữ theo `user_input` gần nhất (giữ nguyên như đã chốt) + fallback mặc định tiếng Anh khi chưa có input/không đoán được — không đổi gì so với thiết kế cũ, chỉ đổi NGÔN NGỮ CỦA BẢN THÂN PROMPT (phần chỉ thị cho LLM) từ tiếng Việt sang tiếng Anh. **Không đụng vào comment code Python, docstring, roadmap, hay tài liệu tóm tắt dự án** — theo đúng yêu cầu, vì không ảnh hưởng trải nghiệm người dùng. Làm chung 1 đợt với mục 3 (chặn lẫn ngôn ngữ) vì cùng 1 đoạn prompt. Xong, xem mục 0.4.
13. **(MỚI) Card/Checkpoint scale khi >50 item** — hiện Characters/Checkpoints/Cards đều là danh sách dọc đơn giản, chưa tính trường hợp world lớn (nhiều nhân vật/checkpoint) sẽ kéo dài vô tận. Ý tưởng: đổi từ list thành card thật + phân loại (theo faction/arc/tag tự đặt) giống thư mục. Phạm vi UI khá lớn, Rinn tự nhận xét nên để cuối cùng — đồng ý, xếp 🟢.
14. **(MỚI, cần bàn kỹ hơn) `interaction_mode`: "narrative" (mặc định) vs "interactive"** — phát sinh từ câu hỏi lớn của Rinn về cách chapter đang vận hành: hiện narrator tự viết toàn bộ nội tâm/lời thoại/hành động của protagonist, user chỉ thỉnh thoảng chen 1 câu định hướng (kiểu "kể chuyện có định hướng"), khác với lối "nhập vai thật" (khi NPC hỏi thì narrator dừng lại, để user tự quyết protagonist nói/làm gì). Đề xuất: thêm field `world_config.interaction_mode` (mặc định `"narrative"`, giữ y nguyên hành vi hiện tại, không gò bó ai) — set `"interactive"` (yêu cầu đã có `protagonist_id` ở mục 5) thì thêm luật cho narrator: tới lượt protagonist phải phản ứng/quyết định gì thì **dừng chapter tại đó**, không tự viết hộ, để `suggested_actions` (mục 7) hoặc ô nhập của user tiếp lời. Cố tình **không** làm 2 prompt riêng biệt ("kể chuyện" vs "nhập vai") ngay từ đầu để tránh phình 2 bản phải đồng bộ tay — dùng 1 field điều kiện trong cùng 1 prompt. Chỉ hỗ trợ **1 protagonist duy nhất** (không làm multi-character/party control) để giữ scope gọn. **Cần Rinn xác nhận lại thiết kế trước khi bắt tay** — đây là thay đổi hành vi narrator lớn nhất trong list, nên bàn kỹ hơn ở đợt chuẩn bị làm, không nên coi là "chắc chắn làm y như mô tả" ngay bây giờ.
15. ✅ **(MỚI) Chapter mở đầu / "first message" — AI tự sinh hoặc user tự viết** — phát sinh từ playtest chapter 1 (cập nhật 05/07): trước giờ world mới/rỗng chỉ hiện 1 dòng text tĩnh bắt user tự gõ hành động đầu tiên vào `/chapter/continue` — không khác gì thiếu hẳn một "first message"/"greeting message" như SillyTavern/các chatbot khác, dễ khiến mốc khởi đầu bị lệch ý đồ gốc nếu không tự viết rõ ràng ngay từ đầu. Thêm endpoint mới `/chapter/start` (chỉ dùng khi world chưa có chapter nào) với đúng 2 lựa chọn Rinn đề xuất: **AI tự gen** (narrator tự viết cảnh mở đầu dựa trên mô tả checkpoint hiện tại, vẫn qua đủ boundary fallback + consistency checker như 1 chapter bình thường) hoặc **user tự chọn cách viết** (dùng nguyên văn do Rinn tự viết/dán, không qua narrator/checker, giữ đúng 100% ý). Cách cũ (tự gõ hành động đầu tiên vào ô input) vẫn còn nguyên như 1 lối thứ 3 ngầm định, không bị thay thế. **(Làm rõ thêm 05/07):** đây đúng nghĩa là "first message" kiểu SillyTavern — `opening_mode`/`opening_text` lưu ngay trong `world_config.json`, tức là **gắn liền với world** (nhập 1 lần trong Creator Mode lúc build world, không phải nhập lại mỗi lần chơi/mỗi save), và **tự động đi kèm world khi export** sau này (xem ghi chú ở Giai đoạn G, mục 2) vì không phải state riêng theo save/branch. Đổi luôn chữ trong UI (panel bắt đầu truyện + Creator Mode) sang "first message" cho khớp thuật ngữ Rinn quen dùng — tên field JSON trong code (`opening_mode`/`opening_text`) giữ nguyên để không phá test/tương thích ngược, chỉ đổi phần hiển thị cho người dùng. Xong, xem mục 0.5.

**🟢 Ưu tiên thấp hơn — giá trị thật nhưng phạm vi lớn hơn, nên làm sau khi 2 nhóm trên ổn:**
8. **Style-card riêng theo world** (giọng văn/tone tách khỏi `world_config`) — trùng đúng mục **Giai đoạn C** đã có sẵn trong roadmap gốc, không phải phát sinh mới.
9. **Chapter cũ gập lại thành tóm tắt + chọn/lật chương** — feed đang chơi (chapter mới nhất) giữ nguyên kiểu cuộn liên tục (đã chốt, không đổi), chỉ chapter đã "đóng" (qua checkpoint mới) mới gập lại + có mục lục lật qua lại. Cần thiết kế UI mới, phạm vi lớn hơn các mục còn lại trong nhóm 🟡.
10. **Spinner không xoay khi bật "reduce motion"/performance mode** — Rinn xác nhận là do tự bật tắt hiệu ứng để mượt máy, không phải bug. Giữ trong list nhưng hạ thấp nhất: có thể tách riêng `.spinner` (báo trạng thái thật) khỏi rule tắt hiệu ứng trang trí chung, nhưng tuỳ Rinn — không cần nếu Rinn thấy ổn với hiện trạng.

**Ghi chú vận hành (không phải bug code, không nằm trong list trên):** lỗi `401 Unauthorized` gặp phải khi test là do OpenRouter từ chối xác thực key (khác hẳn 429 rate-limit — hệ thống retry mới ở mục 0.1 **đúng ý thiết kế không retry 401**, vì retry key sai vô ích). Đã soát lại `call_llm`, phần build header `Authorization: Bearer {key}` không có bug. Nhiều khả năng là key copy thiếu/dán nhầm/bị revoke — xác minh bằng cách gọi thẳng OpenRouter qua `curl` để tách vấn đề key khỏi vấn đề app trước khi kết luận là bug.

---

### 0.4. Chi tiết 5 mục 🔴 đã làm xong (cập nhật 05/07/2026)

**1. Toast dời lên góc trên-phải + tự xếp chồng không đè nhau:**
- `.toast` đổi từ `bottom: 22px` sang `top: 22px` (vùng này không có gì fixed khác, không còn bị `#inputBar` đè lên như cũ).
- Bonus nhỏ phát hiện khi sửa: trước đây nếu 2 toast hiện cùng lúc (vd checkpoint mới + cảnh báo RAG-lite) sẽ **chồng lên nhau** vì cùng 1 toạ độ cố định. Giờ mỗi toast tự tính `top` dựa trên chiều cao các toast phía trước nó (hàm `positionToasts()` trong `app.js`, gọi lại mỗi khi thêm/xoá 1 toast) — không cần đổi cách gọi `showToast()` ở bất kỳ đâu khác.

**2. `confirm()` khi tắt `alive` trong tab Characters:**
- Mỗi hàng nhân vật giờ ghi nhớ trạng thái `alive` gốc + có phải nhân vật đã tồn tại từ trước hay không, ngay lúc dựng form.
- Lúc bấm "Lưu tất cả": nếu phát hiện **nhân vật đã tồn tại và đang alive** bị chuyển sang `alive: false`, hiện `confirm()` liệt kê rõ tên, bấm Cancel thì huỷ lưu hoàn toàn (không gọi API). Nhân vật **mới thêm** đặt `alive: false` ngay từ đầu thì không bị hỏi (không phải "chuyển sang chết", mà là tạo mới đã chết).

**3 + 12. Prompts.py dịch sang tiếng Anh làm mặc định + chặn lẫn ngôn ngữ:**
- Dịch nguyên văn cả 3 system prompt (`WORLD_BUILDER_SYSTEM_PROMPT`, `NARRATOR_SYSTEM_PROMPT`, `CONSISTENCY_CHECKER_SYSTEM_PROMPT`) sang tiếng Anh, giữ nguyên số thứ tự luật/field/schema JSON — chỉ đổi ngôn ngữ chỉ thị, không đổi logic. Comment Python (docstring đầu file) vẫn giữ tiếng Việt như yêu cầu.
- `NARRATOR_SYSTEM_PROMPT`: luật ngôn ngữ cũ ("viết bằng tiếng Việt" cứng) đổi thành rule 7 — viết `chapter_text` theo đúng ngôn ngữ của `user_input` gần nhất, mặc định tiếng Anh nếu rỗng/không đoán được — và thêm rule 8 cấm rõ việc trộn ngôn ngữ giữa chừng 1 chapter.
- `CONSISTENCY_CHECKER_SYSTEM_PROMPT`: thêm rule 6 — nếu phát hiện `chapter_text` bị lẫn ngôn ngữ thì phải báo issue (mặc định `severity: "minor"`, chỉ lên `"major"` nếu lẫn nặng tới mức khó đọc).
- Đây là thay đổi ở tầng chỉ thị cho LLM — mức độ giảm hẳn phụ thuộc vào model đang dùng có tuân lệnh tốt hay không (model free hay bỏ qua rule hơn model trả phí), Rinn nên playtest lại 1-2 chapter để xem model hiện tại (`nvidia/nemotron-3-ultra-550b-a55b:free`) có cải thiện rõ không.

**4. Vòng lặp retry 429 chuyển hẳn ra frontend, hiện tiến trình + nút Dừng:**
- Backend (`call_llm`): bỏ hẳn vòng lặp tự `sleep`/retry cũ — giờ **chỉ thử 1 lần**, gặp 429 thì raise `RateLimitError` (subclass của `LLMCallError` cũ, không phá chỗ fail-open của consistency checker) kèm `retry_after` lấy từ header `Retry-After` thật của provider nếu có, `None` nếu không có.
- `chapter_continue`: khi narrator gặp `RateLimitError` → trả **`HTTP 429` thật** (khác với lỗi LLM khác vẫn là `503` như cũ) kèm `detail: {message, retry_after}`. Không ghi chapter nào (giữ nguyên nguyên tắc cũ).
- Frontend (`sendChapter`): tự lặp lại tối đa 3 lần khi gặp 429, hiện thanh trạng thái ngay trên ô nhập ("⏳ Rate-limited... retrying in Ns... (attempt X/3)") với thời gian đếm ngược lấy từ `retry_after` của backend nếu có, không thì dùng backoff cố định 2s/4s/8s. Có nút "⏹ Stop" dùng `AbortController` để huỷ giữa chừng — input của Rinn không bị mất, thử lại được ngay.
- **11. Nút "🔌 Test connection" + toggle 👁 hiện/ẩn key** (làm chung đợt vì cùng đụng `runtime-config`/API & Model tab):
  - Backend: hàm `test_llm_connection()` + endpoint `POST /runtime-config/test-connection` — gọi 1 request tối thiểu (`max_tokens: 1`) bằng key/model **đang lưu hiệu lực**, phân loại rõ kết quả: `ok` / `no_key` / `unauthorized` (401) / `no_credit` (402) / `rate_limited` (429) / `model_not_found` (404 hoặc 400 kèm message nhắc tới model) / `provider_error` (còn lại). Luôn trả `HTTP 200` — bản thân kết quả test mới là `ok: true/false`, không phải lỗi request.
  - Frontend: nút "🔌 Test connection" cạnh "💾 Save key & model" trong tab 🔑 API & Model, hiện kết quả ngay dưới dạng hộp text (không chỉ toast, để không tự biến mất). Ô nhập key giờ có icon 👁/🙈 bật/tắt hiện chữ.

**Test:**
- `test_engine.py` nhóm 17 (viết lại toàn bộ 17d–17i): 429 chỉ thử 1 lần + `retry_after` đúng từ header/`None` khi thiếu, `chapter_continue` trả đúng `429` (không phải `503`) kèm `retry_after`, lỗi LLM khác 429 vẫn `503` như cũ, checker fail-open vẫn đúng, và 5 kịch bản của `POST /runtime-config/test-connection`. Đã tự chạy, **PASS toàn bộ**.
- Frontend: smoke-test bằng jsdom (mock `fetch`/`confirm`, tương tác DOM + `selectWorld()`/sub-tab click thật như luồng thật) — 27 assertion cho cả 5 mục (stacking toast, confirm khi giết nhân vật cũ/không hỏi với nhân vật mới, `apiFetch` tách đúng `retry_after`, toggle hiện key, nút test connection hiện đúng kết quả, và trọn vòng lặp retry 429 + bấm Dừng giữa chừng). Đã tự chạy, **PASS toàn bộ**, không giữ lại làm file chính thức trong project (giống cách làm cũ ở mục 0.1 — chỉ để tự kiểm tra trước khi giao).

**Việc CHƯA làm / cần Rinn tự xác nhận:**
- Chưa mở Chrome thật để xem layout CSS mới (thanh retry-status, nút test connection, icon 👁) trên trình duyệt thật — jsdom chỉ xác nhận đúng hành vi DOM/JS, không xác nhận đẹp/lệch layout.
- Việc dịch prompt sang tiếng Anh **không đảm bảo hết hẳn** lỗi lẫn ngôn ngữ — vẫn phụ thuộc độ tuân lệnh của model đang dùng, cần Rinn playtest thêm để đánh giá mức cải thiện thật.
- Mục 4 roadmap gốc ("Tự chơi thử...") vẫn đang ở trạng thái 🟨 — 5 việc trên chỉ là fix theo feedback playtest đã có, chưa phải một vòng playtest MỚI để xác nhận các fix này thật sự ổn trong tay Rinn.

---

### 0.5. Chi tiết mục 15 đã làm xong (cập nhật 05/07/2026) — Chapter mở đầu (opening)

**Vấn đề phát hiện:** Rinn playtest chapter 1 world demo, nhận ra world mới/rỗng không có gì tương đương "greeting message" — `ChapterContinueRequest.user_input` luôn bắt buộc, không có nhánh riêng cho "chưa có chapter nào", nên chapter 1 thực chất là do Rinn tự gõ tay hành động đầu tiên rồi mới đưa qua narrator, không phải app tự sinh ra gì. Grep cả roadmap lẫn file tóm tắt dự án lúc đó đều không có chữ nào về "greeting"/"opening"/"chapter 0" — xác nhận đây là khoảng trống thiết kế thật, không phải bug bị bỏ sót. Rinn đề xuất đúng 2 hướng: để AI tự gen, hoặc để user tự chọn cách viết/tự viết chương mở đầu.

**Backend (`main.py`):**
- Tách phần thân dùng chung của pipeline (build payload → gọi narrator → boundary fallback → consistency checker → merge state → save chapter → advance checkpoint) ra hàm riêng `_generate_chapter(world_name, narrator_input, display_input=None)`. `/chapter/continue` giờ chỉ còn là 1 dòng gọi lại hàm này — không đổi hành vi cũ, đã chạy lại toàn bộ test cũ (nhóm 1–17) xác nhận PASS 100%, không có regression từ việc tách hàm.
- `narrator_input` (text thật sự gửi cho narrator LLM) và `display_input` (text lưu vào `chapter_record["user_input"]`, hiện lên UI dạng "▸ ...") được tách riêng — lý do: chế độ `ai_generate` cần gửi 1 câu instruction hệ thống cho narrator nhưng KHÔNG được hiện câu đó lên UI như thể user vừa tự gõ (`display_input` truyền `""`, frontend vốn đã có sẵn logic ẩn khung "▸ ..." khi `user_input` rỗng — không cần sửa gì thêm ở đó).
- Endpoint mới `POST /worlds/{world_name}/chapter/start` — **chỉ dùng được khi `chapters.json` còn rỗng** (gọi lại khi đã có chapter → `400`, nhắc dùng `/chapter/continue`). Nhận `opening_mode` + `opening_text` optional trong request (ghi đè riêng cho lần gọi này); không truyền gì thì lấy mặc định từ `world_config.opening_mode`/`opening_text` (Creator set sẵn qua Creator Mode, xem phần Frontend bên dưới).
  - `ai_generate` (mặc định): helper mới `build_opening_instruction(checkpoint)` soạn 1 câu instruction dựa trên `checkpoint["description"]` của checkpoint hiện tại (`current_checkpoint_id`, thường là `cp_0`), gửi qua `_generate_chapter(..., display_input="")` — chạy đủ pipeline thật (boundary + consistency checker) như 1 chapter bình thường, không tắt bớt bước kiểm tra nào.
  - `user_defined`: ghi thẳng `opening_text` thành `chapter_text` của chapter 1, **không gọi narrator/checker** — giữ đúng 100% văn bản Rinn tự viết/dán, không tốn API call. `consistency_check` đánh dấu `severity: "none"` kèm giải thích rõ là bỏ qua kiểm tra vì không qua narrator (để không nhầm với "đã kiểm tra và ổn").
  - Thiếu `opening_text` khi `opening_mode` là `user_defined` (cả request lẫn `world_config` đều rỗng) → `400` rõ ràng, không âm thầm tạo chapter rỗng. `opening_mode` sai giá trị (không phải 2 giá trị hợp lệ) → `400` ở cả `PUT world_config` lẫn `POST chapter/start`.
- `world_config` có thêm 2 field mới: `opening_mode` (mặc định `"ai_generate"`) + `opening_text` (mặc định `""`) — thêm vào cả `TEMPLATES` (world tạo mới từ đầu) và `seed-demo` (world demo Xue Li/Gu Changge), world cũ chưa có 2 field này khi đọc qua `world_config.get(...)` vẫn tự rơi về mặc định `ai_generate`, không cần migrate dữ liệu cũ.

**Frontend:**
- `renderChapters([])` không còn hiện dòng text tĩnh cũ ("Type your character's first move...") mà hiện panel "bắt đầu truyện" với 2 lựa chọn: nút "✨ Let AI write the opening" và textarea + nút "📝 Use this as chapter 1". Vẫn còn 1 dòng ghi chú nhỏ nhắc lối cũ (tự gõ hành động đầu tiên vào ô input bên dưới) vẫn hoạt động bình thường — không bớt lựa chọn nào Rinn đang quen dùng.
- Tách vòng lặp retry-429 (vốn nằm cứng trong `sendChapter()`) thành hàm dùng chung `postWithChapterRetry(url, body)`, để nút "Let AI write the opening"/"Use this as chapter 1" (hàm mới `startStory()`) thừa hưởng y hệt hành vi retry/đếm ngược/nút Dừng của `/chapter/continue`, không phải viết lại logic riêng.
- `handleChapterError()` nhận thêm tham số `actionLabel` (mặc định `"continue chapter"`) để toast lỗi mô tả đúng hành động vừa thất bại — `startStory()` truyền `"start the story"` thay vì luôn nói "continue".
- Creator Mode → tab World Config: thêm 2 field `opening_mode` (dropdown) + `opening_text` (textarea) để Rinn set sẵn mặc định cho world (vd viết sẵn 1 đoạn mở đầu ưng ý trong lúc build world, không cần gõ lại lúc bắt đầu chơi thật). Nằm trong nhóm `dirty-tracked` sẵn có của World Config, không cần cơ chế lưu riêng.

**Test:**
- `test_engine.py` nhóm 18 (7 case, 15 assertion): mặc định `opening_mode`/`opening_text` đúng khi seed-demo; `ai_generate` gọi narrator với instruction có nhắc tới mô tả checkpoint nhưng `user_input` lưu lại rỗng; gọi `/chapter/start` lần 2 khi đã có chapter → `400`; `user_defined` **không gọi narrator/checker lần nào** và giữ nguyên 100% text; thiếu `opening_text` → `400`; `opening_mode` sai → `400` ở cả `PUT world_config` lẫn `chapter/start`; Creator set sẵn qua `world_config` thì gọi `chapter/start` không cần truyền gì vẫn dùng đúng giá trị đã set. Đã tự chạy, **PASS toàn bộ 18 nhóm** (17 nhóm cũ + nhóm mới), không có regression.
- Frontend: smoke-test bằng jsdom (mock `fetch`, dựng lại đúng DOM thật từ `index.html`) — 15 assertion: panel hiện đúng 2 lựa chọn khi 0 chapter, textarea rỗng thì chặn + toast trước khi gọi API, nút AI generate gửi đúng `opening_mode: "ai_generate"` và không hiện khung "▸ ..." (vì `display_input` rỗng), nút tự viết gửi đúng `opening_mode: "user_defined"` kèm đúng text đã gõ, panel biến mất + chapter mới hiện đúng trong feed sau khi thành công. Đã tự chạy, **PASS toàn bộ 15/15**, không giữ lại làm file chính thức trong project (đúng cách làm cũ ở mục 0.1/0.4).

**Việc CHƯA làm / giới hạn đã biết:**
- `build_opening_instruction()` viết cứng câu instruction bằng tiếng Việt (vì world demo hiện tại toàn bộ tiếng Việt, và rule 7 của `NARRATOR_SYSTEM_PROMPT` chọn ngôn ngữ output theo ngôn ngữ của `user_input` gửi cho narrator). Nếu sau này Rinn tạo 1 world tiếng Anh và dùng `ai_generate`, cảnh mở đầu nhiều khả năng vẫn ra tiếng Việt do câu instruction này — chưa làm tự nhận diện ngôn ngữ theo `checkpoint.description`. Cố tình để dành, theo đúng nguyên tắc "ưu tiên do bug tìm được quyết định" — chưa đáng làm cho 1 world duy nhất hiện có.
- Chưa mở Chrome thật để xem layout CSS thật của panel mới (2 cột option cạnh nhau, responsive khi màn hẹp) — jsdom chỉ xác nhận đúng hành vi DOM/JS, không xác nhận đẹp/lệch layout.
- Rinn nên tự tạo 1 world mới thật sự rỗng (không phải seed-demo có sẵn `cp_0`) và thử cả 2 luồng `ai_generate`/`user_defined` bằng tay ít nhất 1 lần, xác nhận trải nghiệm thật khớp đúng ý trước khi coi mục này là đóng hẳn.

**Làm rõ thêm (05/07) — "first message" gắn liền với world, không phải state riêng:**
- `opening_mode`/`opening_text` nằm ngay trong `world_config.json` — **cùng 1 file với các field cốt lõi khác của world** (`genre`, `fixed_rules`, `current_checkpoint_id`...), không phải file/bảng riêng, không đi theo save/branch (khác `chapters.json`/`character_state.json`, vốn có bản riêng theo từng save qua cơ chế snapshot bước 8). Tức là: nhập 1 lần trong Creator Mode lúc build world → dùng chung cho **mọi save/branch** của world đó, đúng bản chất "first message" kiểu character card SillyTavern (thuộc về nhân vật/world, không thuộc về 1 phiên chat cụ thể).
- Hệ quả trực tiếp cho **Giai đoạn G — Export/import world package** (mục 2, chưa làm): vì đã nằm sẵn trong `world_config.json`, feature export sau này **không cần thêm bước riêng nào** để gồm first message — export nguyên `world_config.json` là tự động kèm theo. Đã ghi chú thẳng vào dòng backlog tương ứng ở mục 2 để không bị quên khi tới lượt làm Giai đoạn G.
- Đổi chữ hiển thị trong UI (panel bắt đầu truyện: "Let AI write the first message" / "Use this as the first message"; Creator Mode: nhãn field nhắc rõ "SillyTavern-style greeting") sang thuật ngữ "first message" cho khớp cách Rinn quen gọi. **Không đổi tên field JSON `opening_mode`/`opening_text` trong code/API** — chỉ đổi phần chữ hiển thị cho người dùng, để không phải sửa lại test đã PASS (nhóm 18) hay risk gõ sai tên field ở đâu đó.

---

### 0.6. Backlog mới chốt từ phiên bàn luận 05/07/2026 (turn/chapter tier, world creation resilience, checkpoint graph phi tuyến, trait system)

Phát sinh từ lo ngại gốc của Rinn: chất lượng nội dung tự gen (world/card/checkpoint) là "tim dự án", cộng thêm vấn đề chapter phình to/dị khi tương tác dày trên free-tier. Bàn rộng ra thành 1 cụm thay đổi liên quan tới nhau. **Thứ tự dưới đây có ràng buộc phụ thuộc thật, không tuỳ ý đảo** — đặc biệt mục 6 (trait) phải xong trước mục 7 (checkpoint graph), vì fork/trial dùng trait làm điều kiện.

**🔴 Làm ngay tiếp theo — trực tiếp phục vụ chất lượng novel + token, không đụng kiến trúc lớn:**

1. ✅ **Tầng Turn/Chapter** — **XONG (07/07/2026)**. hiện `_generate_chapter` coi 1 lần gọi narrator = 1 `chapter_record` luôn, gây 2 cực đoan: tương tác nhỏ dồn thành chapter feed vụn vặt như nhật ký, hoặc ép narrator viết dài mỗi turn tốn token/dễ 429. Tách 2 khái niệm:
   - **Turn**: 1 lần gọi narrator, đoạn ngắn, đánh `turn_index` **reset về #1 mỗi khi sang chapter mới** (không cộng dồn toàn world) — mục đích để Rinn dễ trỏ tay khi cần regenerate 1 đoạn cụ thể.
   - **Chapter**: gom nhiều turn, đóng theo ngưỡng mềm (số turn/số từ) hoặc narrator tự đánh flag `chapter_end` (có ngưỡng cứng làm rào an toàn phòng model free-tier đoán sai nhịp). Feed hiển thị header chương thật ("Chương N — ...") khi qua ranh giới, các turn trong cùng chương chảy liền không ngắt khối.
   - **Checkpoint giữ nguyên là Arc** (không đổi gì, không cần phân cấp thêm — 4-8 checkpoint/world hiện tại đã đúng cỡ 1 arc; demo world chỉ để bắt bug, world thật sẽ do world-builder tự gen nên chưa cần lo phân cấp checkpoint trước khi có dữ liệu thật).
   - ⚠️ Cần soát lại `build_save_entry`/snapshot (bước 8) vì đang đếm `chapter_count` theo `len(chapters.json["chapters"])` — đổi cấu trúc turn-trong-chapter thì hàm này phải sửa theo, không tự khớp.
   - **Cách làm thật (khác 1 chi tiết so với bản nháp trên):** `chapters.json` **giữ nguyên list phẳng** `{"chapters": [...]}` thay vì lồng `turns` bên trong từng chapter — mỗi phần tử trong list giờ là 1 TURN record, thêm 3 field mới `turn_index`, `chapter_closed`, `chapter_title` (chỉ có giá trị khi turn đó đóng chapter của nó). Cách này ít phải sửa code đọc file khác, và **tương thích ngược 100% với world cũ**: data cũ thiếu field `chapter_closed` được code coi mặc định là `True` (đã đóng) → turn tiếp theo tự bắt đầu chapter mới, đúng y hệt hành vi cũ (mỗi turn cũ vốn là 1 chapter riêng) — không cần viết migration script.
   - Ngưỡng đã chốt: `CHAPTER_SOFT_CLOSE_TURNS=5`, `CHAPTER_SOFT_CLOSE_WORDS=900`, `CHAPTER_HARD_CLOSE_TURNS=8` (hằng số ở đầu main.py, dễ chỉnh sau khi có dữ liệu chơi thật).
   - `recent_chapters_for_context` (lấy `[-3:]` theo CHAPTER) đổi thành `get_recent_turns_for_context()` lấy 5 TURN gần nhất (flatten, không gom theo chapter) — payload gửi narrator đổi key `recent_chapters` → `recent_turns`. Đây cũng là bước dọn đường nhẹ cho mục 2 (sliding window) sắp tới.
   - `build_save_entry` đã soát lại như cảnh báo: `chapter_count` giờ = `chapter_index` của turn cuối cùng (không còn `len(list)`), thêm `turn_count` riêng = tổng số turn. Với world cũ 2 cách tính cho cùng kết quả nên không lệch số khi đọc save cũ.
   - Frontend: 1 chapter giờ render thành 1 khối `.chapter-card` duy nhất chứa nhiều `.turn-block` chảy liền bên trong (chỉ 1 header "Chapter N" mỗi chapter, có ranh giới dashed nhẹ giữa các turn cùng chương để dễ phân biệt mà không tách card).
   - Test: `test_engine.py` nhóm 19 (7 test con) — phần "sliding window nén chapter cũ thành summary" thuộc mục 2, xem nhóm 20.

2. ✅ **Sliding window + running summary cho context** — **XONG (08/07/2026)**. `get_recent_turns_for_context` (mục 1) vẫn rớt hoàn toàn mọi thứ trước cửa sổ turn thô — story càng dài narrator càng "quên" chapter cũ. 2 quyết định của Rinn (chốt qua lựa chọn nhanh trước khi code):
   - **Cách tóm tắt: LLM tóm tắt riêng** (không phải rule-based) — agent thứ 3 `SUMMARIZER_SYSTEM_PROMPT` (`prompts.py`), chạy **CHỈ khi 1 chapter vừa đóng lại**, nhận `previous_summary` (rỗng ở lần đầu) + toàn văn chapter vừa đóng (gộp mọi turn cùng `chapter_index`, đúng thứ tự `turn_index`) → trả về **1 summary MỚI đã tích hợp**, không phải nối chuỗi vô hạn (prompt yêu cầu tự nén mạnh hơn phần cũ khi thêm phần mới, giữ ~100-250 từ bất kể truyện dài bao nhiêu chapter).
   - **Cửa sổ turn nguyên văn: giảm còn 2** — `RECENT_TURNS_CONTEXT_LIMIT` 5 → 2 (hằng số đầu `main.py`).
   - **Lưu trữ**: `running_summary` (string) nằm ở **cấp top-level của `chapters.json`**, ngang hàng `"chapters"` — tự động được snapshot theo save/branch giống 4 file JSON còn lại của world, không cần sửa `build_save_entry`. World cũ thiếu field này đọc `.get("running_summary", "")` mặc định rỗng, không cần migrate.
   - **Fail-open giống hệt consistency checker**: lỗi gọi summarizer (rate-limit, mạng, JSON sai định dạng) → giữ nguyên `running_summary` cũ, **không** chặn/làm hỏng chapter vừa sinh (chapter đó đã lưu thành công rồi, đây chỉ là bước làm giàu context cho lần continue kế tiếp).
   - `running_summary` được đưa vào **cả 2 nơi**: (1) payload gửi narrator (`base_payload["running_summary"]`, kèm rule 12 mới trong `NARRATOR_SYSTEM_PROMPT` dặn narrator dùng làm bối cảnh nền, không trích nguyên văn), và (2) `build_rag_context_text` (để RAG-lite chọn lore card không bị mất độ chính xác do cửa sổ thô co lại 5→2).
   - ⚠️ **Giới hạn đã biết**: nếu 1 chapter đang MỞ tích luỹ nhiều turn (tối đa `CHAPTER_HARD_CLOSE_TURNS=8` trước khi bị ép đóng), các turn Ở GIỮA (vượt quá cửa sổ 2 turn nhưng chapter đó chưa đóng nên summarizer chưa chạy) tạm thời không nằm trong cả cửa sổ thô lẫn running_summary — có thể mất vài chi tiết giữa chừng cho tới khi chapter đó đóng lại. Chấp nhận đánh đổi này ở bản đầu (đơn giản, để playtest quyết định bước tiếp theo) thay vì làm cửa sổ "giới hạn ranh giới chapter đang mở (phức tạp hơn, chưa có dữ liệu thực tế để biết có đáng làm không).
   - Test: `test_engine.py` nhóm 20 (13 test con) — cover mock/parse fail-open, nội dung payload gửi summarizer, thứ tự gọi (chỉ gọi khi đóng chapter), fail-open không chặn chapter, và running_summary có mặt đúng trong payload narrator.

3. ✅ **Tách Settings (API key/Model) ra khỏi Creator Mode** — **XONG (21/07/2026)**. 2 thứ khác bản chất: cấu hình vận hành (không spoil gì, nên luôn truy cập được) vs công cụ GM thật (sửa card/checkpoint/state, cần khoá). Đã tạo mục **⚙️ Settings** riêng (mode-tab thứ 3 khi có world mở + nút riêng ở sidebar khi chưa mở world nào), chỉ chứa API & Model — nhân tiện đã tách luôn key mặc định toàn app vs key override riêng theo từng world (ưu tiên: world override > app default > .env). Chi tiết đầy đủ xem mục 5n trong `story-engine-tom-tat-du-an.md`.

4. ✅ **Khoá Creator Mode qua config file, không qua UI toggle** — **XONG**. Thêm `creator_mode_enabled: false` (mặc định) vào `data/runtime_config.json`, chỉ gate quyền vào tab Creator Mode **lúc đang PLAY** một world đã có tiến trình. World creation wizard (mục 1, luồng tạo world mới) **luôn mở bất kể flag này** — vì lúc đó user đang là tác giả quyết định nội dung, không phải xem trước tương lai của 1 playthrough đang chơi dở nên không có gì để spoil. Người dùng phổ thông muốn bật phải tự sửa file JSON, tránh nghịch UI vô tình.

**🟡 Tiếp theo — nền tảng, nên xong trước khi đụng checkpoint graph:**

5. ✅ **World-builder chunking + `creation_status` resumable** — **XONG**. Hiện `WORLD_BUILDER_SYSTEM_PROMPT` sinh world_config+cards+checkpoints+characters trong 1 lần gọi duy nhất; bot chết/lỗi giữa chừng là mất trắng. Chia thành nhiều lần gọi nhỏ theo section (skeleton → cards → characters chi tiết), ghi `creation_status` xuống đĩa sau mỗi bước hoàn thành. World có `creation_status != "complete"` không hiện trong danh sách Play, chỉ hiện nút "Tiếp tục tạo".

6. ✅ **Scope selector lúc tạo world + khả năng extend arc sau** — **XONG**. Thêm field cấu hình riêng (không lẫn vào ô prompt tự do) cho độ dài mong muốn: **One-shot** (~2-3 checkpoint, kết trọn) / **Arc mở đầu** (mặc định, 4-8 checkpoint, để ngỏ) / **Ongoing** (nhịp chậm, chủ đích không kết ở arc đầu). Dù chọn gì, 1 lần gọi world-builder vẫn chỉ sinh 1 cụm checkpoint gần (không phình size theo scope, tránh tăng rủi ro đứt gãy) — khác biệt nằm ở field text mới `narrative_scope_note` (định hướng nhịp/tông cho AI, dùng lại làm ngữ cảnh khi gọi world-builder ở quy mô nhỏ để **gen thêm arc tiếp theo** lúc truyện gần chạm checkpoint cuối).

7. ✅ **`trait_definitions` + `titles` + `status_effects`** (mở rộng Giai đoạn B) — **XONG (21/07/2026)**:
   - `trait_definitions` trong `world_config`: khai báo trước tập trait khả dụng + giá trị hợp lệ (như `power_system`/`realm` đã làm) — narrator KHÔNG được tự bịa tên trait mới nếu trait đó sẽ dùng làm điều kiện fork/trial. Trait "màu mè" không ảnh hưởng logic có thể để tự do, nhưng không được dùng trong `required_conditions`.
   - `character_state` thêm `traits: {}` (mutable, set/xoá tự do qua `state_changes.traits_set` / `traits_clear` — khác `knowledge_flags` chỉ cộng thêm).
   - `titles`: danh hiệu `exclusive: true` (kiểu "Ma Vương") — khai báo trong `world_config`, code tự tước khỏi chủ cũ khi gán cho người mới, không phụ thuộc LLM nhớ tự xoá.
   - `status_effects`: hiệu ứng có thời hạn (kiểu "Peter suy sụp N turn sau khi chú Ben mất) — gắn thẳng vào checkpoint gây ra (checkpoint tự apply khi advance, giống `realm_updates`), hết hạn do code tự đếm/tự xoá, KHÔNG giao cho LLM tự nhớ.
   - ⚠️ **`CONSISTENCY_CHECKER_SYSTEM_PROMPT` phải cập nhật cùng đợt** — thêm `trait_definitions`/`titles` vào canon data checker nhận, dạy nó biết bắt lỗi kiểu "trait ngoài enum đã khai báo" / "2 nhân vật cùng giữ title exclusive". Không cập nhật cùng lúc thì checker sẽ không phát hiện được gì ở vùng dữ liệu mới này dù có vẻ như "đã kiểm tra".

**🟢 Sau cùng trong nhóm core logic — thay đổi kiến trúc lớn nhất, phụ thuộc mục 7:**

8. ✅ **Checkpoint graph phi tuyến** (mở rộng Giai đoạn F) — **XONG (21/07/2026)**. `checkpoints` hiện là list tuyến tính, "tiếp theo" luôn là checkpoint kế trong list. Thêm:
   - **`alternate_outcomes`**: `{condition, next_checkpoint_id}` mỗi checkpoint — check bằng code y hệt `required_conditions`, nhưng đánh giá trước khi advance mặc định. Bad-end/fork **phải do tác giả khai báo trước lúc tạo world** (world-builder gen cùng chất lượng với checkpoint chính, cards của nó locked tự động qua cơ chế `unlock_checkpoint_id` sẵn có — không cần field "bad end" riêng). **Không để engine/narrator tự phát sinh nhánh runtime** — chất lượng chắc chắn thua checkpoint được soạn sẵn.
   - **Checkpoint kiểu "trial"**: đánh giá pass/fail ngay tại thời điểm đối đầu bằng stat hiện có (khác "threshold" chờ đủ điều kiện không giới hạn thời gian) — dùng lại đúng `required_conditions`/`>=`.
   - **Stall budget**: đếm `turns_since_checkpoint_entered` (code thuần), checkpoint khai `stall_limit` (optional) — hết ngân sách thì tự đóng theo outcome đã định trước (fail-branch nhẹ hoặc mặc định tuỳ thể loại), không cố ép user.
   - **Giới hạn nudge (soft-pull mở rộng)**: thêm lớp check mới **"checkpoint-pull"** (khác boundary hiện tại) — so state_changes với `required_conditions` của checkpoint kế tiếp, không chỉ boundary. Tối đa 1-2 lần nudge tự nhiên (narrator viết lý do trong truyện); từ chối tiếp thì **chấp nhận lựa chọn của user là thật**, chuyển thành outcome/fork thật (không ép nudge vô hạn gây gượng gạo).

**⚪ Giai đoạn G — nice-to-have, làm khi rảnh hoặc bỏ qua cũng được:**

9. ✅ **Panel bên (sidebar toggle dạng segment, ẩn mặc định)** — **XONG (21/07/2026)**. chỉ số nhân vật chính (tên + tag nhỏ, KHÔNG avatar), card đã mở kèm affinity, thanh tiến độ arc. Đã tạo endpoint `GET /worlds/{world_name}/play-state` đọc riêng cho Play mode (chỉ trả phần đã unlock), kết hợp với segment toggle `[Story | Status]` ở header Play Mode và sidebar phía bên phải.
10. **"World design assistant" (chatbot tư vấn thiết kế world)** — opt-in, chạy trong Creator Mode lúc thiết kế/bí ý tưởng fork, KHÔNG chạy trong hot path mỗi turn (tránh đội thêm chi phí/lượt chơi).

---

## 1. World Generation flow (thiết kế, làm sau vòng test đầu)

Flow đầy đủ:

1. User nhập prompt tự do — mô tả thế giới, cốt truyện, hướng mở đầu
2. Gọi API lần 1 — AI đọc, ra bản draft sơ bộ
3. **Interview loop**: AI hỏi lại những gì còn thiếu/mơ hồ, user trả lời, lặp lại
   - Điều kiện dừng: AI tự tin thì tự dừng, **cộng thêm** nút "Đủ rồi, tạo luôn" để user chủ động cắt bất cứ lúc nào (không hard-cap số câu)
4. User chờ — hệ thống bắt đầu sinh dựa trên toàn bộ nội dung interview
   - **Cần progress indicator theo bước** ("đang sinh checkpoint 2/5", "đang tạo nhân vật chính"...), không phải spinner trơn — đây là chỗ tốn thời gian nhất trong app
5. Ra **checkpoint chính** (canon event chắc chắn xảy ra) dạng tóm tắt để user đọc thử
6. **User xác nhận / chỉnh sửa checkpoint**:
   - Nếu không ưng: AI sửa lại theo yêu cầu, **hoặc** user sửa tay trực tiếp
   - AI gen tiếp các bước sau dựa trên **bản đã sửa** (dù AI sửa hay user sửa tay) — **trách nhiệm về tính nhất quán của bản sửa tay thuộc về user**, hệ thống không tự validate lại nội dung tự do user gõ vào
7. Gen tiếp các phần nhỏ hơn (character, location, power system...) dựa trên checkpoint đã chốt

**Mapping theo số model user cấu hình** (tùy setting, co giãn 1–3 con):
- **1 model**: làm hết toàn bộ chuỗi draft → interview → checkpoint → detail gen, tuần tự
- **2 model**: 1 con lo phần sáng tạo (draft, hỏi, viết checkpoint dạng văn xuôi cho user đọc), 1 con lo structured data (convert checkpoint đã duyệt thành JSON cho card_registry/checkpoint engine)
- **3 model**: thêm Editor polish văn phong checkpoint trước khi show cho user ở bước 5

Ghi chú: world demo hiện tại (Xue Li / Gu Changge) **không cần** chạy qua flow này — flow này chỉ áp dụng khi tạo world mới từ đầu.

---

## 2. Backlog đầy đủ — 14 hạng mục, xếp theo giai đoạn

**Giai đoạn A — Hạ tầng chịu lỗi**
- Model fallback chain theo provider (mở rộng từ mục 0.2, đầy đủ hơn: đa provider, không chỉ retry)

**Giai đoạn B — Mở rộng schema state** — ✅ **XONG (22/07/2026)**
- Bảng relationship/age + story_clock toàn cục
- Chekhov's gun / foreshadowing tracker (`planted_chapter` / `payoff_chapter`)

**Giai đoạn C — Rule cứng & style cố định** — ✅ **XONG (22/07/2026)**
- Style-card cố định (giọng văn, ngôi kể, tone) tách khỏi world_config
- Skill-limiter cứng (`power_stat.known_skills`, boundary-check không phải LLM)

**Giai đoạn D - Tách pipeline runtime (Writer + Extractor + Editor)** - ✅ **XONG 22/07/2026**
- ✅ Writer (bắt buộc) + Extractor/Logic (bắt buộc, rẽ) + Editor (tùy chọn)
- ✅ Suggested actions (field JSON có sẵn từ Writer)
- ✅ Token/cost budget hiển thị theo từng role (bỏ qua phần UI, backend đã tách)

**Giai đoạn E — Sinh nội dung mới**
- World creation interview + sinh top-down (chi tiết ở mục 1 trên)
- ~~Sliding window + running summary cho context dài~~ — chuyển lên mục 0.6 #2, đã xong 08/07/2026

**Giai đoạn F — Rủi ro cao, để cuối** — ✅ **XONG (22/07/2026)**
- ✅ Dynamic spawn NPC/địa điểm (trạng thái `draft` chờ duyệt)
- ✅ Canon consistency linter (chạy nền định kỳ, cần schema ổn định từ Giai đoạn B trước)
- ✅ Tension/mood arc theo chapter

**Giai đoạn G — Nice-to-have**
- Export/import world package (chia sẻ độc lập với save-state) — **lưu ý (05/07, từ mục 15/0.5):** "first message" (`opening_mode`/`opening_text`) đã nằm sẵn trong `world_config.json` ngay từ đầu, không phải state riêng theo save/branch → khi làm export, chỉ cần export nguyên `world_config.json` là tự động kèm theo, không cần thêm bước copy riêng nào.
- UI polish: toggle creator mode, sidebar, tách debug flag (boundary/consistency) ra khỏi story feed thành panel riêng

---

## Nguyên tắc chọn việc tiếp theo

Sau khi qua giai đoạn 0 (test sớm), **thứ tự thực tế không cố định theo lý thuyết** — ưu tiên do bug tìm được quyết định. Ví dụ:
- AI hay quên relationship/tuổi → đẩy Giai đoạn B lên trước
- Context tràn sau vài chapter → đẩy sliding window (Giai đoạn E) lên trước
- AI phá boundary hay bịa skill → đẩy Giai đoạn C lên trước

---

### 0.7. Các update UI/UX nhỏ (21/07/2026)

Các tính năng sau đã được hoàn thiện dựa trên phản hồi để tăng tính tiện dụng:
- ✅ **Nút Regenerate**: Thêm nút Regenerate cho phép tạo lại lượt (turn) mới nhất, tích hợp trực tiếp cạnh nút gửi và gọi API với tuỳ chọn ẩn lượt cũ.
- ✅ **Gợi ý hành động (Suggested actions)**: Hiển thị dạng thẻ (chips) nằm phía trên thanh input để người chơi có thể click chọn nhanh, giao diện có hiệu ứng glassmorphism. Sẽ tự động ẩn đi nếu người chơi bắt đầu gõ văn bản tùy chỉnh.
- ✅ **Tag Nhân vật chính**: Thêm tag "(you)" nhỏ cạnh tên nhân vật trong tab Characters đối với nhân vật được đánh dấu là `protagonist_id`, giúp dễ dàng phân biệt.

### 0.8. Hotfix Mismatch Data & UI Crash (21/07/2026)

- ✅ **Sửa lỗi crash giao diện:** Đã gỡ bỏ dấu escape thừa (\"\) trong file app.js gây lỗi cú pháp (SyntaxError).
- ✅ **Đồng bộ Key API Checkpoint:** Đã sửa hàm advance_checkpoint_if_ready trong backend (main.py) trả về đúng key to_checkpoint_id và cards_unlocked (kèm to_checkpoint_description) theo đúng chuẩn mà UI và Test Suite đang dùng.
- 💡 **Bài học kinh nghiệm:**
  - **Frontend:** Tuyệt đối cẩn thận khi gõ hoặc sinh code JS có chứa nháy kép (double quotes), tránh để sót các dấu backslash (\) không hợp lệ gây lỗi parse khiến toàn bộ file script chết.
  - **Backend API & Testing:** Khi refactor thay đổi schema field (ở đây là tính năng checkpoint phi tuyến), cần tìm toàn bộ project (grep) để đổi đồng bộ ở cả Backend, Frontend (cách đọc res.checkpoint_advanced) và Test Suite. Đừng quá tin vào claim 'Test PASS' nếu chưa tự verify lại trên code mới nhất.
