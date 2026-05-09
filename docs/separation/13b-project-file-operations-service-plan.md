# Phase 13B - Project File Operations Service Plan

## Mục tiêu

Tách các thao tác file trong project khỏi `webui/routes/projects.py`.

## File được phép chạm

- `webui/routes/projects.py`
- `backend/application/use_cases/project_files/`
- `backend/infrastructure/workspace/project_file_service.py`
- test hoặc artifact liên quan phase này

## Route liên quan

- `GET /api/projects/<slug>/file/<path:filepath>`
- `PUT /api/projects/<slug>/file/<path:filepath>`
- `DELETE /api/projects/<slug>/file/<path:filepath>`
- `POST /api/projects/<slug>/upload`
- `POST /api/projects/<slug>/merge`
- `POST /api/projects/<slug>/chunk/<filename>`
- `POST /api/projects/<slug>/rename`
- `POST /api/projects/<slug>/move-done`
- `POST /api/projects/<slug>/move-back`

## Bước thực hiện

1. Tạo file service cho read/write/delete/upload/rename/move.
2. Di chuyển read file trước vì ít side effect nhất.
3. Di chuyển write file sau khi read ổn.
4. Di chuyển delete/upload/rename/move từng route riêng.
5. Chỉ xử lý merge/chunk sau cùng vì có nhiều biến thể output.

## Kiểm tra

```bash
python -c "from webui import create_app; app = create_app(); print(app.name)"
python -c "from webui.routes.projects import projects_bp; print(projects_bp.name)"
```

## Dừng nếu

- Đường dẫn file không còn bị giới hạn trong project.
- Upload có thể ghi ra ngoài `sources`.
- Rename không đồng bộ source/translated như baseline.
- Move done/back làm mất file.
