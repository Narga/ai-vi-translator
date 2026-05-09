# Phase 13C - Project Prompts Assets Service Plan

## Mục tiêu

Tách prompts, guidelines, assets và summarize project khỏi route project lớn.

## File được phép chạm

- `webui/routes/projects.py`
- `backend/application/use_cases/project_prompts/`
- `backend/application/use_cases/project_assets/`
- `backend/infrastructure/workspace/project_asset_service.py`
- test hoặc artifact liên quan phase này

## Route liên quan

- `GET /api/projects/<slug>/prompts`
- `PUT /api/projects/<slug>/prompts`
- `DELETE /api/projects/<slug>/prompts`
- `POST /api/projects/<slug>/prompts/import`
- `GET /api/projects/<slug>/guidelines`
- `PUT /api/projects/<slug>/guidelines`
- `POST /api/projects/<slug>/summarize`

## Bước thực hiện

1. Tách project prompt read/write/delete.
2. Tách prompt import.
3. Tách guideline assets read/write.
4. Tách summarize project sau cùng vì có gọi AI/provider.
5. Giữ prompt global ở service của Phase 05, không trộn lại vào phase này.

## Kiểm tra

```bash
python -c "from webui import create_app; app = create_app(); print(app.name)"
python -c "from webui.routes.projects import projects_bp; print(projects_bp.name)"
```

## Dừng nếu

- Project prompt ghi đè nhầm global prompt.
- Guidelines đổi tên file asset ngoài baseline.
- Summarize project gọi provider sai active provider.
