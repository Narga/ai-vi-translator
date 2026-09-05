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

    async def translate_chunk(self, prompt: str, on_attempt=None) -> str:
        if on_attempt:
            on_attempt(1, 0)
        return "DỊCH:" + prompt[:20]


@pytest.fixture()
def app(tmp_path, monkeypatch):
    from core.config import CONFIG_FILE
    snapshot = CONFIG_FILE.read_bytes() if CONFIG_FILE.exists() else None
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
    if snapshot is not None:  # PUT /settings ghi config thật → hoàn nguyên
        CONFIG_FILE.write_bytes(snapshot)


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
    d = json.loads(b)
    assert s == 200 and d["ok"] is True and d["version"] == "2.6.0"  # lệch version = server cũ
    assert "started_at" in d  # đổi sau restart -> phát hiện tiến trình cũ


def test_restart_args_absolute():
    import os
    import sys

    args = server._restart_args()
    assert args[0] == (sys.executable or "python3")
    assert os.path.isabs(args[1])  # chốt bài học uv run: không argv tương đối


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


def test_file_delete_rename_and_project_delete(app):
    _seed(app)
    req = urllib.request.Request(app + "/api/projects/Kiem_Hiep/upload?filename=ch02.md",
                                 data="Nội dung 2.".encode(), method="POST")
    urllib.request.urlopen(req).read()
    # rename ok
    s, b = call(app, "POST", "/api/projects/Kiem_Hiep/rename", {"old": "ch02.md", "new": "ch02b.md"})
    assert s == 200 and json.loads(b)["filename"] == "ch02b.md"
    # rename ext lạ / traversal / trùng tên
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/rename", {"old": "ch02b.md", "new": "x.exe"})
    assert s == 400
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/rename", {"old": "ch02b.md", "new": "../evil.md"})
    assert s in (400, 404)
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/rename", {"old": "ch02b.md", "new": "ch01.md"})
    assert s == 400
    # delete file
    s, _ = call(app, "DELETE", "/api/projects/Kiem_Hiep/files?filename=ch02b.md")
    assert s == 200
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/files")
    assert "ch02b" not in b.decode() and "ch01.md" in b.decode()
    s, _ = call(app, "DELETE", "/api/projects/Kiem_Hiep/files?filename=khongco.md")
    assert s == 404
    s, _ = call(app, "DELETE", "/api/projects/Kiem_Hiep/files?filename=../evil.md")
    assert s in (400, 404)
    # delete project
    s, _ = call(app, "DELETE", "/api/projects/Kiem_Hiep")
    assert s == 200
    s, b = call(app, "GET", "/api/projects")
    assert "Kiem_Hiep" not in b.decode()
    s, _ = call(app, "DELETE", "/api/projects/KhongCo")
    assert s == 404


def test_view_file_sides(app):
    _seed(app)
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/file?filename=ch01.md&side=sources")
    assert s == 200 and "Đoạn 1" in json.loads(b)["content"]
    s, _ = call(app, "GET", "/api/projects/Kiem_Hiep/file?filename=ch01.md&side=results")
    assert s == 404  # chưa dịch
    s, _ = call(app, "GET", "/api/projects/Kiem_Hiep/file?filename=../evil&side=sources")
    assert s in (400, 404)
    s, _ = call(app, "GET", "/api/projects/Kiem_Hiep/file?filename=ch01.md&side=other")
    assert s == 400


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


def test_provider_crud_and_model_info(app):
    s, b = call(app, "POST", "/api/settings/providers",
                {"name": "Groq", "type": "openai", "base_url": "https://api.groq.com/openai/v1"})
    assert s == 200 and json.loads(b)["id"] == "groq"
    s, b = call(app, "GET", "/api/settings/model-info?provider_id=groq&model=qwen-x")
    assert s == 200 and "console.groq.com" in json.loads(b)["docs_url"]
    s, _ = call(app, "DELETE", "/api/settings/providers/groq")
    assert s == 200
    s, _ = call(app, "DELETE", "/api/settings/providers/gemini-default")
    assert s == 400  # active không xóa được


def test_prefs_extended(app):
    s, _ = call(app, "PUT", "/api/settings",
                {"max_chunk_chars": 8000, "api_delay_seconds": 0.5, "timeout_seconds": 60})
    assert s == 200
    s, b = call(app, "GET", "/api/settings")
    d = json.loads(b)
    assert (d["max_chunk_chars"], d["api_delay_seconds"], d["timeout_seconds"]) == (8000, 0.5, 60)
    assert "OFF" in d["thinking_levels"]


def test_merge_translate(app):
    _seed(app)
    req = urllib.request.Request(app + "/api/projects/Kiem_Hiep/upload?filename=ch02.md",
                                 data="Nội dung hai.".encode(), method="POST")
    urllib.request.urlopen(req).read()
    s, b = call(app, "POST", "/api/translate/merge",
                {"project": "Kiem_Hiep", "files": ["ch01.md", "ch02.md"],
                 "provider_id": "gemini-default", "prompt": "default_translation.txt"})
    assert s == 200
    txt = b.decode()
    assert "event: chunk" in txt and "event: done" in txt
    # 1 chunk gộp trải cả 2 file: chunk event + done đều liệt kê
    assert txt.count('"files": ["ch01.md", "ch02.md"]') >= 2
    # lỗi: rỗng / thiếu file
    s, _ = call(app, "POST", "/api/translate/merge",
                {"project": "Kiem_Hiep", "files": [], "provider_id": "gemini-default"})
    assert s == 400
    s, _ = call(app, "POST", "/api/translate/merge",
                {"project": "Kiem_Hiep", "files": ["khongco.md"], "provider_id": "gemini-default"})
    assert s == 404


def test_find_replace_scope(app):
    _seed(app)
    req = urllib.request.Request(app + "/api/projects/Kiem_Hiep/upload?filename=ch02.md",
                                 data="Đoạn 1 và đoạn 2.".encode(), method="POST")
    urllib.request.urlopen(req).read()
    s, b = call(app, "POST", "/api/find-replace",
                {"project": "Kiem_Hiep", "side": "sources", "pattern": "đoạn",
                 "repl": "PHẦN", "regex": False, "case": False})
    d = json.loads(b)
    assert s == 200 and d["total"] == 4 and set(d["files"]) == {"ch01.md", "ch02.md"}
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/file?filename=ch02.md&side=sources")
    assert "PHẦN 1 và PHẦN 2" in json.loads(b)["content"]
    # regex lỗi / thiếu mẫu / side lạ
    s, _ = call(app, "POST", "/api/find-replace",
                {"project": "Kiem_Hiep", "side": "sources", "pattern": "(a", "repl": "x", "regex": True})
    assert s == 400
    s, _ = call(app, "POST", "/api/find-replace",
                {"project": "Kiem_Hiep", "side": "sources", "pattern": "", "repl": "x"})
    assert s == 400
    s, _ = call(app, "POST", "/api/find-replace",
                {"project": "../evil", "side": "sources", "pattern": "a", "repl": "x"})
    assert s == 400
