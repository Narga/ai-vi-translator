"""Test Phase 4 Doc Viewer backend: resolve_doc + /api/docs*. Không gọi mạng thật."""

import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

import main as server
from core import fileops
from core.fileops import DocForbiddenError, read_doc_limited, resolve_doc


@pytest.fixture()
def docroot(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / "docs" / "sub").mkdir(parents=True)
    (root / "README.md").write_text("# Hi", encoding="utf-8")
    (root / "main.py").write_text("x=1", encoding="utf-8")
    (root / "docs" / "a.md").write_text("# A", encoding="utf-8")
    (root / "docs" / "sub" / "b.txt").write_text("B", encoding="utf-8")
    (root / "docs" / "c.html").write_text("<p>C</p>", encoding="utf-8")
    outside = tmp_path / "secret.md"
    outside.write_text("nope", encoding="utf-8")
    monkeypatch.setattr(server, "PROJECT_ROOT", root)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", root
    srv.shutdown()


def call(base, path):
    req = urllib.request.Request(base + path, method="GET")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_resolve_doc_ok(docroot):
    _, root = docroot
    assert resolve_doc(root, "README.md").name == "README.md"
    assert resolve_doc(root, "docs/sub/b.txt").name == "b.txt"


def test_resolve_doc_bad_path(docroot):
    _, root = docroot
    for bad in ("", "../app.db", "/etc/passwd", "docs\\..\\main.py", "a\x00.md"):
        with pytest.raises(ValueError):
            resolve_doc(root, bad)
    with pytest.raises(ValueError):  # sai ext
        resolve_doc(root, "main.py")
    with pytest.raises(ValueError):  # thư mục (không ext → input xấu, 400)
        resolve_doc(root, "docs")
    with pytest.raises(FileNotFoundError):
        resolve_doc(root, "docs/missing.md")


def test_resolve_doc_symlink_escape(docroot, tmp_path):
    _, root = docroot
    link = root / "docs" / "evil.md"
    try:
        link.symlink_to(tmp_path / "secret.md")
    except OSError:
        pytest.skip("không tạo được symlink trên máy này")
    with pytest.raises(DocForbiddenError):
        resolve_doc(root, "docs/evil.md")


def test_read_doc_limited_cap(docroot, monkeypatch):
    _, root = docroot
    monkeypatch.setattr(fileops, "MAX_DOC_BYTES", 10)
    (root / "big.md").write_text("x" * 20, encoding="utf-8")
    with pytest.raises(ValueError):
        read_doc_limited(root / "big.md")


def test_list_docs(docroot):
    base, _ = docroot
    s, b = call(base, "/api/docs")
    assert s == 200
    paths = {f["path"] for f in json.loads(b)}
    assert {"README.md", "docs/a.md", "docs/sub/b.txt", "docs/c.html"} <= paths
    assert not any(p.endswith(".py") for p in paths)  # whitelist ext


def test_list_docs_dir_symlink_escaped(docroot, tmp_path):
    base, root = docroot
    import shutil
    shutil.rmtree(root / "docs")
    try:
        (root / "docs").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("không tạo được symlink trên máy này")
    s, b = call(base, "/api/docs")
    assert s == 200
    paths = {f["path"] for f in json.loads(b)}
    assert "secret.md" not in paths and not any(
        p.startswith("docs/") for p in paths)  # bỏ qua cả thư mục


def test_content_ok_and_errors(docroot):
    base, _ = docroot
    s, b = call(base, "/api/docs/content?path=docs/a.md")
    d = json.loads(b)
    assert s == 200 and d["ext"] == ".md" and d["content"] == "# A"
    cases = [("/api/docs/content", 400),  # thiếu path
             ("/api/docs/content?path=", 400),
             ("/api/docs/content?path=../app.db", 400),
             ("/api/docs/content?path=%2e%2e%2fapp.db", 400),  # URL-encoded
             ("/api/docs/content?path=main.py", 400),  # sai ext
             ("/api/docs/content?path=docs", 400),  # thư mục không ext
             ("/api/docs/content?path=docs/missing.md", 404)]
    for path, want in cases:
        s, b = call(base, path)
        assert s == want, path
        assert "error" in json.loads(b)  # shape {"error"} thống nhất _err


def test_content_symlink_403(docroot, tmp_path):
    base, root = docroot
    link = root / "docs" / "evil.md"
    try:
        link.symlink_to(tmp_path / "secret.md")
    except OSError:
        pytest.skip("không tạo được symlink trên máy này")
    s, b = call(base, "/api/docs/content?path=docs/evil.md")
    assert s == 403 and "error" in json.loads(b)


def test_content_too_large_413(docroot, monkeypatch):
    base, root = docroot
    monkeypatch.setattr(fileops, "MAX_DOC_BYTES", 10)
    (root / "big.md").write_text("x" * 20, encoding="utf-8")
    s, _ = call(base, "/api/docs/content?path=big.md")
    assert s == 413
