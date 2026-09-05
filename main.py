"""Content Translator — điểm vào duy nhất: tự bật WebUI server.

Chạy:  python main.py [host] [port]  ->  http://127.0.0.1:8000

Backend: stdlib http.server, 1 phiên dịch in-flight, SSE dịch tuần tự.
CLI (run.py) chỉ là tính năng phụ.
"""

import asyncio
import datetime
import json
import os
import re
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from core.app_db import get_db, log_run
from core.chunker import split_text
from core.config import AppConfig
from core.errors import TranslateCancelled
from core.file_handler import SafeFileHandler, atomic_write_text
from core.prompt_engine import PromptEngine
from core.provider_manager import AIProviderManager
from run import build_client

PROJECT_ROOT = Path(__file__).resolve().parent
WEB_DIR = PROJECT_ROOT / "web"
THINKING_LEVELS = AIProviderManager.THINKING_LEVELS  # hằng số, không bị patch trong test

_translate_lock = threading.Lock()
_active_job = None  # (project, file) đang dịch — chặn xóa/đổi tên đích đang chạy
_cancel_event = threading.Event()  # hủy phiên đang chạy (POST /api/translate/cancel)
_STARTED_AT = datetime.datetime.now().isoformat(timespec="seconds")


def _restart_args() -> list:
    """argv cho os.execv với script absolutize — đúng mọi launcher (python/uv run/venv).

    Bài học dự án cũ: sys.argv[0] tương đối + CWD lệch = tiến trình mới chết lặng.
    """
    exe = sys.executable or "python3"
    if sys.argv and sys.argv[0] not in ("-c", ""):
        return [exe, str(Path(sys.argv[0]).resolve()), *sys.argv[1:]]
    return [exe, *sys.argv]


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


def _file_id(project: str, filename: str) -> int | None:
    """id hàng files (cho runs.file_id) — None nếu chưa index."""
    try:
        con = get_db()
        row = con.execute("SELECT id FROM files WHERE project_slug=? AND filename=?",
                          (project, filename)).fetchone()
        con.close()
        return row[0] if row else None
    except Exception:
        return None


def _delete_file_row(project: str, filename: str):
    con = get_db()
    con.execute("DELETE FROM files WHERE project_slug=? AND filename=?", (project, filename))
    con.commit()
    con.close()


def _rename_file_row(project: str, old: str, new: str):
    con = get_db()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    con.execute("UPDATE files SET filename=?, updated_at=? WHERE project_slug=? AND filename=?",
                (new, now, project, old))
    con.commit()
    con.close()


def _delete_project_rows(slug: str):
    con = get_db()
    con.execute("DELETE FROM files WHERE project_slug=?", (slug,))
    con.execute("DELETE FROM projects WHERE slug=?", (slug,))
    con.commit()
    con.close()


def _build_prompts(project: str, chunks: list, base_tpl: str, extras: list) -> list:
    """Dựng prompt từng chunk (glossary lọc theo chunk). Dùng chung translate + merge."""
    out = []
    for ch in chunks:
        p = base_tpl.replace("{{source_text}}", ch).replace(
            "{{glossary_terms}}", _glossary_for_chunk(project, ch))
        for e in extras:
            p += "\n\n" + e
        out.append(p)
    return out


def _split_marked(text: str, files: list):
    """Chia output gộp về từng file theo marker `===== FILE: name =====`.
    Trả ({fname: segment}, [(start, end, fname), ...]). File không có marker
    thì không có key (caller fallback). Marker line không tính vào nội dung."""
    out, regs, cur, buf, seg_start = {}, [], None, [], 0
    pos = 0
    for line in text.split("\n"):
        s = line.strip()
        name = None
        if s.startswith("===== FILE:") and s.endswith("====="):
            mid = s[len("===== FILE:"):-len("=====")].strip()
            if mid in files:
                name = mid
            else:
                for f in files:
                    if f and f in s:
                        name = f
                        break
        if name is not None:
            if cur is not None:
                out[cur] = "\n".join(buf).strip()
                regs.append((seg_start, pos, cur))
            cur, buf = name, []
            seg_start = pos + len(line) + 1
        else:
            buf.append(line)
        pos += len(line) + 1
    if cur is not None:
        out[cur] = "\n".join(buf).strip()
        regs.append((seg_start, pos, cur))
    return out, regs


