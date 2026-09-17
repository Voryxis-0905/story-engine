# Story Engine — New System Design v2: Living World, Influence & Endgame
### (Mở rộng chi tiết từ bản gốc — đã đối chiếu với codebase thực tế, sẵn sàng giao agent)

**✅ Done - 2026-08-01: Cụm A — mở rộng eval_condition hỗ trợ world_flags.* (state_manager.py:56-67)**

✅ Done - 2026-08-01: Cụm A — xác nhận đã có sẵn trong code, không cần sửa (state_manager.py:65-73)

✅ Done - 2026-08-01: Cụm B — Living World Thread (world_events.py + tick_world_events tích hợp vào chapter_generator.py sau dòng 1380)

✅ Done - 2026-08-01: Cụm C — Mode Endless/Có hồi kết (thêm story_mode, target_ending_scenario, lifecycle_status, world_flags vào world_config template; mở rộng sanitize_required_conditions hỗ trợ story_clock.* và world_flags.*; thêm tick_endgame() và tích hợp vào chapter_generator.py sau advance_checkpoint_if_ready)

Tài liệu này mở rộng `story-engine-new-system-design.md` (v1). Mục tiêu: mỗi mục đủ chi tiết để giao thẳng cho agent code mà không cần hỏi lại — có schema JSON cụ thể, điểm tích hợp vào file/hàm thực tế, luồng xử lý từng bước, edge case, và acceptance criteria. Phần đối chiếu codebase (Mục 9) là phần quan trọng nhất — nó chỉ ra 3 chỗ giả định trong bản gốc **không khớp** với code hiện tại, cần chốt hướng trước khi viết workorder.

---

## 0. Vấn đề gốc cần giải quyết

*(giữ nguyên từ v1)*

Kiến trúc checkpoint hiện tại buộc main phải "dính" đúng vị trí/hành động để sự kiện được phép xảy ra — khi main lệch hướng, AI phải bịa chướng ngại (hộ vệ chặn đường...) để kéo về. Hướng thiết kế mới: tách sự kiện cốt truyện ra khỏi việc bắt buộc có mặt của main, biến giới hạn từ "cấm đoán vô hình" thành "luật chơi minh bạch" (map chưa mở khóa) + "hệ quả thật" (world tự trôi, có thể bỏ lỡ).

**Nguyên tắc thiết kế xuyên suốt cho mọi mục dưới đây:** ưu tiên tối đa việc tái dùng field/hàm đã có (`story_clock`, `required_conditions`, `eval_condition`, `world_canon_store`, `power_stat`, `relationships`) thay vì generate ra hệ thống song song. Chỉ thêm field mới khi thật sự không có cách map vào cái cũ.

---

## 1. Map System — giới hạn minh bạch thay cho boundary vô hình

### 1.1 Trạng thái thực tế (đã implement, không phải thiết kế mới)

Đã có đầy đủ:
- `checkpoint_engine.py::generate_location_map()` — sinh `location_map.json` bằng LLM qua `LOCATION_MAP_GENERATOR_PROMPT`, được gọi tự động cuối flow world creation (`builder_routes.py`, sau khi `creation_status = "complete"`).
- `checkpoint_engine.py::check_map_based_restrictions()` — chặn di chuyển tới location chưa đủ điều kiện.
- Route đọc: `GET /worlds/{world_name}/location_map` (`world_routes.py::get_world_location_map`).
- Dữ liệu thật đã tồn tại ở `data/worlds/HORROR/location_map.json`, `test_engine_world_branch/`, `test_engine_empty_world/`.

### 1.2 Schema thực tế (khác với mô tả ở v1 — xem Mục 9.1)

```json
{
  "locations": [
    {
      "id": "loc_start_village",
      "name": "Whispering Village",
      "description": "A quiet village at the edge of the known world",
      "x": 20.0,
      "y": 30.0,
      "zone": "Frontier Lands",
      "unlock_realm": null,
      "unlock_exp": 0,
      "unlock_checkpoint_id": null,
      "is_starting_location": true,
      "connected_to": ["loc_old_forest", "loc_north_road"],
      "tags": ["safe", "settlement"]
    }
  ]
}
```

Không có field `unlocked` (bool) hay `unlock_condition` (field-path kiểu `required_conditions`) như v1 mô tả. Điều kiện mở khóa là 3 field cứng: `unlock_realm` (so khớp `power_stat.realm`), `unlock_exp` (so `power_stat.exp`), `unlock_checkpoint_id` (so `world_config.completed_checkpoints`). Đây là thiết kế **đơn giản hơn nhưng đủ dùng** — không cần đổi sang field-path generic, vì location chỉ cần gate theo 3 trục này (không giống checkpoint có thể gate theo bất kỳ field nào của nhân vật).

`x`, `y` được clamp `[0, 100]` khi generate (`checkpoint_engine.py` dòng ~539-540).

