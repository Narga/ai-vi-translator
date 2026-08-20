# services/checkpoint_service.py - v5.0.0
# Tác giả: Narga
# Chức năng: Quản lý checkpoint bằng SQLite để resume dịch thuật khi bị gián đoạn

"""
Checkpoint Service - SQLite-based checkpoint management.

Tính năng:
- ACID transactions → an toàn khi crash
- Auto-save checkpoint sau mỗi chunk (chỉ UPDATE 1 row)
- Resume từ chunk cuối cùng thành công
- Hỗ trợ nhiều file, mỗi file 1 database riêng
- Query nhanh tiến độ mà không load toàn bộ text

Sử dụng:
    from services.checkpoint_service import CheckpointService

    checkpoint = CheckpointService('workspace/checkpoints')

    # Khởi tạo session cho file
    checkpoint.init_session('novel.txt', total_chunks=100)

    # Lưu checkpoint sau mỗi chunk
    checkpoint.save_chunk(
        filename='novel.txt',
        chunk_index=5,
        original_text='原文...',
        translated_text='Bản dịch...',
        api_key_used='key1'
    )

    # Resume
    info = checkpoint.get_resume_info('novel.txt')
    if info and info['can_resume']:
        print(f"Resume từ chunk {info['next_chunk_index']}")
"""

import os
import sqlite3
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, Callable
from datetime import datetime
from threading import Lock

# ============================================================
# Checkpoint identity: tách "nguồn" và "thực thi"
# Nguồn đổi  → checkpoint KHÔNG còn dùng được (phải dịch lại từ đầu).
# Thực thi đổi → checkpoint VẪN dùng được, chỉ cần ghi nhận mixed_provider.
# Dùng CHUNG cho core/executor.py và webui/routes/projects.py — không nhân bản logic.
# ============================================================
SOURCE_IDENTITY_FIELDS = (
    "project_file", "project_slug", "source_hash",
    "chunker_version", "chunk_size", "prompt_hash", "schema_version",
)
EXECUTION_IDENTITY_FIELDS = (
    "provider_kind", "provider_id", "base_url", "model", "qa_model", "credential_mode",
)


def source_identity(identity: Optional[dict]) -> Dict[str, str]:
    """Chỉ giữ các field quyết định checkpoint còn dùng được hay không."""
    identity = identity or {}
    return {k: str(identity.get(k, "")) for k in SOURCE_IDENTITY_FIELDS}


def execution_identity(identity: Optional[dict]) -> Dict[str, str]:
    identity = identity or {}
    return {k: str(identity.get(k, "")) for k in EXECUTION_IDENTITY_FIELDS}


def same_source_identity(saved: Optional[dict], current: Optional[dict]) -> bool:
    return source_identity(saved) == source_identity(current)


def execution_drift(saved: Optional[dict], current: Optional[dict]) -> List[str]:
    """Danh sách field thực thi đã đổi (sorted). Rỗng = không đổi."""
    a, b = execution_identity(saved), execution_identity(current)
    return sorted(k for k in EXECUTION_IDENTITY_FIELDS if a[k] != b[k])


def _is_hex12(value: str) -> bool:
    return len(value) == 12 and all(c in "0123456789abcdef" for c in value)


