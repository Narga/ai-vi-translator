# Phase 03 - Backend Scaffold

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Dựng khung backend dùng chung nhưng chưa di chuyển logic lớn, để các phase sau có chỗ đặt code ổn định.

## Không làm ở phase này

- Không di chuyển `TranslationExecutor`.
- Không di chuyển route Flask.
- Không đổi CLI behavior.

## Cấu trúc mục tiêu tối thiểu

Có thể tạo các thư mục sau:

- `backend/`
- `backend/application/`
- `backend/application/dto/`
- `backend/application/use_cases/`
- `backend/application/ports/`
- `backend/domain/`
- `backend/infrastructure/`
- `backend/infrastructure/config/`
- `backend/infrastructure/providers/`
- `backend/infrastructure/workspace/`
- `backend/infrastructure/progress/`
- `backend/facade/`

## File nên tạo trước

- `backend/__init__.py`
- `backend/application/__init__.py`
- `backend/infrastructure/__init__.py`
- `backend/facade/__init__.py`
- `backend/facade/app_service.py`

## Phase nội bộ

### Phase A - Tạo package rỗng

Việc làm:

1. Tạo thư mục backend.
2. Thêm `__init__.py` tối thiểu.
3. Không import vòng tròn.

### Phase B - Tạo facade rỗng

Mục tiêu:

- Có một nơi tập trung để CLI và WebUI gọi về sau.

Việc làm:

1. Tạo `backend/facade/app_service.py`.
2. Chỉ tạo class hoặc object khung, ví dụ `AppService`.
3. Chưa cần triển khai logic.

### Phase C - Tạo README nội bộ cho backend

Việc làm:

1. Tạo file mô tả ngắn trong backend hoặc trong `docs/separation/artifacts/`.
2. Ghi quy ước:
   - `application/use_cases` cho orchestration nghiệp vụ
   - `infrastructure/*` cho file system, config, provider, progress
   - `facade/app_service.py` là entrypoint dùng chung

## Tiêu chí hoàn tất

- Import backend package không lỗi.
- Chưa có code production nào bị redirect sang backend mới.
- Có khung thư mục ổn định cho các phase sau.

## Không được chuyển phase nếu

- Khung package chưa import được.
- Chưa định nghĩa rõ vai trò từng thư mục.
