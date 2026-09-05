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

    async def translate_chunk(self, prompt: str, on_attempt=None, abort=None) -> str:
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
    assert s == 200 and d["ok"] is True and d["version"] == "3.1.0"  # lệch version = server cũ
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
    # rename ext lạ cho phép (không gate ext); traversal vẫn chặn
    s, b = call(app, "POST", "/api/projects/Kiem_Hiep/rename", {"old": "ch02b.md", "new": "x.exe"})
    assert s == 200 and json.loads(b)["filename"] == "x.exe"
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/rename", {"old": "x.exe", "new": "../evil.md"})
    assert s in (400, 404)
    # rename trùng -> _conflict tự động, không 400, không đè
    s, b = call(app, "POST", "/api/projects/Kiem_Hiep/rename", {"old": "x.exe", "new": "ch01.md"})
    assert s == 200 and json.loads(b)["filename"] == "ch01_conflict.md"
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/files")
    assert "ch01.md" in b.decode() and "ch01_conflict.md" in b.decode()
    # delete file
    s, _ = call(app, "DELETE", "/api/projects/Kiem_Hiep/files?filename=ch01_conflict.md")
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
    # 1 chunk gộp trải cả 2 file: chunk event liệt kê cả 2
    assert txt.count('"files": ["ch01.md", "ch02.md"]') >= 1
    # split-back: file có marker được lưu riêng vào results/
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/file?filename=ch01.md&side=results")
    assert s == 200 and "DỊCH:" in json.loads(b)["content"]
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/files")
    d = json.loads(b)
    assert "ch01.md" in d["results"] and "ch02.md" in d["results"]
    assert '"file": "ch01.md"' in txt and '"file": "ch02.md"' in txt  # done liệt kê từng file
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


def test_static_mime(app, tmp_path):
    import urllib.request
    import main as server

    css = server.WEB_DIR / "css" / "app.css"
    assert css.exists(), "web/css/app.css chưa được tách"
    with urllib.request.urlopen(app + "/css/app.css") as r:
        assert r.status == 200 and "text/css" in r.headers.get("Content-Type", "")
    with urllib.request.urlopen(app + "/js/app.js") as r:
        assert r.status == 200 and "javascript" in r.headers.get("Content-Type", "")
    s, _ = call(app, "GET", "/css/../main.py")
    assert s == 404  # traversal vẫn chặn


def test_prompt_rename_delete_backup(app):
    s, _ = call(app, "PUT", "/api/prompts/tmp_x.txt", {"content": "nội dung X"})
    assert s == 200
    s, b = call(app, "POST", "/api/prompts/rename", {"old": "tmp_x.txt", "new": "tmp_y.txt"})
    assert s == 200 and json.loads(b)["filename"] == "tmp_y.txt"
    s, _ = call(app, "POST", "/api/prompts/rename", {"old": "tmp_y.txt", "new": "x.md"})
    assert s == 400
    s, _ = call(app, "POST", "/api/prompts/rename",
                {"old": "tmp_y.txt", "new": "default_translation.txt"})
    assert s == 400  # trùng tên
    s, _ = call(app, "DELETE", "/api/prompts/tmp_y.txt")
    assert s == 200
    s, _ = call(app, "DELETE", "/api/prompts/tmp_y.txt")
    assert s == 404
    # backup vào dự án
    _seed(app)
    s, b = call(app, "POST", "/api/projects/Kiem_Hiep/prompt-backup",
                {"name": "default_translation.txt"})
    assert s == 200 and json.loads(b)["path"] == "assets/prompts/default_translation.txt"
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/prompt-backup", {"name": "khongco.txt"})
    assert s == 404
    s, _ = call(app, "POST", "/api/projects/../evil/prompt-backup", {"name": "default_translation.txt"})
    assert s in (400, 404)
    call(app, "DELETE", "/api/prompts/tmp_x.txt")  # dọn dù test giữa chừng có lỗi
    call(app, "DELETE", "/api/prompts/tmp_y.txt")


