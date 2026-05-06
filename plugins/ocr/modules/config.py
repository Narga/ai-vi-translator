# -*- coding: utf-8 -*-

"""
OCR reader module: extract text from scanned PDFs or images based on settings in config/config.yaml.

Dependencies:
- pytesseract (Python wrapper for Tesseract OCR)
- pdf2image (convert PDF pages to images)
- Pillow (image processing)
- PyYAML (read YAML config)

Config example in config/config.yaml:
  ocr:
    enabled: true
    tesseract_cmd: "C:/Program Files/Tesseract-OCR/tesseract.exe"
    lang: "vie+eng"
    psm: 3
    dpi: 300
"""

import os
import sys
import subprocess
import logging
import time
import asyncio
import gc
from typing import List, Optional
from pathlib import Path

# Suppress noisy logs từ Google libraries (absl, gRPC) trước khi import
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GLOG_minloglevel'] = '2'  # Suppress INFO và WARNING từ GLOG/absl
os.environ['GRPC_PYTHON_LOG_LEVEL'] = 'ERROR'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TensorFlow logs nếu có

# Define StderrFilter trước để filter stderr ngay từ đầu
class NoisyMessageFilter:
    """Filter để chặn các messages gây nhiễu được in trực tiếp ra stderr/stdout."""
    def __init__(self, original_stream):
        self.original_stream = original_stream
        # Buffer để xử lý multi-line messages
        self.buffer = ""
        # Patterns gây nhiễu (tất cả lowercase để so sánh)
        # Bao gồm cả partial matches để catch variations
        self.noisy_patterns = [
            'e0000',  # gRPC error prefix
            'alts_credentials',
            'alts creds',
            'alts creds ignored',
            'alts creds ignored. not running on gcp',
            'absl::initializelog',
            'not running on gcp',
            'untrusted alts',
            'untrusted alts is not enabled',
            'written to stderr',
            'all log messages before',
            'all log messages before absl',
            'alts_credentials.cc',  # File path pattern
            'alts_credentials.cc:93',  # File path with line number
            'warning: all log messages'  # Warning prefix
        ]
    
    def write(self, text):
        if not text:
            return
        
        # Thêm vào buffer để xử lý multi-line messages
        self.buffer += text
        
        # Kiểm tra buffer có chứa noisy patterns không (case-insensitive)
        buffer_lower = self.buffer.lower()
        
        # Kiểm tra nhanh trước khi split (tối ưu hơn)
        is_noisy = False
        
        # Check toàn bộ buffer trước (faster)
        for pattern in self.noisy_patterns:
            if pattern in buffer_lower:
                is_noisy = True
                break
        
        # Nếu chưa detect, check từng dòng chi tiết
        if not is_noisy:
            lines = self.buffer.split('\n')
            for line in lines:
                line_lower = line.lower().strip()
                # Check các pattern cụ thể
                if any(pattern in line_lower for pattern in self.noisy_patterns):
                    is_noisy = True
                    break
                # Check pattern E0000 ở đầu dòng
                if line_lower.startswith('e0000'):
                    is_noisy = True
                    break
                # Check "WARNING:" prefix với absl messages
                if line_lower.startswith('warning:') and ('absl' in line_lower or 'stderr' in line_lower):
                    is_noisy = True
                    break
        
        # Nếu không noisy, ghi ra stream
        if not is_noisy:
            self.original_stream.write(text)
        # Nếu noisy, không ghi gì cả (suppress hoàn toàn)
        
        # Reset buffer sau mỗi newline hoặc khi buffer quá dài
        if '\n' in text:
            # Giữ lại phần sau newline cuối cùng để check tiếp (cho multi-line messages)
            parts = self.buffer.rsplit('\n', 1)
            self.buffer = parts[-1] if len(parts) > 1 else ""
        
        if len(self.buffer) > 2000:  # Reset nếu buffer quá dài
            self.buffer = ""
    
    def flush(self):
        self.original_stream.flush()
    
    def __getattr__(self, name):
        return getattr(self.original_stream, name)


# Alias cho backward compatibility
StderrFilter = NoisyMessageFilter

# Suppress warnings từ absl trước khi import google libraries
try:
    import absl.logging
    absl.logging.set_verbosity(absl.logging.ERROR)
except Exception:
    pass

# Suppress logging từ các Google libraries
for lib_name in ['google', 'grpc', 'absl', 'google.generativeai', 'google.api_core', 'google.auth']:
    lib_logger = logging.getLogger(lib_name)
    lib_logger.setLevel(logging.ERROR)
    lib_logger.propagate = False

