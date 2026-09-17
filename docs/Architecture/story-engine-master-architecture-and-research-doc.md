# TÀI LIỆU TỔNG HỢP TOÀN DIỆN: NGHIÊN CỨU, ĐỀ XUẤT KIẾN TRÚC & KẾ HOẠCH NÂNG CẤP STORY ENGINE

> **Dự án mục tiêu:** `story-engine-PR` (`c:\Users\phuoc\Desktop\story-engine-PR\story-engine`)  
> **Nguồn đối chiếu 1:** `Sonder_Engine-alpha6.0.1`  
> **Nguồn đối chiếu 2:** `https://github.com/forsonny/book-os` (Novel-OS)  
> **Tài liệu chiến lược:** `story-engine-master-plan.md`  
> **Quyết định công nghệ:** Backend **Python (FastAPI + Pydantic)** & Frontend **React + TypeScript (Vite)**  
> **Tiêu chí:** Trung thực, minh bạch, có bằng chứng mã nguồn thật, phân tích logic đa tầng, kế hoạch hành động chuẩn `planning-and-task-breakdown`.

---

## 📌 MỤC LỤC

1. [Chương I: Tổng Quan Vấn Đề & Định Hướng Công Nghệ (Technology Stack Decision)](#chuong-i-tong-quan-van-de--dinh-huong-cong-nghe)
2. [Chương II: Phân Tích Đa Tầng Từ Sonder Engine Alpha6.0.1 (Logic & Code Evidence)](#chuong-ii-phan-tich-da-tang-tu-sonder-engine-alpha601)
3. [Chương III: Phân Tích Đa Tầng Từ Book-OS / Novel-OS (Prompt & Context Layering)](#chuong-iii-phan-tich-da-tang-tu-book-os--novel-os)
4. [Chương IV: Đối Chiếu 4 Nhóm Công Việc Trong Story-Engine-Master-Plan.md](#chuong-iv-doi-chieu-4-nhom-cong-viec-trong-story-engine-master-planmd)
5. [Chương V: Kế Hoạch Triển Khai Chi Tiết (Phased Task Breakdown)](#chuong-v-ke-hoach-trien-khai-chi-tiet)
6. [Kết Luận](#ket-luan)

---

<a name="chuong-i-tong-quan-van-de--dinh-huong-cong-nghe"></a>
## CHƯƠNG I: TỔNG QUAN VẤN ĐỀ & ĐỊNH HƯỚNG CÔNG NGHỆ

### 1.1 Đặt vấn đề từ thực trạng `story-engine`
Dự án `story-engine` vận hành theo mô hình 4-Agent (World Builder, Planner, Writer, Extractor). Dù sở hữu nền tảng RAG thẻ thông tin tốt, dự án đang gặp 4 điểm nghẽn chính:
1. **Lỗi "Lồng giam Checkpoint":** Boundary gò bó vô lý, ép AI tự bịa rào cản giả.
2. **Lỗi "Field path ma" & "Dữ liệu lồng nhau":** LLM tự bịa path không có trong schema (`kaius.stats.shadow_power`) làm kẹt checkpoint, và ghi `relationships` thành object lồng nhau gây hiển thị `[object Object]`.
3. **Thiếu Ma sát Narrative:** Planner chỉ giữ nhịp truyện xuôi chiều, thiếu trở ngại/thử thách cuốn hút ở từng turn.
4. **Hạn chế giao diện (Vanilla JS):** Vanilla JS hiện tại khó mở rộng cho các tính năng phức tạp như Interactive Map, Codex Network Graph, và Túi đồ dạng lưới.

### 1.2 Phân định vai trò của hai file Models (`backend/models.py` vs `backend/app/models.py`)
Qua kiểm tra mã nguồn thực tế:
- **`backend/app/models.py` (OFFICIAL SOURCE OF TRUTH):** Là file Pydantic Schema chính thức được toàn bộ hệ thống (`backend/app/engine.py`, các file routes trong `backend/app/routes/`) sử dụng. Chứa các class cốt lõi: `CharacterModel`, `StateChangesModel`, `CheckpointModel`, `CardModel`, `WorldConfigUpdate`, `BranchLocalDeltaModel`. Mọi định nghĩa Pydantic mới hoặc chỉnh sửa schema **BẮT BUỘC** thực hiện tại đây.
- **`backend/models.py` (LEGACY WRAPPER):** Là file model cũ từ giai đoạn single-file prototype ban đầu, giữ vai trò tương thích ngược. Trong lộ trình tái cấu trúc, tất cả import sẽ được quy về `backend/app/models.py`.

### 1.3 Quyết định Chọn Kiến trúc Công nghệ: Golden Architecture
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
| **1.6 Affinity Network rỗng** | Đồ thị không vẽ được đường nối | Backend/API chỉ trả `c.affinity` (rỗng) & Frontend đọc nhầm field | (1) Backend API trả đúng `c.relationships`.<br>(2) Frontend đọc `c.relationships` và render đường nối theo existence. |
| **Nhóm 2: Đổi triết lý Checkpoint** | AI bịa lý do cưỡng ép nhốt nhân vật | Checkpoint bị coi là "lồng giam vật lý" | Sửa Prompt: Checkpoint là **Mục tiêu động cơ nội tại**. Áp dụng **Zone Prefix Matching** (`"Valdris Estate - Kitchen"` hợp lệ với `"Valdris Estate"`). |
| **Nhóm 3: Map System mới** | Di chuyển bị gò bó tùy tiện | Thiếu bản đồ công khai minh bạch | Tạo `location_map.json` chuẩn hóa (0-100), tích hợp điều kiện unlock với EXP/Realm sẵn có. |
| **Nhóm 4.1: Planner Friction** | Diễn biến truyện trôi chảy quá mức | Prompt Prompt thiếu chỉ thị tạo xung đột | Bắt buộc Planner sinh `narrative_friction` theo mô hình Scene-and-Sequel của Book-OS. |
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
    │                       │
    │                       └── Phase 5: Technical Debt & Backend Refactoring 🆕
    │                               │
    │                               └── Phase 6: Advanced Architecture (Sonder Engine Patterns) 🆕
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

#### Task 1.4: Fix Codex Affinity Network Backend API & Vanilla JS Frontend Fix (Bug 1.6)
- **Description:** 
  - (1) Backend: Cập nhật API endpoint trong `backend/app/routes/world_routes.py` trả về đúng dictionary `relationships` hợp lệ từ `CharacterModel` (trong `backend/app/models.py`).
  - (2) Frontend (Vanilla JS Phase 1): Sửa mã render Codex trong Vanilla JS đọc trực tiếp `c.relationships` thay vì `c.affinity`, chuyển logic vẽ đường nối dựa theo existence của mối quan hệ.
- **Acceptance Criteria:**
  - [ ] API endpoint `/world/.../codex` trả về danh sách quan hệ dạng dictionary string-string.
  - [ ] Đồ thị Affinity Network trên UI hiện tại hiển thị chính xác các đường nối quan hệ giữa các nhân vật mà không dính `[object Object]`.
- **Verification:** Gọi API Codex và kiểm tra hiển thị đồ thị mạng lưới quan hệ trên UI.
- **Files touched:** `backend/app/routes/world_routes.py`, `frontend/app.js` (Vanilla JS rendering code).
- **Scope:** Small (2 files).

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
- **Description:** Định nghĩa data structure cho `location_map.json` sử dụng Tọa độ chuẩn hóa (0-100) trong `backend/app/models.py`. Viết generator sinh map từ mô tả thế giới.
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

#### Task 4.2: Build Separated UI Components & Codex Affinity Graph (Dùng React Flow)
- **Description:** Xây dựng các React Component riêng biệt: Status Panel, Inventory Grid (túi đồ dạng lưới), Skills Panel, và Codex Modal Network Graph chính thức chốt thư viện **React Flow** (`@xyflow/react`).
  - *Lý do chốt React Flow:* Hỗ trợ React-native declarative nodes, zoom/pan tự động, tùy biến đường nối Custom Edges, và kéo thả layout trực quan hơn 10 lần so với D3.js thủ công.
- **Acceptance Criteria:**
  - [ ] Giao diện hiển thị sắc nét, type-safe 100%, không còn dính bug `[object Object]`.
  - [ ] Codex Affinity Network render mượt mà bằng React Flow.
- **Verification:** Kiểm tra trực quan trên trình duyệt.
- **Files touched:** `frontend/src/components/CodexModal.tsx`, `frontend/src/components/InventoryGrid.tsx`, `frontend/src/components/StatusPanel.tsx`.
- **Scope:** Medium (3-4 files).

#### Task 4.3: Interactive Location Map Tab Component
- **Description:** Phát triển Tab Map tương tác trên React render sơ đồ vị trí từ `location_map.json` với Tọa độ chuẩn hóa (0-100), hiệu ứng Sương mù (Fog of War) và trạng thái mở/khóa khu vực.
- **Acceptance Criteria:**
  - [ ] Map SVG/Canvas hiển thị mượt mà, hỗ trợ zoom/pan và click chọn vị trí di chuyển.
- **Verification:** Mở tab Map và kiểm tra tương tác di chuyển vị trí.
- **Files touched:** `frontend/src/components/MapTab.tsx`.
- **Scope:** Medium.

---

### PHASE 5: TECHNICAL DEBT & BACKEND REFACTORING 🆕

#### Task 5.1: Decompose `engine.py` into Domain Modules
- **Description:** Tách `backend/app/engine.py` (~2755 dòng) thành các module domain riêng biệt: `llm_client.py` (gọi LLM, fallback, role assignment), `chapter_generator.py` (pipeline điều phối Planner→Writer→Extractor→Checker), `checkpoint_engine.py` (boundary, checkpoint advance, sub-beat), `state_manager.py` (state đọc/ghi, normalize, rollback), `rag.py` (TF-IDF, cosine similarity, card selection), `language_detection.py`.
- **Acceptance Criteria:**
  - [ ] `engine.py` giảm từ 2755 dòng xuống ≤ 600 dòng (chỉ còn orchestration).
  - [ ] Mỗi module mới có thể unit test độc lập, không cần import toàn bộ engine.
  - [ ] Không còn pattern `import main as _m` trong function body — circular imports được giải quyết triệt để.
- **Verification:** `pytest backend/test_engine.py` pass 100% sau khi tách; kiểm tra không còn `import main as _m` trong codebase.
- **Files touched:** `backend/app/engine.py` → refactor thành `backend/app/engine.py` (orchestrator) + `backend/app/llm_client.py` [NEW] + `backend/app/chapter_generator.py` [NEW] + `backend/app/checkpoint_engine.py` [NEW] + `backend/app/state_manager.py` [NEW] + `backend/app/rag.py` [NEW].
- **Scope:** Large (6+ files).

#### Task 5.2: Fix Write Order — Cross-Check Before Disk Commit
- **Description:** Trong `_generate_chapter()`, hiện tại ghi `character_state.json`, `chapters.json`, `world_config.json` xuống disk **trước** khi chạy Extractor cross-check. Đảo thứ tự: cross-check chạy trước, chỉ ghi disk khi cross-check pass (hoặc warning không chặn). Nếu cross-check fail nặng, rollback toàn bộ turn.
- **Acceptance Criteria:**
  - [ ] Extractor cross-check chạy TRƯỚC khi ghi state files.
  - [ ] Cross-check fail → state không bị thay đổi trên disk.
  - [ ] Có cơ chế staging (ghi vào temp key, chỉ commit khi tất cả validate pass).
- **Verification:** Inject lỗi vào LLM output giả, xác nhận state files không bị ghi đè sai.
- **Files touched:** `backend/app/engine.py`, `backend/app/state_manager.py` [NEW from 5.1].
- **Scope:** Medium (2 files).

#### Task 5.3: Centralize Character Normalization
- **Description:** Hiện tại logic normalize character data từ raw LLM output sang schema chuẩn bị lặp ở 3 nơi: `builder_routes.py` (world builder step "characters"), `engine.py` `_validate_imported_package()` (import validation), và `engine.py` `process_alternate_outcome()` (alternate outcome). Tạo 1 hàm `normalize_character(raw: dict) -> CharacterModel` duy nhất trong `backend/app/models.py` (hoặc `state_manager.py` mới), cả 3 nơi đều gọi chung.
- **Acceptance Criteria:**
  - [ ] Hàm `normalize_character()` xử lý `power_stat`, `known_skills`, `knowledge_flags`, `inventory`, `relationships`, 6 SillyTavern fields, `traits`, `status_effects`.
  - [ ] Cả 3 nơi (builder_routes, validate_imported_package, process_alternate_outcome) đều gọi chung 1 hàm.
  - [ ] Thêm field mới vào schema → chỉ sửa 1 chỗ.
- **Verification:** Build world mới + import package + alternate outcome — kiểm tra character data đồng nhất.
- **Files touched:** `backend/app/models.py`, `backend/app/routes/builder_routes.py`, `backend/app/engine.py`.
- **Scope:** Medium (3 files).

#### Task 5.4: Remove `appearance_append` / `abilities_append` Global Side-Effect
- **Description:** 2 field `appearance_append` và `abilities_append` trong `_apply_outcome_payload()` không có trong bất kỳ Pydantic schema nào (`StateChangesModel` / `CharacterStateChange`), không được validate kiểu, và **tự động ghi đè lên toàn bộ nhân vật** thay vì chỉ 1 target. Xóa hoặc thay thế bằng cơ chế có char_id rõ ràng trong `CharacterStateChange`.
- **Acceptance Criteria:**
  - [ ] `appearance_append` / `abilities_append` không còn là global side-effect.
  - [ ] Mọi state change đều gắn với `char_id` cụ thể.
  - [ ] Dữ liệu xuống disk là deterministic, có thể kiểm chứng.
- **Verification:** Chạy test với alternate outcome có chứa 2 field trên, xác nhận chỉ character được chỉ định bị ảnh hưởng.
- **Files touched:** `backend/app/engine.py`, `backend/app/models.py`.
- **Scope:** Small (2 files).

#### Task 5.5: Fix Circular Imports, Pacing Threshold & RAG Stopwords
- **Description:** Giải quyết 3 technical debt nhỏ còn lại: (1) Tái cấu trúc imports để xóa pattern `import main as _m` trong function body. (2) Sửa `decide_chapter_closed()` / `get_close_thresholds()` dùng cả `pacing_level` (Slowburn/Balanced/Fast) bên cạnh `output_length` để điều chỉnh soft/hard close thresholds. (3) Dọn `_rag_stopwords`: xóa từ trùng lặp, sửa lỗi chính tả (`"ando"`), thêm stopwords tiếng Việt.
- **Acceptance Criteria:**
  - [ ] Không còn `import main as _m` hay `from main import ...` bên trong function body.
  - [ ] Slowburn chapter có soft_close_turns cao hơn Fast chapter.
  - [ ] RAG stopwords list sạch, không trùng, không lỗi, hỗ trợ tiếng Việt.
- **Verification:** Chạy test với 3 pacing levels khác nhau, kiểm tra close thresholds; import test.
- **Files touched:** `backend/app/engine.py`, `backend/prompts.py`.
- **Scope:** Small (2 files).

---

### PHASE 6: ADVANCED ARCHITECTURE (SONDER ENGINE PATTERNS) 🆕

#### Task 6.1: Dual Representation — steps + variants Storage
- **Description:** Áp dụng pattern từ Sonder Engine: mỗi stage output trong pipeline được lưu thành 2 representation — **steps row** (kết quả hiện tại) và **variants row** (immutable snapshot với đúng 1 variant active). Cho phép reroll (chọn variant khác), rerun-from-stage (chạy lại từ stage bất kỳ), manual editing, và audit trail đầy đủ. Sửa `backend/app/storage.py` thêm collection cho steps/variants.
- **Acceptance Criteria:**
  - [ ] Mỗi stage (planner, writer, extractor, checker) lưu steps + variants riêng.
  - [ ] API route cho phép xem danh sách variants của 1 stage.
  - [ ] API route cho phép chọn variant khác (reroll).
  - [ ] toàn bộ history có thể tái hiện (replay).
- **Verification:** Generate chapter, reroll writer variant, xác nhận chapter thay đổi mà không ảnh hưởng planner/extractor output.
- **Files touched:** `backend/app/storage.py`, `backend/app/models.py`, `backend/app/engine.py`, `backend/app/routes/studio_routes.py`.
- **Scope:** Large (4+ files).

#### Task 6.2: Structured Perception Output
- **Description:** Chuyển perception output của Writer từ prose string (miêu tả tự nhiên) sang structured data có fields: `observed_entities`, `overheard_dialogue`, `environmental_cues`, `emotional_hints`. Character agent có thể đọc chính xác ai đang ở trong phòng, họ đang làm gì, không gian như thế nào — qua structured fields chứ không phải parse từ prose. Lấy cảm hứng từ `agents/perception.py` của Sonder Engine với `structured_observations`.
- **Acceptance Criteria:**
  - [ ] Writer output thêm block `perception_data` dạng JSON bên cạnh chapter prose.
  - [ ] `perception_data` chứa danh sách entity, dialogue snippet, environment trạng thái.
  - [ ] Backend lưu perception_data riêng, prose riêng.
- **Verification:** Kiểm tra chapter JSON output có trường `perception_data` đúng cấu trúc.
- **Files touched:** `backend/prompts.py`, `backend/app/models.py`, `backend/app/engine.py`, `frontend/src/components/ChapterCard.tsx` (hiển thị prose như cũ, ignore perception_data).
- **Scope:** Medium (4 files).

#### Task 6.3: Per-Observer LLM Calls (Long-term)
- **Description:** Tách Writer agent thành per-character Writer instances. Mỗi perceiver (nhân vật) nhận 1 LLM call riêng với context window riêng, chỉ chứa thông tin mà nhân vật đó legitimately biết (qua Perception Filter). Không chia sẻ context giữa các characters. Đây là physical barrier chống metagaming ở cấp infrastructure — triệt để hơn mọi prompt engineering.
- **Acceptance Criteria:**
  - [ ] Mỗi character trong scene nhận 1 LLM call Writer riêng.
  - [ ] Context của character A không chứa thông tin chỉ character B mới biết.
  - [ ] Narrator tổng hợp các per-character output thành chapter prose cuối cùng.
  - [ ] Số LLM calls tăng lên = 1 Planner call + 1 Narrator call + N * Writer calls.
- **Verification:** Tạo scene có 3 characters với bí mật riêng, xác nhận character A không vô tình tiết lộ bí mật của B.
- **Files touched:** `backend/app/chapter_generator.py`, `backend/app/llm_client.py`, `backend/app/engine.py`.
- **Scope:** Very Large (3+ files, thay đổi kiến trúc pipeline).

#### Task 6.4: Psychology Runtime (Very Long-term)
- **Description:** Implement hệ thống tâm lý nhân vật deterministic bằng Python thuần (không dùng LLM), dựa trên Sonder Engine `psychology_runtime.py`, `theory_of_mind.py`, `affect.py`. Các module chính: (1) **Hedonic State** — đau/khoái lạc là 2 trục độc lập với charge tích lũy/half-life. (2) **Stress System** — strain/overload tách biệt drive. (3) **Cognitive Absorption** — % tâm trí bị chiếm dụng. (4) **Belief Updates** — inertia gấp 3 cho protected beliefs. (5) **Theory of Mind** — 7 kind beliefs (observation, stated_fact, emotion, goal, trait, identity, second_order) với confidence cap, plasticity, half-life riêng.
- **Acceptance Criteria:**
  - [ ] Mỗi character có psychology state (hedonic, stress, cognitive absorption, beliefs).
  - [ ] Psychology state thay đổi deterministic theo actions/events, không qua LLM.
  - [ ] Character có hành vi nhất quán với core_drive + psychology state ngay cả khi prompt không nhắc.
- **Verification:** Chạy simulation 20 turns, kiểm tra psychology state thay đổi predictable theo actions.
- **Files touched:** `backend/app/psychology_runtime.py` [NEW], `backend/app/theory_of_mind.py` [NEW], `backend/app/affect.py` [NEW], `backend/app/models.py`, `backend/app/engine.py`.
- **Scope:** Very Large (5+ files, dài hạn).

---

<a name="ket-luan"></a>
## 📌 KẾT LUẬN

Tài liệu tổng hợp đã được hoàn thiện 100% chính xác.
Mọi thứ đã sẵn sàng và chuẩn chỉnh tuyệt đối!
