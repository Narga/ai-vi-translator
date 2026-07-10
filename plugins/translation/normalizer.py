# src/text_normalizer.py - v2.4.1
# Tác giả: Narga
# Chức năng: Module chuẩn hóa văn bản, xử lý các ký tự đặc biệt và định dạng
#            trong bản dịch để đảm bảo tính nhất quán và chuyên nghiệp.

import re
import logging
from pathlib import Path


class TextNormalizer:
    """
    Lớp chuẩn hóa văn bản bản dịch, xử lý các vấn đề về ký tự và định dạng.
    
    Nhiệm vụ chính:
    - Chuyển đổi dấu gạch ngang dài (em dash) thành dấu gạch ngang thường
    - Chuyển đổi dấu ngoặc kép thành smart quotes
    - Chuẩn hóa dấu ngoặc vuông tiếng Trung
    - Loại bỏ các ký tự markdown không mong muốn
    """
    
    def __init__(self, is_text_source: bool = True):
        """
        Khởi tạo TextNormalizer.
        
        Args:
            is_text_source (bool): True nếu nguồn là file .txt (cần loại bỏ markdown),
                                   False nếu nguồn là markdown hoặc định dạng khác
        """
        self.is_text_source = is_text_source
        
        # Biểu thức chính quy để phát hiện dấu -- dùng trong ngữ cảnh đặc biệt
        # (như nhật ký, ghi chú tác giả: -- Ngày 1 --, -- Chú thích --)
        self.separator_pattern = re.compile(r'--\s*[^-]+\s*--')
        
        logging.info(f"🔧 TextNormalizer đã khởi tạo (text_source={is_text_source})")
    
    def normalize_dashes(self, text: str) -> str:
        """
        Chuẩn hóa dấu gạch ngang trong văn bản.
        
        - Chuyển dấu em dash (—, ——) ở đầu câu hội thoại thành dấu gạch ngang thường (-)
        - Giữ nguyên dấu -- khi dùng làm dấu ngăn cách (VD: -- Chương 1 --)
        
        Args:
            text (str): Văn bản cần chuẩn hóa
            
        Returns:
            str: Văn bản đã được chuẩn hóa dấu gạch ngang
        """
        # Bước 1: Đánh dấu các trường hợp dấu -- dùng làm separator để bảo vệ
        protected_separators = []
        
        def protect_separator(match):
            """Hàm callback để lưu trữ các separator cần bảo vệ."""
            protected_separators.append(match.group(0))
            return f"__PROTECTED_SEP_{len(protected_separators)-1}__"
        
        text = self.separator_pattern.sub(protect_separator, text)
        
        # Bước 2: Thay thế em dash (— hoặc ——) ở đầu câu hội thoại
        # Pattern: em dash ở đầu dòng hoặc sau khoảng trắng + có text sau đó
        text = re.sub(r'(^|\n|\s)(—+)', r'\1-', text)
        
        # Bước 3: Khôi phục lại các separator đã được bảo vệ
        for i, sep in enumerate(protected_separators):
            text = text.replace(f"__PROTECTED_SEP_{i}__", sep)
        
        return text
    
    def convert_to_smart_quotes(self, text: str) -> str:
        """
        Chuyển đổi dấu ngoặc kép thẳng thành smart quotes (curly quotes).
        
        Quy tắc:
        - Dấu " ở đầu câu hoặc sau khoảng trắng -> " (opening double quote)
        - Dấu " ở cuối câu hoặc trước dấu câu -> " (closing double quote)
        - Dấu ' tương tự -> ' và ' (single quotes)
        
        Args:
            text (str): Văn bản cần chuyển đổi
            
        Returns:
            str: Văn bản với smart quotes
        """
        # Xử lý dấu ngoặc kép đôi (")
        # Opening quote: sau khoảng trắng, đầu dòng, hoặc dấu mở ngoặc
        text = re.sub(r'(^|\s|[({$$])"', r'\1"', text, flags=re.MULTILINE)
        
        # Closing quote: trước khoảng trắng, dấu câu, cuối dòng, hoặc dấu đóng ngoặc
        text = re.sub(r'"(\s|[.,!?;:)}$$]|$)', r'"\1', text, flags=re.MULTILINE)
        
        # Xử lý dấu ngoặc đơn (')
        # Opening single quote
        text = re.sub(r"(^|\s|[({$$])'", r"\1'", text, flags=re.MULTILINE)
        
        # Closing single quote
        text = re.sub(r"'(\s|[.,!?;:)}$$]|$)", r"'\1", text, flags=re.MULTILINE)
        
        return text
    
    def normalize_brackets(self, text: str) -> str:
        """
        Chuẩn hóa dấu ngoặc vuông, chuyển dấu ngoặc vuông tiếng Trung thành dấu chuẩn.
        
        Chuyển đổi:
        - 【 】 -> [ ]
        - 〔 〕 -> [ ]
        - ［ ］ -> [ ]
        
        Args:
            text (str): Văn bản cần chuẩn hóa
            
        Returns:
            str: Văn bản với dấu ngoặc vuông chuẩn
        """
        # Các loại dấu ngoặc vuông tiếng Trung/Nhật
        chinese_brackets = {
            '【': '[',
            '】': ']',
            '〔': '[',
            '〕': ']',
            '［': '[',
            '］': ']'
        }
        
        for cn_bracket, en_bracket in chinese_brackets.items():
            text = text.replace(cn_bracket, en_bracket)
        
        return text
    
    def remove_markdown_formatting(self, text: str) -> str:
        """
        Loại bỏ các ký tự định dạng markdown không mong muốn.
        
        Chỉ áp dụng khi nguồn là file .txt thuần túy (is_text_source=True).
        Loại bỏ:
        - Code blocks (``` hoặc ''')
        - Bold (**text** hoặc __text__)
        - Italic (*text* hoặc _text_)
        
        Args:
            text (str): Văn bản cần xử lý
            
        Returns:
            str: Văn bản đã loại bỏ markdown formatting
        """
        if not self.is_text_source:
            return text
        
        # Loại bỏ code blocks (```
        text = re.sub(r"```|'''", '', text)
        
        # Loại bỏ bold: **text** hoặc __text__
        # Nhưng cần cẩn thận với __ trong separator (-- __ --)
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        
        # Loại bỏ italic: *text* hoặc _text_
        # Cẩn thận với * trong các biểu thức toán học hoặc chú thích
        text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'\1', text)
        text = re.sub(r'(?<!_)_(?!_)(.+?)(?<!_)_(?!_)', r'\1', text)
        
        return text
    
    def normalize(self, text: str) -> str:
        """
        Thực hiện toàn bộ quy trình chuẩn hóa văn bản.
        
        Áp dụng tất cả các bước chuẩn hóa theo thứ tự:
        1. Chuẩn hóa dấu gạch ngang
        2. Chuẩn hóa dấu ngoặc vuông
        3. Chuyển đổi thành smart quotes
        4. Loại bỏ markdown formatting (nếu cần)
        
        Args:
            text (str): Văn bản gốc cần chuẩn hóa
            
        Returns:
            str: Văn bản đã được chuẩn hóa hoàn chỉnh
        """
        if not text:
            return text
        
        # Bước 1: Chuẩn hóa dấu gạch ngang
        text = self.normalize_dashes(text)
        
        # Bước 2: Chuẩn hóa dấu ngoặc vuông
        text = self.normalize_brackets(text)
        
        # Bước 3: Chuyển đổi sang smart quotes
        text = self.convert_to_smart_quotes(text)
        
        # Bước 4: Loại bỏ markdown formatting (nếu nguồn là .txt)
        text = self.remove_markdown_formatting(text)
        
        return text


def detect_source_type(file_path: Path) -> bool:
    """
    Phát hiện loại file nguồn để xác định có nên loại bỏ markdown hay không.
    
    Args:
        file_path (Path): Đường dẫn đến file nguồn
        
    Returns:
        bool: True nếu là file .txt (cần loại bỏ markdown), False nếu ngược lại
    """
    if file_path.suffix.lower() == '.txt':
        return True
    elif file_path.suffix.lower() in ['.md', '.markdown', '.html', '.htm', '.xhtml']:
        return False
    else:
        # Mặc định coi như file text thuần túy
        return True
