# Phase 13D - Project Archive Service Plan

## Mục tiêu

Tách archive/restore project khỏi `webui/routes/projects.py`.

## File được phép chạm

- `webui/routes/projects.py`
- `backend/application/use_cases/project_archive/`
- `backend/infrastructure/workspace/project_archive_service.py`
- test hoặc artifact liên quan phase này

## Route liên quan

- `POST /api/projects/<slug>/archive`
- `GET /api/archive`
- `POST /api/archive/restore`
- `DELETE /api/archive/<filename>`

## Bước thực hiện

1. Ghi baseline archive path và restore behavior.
2. Tạo archive service dùng lại logic hiện có.
3. Tách archive project trước.
4. Tách list archive.
5. Tách restore.
6. Tách delete archive artifact sau cùng.

## Kiểm tra

```bash
python -c "from webui import create_app; app = create_app(); print(app.name)"
python -c "from webui.routes.projects import projects_bp; print(projects_bp.name)"
```

## Dừng nếu

- Archive xóa project live khi chưa tạo artifact thành công.
- Restore ghi đè project hiện có mà không theo baseline.
- Delete archive có thể xóa file ngoài archive directory.
