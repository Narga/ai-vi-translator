# Phase 11 - Project Translation Use Case

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Tách flow dịch file theo project ra khỏi `webui/routes/projects.py` thành use case độc lập.

## Symbol và file cần xử lý

- `webui/routes/projects.py:translate_project_file`
- `webui/routes/projects.py:_project_translate_worker`
- `core/executor.py:TranslationExecutor`

## Vấn đề hiện tại

Route project translation đang tự làm:

- load project meta
- load prompts
- load assets context
- resolve glossary paths
- create `TranslationMemory`
- lặp file
- emit progress
- update translation_result
- save meta

Đây là orchestration nghiệp vụ điển hình phải đưa về backend.

## File đích nên tạo

- `backend/application/use_cases/translate_project_files_use_case.py`
- `backend/application/dto/project_translation_request.py`
- `backend/application/dto/project_translation_result.py`

## Phase nội bộ

### Phase A - Tách request DTO

Request nên chứa:

- `project_slug`
- `files`
- `model`
- `temperature`
- `chunk_size`
- `use_cache`

### Phase B - Tách project prompt resolution

Việc làm:

1. Prompt global + prompt project + assets context phải được resolve trong backend.
2. Không để route tự mở file prompt/asset nữa.

### Phase C - Tách TM và glossary resolution

Việc làm:

1. `TranslationMemory` project-level phải được khởi tạo trong use case.
2. `glossary.txt`, `relationship.txt`, `style_guide.txt` phải được resolve trong backend.

### Phase D - Tách vòng lặp multi-file

Việc làm:

1. Use case chịu trách nhiệm loop qua file.
2. Event `file_complete` và `complete` phải phát từ backend contract.
3. Route chỉ nhận request và khởi thread/use case.

### Phase E - Tách cập nhật project meta

Việc làm:

1. `updated_at`
2. thống kê sau dịch
3. output path state

Các phần này đi về project service hoặc use case kết thúc.

## Kiểm tra bắt buộc

- Dịch nhiều file trong project vẫn hoạt động.
- Translation memory project-level vẫn dùng được.
- Frontend vẫn thấy tiến trình và kết quả cuối như cũ.

## Lệnh kiểm tra mẫu

Trước khi sửa:

```bash
npx gitnexus impact --repo Novel-Translator translate_project_file
npx gitnexus impact --repo Novel-Translator _project_translate_worker
npx gitnexus impact --repo Novel-Translator TranslationExecutor
```

Sau khi sửa:

```bash
python -c "from webui import create_app; app = create_app(); print(app.name)"
python -c "from webui.routes.projects import projects_bp; print(projects_bp.name)"
python -c "from backend.application.use_cases.translate_project_files_use_case import TranslateProjectFilesUseCase; print(TranslateProjectFilesUseCase.__name__)"
```

## Rollback và điều kiện dừng

Dừng ngay nếu:

- Multi-file translation không còn phát `file_complete`.
- Project translation không còn dùng project-level translation memory.
- Route phải biết chi tiết prompt/assets/glossary path sau khi refactor.
- Metadata `updated_at` không còn được cập nhật sau khi dịch xong.

Rollback:

1. Khôi phục worker nội bộ cũ nếu use case project chưa xử lý đủ events.
2. Giữ prompt/assets resolution cũ trong route cho tới khi backend service pass smoke check.
3. Không tách project file operations trong cùng lượt.

## Tiêu chí hoàn tất

- `translate_project_file` chỉ còn là controller.
- Business logic project translation nằm trong backend use case.
