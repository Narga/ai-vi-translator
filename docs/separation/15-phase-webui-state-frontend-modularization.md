# Phase 15 - WebUI State And Frontend Modularization

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Sau khi backend đã tách ổn, làm sạch adapter WebUI và chia nhỏ frontend mà không ảnh hưởng behavior.

## File trọng tâm

- `webui/__init__.py`
- `webui.py`
- `webui/static/js/main.js`
- `webui/templates/*.html`

## Vấn đề hiện tại

- `webui/__init__.py` giữ state toàn cục:
  - `progress_queue`
  - `translation_result`
  - `translation_stats`
  - `translation_memory`
- `webui/static/js/main.js` rất lớn và ôm hầu hết toàn bộ UI behavior.

## Mục tiêu cụ thể

- Flask app chỉ giữ app wiring.
- State runtime của translation/spellcheck có chỗ quản lý rõ ràng hơn.
- Frontend JS được tách module theo màn hình/chức năng.

## Phase nội bộ

### Phase A - Tách state runtime khỏi `webui/__init__.py`

Việc làm:

1. Tạo module state riêng, ví dụ:
   - `interfaces/webapi/runtime_state.py`
2. Chuyển:
   - `progress_queue`
   - `translation_result`
   - `translation_stats`
   - `translation_memory`
3. `create_app()` chỉ lo register blueprint và config app.

### Phase B - Làm mỏng `webui.py`

Việc làm:

1. Giữ `webui.py` là launcher thuần.
2. Retry logic port có thể giữ, nhưng không thêm business logic.

### Phase C - Chia `webui/static/js/main.js`

Chia theo module:

- `api-client.js`
- `app-state.js`
- `translation-ui.js`
- `project-ui.js`
- `spellcheck-ui.js`
- `settings-ui.js`
- `prompts-ui.js`
- `plugin-ui.js`

Lưu ý:

- Phase này không đổi giao diện lớn.
- Không rewrite framework.
- Chỉ tách module tuần tự.

### Phase D - Chuẩn hóa API calls frontend

Việc làm:

1. Tập trung mọi `fetch` vào một lớp API client.
2. Không để mỗi nút UI tự xử lý response shape riêng quá nhiều.

### Phase E - Final hardening

Việc làm:

1. Rà lại tất cả adapter.
2. Loại bỏ wrapper tương thích ngược không còn cần.
3. Chạy GitNexus detect changes trước khi commit.
4. Cập nhật docs architecture nếu cần.

## Kiểm tra bắt buộc

- WebUI vẫn boot được.
- Các tab chính vẫn chạy:
  - Workspace
  - Prompt/Thông tin
  - Translation
  - Spellcheck
  - Settings
- Không có regression lớn ở progress và actions chính.

## Tiêu chí hoàn tất

- Backend, CLI adapter, WebUI adapter, frontend state được phân lớp rõ.
- Mọi tính năng nghiệp vụ chính có một nơi thực thi duy nhất ở backend.