def test_project_archive(app, tmp_path, monkeypatch):
    import zipfile
    import main as server
    from core.file_handler import SafeFileHandler as RealHandler

    ws = tmp_path / "workspace"
    monkeypatch.setattr(server, "SafeFileHandler", lambda: RealHandler(ws))
    _seed(app)  # seed SAU patch để project nằm trong ws riêng của test này
    s, b = call(app, "POST", "/api/projects/Kiem_Hiep/archive")
    assert s == 200 and json.loads(b)["path"] == "archive/Kiem_Hiep.zip"
    assert zipfile.is_zipfile(ws / "archive" / "Kiem_Hiep.zip")
    assert not (ws / "projects" / "Kiem_Hiep").exists()
    s, b = call(app, "GET", "/api/projects")
    assert "Kiem_Hiep" not in b.decode()
    s, _ = call(app, "POST", "/api/projects/KhongCo/archive")
    assert s == 404


def test_translate_cancel_idle(app):
    s, b = call(app, "POST", "/api/translate/cancel")
    assert s == 200 and json.loads(b) == {"ok": True, "cancelled": False}  # không phiên nào chạy


def test_history(app, tmp_path, monkeypatch):
    import main as server
    from core.app_db import get_db as real_get_db, log_run as real_log_run

    db = tmp_path / "h.db"  # db riêng: fixture đang no-op log_run
    monkeypatch.setattr(server, "get_db", lambda: real_get_db(db))
    monkeypatch.setattr(server, "log_run",
                         lambda *a, **k: real_log_run(*a, **{**k, "db_path": db}))
    _seed(app)
    s, _ = call(app, "POST", "/api/translate",
                {"project": "Kiem_Hiep", "file": "ch01.md",
                 "provider_id": "gemini-default", "prompt": "default_translation.txt"})
    assert s == 200
    s, b = call(app, "GET", "/api/history?limit=5")
    d = json.loads(b)
    assert s == 200 and d["runs"]
    assert d["runs"][0]["project"] == "Kiem_Hiep" and d["runs"][0]["file"] == "ch01.md"
    assert d["runs"][0]["status"] == "ok"


def test_upload_conflict_and_binary(app):
    _seed(app)  # ch01.md đã có
    up = lambda fn, data: urllib.request.Request(
        app + "/api/projects/Kiem_Hiep/upload?filename=" + fn, data=data, method="POST")
    # trùng tên -> _conflict, không đè
    urllib.request.urlopen(up("ch01.md", "MỚI".encode())).read()
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/file?filename=ch01.md&side=sources")
    assert "Đoạn 1" in json.loads(b)["content"]  # gốc nguyên
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/file?filename=ch01_conflict.md&side=sources")
    assert "MỚI" in json.loads(b)["content"]
    # non-text nguyên bit (byte roundtrip đã test ở test_fileops; API check danh sách)
    blob = bytes(range(256))
    urllib.request.urlopen(up("b.dat", blob)).read()
    s, b = call(app, "GET", "/api/projects/Kiem_Hiep/files")
    assert "b.dat" in b.decode()
    # tên rỗng / side lạ / traversal
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/upload?filename=")
    assert s == 400
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/upload?filename=a.md&side=other")
    assert s == 400


