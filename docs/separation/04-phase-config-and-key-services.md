# Phase 04 - Config And Key Services

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Tách logic cấu hình và API keys dùng chung ra khỏi `main.py` và `webui/helpers.py`.

## Symbol và file cần chú ý

Nguồn hiện tại:

- `main.py:load_api_keys`
- `webui/helpers.py:load_config`
- `webui/helpers.py:load_api_keys`
- `webui/helpers.py:load_openai_key`
- `webui/helpers.py:_parse_api_file`
- `services/config_service.py:ConfigService`

## Đích cần tạo

Gợi ý file:

- `backend/infrastructure/config/app_config_service.py`
- `backend/infrastructure/config/api_key_service.py`

## Phase nội bộ

### Phase A - Tạo `AppConfigService`

Việc làm:

1. Bọc `services/config_service.py:ConfigService` hoặc tái sử dụng nó.
2. Tạo API dùng chung cho:
   - đọc `config/app.ini`
   - đọc chunk size mặc định
   - đọc model mặc định
   - đọc active provider
   - đọc OpenAI base URL
   - đọc OpenAI model
3. Không để WebUI phải tự parse `configparser` nữa.

### Phase B - Tạo `ApiKeyService`

Việc làm:

1. Chuyển logic `_parse_api_file` sang backend service.
2. Gộp logic đọc:
   - `config/API.txt`
   - `.env` fallback
   - section `GEMINI`
   - section `OPENAI`
3. Tạo method riêng:
   - `load_gemini_keys()`
   - `load_openai_key()`
   - `load_all_keys()`
   - `save_keys(section, keys_text)`

### Phase C - Giữ compatibility cho WebUI

Việc làm:

1. Không xóa ngay hàm trong `webui/helpers.py`.
2. Chuyển chúng thành wrapper mỏng gọi backend service mới.
3. Không đổi tên hàm public ở WebUI phase này.

### Phase D - Giữ compatibility cho CLI

Việc làm:

1. Không để `main.py` tự đọc file keys nữa.
2. Nếu thay đổi, chỉ đổi implementation bên trong, giữ behavior cũ.
3. Nếu cần, tạo wrapper `main.py:load_api_keys` gọi service mới rồi phase sau mới xóa.

## Kiểm tra bắt buộc

- Gemini keys vẫn đọc được.
- OpenAI key vẫn đọc được.
- `config/app.ini` vẫn được đọc đúng.
- Route `/api/provider`, `/api/models`, `/api/openai/models` không gãy.

## Tiêu chí hoàn tất

- Không còn logic parse API file bị nhân bản ở nhiều nơi.
- WebUI helpers và CLI chỉ còn gọi backend config/key services.

## Không được chuyển phase nếu

- Còn hơn một nơi parse trực tiếp `config/API.txt`.
- WebUI settings routes còn tự xử lý quá sâu với `configparser`.
