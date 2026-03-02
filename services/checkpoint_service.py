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
from typing import Dict, Any, Optional, List
from datetime import datetime
from threading import Lock


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
                     chunks_text: Optional[List[str]] = None):
        """
        Khởi tạo session dịch mới: tạo DB và insert tất cả chunks ở trạng thái pending.

        Args:
            filename: Tên file đang dịch
            total_chunks: Tổng số chunks
            chunks_text: Danh sách text gốc của từng chunk (optional)
        """
        with self._lock:
            conn = self._get_connection(filename)

            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("total_chunks", str(total_chunks))
            )
            conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
                ("started_at", datetime.now().isoformat())
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
                   api_key_used: str = "", tokens_used: int = 0):
        """
        Lưu kết quả dịch cho một chunk.

        Args:
            filename: Tên file đang dịch
            chunk_index: Index của chunk
            original_text: Text gốc
            translated_text: Text đã dịch
            api_key_used: API key đã sử dụng
            tokens_used: Số tokens đã dùng
        """
        with self._lock:
            conn = self._get_connection(filename)

            conn.execute(
                """INSERT OR REPLACE INTO chunks
                   (chunk_index, original_text, translated_text, status,
                    api_key_used, tokens_used, updated_at)
                   VALUES (?, ?, ?, 'done', ?, ?, ?)""",
                (chunk_index, original_text, translated_text,
                 api_key_used, tokens_used, datetime.now().isoformat())
            )
            conn.commit()

            self._logger.debug(
                f"💾 Saved chunk {chunk_index}: {filename}"
            )

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

        if not path.exists():
            self._logger.error(f"❌ Checkpoint không tồn tại: {checkpoint_path}")
            return None

        try:
            conn = sqlite3.connect(str(path))
            conn.row_factory = sqlite3.Row

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
            try:
                conn = sqlite3.connect(str(db_file))
                conn.row_factory = sqlite3.Row

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

    def get_resume_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin resume nhanh (không load toàn bộ text).

        Args:
            filename: Tên file

        Returns:
            Dict với thông tin resume hoặc None
        """
        db_path = self._get_db_path(filename)

        if not db_path.exists():
            return None

        try:
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row

            meta = {}
            for row in conn.execute("SELECT key, value FROM metadata"):
                meta[row["key"]] = row["value"]

            done_count = conn.execute(
                "SELECT COUNT(*) as cnt FROM chunks WHERE status='done'"
            ).fetchone()["cnt"]

            total = int(meta.get("total_chunks", 0))

            conn.close()

            return {
                "can_resume": done_count < total,
                "next_chunk_index": done_count,
                "chunk_index": done_count - 1 if done_count > 0 else 0,
                "total_chunks": total,
                "progress_pct": round(done_count / total * 100, 1) if total > 0 else 0,
                "translated_count": done_count,
                "timestamp": meta.get("updated_at", ""),
                "checkpoint_path": str(db_path),
            }

        except Exception as e:
            self._logger.error(f"❌ Lỗi lấy resume info: {e}")
            return None

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
