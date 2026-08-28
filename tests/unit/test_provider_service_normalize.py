# tests/unit/test_provider_service_normalize.py
# v8.29.2 (zero-residue): ProviderService.save_providers() phải xóa field legacy
# 'qa_model' khỏi file ghi. Bao phủ cả nhánh ETag (save_providers_with_etag) lẫn
# non-ETag, idempotent khi không có qa_model, strip khi qa_model="".

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def _setup_providers_file(tmp_path: Path, providers: list) -> Path:
    cfg_dir = tmp_path / "config"
    cfg_dir.mkdir()
    (cfg_dir / "providers.json").write_text(
        json.dumps({"version": 2, "active_id": "x", "providers": providers},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cfg_dir


def test_save_providers_normalize_qa_model_non_etag(tmp_path):
    """Nhánh non-ETag: gọi save_providers() trực tiếp, qa_model bị xóa."""
    from backend.infrastructure.providers.provider_service import ProviderService
    cfg_dir = _setup_providers_file(tmp_path, [
        {"id": "x", "type": "gemini", "name": "X", "default_model": "gemini-2.0-flash",
         "api_keys": ["k"], "qa_model": "gemini-old-qa"},
    ])
    svc = ProviderService(config_dir=cfg_dir)
    data = svc.load_providers()
    data["providers"][0]["default_model"] = "gemini-2.5-flash"
    svc.save_providers(data)
    out = json.loads((cfg_dir / "providers.json").read_text())
    assert "qa_model" not in out["providers"][0]
    assert out["providers"][0]["default_model"] == "gemini-2.5-flash"


def test_save_providers_normalize_qa_model_etag(tmp_path):
    """Nhánh ETag: save_providers_with_etag() cũng xóa qa_model."""
    from backend.infrastructure.providers.provider_service import ProviderService
    cfg_dir = _setup_providers_file(tmp_path, [
        {"id": "x", "type": "gemini", "name": "X", "default_model": "gemini-2.0-flash",
         "api_keys": ["k"], "qa_model": "gemini-old-qa"},
    ])
    svc = ProviderService(config_dir=cfg_dir)
    data = svc.load_providers()
    data["providers"][0]["default_model"] = "gemini-2.5-flash"
    etag = svc.get_etag()
    result = svc.save_providers_with_etag(data, etag)
    assert "error" not in result, result
    out = json.loads((cfg_dir / "providers.json").read_text())
    assert "qa_model" not in out["providers"][0]
    assert out["providers"][0]["default_model"] == "gemini-2.5-flash"


def test_save_providers_idempotent_when_no_qa_model(tmp_path):
    """Provider không có qa_model → save không thay đổi field này."""
    from backend.infrastructure.providers.provider_service import ProviderService
    cfg_dir = _setup_providers_file(tmp_path, [
        {"id": "x", "type": "gemini", "name": "X", "default_model": "gemini-2.0-flash",
         "api_keys": ["k"]},
    ])
    svc = ProviderService(config_dir=cfg_dir)
    data = svc.load_providers()
    svc.save_providers(data)
    out = json.loads((cfg_dir / "providers.json").read_text())
    assert "qa_model" not in out["providers"][0]


def test_save_providers_strips_empty_qa_model(tmp_path):
    """qa_model="" cũng bị xóa (không giữ chuỗi rỗng thừa)."""
    from backend.infrastructure.providers.provider_service import ProviderService
    cfg_dir = _setup_providers_file(tmp_path, [
        {"id": "x", "type": "gemini", "name": "X", "default_model": "gemini-2.0-flash",
         "api_keys": ["k"], "qa_model": ""},
    ])
    svc = ProviderService(config_dir=cfg_dir)
    data = svc.load_providers()
    svc.save_providers(data)
    out = json.loads((cfg_dir / "providers.json").read_text())
    assert "qa_model" not in out["providers"][0]


def test_save_providers_normalize_multiple_providers(tmp_path):
    """Tất cả provider đều được normalize, không chỉ provider đầu tiên."""
    from backend.infrastructure.providers.provider_service import ProviderService
    cfg_dir = _setup_providers_file(tmp_path, [
        {"id": "a", "type": "gemini", "name": "A", "default_model": "gemini-2.0-flash",
         "api_keys": ["k1"], "qa_model": "qa-1"},
        {"id": "b", "type": "openai", "name": "B", "api_key": "sk-x",
         "base_url": "https://example.com/v1", "default_model": "m", "qa_model": "qa-2"},
        {"id": "c", "type": "gemini", "name": "C", "default_model": "gemini-2.0-flash",
         "api_keys": ["k3"]},
    ])
    # Sửa active_id cho hợp lệ
    data = json.loads((cfg_dir / "providers.json").read_text())
    data["active_id"] = "a"
    (cfg_dir / "providers.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    svc = ProviderService(config_dir=cfg_dir)
    data = svc.load_providers()
    svc.save_providers(data)
    out = json.loads((cfg_dir / "providers.json").read_text())
    for p in out["providers"]:
        assert "qa_model" not in p, f"provider {p['id']} vẫn còn qa_model"
