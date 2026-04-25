# core/spellcheck_executor.py
import logging
import re
from pathlib import Path
from typing import Dict, Any, Callable, List, Optional, Tuple
from services.api_service import ApiManager
from plugins.translation.chunker import process_text_for_chunking
from plugins.spellcheck.spellchecker import spellcheck_chunk

logger = logging.getLogger(__name__)
from typing import Callable

class ProgressLogHandler(logging.Handler):
    """Handler chuyển hướng logs vào progress emitter của UI."""
    def __init__(self, emit_func: Callable):
        super().__init__()
        self.emit_func = emit_func
        self.setFormatter(logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S"))

    def emit(self, record):
        try:
            if record.levelno >= logging.INFO:
                self.emit_func({"type": "info", "message": record.getMessage()})
        except Exception:
            self.handleError(record)

class SpellcheckExecutor:
    """
    Executor chuyên biệt cho tác vụ Soát lỗi chính tả.
    Độc lập hoàn toàn với Translation Memory và Translation Glossary.
    """

    def __init__(
        self,
        api_keys: List[str],
        config: Dict[str, Any]
    ):
        self.api_manager = ApiManager(api_keys)
        self.config = config
        self.prompts = config.get("prompts", {})

    def execute(
        self,
        text: str,
        progress_callback: Optional[Callable] = None
    ) -> Tuple[str, str]:
        """
        Thực hiện soát lỗi chính tả cho toàn bộ văn bản.
        
        Returns:
            Tuple[clean_text, error_log]
        """
        # Đăng ký handler để chuyển hướng log vào UI
        ui_log_handler = None
        if progress_callback:
            ui_log_handler = ProgressLogHandler(progress_callback)
            logging.root.addHandler(ui_log_handler)

        try:
            # 1. Chia nhỏ văn bản
            chunk_size = self.config.get("chunk_size", 15000)
            min_chars = int(chunk_size * 0.7) # Ngưỡng tối thiểu mặc định
            chunks = process_text_for_chunking(text, min_chars=min_chars, max_chars=chunk_size)
            total_chunks = len(chunks)

            full_clean_text = []
            full_error_log = []

            spellcheck_prompt = self.prompts.get("main", "")

            for i, chunk in enumerate(chunks):
                base_percent = int((i / total_chunks) * 100)
                if progress_callback:
                    progress_callback({
                        "type": "progress",
                        "current": i + 1,
                        "total": total_chunks,
                        "percent": base_percent + 2,
                        "message": f"Đang gửi đoạn {i+1}/{total_chunks} đến AI..."
                    })

                # 2. Gọi AI soát lỗi
                result, status, api_key = spellcheck_chunk(
                    text=chunk,
                    prompt=spellcheck_prompt,
                    api_manager=self.api_manager,
                    config=self.config
                )

                if status == "success":
                    if progress_callback:
                        progress_callback({
                            "type": "progress",
                            "current": i + 1,
                            "total": total_chunks,
                            "percent": int(((i + 1) / total_chunks) * 100),
                            "message": f"✅ Soát lỗi đoạn {i+1} thành công!"
                        })
                    # 3. Phân tách kết quả (Văn bản sạch | Bảng lỗi)
                    clean, log = self._parse_result(result)
                    full_clean_text.append(clean)
                    if log:
                        full_error_log.append(f"--- Đoạn {i+1} ---\n{log}")
                else:
                    logger.error(f"Lỗi tại chunk {i+1}: {status}")
                    full_clean_text.append(chunk) # Giữ nguyên nếu lỗi
                    full_error_log.append(f"--- Đoạn {i+1} ---\nLỗi API: {status}")

            return "\n".join(full_clean_text), "\n\n".join(full_error_log)
        finally:
            if ui_log_handler:
                logging.root.removeHandler(ui_log_handler)

    def _parse_result(self, result: str) -> Tuple[str, str]:
        """
        Phân tách kết quả từ AI thành văn bản sạch và log lỗi.
        Thường AI trả về văn bản đã sửa, sau đó là dấu '---' và bảng Markdown.
        """
        # Tìm dấu phân cách phổ biến (--- hoặc === hoặc ### Bảng)
        delimiters = [r"\n---\n", r"\n===\n", r"\n#+ Bảng", r"\n#+ Log"]
        
        clean_text = result
        error_log = ""

        for delim in delimiters:
            parts = re.split(delim, result, flags=re.IGNORECASE)
            if len(parts) > 1:
                clean_text = parts[0].strip()
                error_log = parts[1].strip()
                break
        
        # Fallback nếu không thấy dấu phân cách rõ ràng nhưng có bảng Markdown
        if not error_log and "|" in result:
            lines = result.split("\n")
            clean_lines = []
            log_lines = []
            in_log = False
            for line in lines:
                if "|" in line and ("---" in line or "Từ gốc" in line):
                    in_log = True
                if in_log:
                    log_lines.append(line)
                else:
                    clean_lines.append(line)
            
            if log_lines:
                clean_text = "\n".join(clean_lines).strip()
                error_log = "\n".join(log_lines).strip()

        return clean_text, error_log