### 1.3 Việc còn thiếu (frontend + polish, phần cần giao agent)

- [x] Tab **Map** ở frontend (chưa thấy render trong `app.js` — cần audit lại để xác nhận, nhưng theo BRIEFING mẫu trong `.agents/` chưa có tab Map được nhắc tới ở M4). Hiển thị node theo `x/y` trên canvas/SVG 100x100, scale theo container.
- [x] Location chưa đạt `unlock_realm`/`unlock_exp`/`unlock_checkpoint_id` → hiển thị mờ + icon khóa (fog of war). So khớp điều kiện dùng đúng logic `_get_location_unlock_requirements()` — không viết lại ở frontend, gọi qua 1 endpoint mới trả về trạng thái unlock đã tính sẵn (tránh đồng bộ logic 2 nơi).
- [x] Vẽ line nối theo `connected_to` giữa các node.
- [x] Click node hiển thị `description`, `zone`, `tags`, và điều kiện mở khóa còn thiếu (vd "Cần đạt Kim Đan Cảnh" / "Cần hoàn thành checkpoint X").
- [x] **Endpoint mới cần thêm**: `GET /worlds/{world_name}/location_map/status` — trả về `location_map.locations` đã enrich thêm field `is_unlocked: bool` và `unlock_reason_missing: str | null` tính sẵn ở backend (tái dùng `_get_location_unlock_requirements` + `character_state` của main). Tránh để frontend tự tính lại điều kiện unlock (single source of truth).

✅ Done - 2026-08-01: Cụm D — Map frontend polish (endpoint status + LocationMap.tsx + PlayPage.tsx)

### 1.4 Acceptance criteria

- World mới tạo luôn có `location_map.json` với ≥1 location có `is_starting_location: true`.
- Di chuyển tới location chưa unlock → bị `check_map_based_restrictions` chặn (đã có, chỉ cần test lại không regress).
- Tab Map hiển thị đúng trạng thái khóa/mở, không gọi LLM lúc render (chỉ đọc `location_map.json` + `character_state.json` đã cache).

---

## 2. Checkpoint Philosophy — main tự nguyện, không bị giam

### 2.1 Trạng thái thực tế

Xác nhận: `WORLD_BUILDER_SKELETON_PROMPT` (`prompts.py`) đã có rule về (a) checkpoint là mục tiêu có động lực nội tại, (b) zone-prefixed naming (`"Estate - Kitchen"`). Đây là rule ở tầng **prompt cho LLM lúc world-building**, không phải logic code — nghĩa là chất lượng phụ thuộc vào LLM tuân thủ đúng rule, không có validator cứng kiểm tra sau khi sinh.

### 2.2 Việc cần làm thêm (gap thật, không phải đã xong)

Vì đây là prompt-level rule không có enforcement, cần 1 lớp kiểm tra nhẹ sau khi world-builder sinh checkpoint chain (chạy trong `builder_routes.py`, cùng chỗ với `sanitize_required_conditions`):

- [x] **Heuristic linter cho checkpoint description** (không cần LLM, string-match đơn giản): cảnh báo (log warning, không block) nếu `boundary.description` hoặc `description` chứa các cụm cố định kiểu "không thể rời", "bị giam", "buộc phải ở lại", "lính gác chặn" (danh sách từ khóa tiếng Việt + Anh tương đương) — đây là dấu hiệu checkpoint đang được viết theo kiểu "lồng" thay vì "mục tiêu tự nguyện". Không tự sửa (risk sai ngữ cảnh), chỉ log để người review soát lại lúc creation.
- [x] Đảm bảo mọi location trong `boundary.locations` của 1 checkpoint đều cùng zone-prefix (kiểm tra bằng cách so `location.split(" - ")[0]` giữa các location trong cùng checkpoint) — cảnh báo nếu lệch zone mà không có lý do rõ (di chuyển liên khu vực hợp lý cần qua `location_map.connected_to`, không phải tùy tiện).

**Ghi chú 2026-08-01 (Cụm E):** phần linter heuristic description đã có sẵn trong `builder_routes.py` (block `forced_phrases`, ~dòng 347-366). Cụm E bổ sung `backend/app/services/validators.py` với 3 hàm deterministic, không gọi LLM:
- `validate_location_map()` — `connected_to` trỏ đến id tồn tại, không self-reference, `unlock_exp >= 0`, `unlock_realm`/`unlock_checkpoint_id` là str/null, có ≥ 1 location `is_starting_location: true`. (Lưu ý: schema thật dùng `unlock_realm`/`unlock_exp`/`unlock_checkpoint_id` + `is_starting_location`, KHÔNG phải `unlock_requires` như bản nháp — xem Mục 9.1.)
- `checkpoint_linter()` — không trùng `checkpoint_id`, `boundary.locations` trỏ đến location tồn tại (match theo name/id), `cards_unlocked` trỏ đến card id tồn tại, `default_next_checkpoint_id` trỏ đến checkpoint tồn tại, `required_conditions` có `field`/`op`/`value` hợp lệ và field base là character tồn tại (hoặc prefix `story_clock.`/`world_flags.`). (Lưu ý: `required_conditions` thật là list dict `{field, op, value}`, không phải string `"type:value"`; checkpoint dùng `checkpoint_id`/`description`, không có field `chapter` → rule "chapter liền mạch" và `story_beats` không áp dụng với canon_timeline hiện tại.)
- `validate_world_bundle()` — gộp 2 hàm trên + `character_state.characters` cấu trúc + nếu `story_mode == "fixed_ending"` thì `target_ending_scenario` phải có `summary` + `endgame_conditions`.

