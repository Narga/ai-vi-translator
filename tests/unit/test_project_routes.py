# tests/unit/test_project_routes.py
# Unit tests cho project routes: tm/clear và translate with force_retranslate

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def client():
    """Tạo Flask test client."""
    from webui import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestClearProjectTMRoute:
    """Task B.2: Kiểm tra API xóa TM dự án."""

    def test_clear_tm_success(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir, \
             patch("services.translation_memory.TranslationMemory") as mock_tm_cls:

            mock_pdir = MagicMock(spec=Path)
            mock_pdir.exists.return_value = True
            mock_dir.return_value = mock_pdir

            mock_tm = MagicMock()
            mock_tm.clear.return_value = 15
            mock_tm_cls.return_value = mock_tm

            response = client.post("/api/projects/test-slug/tm/clear")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["deleted"] == 15
            mock_tm.clear.assert_called_once()

    def test_clear_tm_project_not_found(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir:
            mock_pdir = MagicMock(spec=Path)
            mock_pdir.exists.return_value = False
            mock_dir.return_value = mock_pdir

            response = client.post("/api/projects/nonexistent/tm/clear")

            assert response.status_code == 404
            data = response.get_json()
            assert "error" in data

    def test_clear_tm_exception(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir, \
             patch("services.translation_memory.TranslationMemory") as mock_tm_cls:

            mock_pdir = MagicMock(spec=Path)
            mock_pdir.exists.return_value = True
            mock_dir.return_value = mock_pdir

            mock_tm = MagicMock()
            mock_tm.clear.side_effect = RuntimeError("DB error")
            mock_tm_cls.return_value = mock_tm

            response = client.post("/api/projects/test-slug/tm/clear")

            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data


class TestTranslateProjectForceRetranslate:
    """Task B.3: Kiểm tra API translate nhận diện force_retranslate."""

    def _setup_mocks(self):
        """Helper thiết lập mocks cho translate route."""
        mocks = {}

        mocks["dir"] = patch("webui.routes.projects._get_project_dir")
        mocks["meta"] = patch("webui.routes.projects._load_project_meta")
        mocks["prompt_svc"] = patch("backend.infrastructure.config.prompt_service.PromptService")
        mocks["ctx_svc"] = patch("backend.infrastructure.config.project_context_service.ProjectContextService")
        mocks["cfg_svc"] = patch("backend.infrastructure.config.app_config_service.AppConfigService")
        mocks["prov_svc"] = patch("backend.infrastructure.providers.provider_service.ProviderService")
        mocks["tm_cls"] = patch("services.translation_memory.TranslationMemory")
        mocks["thread"] = patch("webui.routes.projects.Thread")
        mocks["queue"] = patch("webui.progress_queue")

        started = {}
        for key, p in mocks.items():
            started[key] = p.start()

        mock_pdir = MagicMock(spec=Path)
        mock_pdir.__truediv__ = lambda self, x: MagicMock(spec=Path, exists=lambda: False)
        started["dir"].return_value = mock_pdir

        started["meta"].return_value = {"book_title": "Test", "slug": "test-slug"}

        mock_prompt = MagicMock()
        mock_prompt.load_merged_prompts.return_value = {"main": "Dịch:"}
        started["prompt_svc"].return_value = mock_prompt

        mock_ctx = MagicMock()
        mock_ctx.load_context.return_value = {}
        mock_ctx.render_prompt.return_value = "Dịch:"
        started["ctx_svc"].return_value = mock_ctx

        mock_cfg = MagicMock()
        mock_cfg.get_temperature.return_value = 1.0
        mock_cfg.get_default_chunk_size.return_value = 22000
        mock_cfg.get_context_char_count.return_value = 500
        started["cfg_svc"].return_value = mock_cfg

        mock_prov = MagicMock()
        mock_prov.get_active_provider_config.return_value = {
            "type": "gemini",
            "api_keys": ["test-key"],
            "default_model": "gemini-flash",
        }
        started["prov_svc"].return_value = mock_prov

        mock_tm = MagicMock()
        started["tm_cls"].return_value = mock_tm

        started["queue"].empty.return_value = True

        return started

    def _stop_mocks(self, mocks):
        for p in mocks.values():
            p.stop()

    def test_translate_accepts_force_flag(self, client):
        mocks = self._setup_mocks()
        try:
            payload = {
                "files": ["chapter1.txt"],
                "model": "gemini-flash",
                "force_retranslate": True,
            }

            response = client.post(
                "/api/projects/test-slug/translate",
                json=payload,
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "started"
        finally:
            self._stop_mocks(mocks)

    def test_translate_without_force_flag(self, client):
        mocks = self._setup_mocks()
        try:
            payload = {
                "files": ["chapter1.txt"],
                "model": "gemini-flash",
            }

            response = client.post(
                "/api/projects/test-slug/translate",
                json=payload,
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "started"
        finally:
            self._stop_mocks(mocks)

    def test_translate_no_project(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir, \
             patch("webui.routes.projects._load_project_meta") as mock_meta:

            mock_pdir = MagicMock(spec=Path)
            mock_dir.return_value = mock_pdir
            mock_meta.return_value = None

            payload = {"files": ["chapter1.txt"]}

            response = client.post(
                "/api/projects/nonexistent/translate",
                json=payload,
            )

            assert response.status_code == 404

    def test_translate_no_files(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir, \
             patch("webui.routes.projects._load_project_meta") as mock_meta:

            mock_pdir = MagicMock(spec=Path)
            mock_dir.return_value = mock_pdir
            mock_meta.return_value = {"book_title": "Test"}

            payload = {"files": []}

            response = client.post(
                "/api/projects/test-slug/translate",
                json=payload,
            )

            assert response.status_code == 400
