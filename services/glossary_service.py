# services/glossary_service.py - v5.0.1
# Tác giả: Narga
# Dịch vụ quản lý và truy vấn từ điển (Glossary) động.
# Tối ưu: Dùng dict để dedup O(1), sắp xếp theo độ dài giảm dần
# để ưu tiên thuật ngữ dài hơn (tránh match bộ phận).

import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GlossaryEntry:
    """Một mục trong từ điển."""

    __slots__ = ("source", "target", "note")

    def __init__(self, source: str, target: str, note: str = ""):
        self.source = source
        self.target = target
        self.note = note

    def format(self) -> str:
        """Định dạng thành dòng text cho Prompt."""
        line = f"- {self.source} → {self.target}"
        if self.note:
            line += f" ({self.note})"
        return line


class GlossaryService:
    """
    Dịch vụ lọc và nhúng thuật ngữ từ điển dựa trên nội dung văn bản.

    - Tải từ điển một lần khi khởi tạo.
    - Quét chunk văn bản, chỉ trả về các thuật ngữ thực sự xuất hiện.
    - Sắp xếp theo độ dài giảm dần để ưu tiên thuật ngữ dài (tránh match sai).
    """

    PROMPT_HEADER = (
        "\n\n# BẢNG THUẬT NGỮ (GLOSSARY)\n"
        "Sử dụng các thuật ngữ sau để đảm bảo nhất quán:\n"
    )

    def __init__(self, glossary_paths: Optional[List[Path]] = None):
        """
        Khởi tạo với danh sách các đường dẫn file từ điển.

        Args:
            glossary_paths: List các Path dẫn đến file glossary.txt, characters.txt, v.v.
                            Nếu None hoặc rỗng, service sẽ không hoạt động.
        """
        self._entries: List[GlossaryEntry] = []
        if glossary_paths:
            self._load_all(glossary_paths)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def entry_count(self) -> int:
        """Số lượng mục từ điển đã tải."""
        return len(self._entries)

    @property
    def is_active(self) -> bool:
        """Kiểm tra xem service có dữ liệu hay không."""
        return len(self._entries) > 0

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_all(self, paths: List[Path]) -> None:
        """Tải và parse dữ liệu từ nhiều file, loại bỏ trùng lặp."""
        seen: Dict[str, GlossaryEntry] = {}  # source -> entry (dedup O(1))
        loaded_files = 0

        for path in paths:
            path = Path(path)
            if not path.exists():
                logger.warning(f"Glossary file không tồn tại: {path}")
                continue

            count_before = len(seen)
            try:
                for entry in self._parse_file(path):
                    # Nếu source đã tồn tại, giữ entry cũ (ưu tiên file đầu tiên)
                    if entry.source not in seen:
                        seen[entry.source] = entry
                loaded_files += 1
                added = len(seen) - count_before
                logger.debug(f"  └─ {path.name}: +{added} mục")
            except Exception as e:
                logger.error(f"Lỗi khi đọc glossary {path.name}: {e}")

        # Sắp xếp theo độ dài source giảm dần → ưu tiên match thuật ngữ dài trước
        self._entries = sorted(seen.values(), key=lambda e: len(e.source), reverse=True)

        if self._entries:
            logger.info(
                f"✅ Glossary: {len(self._entries)} mục từ {loaded_files} file(s)"
            )

    @staticmethod
    def _parse_file(path: Path) -> List[GlossaryEntry]:
        """
        Parse một file glossary.

        Format hỗ trợ:
            thuật ngữ gốc | thuật ngữ dịch | ghi chú (tùy chọn)

        Bỏ qua dòng trống và dòng bắt đầu bằng '#'.
        """
        entries: List[GlossaryEntry] = []

        with open(path, "r", encoding="utf-8") as f:
            for line_num, raw_line in enumerate(f, start=1):
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 2:
                    logger.warning(
                        f"Glossary {path.name}:{line_num} — bỏ qua dòng thiếu cột: {line!r}"
                    )
                    continue

                source, target = parts[0], parts[1]
                if not source or not target:
                    continue

                note = parts[2] if len(parts) > 2 else ""
                entries.append(GlossaryEntry(source, target, note))

        return entries

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get_relevant_entries(self, text: str) -> List[GlossaryEntry]:
        """
        Quét văn bản và trả về danh sách các entry xuất hiện trong text.

        Args:
            text: Văn bản cần quét (thường là nội dung 1 chunk).

        Returns:
            List các GlossaryEntry xuất hiện trong text (đã sắp xếp theo độ dài giảm dần).
        """
        if not self._entries or not text:
            return []

        return [entry for entry in self._entries if entry.source in text]

    def format_for_prompt(self, entries: List[GlossaryEntry]) -> str:
        """
        Đóng gói danh sách entry thành block text sẵn sàng nhúng vào Prompt.

        Args:
            entries: Danh sách GlossaryEntry từ get_relevant_entries().

        Returns:
            Chuỗi prompt block, hoặc chuỗi rỗng nếu entries trống.
        """
        if not entries:
            return ""

        lines = [entry.format() for entry in entries]
        return self.PROMPT_HEADER + "\n".join(lines) + "\n"

    def inject_into_prompt(self, text: str, prompt: str) -> Tuple[str, int]:
        """
        Tiện ích kết hợp: quét text, tìm thuật ngữ, nhúng vào prompt.

        Args:
            text: Nội dung chunk cần quét.
            prompt: Prompt gốc (main prompt).

        Returns:
            Tuple[str, int]: (prompt đã nhúng glossary, số thuật ngữ tìm được)
        """
        relevant = self.get_relevant_entries(text)
        if not relevant:
            return prompt, 0

        block = self.format_for_prompt(relevant)
        return prompt + block, len(relevant)
