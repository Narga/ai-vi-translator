"""Content Translator — điểm vào duy nhất: tự bật WebUI server.

Chạy:  python main.py [host] [port]  ->  http://127.0.0.1:8000

Backend: stdlib http.server, 1 phiên dịch in-flight, SSE dịch tuần tự.
CLI (run.py) chỉ là tính năng phụ.
"""

import asyncio
import datetime
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core.app_db import get_db, log_run
from core.chunker import split_text
from core.config import AppConfig
from core.file_handler import SafeFileHandler
from core.prompt_engine import PromptEngine
from core.provider_manager import AIProviderManager
from run import build_client

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
ALLOWED_EXTS = {".txt", ".md", ".html"}
THINKING_LEVELS = AIProviderManager.THINKING_LEVELS  # hằng số, không bị patch trong test

_translate_lock = threading.Lock()


def _glossary_for_chunk(slug: str, chunk: str) -> str:
    """Lọc assets/glossary.txt chỉ lấy dòng có từ gốc xuất hiện trong chunk."""
    gfile = SafeFileHandler().get_project_dir(slug) / "assets" / "glossary.txt"
    if not gfile.exists():
        return ""
    hits = []
    for line in gfile.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        term = s.split("=", 1)[0].strip()
        if term and term in chunk:
            hits.append("- " + s)
    return "\n".join(hits)


def _upsert_file(project: str, filename: str, chars: int, chunks: int, status: str):
    con = get_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    size = len(filename.encode("utf-8")) + chars  # ước lượng nhẹ, khỏi stat thêm
    con.execute(
        "INSERT INTO files(project_slug, filename, size_bytes, char_count, chunk_count, status, updated_at)"
        " VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(project_slug, filename) DO UPDATE SET"
        " char_count=excluded.char_count, chunk_count=excluded.chunk_count,"
        " status=excluded.status, updated_at=excluded.updated_at",
        (project, filename, size, chars, chunks, status, now),
    )
    con.commit()
    con.close()


