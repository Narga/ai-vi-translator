# src/configuration.py - v2.5.1
# Tác giả: Narga
# Chức năng: Module quản lý việc nạp và xử lý tất cả các file cấu hình.
#            API keys được nạp từ file API.txt riêng biệt.
#            Translation guidelines được nạp từ prompts/instructions/.

import configparser
import logging
from pathlib import Path
from typing import Dict, List

from .translation_guide import load_guidelines_from_instructions_dir


def load_api_keys(api_file_path: str = 'API.txt') -> List[str]:
    """
    Đọc danh sách API keys từ file text.
    
    File format:
    - Mỗi key trên một dòng
    - Dòng trống sẽ bị bỏ qua
    - Dòng bắt đầu bằng # là comment (bị bỏ qua)
    - Khoảng trắng đầu/cuối dòng được tự động loại bỏ
    
    Args:
        api_file_path (str): Đường dẫn đến file chứa API keys
        
    Returns:
        List[str]: Danh sách các API keys hợp lệ
        
    Raises:
        FileNotFoundError: Nếu không tìm thấy file API.txt
        ValueError: Nếu file không chứa API key nào hợp lệ
    """
    api_path = Path(api_file_path)
    
    if not api_path.exists():
        raise FileNotFoundError(
            f"Không tìm thấy file '{api_file_path}'. "
            f"Vui lòng tạo file này và thêm các Gemini API keys (mỗi key một dòng)."
        )
    
    try:
        with open(api_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Lọc và làm sạch các dòng
        api_keys = []
        for line_num, line in enumerate(lines, start=1):
            line = line.strip()
            
            # Bỏ qua dòng trống và comment
            if not line or line.startswith('#'):
                continue
            
            # Kiểm tra độ dài key (Gemini API key thường dài 39 ký tự)
            if len(line) < 20:
                logging.warning(f"Dòng {line_num} trong {api_file_path} có vẻ không phải API key hợp lệ (quá ngắn). Bỏ qua.")
                continue
            
            api_keys.append(line)
        
        if not api_keys:
            raise ValueError(
                f"File '{api_file_path}' không chứa API key nào hợp lệ. "
                f"Vui lòng thêm ít nhất một Gemini API key."
            )
        
        logging.info(f"✅ Đã nạp {len(api_keys)} API key từ '{api_file_path}'.")
        return api_keys
    
    except Exception as e:
        logging.error(f"Lỗi khi đọc file API keys: {e}")
        raise


def setup_directories(config: configparser.RawConfigParser) -> Dict[str, Path]:
    """
    Đọc đường dẫn từ config, tạo các thư mục nếu chưa tồn tại.
    
    Args:
        config (configparser.RawConfigParser): Đối tượng parser đã đọc file config.ini.
        
    Returns:
        Dict[str, Path]: Dictionary chứa các đối tượng Path cho thư mục làm việc.
    """
    dirs = {
        'input': Path(config.get('DIRECTORIES', 'INPUT_DIR')),
        'output_base': Path(config.get('DIRECTORIES', 'OUTPUT_DIR')),
        'cache': Path(config.get('DIRECTORIES', 'CACHE_DIR')),
        'progress': Path(config.get('DIRECTORIES', 'PROGRESS_DIR')),
    }
    
    for dir_path in dirs.values():
        dir_path.mkdir(parents=True, exist_ok=True)
    
    return dirs


def load_all_configs() -> configparser.RawConfigParser:
    """
    Đọc file cấu hình config.ini một cách an toàn.
    
    Returns:
        configparser.RawConfigParser: Đối tượng parser chứa toàn bộ cấu hình
        
    Raises:
        FileNotFoundError: Nếu không tìm thấy file config.ini
        Exception: Các lỗi khác khi đọc file cấu hình
    """
    config_parser = configparser.RawConfigParser()
    config_file_path = 'config.ini'
    
    try:
        if not Path(config_file_path).exists():
            raise FileNotFoundError(f"Không tìm thấy file cấu hình '{config_file_path}'.")
        
        config_parser.read(config_file_path, encoding='utf-8')
        logging.info(f"✅ Đã nạp file cấu hình '{config_file_path}'.")
        
        return config_parser
    
    except Exception as e:
        logging.error(f"Lỗi khi đọc file cấu hình: {e}")
        raise


def load_prompts(
    config: configparser.RawConfigParser,
    dirs: Dict[str, Path],
    base_filename: str
) -> Dict[str, str]:
    """
    Nạp các file prompt và file notes.txt của dự án.
    Translation guidelines được nạp từ prompts/instructions/.
    
    Args:
        config (configparser.RawConfigParser): Đối tượng cấu hình
        dirs (Dict[str, Path]): Dictionary chứa các đường dẫn thư mục
        base_filename (str): Tên cơ sở của file đang dịch
        
    Returns:
        Dict[str, str]: Dictionary chứa các prompt
            - 'main': Prompt dịch chính
            - 'retranslate': Prompt dịch lại (chống cắt ngắn)
            - 'correction': Prompt sửa lỗi ký tự tiếng Trung
            - 'consistency': Prompt kiểm tra nhất quán (nếu có)
    """
    prompts = {}
    
    # Đọc project notes (nếu có)
    project_notes_content = ""
    notes_file_path = dirs['input'] / base_filename / 'notes.txt'
    
    if notes_file_path.exists():
        try:
            with open(notes_file_path, 'r', encoding='utf-8') as f:
                project_notes_content = f.read()
            logging.info(f"📝 Đã nạp file notes.txt cho dự án '{base_filename}'.")
        except Exception as e:
            logging.warning(f"⚠️  Không thể đọc file notes.txt: {e}")
    else:
        # Tìm notes.txt ở thư mục input gốc (cho trường hợp file đơn)
        notes_file_fallback = dirs['input'] / 'notes.txt'
        if notes_file_fallback.exists():
            try:
                with open(notes_file_fallback, 'r', encoding='utf-8') as f:
                    project_notes_content = f.read()
                logging.info(f"📝 Đã nạp file notes.txt từ thư mục input.")
            except Exception as e:
                logging.warning(f"⚠️  Không thể đọc file notes.txt: {e}")
    
    if not project_notes_content.strip():
        project_notes_content = "Không có ghi chú đặc biệt cho dự án này."
    
    # Nạp translation guidelines từ prompts/instructions/
    logging.info(f"🔍 Tìm kiếm translation guidelines trong prompts/instructions/...")
    translation_guidelines = load_guidelines_from_instructions_dir()
    
    # Đọc các file prompt
    prompt_files = {
        'main': '01-main.txt',
        'retranslate': '02-retranslate.txt',
        'correction': '03-correction.txt',
        'consistency': '04-consistency_check.txt'
    }
    
    prompts_dir = Path('prompts')
    
    for key, filename in prompt_files.items():
        file_path = prompts_dir / filename
        
        if file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    prompt_content = f.read()
                
                # Thay thế placeholder {project_notes}
                prompt_content = prompt_content.replace('{project_notes}', project_notes_content)
                
                # Thay thế placeholder {translation_guidelines}
                prompt_content = prompt_content.replace('{translation_guidelines}', translation_guidelines)
                
                # Lưu vào dictionary
                prompts[key] = prompt_content
                
                logging.info(f"✅ Đã nạp prompt '{filename}'.")
            
            except Exception as e:
                logging.error(f"❌ Lỗi khi đọc file prompt '{filename}': {e}")
                prompts[key] = ""
        else:
            logging.warning(f"⚠️  Không tìm thấy file prompt '{filename}'.")
            prompts[key] = ""
    
    # Kiểm tra prompt chính
    if not prompts.get('main'):
        logging.critical("❌ CẢNH BÁO: Prompt chính (01-main.txt) không được nạp!")
    
    return prompts


def validate_config(config: configparser.RawConfigParser, api_keys: List[str]) -> bool:
    """
    Kiểm tra tính hợp lệ của cấu hình và API keys.
    
    Args:
        config (configparser.RawConfigParser): Đối tượng cấu hình cần kiểm tra
        api_keys (List[str]): Danh sách API keys đã nạp
        
    Returns:
        bool: True nếu cấu hình hợp lệ, False nếu có lỗi
    """
    try:
        # Kiểm tra API keys
        if not api_keys:
            logging.error("❌ Lỗi: Không có API key nào được nạp từ file API.txt!")
            return False
        
        # Kiểm tra các thư mục
        required_dirs = ['INPUT_DIR', 'OUTPUT_DIR', 'CACHE_DIR', 'PROGRESS_DIR']
        
        for dir_key in required_dirs:
            if not config.has_option('DIRECTORIES', dir_key):
                logging.error(f"❌ Lỗi: Thiếu cấu hình '{dir_key}' trong section [DIRECTORIES]!")
                return False
        
        logging.info("✅ Cấu hình hợp lệ.")
        return True
    
    except Exception as e:
        logging.error(f"❌ Lỗi khi validate cấu hình: {e}")
        return False
