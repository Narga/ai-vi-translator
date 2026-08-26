# tests/unit/test_settings_endpoints.py
# D1 + D4-B: Test cho 3 endpoint mới trong settings.py
# - PUT /api/providers/<id>/models
# - PUT /api/providers/<id>/credentials
# - POST /api/settings/save (transaction)

import json
import sys
import shutil
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def real_config_dir(tmp_path, monkeypatch):
    """Copy config vào tmp_path để test không phá config thật."""
    real = Path("config")
    d = tmp_path / "config"
    shutil.copytree(real, d)
    monkeypatch.chdir(tmp_path)
    yield d


class TestUpdateProviderModels:

    def test_update_default_model_gemini_valid(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.put("/api/providers/gemini-default/models",
                       json={"default_model": "gemini-2.5-pro"})
        assert r.status_code == 200, r.get_json()
        data = r.get_json()
        assert data["success"] is True
        assert data["provider"]["default_model"] == "gemini-2.5-pro"
        # Revert
        client.put("/api/providers/gemini-default/models",
                   json={"default_model": "gemini-2.0-flash"})

    def test_reject_cross_namespace_gemini_step(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.put("/api/providers/gemini-default/models",
                       json={"default_model": "step-3.7-flash"})
        assert r.status_code == 400
        data = r.get_json()
        assert "errors" in data
        assert any(e["field"] == "default_model" for e in data["errors"])

    def test_reject_cross_namespace_openai_gemini(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.put("/api/providers/openrouter/models",
                       json={"default_model": "gemini-2.0-flash"})
        assert r.status_code == 400

    def test_update_qa_model(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.put("/api/providers/gemini-default/models",
                       json={"qa_model": "gemini-1.5-flash"})
        assert r.status_code == 200
        data = r.get_json()
        assert data["provider"]["qa_model"] == "gemini-1.5-flash"
        # Revert
        client.put("/api/providers/gemini-default/models",
                   json={"qa_model": "gemini-1.5-pro"})

    def test_clear_qa_with_empty_string(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.put("/api/providers/gemini-default/models",
                       json={"qa_model": ""})
        assert r.status_code == 200
        data = r.get_json()
        assert data["provider"]["qa_model"] == ""
        # Revert
        client.put("/api/providers/gemini-default/models",
                   json={"qa_model": "gemini-1.5-pro"})

    def test_provider_not_found(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.put("/api/providers/nonexistent/models",
                       json={"default_model": "gemini-2.0-flash"})
        assert r.status_code == 400
        assert "field" in r.get_json()


class TestUpdateProviderCredentials:

    def test_update_api_key_openai(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        # Lưu lại key cũ
        original = json.loads((real_config_dir / "providers.json").read_text())
        old_key = next(p for p in original["providers"] if p["id"] == "openrouter")["api_key"]
        try:
            r = client.put("/api/providers/openrouter/credentials",
                           json={"api_key": "sk-new-test-1234567890"})
            assert r.status_code == 200
            data = r.get_json()
            assert data["success"] is True
            # API key phải mask
            assert data["provider"]["api_key_last4"] == "...7890"
            assert data["provider"].get("api_key") in (None, "")
        finally:
            # Revert
            client.put("/api/providers/openrouter/credentials",
                       json={"api_key": old_key})

    def test_reject_invalid_base_url(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.put("/api/providers/openrouter/credentials",
                       json={"base_url": "not-a-url"})
        assert r.status_code == 400
        assert "base_url" in r.get_json()["field"]

    def test_update_gemini_keys(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        original = json.loads((real_config_dir / "providers.json").read_text())
        old_keys = next(p for p in original["providers"] if p["id"] == "gemini-default")["api_keys"]
        try:
            r = client.put("/api/providers/gemini-default/credentials",
                           json={"api_keys": ["AIzaNewKey12345"]})
            assert r.status_code == 200
            data = r.get_json()
            assert data["provider"]["key_count"] == 1
            assert data["provider"]["api_key_last4"] == ["...2345"]
        finally:
            client.put("/api/providers/gemini-default/credentials",
                       json={"api_keys": old_keys})


class TestSaveSettingsTransaction:

    def test_save_only_app_config(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        original_temp = (real_config_dir / "app.ini").read_text()
        try:
            r = client.post("/api/settings/save", json={
                "app_config": {
                    "PROCESSING": {"TEMPERATURE": "0.85", "REQUEST_DELAY": "3.5"},
                }
            })
            assert r.status_code == 200
            data = r.get_json()
            assert data["success"] is True
            # TEMPERATURE trả float (đã convert qua ConfigParser)
            assert abs(data["config"]["PROCESSING"]["TEMPERATURE"] - 0.85) < 0.001
            assert abs(data["config"]["PROCESSING"]["REQUEST_DELAY"] - 3.5) < 0.001
        finally:
            (real_config_dir / "app.ini").write_text(original_temp)

    def test_save_with_provider_model(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.post("/api/settings/save", json={
            "provider_id": "gemini-default",
            "default_model": "gemini-2.5-pro",
        })
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert data["provider"]["default_model"] == "gemini-2.5-pro"
        # Revert
        client.post("/api/settings/save", json={
            "provider_id": "gemini-default",
            "default_model": "gemini-2.0-flash",
        })

    def test_save_combined(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        original_temp = (real_config_dir / "app.ini").read_text()
        try:
            r = client.post("/api/settings/save", json={
                "provider_id": "openrouter",
                "default_model": "anthropic/claude-3.5-sonnet",
                "qa_model": "anthropic/claude-3-haiku",
                "app_config": {"PROCESSING": {"TEMPERATURE": "0.7"}},
            })
            assert r.status_code == 200
            data = r.get_json()
            assert data["provider"]["default_model"] == "anthropic/claude-3.5-sonnet"
            assert data["provider"]["qa_model"] == "anthropic/claude-3-haiku"
            assert abs(data["config"]["PROCESSING"]["TEMPERATURE"] - 0.7) < 0.001
        finally:
            (real_config_dir / "app.ini").write_text(original_temp)
            client.post("/api/settings/save", json={
                "provider_id": "openrouter",
                "default_model": "deepseek/deepseek-v4-flash-0731",
                "qa_model": "",
            })

    def test_validation_error_returns_400_with_errors(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.post("/api/settings/save", json={
            "provider_id": "gemini-default",
            "default_model": "step-3.7-flash",  # sai namespace
            "app_config": {"PROCESSING": {"TEMPERATURE": "5.0"}},  # ngoài range
        })
        assert r.status_code == 400
        data = r.get_json()
        assert "errors" in data
        fields = [e["field"] for e in data["errors"]]
        assert "default_model" in fields
        assert any("TEMPERATURE" in f for f in fields)

    def test_reject_legacy_model_section(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.post("/api/settings/save", json={
            "app_config": {"MODEL": {"MODEL": "evil"}},
        })
        assert r.status_code == 400
        data = r.get_json()
        assert any("MODEL" in e["field"] for e in data["errors"])

    def test_unknown_provider(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.post("/api/settings/save", json={
            "provider_id": "nonexistent",
            "default_model": "gemini-2.0-flash",
        })
        assert r.status_code == 400

    def test_app_config_no_change_when_empty(self, real_config_dir):
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.post("/api/settings/save", json={})
        assert r.status_code == 200
        data = r.get_json()
        assert data["success"] is True
        assert data["provider"] is None