# Filter stderr ngay từ đầu để chặn messages in trực tiếp
# (không filter stdout ở đây để không ảnh hưởng đến user interaction)
_stderr_filter_active = False
_stdout_filter_active = False
try:
    original_stderr = sys.stderr
    sys.stderr = NoisyMessageFilter(original_stderr)
    _stderr_filter_active = True
except Exception:
    pass

# Lazy import yaml to avoid import errors
yaml = None
try:
    import yaml as _yaml
    yaml = _yaml
except ImportError:
    pass  # Will be imported later via lazy_import_and_install if needed

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from pdf2image import convert_from_path
except Exception:
    convert_from_path = None

try:
    from tqdm import tqdm  # progress bar (optional)
except Exception:
    tqdm = None

try:
    import PyPDF2
except Exception:
    PyPDF2 = None

try:
    import pdfplumber
except Exception:
    pdfplumber = None

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from docx import Document
    from docx.shared import Inches, Pt
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
except Exception:
    Document = None

# pdf2docx và ocrmypdf sẽ được import lazy trong _ensure_dependencies để tránh treo khi load module
Converter = None

# OCRmyPDF (for fallback when pdf2docx fails)
ocrmypdf_available = False
ocrmypdf = None

logger = logging.getLogger("NovelTranslator")


class GoogleLogFilter(logging.Filter):
    """
    Filter để loại bỏ các log messages gây nhiễu từ Google libraries.
    """
    def filter(self, record):
        msg = str(record.getMessage())
        msg_lower = msg.lower()
        
        # Loại bỏ các messages về absl::InitializeLog
        if 'absl::initializelog' in msg_lower or 'absl::InitializeLog' in msg:
            return False
        
        # Loại bỏ các messages về ALTS creds (nhiều pattern khác nhau)
        if any(pattern in msg for pattern in [
            'ALTS creds',
            'alts_credentials',
            'alts creds ignored',
            'not running on gcp',
            'untrusted alts is not enabled'
        ]):
            return False
        
        # Loại bỏ các messages từ absl logger
        if record.name.startswith('absl.') or 'absl' in record.name.lower():
            return False
        
        # Loại bỏ messages có pattern E0000 từ gRPC/absl
        if msg.startswith('E0000') and ('alts' in msg_lower or 'cred' in msg_lower):
            return False
        
        return True


_stderr_filter_active = False


def _suppress_google_logs():
    """
    Suppress logging từ Google libraries (gRPC, absl, etc.)
    Bao gồm cả việc filter stderr trực tiếp.
    """
    global _stderr_filter_active
    
    # Set environment variables
    os.environ['GRPC_VERBOSITY'] = 'ERROR'
    os.environ['GLOG_minloglevel'] = '2'
    os.environ['GRPC_PYTHON_LOG_LEVEL'] = 'ERROR'
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
    
    # Suppress absl logging nếu có
    try:
        import absl.logging
        absl.logging.set_verbosity(absl.logging.ERROR)
        # Disable absl handler
        for handler in absl.logging._absl_logger.handlers:
            handler.setLevel(logging.ERROR)
    except Exception:
        pass
    
    # Filter stderr và stdout để chặn messages in trực tiếp (re-apply để đảm bảo)
    global _stderr_filter_active, _stdout_filter_active
    try:
        # Kiểm tra nếu đã là NoisyMessageFilter rồi thì không cần apply lại
        if not isinstance(sys.stderr, NoisyMessageFilter):
            original_stderr = sys.stderr if not isinstance(sys.stderr, NoisyMessageFilter) else sys.stderr.original_stream
            sys.stderr = NoisyMessageFilter(original_stderr)
            _stderr_filter_active = True
    except Exception:
        pass
    
    try:
        if not isinstance(sys.stdout, NoisyMessageFilter):
            original_stdout = sys.stdout if not isinstance(sys.stdout, NoisyMessageFilter) else sys.stdout.original_stream
            sys.stdout = NoisyMessageFilter(original_stdout)
            _stdout_filter_active = True
    except Exception:
        pass
    
    # Apply filter cho root logger và các loggers cụ thể
    google_filter = GoogleLogFilter()
    root_logger = logging.getLogger()
    root_logger.addFilter(google_filter)
    
    # Suppress logging từ các Google libraries
    for lib_name in ['google', 'grpc', 'absl', 'google.generativeai', 'google.api_core', 'google.auth', 'grpc._cython']:
        lib_logger = logging.getLogger(lib_name)
        lib_logger.setLevel(logging.ERROR)
        lib_logger.propagate = False
        lib_logger.addFilter(google_filter)


