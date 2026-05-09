# Phase 10 - WebUI Translation Route Refactor

Kế hoạch này bắt buộc kế thừa các nguyên tắc chung trong [00-overview.md](/Users/narga/Briefcase/Projects/Novel-Translator/docs/separation/00-overview.md), đặc biệt là: tận dụng mã sẵn có, không viết mới ngoài kế hoạch, chỉnh sửa tối thiểu, và phải kiểm tra hệ thống sau phase.

## Mục tiêu

Biến `webui/routes/translation.py` thành controller mỏng gọi backend use case thay vì tự orchestration.

## Symbol và file cần xử lý

- `webui/routes/translation.py:translate_worker`
- `webui/routes/translation.py:start_translation`
- `webui/routes/translation.py:progress_stream`
- `webui/routes/translation.py:translate_text`

## Vấn đề hiện tại

File route này đang tự làm:

- load API keys
- load prompts
- resolve glossary paths
- dựng `TranslationExecutor`
- đẩy queue SSE

Các phần trên phải dần chuyển xuống backend.

## Phase nội bộ

### Phase A - Tách thread worker khỏi route

Gợi ý file:

- `backend/infrastructure/progress/webui_progress_bridge.py`
- `backend/application/use_cases/translate_text_async_use_case.py`

Việc làm:

1. Route chỉ parse request.
2. Worker logic nằm ở backend adapter hoặc use case wrapper.

### Phase B - Chuyển config assembly

Việc làm:

1. Không dựng dict config lớn trực tiếp trong route nữa.
2. Route chỉ map request JSON sang DTO.
3. Prompt resolution và glossary resolution do backend làm.

### Phase C - Giữ SSE tương thích

Việc làm:

1. `progress_stream()` có thể giữ nguyên transport.
2. Nhưng payload đi qua event contract chuẩn của backend.

### Phase D - Tách `translate_text` direct action

Lưu ý:

Route `/api/translate-text` hiện là flow riêng cho retranslate/correction.

Việc làm:

1. Tạo use case riêng cho direct translate hoặc text action.
2. Không để route tự load cache/client/prompt quá sâu.

## Kiểm tra bắt buộc

- Translation từ tab chính vẫn chạy.
- SSE progress vẫn đổ về frontend.
- Retranslate/correction flow không gãy.

## Lệnh kiểm tra mẫu

Trước khi sửa:

```bash
npx gitnexus impact --repo Novel-Translator translate_worker
npx gitnexus impact --repo Novel-Translator start_translation
```

Sau khi sửa:

```bash
python -c "from webui import create_app; app = create_app(); print(app.name)"
python -c "from webui.routes.translation import translation_bp; print(translation_bp.name)"
```

Nếu đã có test harness:

```bash
pytest tests/smoke
```

## Rollback và điều kiện dừng

Dừng ngay nếu:

- `/api/progress` không còn phát event `ping`, `complete`, hoặc `error` theo baseline.
- Route `/api/translate` đổi response shape ngoài kế hoạch.
- Worker mới cần import Flask request context trong backend use case.
- `translation_result` hoặc progress queue bị mất compatibility với frontend hiện tại.

Rollback:

1. Giữ `progress_stream()` theo implementation cũ nếu SSE bị lỗi.
2. Khôi phục `translate_worker` cũ nếu use case wrapper chưa phát event đúng.
3. Không refactor `/api/translate-text` cùng lượt nếu `/api/translate` chưa ổn.

## Tiêu chí hoàn tất

- `webui/routes/translation.py` chỉ còn request parsing, thread kick-off, response trả về.
