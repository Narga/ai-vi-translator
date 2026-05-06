# core/log_handler.py
"""Shared logging handler cho core executors."""

import logging
from typing import Callable


class ProgressLogHandler(logging.Handler):
    """Handler chuyển hướng logs vào progress emitter của UI.

    Hỗ trợ 2 emit styles:
    - "kwargs": emit_func("info", message=...) — dùng bởi TranslationExecutor
    - "dict": emit_func({"type": "info", "message": ...}) — dùng bởi SpellcheckExecutor
    """

    def __init__(self, emit_func: Callable, style: str = "kwargs"):
        super().__init__()
        self.emit_func = emit_func
        self.style = style
        self.setFormatter(
            logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record):
        try:
            if record.levelno >= logging.INFO:
                msg = record.getMessage()
                if self.style == "dict":
                    self.emit_func({"type": "info", "message": msg})
                else:
                    self.emit_func("info", message=msg)
        except Exception:
            self.handleError(record)