def _parse_pages(pages_str: str) -> Optional[List[int]]:
    """
    Parse chuỗi pages thành danh sách số trang.
    Hỗ trợ:
    - "1,2,5,7" → [1, 2, 5, 7]
    - "1-7" → [1, 2, 3, 4, 5, 6, 7]
    - "1-3,5,7-9" → [1, 2, 3, 5, 7, 8, 9]
    
    Returns: List[int] hoặc None nếu không hợp lệ
    """
    if not pages_str or not pages_str.strip():
        return None
    
    pages_str = pages_str.strip()
    # Loại bỏ dấu ngoặc vuông hoặc ngoặc tròn nếu có (để tương thích ngược)
    if (pages_str.startswith('[') and pages_str.endswith(']')) or \
       (pages_str.startswith('(') and pages_str.endswith(')')):
        pages_str = pages_str[1:-1].strip()
    
    pages: List[int] = []
    parts = [p.strip() for p in pages_str.split(',')]
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        # Kiểm tra có phải range không (ví dụ: "1-7")
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                start = int(start.strip())
                end = int(end.strip())
                if start > end:
                    logger.warning(f"Range không hợp lệ: {part} (start > end). Bỏ qua.")
                    continue
                pages.extend(range(start, end + 1))
            except ValueError:
                logger.warning(f"Range không hợp lệ: {part}. Bỏ qua.")
                continue
        else:
            # Số trang đơn lẻ
            try:
                page_num = int(part)
                if page_num > 0:
                    pages.append(page_num)
            except ValueError:
                logger.warning(f"Số trang không hợp lệ: {part}. Bỏ qua.")
                continue
    
    # Loại bỏ trùng lặp và sắp xếp
    pages = sorted(list(set(pages)))
    
    if not pages:
        logger.warning("Không có trang hợp lệ nào được parse.")
        return None
    
    return pages


def _ensure_logger_config() -> None:
    """Đảm bảo logger có handler để in ra console và lưu file khi chạy trực tiếp.
    Tránh tình trạng không thấy log do thiếu cấu hình bên ngoài.
    """
    if getattr(_ensure_logger_config, "_configured", False):
        return
    
    # Suppress Google logs trước khi cấu hình logger
    _suppress_google_logs()
    
    logger.setLevel(logging.INFO)
    logger.propagate = False
    # Kiểm tra có StreamHandler/FileHandler chưa
    has_stream = any(isinstance(h, logging.StreamHandler) for h in logger.handlers)
    has_file = any(isinstance(h, logging.FileHandler) for h in logger.handlers)
    # Console handler
    if not has_stream:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        ch.addFilter(GoogleLogFilter())  # Apply filter để loại bỏ Google logs
        logger.addHandler(ch)
    # File handler
    if not has_file:
        try:
            os.makedirs("logs", exist_ok=True)
            fh = logging.FileHandler(os.path.join("logs", "ocr_runtime.log"), encoding="utf-8")
            fh.setLevel(logging.INFO)
            fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
            fh.addFilter(GoogleLogFilter())  # Apply filter để loại bỏ Google logs
            logger.addHandler(fh)
        except Exception:
            pass
    setattr(_ensure_logger_config, "_configured", True)


def _load_yaml(path: str) -> dict:
    global yaml
    if yaml is None:
        try:
            import yaml as _yaml
            yaml = _yaml
        except ImportError:
            raise ImportError("PyYAML is not installed. Please install: pip install PyYAML")
    
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}



def load_ocr_config(config_path: str = "config/config.yaml") -> dict:
    cfg = _load_yaml(config_path)
    ocr_cfg = cfg.get("ocr") or {}
    # Lưu config_path để dùng sau
    ocr_cfg["_config_path"] = config_path
    # Lưu api_keys từ root config để dùng cho AI cleanup
    ocr_cfg["_root_api_keys"] = cfg.get("api_keys", [])
    # Lưu safety_level từ root config (nếu có) để dùng cho AI cleanup/spell check
    # Ưu tiên: ocr.safety_level > root safety_level > default BLOCK_ONLY_HIGH
    if "safety_level" not in ocr_cfg:
        ocr_cfg["safety_level"] = cfg.get("safety_level", "BLOCK_ONLY_HIGH")
    return ocr_cfg


