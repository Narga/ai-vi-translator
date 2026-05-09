# Phase 01 - Baseline Inventory

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Đóng băng hiện trạng trước khi tách lớp để mọi refactor sau này đều có điểm so sánh rõ ràng.

## Không sửa gì ở phase này

- Không đổi logic nghiệp vụ.
- Không đổi response JSON.
- Không đổi tham số CLI.
- Chỉ thêm tài liệu, danh sách kiểm kê, và nếu cần thì script đọc hiện trạng không can thiệp hệ thống.

## Phạm vi kiểm kê bắt buộc

### CLI

Kiểm kê file:

- `cli.py`
- `main.py`

Kiểm kê function/class:

- `cli.py:NovelTranslatorCLI`
- `cli.py:NovelTranslatorCLI._create_parser`
- `cli.py:NovelTranslatorCLI._handle_translate`
- `cli.py:NovelTranslatorCLI._handle_status`
- `cli.py:NovelTranslatorCLI._handle_resume`
- `cli.py:NovelTranslatorCLI._handle_serve`
- `main.py:main`
- `main.py:load_api_keys`
- `main.py:load_prompts`
- `main.py:find_input_files`
- `main.py:merge_small_files`

### WebUI

Kiểm kê file:

- `webui.py`
- `webui/__init__.py`
- `webui/helpers.py`
- `webui/routes/translation.py`
- `webui/routes/settings.py`
- `webui/routes/prompts.py`
- `webui/routes/projects.py`
- `webui/routes/plugins.py`
- `webui/static/js/main.js`

Kiểm kê route groups:

- Translation routes
- Settings routes
- Prompt-set routes
- Project CRUD routes
- Project translation/spellcheck routes
- Translation memory routes
- Plugin routes

### Core và services

Kiểm kê file:

- `core/executor.py`
- `core/spellcheck_executor.py`
- `services/config_service.py`
- `services/api_service.py`
- `services/cache_service.py`
- `services/checkpoint_service.py`
- `services/glossary_service.py`
- `services/translation_memory.py`
- `services/ai_provider.py`
- `services/openai_client.py`
- `services/genai_client.py`

## Phase nội bộ

### Phase A - Lập bản đồ entrypoint

Việc làm:

1. Ghi lại CLI commands hiện có trong `cli.py`.
2. Ghi lại CLI options mà `main.py` đang thực sự hiểu.
3. Ghi lại các route Flask đang public trong `webui/routes/*.py`.
4. Ghi lại frontend actions chính từ `webui/static/js/main.js`.

Đầu ra:

- `docs/separation/artifacts/cli-command-inventory.md`
- `docs/separation/artifacts/webui-route-inventory.md`
- `docs/separation/artifacts/frontend-action-inventory.md`

### Phase B - Lập bản đồ dependency

Việc làm:

1. Ghi nơi `cli.py` gọi `main.py`.
2. Ghi nơi `main.py` dùng `webui.helpers`.
3. Ghi nơi `core/executor.py` import `webui.helpers`.
4. Ghi nơi routes tự dựng config, prompts, glossary, output path.

Đầu ra:

- `docs/separation/artifacts/current-couplings.md`

### Phase C - Lập bản đồ hành vi public

Việc làm:

1. Chụp help text của CLI.
2. Ghi response shape hiện tại của các route quan trọng:
   - `/api/translate`
   - `/api/progress`
   - `/api/translate-text`
   - `/api/projects/<slug>/translate`
   - `/api/projects/<slug>/spellcheck`
   - `/api/models`
   - `/api/provider`
3. Ghi progress event types hiện có:
   - `progress`
   - `info`
   - `complete`
   - `error`
   - `file_complete`
   - `ping`

Đầu ra:

- `docs/separation/artifacts/public-behavior-baseline.md`

## Lưu ý cho model thực hiện

- Nếu phải đọc code, chỉ đọc và ghi chép.
- Không được “tiện tay” tối ưu code ở phase này.
- Nếu phát hiện bug, chỉ ghi vào tài liệu, không sửa.

## Tiêu chí hoàn tất

- Có tài liệu kiểm kê đủ CLI, WebUI, core/services.
- Có danh sách coupling hiện tại.
- Có mô tả hành vi public để đối chiếu các phase sau.

## Không được chuyển phase nếu

- Chưa lập xong inventory route.
- Chưa ghi rõ các điểm import chéo giữa CLI, core, WebUI.