def _split_output(outs: list, seg_names: list, files: list) -> dict:
    """Gộp output rồi chia về từng file: ưu tiên marker; file thiếu marker chỉ nhận
    chunk chưa nằm trong region của file khác (không double-count). Heuristic —
    AI giữ marker thì chia chính xác."""
    full = "\n\n".join(outs)
    marked, regs = _split_marked(full, files)
    if set(marked) >= set(files):
        return {f: marked[f] for f in files}
    res = dict(marked)
    cur = 0
    for o, segs_ in zip(outs, seg_names):
        at = full.find(o, cur)
        if at < 0:
            continue
        cur = at + len(o)
        f0 = (segs_ or [None])[0]
        if f0 not in files or f0 in res:
            continue
        if any(s <= at and at + len(o) <= e and rf != f0 for s, e, rf in regs):
            continue
        res[f0] = ((res.get(f0, "") + "\n\n" + o).strip() if res.get(f0) else o)
    return {f: res.get(f, "") for f in files}


def _attribute(chunks: list, joined: str, segs: list) -> list:
    """Map mỗi chunk -> danh sách file nó trải qua (thường 1, chunk gộp có thể 2+)."""
    out, cur = [], 0
    for ch in chunks:
        at = joined.find(ch, cur)
        if at < 0:
            out.append([])
            continue
        cur = at + len(ch)
        out.append([f for f, s, e in segs if s < at + len(ch) and at < e])
    return out


async def _run_chunks(client, prompts: list, seg_names: list, delay: float,
                      nkeys: int, emit, cancel=None) -> list:
    """Chạy tuần tự từng prompt, emit progress/chunk. Dùng chung translate + merge."""
    outs = []
    for i, p in enumerate(prompts, 1):
        if cancel is not None and cancel.is_set():
            raise TranslateCancelled("Đã hủy bởi người dùng")
        if i > 1 and delay > 0:
            await asyncio.sleep(delay)  # giãn request, tránh 429
        seg = seg_names[i - 1] if seg_names else []

        def _progress(attempt, key_idx, _i=i, _seg=seg):
            emit("progress", {"i": _i, "n": len(prompts), "attempt": attempt,
                              "key": key_idx + 1, "keys": nkeys,
                              "file": (_seg or [None])[0], "files": _seg})

        outs.append(await client.translate_chunk(p, on_attempt=_progress, abort=cancel))
        emit("chunk", {"i": i, "n": len(prompts), "text": outs[-1],
                       "file": (seg or [None])[0], "files": seg})
    return outs


