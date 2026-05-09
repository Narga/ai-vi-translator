# Phase 05 - Prompt Provider Model Services

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Tách logic prompts, provider selection, model discovery ra khỏi `webui/helpers.py` để CLI và WebUI cùng dùng.

## Symbol và file cần xử lý

Nguồn hiện tại:

- `main.py:load_prompts`
- `webui/helpers.py:get_default_chunk_size`
- `webui/helpers.py:get_default_model`
- `webui/helpers.py:get_active_provider`
- `webui/helpers.py:get_openai_base_url`
- `webui/helpers.py:get_openai_model`
- `webui/helpers.py:get_available_models`
- `webui/helpers.py:get_available_gemini_models`
- `webui/helpers.py:get_available_openai_models`
- `webui/routes/settings.py:get_models`
- `webui/routes/settings.py:manage_provider`

## Đích cần tạo

Gợi ý file:

- `backend/infrastructure/config/prompt_service.py`
- `backend/infrastructure/providers/provider_service.py`
- `backend/infrastructure/providers/model_catalog_service.py`

## Phase nội bộ

### Phase A - Tạo `PromptService`

Việc làm:

1. Chuyển logic load prompts mặc định từ `main.py` và `webui/helpers.py`.
2. Chuẩn hóa nơi đọc:
   - global prompts
   - project prompts
3. Tạo API rõ ràng:
   - `load_global_prompts()`
   - `load_project_prompts(project_dir)`
   - `save_global_prompts(prompts)`
   - `merge_project_with_global_prompts(project_dir)`

### Phase B - Tạo `ProviderService`

Việc làm:

1. Bọc logic active provider vào service riêng.
2. Tạo API:
   - `get_active_provider()`
   - `set_active_provider(provider)`
   - `get_openai_runtime_config()`

### Phase C - Tạo `ModelCatalogService`

Việc làm:

1. Chuyển logic list models về service riêng.
2. Tách rõ:
   - fallback models
   - fetch models động từ provider
3. Tạo API:
   - `get_models(provider, full=False)`
   - `get_default_model()`

### Phase D - Chuyển settings route sang service

File đích:

- `webui/routes/settings.py`

Việc làm:

1. `get_models()` gọi service mới thay vì tự xử lý.
2. `manage_provider()` gọi service mới.
3. Giữ nguyên shape response JSON.

## Kiểm tra bắt buộc

- WebUI lấy model list như cũ.
- Chuyển provider vẫn lưu được vào config.
- CLI vẫn lấy prompts và model mặc định như cũ.

## Tiêu chí hoàn tất

- `webui/helpers.py` không còn là nơi cài logic provider/model/prompt chính.
- Prompt, provider, model đã có service riêng trong backend.
