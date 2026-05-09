# Phase 13E - Project Translation Memory Service Plan

## Mục tiêu

Tách Translation Memory API khỏi route project lớn.

## File được phép chạm

- `webui/routes/projects.py`
- `backend/application/use_cases/project_tm/`
- `backend/infrastructure/workspace/project_tm_service.py`
- `services/translation_memory.py`
- test hoặc artifact liên quan phase này

## Route liên quan

- `GET /api/tm/stats`
- `POST /api/tm/find`
- `POST /api/tm/add`
- `POST /api/tm/clear`
- `POST /api/tm/export`
- `POST /api/tm/import`

## Bước thực hiện

1. Chạy GitNexus impact cho `TranslationMemory`.
2. Tạo service wrapper dùng lại `services/translation_memory.py`.
3. Tách stats trước.
4. Tách find/add.
5. Tách clear/export/import sau cùng.
6. Giữ nguyên response JSON.

## Kiểm tra

```bash
python -c "from services.translation_memory import TranslationMemory; print(TranslationMemory.__name__)"
python -c "from webui import create_app; app = create_app(); print(app.name)"
```

## Dừng nếu

- TM path đổi ngoài kế hoạch.
- Clear xóa nhầm ngoài TM directory.
- Import/export đổi format baseline.
