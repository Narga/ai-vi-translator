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
        assert r1["source"] == "api"
        assert [m["id"] for m in r1["models"]] == ["gemini-9-new", "gemini-8-old"]
        r2 = mgr.list_models_for_provider("gemini-default")
        assert r2["source"] == "cache"
        assert g.call_count == 1


def test_list_models_fallback(mgr):
    mgr.update_provider_keys_and_model(
        "gemini-default", api_keys=["K1"], selected_model="gemini-custom-zzz")
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("down")):
        r = mgr.list_models_for_provider("gemini-default")
    assert r["source"] == "fallback" and r["models"][0]["id"] == "gemini-custom-zzz"


def test_thinking_levels(mgr):
    mgr.update_provider_keys_and_model("gemini-default", thinking="MEDIUM")
    g = mgr.get_by_id("gemini-default")
    assert mgr.thinking_budget(g) == 8192
    mgr.update_provider_keys_and_model("gemini-default", thinking="OFF")
    assert mgr.thinking_budget(mgr.get_by_id("gemini-default")) is None
    assert mgr.thinking_budget({"type": "openai"}) is None  # openai bỏ qua
    with pytest.raises(ValueError):
        mgr.update_provider_keys_and_model("gemini-default", thinking="ULTRA")


def test_add_remove_provider(mgr):
    rec = mgr.add_provider("Groq", "openai", "https://api.groq.com/openai/v1", "GKEY")
    assert rec["id"] == "groq" and rec["docs_url"].startswith("https://console.groq.com")
    with pytest.raises(ValueError):  # không xóa active
        mgr.remove_provider("gemini-default")
    mgr.set_active_provider("groq")
    mgr.remove_provider("gemini-default")
    assert mgr.load_config()["active_id"] == "groq"


def test_model_info_gemini(mgr):
    mgr.update_provider_keys_and_model("gemini-default", api_keys=["K1"])
    resp = httpx.Response(200, json={"name": "models/gemini-9-new",
                                     "inputTokenLimit": 1000000, "outputTokenLimit": 64000},
                          request=httpx.Request("GET", "http://t"))
    with patch("httpx.Client.get", return_value=resp):
        info = mgr.model_info("gemini-default", "gemini-9-new")
    assert (info["input_limit"], info["output_limit"]) == (1000000, 64000)
    assert info["quota_url"].startswith("https://")


def test_model_info_openrouter_quota(mgr):
    rec = mgr.add_provider("OR", "openai", "https://openrouter.ai/api/v1", "SK")
    payload = {"data": [{"id": "deepseek/x:free", "name": "X Free", "context_length": 128000,
                         "pricing": {"prompt": "0", "completion": "0"}}]}
    keyinfo = {"data": {"usage": 12.5, "limit": 100}}
    def fake_get(url, headers=None):
        if url.endswith("/auth/key"):
            return httpx.Response(200, json=keyinfo, request=httpx.Request("GET", url))
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))
    with patch("httpx.Client.get", side_effect=fake_get):
        info = mgr.model_info(rec["id"], "deepseek/x:free")
    assert info["is_free"] is True and info["context_length"] == 128000
    assert info["rate_limits"] == {"usage": 12.5, "limit": 100}


def test_gemini_thinking_payload():
    import asyncio
    from unittest.mock import AsyncMock
    from core.ai_client import GeminiClient
    from core.key_rotator import KeyRotator

    async def go(budget):
        c = GeminiClient(KeyRotator(["K"]), model="m", thinking_budget=budget)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as p:
            p.return_value = httpx.Response(
                200, json={"candidates": [{"content": {"parts": [{"text": "ok"}]}}]},
                request=httpx.Request("POST", "http://t"))
            await c.translate_chunk("hi")
            return p.call_args.kwargs["json"]["generationConfig"]

    assert "thinkingConfig" not in asyncio.run(go(None))
    assert asyncio.run(go(1024))["thinkingConfig"] == {"thinkingBudget": 1024}