def test_rename_batch(app):
    _seed(app)
    for fn, tx in (("raw_1.md", "một"), ("raw_2.md", "hai"), ("raw_3.md", "ba")):
        req = urllib.request.Request(
            app + "/api/projects/Kiem_Hiep/upload?filename=" + fn, data=tx.encode(), method="POST")
        urllib.request.urlopen(req).read()
    s, b = call(app, "POST", "/api/projects/Kiem_Hiep/rename-batch",
                {"side": "sources", "pattern": "Chuong{N}.md", "start": 1,
                 "zeropad": 2, "old_names": ["raw_1.md", "raw_2.md", "raw_3.md"]})
    d = json.loads(b)
    assert s == 200 and d["renamed"] == 3
    assert [r["new"] for r in d["results"]] == ["Chuong01.md", "Chuong02.md", "Chuong03.md"]
    # conflict 1 file không chặn file khác
    s, b = call(app, "POST", "/api/projects/Kiem_Hiep/rename-batch",
                {"side": "sources", "pattern": "Chuong{N}.md", "start": 1,
                 "zeropad": 2, "old_names": ["Chuong01.md", "Chuong02.md"]})
    d = json.loads(b)
    assert s == 200 and d["renamed"] == 0
    assert all(not r["ok"] and r["error"] for r in d["results"])
    # thiếu {N} / rỗng / traversal entry
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/rename-batch",
                {"side": "sources", "pattern": "Chuong.md", "start": 1,
                 "zeropad": 2, "old_names": ["Chuong01.md"]})
    assert s == 400
    s, _ = call(app, "POST", "/api/projects/Kiem_Hiep/rename-batch",
                {"side": "sources", "pattern": "{N}.md", "start": 1,
                 "zeropad": 2, "old_names": []})
    assert s == 400
    s, b = call(app, "POST", "/api/projects/Kiem_Hiep/rename-batch",
                {"side": "sources", "pattern": "{N}.md", "start": 5,
                 "zeropad": 2, "old_names": ["../evil.md", "Chuong03.md"]})
    d = json.loads(b)
    assert s == 200 and d["renamed"] == 1
    assert d["results"][0]["ok"] is False and d["results"][1]["new"] == "06.md"


def test_find_replace_hardening(app):
    _seed(app)
    req = urllib.request.Request(app + "/api/projects/Kiem_Hiep/upload?filename=b.dat",
                                 data=bytes(range(256)), method="POST")
    urllib.request.urlopen(req).read()
    s, b = call(app, "POST", "/api/find-replace",
                {"project": "Kiem_Hiep", "side": "sources", "pattern": "o",
                 "repl": "0", "regex": False})
    d = json.loads(b)
    assert s == 200 and "b.dat" not in d["files"] and "b.dat" in d["skipped"]
    # write-error 1 file không lan (giả lập atomic_write_text raise đúng file đó)
    import main as server
    real_write = server.atomic_write_text
    server.atomic_write_text = lambda p, c, **k: (_ for _ in ()).throw(OSError("đĩa lỗi")) \
        if str(p).endswith("ch01.md") else real_write(p, c, **k)
    try:
        s, b = call(app, "POST", "/api/find-replace",
                    {"project": "Kiem_Hiep", "side": "sources", "pattern": "1",
                     "repl": "1", "regex": False})
        d = json.loads(b)
        assert s == 200 and "ch01.md" in d["errors"] and d["total"] >= 0
    finally:
        server.atomic_write_text = real_write


def test_default_prompt_protected_and_prefs(app):
    s, b = call(app, "GET", "/api/settings")
    assert json.loads(b)["default_prompt"] == "default_translation.txt"
    s, _ = call(app, "PUT", "/api/settings", {"default_prompt": "x"})  # xấu -> giữ cũ
    assert s == 200
    s, b = call(app, "GET", "/api/settings")
    assert json.loads(b)["default_prompt"] == "default_translation.txt"
    s, _ = call(app, "PUT", "/api/settings", {"default_prompt": "custom_x.txt"})
    assert s == 200
    from core.config import CONFIG_FILE
    stored = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))["default_prompt"]
    assert stored == "custom_x.txt"  # đã lưu dù file chưa tồn tại
    s, b = call(app, "GET", "/api/settings")
    d = json.loads(b)
    assert d["default_prompt"] == "default_translation.txt"  # fallback vì file chưa tồn tại
    assert d["default_prompt_missing"] is True
    # prompt mặc định bất khả xóa/đổi tên (dù file chưa tồn tại, guard chạy trước)
    s, _ = call(app, "DELETE", "/api/prompts/custom_x.txt")
    assert s == 400
    s, _ = call(app, "PUT", "/api/prompts/prot.txt", {"content": "P"})
    assert s == 200
    s, _ = call(app, "PUT", "/api/settings", {"default_prompt": "prot.txt"})
    assert s == 200
    s, _ = call(app, "DELETE", "/api/prompts/prot.txt")
    assert s == 400
    s, _ = call(app, "POST", "/api/prompts/rename", {"old": "prot.txt", "new": "prot2.txt"})
    assert s == 400
    call(app, "PUT", "/api/settings", {"default_prompt": "default_translation.txt"})
    call(app, "DELETE", "/api/prompts/prot.txt")


