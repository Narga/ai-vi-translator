# Phase 08 - Translation Use Case Shell

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Tạo lớp use case dịch dùng chung, nhưng chưa dời hết logic caller ngay trong một bước.

## Symbol và blast radius cần chú ý

Trước khi sửa symbol nghiệp vụ, phải chạy GitNexus impact cho:

- `TranslationExecutor`
- `main`
- `translate_worker`
- `_project_translate_worker`

Hiện trạng GitNexus đã cho thấy `TranslationExecutor` có risk `MEDIUM`, nên phase này phải làm theo kiểu bọc ngoài trước, chưa mổ lớn vào executor ngay.

## File đích nên tạo

- `backend/application/use_cases/translate_text_use_case.py`
- `backend/application/use_cases/translate_file_use_case.py`

## Ý tưởng

Use case mới sẽ:

1. Nhận input DTO chuẩn.
2. Chuẩn hóa config/prompts/glossary/output path.
3. Gọi `TranslationExecutor`.
4. Trả output chuẩn.

## Phase nội bộ

### Phase A - Tạo input/output DTO

Input DTO nên chứa:

- `text`
- `output_filename`
- `output_file_path`
- `project_slug`
- `model_name`
- `qa_model`
- `temperature`
- `chunk_size`
- `use_cache`
- `prompts`
- `context_char_count`
- `glossary_paths`

Output DTO nên chứa:

- `translated_text`
- `output_path`
- `chunks`
- `cached`
- `tm_hits`
- `tokens_used`

### Phase B - Bọc `TranslationExecutor`

Việc làm:

1. Không thay đổi thuật toán chunking/dịch.
2. Tạo use case gọi `TranslationExecutor.translate_text()`.
3. Tất cả config assembly đi vào use case, không để caller tự ráp nhiều nữa.

### Phase C - Xóa dependency ngược nhỏ đầu tiên

File cần xử lý:

- `core/executor.py:_try_calculate_stats`

Việc làm:

1. Không để core import `webui.helpers`.
2. Nếu cần cập nhật stats UI, chuyển thành callback hook do caller truyền vào hoặc bỏ sang adapter layer.

### Phase D - Chuyển caller đầu tiên

Caller nên chuyển trước:

- `main.py`

Lý do:

- Blast radius của CLI adapter thấp hơn WebUI route lớn.

## Kiểm tra bắt buộc

- Chạy translation từ CLI vẫn thành công.
- Output file vẫn được lưu đúng chỗ.
- Checkpoint và cache vẫn còn hoạt động.

## Lệnh kiểm tra mẫu

Trước khi sửa:

```bash
npx gitnexus impact --repo Novel-Translator TranslationExecutor
npx gitnexus impact --repo Novel-Translator main
```

Sau khi sửa:

```bash
python -c "from core.executor import TranslationExecutor; print(TranslationExecutor.__name__)"
python -c "from backend.application.use_cases.translate_text_use_case import TranslateTextUseCase; print(TranslateTextUseCase.__name__)"
python cli.py --help
```

Nếu phase này đã chuyển caller CLI đầu tiên, chạy thêm:

```bash
python cli.py status
```

## Rollback và điều kiện dừng

Dừng ngay nếu:

- `TranslationExecutor` phải đổi signature public ngoài kế hoạch.
- `main.py` không còn chạy được parser hiện tại.
- Output path của CLI thay đổi so với baseline.
- Checkpoint hoặc cache path bị đổi ngoài ý muốn.

Rollback:

1. Giữ `TranslationExecutor` nguyên trạng gần nhất.
2. Khôi phục wrapper cũ trong `main.py` nếu use case mới chưa ổn.
3. Không chuyển `webui/routes/translation.py` trong cùng lượt làm việc.

## Tiêu chí hoàn tất

- Có use case dịch đầu tiên.
- `main.py` không còn tự dựng toàn bộ translation orchestration.
