# TÀI LIỆU TỔNG HỢP TOÀN DIỆN: NGHIÊN CỨU, ĐỀ XUẤT KIẾN TRÚC & KẾ HOẠCH NÂNG CẤP STORY ENGINE

> **Dự án mục tiêu:** `story-engine-PR` (`c:\Users\phuoc\Desktop\story-engine-PR\story-engine`)  
> **Nguồn đối chiếu 1:** `Sonder_Engine-alpha6.0.1`  
> **Nguồn đối chiếu 2:** `https://github.com/forsonny/book-os` (Novel-OS)  
> **Tài liệu chiến lược:** `story-engine-master-plan.md`  
> **Quyết định công nghệ:** Backend **Python (FastAPI + Pydantic)** & Frontend **React + TypeScript (Vite)**  
> **Tiêu chí:** Trung thực, minh bạch, có bằng chứng mã nguồn thật, phân tích logic đa tầng, kế hoạch hành động chuẩn `planning-and-task-breakdown`. KHÔNG SỬA CODE HIỆN TẠI.

---

## 📌 MỤC LỤC

1. [Chương I: Tổng Quan Vấn Đề & Định Hướng Công Nghệ (Technology Stack Decision)](#chuong-i-tong-quan-van-de--dinh-huong-cong-nghe)
2. [Chương II: Phân Tích Đa Tầng Từ Sonder Engine Alpha6.0.1 (Logic & Code Evidence)](#chuong-ii-phan-tich-da-tang-tu-sonder-engine-alpha601)
3. [Chương III: Phân Tích Đa Tầng Từ Book-OS / Novel-OS (Prompt & Context Layering)](#chuong-iii-phan-tich-da-tang-tu-book-os--novel-os)
4. [Chương IV: Đối Chiếu 4 Nhóm Công Việc Trong Story-Engine-Master-Plan.md](#chuong-iv-doi-chieu-4-nhom-cong-viec-trong-story-engine-master-planmd)
5. [Chương V: Kế Hoạch Triển Khai Chi Tiết (Phased Task Breakdown)](#chuong-v-ke-hoach-trien-khai-chi-tiet)

---

<a name="chuong-i-tong-quan-van-de--dinh-huong-cong-nghe"></a>
## CHƯƠNG I: TỔNG QUAN VẤN ĐỀ & ĐỊNH HƯỚNG CÔNG NGHỆ

### 1.1 Đặt vấn đề từ thực trạng `story-engine`
Dự án `story-engine` vận hành theo mô hình 4-Agent (World Builder, Planner, Writer, Extractor). Dù sở hữu nền tảng RAG thẻ thông tin tốt, dự án đang gặp 4 điểm nghẽn chính:
1. **Lỗi "Lồng giam Checkpoint":** Boundary gò bó vô lý, ép AI tự bịa rào cản giả.
2. **Lỗi "Field path ma" & "Dữ liệu lồng nhau":** LLM tự bịa path không có trong schema (`kaius.stats.shadow_power`) làm kẹt checkpoint, và ghi `relationships` thành object lồng nhau gây hiển thị `[object Object]`.
3. **Thiếu Ma sát Narrative:** Planner chỉ giữ nhịp truyện xuôi chiều, thiếu trở ngại/thử thách cuốn hút ở từng turn.
4. **Hạn chế giao diện (Vanilla JS):** Vanilla JS hiện tại khó mở rộng cho các tính năng phức tạp như Interactive Map, Codex Network Graph, và Túi đồ dạng lưới.

### 1.2 Quyết định Chọn Kiến trúc Công nghệ: Golden Architecture
Nhằm **đặt Quality lên hàng đầu**, cấu trúc công nghệ được chốt như sau:

```
┌──────────────────────────────────────────────────────────────┐
│ FRONTEND: Vite + React + TypeScript + Vanilla CSS            │
│ -> Tối ưu UI/UX, Type Safety, Render Map SVG, Inventory Grid │
└──────────────────────────────┬───────────────────────────────┘
                               │ REST API / WebSockets (JSON)
┌──────────────────────────────▼───────────────────────────────┐
│ BACKEND: Python + FastAPI + Pydantic + Pytest                │
│ -> Xử lý AI Pipeline, Commit Sanitizer, Lore RAG, Engine Logic│
└──────────────────────────────────────────────────────────────┘
```

* **Tại sao GIỮ Backend Python (FastAPI)?**
  - Python là "vua" hệ sinh thái AI/LLM. Pydantic validate schema vượt trội so với các công cụ trong Node.js.
  - Sonder Engine (engine hàng đầu với 4.600 dòng commit atomic) cũng dùng Python thuần + SQLite + FastAPI.
  - Tránh rủi ro rewrite 2.700 dòng engine backend & 220KB unit test suite mà không mang lại giá trị gia tăng cho câu chuyện.
* **Tại sao NÊN ĐỔI Frontend sang React + TypeScript (Vite)?**
  - **Type Safety:** Ngăn ngừa tuyệt đối các lỗi render object `[object Object]` hay đọc sai field (`c.relationships` vs `c.affinity`).
  - **State Management:** Quản lý sạch sẽ dữ liệu phức tạp cho Map Tab (Tọa độ 0-100, Fog of War), Inventory Grid, và Affinity Network Graph.

---

<a name="chuong-ii-phan-tich-da-tang-tu-sonder-engine-alpha601"></a>
## CHƯƠNG II: PHÂN TÍCH ĐA TẦNG TỪ SONDER ENGINE ALPHA6.0.1

---

### TẦNG 1: BỨC TƯỜNG THÔNG TIN EPISTEMOLOGY (EPISTEMOLOGICAL FIREWALL)

#### 1. Bằng chứng mã nguồn (Source Code Evidence)
Tại `Sonder_Engine-alpha6.0.1/commit.py` (L68–99):
```python
def update_place_graph(graph, scene, here_rid, turn_idx, came_from=None, visible=None):
    """
    Firewall discipline, in order of temptation:
    * Nodes/edges come ONLY from (a) the room the character is standing in... 
      (b) the step they just took (`came_from`, guarded by rooms_adjacent)... 
      (c) the `visible` list...
    * A room absent from the scene entirely keeps its nodes and edges untouched: 
      the character learns a place is gone by standing where it was, 
      not by the registry telling their memory.
    * Nothing here reads another character's state, and nothing writes 
      anything the character did not walk, see, or step through.
    """
```
Tại `Sonder_Engine-alpha6.0.1/agents/perception.py` (L78–100):
```python
def _dialogue_hear_level(entry, rel, observer_name):
    # Kiểm tra tầm nhìn sightlines, ánh sáng effective_light, ngụy trang active_disguises
    # để quyết định nhân vật nghe/thấy được gì trước khi gửi thông tin vào prompt.
```

#### 2. Phân tích Logic & Suy luận
* **Vấn đề:** Nếu AI biết toàn bộ sự thật khách quan (Omniscient Godview), nhân vật phụ sẽ tự động hành xử như thể họ biết được bí mật của người chơi hay thông tin ở phòng bên cạnh (Metagaming).
* **Kết luận cho Story Engine:** Tách biệt thông tin. Writer chỉ được nạp các Card/Lore mà nhân vật hiện tại đã unlock hoặc trực tiếp chứng kiến thông qua một bước **Perception Filter**.

---

### TẦNG 2: BOUNDARY GHI STATE QUYẾT ĐỊNH (DETERMINISTIC COMMIT BOUNDARY)

#### 1. Bằng chứng mã nguồn (Source Code Evidence)
Tại `Sonder_Engine-alpha6.0.1/CLAUDE.md` (L64–65) và `commit.py`:
```
commit.py is the sole persistence boundary — model output is provisional until 
deterministic commit code validates it. Slow lore/memory preparation happens 
before the write lock, then all primary turn mutations commit inside one outer transaction. 
Any domain failure rolls the entire turn back...
```

#### 2. Phân tích Logic & Suy luận
* **Vấn đề:** LLM là cỗ máy xác suất, không bao giờ đảm bảo 100% sinh đúng JSON Schema hay đúng field path có thật.
* **Kết luận cho Story Engine:** Viết module `commit_sanitizer.py` bằng code Python thuần:
  - Validate mọi field path trong `required_conditions` trước khi đánh giá. Nếu path ma (vd: `kaius.stats.shadow_power`) xuất hiện, tự động sanitize/loại bỏ thay vì làm kẹt checkpoint.
  - Ép kiểu `str(val)` cho `relationships` tại `builder_routes.py` trước khi ghi đĩa.

---

### TẦNG 3: MÔ HÌNH ĐỘNG LỰC NỘI TẠI & TÂM LÝ CHIỀU SÂU (PSYCHOLOGY RUNTIME)

#### 1. Bằng chứng mã nguồn (Source Code Evidence)
Tại `Sonder_Engine-alpha6.0.1/psychology_runtime.py` (L19–26 & 75–100):
```python
_CHARGE_GAIN = 0.18
_CHARGE_HALF_LIFE = 12.0
_CHARGE_SATURATION = 0.85

def resolve_hedonic(previous, appraisal, interoception, body_state, elapsed_units, ...):
    # Charge tích tụ liên tục khi nhu cầu/động lực (drive) không được giải tỏa.
```
Tại `CLAUDE.md` (L100–108):
```
Goals are built to be completable and abandonable — so when they decay the character 
simply stops wanting things... A courier walked 16 optimal rooms to his destination 
and turned away, because nothing underneath the spent goals wanted it.
```

#### 2. Phân tích Logic & Suy luận
* **Vấn đề:** Goal (Mục tiêu) ngắn hạn sẽ biến mất sau khi hoàn thành. Nếu không có **Core Drive** (Động lực lõi trường tồn), nhân vật sẽ bị "rỗng động lực" và rơi vào trạng thái thụ động.
* **Kết luận cho Story Engine:** Sửa `WORLD_BUILDER_CHARACTERS_PROMPT` bắt buộc tạo `core_drive` (vd: *"Luôn tìm kiếm quyền lực để không ai đè nén được mình"*) và quy định `values` dạng đánh đổi (`"Lợi ích cá nhân > Trung thành"`).

---

### TẦNG 4: SPATIAL ENGINE & BẢN ĐỒ TỌA ĐỘ CHUẨN HÓA (SPATIAL & MAP REALITY)

#### 1. Phân tích Logic & Suy luận
* Sonder Engine duy trì `spatial.py` (178KB) xử lý góc nhìn, khoảng cách và vật lý.
* Với `story-engine`, áp dụng giải pháp gọn gàng nhưng minh bạch: File `location_map.json` sử dụng **Tọa độ chuẩn hóa (Normalized Coordinates 0-100)**:
  ```json
  {
    "locations": [
      {"id": "loc_main_hall", "name": "Đại Điện", "x": 50.0, "y": 20.0, "unlocked": true},
      {"id": "loc_forbidden_library", "name": "Thư Viện Cấm", "x": 80.0, "y": 75.0, "unlocked": false, 
       "unlock_condition": {"field": "protagonist.power_stat.realm", "op": ">=", "value": 2}}
    ],
    "fog_of_war": true
  }
  ```
* Tọa độ chuẩn hóa giúp Frontend React tự động scale sơ đồ bản đồ mượt mà trên mọi thiết bị.

---

<a name="chuong-iii-phan-tich-da-tang-tu-book-os--novel-os"></a>
## CHƯƠNG III: PHÂN TÍCH ĐA TẦNG TỪ BOOK-OS / NOVEL-OS

---

### TẦNG 5: CONTEXT 3 TẦNG (THREE-LAYER CONTEXT FRAMEWORK)
* **Layer 1: Standards (`~/.novel-os/standards/`)** — `prose-style.md`, `narrative-techniques.md`. Định nghĩa DNA viết lách chung.
* **Layer 2: Novel (`.novel-os/novel/`)** — `premise.md`, `writing-plan.md`. Định nghĩa tầm nhìn riêng của tác phẩm.
* **Layer 3: Manuscripts (`.novel-os/manuscripts/`)** — `story-outline.md`, `writing-tasks.md`. Chi tiết từng scene.

👉 **Áp dụng:** Phân tách `backend/prompts.py` thành 3 khối rõ ràng: `SYSTEM_WRITING_STANDARDS` (Quy tắc hành văn, Anti-OOC), `WORLD_LORE_CONTEXT` (Sức mạnh, thế giới), và `ACTIVE_SCENE_ROADMAP` (Checkpoint hiện tại).

---

### TẦNG 6: THẺ XML TAG & KỸ THUẬT MA SÁT SCENE-AND-SEQUEL
* Tại `standards/narrative-techniques.md` trong Book-OS:
  ```markdown
  <conditional-block context-check="story-structure">
  ### Scene Structure:
  - Goal: What the character wants in this scene
  - Conflict: What prevents them from getting it
  - Disaster: How the scene ends badly or with new complications
  - Reaction: Character's emotional response and new decision
  </conditional-block>
  ```
👉 **Áp dụng:** Đưa quy tắc Scene-and-Sequel vào `PLANNER_SYSTEM_PROMPT`. Bắt buộc Planner xuất ra trường `narrative_friction` để mỗi turn đều có trở ngại và lật kèo hấp dẫn.

---

<a name="chuong-iv-doi-chieu-4-nhom-cong-viec-trong-story-engine-master-planmd"></a>
## CHƯƠNG IV: ĐỐI CHIẾU 4 NHÓM CÔNG VIỆC TRONG MASTER PLAN

| Mục Master Plan | Vấn đề hiện tại | Nguyên nhân gốc rễ | Giải pháp kỹ thuật học được |
| :--- | :--- | :--- | :--- |
| **1.1 Revert `checkpoint_conditions_met()`** | Logic bị comment out `return True` | Bị ngắt tạm thời trong quá trình dev | Revert lại logic kiểm tra điều kiện thật. |
| **1.2 Fix field path ma trong conditions** | LLM tự bịa path không có trong schema | Prompt thiếu danh sách field valid & thiếu validation code | (1) Sửa Skeleton prompt chỉ rõ valid paths.<br>(2) Viết `commit_sanitizer.py` validate path trước khi lưu. |
| **1.3 Safety net checkpoint rỗng** | Checkpoint rỗng bị lặp retry vô ích | Thiếu Guard condition | Kiểm tra `locations` & `allowed_characters` rỗng trước khi gọi LLM. Trả lỗi dừng sớm ngay lập tức. |
| **1.4 Auto-advance `current_checkpoint_id`** | Confirm prelude không nhảy sang `cp_1` | `chapter_confirm_prelude()` thiếu dòng gán checkpoint | Cập nhật `current_checkpoint_id = next_cp_id` ngay khi confirm prelude. |
| **1.5 `relationships` bị lồng object** | Frontend hiện `[object Object]` | Builder prompt ví dụ sai kiểu + route thiếu defensive code | (1) Sửa ví dụ trong prompt.<br>(2) Bổ sung ép kiểu `str(value)` trong `builder_routes.py`. |
| **1.6 Affinity Network rỗng** | Đồ thị không vẽ được đường nối | Frontend đọc sai field (`c.affinity` thay vì `c.relationships`) | Sửa frontend đọc đúng `c.relationships` và đổi logic vẽ đường nối dựa theo existence. |
| **Nhóm 2: Đổi triết lý Checkpoint** | AI bịa lý do cưỡng ép nhốt nhân vật | Checkpoint bị coi là "lồng giam vật lý" | Sửa Prompt: Checkpoint là **Mục tiêu động cơ nội tại**. Áp dụng **Zone Prefix Matching** (`"Valdris Estate - Kitchen"` hợp lệ với `"Valdris Estate"`). |
| **Nhóm 3: Map System mới** | Di chuyển bị gò bó tùy tiện | Thiếu bản đồ công khai minh bạch | Tạo `location_map.json` chuẩn hóa (0-100), tích hợp điều kiện unlock với EXP/Realm sẵn có. |
| **Nhóm 4.1: Planner Friction** | Diễn biến truyện trôi chảy quá mức | Prompt Planner thiếu chỉ thị tạo xung đột | Bắt buộc Planner sinh `narrative_friction` theo mô hình Scene-and-Sequel của Book-OS. |
| **Nhóm 4.2: Frontend Migration & UI** | Tag thông tin phẳng, Vanilla JS hạn chế | Vanilla JS thiếu Type Safety & State Management | Chuyển Frontend sang **Vite + React + TypeScript** cho UI mượt mà, type-safe 100%. |

---

<a name="chuong-v-ke-hoach-trien-khai-chi-tiet"></a>
## CHƯƠNG V: KẾ HOẠCH TRIỂN KHAI CHI TIẾT (PHASED TASK BREAKDOWN)

```
Phase 1: Critical Bug Fixes & Commitment Safety Net (Nhóm 1)
    │
    ├── Phase 2: Redesign Triết lý Checkpoint & Scene Friction Prompts (Nhóm 2 & 4.1)
    │       │
    │       └── Phase 3: Spatial Location Map System (Nhóm 3)
    │               │
    │               └── Phase 4: Frontend React TypeScript Migration & UI Separation (Nhóm 4.2)
```

---

### PHASE 1: CRITICAL BUG FIXES & SANITIZER SAFETY NET

#### Task 1.1: Revert `checkpoint_conditions_met()` & Auto-Advance Prelude
- **Description:** Revert logic thật cho `checkpoint_conditions_met()` và cập nhật `current_checkpoint_id` khi xác nhận prelude trong `chapter_confirm_prelude()`.
- **Acceptance Criteria:**
  - [ ] `checkpoint_conditions_met()` đánh giá đúng điều kiện `exp`, `realm`, `knowledge_flags`.
  - [ ] Xác nhận prelude đẩy `current_checkpoint_id` từ `cp_0` sang checkpoint tiếp theo.
- **Verification:** Run `pytest backend/test_engine.py -k "test_prelude or test_checkpoint"`.
- **Files touched:** `backend/app/engine.py`, `backend/app/routes/chapter_routes.py`.
- **Scope:** Small (2 files).

#### Task 1.2: Implement Defensive Condition Sanitizer & Prompt Rules
- **Description:** Cập nhật `WORLD_BUILDER_SKELETON_PROMPT` với danh sách field path hợp lệ. Viết hàm sanitizer trong `commit_sanitizer.py` lọc field path ma trước khi lưu/đánh giá condition.
- **Acceptance Criteria:**
  - [ ] Skeleton prompt liệt kê rõ valid path (`power_stat.exp`, `power_stat.realm`, `knowledge_flags`, `karma`, `inventory`).
  - [ ] Path ma tự động bị loại bỏ hoặc cảnh báo, không gây kẹt checkpoint vĩnh viễn.
- **Verification:** Run test với payload có condition ma, xác nhận engine không crash và không bị kẹt.
- **Files touched:** `backend/prompts.py`, `backend/app/engine.py`, `backend/app/commit_sanitizer.py` [NEW].
- **Scope:** Small (3 files).

#### Task 1.3: Empty Boundary Early Safety Net & Relationship String Enforcement
- **Description:** Chặn sớm checkpoint boundary rỗng (`locations: []` & `allowed_characters: []`). Ép kiểu string cho `relationships` trong `builder_routes.py` và sửa `WORLD_BUILDER_CHARACTERS_PROMPT`.
- **Acceptance Criteria:**
  - [ ] Checkpoint boundary rỗng trả về thông báo lỗi rõ ràng ngay lập tức, không gọi LLM Writer.
  - [ ] Tất cả value trong `relationships` được lưu dưới dạng `string` thuần túy.
- **Verification:** Kiểm tra JSON output của `character_state.json` sau khi build world mới.
- **Files touched:** `backend/prompts.py`, `backend/app/engine.py`, `backend/app/routes/builder_routes.py`.
- **Scope:** Medium (3 files).

#### Task 1.4: Fix Codex Affinity Network Logic
- **Description:** Sửa logic backend/API trả về đúng field `relationships` thay vì `affinity` rỗng, cập nhật logic vẽ đồ thị đường nối quan hệ.
- **Acceptance Criteria:**
  - [ ] Đồ thị Affinity Network trả về chính xác các đường nối quan hệ giữa các nhân vật.
  - [ ] Không còn dữ liệu `[object Object]`.
- **Verification:** Kiểm tra API endpoint của Codex trả về đúng cấu trúc dữ liệu quan hệ.
- **Files touched:** `backend/app/routes/world_routes.py`.
- **Scope:** Small (1 file).

---

### PHASE 2: REDESIGN CHECKPOINT PHILOSOPHY & SCENE FRICTION PROMPTS

#### Task 2.1: Zone Prefix Matching & Softer Boundary Correction Notes
- **Description:** Sửa `check_boundary_violations()` hỗ trợ so khớp theo zone prefix (`"Valdris Estate - Kitchen"` thuộc `"Valdris Estate"`). Sửa `build_boundary_correction_note()` giảm thiểu việc ép AI bịa chướng ngại vật.
- **Acceptance Criteria:**
  - [ ] Di chuyển trong cùng khu vực lớn được chấp nhận là hợp lệ.
  - [ ] Prompt hướng dẫn AI xử lý rào cản tự nhiên, hướng theo động cơ nhân vật.
- **Verification:** Chạy test case di chuyển giữa các sub-location trong cùng zone.
- **Files touched:** `backend/app/engine.py`, `backend/prompts.py`.
- **Scope:** Small (2 files).

#### Task 2.2: Implement Scene-and-Sequel Friction in Planner Prompt
- **Description:** Nâng cấp `PLANNER_SYSTEM_PROMPT` theo mô hình Book-OS: Bắt buộc tạo ra `narrative_friction` (Goal → Conflict → Disaster → Reaction) trong các turn.
- **Acceptance Criteria:**
  - [ ] Planner output trả về thêm cấu trúc `narrative_friction`.
  - [ ] Các turn diễn ra có trở ngại và biến cố cuốn hút, không bị trôi chảy quá mức.
- **Verification:** Run simulation 5 turns và kiểm tra JSON log của Planner.
- **Files touched:** `backend/prompts.py`, `backend/app/engine.py`.
- **Scope:** Small (2 files).

---

### PHASE 3: SPATIAL LOCATION MAP SYSTEM

#### Task 3.1: Define `location_map.json` Model & Generator
- **Description:** Định nghĩa data structure cho `location_map.json` sử dụng Tọa độ chuẩn hóa (0-100). Viết generator sinh map từ mô tả thế giới.
- **Acceptance Criteria:**
  - [ ] World creation tạo ra file `location_map.json` chứa danh sách node vị trí và tọa độ `(x, y)`.
  - [ ] `unlock_condition` map trực tiếp vào `power_stat.exp` hoặc `realm`.
- **Verification:** Kiểm tra file `location_map.json` được tạo trong thư mục data của world.
- **Files touched:** `backend/app/models.py`, `backend/app/engine.py`, `backend/app/routes/world_routes.py`.
- **Scope:** Medium (3 files).

#### Task 3.2: Map-based Boundary Checking
- **Description:** Cập nhật logic boundary check: Khi người chơi di chuyển đến vị trí chưa `unlocked`, hệ thống báo rõ lý do ("Khu vực chưa mở khóa, cần đạt EXP X") thay vì ép AI viết cảnh hộ vệ chặn đường.
- **Acceptance Criteria:**
  - [ ] Người chơi nhận được phản hồi minh bạch khi đến khu vực chưa mở khóa.
- **Verification:** Test hành động di chuyển vào location bị khóa.
- **Files touched:** `backend/app/engine.py`.
- **Scope:** Small (1 file).

---

### PHASE 4: FRONTEND MIGRATION TO REACT + TYPESCRIPT & UI SEPARATION

#### Task 4.1: Initialize Vite + React + TypeScript Frontend Project
- **Description:** Khởi tạo project React mới trong `frontend/` sử dụng Vite và TypeScript. Cấu hình API client kết nối với Python FastAPI backend.
- **Acceptance Criteria:**
  - [ ] Build thành công project Vite React TS.
  - [ ] Kết nối API mượt mà với FastAPI backend.
- **Verification:** Run `npm run build` & `npm run dev`.
- **Files touched:** `frontend/` (React structure).
- **Scope:** Medium.

#### Task 4.2: Build Separated UI Components (Status, Inventory Grid, Skills)
- **Description:** Xây dựng các React Component riêng biệt: Status Panel, Inventory Grid (túi đồ dạng lưới), Skills Panel, và Codex Modal (Affinity Network graph bằng React Flow/D3).
- **Acceptance Criteria:**
  - [ ] Giao diện hiển thị sắc nét, type-safe 100%, không còn dính bug `[object Object]`.
- **Verification:** Kiểm tra trực quan trên trình duyệt.
- **Files touched:** `frontend/src/components/...`.
- **Scope:** Medium.

#### Task 4.3: Interactive Location Map Tab Component
- **Description:** Phát triển Tab Map tương tác trên React render sơ đồ vị trí từ `location_map.json` với Tọa độ chuẩn hóa (0-100), hiệu ứng Sương mù (Fog of War) và trạng thái mở/khóa khu vực.
- **Acceptance Criteria:**
  - [ ] Map SVG/Canvas hiển thị mượt mà, hỗ trợ zoom/pan và click chọn vị trí di chuyển.
- **Verification:** Mở tab Map và kiểm tra tương tác di chuyển vị trí.
- **Files touched:** `frontend/src/components/MapTab.tsx`.
- **Scope:** Medium.

---

## 📌 KẾT LUẬN

Tài liệu này tổng hợp **100% tất cả các góc nhìn, lập luận logic, bằng chứng mã nguồn và quyết định kiến trúc** đã thảo luận từ đầu đến nay. 

Mọi thứ đã được chuẩn hóa để bạn có một cẩm nang chiến lược hoàn chỉnh. Khi bạn sẵn sàng bắt tay vào code triển khai, chúng ta sẽ lần lượt thực hiện theo từng Task trong Phase 1!
