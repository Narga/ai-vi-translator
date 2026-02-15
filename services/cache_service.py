# services/cache_service.py - v3.0.0
# Tác giả: Narga
# Chức năng: Quản lý cache kết quả dịch, thread-safe, lưu bằng pickle theo khóa băm MD5.
# v3.0.0: Di chuyển từ src/translators/ sang services/ cho plugin architecture.
#         Giữ nguyên logic cache với khóa gồm: model_name, temperature, prompts signature,
#         previous_chunk_context hash, và original_chunk hash để tránh reuse sai.
# v4.0.1: Thêm gzip compression để giảm disk I/O.


import os
import json
import pickle
import gzip
import hashlib
import logging
from threading import Lock
from typing import Optional, Dict, Any


class TranslationCache:
    """
    Cache file-based đơn giản để giảm chi phí API.
    - Mỗi item lưu vào một .pkl.gz đặt tên theo MD5 của key.
    - Thread-safe khi đọc/ghi.
    - Sử dụng gzip compression để giảm kích thước file.
    - Khóa thiết kế mới (v2.7.0) giúp tránh reuse sai khi cấu hình thay đổi.
    """

    COMPRESS = True  # Enable gzip compression by default

    def __init__(self, cache_dir: str, enabled: bool = True) -> None:
        self.enabled = enabled
        if not self.enabled:
            logging.info("ℹ️ Cache dịch thuật đã bị tắt.")
            return
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)
        self._lock = Lock()
        logging.info(
            f"📦 Cache dịch thuật được bật. Thư mục: '{self.cache_dir}' (gzip: {self.COMPRESS})"
        )

    def _md5(self, data: bytes) -> str:
        """Tính MD5 nhanh và ổn định cho dữ liệu nhị phân."""
        h = hashlib.md5()
        h.update(data)
        return h.hexdigest()

    def _stable_hash_text(self, text: str) -> str:
        """Hash ổn định cho chuỗi văn bản (UTF-8)."""
        return self._md5((text or "").encode("utf-8"))

    def _prompts_signature(self, prompts: Dict[str, str]) -> str:
        """
        Tạo chữ ký phiên bản ổn định cho prompts (main/retranslate/correction/consistency...).
        - Sử dụng JSON chuẩn hóa key-sorted và không escape ASCII để ổn định cross-platform.
        """
        try:
            normalized = json.dumps(
                prompts or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        except Exception:
            # Phòng hờ: nếu có object không JSON được, fallback sang str() rồi hash
            normalized = str(prompts)
        return self._stable_hash_text(normalized)

    def build_key(
        self,
        original_chunk: str,
        prompts: Dict[str, str],
        config: Dict[str, Any],
        previous_chunk_context: str,
    ) -> str:
        """
        Xây dựng khóa logic (string) chứa đầy đủ thành phần ảnh hưởng kết quả dịch:
        - model_name, temperature
        - prompts_signature (hash nội dung các prompt)
        - prev_context_hash (hash ngữ cảnh chunk trước)
        - input_hash (hash nội dung gốc)
        """
        model_name = str(config.get("model_name", "unset"))
        temperature = float(config.get("temperature", 0.0))
        prompts_sig = self._prompts_signature(prompts)
        prev_ctx_hash = self._stable_hash_text(previous_chunk_context or "")
        input_hash = self._stable_hash_text(original_chunk or "")

        key_obj = {
            "model": model_name,
            "temperature": round(temperature, 4),
            "prompts_sig": prompts_sig,
            "prev_ctx": prev_ctx_hash,
            "input": input_hash,
            # Có thể mở rộng thêm các trường cấu hình quan trọng khác trong tương lai (ví dụ: min/max ratio)
        }
        # Trả về chuỗi JSON ổn định, phần _get_cache_key sẽ băm MD5 làm tên file
        return json.dumps(
            key_obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    def _get_cache_path_from_logical_key(self, logical_key: str) -> str:
        """
        Nhận logical_key (JSON string) và trả về đường dẫn file cache (.pkl.gz) tương ứng.
        """
        ext = ".pkl.gz" if self.COMPRESS else ".pkl"
        file_name = self._md5(logical_key.encode("utf-8")) + ext
        return os.path.join(self.cache_dir, file_name)

    # API cũ vẫn giữ để tương thích (ít dùng trong v2.7.0)
    def get(self, logical_key: str) -> Optional[str]:
        """Trả về bản dịch đã cache theo logical_key (string)."""
        if not self.enabled:
            return None
        path = self._get_cache_path_from_logical_key(logical_key)

        # Try .pkl.gz first, then fallback to .pkl (legacy)
        if self.COMPRESS and os.path.exists(path):
            try:
                with self._lock, gzip.open(path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                pass

        # Try legacy .pkl without gzip
        legacy_path = path.replace(".pkl.gz", ".pkl")
        if os.path.exists(legacy_path):
            try:
                with self._lock, open(legacy_path, "rb") as f:
                    return pickle.load(f)
            except Exception:
                pass
        return None

    def set(self, logical_key: str, translation: str) -> None:
        """Lưu bản dịch vào cache theo logical_key (string)."""
        if not self.enabled:
            return
        path = self._get_cache_path_from_logical_key(logical_key)
        try:
            if self.COMPRESS:
                with self._lock, gzip.open(path, "wb") as f:
                    pickle.dump(translation, f)
            else:
                with self._lock, open(path, "wb") as f:
                    pickle.dump(translation, f)
        except Exception as e:
            logging.warning(f"⚠️ Không thể lưu cache: {e}")

    # API thuận tiện mới cho robust_translate
    def get_by_components(
        self,
        original_chunk: str,
        prompts: Dict[str, str],
        config: Dict[str, Any],
        previous_chunk_context: str,
    ) -> Optional[str]:
        """Xây khóa từ các thành phần và truy xuất cache."""
        key = self.build_key(original_chunk, prompts, config, previous_chunk_context)
        return self.get(key)

    def set_by_components(
        self,
        original_chunk: str,
        prompts: Dict[str, str],
        config: Dict[str, Any],
        previous_chunk_context: str,
        translation: str,
    ) -> None:
        """Xây khóa từ các thành phần và lưu cache."""
        key = self.build_key(original_chunk, prompts, config, previous_chunk_context)
        self.set(key, translation)
