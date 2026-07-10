# tests/smoke/test_webui_app_factory.py
# Smoke tests cho WebUI app factory và routes cơ bản

import sys
import pytest
from pathlib import Path

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
        """Test rằng route /api/models trả về 200."""
        response = flask_client.get("/api/models")
        assert response.status_code == 200
        data = response.get_json()
        assert "models" in data
        assert "default" in data
        assert "provider" in data

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
