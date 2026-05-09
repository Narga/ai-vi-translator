# Phase 13A - Project CRUD Service Plan

## Mục tiêu

Tách riêng nghiệp vụ CRUD project khỏi `webui/routes/projects.py`.

## File được phép chạm

- `webui/routes/projects.py`
- `backend/application/use_cases/project_crud/`
- `backend/infrastructure/workspace/project_service.py`
- test hoặc artifact liên quan phase này

## Route liên quan

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/<slug>`
- `PUT /api/projects/<slug>`
- `DELETE /api/projects/<slug>`
- `PUT /api/projects/<slug>/file-status`

## Bước thực hiện

1. Chạy GitNexus impact cho các function route tương ứng.
2. Tạo service/use case CRUD dùng lại helper đã có từ Phase 06.
3. Di chuyển từng route một, bắt đầu từ `GET /api/projects`.
4. Sau mỗi route, giữ nguyên JSON response shape.
5. Chỉ xóa code cũ sau khi route tương ứng đã pass smoke check.

## Kiểm tra

```bash
python -c "from webui import create_app; app = create_app(); print(app.name)"
python -c "from webui.routes.projects import projects_bp; print(projects_bp.name)"
```

## Dừng nếu

- Route list project đổi schema.
- Delete project ảnh hưởng archive ngoài kế hoạch.
- Cần sửa file operations để CRUD chạy.
