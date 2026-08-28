# tests/unit/test_migrate_providers_v2.py
# Nhóm 4: Test cho migrate_providers_v2 và rollback_providers.

import json
import sys
import subprocess
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import trực tiếp module để test functions
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from migrate_providers_v2 import (
    transform_providers,
    transform_app_ini,
    is_valid_gemini_model,
    run_migration,
)
import configparser


@pytest.fixture
def mock_config_v1(tmp_path):
    """Tạo config dir với providers.json v1 (có lỗi) và app.ini legacy."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    providers_data = {
        "version": 1,
        "active_id": "gemini-default",
        "providers": [
            {
                "id": "gemini-default",
                "type": "gemini",
                "name": "Google Gemini",
                "api_keys": ["AIzaTest12345"],
                "default_model": "step-3.7-flash",  # Lỗi cross-provider
            },
            {
                "id": "openrouter",
                "type": "openai",
                "name": "OpenRouter",
                "api_key": "sk-or-test-1234567890",
                "base_url": "https://openrouter.ai/api/v1",
                "default_model": "deepseek/deepseek-chat",
                "extra_field": "keep me",  # R6: giữ field mở rộng
            },
        ],
    }
    (config_dir / "providers.json").write_text(
        json.dumps(providers_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    app_ini_content = """[MODEL]
MODEL = step-3.7-flash
THINKING_LEVEL = OFF

