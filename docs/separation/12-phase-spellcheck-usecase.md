# Phase 12 - Spellcheck Use Case

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Tách flow spellcheck project ra khỏi `webui/routes/projects.py` thành use case song song với translation.

## Symbol và file cần xử lý

- `webui/routes/projects.py:spellcheck_project_file`
- worker spellcheck nội bộ của route
- `core/spellcheck_executor.py:SpellcheckExecutor`

## Vấn đề hiện tại

Route spellcheck đang tự làm:

- load prompt spellcheck
- fallback prompt mặc định
- load style guide
- replace placeholders
- resolve glossary/paths
- loop files
- dựng executor
- phát progress

Logic này phải được gom về backend giống translation.

## File đích nên tạo

- `backend/application/use_cases/spellcheck_project_files_use_case.py`
- `backend/application/dto/spellcheck_request.py`
- `backend/application/dto/spellcheck_result.py`

## Phase nội bộ

### Phase A - Tạo request/output DTO

Input:

- `project_slug`
- `files`
- `model`
- `temperature`
- `chunk_size`
- `use_cache`

Output:

- `clean_texts`
- `error_logs`
- `output_paths`
- `processed_files`

### Phase B - Tách prompt assembly

Nguồn hiện tại:

- `webui/routes/projects.py:spellcheck_project_file`

Việc làm:

1. Prompt spellcheck phải được resolve bởi backend service.
2. Placeholder như `{translation_guidelines}` phải được thay thế ở backend.

### Phase C - Tách loop và output handling

Việc làm:

1. Use case thực hiện loop file.
2. Route không tự dựng `SpellcheckExecutor` nữa.
3. Output lưu file phải do backend service/use case xử lý.

### Phase D - Chuẩn hóa event contract

Việc làm:

1. Spellcheck dùng cùng progress event contract như translation.
2. Nếu thiếu field, thêm qua metadata thay vì tạo shape hoàn toàn khác.

## Kiểm tra bắt buộc

- Spellcheck một file và nhiều file vẫn chạy.
- Error log và clean text vẫn được tách đúng.
- Frontend nút spellcheck không gãy.

## Lệnh kiểm tra mẫu

Trước khi sửa:

```bash
npx gitnexus impact --repo Novel-Translator spellcheck_project_file
npx gitnexus impact --repo Novel-Translator SpellcheckExecutor
```

Sau khi sửa:

```bash
python -c "from core.spellcheck_executor import SpellcheckExecutor; print(SpellcheckExecutor.__name__)"
python -c "from webui import create_app; app = create_app(); print(app.name)"
python -c "from backend.application.use_cases.spellcheck_project_files_use_case import SpellcheckProjectFilesUseCase; print(SpellcheckProjectFilesUseCase.__name__)"
```

## Rollback và điều kiện dừng

Dừng ngay nếu:

- Spellcheck result không còn tách được `clean_text` và `error_log`.
- Placeholder `{translation_guidelines}` không còn được thay thế.
- Route đổi response shape khiến frontend không nhận được kết quả.
- `SpellcheckExecutor.execute()` phải đổi signature ngoài kế hoạch.

Rollback:

1. Giữ `SpellcheckExecutor` nguyên signature cũ.
2. Khôi phục prompt assembly trong route nếu backend prompt assembly chưa đúng.
3. Không gộp spellcheck với translation use case.

## Tiêu chí hoàn tất

- Spellcheck đã có use case riêng.
- Route spellcheck không còn mang orchestration chính.
