# Phase 13 - Project Service Decomposition

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Bẻ nhỏ `webui/routes/projects.py` theo nhóm nghiệp vụ để route chỉ còn vai trò transport.

Phase này không được thực hiện như một thay đổi đơn lẻ. Phải thực hiện tuần tự qua 5 sub-plan:

1. [13a-project-crud-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13a-project-crud-service-plan.md)
2. [13b-project-file-operations-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13b-project-file-operations-service-plan.md)
3. [13c-project-prompts-assets-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13c-project-prompts-assets-service-plan.md)
4. [13d-project-archive-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13d-project-archive-service-plan.md)
5. [13e-project-translation-memory-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13e-project-translation-memory-service-plan.md)

## File trọng tâm

- `webui/routes/projects.py`

## Vì sao phase này lớn nhưng phải đi muộn

File này dài và chứa nhiều nghiệp vụ. Nếu làm sớm hơn các phase translation/spellcheck/config/workspace thì sẽ dễ rối và dễ đụng nhiều behavior cùng lúc.

## Nhóm chức năng cần tách

### Nhóm 1 - Project CRUD

Route ví dụ:

- `/api/projects`
- `/api/projects/<slug>`

### Nhóm 2 - File operations

Route ví dụ:

- read file
- update file
- delete file
- upload
- rename
- move-done
- move-back
- merge
- chunk

### Nhóm 3 - Prompt/guideline/project asset

Route ví dụ:

- project prompts
- import prompts
- guidelines
- summarize project

### Nhóm 4 - Archive

Route ví dụ:

- archive project
- list archive
- restore archive
- delete archive artifact

### Nhóm 5 - Translation Memory

Route ví dụ:

- `/api/tm/stats`
- `/api/tm/find`
- `/api/tm/add`
- `/api/tm/clear`
- `/api/tm/export`
- `/api/tm/import`

## File đích nên tạo

Gợi ý:

- `backend/application/use_cases/project_crud/`
- `backend/application/use_cases/project_files/`
- `backend/application/use_cases/project_prompts/`
- `backend/application/use_cases/project_archive/`
- `backend/application/use_cases/project_tm/`

## Phase nội bộ

### Phase A - Tách project CRUD

Thực hiện theo [13a-project-crud-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13a-project-crud-service-plan.md).

### Phase B - Tách file operations

Thực hiện theo [13b-project-file-operations-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13b-project-file-operations-service-plan.md).

### Phase C - Tách prompts và guideline assets

Thực hiện theo [13c-project-prompts-assets-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13c-project-prompts-assets-service-plan.md).

### Phase D - Tách archive

Thực hiện theo [13d-project-archive-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13d-project-archive-service-plan.md).

### Phase E - Tách translation memory APIs

Thực hiện theo [13e-project-translation-memory-service-plan.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/13e-project-translation-memory-service-plan.md).

## Kiểm tra bắt buộc

- Mỗi nhóm route vẫn trả JSON như cũ.
- Không có route nào trực tiếp mở quá nhiều file hoặc chứa business logic dài.

## Tiêu chí hoàn tất

- `webui/routes/projects.py` giảm đáng kể kích thước.
- Business logic chính đã đi vào backend services/use cases riêng.