Tích hợp: gọi `validate_world_bundle()` ở cuối phase `characters` của `world_builder_step` (sau khi `location_map` được generate + save) và cuối `extend_arc` (sau khi append checkpoint mới). Lỗi được **log warning + trả trong response field `lint_errors`** (không raise/chặn flow — vì AI-sinh không bao giờ hoàn hảo, giống pattern `sanitize_required_conditions` hiện tại).

### 2.3 Acceptance criteria

- Linter chạy không lỗi, không chặn creation (chỉ cảnh báo).
- Có log/report xuất ra cho người review xem sau khi tạo world mới (tương tự cách `sanitize_required_conditions` đang report `removed_any`).

---

## 3. Luồng nhân quả nền (Living World Thread)

Đây là mục **cần thiết kế mới hoàn toàn** — chưa có gì tương đương trong code hiện tại ngoài `story_clock` (đếm turn/ngày) và `open_threads` (ghi chú narrative thread dạng text tự do, không có state machine).

### 3.1 Data model mới: `world_events.json` (per world, file mới)

```json
{
  "events": [
    {
      "event_id": "evt_bandit_raid_westvillage",
      "title": "Băng cướp tấn công làng Tây",
      "status": "pending",
      "trigger_conditions": [
        {"field": "story_clock.tick", "op": ">=", "value": 12}
      ],
      "outcomes": [
        {
          "outcome_id": "raid_succeeds",
          "condition": {"field": "world_flags.village_defense_alerted", "op": "!=", "value": true},
          "canon_facts_add": [
            "Băng cướp Hắc Lang đã cướp phá làng Tây, đốt 1/3 số nhà, giết trưởng làng cũ."
          ],
          "world_flags_set": {"village_west_raided": true},
          "location_effects": [
            {"location_id": "loc_west_village", "tags_add": ["ruined"], "tags_remove": ["safe"]}
          ]
        },
        {
          "outcome_id": "raid_repelled",
          "condition": {"field": "world_flags.village_defense_alerted", "op": "==", "value": true},
          "canon_facts_add": [
            "Làng Tây đã kịp chuẩn bị phòng thủ và đẩy lui băng cướp Hắc Lang."
          ],
          "world_flags_set": {"village_west_raided": false}
        }
      ],
      "resolved_outcome_id": null,
      "resolved_at_tick": null
    }
  ]
}
```

Điểm thiết kế quan trọng:
- `trigger_conditions` và `outcome.condition` dùng **đúng cấu trúc** `{field, op, value}` / `{all:[...]}` / `{any:[...]}` mà `state_manager.py::eval_condition()` đã hỗ trợ — không tạo cú pháp điều kiện mới.
- **Vấn đề cần giải quyết trước khi code (xem Mục 9.2)**: `eval_condition` hiện chỉ resolve được field bắt đầu bằng `story_clock.` (đọc từ `world_config`) hoặc field dạng `char_id.xxx` (đọc từ `character_state`). Nó **không** biết đọc `world_flags.xxx` hay field tự do khác của `world_config`. Cần mở rộng `eval_condition` thêm 1 nhánh: field bắt đầu bằng `world_flags.` → đọc từ `world_config.get("world_flags", {})`. Đây là thay đổi bắt buộc, nhỏ, không phá vỡ logic cũ (thêm branch mới, các branch cũ giữ nguyên).
- `world_flags` là dict phẳng mới trong `world_config.json` (giống `completed_checkpoints`, `sub_beats_progress` đã có) — nơi lưu boolean/số liệu nền do event nền set ra, tách biệt với `character_state` (vì đây là fact về *thế giới*, không phải về 1 nhân vật cụ thể).

### 3.2 Luồng xử lý (deterministic tick — không gọi LLM)

Chạy **sau** mỗi lần `advance_checkpoint_if_ready()` được gọi trong `chapter_generator.py` (cùng điểm với nơi `story_clock` được cập nhật, dòng ~1380), thêm bước mới `tick_world_events()`:

