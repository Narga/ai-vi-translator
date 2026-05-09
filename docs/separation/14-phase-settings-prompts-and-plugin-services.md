# Phase 14 - Settings Prompts And Plugin Services

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Hoàn tất việc chuyển logic settings, prompt-set, và plugin orchestration còn lại ra backend dùng chung.

## File trọng tâm

- `webui/routes/settings.py`
- `webui/routes/prompts.py`
- `webui/routes/plugins.py`

## Nhóm cần xử lý

### Nhóm 1 - Settings

Bao gồm:

- models
- provider
- openai config
- model info
- estimate tokens
- config
- stats
- cache clear
- logs
- app settings

### Nhóm 2 - Prompt sets

Bao gồm:

- list prompt sets
- get one prompt set
- create/update/delete
- apply prompt set

### Nhóm 3 - Plugins

Bao gồm:

- EPUB converter
- OCR
- plugin progress
- plugin list

## File đích nên tạo

Gợi ý:

- `backend/application/use_cases/settings/`
- `backend/application/use_cases/prompt_sets/`
- `backend/application/use_cases/plugins/`

## Phase nội bộ

### Phase A - Tách settings services

Việc làm:

1. Model/provider/settings/config/log/cache actions phải đi qua backend service.
2. Route chỉ map request và response.

### Phase B - Tách prompt-set services

Việc làm:

1. CRUD prompt sets đi về service riêng.
2. Logic apply prompt set vào project cũng đi về service.

### Phase C - Tách plugin orchestration

Việc làm:

1. Nếu plugin action không phụ thuộc GUI, orchestration phải ở backend.
2. Route plugins chỉ còn là transport.
3. Chuẩn hóa progress cho plugin nếu có thể.

## Kiểm tra bắt buộc

- Settings UI vẫn dùng được.
- Prompt-set CRUD không gãy.
- Plugin endpoints vẫn hoạt động.

## Tiêu chí hoàn tất

- Ba route modules trên đều trở thành adapter/controller mỏng.