class CheckpointService:
    """
    Service quản lý checkpoint cho quá trình dịch thuật.
    Sử dụng SQLite cho ACID transactions và query hiệu quả.
    """

    def __init__(self, checkpoint_dir: str = "workspace/checkpoints"):
        """
        Khởi tạo CheckpointService.

        Args:
            checkpoint_dir: Thư mục lưu checkpoint databases
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)
        self._connections: Dict[str, sqlite3.Connection] = {}

        self._logger.info(f"📍 CheckpointService initialized (SQLite): {self.checkpoint_dir}")

    @staticmethod
    def _is_valid_sqlite_file(path: Path) -> bool:
        """Kiểm tra file tồn tại và không rỗng."""
        try:
            return path.is_file() and path.stat().st_size > 0
        except OSError:
            return False

    @staticmethod
    def _has_table(conn: sqlite3.Connection, table_name: str) -> bool:
        """Kiểm tra table có tồn tại trong sqlite connection hay không."""
        try:
            row = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            ).fetchone()
            return row is not None
        except Exception:
            return False

    def _get_db_path(self, filename: str) -> Path:
        """Tạo đường dẫn database từ tên file."""
        safe_name = hashlib.md5(filename.encode()).hexdigest()[:12]
        return self.checkpoint_dir / f"{safe_name}.db"

    def _get_connection(self, filename: str) -> sqlite3.Connection:
        """Lấy hoặc tạo connection cho file."""
        db_path = str(self._get_db_path(filename))

        if db_path not in self._connections:
            conn = sqlite3.connect(db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._init_schema(conn, filename)
            self._connections[db_path] = conn

        return self._connections[db_path]

    def _init_schema(self, conn: sqlite3.Connection, filename: str):
        """Khởi tạo schema cho database."""
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chunk_index INTEGER NOT NULL UNIQUE,
                original_text TEXT NOT NULL,
                translated_text TEXT,
                status TEXT DEFAULT 'pending',
                api_key_used TEXT,
                tokens_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(status);
            CREATE INDEX IF NOT EXISTS idx_chunks_index ON chunks(chunk_index);
        """)

        # Lưu metadata cơ bản
        conn.execute(
            "INSERT OR IGNORE INTO metadata (key, value) VALUES (?, ?)",
            ("filename", filename)
        )
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("version", "5.0.0")
        )
        conn.commit()

    def init_session(self, filename: str, total_chunks: int,
                     chunks_text: Optional[List[str]] = None,
                     identity: Optional[Dict[str, str]] = None,
                     reset: bool = False):
        """
        Khởi tạo session dịch mới: tạo DB và insert tất cả chunks ở trạng thái pending.

        Args:
            filename: Tên file đang dịch
            total_chunks: Tổng số chunks
            chunks_text: Danh sách text gốc của từng chunk (optional)
            identity: Checkpoint identity để validate khi resume
        """
        with self._lock:
            conn = self._get_connection(filename)

            if reset:
                conn.execute("DELETE FROM chunks")
                conn.execute("DELETE FROM metadata WHERE key LIKE 'ident_%'")

            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("total_chunks", str(total_chunks))
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("started_at", datetime.now().isoformat())
            )
            
            if identity:
                for k, v in identity.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                        (f"ident_{k}", str(v))
                    )

            if chunks_text:
                for i, text in enumerate(chunks_text):
                    conn.execute(
                        """INSERT OR IGNORE INTO chunks (chunk_index, original_text, status)
                           VALUES (?, ?, 'pending')""",
                        (i, text)
                    )

            conn.commit()
            self._logger.info(
                f"📍 Session initialized: {filename} - {total_chunks} chunks"
            )

    def save_chunk(self, filename: str, chunk_index: int,
                   original_text: str, translated_text: str,
                   api_key_used: str = "", tokens_used: int = 0,
                   status: str = 'done',
                   lease_epoch: Optional[int] = None,
                   lease_token: Optional[str] = None,
                   lease_validator: Optional[Callable[[], bool]] = None) -> bool:
        """
        Lưu kết quả dịch cho một chunk với atomic lease fencing CAS & durable lease check.
        - Kiểm tra lease_validator (durable lease check từ tasks.db) nếu có.
        - Kiểm tra checkpoint metadata lease_epoch / lease_token.
        Trả về True nếu lưu thành công, False nếu bị reject bởi fencing CAS.
        """
        with self._lock:
            if lease_validator is not None:
                if not lease_validator():
                    self._logger.warning(
                        f"🚨 [CHECKPOINT_FENCING_REJECT] Reject chunk {chunk_index} vì durable lease check trong tasks.db thất bại!"
                    )
                    return False

            conn = self._get_connection(filename)

            if lease_epoch is not None:
                if not lease_token:
                    self._logger.warning(
                        f"🚨 [CHECKPOINT_FENCING_REJECT] Reject chunk {chunk_index} vì có lease_epoch ({lease_epoch}) nhưng thiếu lease_token!"
                    )
                    return False

                row_epoch = conn.execute("SELECT value FROM metadata WHERE key = 'lease_epoch'").fetchone()
                row_token = conn.execute("SELECT value FROM metadata WHERE key = 'lease_token'").fetchone()
                current_epoch = None
                current_token = None
                if row_epoch and row_epoch[0]:
                    try:
                        current_epoch = int(row_epoch[0])
                    except ValueError:
                        pass
                if row_token and row_token[0]:
                    current_token = str(row_token[0])

                if current_epoch is not None:
                    if lease_epoch < current_epoch:
                        self._logger.warning(
                            f"🚨 [CHECKPOINT_FENCING_REJECT] Reject chunk {chunk_index} vì lease_epoch cũ: {lease_epoch} < {current_epoch}"
                        )
                        return False
                    elif lease_epoch == current_epoch:
                        if not current_token or not lease_token or lease_token != current_token:
                            self._logger.warning(
                                f"🚨 [CHECKPOINT_FENCING_REJECT] Reject chunk {chunk_index} vì metadata token thiếu/hỏng hoặc không khớp tại epoch {lease_epoch}: '{lease_token}' vs '{current_token}'"
                            )
                            return False

                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES ('lease_epoch', ?)",
                    (str(lease_epoch),)
                )
                if lease_token:
                    conn.execute(
                        "INSERT OR REPLACE INTO metadata (key, value) VALUES ('lease_token', ?)",
                        (str(lease_token),)
                    )

            conn.execute(
                """INSERT OR REPLACE INTO chunks
                   (chunk_index, original_text, translated_text, status,
                    api_key_used, tokens_used, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (chunk_index, original_text, translated_text,
                 status, api_key_used, tokens_used, datetime.now().isoformat())
            )
            conn.commit()

            self._logger.debug(
                f"💾 Saved chunk {chunk_index}: {filename} ({status})"
            )
            return True

    def clone_namespace(self, source_filename: str, target_filename: str) -> bool:
        """
        Copy toàn bộ checkpoint từ source DB sang target DB (tạo mới).
        Dùng cho recovery: source checkpoint giữ nguyên, target là namespace mới.

        Args:
            source_filename: Tên file checkpoint gốc
            target_filename: Tên file checkpoint mới

        Returns:
            True nếu thành công
        """
        source_path = self._get_db_path(source_filename)
        target_path = self._get_db_path(target_filename)

        if not source_path.exists():
            self._logger.error(f"❌ Source checkpoint không tồn tại: {source_path}")
            return False

        if target_path.exists():
            self._logger.error(f"❌ Target checkpoint đã tồn tại: {target_path}")
            return False

        try:
            src_conn = sqlite3.connect(str(source_path))
            src_conn.row_factory = sqlite3.Row
            tgt_conn = sqlite3.connect(str(target_path))
            tgt_conn.execute("PRAGMA journal_mode=WAL")
            tgt_conn.execute("PRAGMA synchronous=NORMAL")

            with tgt_conn:
                src_conn.backup(tgt_conn)

            source_meta = src_conn.execute(
                "SELECT value FROM metadata WHERE key = 'filename'"
            ).fetchone()
            source_filename = source_meta[0] if source_meta else source_filename

            tgt_conn.execute(
                "UPDATE metadata SET value = ? WHERE key = 'filename'",
                (target_filename,)
            )
            tgt_conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("source_filename", source_filename),
            )
            tgt_conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("checkpoint_id", target_filename),
            )
            # Reset lease metadata để task recovery mới có thể acquire và ghi với token mới
            tgt_conn.execute(
                "DELETE FROM metadata WHERE key IN ('lease_token', 'lease_epoch')"
            )

            tgt_conn.commit()
            tgt_conn.close()
            src_conn.close()

            self._logger.info(
                f"📋 Cloned checkpoint: {source_filename} → {target_filename}"
            )
            return True

        except Exception as e:
            self._logger.error(f"❌ Lỗi clone namespace: {e}")
            if target_path.exists():
                target_path.unlink()
            return False

    def assemble_partial(
        self,
        filename: str,
        marker: str = (
            "[CHUNK {idx} CHƯA DỊCH | nguồn: ký tự {char_start}-{char_end} "
            "(end không gồm), dòng {line_start}-{line_end} | xem manifest để lấy nội dung]"
        ),
    ) -> Optional[str]:
        """
        Assemble partial file từ checkpoint hiện tại.
        Chunk thiếu được thay bằng marker.

        Args:
            filename: Tên file checkpoint
            marker: Template marker cho chunk thiếu (dùng {idx} làm placeholder)

        Returns:
            Nội dung partial đã assemble, hoặc None nếu lỗi
        """
        db_path = self._get_db_path(filename)

        if not self._is_valid_sqlite_file(db_path):
            return None

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            if not self._has_table(conn, "metadata") or not self._has_table(conn, "chunks"):
                conn.close()
                return None

            meta = {}
            for row in conn.execute("SELECT key, value FROM metadata"):
                meta[row["key"]] = row["value"]

            total = int(meta.get("total_chunks", 0))
            if total == 0:
                return None

            chunks = {}
            for row in conn.execute(
                """
                SELECT chunk_index, original_text, translated_text, status
                FROM chunks
                ORDER BY chunk_index
                """
            ):
                chunks[row["chunk_index"]] = {
                    "original_text": row["original_text"] or "",
                    "text": row["translated_text"],
                    "status": row["status"],
                }

            conn.close()

            parts = []
            missing = []
            source_cursor = 0
            source_line = 1
            for i in range(total):
                if i in chunks and chunks[i]["status"] == "done" and chunks[i]["text"]:
                    parts.append(chunks[i]["text"])
                else:
                    original_text = chunks.get(i, {}).get("original_text", "")
                    char_start = source_cursor
                    char_end = char_start + len(original_text)
                    line_start = source_line
                    line_end = line_start + original_text.count("\n")
                    parts.append(marker.format(
                        idx=i,
                        char_start=char_start,
                        char_end=char_end,
                        line_start=line_start,
                        line_end=line_end,
                    ))
                    missing.append(i)

                if i in chunks:
                    original_text = chunks[i]["original_text"]
                    source_cursor += len(original_text) + 2
                    source_line += original_text.count("\n") + 1

            if missing:
                self._logger.warning(
                    f"⚠️ Partial file có {len(missing)} chunk thiếu: {missing}"
                )

            return "\n\n".join(parts)

        except Exception as e:
            self._logger.error(f"❌ Lỗi assemble partial: {e}")
            return None

    def write_partial_file(
        self,
        checkpoint_filename: str,
        output_dir: Path,
        marker: str = (
            "[CHUNK {idx} CHƯA DỊCH | nguồn: ký tự {char_start}-{char_end} "
            "(end không gồm), dòng {line_start}-{line_end} | xem manifest để lấy nội dung]"
        ),
    ) -> Optional[Path]:
        """
        Assemble và ghi partial file với manifest sidecar.

        Args:
            checkpoint_filename: Tên file checkpoint
            output_dir: Thư mục output (ví dụ: translated/.recovery/)
            marker: Marker cho chunk thiếu

        Returns:
            Path đến file partial, hoặc None nếu lỗi
        """
        import json

        content = self.assemble_partial(checkpoint_filename, marker)
        if content is None:
            return None

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        db_path = self._get_db_path(checkpoint_filename)
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        meta = {}
        for row in conn.execute("SELECT key, value FROM metadata"):
            meta[row["key"]] = row["value"]

        chunk_rows = conn.execute(
            """
            SELECT chunk_index, original_text, translated_text, status
            FROM chunks
            ORDER BY chunk_index
            """
        ).fetchall()

        done_count_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM chunks WHERE status='done'"
        ).fetchone()
        done_count = done_count_row["cnt"] if done_count_row else 0
        conn.close()

        source_filename = meta.get("source_filename", meta.get("filename", checkpoint_filename))

        partial_name = f"{source_filename}.{checkpoint_filename}.partial.md"
        partial_path = output_dir / partial_name

        tmp_path = partial_path.with_suffix(".tmp")
        tmp_path.write_text(content, encoding="utf-8")
        tmp_path.replace(partial_path)

        # The partial text alone cannot tell a user what to resend manually.
        # Keep an explicit source map in the sidecar manifest. Offsets refer to
        # the original source assembled with the same ``\n\n`` separator used
        # by the translator, and line numbers are 1-based and inclusive.
        chunks_manifest = []
        source_cursor = 0
        for row in chunk_rows:
            original_text = row["original_text"] or ""
            source_start = source_cursor
            source_end = source_start + len(original_text)
            chunks_manifest.append({
                "index": row["chunk_index"],
                "status": row["status"],
                "source_char_start": source_start,
                "source_char_end": source_end,
                "source_line_start": None,
                "source_line_end": None,
                "source_char_count": len(original_text),
                "source_text": original_text if row["status"] != "done" else None,
            })
            source_cursor = source_end + 2

        source_line = 1
        for chunk_info, row in zip(chunks_manifest, chunk_rows):
            original_text = row["original_text"] or ""
            chunk_info["source_line_start"] = source_line
            chunk_info["source_line_end"] = source_line + original_text.count("\n")
            source_line = chunk_info["source_line_end"] + 1

        manifest = {
            "source_file": source_filename,
            "checkpoint_file": checkpoint_filename,
            "total_chunks": int(meta.get("total_chunks", 0)),
            "done_chunks": done_count,
            "is_complete": False,
            "marker_template": marker,
            "created_at": datetime.now().isoformat(),
            "position_format": {
                "character_offsets": "0-based, end-exclusive",
                "line_numbers": "1-based, inclusive",
                "separator_between_chunks": "\\n\\n",
            },
            "chunks": chunks_manifest,
        }
        manifest_path = partial_path.with_suffix(".manifest.json")
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        self._logger.info(f"📄 Partial file written: {partial_path}")
        return partial_path

    def save(self, filename: str, chunk_index: int, total_chunks: int,
             translated_chunks: Dict[int, str],
             api_key_usage: Dict[str, int],
             metadata: Optional[Dict[str, Any]] = None) -> Path:
        """
        Lưu checkpoint (API tương thích v4.0).

        Args:
            filename: Tên file đang dịch
            chunk_index: Index của chunk hiện tại
            total_chunks: Tổng số chunks
            translated_chunks: Dict các chunks đã dịch {index: text}
            api_key_usage: Thống kê sử dụng API key
            metadata: Metadata bổ sung

        Returns:
            Path: Đường dẫn database
        """
        with self._lock:
            conn = self._get_connection(filename)

            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("total_chunks", str(total_chunks))
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("last_chunk_index", str(chunk_index))
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("updated_at", datetime.now().isoformat())
            )

            if api_key_usage:
                import json
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    ("api_key_usage", json.dumps(api_key_usage))
                )

            if metadata:
                import json
                conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                    ("extra_metadata", json.dumps(metadata))
                )

            # Upsert translated chunks
            for idx, text in translated_chunks.items():
                conn.execute(
                    """INSERT OR REPLACE INTO chunks
                       (chunk_index, original_text, translated_text, status, updated_at)
                       VALUES (?, ?, ?, 'done', ?)""",
                    (int(idx), "", text, datetime.now().isoformat())
                )

            conn.commit()
            db_path = self._get_db_path(filename)
            self._logger.debug(
                f"💾 Saved checkpoint: {filename} - chunk {chunk_index}/{total_chunks}"
            )
            return db_path

    def load(self, checkpoint_path: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint từ database file.

        Args:
            checkpoint_path: Đường dẫn database (.db)

        Returns:
            Dict chứa checkpoint data hoặc None nếu lỗi
        """
        path = Path(checkpoint_path)

        if not self._is_valid_sqlite_file(path):
            self._logger.warning(f"⚠️ Checkpoint không tồn tại hoặc rỗng: {checkpoint_path}")
            return None

        try:
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row

            if not self._has_table(conn, "metadata") or not self._has_table(conn, "chunks"):
                conn.close()
                return None

            # Load metadata
            meta = {}
            for row in conn.execute("SELECT key, value FROM metadata"):
                meta[row["key"]] = row["value"]

            # Load translated chunks
            translated_chunks = {}
            for row in conn.execute(
                "SELECT chunk_index, translated_text FROM chunks WHERE status='done' ORDER BY chunk_index"
            ):
                translated_chunks[row["chunk_index"]] = row["translated_text"]

            total_chunks = int(meta.get("total_chunks", 0))
            last_idx = int(meta.get("last_chunk_index", len(translated_chunks) - 1))

            data = {
                "version": meta.get("version", "5.0.0"),
                "filename": meta.get("filename", ""),
                "chunk_index": last_idx,
                "total_chunks": total_chunks,
                "progress_pct": round(len(translated_chunks) / total_chunks * 100, 1) if total_chunks > 0 else 0,
                "translated_chunks": translated_chunks,
                "api_key_usage": {},
                "timestamp": meta.get("updated_at", ""),
                "metadata": {},
            }

            # Parse JSON metadata
            import json
            if "api_key_usage" in meta:
                try:
                    data["api_key_usage"] = json.loads(meta["api_key_usage"])
                except Exception:
                    pass
            if "extra_metadata" in meta:
                try:
                    data["metadata"] = json.loads(meta["extra_metadata"])
                except Exception:
                    pass

            conn.close()

            self._logger.info(
                f"📂 Loaded checkpoint: {data['filename']} - "
                f"{len(translated_chunks)}/{total_chunks} chunks done "
                f"({data['progress_pct']}%)"
            )

            return data

        except Exception as e:
            self._logger.error(f"❌ Lỗi đọc checkpoint: {e}")
            return None

    def find_latest(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Tìm và load checkpoint mới nhất cho file.

        Args:
            filename: Tên file

        Returns:
            Dict chứa checkpoint data hoặc None
        """
        db_path = self._get_db_path(filename)

        if db_path.exists():
            return self.load(str(db_path))

        return None

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        Liệt kê tất cả checkpoints.

        Returns:
            List các checkpoint info
        """
        checkpoints = []

        for db_file in sorted(
            self.checkpoint_dir.glob("*.db"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            if not self._is_valid_sqlite_file(db_file):
                continue
            try:
                conn = sqlite3.connect(str(db_file))
                conn.row_factory = sqlite3.Row
                if not self._has_table(conn, "metadata") or not self._has_table(conn, "chunks"):
                    conn.close()
                    continue

                meta = {}
                for row in conn.execute("SELECT key, value FROM metadata"):
                    meta[row["key"]] = row["value"]

                done_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM chunks WHERE status='done'"
                ).fetchone()["cnt"]

                total = int(meta.get("total_chunks", 0))

                checkpoints.append({
                    "filename": meta.get("filename", "unknown"),
                    "path": str(db_file),
                    "chunk_index": done_count - 1 if done_count > 0 else 0,
                    "total_chunks": total,
                    "progress_pct": round(done_count / total * 100, 1) if total > 0 else 0,
                    "timestamp": meta.get("updated_at", ""),
                })

                conn.close()
            except Exception:
                continue

        return checkpoints

    def delete(self, checkpoint_path: str) -> bool:
        """
        Xóa checkpoint.

        Args:
            checkpoint_path: Đường dẫn database

        Returns:
            True nếu thành công
        """
        path = Path(checkpoint_path)

        # Close connection if open
        path_str = str(path)
        if path_str in self._connections:
            try:
                self._connections[path_str].close()
            except Exception:
                pass
            del self._connections[path_str]

        if path.exists():
            path.unlink()
            # Also remove WAL and SHM files
            for suffix in ["-wal", "-shm"]:
                wal = Path(str(path) + suffix)
                if wal.exists():
                    wal.unlink()
            self._logger.info(f"🗑️ Deleted checkpoint: {path.name}")
            return True

        return False

    def cleanup(self, filename: str) -> bool:
        """
        Dọn dẹp checkpoint cho một file sau khi dịch thành công.

        Args:
            filename: Tên file gốc.

        Returns:
            True nếu xóa thành công, False nếu không tìm thấy.
        """
        db_path = self._get_db_path(filename)
        return self.delete(str(db_path))

    def delete_by_key(self, checkpoint_key: str) -> bool:
        """
        Xóa checkpoint dựa trên checkpoint key (logical hoặc physical).
        Dùng cho rollback preparation hoặc dọn dẹp checkpoint.
        """
        if not checkpoint_key:
            return False
        resolved = self.resolve_checkpoint_key(checkpoint_key)
        if resolved and resolved.get("path"):
            return self.delete(resolved["path"])
        db_path = self._get_db_path(checkpoint_key)
        return self.delete(str(db_path))

    def get_resume_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin resume nhanh (không load toàn bộ text).

        Args:
            filename: Tên file

        Returns:
            Dict với thông tin resume hoặc None
        """
        db_path = self._get_db_path(filename)

        if not self._is_valid_sqlite_file(db_path):
            return None

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            if not self._has_table(conn, "metadata") or not self._has_table(conn, "chunks"):
                conn.close()
                return None

            meta = {}
            for row in conn.execute("SELECT key, value FROM metadata"):
                meta[row["key"]] = row["value"]

            done_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM chunks WHERE status='done'"
            ).fetchone()["cnt"]

            total = int(meta.get("total_chunks", 0))

            pending_row = conn.execute(
                "SELECT chunk_index FROM chunks WHERE status != 'done' ORDER BY chunk_index LIMIT 1"
            ).fetchone()
            next_chunk_index = int(pending_row["chunk_index"]) if pending_row else total

            identity = {}
            for k, v in meta.items():
                if k.startswith("ident_"):
                    identity[k.replace("ident_", "", 1)] = v

            conn.close()

            return {
                "can_resume": done_count < total,
                "filename": meta.get("filename") or filename,   # ← THÊM (B2)
                "next_chunk_index": next_chunk_index,
                "chunk_index": next_chunk_index - 1 if next_chunk_index > 0 else 0,
                "total_chunks": total,
                "progress_pct": round(done_count / total * 100, 1) if total > 0 else 0,
                "translated_count": done_count,
                "timestamp": meta.get("updated_at", ""),
                "checkpoint_path": str(db_path),
                "identity": identity,
            }

        except Exception as e:
            self._logger.error(f"❌ Lỗi lấy resume info: {e}")
            return None

    def get_resume_info_from_path(self, checkpoint_path: str) -> Optional[Dict[str, Any]]:
        """Read resume metadata for an already-discovered SQLite path.

        Startup scans enumerate physical DB files, so they must not pass the
        MD5 stem back through ``get_resume_info(filename)`` (which hashes its
        argument as a logical filename).
        """
        path = Path(checkpoint_path)
        if not self._is_valid_sqlite_file(path):
            return None
        try:
            conn = sqlite3.connect(str(path))
            if not self._has_table(conn, "metadata"):
                conn.close()
                return None
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'filename'"
            ).fetchone()
            conn.close()
            if not row or not row[0]:
                return None
            return self.get_resume_info(row[0])
        except Exception as e:
            self._logger.warning(f"⚠️ Lỗi đọc resume theo path '{checkpoint_path}': {e}")
            return None

    @staticmethod
    def _assert_safe_key(key: str) -> str:
        """Chặn path traversal: key đến từ URL `<path:checkpoint_key>` và từ DB.

        Chỉ cho phép MỘT thành phần tên file. Không '/', '\\', '..', không absolute.
        """
        key = (key or "").strip()
        if not key:
            raise ValueError("checkpoint_key rỗng")
        if key in (".", "..") or "/" in key or "\\" in key or "\x00" in key:
            raise ValueError(f"checkpoint_key không hợp lệ: {key!r}")
        if Path(key).name != key:
            raise ValueError(f"checkpoint_key không hợp lệ: {key!r}")
        return key

    def physical_checkpoint_key(self, key: str) -> Optional[str]:
        """Chuẩn hóa key về TÊN FILE VẬT LÝ, KHÔNG cần đọc đĩa.

        - "f1ed388c8e76.db"  → chính nó          (đã vật lý, không hash lại)
        - "f1ed388c8e76"     → + ".db"           (MD5 stem)
        - "book.txt", "f1ed388c8e76.db.9a1b2c3d" → md5(...)[:12] + ".db"

        Nhận diện "đã vật lý" bằng ĐÚNG khuôn `<12 hex>.db` — không dùng
        `endswith(".db")` để một file nguồn tên "notes.db" không bị hiểu sai.
        Dùng cho SO SÁNH key (task row lưu tên logic, payload 409 lưu tên vật lý — B4/B9).
        """
        try:
            key = self._assert_safe_key(key)
        except ValueError:
            return None
        if key.endswith(".db") and _is_hex12(key[:-3]):
            return key
        if _is_hex12(key):
            return key + ".db"
        return self._get_db_path(key).name

    def same_checkpoint_key(self, a: Optional[str], b: Optional[str]) -> bool:
        """True nếu 2 key (logic hoặc vật lý, lẫn lộn tùy ý) chỉ về cùng 1 checkpoint."""
        if not a or not b:
            return False
        if a == b:
            return True
        pa, pb = self.physical_checkpoint_key(a), self.physical_checkpoint_key(b)
        return bool(pa) and pa == pb

    def _read_logical_filename(self, db_path: Path) -> Optional[str]:
        """Đọc metadata['filename'] — tên logic thật của checkpoint."""
        if not self._is_valid_sqlite_file(db_path):
            return None
        try:
            conn = sqlite3.connect(str(db_path))
            if not self._has_table(conn, "metadata"):
                conn.close()
                return None
            row = conn.execute(
                "SELECT value FROM metadata WHERE key = 'filename'"
            ).fetchone()
            conn.close()
            return row[0] if row and row[0] else None
        except Exception as e:
            self._logger.warning(f"⚠️ Lỗi đọc metadata filename '{db_path}': {e}")
            return None

    def resolve_checkpoint_key(self, key: Optional[str]) -> Optional[Dict[str, Any]]:
        """Resolve một checkpoint key bất kỳ về MỘT checkpoint vật lý duy nhất.

        Chấp nhận: logical filename ("book.txt"), tên file .db ("f1ed388c8e76.db"),
        MD5 stem ("f1ed388c8e76"), hoặc namespace recovery ("f1ed…db.9a1b2c3d").

        Trả về dict {checkpoint_key, filename, path, resume_info} hoặc None.
        `filename` là tên LOGIC đọc từ metadata của chính file đó — đây là giá trị
        duy nhất được phép truyền vào get_done_pending_indices / write_partial_file /
        assemble_partial / get_translated_chunks (các hàm đó tự hash).
        """
        if not key:
            return None
        try:
            key = self._assert_safe_key(key)
        except ValueError as e:
            self._logger.warning(f"⚠️ resolve_checkpoint_key bị từ chối: {e}")
            return None

        path = None
        # 1) key trỏ trực tiếp tới file trong checkpoint_dir (KHÔNG hash lại)
        for cand in (key, f"{key}.db"):
            p = self.checkpoint_dir / cand
            if p.is_file() and p.stat().st_size > 0:
                path = p
                break
        # 2) coi key là logical filename
        if path is None:
            lp = self._get_db_path(key)
            if lp.is_file() and lp.stat().st_size > 0:
                path = lp
        if path is None:
            return None

        logical = self._read_logical_filename(path)
        info = self.get_resume_info(logical) if logical else None
        # Bất biến: metadata phải trỏ về đúng file vừa mở. Nếu lệch (checkpoint bị copy
        # tay/rename) thì tin PATH, không tin metadata, và không hash lại.
        if logical and self._get_db_path(logical).name != path.name:
            self._logger.warning(
                f"⚠️ Checkpoint {path.name} có metadata filename={logical!r} không khớp hash; dùng path."
            )
            info = self.get_resume_info_from_path(str(path))

        return {
            "checkpoint_key": path.name,   # LUÔN là tên vật lý
            "filename": logical,           # có thể None nếu metadata hỏng
            "path": str(path),
            "resume_info": info,
        }

    def get_done_pending_indices(self, filename: str, db_path_override: Optional[str] = None) -> Optional[Dict[str, List[int]]]:
        """
        Lấy danh sách index done/pending/failed chính xác.
        Không dùng done_count làm proxy — trả về list index thực tế.
        """
        if db_path_override:
            db_path = Path(db_path_override)
        else:
            db_path = self._get_db_path(filename)

        if not self._is_valid_sqlite_file(db_path):
            return None

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            if not self._has_table(conn, "chunks"):
                conn.close()
                return None

            done = [
                row["chunk_index"]
                for row in conn.execute(
                    "SELECT chunk_index FROM chunks WHERE status='done' ORDER BY chunk_index"
                )
            ]
            pending = [
                row["chunk_index"]
                for row in conn.execute(
                    "SELECT chunk_index FROM chunks WHERE status IN ('pending','failed') ORDER BY chunk_index"
                )
            ]
            failed = [
                row["chunk_index"]
                for row in conn.execute(
                    "SELECT chunk_index FROM chunks WHERE status='failed' ORDER BY chunk_index"
                )
            ]
            meta_row = conn.execute(
                "SELECT value FROM metadata WHERE key='total_chunks'"
            ).fetchone()
            total_chunks = int(meta_row["value"]) if meta_row else (len(done) + len(pending))

            conn.close()
            return {
                "total_chunks": total_chunks,
                "done_indices": done,
                "pending_indices": pending,
                "failed_indices": failed,
            }
        except Exception as e:
            self._logger.error(f"❌ Lỗi lấy indices: {e}")
            return None

    def clone_checkpoint(self, source_filename: str, target_filename: str) -> bool:
        """Alias cho clone_namespace (P1 Phase 8)."""
        return self.clone_namespace(source_filename, target_filename)

    def get_translated_chunks(self, filename: str) -> Dict[int, str]:
        """
        Lấy tất cả chunks đã dịch (để resume).

        Args:
            filename: Tên file

        Returns:
            Dict {chunk_index: translated_text}
        """
        db_path = self._get_db_path(filename)

        if not db_path.exists():
            return {}

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            result = {}
            for row in conn.execute(
                "SELECT chunk_index, translated_text FROM chunks WHERE status='done' ORDER BY chunk_index"
            ):
                result[row["chunk_index"]] = row["translated_text"]

            conn.close()
            return result

        except Exception as e:
            self._logger.error(f"❌ Lỗi đọc translated chunks: {e}")
            return {}



    def verify_checkpoint_completeness(self, checkpoint_key: str) -> Tuple[bool, dict]:
        """
        Verification Gate cho Recovery / Translation (Phase 8):
        - Kiểm tra tính toàn vẹn 100% của SQLite checkpoint: done_indices == set(range(total_chunks)).
        - Zero-marker check: các đoạn dịch không chứa chuỗi placeholder "[CHUNK n CHƯA DỊCH".
        - Trả về (is_valid, details_dict).
        """
        resolved = self.resolve_checkpoint_key(checkpoint_key)
        if not resolved:
            return False, {"error": "Checkpoint not found", "checkpoint_key": checkpoint_key}

        filename = resolved["filename"]
        idx_info = self.get_done_pending_indices(filename)
        if not idx_info:
            return False, {"error": "Cannot read indices", "checkpoint_key": checkpoint_key}

        total_chunks = idx_info["total_chunks"]
        done_indices = set(idx_info["done_indices"])
        pending_indices = idx_info["pending_indices"]

        expected_indices = set(range(total_chunks))
        missing_from_done = sorted(list(expected_indices - done_indices))

        is_complete = (len(missing_from_done) == 0 and len(pending_indices) == 0)

        # Sanity check marker trong text
        marker_violations = []
        if is_complete:
            translated_chunks = self.get_translated_chunks(filename)
            for idx, text in translated_chunks.items():
                if not text or not text.strip():
                    is_complete = False
                    marker_violations.append({"index": idx, "reason": "empty_translation"})
                elif f"[CHUNK {idx} CHƯA DỊCH" in text or f"[CHUNK {idx + 1} CHƯA DỊCH" in text:
                    is_complete = False
                    marker_violations.append({"index": idx, "reason": "marker_placeholder_found"})

        details = {
            "checkpoint_key": checkpoint_key,
            "filename": filename,
            "total_chunks": total_chunks,
            "done_count": len(done_indices),
            "done_indices": sorted(list(done_indices)),
            "pending_indices": pending_indices,
            "missing_indices": missing_from_done,
            "marker_violations": marker_violations,
            "is_complete": is_complete,
        }
        return is_complete, details

    def create_manifest(
        self,
        checkpoint_key: str,
        source_task_id: Optional[str] = None,
        recovery_task_id: Optional[str] = None,
        provider_id: Optional[str] = None,
        model: Optional[str] = None,
        output_text: Optional[str] = None,
    ) -> dict:
        """
        Tạo manifest chuẩn JSON contract v1.0 (Phase 8).
        """
        import hashlib
        is_complete, details = self.verify_checkpoint_completeness(checkpoint_key)

        output_hash = None
        if output_text is not None:
            output_hash = f"sha256:{hashlib.sha256(output_text.encode('utf-8')).hexdigest()}"

        manifest = {
            "manifest_version": "1.0",
            "source_task_id": source_task_id,
            "recovery_task_id": recovery_task_id,
            "checkpoint_key": checkpoint_key,
            "total_chunks": details.get("total_chunks", 0),
            "done_indices": details.get("done_indices", []),
            "pending_indices": details.get("pending_indices", []),
            "output_hash": output_hash,
            "timestamp": datetime.now().isoformat(),
            "provider_id": provider_id,
            "model": model,
            "is_complete": is_complete,
        }
        return manifest

    def atomic_write_file(
        self,
        target_path: Path,
        content: str,
        pre_replace_check: Optional[Callable[[], bool]] = None,
    ) -> Path:
        """
        Ghi file an toàn nguyên tử (atomic): ghi ra .tmp -> fsync -> kiểm tra lease guard -> replace.
        Nếu pre_replace_check trả về False (lease mất ngay trước replace), xóa tmp_path và raise RuntimeError.
        """
        import os, uuid
        target_path = Path(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_name = f".{target_path.name}.tmp.{uuid.uuid4().hex[:8]}"
        tmp_path = target_path.parent / tmp_name

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())

            if pre_replace_check is not None:
                if not pre_replace_check():
                    raise RuntimeError("Lease lost before atomic file replace")

            os.replace(tmp_path, target_path)
            return target_path
        except Exception:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
            raise

    def close(self):
        """Đóng tất cả connections."""
        for conn in self._connections.values():
            try:
                conn.close()
            except Exception:
                pass
        self._connections.clear()

    def __del__(self):
        self.close()