```
tick_world_events(world_events, world_config, character_state):
    for event in world_events.events where status == "pending":
        if eval_condition(event.trigger_conditions as {"all": trigger_conditions}, character_state, world_config):
            # chọn outcome đầu tiên có condition == true, mặc định outcome cuối nếu không outcome nào match
            outcome = pick_matching_outcome(event.outcomes, character_state, world_config)
            event.status = "resolved"
            event.resolved_outcome_id = outcome.outcome_id
            event.resolved_at_tick = world_config.story_clock.tick
            # ghi fact vào world_canon_store — QUAN TRỌNG: statement là prose có sẵn
            # trong outcome.canon_facts_add, KHÔNG cần LLM viết lại (tiết kiệm token, đúng yêu cầu v1 mục 3)
            append_facts_to_canon(world_canon_store, outcome.canon_facts_add, source="world_event:" + event.event_id)
            apply world_flags_set to world_config.world_flags
            apply location_effects to location_map.json (tags_add/remove) nếu có
    return list of newly-resolved event_ids  # để log / hiện thông báo nếu cần
```

- Đây là **hàm thuần deterministic**, không LLM, chi phí gần như 0 token — đúng tinh thần "chạy nền không cần LLM viết prose mỗi tick" của v1.
- `pick_matching_outcome`: duyệt `event.outcomes` theo thứ tự, trả outcome đầu tiên có `condition` = true (hoặc không có `condition` → luôn match, dùng cho outcome mặc định/fallback — nên đặt outcome không-condition ở cuối danh sách).

### 3.3 Lazy generation — chỉ sinh prose khi main thật sự chạm vào

Không sinh narrative text lúc event resolve ở nền. Việc "main chạm vào" nghĩa là: main di chuyển tới 1 `location_id` có trong `event.outcomes[].location_effects[].location_id`, HOẶC main tương tác với NPC liên quan (field mới, tùy chọn: `event.outcomes[].related_character_ids`).

Khi đó, planner (writer stage trong `chapter_generator.py`) cần biết fact này để tham chiếu tự nhiên — cách tích hợp: facts đã ghi vào `world_canon_store` qua `append_facts_to_canon` **tự động** được planner đọc, vì `chapter_generator.py` dòng ~1203 đã build `world_canon_facts` từ toàn bộ `merged_canon.get("facts", [])` để đưa vào context planner. **Không cần thêm cơ chế mới ở bước này** — chỉ cần đảm bảo fact được ghi đúng lúc trigger, phần còn lại tự động chạy qua pipeline facts-injection sẵn có.

### 3.4 Main có thể bỏ lỡ vĩnh viễn

Vì `tick_world_events` chạy độc lập theo `story_clock.tick`/điều kiện — nếu main không bao giờ set được `world_flags.village_defense_alerted = true` trước khi `story_clock.tick >= 12`, outcome `raid_succeeds` xảy ra vĩnh viễn, không có cơ chế "chờ main". Đây **là** hành vi mong muốn (đúng yêu cầu v1), không phải bug — cần ghi rõ trong workorder để agent không tự ý thêm logic "đợi player" (dễ bị agent "sửa" nhầm thành chờ vì tưởng là thiếu điều kiện).

### 3.5 Nguồn tạo `world_events.json`

Sinh lúc world creation (cùng bước với `generate_location_map`), qua 1 prompt mới `WORLD_EVENTS_GENERATOR_PROMPT` — input tương tự `LOCATION_MAP_GENERATOR_PROMPT` (world_config, checkpoints, characters) + thêm `location_map.locations` đã sinh trước đó (để event có thể tham chiếu đúng `location_id` thật). Sinh 3-8 sự kiện nền tùy độ dài world dự kiến. Không bắt buộc — nếu LLM không sinh được / lỗi, world vẫn hoạt động bình thường không có living world thread (giống cách `generate_location_map` fail-soft trả `{"locations": []}`).

### 3.6 Acceptance criteria

- `eval_condition` hỗ trợ `world_flags.*` mà không phá test cũ (`test_engine.py` phải PASS 100%, thêm test mới cho branch `world_flags`).
- `tick_world_events` chạy sau mỗi turn, không gọi LLM, không tăng latency đáng kể (<50ms cho world events thông thường).
- Fact ghi vào `world_canon_store` bởi event nền phải xuất hiện trong context planner ở turn kế tiếp sau khi resolve (test bằng cách assert `world_canon_facts` chứa statement mới sau khi trigger).
- Event đã `resolved` không bao giờ trigger lại (idempotent).

---

## 4. Quest Board (toggle on/off lúc tạo world)

### 4.1 Config

Thêm `quest_board_enabled: bool` vào `world_config.json`, đặt cạnh `pacing_level`/`output_length` trong form tạo world (frontend `renderConfigTab`/world creation wizard) — validate trong `commit_sanitizer.py::validate_world_config` giống cách `pacing_level` đang được validate (thêm dòng check `isinstance(data.get("quest_board_enabled"), bool)` nếu có mặt field).

