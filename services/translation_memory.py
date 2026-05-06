# services/translation_memory.py - v1.0.0
# Tác giả: Narga
# Chức năng: Translation Memory - lưu trữ và tìm kiếm các bản dịch đã thực hiện

"""
Translation Memory Service
=========================
Lưu trữ và tìm kiếm các bản dịch đã thực hiện dựa trên fuzzy matching.

Khác với Cache:
- Cache: Lưu theo hash chính xác của chunk
- TM: Lưu các cặp câu/cụm từ, tìm kiếm fuzzy match

Features:
- Fuzzy matching với threshold có thể điều chỉnh
- N-gram based similarity
- Export/Import TM
- Thống kê sử dụng
"""

import os
import json
import logging
import hashlib
from threading import Lock
from typing import Optional, List, Dict, Any, Tuple
from collections import Counter


class TranslationMemory:
    """
    Translation Memory với fuzzy matching.

    Lưu trữ các cặp (source, target) và tìm kiếm dựa trên độ tương tự.
    """

    def __init__(
        self,
        tm_dir: str = "workspace/translation_memory",
        enabled: bool = True,
        min_match_length: int = 20,
        similarity_threshold: float = 0.85,
    ):
        """
        Khởi tạo Translation Memory.

        Args:
            tm_dir: Thư mục lưu TM
            enabled: Bật/tắt TM
            min_match_length: Độ dài tối thiểu để lưu vào TM
            similarity_threshold: Ngưỡng fuzzy match (0-1)
        """
        self.enabled = enabled
        self.min_match_length = min_match_length
        self.similarity_threshold = similarity_threshold
        self.tm_dir = tm_dir

        if not self.enabled:
            logging.info("ℹ️ Translation Memory đã bị tắt.")
            return

        os.makedirs(self.tm_dir, exist_ok=True)
        self._lock = Lock()

        # Load existing TM
        self._memory: Dict[str, List[Dict]] = {}
        self._load_memory()

        logging.info(
            f"📚 Translation Memory initialized. Thư mục: '{self.tm_dir}', "
            f"Min length: {min_match_length}, Threshold: {similarity_threshold}"
        )

    def _load_memory(self) -> None:
        """Load TM từ disk."""
        tm_file = os.path.join(self.tm_dir, "memory.json")
        if os.path.exists(tm_file):
            try:
                with open(tm_file, "r", encoding="utf-8") as f:
                    self._memory = json.load(f)
                total_entries = sum(len(v) for v in self._memory.values())
                logging.info(f"📚 Đã load {total_entries} entries từ TM")
            except Exception as e:
                logging.warning(f"⚠️ Không thể load TM: {e}")
                self._memory = {}

    def _save_memory(self) -> None:
        """Save TM to disk."""
        tm_file = os.path.join(self.tm_dir, "memory.json")
        try:
            with open(tm_file, "w", encoding="utf-8") as f:
                json.dump(self._memory, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f"⚠️ Không thể save TM: {e}")

    def _compute_ngrams(self, text: str, n: int = 3) -> Counter:
        """Compute n-grams từ text."""
        text = text.lower().strip()
        ngrams = []
        for i in range(len(text) - n + 1):
            ngrams.append(text[i : i + n])
        return Counter(ngrams)

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        Tính độ tương tự giữa 2 texts sử dụng n-gram Jaccard similarity.

        Args:
            text1: Text thứ nhất
            text2: Text thứ hai

        Returns:
            Độ tương tự (0-1)
        """
        if not text1 or not text2:
            return 0.0

        text1 = text1.lower().strip()
        text2 = text2.lower().strip()

        if text1 == text2:
            return 1.0

        # Tính n-grams
        ngrams1 = self._compute_ngrams(text1)
        ngrams2 = self._compute_ngrams(text2)

        # Jaccard similarity
        all_ngrams = set(ngrams1.keys()) | set(ngrams2.keys())
        if not all_ngrams:
            return 0.0

        common = set(ngrams1.keys()) & set(ngrams2.keys())
        return len(common) / len(all_ngrams)

    def _normalize_text(self, text: str) -> str:
        """Normalize text để lưu vào TM."""
        # Loại bỏ whitespace thừa, lowercase
        return " ".join(text.lower().split())

    def add_translation(self, source: str, target: str, context: str = "") -> None:
        """
        Thêm một cặp dịch vào TM.

        Args:
            source: Văn bản gốc
            target: Văn bản dịch
            context: Ngữ cảnh (tùy chọn)
        """
        if not self.enabled:
            return

        if len(source) < self.min_match_length:
            return

        source_norm = self._normalize_text(source)
        source_hash = hashlib.md5(source_norm.encode()).hexdigest()[:16]

        entry = {
            "source": source,
            "target": target,
            "context": context,
            "source_hash": source_hash,
        }

        with self._lock:
            if source_hash not in self._memory:
                self._memory[source_hash] = []

            # Check if exists
            for existing in self._memory[source_hash]:
                if existing["source"] == source:
                    existing["target"] = target
                    existing["context"] = context
                    break
            else:
                self._memory[source_hash].append(entry)

            self._save_memory()

    def add_translations(self, translations: List[Tuple[str, str]], context: str = "") -> None:
        """
        Thêm nhiều cặp dịch cùng lúc.

        Args:
            translations: List of (source, target) tuples
            context: Ngữ cảnh chung
        """
        for source, target in translations:
            self.add_translation(source, target, context)

    def find_match(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Tìm kiếm fuzzy match trong TM.

        Args:
            text: Văn bản cần dịch

        Returns:
            Dict với 'translation', 'similarity', 'source' hoặc None
        """
        if not self.enabled or not text:
            return None

        text_norm = self._normalize_text(text)

        # First, exact hash lookup
        text_hash = hashlib.md5(text_norm.encode()).hexdigest()[:16]
        if text_hash in self._memory:
            for entry in self._memory[text_hash]:
                if self._normalize_text(entry["source"]) == text_norm:
                    return {
                        "translation": entry["target"],
                        "similarity": 1.0,
                        "source": entry["source"],
                        "exact": True,
                    }

        # Fuzzy search
        best_match = None
        best_similarity = 0.0

        with self._lock:
            for entries in self._memory.values():
                for entry in entries:
                    similarity = self.compute_similarity(text, entry["source"])
                    if similarity > best_similarity and similarity >= self.similarity_threshold:
                        best_similarity = similarity
                        best_match = entry

        if best_match:
            return {
                "translation": best_match["target"],
                "similarity": best_similarity,
                "source": best_match["source"],
                "exact": False,
            }

        return None

    def find_matches(self, text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Tìm nhiều fuzzy matches.

        Args:
            text: Văn bản cần dịch
            limit: Số lượng kết quả tối đa

        Returns:
            List of matches sorted by similarity
        """
        if not self.enabled or not text:
            return []

        matches = []

        with self._lock:
            for entries in self._memory.values():
                for entry in entries:
                    similarity = self.compute_similarity(text, entry["source"])
                    if similarity >= 0.5:  # Lower threshold for listing
                        matches.append(
                            {
                                "translation": entry["target"],
                                "similarity": similarity,
                                "source": entry["source"],
                            }
                        )

        # Sort by similarity
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        return matches[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê TM."""
        total_entries = sum(len(v) for v in self._memory.values())

        # Estimate total characters
        total_chars = 0
        total_translated = 0
        with self._lock:
            for entries in self._memory.values():
                for entry in entries:
                    total_chars += len(entry.get("source", ""))
                    total_translated += len(entry.get("target", ""))

        return {
            "enabled": self.enabled,
            "total_entries": total_entries,
            "total_source_chars": total_chars,
            "total_target_chars": total_translated,
            "min_match_length": self.min_match_length,
            "similarity_threshold": self.similarity_threshold,
            "memory_size_mb": self._estimate_size(),
        }

    def _estimate_size(self) -> float:
        """Ước tính kích thước TM."""
        try:
            tm_file = os.path.join(self.tm_dir, "memory.json")
            if os.path.exists(tm_file):
                return os.path.getsize(tm_file) / 1024 / 1024
        except Exception as e:
            logging.debug(f"Failed to estimate TM size: {e}")
        return 0.0

    def export_tm(self, filepath: str) -> bool:
        """Export TM ra file."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._memory, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            logging.error(f"Export TM failed: {e}")
            return False

    def import_tm(self, filepath: str, merge: bool = True) -> bool:
        """Import TM từ file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                imported = json.load(f)

            if merge:
                with self._lock:
                    for key, entries in imported.items():
                        if key not in self._memory:
                            self._memory[key] = []
                        for entry in entries:
                            # Check if exists
                            found = False
                            for existing in self._memory[key]:
                                if existing["source"] == entry["source"]:
                                    found = True
                                    break
                            if not found:
                                self._memory[key].append(entry)
                    self._save_memory()
            else:
                self._memory = imported
                self._save_memory()

            return True
        except Exception as e:
            logging.error(f"Import TM failed: {e}")
            return False

    def clear(self) -> int:
        """Xóa toàn bộ TM."""
        count = sum(len(v) for v in self._memory.values())
        with self._lock:
            self._memory = {}
            self._save_memory()
        return count

    def remove_duplicates(self) -> int:
        """Loại bỏ các entries trùng lặp."""
        removed = 0
        with self._lock:
            for key in list(self._memory.keys()):
                seen = set()
                entries = self._memory[key]
                unique_entries = []
                for entry in entries:
                    source_norm = self._normalize_text(entry["source"])
                    if source_norm not in seen:
                        seen.add(source_norm)
                        unique_entries.append(entry)
                    else:
                        removed += 1
                self._memory[key] = unique_entries
            self._save_memory()
        return removed


class ChunkTranslationMemory:
    """
    Translation Memory cho các chunk lớn.

    Khác với TranslationMemory (cho câu/đoạn nhỏ):
    - Lưu trữ các chunk đã dịch hoàn chỉnh
    - Sử dụng cho việc resume/interrupt handling
    """

    def __init__(self, chunk_tm_dir: str = "workspace/translation_memory/chunks"):
        self.chunk_tm_dir = chunk_tm_dir
        os.makedirs(self.chunk_tm_dir, exist_ok=True)
        self._lock = Lock()

    def save_chunk_translation(
        self, chunk_hash: str, translation: str, metadata: Dict[str, Any] = None
    ) -> None:
        """Lưu translation của một chunk."""
        chunk_file = os.path.join(self.chunk_tm_dir, f"{chunk_hash}.json")
        data = {
            "translation": translation,
            "metadata": metadata or {},
        }
        try:
            with open(chunk_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logging.warning(f"⚠️ Không thể lưu chunk TM: {e}")

    def get_chunk_translation(self, chunk_hash: str) -> Optional[str]:
        """Lấy translation của một chunk."""
        chunk_file = os.path.join(self.chunk_tm_dir, f"{chunk_hash}.json")
        if os.path.exists(chunk_file):
            try:
                with open(chunk_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("translation")
            except Exception as e:
                logging.debug(f"Failed to read chunk TM: {e}")
        return None

    def clear_chunk_tm(self) -> int:
        """Xóa toàn bộ chunk TM."""
        count = 0
        for f in os.listdir(self.chunk_tm_dir):
            if f.endswith(".json"):
                os.remove(os.path.join(self.chunk_tm_dir, f))
                count += 1
        return count
