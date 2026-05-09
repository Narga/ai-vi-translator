# Phase 07 - Progress Event Contract

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Chuẩn hóa contract progress event dùng chung cho CLI và WebUI trước khi tách translation use case.

## Tại sao phase này cần đi trước

Hiện tại progress event bị phát sinh trực tiếp từ executor và bị tiêu thụ khác nhau bởi:

- `main.py` qua `tqdm`
- `webui/routes/translation.py` qua SSE queue
- `webui/routes/projects.py` qua worker thread

Nếu chưa thống nhất event model, mọi refactor translation sau này sẽ rất dễ gãy UI hoặc CLI progress.

## File đích nên tạo

- `backend/application/dto/progress_event.py`
- `backend/infrastructure/progress/progress_mapper.py`

## Contract tối thiểu nên hỗ trợ

Field chuẩn:

- `type`
- `message`
- `current`
- `total`
- `percent`
- `result`
- `output_file`
- `tokens_used`
- `source_length`
- `translated_length`
- `metadata`

Event types chuẩn:

- `progress`
- `info`
- `complete`
- `error`
- `file_complete`
- `ping`

## Phase nội bộ

### Phase A - Ghi contract thành code

Việc làm:

1. Tạo DTO hoặc typed dict/dataclass cho progress event.
2. Không ép tất cả field phải có mặt cùng lúc.
3. Có helper normalize event để CLI/WebUI nhận shape ổn định.

### Phase B - Bọc callback adapter

Việc làm:

1. Tạo mapper từ event chuẩn sang:
   - callback cho CLI
   - queue payload cho WebUI
2. Không sửa transport layer quá nhiều ở phase này.

### Phase C - Ứng dụng vào executor

File liên quan:

- `core/executor.py`
- `core/spellcheck_executor.py`

Việc làm:

1. Giữ behavior cũ.
2. Chỉ chuẩn hóa cách emit event.
3. Nếu có log handler, không làm mất compatibility của payload.

## Kiểm tra bắt buộc

- CLI progress bar vẫn cập nhật.
- WebUI SSE vẫn chạy.
- `complete` event vẫn có dữ liệu mà UI đang cần.

## Tiêu chí hoàn tất

- Có một contract event rõ ràng trong backend.
- Executor không phát event ngẫu hứng theo từng caller nữa.
