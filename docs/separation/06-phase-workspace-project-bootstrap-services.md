# Phase 06 - Workspace Project Bootstrap Services

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Tách logic workspace và bootstrap project ra khỏi WebUI để CLI cũng dùng cùng một nguồn.

## Symbol và file cần xử lý

Nguồn hiện tại:

- `webui/helpers.py:ensure_default_project`
- `main.py:find_input_files`
- `main.py:merge_small_files`
- các helper private trong `webui/routes/projects.py` như:
  - `_get_project_dir`
  - `_load_project_meta`
  - `_save_project_meta`

## Đích cần tạo

Gợi ý file:

- `backend/infrastructure/workspace/workspace_service.py`
- `backend/infrastructure/workspace/project_service.py`
- `backend/infrastructure/workspace/file_discovery_service.py`

## Phase nội bộ

### Phase A - Tạo `WorkspaceService`

API gợi ý:

- `ensure_default_project()`
- `get_workspace_root()`
- `get_projects_root()`
- `get_logs_dir()`
- `get_cache_dir()`
- `get_checkpoints_dir()`

### Phase B - Tạo `ProjectService`

API gợi ý:

- `get_project_dir(slug)`
- `project_exists(slug)`
- `load_project_meta(slug)`
- `save_project_meta(slug, meta)`
- `list_projects()`

Lưu ý:

- Phase này chỉ di chuyển helper trước.
- Chưa chuyển toàn bộ CRUD project lớn ra khỏi routes.

### Phase C - Tạo `FileDiscoveryService`

API gợi ý:

- `find_input_files(input_dir)`
- `merge_small_files(files, min_chunk_size)`

Nguồn:

- `main.py:find_input_files`
- `main.py:merge_small_files`

### Phase D - Chuyển các caller đầu tiên

Caller ưu tiên:

- `main.py`
- `webui/__init__.py`
- các helper đầu route trong `webui/routes/projects.py`

## Kiểm tra bắt buộc

- Default project vẫn được tạo.
- CLI vẫn tìm input files như cũ.
- WebUI project routes vẫn đọc meta đúng.

## Tiêu chí hoàn tất

- Bootstrap workspace/project không còn phụ thuộc vào WebUI helpers.
- `main.py` và WebUI cùng dùng chung workspace/project backend service.