class Handler(BaseHTTPRequestHandler):
    server_version = "ContentTranslator/2.3"

    # ---- helpers ----
    def _json(self, obj, status=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, status=400):
        self._json({"error": msg}, status)

    def _body_json(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b""
        try:
            return json.loads(raw.decode("utf-8")) if raw else {}
        except Exception:
            return None

    def log_message(self, *a):  # gọn log
        pass

    # ---- static ----
    def _serve_static(self, path: str):
        rel = "index.html" if path in ("/", "") else path.lstrip("/")
        if ".." in rel or rel.startswith("/"):
            return self._err("Đường dẫn không hợp lệ", 404)
        f = (WEB_DIR / rel).resolve()
        try:
            f.relative_to(WEB_DIR.resolve())
        except ValueError:
            return self._err("Đường dẫn không hợp lệ", 404)
        if f.is_dir():
            f = f / "index.html"
        if not f.exists():
            return self._err("Không tìm thấy", 404)
        ctype = "text/html; charset=utf-8" if f.suffix == ".html" else "application/octet-stream"
        body = f.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # ---- GET ----
    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        fh = SafeFileHandler()

        if u.path == "/api/health":
            return self._json({"ok": True})

        if u.path == "/api/projects":
            base = fh.base_dir / "projects"
            projs = []
            if base.exists():
                for d in sorted(base.iterdir()):
                    if d.is_dir():
                        n = len(list((d / "sources").glob("*"))) if (d / "sources").exists() else 0
                        projs.append({"slug": d.name, "files": n})
            return self._json({"projects": projs})

        if u.path.startswith("/api/projects/") and u.path.endswith("/files"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/files")].strip("/"))
            try:
                src = fh.get_project_dir(slug) / "sources"
                tr = fh.get_project_dir(slug) / "translated"
                return self._json({
                    "sources": sorted(f.name for f in src.iterdir() if f.is_file()),
                    "translated": sorted(f.name for f in tr.iterdir() if f.is_file()),
                })
            except ValueError as e:
                return self._err(str(e))

        if u.path == "/api/chunks":
            project, fname = q.get("project", [""])[0], q.get("file", [""])[0]
            try:
                text = fh.read_source(project, fname)
            except (ValueError, FileNotFoundError) as e:
                return self._err(str(e), 404)
            cfg = AppConfig().get_config()
            chunks = split_text(text, max_chars=cfg["max_chunk_chars"])
            items = [
                {"i": i + 1, "chars": len(c), "tokens_est": len(c) // 4, "preview": c[:200]}
                for i, c in enumerate(chunks)
            ]
            if q.get("full", [""])[0] == "1":  # workspace cần hiện song ngữ
                for item, c in zip(items, chunks):
                    item["text"] = c
            return self._json({"chunks": items})

        if u.path == "/api/prompts":
            return self._json({"prompts": sorted(
                f.name for f in PromptEngine().prompts_dir.glob("*.txt") if f.is_file())})

        if u.path.startswith("/api/prompts/"):
            name = urllib.parse.unquote(u.path[len("/api/prompts/"):])
            if not name or "/" in name or "\\" in name or ".." in name:
                return self._err("Tên prompt không hợp lệ")
            try:
                return self._json({"name": name, "content": PromptEngine().load_prompt(name)})
            except FileNotFoundError as e:
                return self._err(str(e), 404)

        if u.path == "/api/settings":
            cfg = AppConfig().get_config()
            mgr = AIProviderManager()
            try:
                active = mgr.get_active()
            except Exception:
                active = {"id": "", "default_model": ""}
            return self._json({
                "max_chunk_chars": cfg.get("max_chunk_chars"),
                "timeout_seconds": cfg.get("timeout_seconds"),
                "api_delay_seconds": cfg.get("api_delay_seconds"),
                "thinking_levels": THINKING_LEVELS,
                "active_id": active.get("id"),
                "default_model": active.get("default_model"),
            })

        if u.path == "/api/settings/model-info":
            provider_id, model = q.get("provider_id", [""])[0], q.get("model", [""])[0]
            if not provider_id or not model:
                return self._err("Thiếu provider_id/model")
            try:
                return self._json(AIProviderManager().model_info(provider_id, model))
            except ValueError as e:
                return self._err(str(e), 404)

        if u.path == "/api/settings/providers":
            return self._json(AIProviderManager().masked_providers())

        if u.path == "/api/settings/models":
            provider_id = q.get("provider_id", [""])[0]
            if not provider_id:
                return self._err("Thiếu provider_id")
            try:
                return self._json(AIProviderManager().list_models_for_provider(provider_id))
            except ValueError as e:
                return self._err(str(e), 404)

        return self._serve_static(u.path)

    # ---- POST ----
    def do_POST(self):
        u = urllib.parse.urlparse(self.path)

        if u.path == "/api/projects":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            slug = (data.get("slug") or "").strip()
            try:
                SafeFileHandler().get_project_dir(slug)
                con = get_db()
                con.execute("INSERT OR IGNORE INTO projects(slug, created_at) VALUES (?,?)",
                            (slug, datetime.datetime.now().isoformat(timespec="seconds")))
                con.commit()
                con.close()
                return self._json({"slug": slug})
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/projects/") and u.path.endswith("/upload"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/upload")].strip("/"))
            ctype = self.headers.get("Content-Type", "")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            raw = self.rfile.read(length) if length else b""
            fname, content = None, None
            if "multipart/form-data" in ctype and 'name="file"' in raw.decode("utf-8", "replace"):
                # parse tối thiểu 1 file field
                head, _, body = raw.partition(b"\r\n\r\n")
                htxt = head.decode("utf-8", "replace")
                import re
                m = re.search(r'filename="([^"]+)"', htxt)
                fname = Path(m.group(1)).name if m else None
                content = body.rsplit(b"\r\n--", 1)[0] if fname else None
            else:  # raw bytes + ?filename=
                q = urllib.parse.parse_qs(u.query)
                fname = q.get("filename", [""])[0]
                content = raw
            if not fname or content is None:
                return self._err("Thiếu file (multipart field 'file' hoặc raw body + ?filename=)")
            if Path(fname).suffix.lower() not in ALLOWED_EXTS:
                return self._err("Chỉ nhận .txt/.md/.html")
            try:
                fh = SafeFileHandler()
                p = fh.get_source_path(slug, Path(fname).name)
                p.write_bytes(content)
                text = content.decode("utf-8", "replace")
                _upsert_file(slug, p.name, len(text), 0, "new")
                return self._json({"filename": p.name, "chars": len(text)})
            except ValueError as e:
                return self._err(str(e))

        if u.path == "/api/translate":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            return self._handle_translate_sse(data)

        if u.path == "/api/save":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            try:
                fh = SafeFileHandler()
                fh.save_translated(data["project"], data["file"], data.get("content", ""))
                _upsert_file(data["project"], data["file"], len(data.get("content", "")), 0, "done")
                return self._json({"path": f"translated/{data['file']}"})
            except (ValueError, KeyError) as e:
                return self._err(str(e))

        if u.path == "/api/settings/save":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            provider_id = (data.get("provider_id") or "").strip()
            if not provider_id:
                return self._err("Thiếu provider_id")
            try:
                mgr = AIProviderManager()
                mgr.update_provider_keys_and_model(
                    provider_id,
                    api_keys=data.get("api_keys"),
                    api_key=data.get("api_key"),
                    base_url=data.get("base_url"),
                    selected_model=data.get("selected_model"),
                    thinking=data.get("thinking"),
                    docs_url=data.get("docs_url"),
                )
                if data.get("set_active"):
                    mgr.set_active_provider(provider_id)
                return self._json({"ok": True})
            except ValueError as e:
                return self._err(str(e))

        if u.path == "/api/settings/providers":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            try:
                record = AIProviderManager().add_provider(
                    name=data.get("name", ""), ptype=data.get("type", "openai"),
                    base_url=data.get("base_url", ""), api_key=data.get("api_key", ""))
                return self._json(record)
            except ValueError as e:
                return self._err(str(e))

        return self._err("Không tìm thấy", 404)

    # ---- PUT ----
    def do_PUT(self):
        u = urllib.parse.urlparse(self.path)

        if u.path.startswith("/api/prompts/"):
            name = urllib.parse.unquote(u.path[len("/api/prompts/"):])
            if not name or "/" in name or "\\" in name or ".." in name or not name.endswith(".txt"):
                return self._err("Tên prompt phải là *.txt, không chứa /")
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            (PromptEngine().prompts_dir / name).write_text(data.get("content", ""), encoding="utf-8")
            return self._json({"ok": True})

        if u.path == "/api/settings":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            mgr = AppConfig()
            cfg = mgr.get_config()
            for k in ("max_chunk_chars", "timeout_seconds", "api_delay_seconds"):
                try:
                    v = float(data[k]) if k in data else None
                    if v is not None and (v > 0 or (k == "api_delay_seconds" and v >= 0)):
                        cfg[k] = int(v) if k == "max_chunk_chars" else v
                except (ValueError, TypeError):
                    pass
            from pathlib import Path as _P
            (_P(__file__).resolve().parent / "config" / "config.json").write_text(
                json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
            return self._json({"ok": True})

        return self._err("Không tìm thấy", 404)

    # ---- DELETE ----
    def do_DELETE(self):
        u = urllib.parse.urlparse(self.path)

        if u.path.startswith("/api/settings/providers/"):
            provider_id = urllib.parse.unquote(u.path[len("/api/settings/providers/"):]).strip("/")
            try:
                AIProviderManager().remove_provider(provider_id)
                return self._json({"ok": True})
            except ValueError as e:
                return self._err(str(e))

        return self._err("Không tìm thấy", 404)

    # ---- SSE translate ----
    def _handle_translate_sse(self, data):
        project, fname = data.get("project", ""), data.get("file", "")
        mgr = AIProviderManager()
        try:
            provider = mgr.get_by_id(data["provider_id"]) if data.get("provider_id") else mgr.get_active()
        except ValueError as e:
            return self._err(str(e))
        model = data.get("model") or provider.get("default_model", "")
        if not model:
            return self._err(f"Provider '{provider['id']}' chưa chọn model. Mở Cấu Hình để chọn.", 400)
        prompt_name = data.get("prompt", "default_translation.txt")
        extra = [e for e in (data.get("extra_prompts") or []) if isinstance(e, str)]

        if not _translate_lock.acquire(blocking=False):
            return self._err("Đang có 1 phiên dịch chạy. Vui lòng chờ xong.", 409)

        try:
            fh = SafeFileHandler()
            text = fh.read_source(project, fname)
        except (ValueError, FileNotFoundError) as e:
            _translate_lock.release()
            return self._err(str(e), 404)

        cfg = AppConfig().get_config()
        keys = mgr.get_keys(provider)
        if not keys:
            _translate_lock.release()
            return self._err(f"Chưa có API Key cho provider '{provider['id']}'. Nhập ở trang Cấu Hình.", 400)

        chunks = split_text(text, max_chars=cfg["max_chunk_chars"])
        if not chunks:
            _translate_lock.release()
            return self._err("File nguồn rỗng")
        try:
            eng = PromptEngine()
            base_tpl = eng.load_prompt(prompt_name)
            extras = [eng.load_prompt(e) for e in extra]
        except FileNotFoundError as e:
            _translate_lock.release()
            return self._err(str(e), 404)

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        def emit(event, payload):
            line = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            self.wfile.write(line.encode("utf-8"))
            self.wfile.flush()

        async def run_all():
            client = build_client(provider, model, keys, cfg["timeout_seconds"])
            delay = cfg.get("api_delay_seconds", 2.0)
            outs = []
            for i, ch in enumerate(chunks, 1):
                if i > 1 and delay > 0:
                    await asyncio.sleep(delay)  # giãn request, tránh 429
                p = base_tpl.replace("{{source_text}}", ch).replace(
                    "{{glossary_terms}}", _glossary_for_chunk(project, ch))
                for e in extras:
                    p += "\n\n" + e
                outs.append(await client.translate_chunk(p))
                emit("chunk", {"i": i, "n": len(chunks), "text": outs[-1]})
            return outs

        try:
            outs = asyncio.run(run_all())
            _upsert_file(project, fname, len(text), len(chunks), "translating")
            log_run(provider["id"], model, "ok")
            emit("done", {"chars": sum(len(o) for o in outs)})
        except (ConnectionError, TimeoutError, RuntimeError, ValueError) as e:
            log_run(provider["id"], model, "error", str(e))
            emit("error", {"error": str(e)})
        finally:
            _translate_lock.release()


def run(host="127.0.0.1", port=8000):
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    if not (WEB_DIR / "index.html").exists():
        (WEB_DIR / "index.html").write_text("<h1>Content Translator — thiếu web/index.html</h1>", encoding="utf-8")
    print(f"🌐 Mở http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    run(host, port)