### 4.2 Cơ chế: quest board = view layer của `world_events.pending`, không phải hệ thống riêng

Khi `quest_board_enabled = true`, mỗi `world_event` có `status: "pending"` **và** đã có ít nhất 1 dấu hiệu main có thể biết tới nó (xem 4.3) được hiển thị như 1 quest gợi ý optional:

```json
{
  "quest_id": "evt_bandit_raid_westvillage",   // = event_id, không tạo ID riêng
  "title": "Điều tra tin đồn cướp bóc ở làng Tây",  // hint text, KHÁC canon title (tránh spoil outcome thật)
  "hint": "Có tin đồn một băng cướp đang nhắm tới làng Tây.",
  "location_hint": "loc_west_village",
  "deadline_tick": 12  // = trigger_conditions story_clock.tick nếu có, để UI hiện đếm ngược mờ (không lộ số chính xác nếu muốn giữ bí ẩn — tùy chọn UI)
}
```

- `title`/`hint` là bản rút gọn **không tiết lộ outcome**, cần field riêng trong `world_events.json` (thêm `quest_hint_title`, `quest_hint_text` vào mỗi event khi generate) — KHÔNG tái dùng `event.title` (title đó có thể chứa spoiler như "Băng cướp tấn công làng Tây" đã khẳng định kết quả).
- Đây chính là "bản nâng cấp của `suggested_actions`" theo đúng nhận định ở v1 — cụ thể: khi world có quest board bật, planner có thể (tùy chọn, không bắt buộc) sinh 1 `suggested_action` liên quan tới quest đang active, tái dùng field `suggested_actions` đã có trong output planner (`prompts.py` dòng 555), không cần thêm field JSON mới ở tầng chapter turn.

### 4.3 Điều kiện hiển thị quest lên board

Quest chỉ hiện khi main đã "biết" về nó — tránh lộ hết mọi event nền ngay từ đầu game (phá vỡ cảm giác khám phá). Cách đơn giản nhất, tái dùng field có sẵn: quest hiện khi `event_id` xuất hiện trong `open_threads` (tức đã được planner nhắc tới qua lời đồn/NPC nào đó trong 1 turn) HOẶC field mới `event.discoverable_from_start: bool` = true (cho các event môi trường ai cũng biết ngay từ đầu, không cần "phát hiện").

### 4.4 Endpoint mới
✅ Done - 2026-08-01: `GET /worlds/{world_name}/quest_board` — trả list quest hiện tại theo logic 4.3, chỉ khi `quest_board_enabled = true` (404/empty nếu tắt).

### 4.5 Acceptance criteria

- Toggle tắt → endpoint trả rỗng, không tính toán thừa.
- Quest hint không chứa outcome text thật (review thủ công vài world mẫu, không có cách tự động kiểm chặt).
- Main lơ quest hoàn toàn → event nền vẫn resolve đúng lịch (không phụ thuộc quest board bật/tắt — quest board thuần là hiển thị).

---

## 5. Narrative Influence — EXPERIMENTAL, mặc định TẮT

*(giữ nguyên quyết định từ v1, bổ sung chi tiết kỹ thuật khi cần bật)*

### 5.1 Mặc định: không code gì thêm

Đúng như v1 — climax/epilogue đọc trực tiếp `character_state.characters[*].relationships` và `affinity` đã có sẵn (đã được `commit_sanitizer.py::validate_character_state` validate là dict bắt buộc). Prompt cho climax/epilogue agent cần 1 rule rõ: "xác định nhân vật/phe nào quan trọng nhất với main dựa trên `relationships` (số lượng tương tác, `affinity` cao/thấp cực trị) và `open_threads` liên quan tới họ — không có field điểm số nào khác để tham chiếu."

### 5.2 Toggle experimental (không ưu tiên code — chỉ ghi schema dự phòng để không phải thiết kế lại từ đầu nếu sau này cần)

Nếu bật `narrative_influence_enabled = true` trong tương lai: thêm `character_state.characters[*].narrative_influence: dict[faction_id, int]` — tăng/giảm qua `state_changes.characters[*].influence_delta` (theo pattern y hệt `affinity_delta`/`karma_delta` đã có trong `prompts.py` dòng 371). **Không code phần này ngay** — chỉ giữ chỗ để không phải re-design.

### 5.3 Acceptance criteria (chỉ áp dụng nếu Mục 5.2 được kích hoạt sau này)

- Không áp dụng ở phase hiện tại — Mục 5 không nằm trong scope workorder đầu tiên.

---

## 6. Kết thúc câu chuyện — chia theo MODE

### 6.1 Config: chọn mode lúc tạo world

Thêm `story_mode: "endless" | "fixed_ending"` vào `world_config.json`, validate trong `commit_sanitizer.py`. Mặc định `"endless"` (tương thích ngược 100% — world cũ không có field này coi như endless).

### 6.2 Mode "Endless"

