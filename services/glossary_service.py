# services/glossary_service.py - v5.0.0
# Tác giả: Narga
# Dịch vụ quản lý và truy vấn từ điển (Glossary) động.

import re
import logging
from pathlib import Path
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)

class GlossaryService:
    """
    Dịch vụ giúp lọc và nhúng thuật ngữ từ điển dựa trên nội dung văn bản.
    Hỗ trợ tránh việc nhúng toàn bộ từ điển gây lãng phí Token.
    """

    def __init__(self, glossary_paths: List[Path]):
        """
        Khởi tạo với danh sách các đường dẫn file từ điển.
        
        Args:
            glossary_paths: List các Path dẫn đến file glossary.txt, characters.txt, v.v.
        """
        self.glossary_paths = glossary_paths
        self.entries: List[Tuple[str, str, str]] = []  # (gốc, dịch, ghi chú)
        self._load_glossaries()

    def _load_glossaries(self):
        """Tải và parse dữ liệu từ các file."""
        self.entries = []
        for path in self.glossary_paths:
            path = Path(path)
            if not path.exists():
                continue
            
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        # Bỏ qua dòng trống hoặc comment
                        if not line or line.startswith("#"):
                            continue
                        
                        # Format: gốc | dịch | ghi chú (tùy chọn)
                        parts = [p.strip() for p in line.split("|")]
                        if len(parts) >= 2:
                            source = parts[0]
                            target = parts[1]
                            note = parts[2] if len(parts) > 2 else ""
                            # Tránh trùng lặp
                            if (source, target, note) not in self.entries:
                                self.entries.append((source, target, note))
            except Exception as e:
                logger.error(f"Lỗi khi đọc file từ điển {path.name}: {e}")
        
        if self.entries:
            logger.info(f"✅ Đã tải {len(self.entries)} mục từ điển từ {len(self.glossary_paths)} files.")

    def get_relevant_entries(self, text: str) -> str:
        """
        Quét văn bản và trả về chuỗi định dạng từ điển chỉ cho các từ xuất hiện trong text.
        
        Args:
            text: Văn bản cần quét
            
        Returns:
            str: Chuỗi glossary để nhúng vào Prompt, hoặc chuỗi trống nếu không tìm thấy từ nào.
        """
        if not self.entries or not text:
            return ""

        found = []
        # Tối ưu: Dùng vòng lặp đơn giản. Với từ điển < 1000 mục, tốc độ Python là đủ nhanh.
        # Lưu ý: key phải có trong text (case-sensitive hoặc tùy nhu cầu, ở đây dùng sensitive cho chính xác)
        for source, target, note in self.entries:
            if source in text:
                entry_str = f"- {source} -> {target}"
                if note:
                    entry_str += f" ({note})"
                found.append(entry_str)
        
        if not found:
            return ""
            
        return "\n".join(found)

    def format_for_prompt(self, relevant_entries: str) -> str:
        """Đóng gói từ điển vào block định dạng cho Prompt."""
        if not relevant_entries:
            return ""
            
        return (
            "\n\n# BẢNG THUẬT NGỮ (GLOSSARY)\n"
            "Sử dụng các thuật ngữ sau để đảm bảo nhất quán:\n"
            f"{relevant_entries}\n"
        )
