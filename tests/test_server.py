"""Test Phase 2 server: workspace/db tạm, AI client giả. Không gọi mạng thật."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import main as server
from core.app_db import get_db as real_get_db
from core.file_handler import SafeFileHandler as RealHandler
from core.provider_manager import AIProviderManager as RealMgr


class FakeClient:
    def __init__(self, *a, **k):
        pass

    async def translate_chunk(self, prompt: str) -> str:
        return "DỊCH:" + prompt[:20]


@pytest.fixture()
def app(tmp_path, monkeypatch):
    ws = tmp_path / "workspace"
    monkeypatch.setattr(server, "SafeFileHandler", lambda: RealHandler(ws))
    monkeypatch.setattr(server, "get_db", lambda: real_get_db(tmp_path / "app.db"))
    monkeypatch.setattr(server, "log_run", lambda *a, **k: None)
    monkeypatch.setattr(server, "build_client", FakeClient)
    monkeypatch.setattr(server, "AIProviderManager", lambda: RealMgr(tmp_path / "pconfig"))
    RealMgr(tmp_path / "pconfig").update_provider_keys_and_model(
        "gemini-default", api_keys=["DUMMY"], selected_model="gemini-test-1")
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def call(base, method, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_health(app):
    s, b = call(app, "GET", "/api/health")
    assert (s, json.loads(b)) == (200, {"ok": True})


def test_project_flow_and_chunks(app):
    assert call(app, "POST", "/api/projects", {"slug": "Kiem_Hiep"})[0] == 200
    s, b = call(app, "GET", "/api/projects")
    assert "Kiem_Hiep" in b.decode()
    # upload raw body
    req = urllib.request.Request(app + "/api/projects/Kiem_Hiep/upload?filename=ch01.md",
                                 data="Đoạn 1.\n\nĐoạn 2.".encode(), method="POST")
    with urllib.request.urlopen(req) as r:
        assert json.loads(r.read())["chars"] == 16
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/files")
    assert "ch01.md" in b.decode()
    s, b = call(app, "GET", "/api/chunks?project=Kiem_Hiep&file=ch01.md")
    assert json.loads(b)["chunks"][0]["chars"] == 16


def _seed(app):
    call(app, "POST", "/api/projects", {"slug": "Kiem_Hiep"})
    req = urllib.request.Request(app + "/api/projects/Kiem_Hiep/upload?filename=ch01.md",
                                 data="Đoạn 1.\n\nĐoạn 2.".encode(), method="POST")
    urllib.request.urlopen(req).read()


def test_prompts_and_translate_sse(app):
    _seed(app)
    s, b = call(app, "GET", "/api/prompts")
    assert "default_translation.txt" in b.decode()
    s, b = call(app, "POST", "/api/translate",
                {"project": "Kiem_Hiep", "file": "ch01.md",
                 "provider_id": "gemini-default", "prompt": "default_translation.txt"})
    assert s == 200
    txt = b.decode()
    assert "event: chunk" in txt and "DỊCH:" in txt and "event: done" in txt
    # save
    s, _ = call(app, "POST", "/api/save",
                {"project": "Kiem_Hiep", "file": "ch01.md", "content": "bản dịch xong"})
    assert s == 200


def test_path_traversal_blocked(app):
    s, b = call(app, "GET", "/api/chunks?project=X&file=../evil")
    assert s in (400, 404)


def test_provider_endpoints_masked_and_save(app):
    s, b = call(app, "GET", "/api/settings/providers")
    data = json.loads(b)
    assert data["active_id"] == "gemini-default"
    assert data["providers"][0]["api_keys"] == ["DUMMY"]  # single-user: full key
    # save đổi model + active
    s, _ = call(app, "POST", "/api/settings/save",
                {"provider_id": "gemini-default", "selected_model": "gemini-new-1"})
    assert s == 200
    s, b = call(app, "GET", "/api/settings/providers")
    assert json.loads(b)["providers"][0]["default_model"] == "gemini-new-1"
    # namespace validation: gpt-* vào gemini bị từ chối
    s, b = call(app, "POST", "/api/settings/save",
                {"provider_id": "gemini-default", "selected_model": "gpt-4o"})
    assert s == 400
