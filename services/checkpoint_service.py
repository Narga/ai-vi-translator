# services/checkpoint_service.py - v4.0.0
# Tác giả: Narga
# Chức năng: Quản lý checkpoint để resume dịch thuật khi bị gián đoạn

"""
Checkpoint Service - Lưu và khôi phục tiến trình dịch thuật.

Tính năng:
- Auto-save checkpoint sau mỗi chunk
- Resume từ chunk cuối cùng thành công
- Hỗ trợ nhiều file
- Lưu trạng thái API keys

Sử dụng:
    from services.checkpoint_service import CheckpointService

    # Khởi tạo
    checkpoint = CheckpointService('workspace/checkpoints')

    # Lưu checkpoint sau mỗi chunk
    checkpoint.save(
        filename='novel.txt',
        chunk_index=5,
        total_chunks=100,
        translated_chunks={0: "...", 1: "...", 2: "..."},
        api_key_usage={'key1': 10, 'key2': 5}
    )

    # Load checkpoint để resume
    state = checkpoint.load('workspace/checkpoints/novel.txt.json')
    if state:
        print(f"Resume từ chunk {state['chunk_index']}")
"""

import json
import os
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from threading import Lock


class CheckpointService:
    """
    Service quản lý checkpoint cho quá trình dịch thuật.
    """

    def __init__(self, checkpoint_dir: str = "workspace/checkpoints"):
        """
        Khởi tạo CheckpointService.

        Args:
            checkpoint_dir: Thư mục lưu checkpoints
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._logger = logging.getLogger(__name__)

        self._logger.info(f"📍 CheckpointService initialized: {self.checkpoint_dir}")

    def _get_checkpoint_path(self, filename: str) -> Path:
        """Tạo đường dẫn checkpoint từ tên file."""
        # Tạo safe filename từ input filename
        safe_name = hashlib.md5(filename.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.checkpoint_dir / f"{safe_name}_{timestamp}.json"

    def _get_latest_checkpoint(self, filename: str) -> Optional[Path]:
        """Tìm checkpoint mới nhất cho file."""
        safe_name = hashlib.md5(filename.encode()).hexdigest()[:8]

        checkpoints = sorted(
            self.checkpoint_dir.glob(f"{safe_name}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        return checkpoints[0] if checkpoints else None

    def save(
        self,
        filename: str,
        chunk_index: int,
        total_chunks: int,
        translated_chunks: Dict[int, str],
        api_key_usage: Dict[str, int],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Path:
        """
        Lưu checkpoint.

        Args:
            filename: Tên file đang dịch
            chunk_index: Index của chunk hiện tại
            total_chunks: Tổng số chunks
            translated_chunks: Dict các chunks đã dịch {index: text}
            api_key_usage: Thống kê sử dụng API key
            metadata: Metadata bổ sung

        Returns:
            Path: Đường dẫn checkpoint đã lưu
        """
        checkpoint_data = {
            "version": "4.0.0",
            "filename": filename,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "progress_pct": round(chunk_index / total_chunks * 100, 1)
            if total_chunks > 0
            else 0,
            "translated_chunks": translated_chunks,
            "api_key_usage": api_key_usage,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        with self._lock:
            checkpoint_path = self._get_checkpoint_path(filename)

            # Save to temp first, then rename (atomic)
            temp_path = checkpoint_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)

            temp_path.replace(checkpoint_path)

            # Cleanup old checkpoints (keep last 5)
            self._cleanup_old_checkpoints(filename)

            self._logger.debug(
                f"💾 Saved checkpoint: {filename} - "
                f"chunk {chunk_index}/{total_chunks} ({checkpoint_data['progress_pct']}%)"
            )

            return checkpoint_path

    def _cleanup_old_checkpoints(self, filename: str) -> None:
        """Xóa các checkpoint cũ, giữ lại 5 version mới nhất."""
        safe_name = hashlib.md5(filename.encode()).hexdigest()[:8]

        checkpoints = sorted(
            self.checkpoint_dir.glob(f"{safe_name}_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Keep only 5 newest
        for old_checkpoint in checkpoints[5:]:
            old_checkpoint.unlink()
            self._logger.debug(f"🗑️ Removed old checkpoint: {old_checkpoint.name}")

    def load(self, checkpoint_path: str) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint từ file.

        Args:
            checkpoint_path: Đường dẫn checkpoint

        Returns:
            Dict chứa checkpoint data hoặc None nếu lỗi
        """
        path = Path(checkpoint_path)

        if not path.exists():
            self._logger.error(f"❌ Checkpoint không tồn tại: {checkpoint_path}")
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self._logger.info(
                f"📂 Loaded checkpoint: {data['filename']} - "
                f"chunk {data['chunk_index']}/{data['total_chunks']} "
                f"({data['progress_pct']}%)"
            )

            return data

        except json.JSONDecodeError as e:
            self._logger.error(f"❌ Lỗi đọc checkpoint: {e}")
            return None
        except KeyError as e:
            self._logger.error(f"❌ Checkpoint không hợp lệ: {e}")
            return None

    def find_latest(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Tìm và load checkpoint mới nhất cho file.

        Args:
            filename: Tên file

        Returns:
            Dict chứa checkpoint data hoặc None
        """
        latest_path = self._get_latest_checkpoint(filename)

        if latest_path:
            return self.load(str(latest_path))

        return None

    def list_checkpoints(self) -> List[Dict[str, Any]]:
        """
        Liệt kê tất cả checkpoints.

        Returns:
            List các checkpoint info
        """
        checkpoints = []

        for path in sorted(
            self.checkpoint_dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                checkpoints.append(
                    {
                        "filename": data.get("filename", "unknown"),
                        "path": str(path),
                        "chunk_index": data.get("chunk_index", 0),
                        "total_chunks": data.get("total_chunks", 0),
                        "progress_pct": data.get("progress_pct", 0),
                        "timestamp": data.get("timestamp", ""),
                    }
                )
            except Exception:
                continue

        return checkpoints

    def delete(self, checkpoint_path: str) -> bool:
        """
        Xóa checkpoint.

        Args:
            checkpoint_path: Đường dẫn checkpoint

        Returns:
            True nếu thành công
        """
        path = Path(checkpoint_path)

        if path.exists():
            path.unlink()
            self._logger.info(f"🗑️ Deleted checkpoint: {path.name}")
            return True

        return False

    def get_resume_info(self, filename: str) -> Optional[Dict[str, Any]]:
        """
        Lấy thông tin resume mà không load toàn bộ checkpoint.

        Args:
            filename: Tên file

        Returns:
            Dict với thông tin resume hoặc None
        """
        latest = self.find_latest(filename)

        if not latest:
            return None

        return {
            "can_resume": latest["chunk_index"] < latest["total_chunks"] - 1,
            "chunk_index": latest["chunk_index"],
            "total_chunks": latest["total_chunks"],
            "progress_pct": latest["progress_pct"],
            "translated_count": len(latest.get("translated_chunks", {})),
            "timestamp": latest.get("timestamp", ""),
            "checkpoint_path": str(self._get_latest_checkpoint(filename)),
        }
