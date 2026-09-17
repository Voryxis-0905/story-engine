# Todo Checklist: Story Engine Master Plan Upgrade

## Phase 1: Critical Bug Fixes & Commitment Safety Net ✅
- [x] **Task 1.1:** Revert `checkpoint_conditions_met()` logic thật & Auto-Advance `current_checkpoint_id` khi confirm prelude.
- [x] **Task 1.2:** Implement Defensive Condition Sanitizer & Sửa `WORLD_BUILDER_SKELETON_PROMPT` liệt kê valid paths.
- [x] **Task 1.3:** Early Safety Net cho Checkpoint Boundary rỗng & Ép kiểu string cho `relationships` trong `builder_routes.py`.
- [x] **Task 1.4:** Fix Codex Affinity Network Backend API (`world_routes.py`) & Vanilla JS Frontend Fix (đọc đúng field `relationships`).

## Phase 2: Checkpoint Redesign & Narrative Friction ✅
- [x] **Task 2.1:** Implement Zone Prefix Matching & Softer Boundary Correction Notes trong `engine.py`.
- [x] **Task 2.2:** Nâng cấp `PLANNER_SYSTEM_PROMPT` hỗ trợ Scene-and-Sequel Friction (`narrative_friction`).

## Phase 3: Spatial Location Map System ✅
- [x] **Task 3.1:** Định nghĩa `location_map.json` model trong `backend/app/models.py` (tọa độ 0-100) & Generator sinh map từ mô tả thế giới.
- [x] **Task 3.2:** Tích hợp Map-based Boundary Check (thông báo rõ lý do khu vực bị khóa theo EXP/Realm).

## Phase 4: Frontend React TypeScript Migration & UI Separation
- [ ] **Task 4.1:** Initialize Vite + React + TypeScript Frontend Project & API Client setup.
- [ ] **Task 4.2:** Build Separated UI Components & Codex Affinity Graph bằng React Flow (`@xyflow/react`).
- [ ] **Task 4.3:** Interactive Location Map Tab Component (Canvas/SVG rendering với Fog of War & Tọa độ 0-100).

## Phase 5: Technical Debt & Backend Refactoring ✅
- [x] **Task 5.1:** Decompose `engine.py` → `llm_client.py`, `chapter_generator.py`, `checkpoint_engine.py`, `state_manager.py`, `rag.py`, `language_detection.py`.
- [x] **Task 5.2:** Fix Write Order — Cross-check trước khi ghi disk (`commit_sanitizer.py` + atomic write).
- [x] **Task 5.3:** Centralize `normalize_character()` → `normalize_character_dict()` dùng chung 3 nơi.
- [x] **Task 5.4:** Xóa `appearance_append` / `abilities_append` global side-effect (scope theo target character).
- [x] **Task 5.5:** Fix circular imports, pacing threshold (`decide_chapter_closed` dùng `pacing_level`), RAG stopwords (dedup + xóa typo).

## Phase 6: Advanced Architecture (Sonder Engine Patterns) ✅
- [x] **Task 6.1:** Dual Representation (steps + variants) cho audit trail & reroll.
- [x] **Task 6.2:** Structured Perception Output (`perception_data` JSON).
- [x] **Task 6.3:** Per-Observer LLM Calls (mỗi character 1 call riêng) — dài hạn.
- [x] **Task 6.4:** Psychology Runtime (hedonic, stress, belief, Theory of Mind) — rất dài hạn.

## Phase 7: UI Redesign & Full Backend Sync ✅
> Rebuilt React UI according to multi-page architecture with Airi-inspired dark tech design system.

### Kiến trúc tổng thể
- 3 trang chính dùng React Router: **Home**, **Worlds**, **Chat**
- Multi-page React UI với `@phosphor-icons/react`, `@xyflow/react` và Tailwind CSS v4

### Trang Home (`/`)
- [x] **Task 7.1:** Logo + tagline. 3 nav card: "Gen World", "Worlds", "Settings".

### Trang Worlds (`/worlds`)
- [x] **Task 7.2:** Danh sách worlds dạng cards/table — mỗi hàng có tên world + action buttons bên phải (export, settings, file, delete).
- [x] **Task 7.3:** Action "Gen World" mở Builder flow (interview → builder steps → prelude → confirm).

### Trang Chat (`/worlds/:name/play`)
- [x] **Task 7.4:** **Left sidebar** (collapsible) — World State: mùa, thời gian, năm/ngày, địa điểm hiện tại, arc progress bar.
- [x] **Task 7.5:** **Center** — Narrative scroll area (prose text) + input bar "What do you do?" ở bottom. Pacing/Length controls nhỏ gọn phía trên.
- [x] **Task 7.6:** **Right icon strip** — 6 icon button nhỏ dọc theo cạnh phải mở slide-in panel:
  - 🎒 Inventory (unlocked cards — items)
  - 🗺 Map (LocationMap canvas)
  - 📖 Codex (lore cards + Affinity Graph React Flow)
  - 👤 Status (character card)
  - ⚔ Skills (known_skills)
  - 🔮 Foreshadowing tracker
- [x] **Task 7.7:** Prelude flow: nếu world chưa có chapters → màn prelude trước khi vào chat.

### Trang Settings (`/settings`)
- [x] **Task 7.8:** API Key config (PUT /runtime-config, test connection).

### Creator Tools (trong Worlds page, per-world)
- [x] **Task 7.9:** Per-world menu: Saves (save/restore/branch), Style Card, Traits, Canon Log, Export Story, Fork.

### API Client
- [x] **Task 7.10:** Bổ sung toàn bộ endpoints còn thiếu: builder, creator, studio, config, saves, traits, foreshadowings, affinity graph.