def test_concurrency_lock_scope(app, monkeypatch):
    import asyncio
    import threading
    import time
    import main as server

    _seed(app)
    req = urllib.request.Request(app + "/api/projects/Kiem_Hiep/upload?filename=other.md",
                                 data="khác".encode(), method="POST")
    urllib.request.urlopen(req).read()
    call(app, "POST", "/api/projects", {"slug": "Khac"})

    class SlowClient:
        def __init__(self, *a, **k):
            pass

        async def translate_chunk(self, prompt, on_attempt=None, abort=None):
            await asyncio.sleep(3)
            return "XONG"

    monkeypatch.setattr(server, "build_client", SlowClient)
    errs = {}

    def run_tl():
        try:
            call(app, "POST", "/api/translate",
                 {"project": "Kiem_Hiep", "file": "ch01.md",
                  "provider_id": "gemini-default", "prompt": "default_translation.txt"})
        except Exception as e:  # SSE đọc tới cancel -> error event, không exception HTTP
            errs["tl"] = str(e)

    t = threading.Thread(target=run_tl, daemon=True)
    t.start()
    time.sleep(1.0)  # phiên treo đang giữ lock
    try:
        s, _ = call(app, "DELETE", "/api/projects/Kiem_Hiep/files?filename=ch01.md")
        file_running = s
        s, _ = call(app, "DELETE", "/api/projects/Kiem_Hiep/files?filename=other.md")
        file_other = s
        s, _ = call(app, "DELETE", "/api/projects/Khac")
        proj_other = s
        s, _ = call(app, "DELETE", "/api/projects/Kiem_Hiep")
        proj_running = s
        s, _ = call(app, "POST", "/api/translate/cancel")
        assert s == 200
    finally:
        t.join(timeout=10)
    assert file_running == 409, "file đang dịch phải 409"
    assert file_other == 200, "file khác cùng project được phép"
    assert proj_other == 200, "project khác được phép"
    assert proj_running == 409, "project đang dịch phải 409"


def test_project_create_info_and_cards(app):
    import urllib.parse
    s, b = call(app, "POST", "/api/projects",
                {"title": "Truyện Kiếm Hiệp", "author": "Tác Giả", "description": "Mô tả"})
    assert s == 200
    slug = json.loads(b)["slug"]
    assert slug  # slug tự sinh từ tên sách
    eslug = urllib.parse.quote(slug, safe="")
    s, b = call(app, "POST", "/api/projects",
                {"title": "Truyện Kiếm Hiệp", "author": "X", "description": ""})
    assert s == 200 and json.loads(b)["slug"] != slug  # trùng tên -> slug_2
    s, b = call(app, "GET", f"/api/projects/{eslug}/info")
    d = json.loads(b)
    assert s == 200 and d["title"] == "Truyện Kiếm Hiệp" and d["author"] == "Tác Giả"
    s, _ = call(app, "PUT", f"/api/projects/{eslug}/info",
                {"title": "Tên Mới", "author": "A2", "description": "D2"})
    assert s == 200
    s, b = call(app, "GET", "/api/projects")
    ps = {p["slug"]: p for p in json.loads(b)["projects"]}
    assert ps[slug]["title"] == "Tên Mới" and ps[slug]["done"] == 0
    assert set(("slug", "title", "author", "description", "sources", "results", "done")) \
        <= set(ps[slug])
    s, _ = call(app, "PUT", "/api/projects/../evil/info", {"title": "x"})
    assert s in (400, 404)
