"""Test AIProviderManager: atomic write, masking, sentinel, namespace, cache, migration."""

import json
from unittest.mock import patch

import httpx
import pytest

from core.provider_manager import AIProviderManager


@pytest.fixture()
def mgr(tmp_path):
    return AIProviderManager(tmp_path / "config")


def test_default_config_created(mgr):
    cfg = mgr.load_config()
    assert cfg["active_id"] == "gemini-default"
    assert cfg["providers"][0]["default_model"] == ""


def test_migrate_legacy(tmp_path):
    cdir = tmp_path / "config"
    cdir.mkdir()
    (cdir / "keys.json").write_text(json.dumps(
        {"gemini_keys": ["K1"], "openai_compat_keys": ["SK1"]}), encoding="utf-8")
    (cdir / "config.json").write_text(json.dumps(
        {"providers": {"openai_compat": {"base_url": "https://x.ai/v1"}}}), encoding="utf-8")
    m = AIProviderManager(cdir)
    cfg = m.load_config()
    assert {p["id"] for p in cfg["providers"]} == {"gemini-default", "openai-compat"}
    assert cfg["providers"][0]["api_keys"] == ["K1"]
    assert cfg["providers"][1]["base_url"] == "https://x.ai/v1"


def test_full_keys_returned_for_single_user(mgr):
    mgr.update_provider_keys_and_model("gemini-default", api_keys=["SECRETKEY123"])
    data = mgr.masked_providers()  # single-user: trả full để sửa trực tiếp
    assert data["providers"][0]["api_keys"] == ["SECRETKEY123"]
    masked = mgr.masked_providers(mask=True)
    assert masked["providers"][0]["api_keys"] == ["SECR...Y123"]


def test_no_key_returns_fallback_with_warning(mgr):
    r = mgr.list_models_for_provider("gemini-default")
    assert r["source"] == "fallback" and "API key" in (r["error"] or "")


def test_save_keys_verbatim_single_user(mgr):
    # Single-user: sửa trực tiếp danh sách, xóa dòng = xóa key
    mgr.update_provider_keys_and_model("gemini-default", api_keys=["K1", "K2"])
    mgr.update_provider_keys_and_model("gemini-default", api_keys=["K1"])
    p = mgr.get_by_id("gemini-default")
    assert p["api_keys"] == ["K1"]


def test_namespace_validation(mgr):
    with pytest.raises(ValueError):
        mgr.update_provider_keys_and_model("gemini-default", selected_model="gpt-4o")
    mgr.update_provider_keys_and_model("gemini-default", selected_model="gemini-fresh-1")
    assert mgr.get_by_id("gemini-default")["default_model"] == "gemini-fresh-1"


def test_atomic_write_backup(mgr):
    mgr.update_provider_keys_and_model("gemini-default", api_keys=["K1"])
    assert (mgr.config_dir / "providers.json.bak").exists()
    assert mgr.load_config()["providers"][0]["api_keys"] == ["K1"]


def _gemini_payload(names=("gemini-9-new", "gemini-8-old", "text-embedding-004")):
    return {"models": [
        {"name": f"models/{n}",
         "supportedGenerationMethods": ["embedContent"] if "embedding" in n else ["generateContent"]}
        for n in names
    ]}


def test_list_models_live_and_cache(mgr):
    mgr.update_provider_keys_and_model("gemini-default", api_keys=["K1"])
    resp = httpx.Response(200, json=_gemini_payload(),
                          request=httpx.Request("GET", "http://t"))
    with patch("httpx.Client.get", return_value=resp) as g:
        r1 = mgr.list_models_for_provider("gemini-default")
        assert r1["source"] == "api" and r1["models"] == ["gemini-9-new", "gemini-8-old"]
        r2 = mgr.list_models_for_provider("gemini-default")
        assert r2["source"] == "cache"
        assert g.call_count == 1


def test_list_models_fallback(mgr):
    mgr.update_provider_keys_and_model(
        "gemini-default", api_keys=["K1"], selected_model="gemini-custom-zzz")
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("down")):
        r = mgr.list_models_for_provider("gemini-default")
    assert r["source"] == "fallback" and r["models"][0] == "gemini-custom-zzz"