Không cần thay đổi code — đây là hành vi hiện tại (chạy tới khi main chết qua `character_state.characters[*].alive = false`, hoặc người chơi tự dừng). Chỉ cần đảm bảo UI không hiện bất kỳ progress-tới-ending nào khi mode này được chọn.

### 6.3 Mode "Có hồi kết"

#### 6.3.1 Schema `target_ending_scenario` — sinh song song với checkpoint chain lúc world creation

Thêm vào `world_config.json`:

```json
{
  "story_mode": "fixed_ending",
  "target_ending_scenario": {
    "summary": "Main dẫn dắt liên minh các môn phái đánh bại Ma Giáo, thống nhất võ lâm.",
    "endgame_conditions": [
      {"field": "world_flags.ma_giao_defeated", "op": "==", "value": true}
    ],
    "endgame_conditions_logic": "any",
    "fallback_summary": "Nếu main không đủ mạnh/không tham gia trận cuối, Ma Giáo thắng và thế giới rơi vào loạn lạc — epilogue vẫn sinh dựa trên relationships main đã xây.",
    "status": "pending"
  }
}
```

- `endgame_conditions`: **dùng đúng cấu trúc `{field, op, value}`** như `eval_condition` đã hỗ trợ (sau khi mở rộng thêm nhánh `world_flags.` ở Mục 3.1/9.2). Điều kiện có thể tham chiếu `story_clock.*`, `world_flags.*`, hoặc `character_id.power_stat.realm` như checkpoint condition thường — tái dùng 100% engine cũ, không viết eval riêng cho endgame.
- **⚠️ Bắt buộc theo đúng yêu cầu v1**: `endgame_conditions` phải chạy qua `sanitize_required_conditions` (hoặc bản mở rộng của nó, xem 6.3.3) ngay sau khi world creation xong — pattern y hệt cách checkpoint conditions đang được sanitize ở `builder_routes.py` dòng ~310-322.
- `fallback_summary`: bắt buộc có — vì Mode "Có hồi kết" không được phép treo vô thời hạn nếu main không bao giờ đạt điều kiện (xem 6.3.4, cơ chế timeout).

#### 6.3.2 world_flags cho endgame

Endgame condition dựa trên `world_flags` (Mục 3.1) — nghĩa là **Living World Thread (Mục 3) là nền tảng bắt buộc phải code trước Mục 6.3**, đúng thứ tự ưu tiên v1 đã đề xuất ở "Việc cần làm tiếp theo". `world_flags.ma_giao_defeated` có thể được set bởi 1 `world_event` outcome (Mục 3) khi main đánh bại boss cuối trong 1 chapter, qua `state_changes` mới cần thêm 1 field: `world_flags_set: dict` trong output của writer/extractor stage (`prompts.py` — thêm vào phần state_changes schema, tương tự cách `story_clock_delta` đã được thêm).

#### 6.3.3 Sanitizer dùng chung

Mở rộng `checkpoint_engine.py::sanitize_required_conditions()` thành hàm tổng quát hơn `sanitize_conditions(conditions: list, character_state: dict, world_config: dict) -> dict` chấp nhận thêm field bắt đầu bằng `story_clock.` và `world_flags.` (hiện tại hàm chỉ check field dạng `char_id.xxx` tồn tại trong `character_state`, xem code dòng 218-251 — cần thêm 2 nhánh early-return valid=True cho 2 prefix này tương tự cách `eval_condition` đã phân nhánh). Áp dụng cho cả `checkpoint.required_conditions` (dùng lại) VÀ `target_ending_scenario.endgame_conditions` (dùng mới) — 1 hàm, 2 nơi gọi.

#### 6.3.4 Endgame check chạy như 1 phần của tick nền

Thêm vào cùng điểm gọi `tick_world_events()` (Mục 3.2, sau mỗi turn): nếu `world_config.story_mode == "fixed_ending"` và `target_ending_scenario.status == "pending"`, eval `endgame_conditions` theo `endgame_conditions_logic` (`"all"` hoặc `"any"`, default `"all"`) bằng `eval_condition`. Nếu true → set `target_ending_scenario.status = "ready"` (chưa phải "completed" — chờ người chơi xác nhận, xem 6.3.5).

**Timeout an toàn** (field mới, để tránh treo vĩnh viễn nếu điều kiện không bao giờ đạt): tùy chọn `target_ending_scenario.timeout_tick` — nếu `story_clock.tick` vượt mốc này mà `status` vẫn `"pending"`, tự chuyển `status = "ready"` với flag `used_fallback: true`, epilogue sẽ dùng `fallback_summary` thay vì `summary`. Không bắt buộc set — nếu không set, world có thể chạy vô thời hạn ở chế độ chờ (chấp nhận được, vì đây là lựa chọn của người tạo world).

