# Implementation Plan: Story Engine Master Plan Upgrade

## Overview
Kế hoạch triển khai nâng cấp toàn diện `story-engine` dựa trên 4 Nhóm công việc trong `story-engine-master-plan.md`, tích hợp kiến trúc an toàn từ **Sonder Engine alpha6.0.1** (Deterministic Commit, Perception Filter, Core Drive) và kỹ thuật prompt từ **Book-OS** (Context 3 tầng, Scene-and-Sequel Friction).

## Architecture Decisions
1. **Official Pydantic Source of Truth (`backend/app/models.py`):** Sử dụng `backend/app/models.py` làm file định nghĩa duy nhất cho mọi Pydantic models (`CharacterModel`, `StateChangesModel`, `CheckpointModel`, `CardModel`, v.v.).
2. **Deterministic Commit Boundary (`commit_sanitizer.py`):** Viết lớp kiểm tra/ép kiểu dữ liệu bằng code Python trước khi ghi xuống đĩa, không tin tưởng 100% output của LLM Extractor/Builder.
3. **Zone Prefix Boundary Matching:** Cho phép di chuyển trong cùng khu vực lớn mà không bị coi là vi phạm boundary (`"Valdris Estate - Kitchen"` hợp lệ với `"Valdris Estate"`).
4. **Normalized Coordinates (0-100) for `location_map.json`:** Sử dụng tọa độ chuẩn hóa để Frontend tự động scale theo mọi màn hình thiết bị.
5. **React Flow for Network Graph (`@xyflow/react`):** Sử dụng React Flow cho tab Codex Affinity Network (Phase 4) nhờ hỗ trợ React-native declarative nodes, zoom/pan tự động và kéo thả layout trực quan.

---

## Task List

### Phase 1: Critical Bug Fixes & Commitment Safety Net (Nhóm 1)
- [ ] **Task 1.1:** Revert `checkpoint_conditions_met()` logic thật & Auto-Advance `current_checkpoint_id` khi confirm prelude.
- [ ] **Task 1.2:** Implement Defensive Condition Sanitizer & Sửa `WORLD_BUILDER_SKELETON_PROMPT` liệt kê valid paths.
- [ ] **Task 1.3:** Early Safety Net cho Checkpoint Boundary rỗng & Ép kiểu string cho `relationships` trong `builder_routes.py`.
- [ ] **Task 1.4:** Fix Codex Affinity Network Backend API (`world_routes.py`) & Vanilla JS Frontend Fix (đọc đúng field `relationships`).

### Checkpoint: Phase 1 Bug Fixes
- [ ] Tất cả unit test `test_engine.py` pass.
- [ ] World creation sinh out JSON sạch, `relationships` không bị object lồng nhau.
- [ ] Prelude confirm chuyển checkpoint mượt mà sang `cp_1`.

### Phase 2: Checkpoint Redesign & Narrative Friction (Nhóm 2 & 4.1)
- [ ] **Task 2.1:** Implement Zone Prefix Matching & Softer Boundary Correction Notes trong `engine.py`.
- [ ] **Task 2.2:** Nâng cấp `PLANNER_SYSTEM_PROMPT` hỗ trợ Scene-and-Sequel Friction (`narrative_friction`).

### Checkpoint: Phase 2 Narrative Redesign
- [ ] Di chuyển giữa các sub-location trong cùng zone không bị vi phạm boundary.
- [ ] Turn truyện diễn ra kịch tính, có ma sát/trở ngại rõ ràng.

### Phase 3: Spatial Location Map System (Nhóm 3)
- [ ] **Task 3.1:** Định nghĩa `location_map.json` model trong `backend/app/models.py` (tọa độ 0-100) & Generator sinh map từ mô tả thế giới.
- [ ] **Task 3.2:** Tích hợp Map-based Boundary Check (thông báo rõ lý do khu vực bị khóa theo EXP/Realm).

### Checkpoint: Phase 3 Location Map
- [ ] File `location_map.json` được tạo thành công cho world mới.
- [ ] Logic unlock phản hồi chính xác theo chỉ số EXP/Realm của nhân vật.

### Phase 4: Frontend React TypeScript Migration & UI Separation (Nhóm 4.2)
- [ ] **Task 4.1:** Initialize Vite + React + TypeScript Frontend Project & API Client setup.
- [ ] **Task 4.2:** Build Separated UI Components (Status Panel, Inventory Grid, Skills) & Codex Affinity Graph bằng React Flow (`@xyflow/react`).
- [ ] **Task 4.3:** Interactive Location Map Tab Component (Canvas/SVG rendering với Fog of War & Tọa độ 0-100).

### Checkpoint: Phase 4 Complete
- [ ] Giao diện hiển thị sắc nét, chuyên nghiệp, Type-Safe 100%.
- [ ] Người chơi theo dõi được bản đồ và đồ thị quan hệ minh bạch bằng React Flow.

### Phase 5: Technical Debt & Backend Refactoring 🆕
- [ ] **Task 5.1:** Decompose `engine.py` (~2755 dòng) → `llm_client.py`, `chapter_generator.py`, `checkpoint_engine.py`, `state_manager.py`, `rag.py`, `language_detection.py`.
- [ ] **Task 5.2:** Fix Write Order — Cross-check trước khi ghi disk (staging commit).
- [ ] **Task 5.3:** Centralize `normalize_character()` vào 1 hàm duy nhất, 3 nơi gọi chung.
- [ ] **Task 5.4:** Xóa `appearance_append` / `abilities_append` global side-effect.
- [ ] **Task 5.5:** Fix circular imports (`import main as _m`), pacing threshold (dùng `pacing_level`), RAG stopwords (dọn trùng + thêm tiếng Việt).

### Checkpoint: Phase 5 Technical Debt
- [ ] `engine.py` giảm còn ≤ 600 dòng orchestration, mỗi module mới unit-testable độc lập.
- [ ] Disk write an toàn: cross-check pass mới commit, fail thì rollback.
- [ ] `normalize_character()` tập trung 1 nơi, thêm field mới chỉ sửa 1 chỗ.
- [ ] Không còn global side-effect, không còn `import main as _m`.

### Phase 6: Advanced Architecture (Sonder Engine Patterns) 🆕
- [ ] **Task 6.1:** Dual Representation (steps + variants) cho audit trail, reroll, rerun-from-stage.
- [ ] **Task 6.2:** Structured Perception Output (`perception_data` JSON bên cạnh prose).
- [ ] **Task 6.3:** Per-Observer LLM Calls (mỗi character 1 LLM call riêng) — dài hạn.
- [ ] **Task 6.4:** Psychology Runtime (hedonic state, stress, cognitive absorption, belief updates, Theory of Mind) — rất dài hạn.

### Checkpoint: Phase 6 Advanced Architecture
- [ ] Mỗi stage output có steps + variants, có thể reroll/replay.
- [ ] Perception data là structured JSON, không chỉ prose.
- [ ] Per-character Writer calls với context riêng (physical anti-metagaming barrier).
- [ ] Psychology state deterministic, character hành xử nhất quán không cần prompt nhắc.
