# Phase Execution Template

## Mục đích

File này là mẫu bắt buộc trước khi thực thi từng phase trong `docs/separation`.

Mỗi lần bắt đầu một phase, tạo một execution note mới trong:

- `docs/separation/artifacts/phase-XX-execution-note.md`

Không dùng template này để ghi kết quả trực tiếp. Hãy copy cấu trúc sang artifact riêng.

## 1. Phase Scope

- Phase:
- Ngày bắt đầu:
- Người/model thực hiện:
- Mục tiêu phase:
- Kết quả mong muốn:

## 2. Files Allowed To Touch

Chỉ liệt kê file được phép sửa trong lượt này.

- `path/to/file.py`
- `path/to/file.md`

Nếu phát hiện cần sửa file ngoài danh sách, dừng và cập nhật execution note trước.

## 3. Symbols Requiring GitNexus Impact

Liệt kê symbol phải kiểm tra trước khi sửa.

- `SymbolName`
- `module.py:function_name`

Lệnh mẫu:

```bash
npx gitnexus impact --repo Novel-Translator SymbolName
```

Ghi kết quả:

- Risk:
- Direct callers:
- Affected processes:
- Quyết định:

## 4. Reuse First

Trước khi viết mới, kiểm tra các nơi sau:

- `core/`
- `services/`
- `webui/helpers.py`
- `webui/routes/*.py`
- `main.py`
- `cli.py`

Ghi rõ mã nào sẽ được tái sử dụng:

- Nguồn:
- Cách dùng lại:

## 5. Planned Minimal Edits

Mỗi thay đổi phải nhỏ và có mục tiêu rõ.

1. File:
   Mục tiêu:
   Dòng/vùng dự kiến:
   Lý do:

2. File:
   Mục tiêu:
   Dòng/vùng dự kiến:
   Lý do:

## 6. Smoke Checks

Chọn các kiểm tra phù hợp phase.

CLI:

```bash
python cli.py --help
python cli.py status
```

WebUI import/app factory:

```bash
python -c "from webui import create_app; app = create_app(); print(app.name)"
```

Core import:

```bash
python -c "from core.executor import TranslationExecutor; print(TranslationExecutor.__name__)"
```

Backend import:

```bash
python -c "import backend; print('backend import ok')"
```

Tests:

```bash
pytest
```

## 7. Rollback Or Stop Conditions

Dừng ngay nếu:

- Import lỗi ở module vừa sửa.
- CLI parser không chạy.
- Flask app factory không boot.
- WebUI route trả response shape khác baseline mà phase không cho phép.
- GitNexus impact báo `HIGH` hoặc `CRITICAL` mà chưa có xác nhận tiếp tục.
- Cần sửa file ngoài danh sách allowed files.

Rollback thủ công:

- Chỉ hoàn tác thay đổi của phase hiện tại.
- Không revert thay đổi không thuộc phase.
- Không dùng lệnh destructive nếu chưa được yêu cầu.

## 8. Result Report

Sau khi làm xong, ghi:

- File đã sửa:
- Behavior public có đổi không:
- Test/smoke check đã chạy:
- Kết quả:
- Rủi ro còn lại:
- Có được chuyển phase tiếp theo không:
