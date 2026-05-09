# Phase 09 - CLI Decoupling

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Biến CLI thành adapter thật sự, không còn là wrapper chồng lên `main.py`.

## Symbol và file cần xử lý

- `cli.py:NovelTranslatorCLI`
- `cli.py:NovelTranslatorCLI._handle_translate`
- `cli.py:NovelTranslatorCLI._handle_status`
- `cli.py:NovelTranslatorCLI._handle_resume`
- `cli.py:NovelTranslatorCLI._handle_serve`
- `main.py:main`

## Vấn đề hiện tại

`cli.py:_handle_translate` đang:

1. import `main.py:main`
2. sửa `sys.argv`
3. gọi `run_translation()`

Đây là coupling không bền, khó test, khó tái sử dụng.

## Phase nội bộ

### Phase A - Tạo CLI command adapter mỏng

Gợi ý file:

- `interfaces/cli/commands/translate_command.py`
- `interfaces/cli/commands/status_command.py`
- `interfaces/cli/commands/resume_command.py`

Nếu chưa muốn tạo thư mục mới ngay, có thể tạo module trong `cli.py` tạm thời, nhưng nên hướng tới tách module.

### Phase B - Chuyển `translate` sang use case

Việc làm:

1. `NovelTranslatorCLI._handle_translate` không được sửa `sys.argv` nữa.
2. Tự dựng request DTO cho translation use case.
3. Dùng callback adapter cho progress bar `tqdm`.

### Phase C - Chuyển `status`

Việc làm:

1. Tách status logic sang service hoặc facade.
2. Không để CLI tự dò config, cache, key ở nhiều nơi.

### Phase D - Chuyển `resume`

Việc làm:

1. Hoàn tất `resume` bằng backend checkpoint service.
2. Xóa TODO nếu behavior đã sẵn sàng.
3. Nếu chưa đủ điều kiện làm thật, tạo plan rõ nhưng không giả vờ hoàn chỉnh.

### Phase E - Xử lý `serve`

Việc làm:

1. Quyết định giữ hay bỏ command `serve`.
2. Nếu giữ, nó chỉ gọi adapter khởi động WebUI.
3. Nếu chưa phục vụ use case thật, vẫn giữ command nhưng phải rõ ràng vai trò.

## Kiểm tra bắt buộc

- CLI help không đổi bất ngờ.
- `translate` không còn phụ thuộc vào `sys.argv`.
- `status` vẫn chạy.
- `resume` có hành vi rõ ràng.

## Lệnh kiểm tra mẫu

Trước khi sửa:

```bash
npx gitnexus impact --repo Novel-Translator NovelTranslatorCLI
npx gitnexus context --repo Novel-Translator NovelTranslatorCLI
```

Sau khi sửa:

```bash
python cli.py --help
python cli.py status
python -c "from cli import NovelTranslatorCLI; cli = NovelTranslatorCLI(); print(cli.parser.prog)"
```

Nếu có tách module vào `interfaces/cli/`, chạy thêm:

```bash
python -c "import interfaces.cli; print('interfaces cli import ok')"
```

## Rollback và điều kiện dừng

Dừng ngay nếu:

- CLI help text mất command hiện có.
- `_handle_translate` vẫn cần sửa `sys.argv` để chạy.
- Command `status` crash do thiếu config/key/cache.
- Cần sửa translation algorithm để CLI chạy.

Rollback:

1. Giữ parser hiện tại trong `cli.py`.
2. Khôi phục `_handle_translate` gọi wrapper cũ nếu adapter mới chưa đủ.
3. Không xóa `main.py` trong phase này.

## Tiêu chí hoàn tất

- CLI là consumer trực tiếp của backend/facade.
- `main.py` không còn là engine ẩn phía sau CLI wrapper.
