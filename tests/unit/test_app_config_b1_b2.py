# tests/unit/test_app_config_b1_b2.py
# B2: apply_values + save atomic với _pending buffer.
# (B1: get_qa_model_or_none đã bị xóa cùng với qa_model — v8.29.2 zero-residue.)

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def config_dir(tmp_path):
    """Tạo config dir với providers.json hợp lệ + app.ini."""
    d = tmp_path / "config"
    d.mkdir()
    import json
    (d / "providers.json").write_text(json.dumps({
        "version": 1,
        "active_id": "gemini-default",
        "providers": [
            {
                "id": "gemini-default",
                "type": "gemini",
                "name": "Google Gemini",
                "api_keys": ["AIzaTest12345"],
                "default_model": "gemini-2.0-flash",
            },
        ],
    }, ensure_ascii=False), encoding="utf-8")
    (d / "providers.json.bak").write_text((d / "providers.json").read_text(), encoding="utf-8")
    (d / "app.ini").write_text(
        "[PROCESSING]\nMAX_CHARS_PER_CHUNK = 20000\nTEMPERATURE = 1.0\n\n"
        "[RUNTIME]\nTHINKING_LEVEL = OFF\n",
        encoding="utf-8",
    )
    return d


class TestB2ApplyValuesAndSave:

    def test_apply_values_stages_in_pending(self, config_dir):
        from backend.infrastructure.config.app_config_service import AppConfigService
        svc = AppConfigService(config_dir)
        assert svc.get_pending_snapshot() is None
        svc.apply_values({
            ("PROCESSING", "MAX_CHARS_PER_CHUNK"): "50000",
            ("RUNTIME", "THINKING_LEVEL"): "LOW",
        })
        snapshot = svc.get_pending_snapshot()
        assert "MAX_CHARS_PER_CHUNK = 50000" in snapshot
        assert "THINKING_LEVEL = LOW" in snapshot

    def test_pending_does_not_mutate_in_memory_until_save(self, config_dir):
        from backend.infrastructure.config.app_config_service import AppConfigService
        svc = AppConfigService(config_dir)
        original_chunk = svc.get_default_chunk_size()
        svc.apply_values({("PROCESSING", "MAX_CHARS_PER_CHUNK"): "99999"})
        # _config chưa thay đổi
        assert svc.get_default_chunk_size() == original_chunk
        # save mới commit
        svc.save()
        assert svc.get_default_chunk_size() == 99999

    def test_save_writes_pending_to_file(self, config_dir):
        from backend.infrastructure.config.app_config_service import AppConfigService
        svc = AppConfigService(config_dir)
        svc.apply_values({("PROCESSING", "MAX_CHARS_PER_CHUNK"): "75000"})
        svc.save()
        text = (config_dir / "app.ini").read_text(encoding="utf-8")
        assert "MAX_CHARS_PER_CHUNK = 75000" in text
        # _pending cleared
        assert svc.get_pending_snapshot() is None

    def test_save_without_pending_uses_current_config(self, config_dir):
        from backend.infrastructure.config.app_config_service import AppConfigService
        svc = AppConfigService(config_dir)
        # Mutate _config trực tiếp (cách cũ)
        svc._config.set("PROCESSING", "MAX_CHARS_PER_CHUNK", "12345")
        svc.save()
        text = (config_dir / "app.ini").read_text(encoding="utf-8")
        assert "MAX_CHARS_PER_CHUNK = 12345" in text

    def test_apply_values_adds_new_section(self, config_dir):
        from backend.infrastructure.config.app_config_service import AppConfigService
        svc = AppConfigService(config_dir)
        svc.apply_values({("CUSTOM", "FOO"): "bar"})
        svc.save()
        text = (config_dir / "app.ini").read_text(encoding="utf-8")
        assert "[CUSTOM]" in text
        assert "FOO = bar" in text

    def test_apply_values_does_not_affect_disk_until_save(self, config_dir):
        from backend.infrastructure.config.app_config_service import AppConfigService
        svc = AppConfigService(config_dir)
        original_text = (config_dir / "app.ini").read_text(encoding="utf-8")
        svc.apply_values({("PROCESSING", "MAX_CHARS_PER_CHUNK"): "99999"})
        # Disk chưa thay đổi
        assert (config_dir / "app.ini").read_text(encoding="utf-8") == original_text
        # _config.get() vẫn trả giá trị cũ
        assert svc.get_default_chunk_size() == 20000

    def test_save_atomic_no_temp_leftover(self, config_dir):
        from backend.infrastructure.config.app_config_service import AppConfigService
        svc = AppConfigService(config_dir)
        svc.apply_values({("PROCESSING", "MAX_CHARS_PER_CHUNK"): "33333"})
        svc.save()
        # Không còn file .tmp
        leftover = list(config_dir.glob("*.tmp"))
        assert leftover == [], f"Temp files leaked: {leftover}"

    def test_pending_isolated_from_config(self, config_dir):
        """B2: thay đổi _pending KHÔNG ảnh hưởng _config cho đến khi save."""
        from backend.infrastructure.config.app_config_service import AppConfigService
        svc = AppConfigService(config_dir)
        original_config = svc._config
        svc.apply_values({("PROCESSING", "MAX_CHARS_PER_CHUNK"): "88888"})
        # _config là object khác sau apply_values (deep copy)
        assert svc._config is original_config
        # Sau save, _config mới có giá trị
        svc.save()
        assert svc.get_default_chunk_size() == 88888
