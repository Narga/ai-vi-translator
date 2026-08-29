# tests/smoke/test_webui_app_factory.py
# Smoke tests cho WebUI app factory và routes cơ bản

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Đảm bảo import được webui module
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestWebUIAppFactory:
    """Test Flask app factory."""

    def test_import_webui(self):
        """Test rằng webui module import được."""
        import webui
        assert hasattr(webui, "create_app")
        assert hasattr(webui, "progress_queue")
        assert hasattr(webui, "translation_result")
        assert hasattr(webui, "translation_stats")

    def test_create_app(self):
        """Test rằng app factory tạo app đúng."""
        from webui import create_app
        app = create_app()
        assert app is not None
        assert app.name == "webui"

    def test_app_has_blueprints(self):
        """Test rằng app có đầy đủ blueprints."""
        from webui import create_app
        app = create_app()

        blueprint_names = list(app.blueprints.keys())
        assert "translation" in blueprint_names
        assert "settings" in blueprint_names
        assert "prompts" in blueprint_names
        assert "projects" in blueprint_names
        assert "plugins" in blueprint_names

    def test_app_config_testing(self):
        """Test rằng app có thể set TESTING mode."""
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        assert app.config["TESTING"] is True


class TestWebUIRoutesBasic:
    """Test các routes cơ bản."""

    def test_index_route(self, flask_client):
        """Test rằng route / trả về 200."""
        response = flask_client.get("/")
        assert response.status_code == 200

    def test_api_models_route(self, flask_client):
        """Test rằng route /api/models trả về 200 bất kể active provider nào.

        Hermetic: Mock cả Gemini helper và OpenAIClient để KHÔNG bao giờ gọi mạng thật,
        bảo vệ test suite khỏi flakiness và timeout.
        """
        gemini_models = [
            "gemini-2.0-flash", "gemini-3-flash", "gemini-3-pro",
        ]

        with patch("webui.helpers.get_available_gemini_models", return_value=list(gemini_models)), \
             patch("services.openai_client.OpenAIClient.list_models", return_value=["test-model-a", "test-model-b"]), \
             patch("services.openai_client.OpenAIClient.list_models_full", return_value=[{"id": "test-model-a", "is_free": False}]):
            response = flask_client.get("/api/models")
        assert response.status_code == 200
        data = response.get_json()
        assert "models" in data
        assert "default" in data
        assert "provider" in data

    def test_api_models_route_gemini_explicit(self, flask_client):
        """Test /api/models với ?provider=gemini."""
        gemini_models = [
            "gemini-2.0-flash", "gemini-3-flash", "gemini-3-pro",
        ]

        with patch("webui.helpers.get_available_gemini_models", return_value=list(gemini_models)):
            response = flask_client.get("/api/models?provider=gemini")
        assert response.status_code == 200
        data = response.get_json()
        assert "models" in data
        assert data.get("provider") == "gemini"

    def test_api_models_route_openai_explicit(self, flask_client):
        """Test /api/models với ?provider=openai (Hermetic mock)."""
        with patch("services.openai_client.OpenAIClient.list_models", return_value=["test-model-a", "test-model-b"]), \
             patch("services.openai_client.OpenAIClient.list_models_full", return_value=[{"id": "test-model-a"}]):
            response = flask_client.get("/api/models?provider=openai")
        assert response.status_code == 200
        data = response.get_json()
        assert "models" in data
        assert data.get("provider") == "openai"
        assert "test-model-a" in data["models"]


    def test_api_models_route_error_handling(self, flask_client):
        """Test rằng route /api/models xử lý ngoại lệ có cấu trúc khi provider gặp lỗi."""
        from unittest.mock import patch

        def _mock_failure(*args, **kwargs):
            raise RuntimeError("Mocked provider upstream failure")

        with patch("services.openai_client.OpenAIClient.list_models", _mock_failure):
            response = flask_client.get("/api/models?provider=openai")
        # Assert route bắt ngoại lệ và trả JSON error có cấu trúc
        assert response.status_code in (200, 500, 502, 503)
        data = response.get_json()
        assert "error" in data or "models" in data

    def test_api_provider_get(self, flask_client):
        """Test rằng route GET /api/provider trả về 200."""
        response = flask_client.get("/api/provider")
        assert response.status_code == 200
        data = response.get_json()
        assert "active" in data

    def test_api_config_route(self, flask_client):
        """Test rằng route /api/config trả về 200."""
        response = flask_client.get("/api/config")
        assert response.status_code == 200
        data = response.get_json()
        assert "default_chunk_size" in data
        assert "default_model" in data

    def test_api_projects_route(self, flask_client):
        """Test rằng route /api/projects trả về 200."""
        response = flask_client.get("/api/projects")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_api_prompt_library_route(self, flask_client):
        """Test rằng route /api/prompts/library trả về 200."""
        response = flask_client.get("/api/prompts/library")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_api_plugins_list_route(self, flask_client):
        """Test rằng route /api/plugins/list trả về 200."""
        response = flask_client.get("/api/plugins/list")
        assert response.status_code == 200
        data = response.get_json()
        assert isinstance(data, list)

    def test_api_stats_route(self, flask_client):
        """Test rằng route /api/stats trả về 200."""
        response = flask_client.get("/api/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert "status" in data
        assert data["status"] == "ready"

    def test_api_tm_stats_route(self, flask_client):
        """Test rằng route /api/tm/stats trả về 200."""
        response = flask_client.get("/api/tm/stats")
        assert response.status_code == 200

    def test_header_active_model_ssr_falls_back_to_default(self, flask_client, monkeypatch):
        """Regression: header #header-active-model phải chứa default_model từ active provider.

        Trước v8.29.0, ``loadAppConfig()`` cập nhật DOM sau khi gọi ``/api/settings/app``;
        commit 4a2fc7c xóa đoạn đó. Trang render giờ chỉ có chuỗi "--" tĩnh. Test này
        chốt lại hợp đồng SSR: nếu active provider có ``default_model`` thì header
        pill phải hiển thị giá trị đó ngay khi F5 (không cần JS chạy).
        """
        import re

        # Route / import webui.helpers.get_default_model trực tiếp trong hàm,
        # nên mock tại webui.routes.translation (điểm lookup thực tế).
        with patch(
            "webui.routes.translation.get_default_model",
            return_value="gemini-3.6-flash",
        ):
            response = flask_client.get("/")

        assert response.status_code == 200
        body = response.get_data(as_text=True)
        match = re.search(
            r'id="header-active-model"[^>]*>([^<]+)<',
            body,
        )
        assert match, "Thiếu element #header-active-model trong response"
        rendered = match.group(1).strip()
        assert rendered == "gemini-3.6-flash", (
            f"Header phải chứa default_model khi provider đang cấu hình, "
            f"hiện tại: {rendered!r}"
        )