def _build_safety_settings(safety_level: str = "BLOCK_ONLY_HIGH") -> List[dict]:
    """
    Tạo safety settings cho Google Gemini API.
    Học hỏi từ module dịch thuật (model_router.py).
    
    Args:
        safety_level: Safety level từ config (BLOCK_NONE, BLOCK_ONLY_HIGH, BLOCK_MEDIUM_AND_ABOVE, BLOCK_LOW_AND_ABOVE)
    
    Returns:
        List of safety settings dicts cho GenerativeModel
    """
    safety_level = safety_level.upper() if safety_level else "BLOCK_ONLY_HIGH"
    
    # Các levels hợp lệ từ Google Gemini API
    valid_levels = ["BLOCK_NONE", "BLOCK_ONLY_HIGH", "BLOCK_MEDIUM_AND_ABOVE", "BLOCK_LOW_AND_ABOVE"]
    if safety_level not in valid_levels:
        logger.warning(f"Safety level '{safety_level}' không hợp lệ. Dùng default: BLOCK_ONLY_HIGH")
        safety_level = "BLOCK_ONLY_HIGH"
    
    return [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": safety_level},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": safety_level},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": safety_level},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": safety_level},
    ]


def _bundle_base_dir() -> str:
    """Return base dir for bundled resources (PyInstaller) or script dir."""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return getattr(sys, '_MEIPASS')  # PyInstaller temp dir
    # Fallback: repo/script directory
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _detect_bundled_binaries(ocr_cfg: dict) -> dict:
    """
    If config values are missing, try to detect bundled Tesseract and Poppler paths.
    - Looks for vendor/tesseract/tesseract.exe
    - Looks for vendor/poppler/bin
    """
    cfg = dict(ocr_cfg) if ocr_cfg else {}
    base = _bundle_base_dir()
    # Detect Tesseract
    if not cfg.get('tesseract_cmd'):
        cand = os.path.join(base, 'tesseract', 'tesseract.exe')
        if not os.path.exists(cand):
            cand = os.path.join(base, 'vendor', 'tesseract', 'tesseract.exe')
        if os.path.exists(cand):
            cfg['tesseract_cmd'] = cand.replace('\\', '/')
    # Detect Poppler bin
    if not cfg.get('poppler_path'):
        # 1) Bundled relative paths
        cand_dir = os.path.join(base, 'poppler', 'bin')
        if not os.path.isdir(cand_dir):
            cand_dir = os.path.join(base, 'vendor', 'poppler', 'bin')
        if os.path.isdir(cand_dir):
            cfg['poppler_path'] = cand_dir.replace('\\', '/')
        else:
            # 2) Environment variables
            env_poppler = os.environ.get('POPPLER_PATH') or os.environ.get('POPPLER_BIN')
            if env_poppler and os.path.isdir(env_poppler):
                cfg['poppler_path'] = env_poppler.replace('\\', '/')
            else:
                # 3) Try to find pdftoppm from PATH
                try:
                    import shutil
                    pdftoppm = shutil.which('pdftoppm')
                    if pdftoppm:
                        cfg['poppler_path'] = os.path.dirname(pdftoppm).replace('\\', '/')
                except Exception:
                    pass
    return cfg


# Inline lazy import implementation (no dependency on src.utils.helpers)
def lazy_import_and_install(package_name: str, import_name: str = None, version_spec: str = ""):
    """
    Lazy import a package, installing it if not available.
    
    Args:
        package_name: Package name to install (e.g., 'Pillow')
        import_name: Module name to import (e.g., 'PIL'), defaults to package_name
        version_spec: Version specification (e.g., '>=10.0.0')
    
    Returns:
        Imported module
    """
    if import_name is None:
        import_name = package_name
    
    try:
        # Try to import
        import importlib
        return importlib.import_module(import_name)
    except ImportError:
        # Install if not available
        logger.info(f"Installing {package_name}{version_spec}...")
        try:
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', '-q',
                f"{package_name}{version_spec}" if version_spec else package_name
            ])
            import importlib
            return importlib.import_module(import_name)
        except Exception as e:
            raise ImportError(f"Failed to install {package_name}: {e}")

def _pip_install(package: str) -> None:
    # Giữ hàm để tương thích ngược nếu có nơi khác gọi
    try:
        lazy_import_and_install(package)
    except Exception as e:
        raise RuntimeError(f"Không thể cài gói '{package}': {e}")