[PROCESSING]
MAX_CHARS_PER_CHUNK = 20000
TEMPERATURE = 1.0
REQUEST_DELAY = 5
CONTEXT_CHAR_COUNT = 500
TASK_POLL_INTERVAL = 15
"""
    (config_dir / "app.ini").write_text(app_ini_content, encoding="utf-8")
    return config_dir


class TestIsValidGeminiModel:
    def test_accepts_gemini_models(self):
        assert is_valid_gemini_model("gemini-2.0-flash")
        assert is_valid_gemini_model("gemini-1.5-pro")
        assert is_valid_gemini_model("gemma-2-9b")

    def test_rejects_step_models(self):
        assert not is_valid_gemini_model("step-3.7-flash")

    def test_rejects_namespaced(self):
        assert not is_valid_gemini_model("deepseek/deepseek-chat")
        assert not is_valid_gemini_model("workers-ai/@cf/x")

    def test_rejects_free_suffix(self):
        assert not is_valid_gemini_model("gemini-2.0-flash:free")

    def test_rejects_empty(self):
        assert not is_valid_gemini_model("")
        assert not is_valid_gemini_model(None)


class TestTransformProviders:
    def test_sets_default_model_for_invalid_gemini(self, mock_config_v1):
        providers_data = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        result = transform_providers(providers_data)
        gemini = next(p for p in result["providers"] if p["id"] == "gemini-default")
        assert gemini["default_model"] == "gemini-2.0-flash"
        assert "qa_model" not in gemini

    def test_preserves_extension_fields(self, mock_config_v1):
        providers_data = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        result = transform_providers(providers_data)
        openrouter = next(p for p in result["providers"] if p["id"] == "openrouter")
        assert openrouter.get("extra_field") == "keep me"

    def test_rejects_unknown_type(self, mock_config_v1):
        providers_data = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        providers_data["providers"].append({
            "id": "bad", "type": "unsupported", "name": "Bad"
        })
        with pytest.raises(ValueError, match="không.*hỗ trợ"):
            transform_providers(providers_data)

    def test_rejects_duplicate_id(self, mock_config_v1):
        providers_data = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        providers_data["providers"].append({
            "id": "gemini-default", "type": "openai", "name": "Dup"
        })
        with pytest.raises(ValueError, match="trùng"):
            transform_providers(providers_data)

    def test_rejects_unknown_active_id(self, mock_config_v1):
        providers_data = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        providers_data["active_id"] = "nonexistent"
        with pytest.raises(ValueError, match="không có trong providers"):
            transform_providers(providers_data)

    def test_result_has_version_2(self, mock_config_v1):
        providers_data = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        result = transform_providers(providers_data)
        assert result["version"] == 2


class TestTransformAppIni:
    def test_moves_thinking_level_to_runtime(self):
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read_string(
            "[MODEL]\nMODEL = x\nTHINKING_LEVEL = OFF\n[PROCESSING]\nK = 1\n"
        )
        new, changed = transform_app_ini(config)
        assert changed is True
        assert "RUNTIME" in new.sections()
        assert new.get("RUNTIME", "THINKING_LEVEL") == "OFF"
        assert "MODEL" not in new.sections()

    def test_keeps_processing_intact(self):
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read_string("[MODEL]\nMODEL = x\n[PROCESSING]\nK = 1\n")
        new, changed = transform_app_ini(config)
        assert new.get("PROCESSING", "K") == "1"

    def test_no_change_when_no_model_section(self):
        config = configparser.ConfigParser()
        config.optionxform = str
        config.read_string("[PROCESSING]\nK = 1\n")
        new, changed = transform_app_ini(config)
        assert changed is False


class TestRunMigrationDryRun:
    def test_dry_run_does_not_write_files(self, mock_config_v1):
        success = run_migration(mock_config_v1, dry_run=True)
        assert success is True
        # File vẫn giữ nguyên (v1)
        v1_text = (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        assert "step-3.7-flash" in v1_text  # chưa sửa
        # Backup dir không tồn tại
        assert not (mock_config_v1 / "backups").exists()

    def test_dry_run_reports_summary(self, mock_config_v1, caplog):
        with caplog.at_level("INFO"):
            run_migration(mock_config_v1, dry_run=True)
        assert "KẾT QUẢ CHUYỂN ĐỔI SCHEMA V2" in caplog.text
        assert "gemini-default" in caplog.text


class TestRunMigrationIdempotent:
    def test_migration_can_run_twice_without_data_loss(self, mock_config_v1):
        """R-O1: chạy migration 2 lần không làm mất data."""
        # Lần 1
        assert run_migration(mock_config_v1, dry_run=False) is True
        v2_data = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        assert v2_data["version"] == 2
        # Lần 2: providers.json đã v2; transform v2 phải idempotent
        # (sẽ thấy default_model="gemini-2.0-flash" đã đúng, không bị reset)
        assert run_migration(mock_config_v1, dry_run=False) is True
        v2_data_2 = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        assert v2_data_2["version"] == 2
        gemini = next(p for p in v2_data_2["providers"] if p["id"] == "gemini-default")
        assert gemini["default_model"] == "gemini-2.0-flash"
        # extra_field của openrouter vẫn còn
        openrouter = next(p for p in v2_data_2["providers"] if p["id"] == "openrouter")
        assert openrouter.get("extra_field") == "keep me"


class TestMigrationCleansAppIni:
    def test_app_ini_section_moved(self, mock_config_v1):
        run_migration(mock_config_v1, dry_run=False)
        app_ini_text = (mock_config_v1 / "app.ini").read_text(encoding="utf-8")
        assert "[MODEL]" not in app_ini_text
        assert "MODEL = step" not in app_ini_text
        assert "[RUNTIME]" in app_ini_text
        assert "THINKING_LEVEL = OFF" in app_ini_text
        # Process section giữ nguyên
        assert "[PROCESSING]" in app_ini_text
        assert "MAX_CHARS_PER_CHUNK = 20000" in app_ini_text


class TestMigrationCreatesManifest:
    def test_manifest_after_apply(self, mock_config_v1):
        run_migration(mock_config_v1, dry_run=False)
        manifest_files = list((mock_config_v1 / "backups").glob("migration-*.json"))
        assert len(manifest_files) == 1
        manifest = json.loads(manifest_files[0].read_text(encoding="utf-8"))
        assert manifest["version"] == 1
        assert "providers_json" in manifest
        assert "app_ini" in manifest
        assert "sha256_before" in manifest["providers_json"]


class TestMigrationRollback:
    def test_rollback_via_manifest(self, mock_config_v1):
        # Apply
        run_migration(mock_config_v1, dry_run=False)
        manifest_files = list((mock_config_v1 / "backups").glob("migration-*.json"))
        manifest_path = manifest_files[0]

        # Verify state v2
        v2 = json.loads((mock_config_v1 / "providers.json").read_text(encoding="utf-8"))
        assert v2["version"] == 2

        # Rollback via script
        rollback_script = (
            Path(__file__).parent.parent.parent / "scripts" / "rollback_providers.py"
        )
        result = subprocess.run(
            [
                "python3", str(rollback_script),
                "--config-dir", str(mock_config_v1),
                "--manifest", str(manifest_path),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

        # Verify state v1 trở lại
        v1_restored = json.loads(
            (mock_config_v1 / "providers.json").read_text(encoding="utf-8")
        )
        assert "version" not in v1_restored or v1_restored.get("version") == 1
        # gemini-default có default_model cũ "step-3.7-flash"
        gemini = next(p for p in v1_restored["providers"] if p["id"] == "gemini-default")
        assert gemini["default_model"] == "step-3.7-flash"

        # app.ini có section [MODEL] trở lại
        app_ini_text = (mock_config_v1 / "app.ini").read_text(encoding="utf-8")
        assert "[MODEL]" in app_ini_text
        assert "THINKING_LEVEL = OFF" in app_ini_text

    def test_rollback_rejects_missing_manifest(self, mock_config_v1, tmp_path):
        rollback_script = (
            Path(__file__).parent.parent.parent / "scripts" / "rollback_providers.py"
        )
        result = subprocess.run(
            [
                "python3", str(rollback_script),
                "--config-dir", str(mock_config_v1),
                "--manifest", str(tmp_path / "nonexistent.json"),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode != 0

    def test_rollback_rejects_tampered_manifest(self, mock_config_v1):
        run_migration(mock_config_v1, dry_run=False)
        manifest_files = list((mock_config_v1 / "backups").glob("migration-*.json"))
        manifest_path = manifest_files[0]
        # Tamper: đổi sha256
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["providers_json"]["sha256_before"] = "0" * 64
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        rollback_script = (
            Path(__file__).parent.parent.parent / "scripts" / "rollback_providers.py"
        )
        result = subprocess.run(
            [
                "python3", str(rollback_script),
                "--config-dir", str(mock_config_v1),
                "--manifest", str(manifest_path),
            ],
            capture_output=True, text=True,
        )
        assert result.returncode != 0
        assert "checksum" in result.stderr.lower()
