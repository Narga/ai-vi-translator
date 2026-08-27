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

    def test_save_model_without_provider_id_updates_active_provider(self, real_config_dir):
        """Regression: frontend từng gửi provider_id undefined vì activeProviderId không set.

        Backend phải lưu vào active provider thay vì trả success giả nhưng không ghi gì.
        """
        from webui import create_app
        from backend.infrastructure.providers.provider_service import ProviderService

        ps = ProviderService(real_config_dir)
        active = ps.get_active_provider_config()
        assert active is not None
        if active["type"] == "gemini":
            new_default = "gemini-2.5-pro"
            old_default = active.get("default_model", "gemini-2.0-flash")
        else:
            new_default = active.get("default_model") or "gpt-4o-mini"
            old_default = active.get("default_model", "")
            # Ensure the test actually changes something for common OpenAI-compatible active providers.
            if new_default == old_default:
                new_default = old_default + "-regression-test"

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        try:
            r = client.post("/api/settings/save", json={
                "default_model": new_default,
            })
            assert r.status_code == 200, r.get_json()
            data = r.get_json()
            assert data["success"] is True
            assert data["provider"]["id"] == active["id"]
            assert data["provider"]["default_model"] == new_default
            saved = ProviderService(real_config_dir).get_provider_by_id(active["id"])
            assert saved["default_model"] == new_default
        finally:
            client.post("/api/settings/save", json={
                "provider_id": active["id"],
                "default_model": old_default,
            })

    def test_save_clears_qa_model_without_etag(self, real_config_dir):
        """Regression: qa_model='' là sentinel clear và phải hoạt động không cần If-Match."""
        from webui import create_app
        from backend.infrastructure.providers.provider_service import ProviderService

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        ps = ProviderService(real_config_dir)
        provider = ps.get_provider_by_id("gemini-default")
        old_qa = provider.get("qa_model", "gemini-1.5-pro")
        try:
            client.post("/api/settings/save", json={
                "provider_id": "gemini-default",
                "qa_model": "gemini-1.5-flash",
            })
            r = client.post("/api/settings/save", json={
                "provider_id": "gemini-default",
                "qa_model": "",
            })
            assert r.status_code == 200, r.get_json()
            data = r.get_json()
            assert data["provider"]["qa_model"] == ""
            saved = ProviderService(real_config_dir).get_provider_by_id("gemini-default")
            assert saved.get("qa_model", "") == ""
        finally:
            client.post("/api/settings/save", json={
                "provider_id": "gemini-default",
                "qa_model": old_qa,
            })

    def test_get_models_returns_active_provider_id(self, real_config_dir):
        """Frontend cần active_id để gửi provider_id khi lưu model đã chọn."""
        from webui import create_app
        from backend.infrastructure.providers.provider_service import ProviderService

        active = ProviderService(real_config_dir).get_active_provider_config()
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.get("/api/models?full=true")
        assert r.status_code == 200
        data = r.get_json()
        assert data["active_id"] == active["id"]

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

    def test_etag_header_returned(self, real_config_dir):
        """B4: GET /api/providers trả ETag header cho client dùng If-Match."""
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        r = client.get("/api/providers")
        assert r.status_code == 200
        etag = r.headers.get("ETag")
        assert etag is not None
        assert etag.startswith('"sha256-') and etag.endswith('"')

    def test_put_with_correct_etag_succeeds(self, real_config_dir):
        """B4: PUT /models với If-Match đúng → 200."""
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        etag = client.get("/api/providers").headers.get("ETag")
        r = client.put(
            "/api/providers/openrouter/models",
            json={"default_model": "anthropic/claude-3.5-sonnet"},
            headers={"If-Match": etag},
        )
        assert r.status_code == 200
        # Revert
        client.put(
            "/api/providers/openrouter/models",
            json={"default_model": "deepseek/deepseek-v4-flash-0731"},
        )

    def test_put_with_stale_etag_returns_409(self, real_config_dir):
        """B4: PUT với ETag cũ (stale) → 409 Conflict."""
        from webui import create_app
        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()
        # Lấy ETag hiện tại
        old_etag = client.get("/api/providers").headers.get("ETag")
        # Tạo thay đổi để ETag cũ trở thành stale
        client.put(
            "/api/providers/openrouter/models",
            json={"default_model": "anthropic/claude-3.5-sonnet"},
        )
        # PUT với ETag cũ
        r = client.put(
            "/api/providers/openrouter/models",
            json={"default_model": "openai/gpt-4o"},
            headers={"If-Match": old_etag},
        )
        assert r.status_code == 409
        body = r.get_json()
        assert "ETag mismatch" in body["error"]
        assert body["current_etag"] != old_etag
        assert body["your_etag"] == old_etag
        # Revert
        client.put(
            "/api/providers/openrouter/models",
            json={"default_model": "deepseek/deepseek-v4-flash-0731"},
        )