#### 6.3.5 Luồng "Endgame Pending" → epilogue
✅ Done - 2026-08-01: endpoints `GET /chapter/endgame-status`, `POST /chapter/generate-epilogue-choices`, `POST /chapter/generate-epilogue`

```
status: pending → ready → (người chơi xác nhận muốn kết thúc, không tự động) → choices_made → completed
```

- Khi `status = "ready"`: frontend hiện banner "Endgame Pending" (không tự nhảy epilogue — người chơi có thể chơi thêm vài turn trước khi chốt, đúng tinh thần "người chơi luôn là mắt xích cuối cùng" của v1).
- Người chơi bấm "Kết thúc câu chuyện" → 1 loạt lựa chọn biểu tượng cuối cùng (sinh bởi LLM dựa trên `target_ending_scenario.summary` hoặc `fallback_summary` + `relationships` hiện tại — prompt mới `EPILOGUE_CHOICES_PROMPT`, output dạng `suggested_actions`-like: 2-4 lựa chọn ngắn).
- Người chơi chọn 1 → gọi prompt mới `EPILOGUE_GENERATOR_PROMPT`, input: lựa chọn đã chọn + toàn bộ `relationships`/`affinity` các nhân vật + `running_summary` + `target_ending_scenario` — **không** truyền `narrative_influence` (không tồn tại ở default). Output tôn trọng `output_length` đã có (Concise/Standard/Detailed), dùng đúng cơ chế length hiện có trong writer stage.
- Sau epilogue: `world_config.status = "completed"` (field `status` ở world_config root, khác `target_ending_scenario.status` — cần đặt tên rõ tránh nhầm, đề xuất đổi tên field world-level thành `world_config.lifecycle_status` để tránh đụng namespace nếu `status` đã dùng cho việc khác — **cần kiểm tra lại xem `world_config.json` đã có field `status` chưa trước khi đặt tên, tránh conflict**). Route Continue/chapter-generate phải check field này và trả lỗi rõ ràng (không phải lỗi chung chung) nếu world đã `completed`.

### 6.4 Acceptance criteria

- `endgame_conditions` không bao giờ trigger nếu field path không resolve được — verify qua sanitizer, không phải qua "chơi thử và hy vọng nó không trigger nhầm" (đúng yêu cầu tránh bug field-ma của v1).
- Endgame check không tốn thêm lệnh gọi LLM (chạy chung batch deterministic với `tick_world_events`).
- World `story_mode: "endless"` hoàn toàn không bị ảnh hưởng bởi code Mục 6 (early-return ngay đầu hàm check nếu không phải `fixed_ending`).
- Epilogue tôn trọng `output_length`, không hardcode độ dài.

---

## 7. Legacy Mode — chưa có idea, để sau

*(giữ nguyên từ v1 — không mở rộng, vì bản thân v1 đã nói rõ "chưa thiết kế chi tiết". Mở rộng phần chưa có ý tưởng ra thành spec giả sẽ chỉ tạo constraint sai cho tương lai.)*

Duy nhất note lại 1 điểm kỹ thuật để không quên: nếu Legacy Mode sau này cần đọc "main cũ quan trọng thế nào", input đúng là `relationships` (Mục 5) — không tạo field `narrative_influence` mới, và **không** đọc trực tiếp từ `world_events.json`/`world_flags` của world cũ trừ khi rõ ràng cần (world_flags là state của world cũ, có thể không còn ý nghĩa gì ở world mới).

---

## 8. Ghi chú vận hành: Git/GitHub

*(giữ nguyên định hướng v1, bổ sung checklist cụ thể trước khi thực hiện)*

Trước khi khởi tạo git repo và push:

1. `grep -rn "sk-\|api_key\|API_KEY" --include="*.json" --include="*.txt" .` trên toàn bộ project để tìm key còn sót (đặc biệt `job.txt` đã nêu ở v1, và bất kỳ file `.env`/`config` nào từng lưu key thật lúc test free-tier).
2. Nếu tìm thấy key còn hiệu lực → thu hồi/đổi key trên dashboard provider (OpenRouter, v.v.) **trước** khi push, không phải sau.
3. Thêm `.gitignore` chặn: `*.env`, `job.txt` (nếu vẫn dùng làm scratch file), `data/worlds/*/branch_local_delta.json` nếu có dữ liệu test nhạy cảm không muốn public.
4. Bắt đầu bằng **private repo**, review lại `.gitignore` + chạy lại bước 1 một lần nữa ngay trước khi đổi sang public.

---

## 9. Đối chiếu với codebase thực tế — các điểm cần chốt trước khi viết workorder

Đây là phần bổ sung quan trọng nhất so với v1 — liệt kê chỗ giả định trong bản gốc **không khớp 100%** với code, cần quyết định rõ trước khi giao agent để tránh agent tự "sáng tác" theo cách khác nhau giữa các lần chạy.

### 9.1 Map System — schema thật khác mô tả v1