class Handler(BaseHTTPRequestHandler):
    # Ranh giới R2#archi — mọi endpoint file tuân thủ:
    # validation/sanitize: core.fileops.guard_name (NFC, rỗng, traversal)
    # file operation: file_handler/fileops (unique_name, atomic write, strict read)
    # database: _upsert/_delete/_rename_file_row, _delete_project_rows
    # HTTP response: _json/_err (không đoán path ở handler, không tự xử conflict riêng)
    # SSE session: _translate_lock + _active_job + _cancel_event, giải phóng ở finally
    server_version = "ContentTranslator/3.1.0"

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
    MIME_MAP = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".svg": "image/svg+xml", ".json": "application/json"}

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
        ctype = self.MIME_MAP.get(f.suffix.lower(), "application/octet-stream")
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
            return self._json({"ok": True, "version": "3.1.0", "started_at": _STARTED_AT})

        if u.path == "/api/history":
            try:
                limit = max(1, min(int(q.get("limit", ["20"])[0]), 100))
            except (ValueError, TypeError):
                limit = 20
            con = get_db()
            rows = con.execute(
                "SELECT f.project_slug, f.filename, r.provider, r.model,"
                " r.status, r.error, r.started_at, r.finished_at"
                " FROM runs r LEFT JOIN files f ON r.file_id = f.id"
                " ORDER BY r.id DESC LIMIT ?", (limit,)).fetchall()
            con.close()
            return self._json({"runs": [
                {"project": r[0] or "—", "file": r[1] or "—", "provider": r[2],
                 "model": r[3], "status": r[4], "error": r[5] or "",
                 "started_at": r[6], "finished_at": r[7]} for r in rows]})

        if u.path == "/api/projects":
            base = fh.base_dir / "projects"
            con = get_db()
            meta = {r[0]: {"title": r[1] or "", "author": r[2] or "", "description": r[3] or ""}
                    for r in con.execute("SELECT slug, title, author, description FROM projects").fetchall()}
            con.close()
            projs = []
            if base.exists():
                for d in sorted(base.iterdir()):
                    if d.is_dir():
                        src = {f.name for f in (d / "sources").iterdir() if f.is_file()} \
                            if (d / "sources").exists() else set()
                        res = {f.name for f in (d / "results").iterdir() if f.is_file()} \
                            if (d / "results").exists() else set()
                        m = meta.get(d.name, {"title": "", "author": "", "description": ""})
                        projs.append({"slug": d.name, "title": m["title"], "author": m["author"],
                                      "description": m["description"],
                                      "sources": len(src), "results": len(res),
                                      "done": len(src & res)})
            return self._json({"projects": projs})

        if u.path.startswith("/api/projects/") and u.path.endswith("/info"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/info")].strip("/"))
            try:
                SafeFileHandler().get_project_dir(slug)
            except ValueError as e:
                return self._err(str(e))
            con = get_db()
            row = con.execute("SELECT title, author, description FROM projects WHERE slug=?",
                              (slug,)).fetchone()
            con.close()
            if row:
                return self._json({"slug": slug, "title": row[0] or "", "author": row[1] or "",
                                   "description": row[2] or ""})
            return self._json({"slug": slug, "title": "", "author": "", "description": ""})

        if u.path.startswith("/api/projects/") and u.path.endswith("/files"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/files")].strip("/"))
            try:
                src = fh.get_project_dir(slug) / "sources"
                out = fh.get_project_dir(slug) / "results"
                return self._json({
                    "sources": sorted(f.name for f in src.iterdir() if f.is_file()),
                    "results": sorted(f.name for f in out.iterdir() if f.is_file()),
                })
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/projects/") and u.path.endswith("/file"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/file")].strip("/"))
            fname = q.get("filename", [""])[0]
            side = q.get("side", ["sources"])[0]
            if side not in ("sources", "results"):
                return self._err("side phải là sources|results")
            try:
                fh = SafeFileHandler()
                p = fh.get_source_path(slug, fname) if side == "sources" \
                    else fh.get_output_path(slug, fname)
                return self._json({"content": p.read_text(encoding="utf-8", errors="replace")})
            except FileNotFoundError as e:
                return self._err(str(e), 404)
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
            dp = cfg.get("default_prompt", "default_translation.txt")
            dp_missing = not (PromptEngine().prompts_dir / dp).is_file()
            return self._json({
                "max_chunk_chars": cfg.get("max_chunk_chars"),
                "timeout_seconds": cfg.get("timeout_seconds"),
                "api_delay_seconds": cfg.get("api_delay_seconds"),
                "default_prompt": dp if not dp_missing else "default_translation.txt",
                "default_prompt_missing": dp_missing,
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
            from core.fileops import slugify, unique_slug
            fh = SafeFileHandler()
            slug = (data.get("slug") or "").strip()
            title = (data.get("title") or "").strip()
            author = (data.get("author") or "").strip()
            description = (data.get("description") or "").strip()
            try:
                if not slug:
                    slug = unique_slug(fh.base_dir / "projects", slugify(title))
                fh.get_project_dir(slug)
            except ValueError as e:
                return self._err(str(e))
            con = get_db()
            now = datetime.datetime.now().isoformat(timespec="seconds")
            con.execute("INSERT OR IGNORE INTO projects(slug, created_at) VALUES (?,?)", (slug, now))
            con.execute("UPDATE projects SET title=?, author=?, description=? WHERE slug=?",
                        (title, author, description, slug))
            con.commit()
            con.close()
            return self._json({"slug": slug})

        if u.path.startswith("/api/projects/") and u.path.endswith("/upload"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/upload")].strip("/"))
            side = urllib.parse.parse_qs(u.query).get("side", ["sources"])[0]
            if side not in ("sources", "results"):
                return self._err("side phải là sources|results")
            ctype = self.headers.get("Content-Type", "")
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            raw = self.rfile.read(length) if length else b""
            fname, content = None, None
            if "multipart/form-data" in ctype and 'name="file"' in raw.decode("utf-8", "replace"):
                # parse tối thiểu 1 file field (giữ nguyên bytes gốc)
                head, _, body = raw.partition(b"\r\n\r\n")
                htxt = head.decode("utf-8", "replace")
                m = re.search(r'filename="([^"]+)"', htxt)
                fname = Path(m.group(1)).name if m else None
                content = body.rsplit(b"\r\n--", 1)[0] if fname else None
            else:  # raw bytes + ?filename=
                q = urllib.parse.parse_qs(u.query)
                fname = q.get("filename", [""])[0]
                content = raw
            if not fname or content is None:
                return self._err("Thiếu file (multipart field 'file' hoặc raw body + ?filename=)")
            # --- validation/sanitize (helper chung, không gate ext) ---
            try:
                fh = SafeFileHandler()
                target = fh.get_project_dir(slug) / side
                # --- file operation (xb: không ghi đè, chống race) ---
                from core.fileops import write_bytes_no_overwrite
                actual = write_bytes_no_overwrite(target, fname, content)
                text = content.decode("utf-8", "replace")
                # --- database ---
                _upsert_file(slug, actual, len(text), 0, "new")
                # --- HTTP response (trả TÊN THỰC TẾ) ---
                return self._json({"filename": actual, "chars": len(text)})
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/projects/") and u.path.endswith("/archive"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/archive")].strip("/"))
            if _active_job and _active_job[0] == slug:
                return self._err("Dự án đang có phiên dịch chạy, chờ xong rồi lưu trữ.", 409)
            try:
                SafeFileHandler().archive_project(slug)
                _delete_project_rows(slug)
                return self._json({"path": f"archive/{slug}.zip"})
            except FileNotFoundError as e:
                return self._err(str(e), 404)
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/projects/") and u.path.endswith("/prompt-backup"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/prompt-backup")].strip("/"))
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            try:
                eng = PromptEngine()
                clean = eng._check_name(data.get("name"))
                content = eng.load_prompt(clean)
                dest = SafeFileHandler().get_project_dir(slug) / "assets" / "prompts"
                dest.mkdir(parents=True, exist_ok=True)
                atomic_write_text(dest / clean, content)
                return self._json({"path": f"assets/prompts/{clean}"})
            except FileNotFoundError as e:
                return self._err(str(e), 404)
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/projects/") and u.path.endswith("/rename"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/rename")].strip("/"))
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            old, new = (data.get("old") or "").strip(), (data.get("new") or "").strip()
            if _active_job and _active_job[0] == slug and _active_job[1] == old:
                return self._err("File đang dịch, chờ xong rồi đổi tên.", 409)
            try:
                fh = SafeFileHandler()
                pairs = fh.rename_paired(slug, old, new)  # [(side, newname)], va chạm -> _conflict
                # --- database: cùng tên mọi bên thì rename row, lệch thì dựng lại ---
                newnames = {n for _, n in pairs}
                if len(newnames) == 1:
                    _rename_file_row(slug, old, pairs[0][1])
                else:
                    _delete_file_row(slug, old)
                    for _, nn in pairs:
                        _upsert_file(slug, nn, 0, 0, "renamed")
                # --- HTTP response ---
                primary = next((n for s, n in pairs if s == "sources"), pairs[0][1])
                return self._json({"filename": primary,
                                   "renames": [{"side": s, "old": old, "new": n} for s, n in pairs]})
            except FileNotFoundError as e:
                return self._err(str(e), 404)
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/projects/") and u.path.endswith("/rename-batch"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/rename-batch")].strip("/"))
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            side = data.get("side", "sources")
            if side not in ("sources", "results"):
                return self._err("side phải là sources|results")
            pattern = data.get("pattern") or ""
            if "{N}" not in pattern:
                return self._err("Pattern phải chứa {N} (vd: Chuong{N})")
            try:
                start = int(data.get("start", 1))
                zeropad = int(data.get("zeropad", 2))
            except (ValueError, TypeError):
                return self._err("start/zeropad phải là số")
            olds = [o for o in (data.get("old_names") or []) if isinstance(o, str)]
            if not olds:
                return self._err("Chưa chọn file nào")
            from core.fileops import guard_name
            try:
                guard_name(pattern.replace("{N}", "0" * max(zeropad, 1)))
            except ValueError:
                return self._err("Pattern tạo ra tên không hợp lệ")
            try:
                fh = SafeFileHandler()
                target = fh.get_project_dir(slug) / side
            except ValueError as e:
                return self._err(str(e))
            if _active_job and _active_job[0] == slug and _active_job[1] in olds:
                return self._err("Có file đang dịch trong danh sách, chờ xong rồi đổi.", 409)
            # tên mới dự kiến (giữ đuôi old khi thiếu-dot) + phát hiện trùng nội bộ trước
            planned, seen = [], set()
            for idx, old in enumerate(olds):
                num = str(start + idx).zfill(zeropad) if zeropad > 0 else str(start + idx)
                new = pattern.replace("{N}", num)
                if "." not in new and "." in old:
                    new = new + "." + old.rsplit(".", 1)[-1]
                planned.append((old, new, new in seen))
                seen.add(new)
            results, renamed = [], 0
            for old, new, dup in planned:
                entry = {"old": old, "new": new, "ok": False, "error": ""}
                if dup:
                    entry["error"] = "Trùng tên trong batch"
                else:
                    try:
                        clean_old = guard_name(old)
                        clean_new = guard_name(new)
                        src = fh._validate_path(target / clean_old)
                        dst = fh._validate_path(target / clean_new)
                        if not src.is_file():
                            entry["error"] = "File nguồn đã mất"
                        elif dst.exists():
                            entry["error"] = "Tên đích đã tồn tại"
                        else:
                            src.rename(dst)
                            _rename_file_row(slug, clean_old, clean_new)
                            entry["ok"] = True
                            renamed += 1
                    except ValueError as e:
                        entry["error"] = str(e)
                results.append(entry)
            return self._json({"results": results, "renamed": renamed})

        if u.path == "/api/prompts/rename":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            try:
                if (data.get("old") or "").strip() == AppConfig().get_config().get("default_prompt"):
                    return self._err("Đây là prompt mặc định — đổi mặc định khác trước khi đổi tên.", 400)
                name = PromptEngine().rename_prompt(data.get("old"), data.get("new"))
                return self._json({"filename": name})
            except FileNotFoundError as e:
                return self._err(str(e), 404)
            except ValueError as e:
                return self._err(str(e))

        if u.path == "/api/translate":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            return self._handle_translate_sse(data)

        if u.path == "/api/translate/merge":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            return self._handle_merge_sse(data)

        if u.path == "/api/restart":
            args = _restart_args()
            threading.Timer(0.5, lambda: os.execv(args[0], args)).start()
            return self._json({"ok": True, "restarting": True})

        if u.path == "/api/translate/cancel":
            _cancel_event.set()
            return self._json({"ok": True, "cancelled": _active_job is not None})

        if u.path == "/api/find-replace":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            slug = (data.get("project") or "").strip()
            side = data.get("side", "sources")
            if side not in ("sources", "results"):
                return self._err("side phải là sources|results")
            pattern = data.get("pattern") or ""
            if not pattern:
                return self._err("Nhập mẫu tìm")
            repl = data.get("repl", "")
            flags = 0 if data.get("case") else re.IGNORECASE
            try:
                rx_src = pattern if data.get("regex") else re.escape(pattern)
                if data.get("word"):
                    rx_src = r"\b(?:" + rx_src + r")\b"
                rx = re.compile(rx_src, flags)
            except re.error as e:
                return self._err(f"Regex lỗi: {e}")
            try:
                from core.fileops import read_text_strict
                target = SafeFileHandler().get_project_dir(slug) / side
                out, skipped, errors, total = {}, [], {}, 0
                for f in sorted(target.iterdir()):
                    if not f.is_file():
                        continue
                    try:
                        text = read_text_strict(f)  # binary -> skip, không decode-replace-rồi-ghi
                    except ValueError:
                        skipped.append(f.name)
                        continue
                    new, n = rx.subn(repl, text)
                    if not n:
                        continue
                    try:
                        atomic_write_text(f, new)  # all-or-nothing từng file
                    except OSError as e:
                        errors[f.name] = str(e)
                        continue
                    out[f.name] = n
                    total += n
                return self._json({"files": out, "skipped": skipped,
                                   "errors": errors, "total": total})
            except ValueError as e:
                return self._err(str(e))

        if u.path == "/api/save":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            try:
                fh = SafeFileHandler()
                fh.save_output(data["project"], data["file"], data.get("content", ""))
                _upsert_file(data["project"], data["file"], len(data.get("content", "")), 0, "done")
                return self._json({"path": f"results/{data['file']}"})
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
            (PromptEngine().prompts_dir / name).parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(PromptEngine().prompts_dir / name, data.get("content", ""))
            return self._json({"ok": True})

        if u.path.startswith("/api/projects/") and u.path.endswith("/info"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/info")].strip("/"))
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            try:
                SafeFileHandler().get_project_dir(slug)
            except ValueError as e:
                return self._err(str(e))
            con = get_db()
            now = datetime.datetime.now().isoformat(timespec="seconds")
            con.execute("INSERT OR IGNORE INTO projects(slug, created_at) VALUES (?,?)", (slug, now))
            con.execute("UPDATE projects SET title=?, author=?, description=? WHERE slug=?",
                        ((data.get("title") or "").strip(), (data.get("author") or "").strip(),
                         (data.get("description") or "").strip(), slug))
            con.commit()
            con.close()
            return self._json({"ok": True})

        if u.path == "/api/settings":
            data = self._body_json()
            if data is None:
                return self._err("JSON không hợp lệ")
            from core.config import normalize_prefs
            cfg = AppConfig().get_config()
            norm = normalize_prefs(data)
            for k in ("max_chunk_chars", "timeout_seconds", "api_delay_seconds"):
                if k in data:
                    try:
                        valid = float(data[k]) == norm[k]
                    except (ValueError, TypeError):
                        valid = False
                    if valid:  # sai → giữ giá trị đang lưu, không ghi đè default
                        cfg[k] = norm[k]
            if "default_prompt" in data:  # str *.txt, sai → giữ cũ
                dp = data["default_prompt"]
                if isinstance(dp, str) and dp.strip().endswith(".txt") and "/" not in dp:
                    cfg["default_prompt"] = dp.strip()
            from pathlib import Path as _P
            atomic_write_text(_P(__file__).resolve().parent / "config" / "config.json",
                              json.dumps(cfg, indent=2, ensure_ascii=False))
            return self._json({"ok": True})

        return self._err("Không tìm thấy", 404)

    # ---- DELETE ----
    def do_DELETE(self):
        u = urllib.parse.urlparse(self.path)

        if u.path.startswith("/api/prompts/"):
            name = urllib.parse.unquote(u.path[len("/api/prompts/"):])
            try:
                if name == AppConfig().get_config().get("default_prompt"):
                    return self._err("Đây là prompt mặc định — đổi mặc định khác trước khi xóa.", 400)
                PromptEngine().delete_prompt(name)
                return self._json({"ok": True})
            except FileNotFoundError as e:
                return self._err(str(e), 404)
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/projects/") and u.path.endswith("/files"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):-len("/files")].strip("/"))
            fname = urllib.parse.parse_qs(u.query).get("filename", [""])[0]
            if _active_job and (_active_job[0], _active_job[1]) == (slug, fname):
                return self._err("File đang dịch, chờ xong rồi xóa.", 409)
            try:
                SafeFileHandler().delete_file(slug, fname)
                _delete_file_row(slug, fname)
                return self._json({"ok": True})
            except FileNotFoundError as e:
                return self._err(str(e), 404)
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/projects/"):
            slug = urllib.parse.unquote(u.path[len("/api/projects/"):]).strip("/")
            if not slug or "/" in slug:
                return self._err("Không tìm thấy", 404)
            if _active_job and _active_job[0] == slug:
                return self._err("Dự án đang có phiên dịch chạy, chờ xong rồi xóa.", 409)
            try:
                SafeFileHandler().delete_project(slug)
                _delete_project_rows(slug)
                return self._json({"ok": True})
            except FileNotFoundError as e:
                return self._err(str(e), 404)
            except ValueError as e:
                return self._err(str(e))

        if u.path.startswith("/api/settings/providers/"):
            provider_id = urllib.parse.unquote(u.path[len("/api/settings/providers/"):]).strip("/")
            try:
                AIProviderManager().remove_provider(provider_id)
                return self._json({"ok": True})
            except ValueError as e:
                return self._err(str(e))

        return self._err("Không tìm thấy", 404)

    def _resolve_target(self, data):
        """provider/model/keys/cfg chung cho translate + merge. Lỗi -> gửi _err + None."""
        mgr = AIProviderManager()
        try:
            provider = mgr.get_by_id(data["provider_id"]) if data.get("provider_id") else mgr.get_active()
        except ValueError as e:
            self._err(str(e))
            return None
        model = data.get("model") or provider.get("default_model", "")
        if not model:
            self._err(f"Provider '{provider['id']}' chưa chọn model. Mở Cấu Hình để chọn.", 400)
            return None
        cfg = AppConfig().get_config()
        keys = mgr.get_keys(provider)
        if not keys:
            self._err(f"Chưa có API Key cho provider '{provider['id']}'. Nhập ở trang Cấu Hình.", 400)
            return None
        return provider, model, keys, cfg

    # ---- SSE translate ----
    def _handle_translate_sse(self, data):
        project, fname = data.get("project", ""), data.get("file", "")
        r = self._resolve_target(data)
        if r is None:
            return
        provider, model, keys, cfg = r
        prompt_name = data.get("prompt", "default_translation.txt")
        extra = [e for e in (data.get("extra_prompts") or []) if isinstance(e, str)]

        if not _translate_lock.acquire(blocking=False):
            return self._err("Đang có 1 phiên dịch chạy. Vui lòng chờ xong.", 409)
        global _active_job
        _cancel_event.clear()

        try:
            fh = SafeFileHandler()
            text = fh.read_source(project, fname)
        except (ValueError, FileNotFoundError) as e:
            _translate_lock.release()
            return self._err(str(e), 404)

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
        _active_job = (project, fname)  # sau mọi pre-check — finally luôn dọn

        def emit(event, payload):
            line = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            self.wfile.write(line.encode("utf-8"))
            self.wfile.flush()

        try:
            client = build_client(provider, model, keys, cfg["timeout_seconds"])
            prompts = _build_prompts(project, chunks, base_tpl, extras)
            outs = asyncio.run(_run_chunks(client, prompts, [[fname]] * len(prompts),
                                           cfg.get("api_delay_seconds", 2.0), len(keys), emit,
                                           cancel=_cancel_event))
            _upsert_file(project, fname, len(text), len(chunks), "translating")
            log_run(provider["id"], model, "ok", file_id=_file_id(project, fname))
            emit("done", {"chars": sum(len(o) for o in outs)})
        except TranslateCancelled as e:
            log_run(provider["id"], model, "cancelled", str(e), file_id=_file_id(project, fname))
            emit("error", {"error": str(e), "cancelled": True})
        except (ConnectionError, TimeoutError, RuntimeError, ValueError) as e:
            log_run(provider["id"], model, "error", str(e), file_id=_file_id(project, fname))
            emit("error", {"error": str(e)})
        finally:
            _active_job = None
            _translate_lock.release()

    # ---- SSE merge: gộp nhiều file -> chia chunk -> dịch -> ghép ----
    def _handle_merge_sse(self, data):
        project = data.get("project", "")
        files = [f for f in (data.get("files") or []) if isinstance(f, str) and f.strip()]
        if not files:
            return self._err("Chọn ít nhất 1 file để gộp dịch")
        r = self._resolve_target(data)
        if r is None:
            return
        provider, model, keys, cfg = r
        prompt_name = data.get("prompt", "default_translation.txt")
        extra = [e for e in (data.get("extra_prompts") or []) if isinstance(e, str)]

        if not _translate_lock.acquire(blocking=False):
            return self._err("Đang có 1 phiên dịch chạy. Vui lòng chờ xong.", 409)
        global _active_job
        _cancel_event.clear()

        fh = SafeFileHandler()
        parts = []
        for f in files:
            try:
                parts.append((f, fh.read_source(project, f)))
            except (ValueError, FileNotFoundError) as e:
                _translate_lock.release()
                return self._err(str(e), 404)

        pieces, segs, pos = [], [], 0
        for idx, (f, c) in enumerate(parts):
            head = f"===== FILE: {f} =====\n\n"
            if idx:
                pieces.append("\n\n")
                pos += 2
            segs.append((f, pos, pos + len(head) + len(c)))
            pieces.append(head + c)
            pos += len(head) + len(c)
        joined = "".join(pieces)

        chunks = split_text(joined, max_chars=cfg["max_chunk_chars"])
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
        _active_job = (project, files[0])

        def emit(event, payload):
            line = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            self.wfile.write(line.encode("utf-8"))
            self.wfile.flush()

        try:
            client = build_client(provider, model, keys, cfg["timeout_seconds"])
            prompts = _build_prompts(project, chunks, base_tpl, extras)
            seg_names = _attribute(chunks, joined, segs)
            outs = asyncio.run(_run_chunks(client, prompts, seg_names,
                                           cfg.get("api_delay_seconds", 2.0), len(keys), emit,
                                           cancel=_cancel_event))
            parts_out = _split_output(outs, seg_names, files)
            saved = []
            for f in files:
                fh.save_output(project, f, parts_out.get(f, ""))
                _upsert_file(project, f, len(parts_out.get(f, "")), 0, "done")
                saved.append({"file": f, "chars": len(parts_out.get(f, ""))})
            log_run(provider["id"], model, "ok")
            emit("done", {"chars": sum(len(o) for o in outs), "chunks": len(outs), "files": saved})
        except TranslateCancelled as e:
            log_run(provider["id"], model, "cancelled", str(e))
            emit("error", {"error": str(e), "cancelled": True})
        except (ConnectionError, TimeoutError, RuntimeError, ValueError) as e:
            log_run(provider["id"], model, "error", str(e))
            emit("error", {"error": str(e)})
        finally:
            _active_job = None
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