def _ensure_dependencies(ocr_cfg: dict) -> None:
    global Image, pytesseract, convert_from_path, tqdm, PyPDF2, pdfplumber, fitz, Document, Inches, Pt, WD_PARAGRAPH_ALIGNMENT
    # Pillow
    if Image is None:
        # Import trực tiếp submodule PIL.Image để tránh getattr trên package gốc
        _pil_image_mod = lazy_import_and_install("Pillow", "PIL.Image", ">=10.0.0")
        Image = getattr(_pil_image_mod, 'Image', _pil_image_mod)
    # pdf2image
    if convert_from_path is None:
        pdf2image = lazy_import_and_install("pdf2image", "pdf2image", ">=1.17.0")
        convert_from_path = getattr(pdf2image, 'convert_from_path')
    # pytesseract (runtime still needs system Tesseract)
    if pytesseract is None:
        pytesseract = lazy_import_and_install("pytesseract", "pytesseract", ">=0.3.10")
    # pdfplumber (preferred for text extraction)
    if pdfplumber is None:
        try:
            pdfplumber = lazy_import_and_install("pdfplumber", "pdfplumber", ">=0.9.0")
        except Exception:
            pass
    # PyPDF2 (fallback for text extraction)
    if PyPDF2 is None:
        try:
            PyPDF2 = lazy_import_and_install("PyPDF2", "PyPDF2", ">=3.0.0")
        except Exception:
            pass
    # yaml (PyYAML) was already imported to read config; skip
    # tqdm optional
    if bool(ocr_cfg.get("show_progress", True)) and tqdm is None:
        try:
            _tqdm_mod = lazy_import_and_install("tqdm", "tqdm", ">=4.65.0")
            from tqdm import tqdm as _tqdm
            tqdm = _tqdm
        except Exception:
            tqdm = None
    # PyMuPDF (for extracting images from PDF)
    # Limited to <1.26.5 for pdf2docx compatibility (1.26.5+ removed get_area method)
    if fitz is None:
        try:
            fitz = lazy_import_and_install("PyMuPDF", "fitz", ">=1.23.0,<1.26.5")
        except Exception:
            try:
                fitz = lazy_import_and_install("PyMuPDF==1.26.4", "fitz")
            except Exception:
                fitz = None
    # python-docx (for creating DOCX output)
    if Document is None:
        try:
            docx_mod = lazy_import_and_install("python-docx", "docx", ">=1.0.0")
            from docx import Document as _Document
            from docx.shared import Inches as _Inches, Pt as _Pt
            from docx.enum.text import WD_PARAGRAPH_ALIGNMENT as _WD_PARAGRAPH_ALIGNMENT
            Document = _Document
            global Inches, Pt, WD_PARAGRAPH_ALIGNMENT
            Inches = _Inches
            Pt = _Pt
            WD_PARAGRAPH_ALIGNMENT = _WD_PARAGRAPH_ALIGNMENT
        except Exception:
            Document = None
            Inches = None
            Pt = None
            WD_PARAGRAPH_ALIGNMENT = None
    # pdf2docx (for hybrid workflow: PDF → DOCX conversion)
    global Converter
    if Converter is None:
        try:
            _pdf2docx = lazy_import_and_install("pdf2docx", "pdf2docx", ">=0.5.0")
            from pdf2docx import Converter as _Converter
            Converter = _Converter
        except Exception:
            Converter = None
    
    # OCRmyPDF (for fallback when pdf2docx fails)
    global ocrmypdf_available
    if not ocrmypdf_available:
        try:
            _ocrmypdf = lazy_import_and_install("ocrmypdf", "ocrmypdf", ">=15.0.0")
            global ocrmypdf
            ocrmypdf = _ocrmypdf
            ocrmypdf_available = True
        except Exception:
            ocrmypdf_available = False
            ocrmypdf = None
            logger.warning("⚠️  OCRmyPDF không khả dụng. Fallback sẽ không hoạt động.")


def _apply_tesseract_cfg(ocr_cfg: dict) -> None:
    if pytesseract is None:
        raise RuntimeError("pytesseract not installed. Please install pytesseract and system Tesseract.")
    # Allow auto-detect of bundled binaries
    _cfg = _detect_bundled_binaries(ocr_cfg)
    tesseract_cmd = _cfg.get("tesseract_cmd")
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