v1 mô tả `unlocked (bool)` + `unlock_condition (field-path)`. Thực tế: `unlock_realm` / `unlock_exp` / `unlock_checkpoint_id` — 3 field cứng, không phải field-path generic. **Quyết định đề xuất**: giữ nguyên schema thật, không đổi sang field-path — vì 3 trục này đã đủ cho mọi trường hợp mở khóa location trong thực tế (realm/exp là trục sức mạnh, checkpoint_id là trục cốt truyện), đổi sang generic field-path chỉ thêm phức tạp không cần thiết. Nếu không đồng ý, cần nêu rõ use-case cụ thể nào 3 trục hiện tại không cover được.

### 9.2 `eval_condition` chưa hỗ trợ field ngoài `character_state` và `story_clock`

Đây là **gap kỹ thuật thật**, không phải điểm thiết kế — cần fix trước khi Mục 3 và Mục 6.3 chạy được, vì cả 2 đều cần điều kiện tham chiếu `world_flags.*` (state của thế giới, không thuộc về 1 nhân vật, cũng không phải story_clock). Đã ghi rõ cách fix ở Mục 3.1 (thêm 1 branch trong `eval_condition`, tương tự `sanitize_required_conditions` cũng cần thêm branch tương ứng — Mục 6.3.3).

### 9.3 `world_canon_store` facts là prose tự do, không phải flag boolean

v1 viết "facts kiểu `fact_empire_collapsed`" như thể đây là boolean flag có thể check trực tiếp. Thực tế `world_canon_store.facts[]` là list statement dạng câu văn (`{"statement": "...", ...}`) dùng để **inject vào context LLM**, không phải structured data check được bằng `==`/`>=`. Đây là lý do Mục 3 và 6.3 ở bản v2 này tách riêng 2 khái niệm:
- `world_canon_store.facts` → phục vụ narrative context (LLM đọc để viết prose nhất quán), giữ nguyên vai trò cũ.
- `world_flags` (dict mới trong `world_config.json`) → phục vụ **điều kiện deterministic** check được (`eval_condition`), tách biệt hoàn toàn khỏi facts dạng prose.

Không gộp 2 cái làm 1 — nếu cố check điều kiện bằng cách string-match vào `statement` sẽ rất giòn (fragile), sai tinh thần "sanitizer đảm bảo field path thật sự resolve" mà v1 yêu cầu.

### 9.4 Tên field `world_config.status` có thể đã dùng cho mục đích khác

Cần kiểm tra thực tế `world_config.json` hiện tại có field `status` chưa (vd dùng cho trạng thái draft/creation) trước khi Mục 6.3.5 gán `status = "completed"` — nếu đã có, đổi tên đề xuất thành `lifecycle_status` để tránh conflict. **Đây là việc agent cần tự kiểm tra bằng cách đọc `models.py`/`storage.py::TEMPLATES["world_config.json"]` trước khi code, không tự đoán.**

---

## 10. Việc cần làm tiếp theo (đã cụ thể hóa từ v1)

1. **Xác nhận 4 điểm ở Mục 9** trước khi viết workorder — đặc biệt 9.2/9.3 (gap kỹ thuật bắt buộc phải fix, không phải tùy chọn) và 9.4 (cần agent tự kiểm tra field trùng tên).
2. Thứ tự implement (đúng ưu tiên v1, cụ thể hóa dependency):
   - **Cụm A — nền tảng**: mở rộng `eval_condition` + `sanitize_required_conditions` hỗ trợ `world_flags.*` (Mục 9.2/9.3) → đây là khóa mở cho mọi thứ sau.
   - **Cụm B — Living World Thread + Quest Board** (Mục 3 + 4): phụ thuộc Cụm A.
   - **Cụm C — Mode Endless/Có hồi kết** (Mục 6): phụ thuộc Cụm A + Cụm B (endgame condition dựa trên `world_flags` do event nền set).
   - **Cụm D — Map frontend polish** (Mục 1.3): độc lập, có thể làm song song bất kỳ lúc nào (backend đã xong).
   - **Cụm E — Checkpoint linter** (Mục 2.2): độc lập, làm bất kỳ lúc nào. ✅ Done - 2026-08-01 (`backend/app/services/validators.py` + tích hợp vào `builder_routes.py`; đồng thời fix bug Cụm C: `target_ending_scenario: null` → `None` trong `checkpoint_engine.py` làm hỏng toàn bộ backend import).
   - **Legacy Mode**: để sau cùng, chưa có idea (giữ nguyên v1).
3. Mỗi cụm = 1 workorder file riêng theo format `.agents/{role}_{milestone}/BRIEFING.md` đã dùng (xem mẫu `worker_m4_1/BRIEFING.md`) — không gộp.
4. Dọn git/API key trước khi push (Mục 8), thực hiện **trước** khi bắt đầu Cụm A (để không có commit nào chứa key cũ trong lịch sử).
