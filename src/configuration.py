# src/configuration.py - v2.2.0
# Tác giả: Narga
# Chức năng: Module quản lý việc nạp và xử lý tất cả các file cấu hình.

import configparser
import logging
from pathlib import Path
from typing import Dict

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
    """Đọc file cấu hình config.ini một cách an toàn."""
    config_parser = configparser.RawConfigParser(interpolation=None)
    if not Path('config.ini').exists():
        raise FileNotFoundError("Không tìm thấy file 'config.ini'.")
    config_parser.read('config.ini', encoding='utf-8')
    return config_parser

def load_prompts(config_parser: configparser.RawConfigParser, dirs: dict, base_filename: str) -> Dict[str, str]:
    """
    Nạp tất cả các file prompt và ngữ cảnh, sau đó chèn ngữ cảnh vào prompt.

    Args:
        config_parser (configparser.RawConfigParser): Đối tượng parser đã đọc config.ini.
        dirs (dict): Dictionary chứa các đường dẫn thư mục làm việc.
        base_filename (str): Tên truyện đang xử lý, dùng để tìm file ngữ cảnh.

    Returns:
        Dict[str, str]: Dictionary chứa nội dung các prompt cuối cùng.
    """
    def load_context_file(filename_key: str, default_text: str) -> str:
        filename = config_parser.get('PROMPTS', filename_key)
        story_dir_path = dirs['input'] / base_filename if base_filename and (dirs['input'] / base_filename).is_dir() else None
        
        path_to_load = None
        if story_dir_path and (story_dir_path / filename).exists():
            path_to_load = story_dir_path / filename
        elif (Path('prompts') / filename).exists():
            path_to_load = Path('prompts') / filename
        
        if path_to_load and path_to_load.exists():
            content = path_to_load.read_text(encoding='utf-8').strip()
            if content:
                logging.info(f"📖 Đã nạp file ngữ cảnh: {path_to_load}")
                return content
        return default_text

    story_notes = load_context_file('story_notes_file', "Không có ghi chú đặc biệt.")
    style_sample = load_context_file('style_sample_file', "Không có văn phong mẫu nào được cung cấp.")

    prompts = {}
    prompt_dir = Path('prompts')
    prompt_keys_map = {
        'main': 'main_prompt_file',
        'retranslate': 'retranslate_prompt_file',
        'correction': 'correction_prompt_file',
        'consistency': 'consistency_check_prompt_file'
    }
    
    for key, config_key in prompt_keys_map.items():
        filename = config_parser.get('PROMPTS', config_key)
        file_path = prompt_dir / filename
        if file_path.exists():
            content = file_path.read_text(encoding='utf-8').strip()
            try:
                # Dùng dict để format an toàn hơn, bỏ qua các key không có
                prompts[key] = content.format(
                    custom_notes=story_notes,
                    glossary=story_notes,
                    style_sample=style_sample,
                    previous_chunk_context="{previous_chunk_context}",
                    language_name="{language_name}"
                )
            except KeyError:
                prompts[key] = content
            logging.info(f"✅ Đã nạp prompt '{key}' từ file: {filename}")
        else:
            prompts[key] = ""
            logging.warning(f"⚠️ Không tìm thấy file prompt '{filename}'")
    
    lang_code = config_parser.get('INPUT', 'INPUT_LANG')
    language_name = {"CN": "tiếng Trung", "EN": "tiếng Anh"}.get(lang_code.upper(), "")
    for key in prompts:
        if prompts[key] and '{language_name}' in prompts[key]: 
            prompts[key] = prompts[key].replace('{language_name}', language_name)

    return prompts