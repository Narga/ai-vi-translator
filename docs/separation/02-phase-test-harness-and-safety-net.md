# Phase 02 - Test Harness And Safety Net

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Tạo lưới an toàn tối thiểu để các phase sau refactor không làm gãy dự án.

## Nguyên tắc

- Chỉ thêm test hoặc script smoke check.
- Không đổi behavior production.
- Nếu dự án chưa có pytest baseline, phase này chỉ dựng khung nhẹ, không ép phủ rộng.

## File cần tạo hoặc cập nhật

Tùy cấu trúc hiện có, có thể thêm:

- `tests/`
- `tests/smoke/`
- `tests/unit/`
- `tests/conftest.py`
- `pytest.ini` hoặc cập nhật `pyproject.toml`
- `docs/separation/artifacts/test-matrix.md`

## Phase nội bộ

### Phase A - Chốt chiến lược test

Việc làm:

1. Kiểm tra hiện có `pytest` hay chưa.
2. Nếu chưa có, thêm cấu hình tối thiểu.
3. Chọn test tối thiểu cho giai đoạn refactor:
   - CLI help và parser
   - WebUI app factory
   - Các route GET/POST cốt lõi
   - Các helper service không side effect mạnh

### Phase B - Smoke tests cho CLI

Ưu tiên test:

- `cli.py:main`
- parser của `NovelTranslatorCLI`

Việc làm:

1. Kiểm tra `--help` chạy được.
2. Kiểm tra `status` không crash.
3. Kiểm tra `translate` parse đủ tham số mà không lỗi parser.
4. Nếu có thể, mock `main.py:main` khi test `_handle_translate`.

### Phase C - Smoke tests cho WebUI

Ưu tiên test:

- `webui/__init__.py:create_app`
- route `/`
- route `/api/models`
- route `/api/provider`

Việc làm:

1. Dùng Flask test client.
2. Test app khởi tạo được.
3. Test route trả status code hợp lệ.
4. Không cần test gọi AI thật.

### Phase D - Snapshot hành vi progress

Việc làm:

1. Chuẩn hóa fixture của progress event.
2. Snapshot các field hiện có:
   - `type`
   - `message`
   - `current`
   - `total`
   - `percent`
   - `result`
   - `output_file`

## Tiêu chí hoàn tất

- Có smoke tests chạy được cục bộ.
- Có tối thiểu một test cho CLI parser.
- Có tối thiểu một test cho Flask app factory.
- Có tài liệu `test-matrix.md` mô tả test nào bảo vệ phase nào.

## Không được chuyển phase nếu

- Chưa có cách xác minh CLI vẫn parse đúng.
- Chưa có cách xác minh Flask app vẫn boot được.
