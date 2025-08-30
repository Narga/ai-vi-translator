# src/workflow.py - v2.0.0
# Tác giả: Narga
# Chức năng: Module điều phối chính, chứa logic xử lý từ đầu đến cuối:
# resume, chia chunk, dịch, kiểm tra và ghép file.

import json
import logging
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from tqdm import tqdm
from typing import Dict, Any

# Import các module cùng cấp trong src
from . import smart_chunker, translator, file_writer
from .configuration import load_prompts

STATE_FILE = "translation_state.json"

def run_consistency_check(progress_dir: Path, api_manager, cache_manager, config_params: Dict[str, Any], prompts: Dict[str, str]):
    """
    Hàm điều phối bước kiểm tra và tinh chỉnh sự nhất quán sau khi dịch.
    Sử dụng đa luồng để tăng tốc độ xử lý.
    """
    logging.info("🔬 Bắt đầu bước kiểm tra và tinh chỉnh sự nhất quán...")
    chunk_files = sorted(progress_dir.glob("chunk_*.txt"))
    if not chunk_files:
        logging.warning("Không tìm thấy chunk nào để kiểm tra sự nhất quán.")
        return
    
    tasks = [(translator.consistency_check_chunk, (chunk_file, api_manager, cache_manager, prompts, config_params)) for chunk_file in chunk_files]
    
    with ThreadPoolExecutor(max_workers=config_params['max_workers']) as executor:
        list(tqdm(executor.map(lambda p: p[0](*p[1]), tasks), total=len(tasks), desc="🔬 Tinh chỉnh"))
    
    logging.info("✅ Hoàn tất bước kiểm tra sự nhất quán.")

def run_translation_workflow(config_parser, dirs: Dict[str, Path]):
    """
    Hàm điều phối toàn bộ quy trình dịch thuật.
    """
    progress_dir = dirs['progress']
    input_dir = dirs['input']
    output_dir_base = dirs['output_base']
    cache_dir = dirs['cache']
    
    # Lấy các tham số từ parser
    config_params = {
        'api_keys': [key.strip() for key in config_parser.get('API', 'GEMINI_API_KEYS').split(',') if key.strip()],
        'model_name': config_parser.get('MODEL', 'MODEL'),
        'qa_model': config_parser.get('MODEL', 'QA_MODEL'),
        'consistency_model': config_parser.get('MODEL', 'CONSISTENCY_MODEL'),
        'input_lang': config_parser.get('INPUT', 'INPUT_LANG'),
        'min_chars_per_chunk': config_parser.getint('PROCESSING', 'MIN_CHARS_PER_CHUNK'),
        'max_chars_per_chunk': config_parser.getint('PROCESSING', 'MAX_CHARS_PER_CHUNK'),
        'temperature': config_parser.getfloat('PROCESSING', 'TEMPERATURE'),
        'request_delay': config_parser.getfloat('PROCESSING', 'REQUEST_DELAY'),
        'max_refinement_attempts': config_parser.getint('PROCESSING', 'MAX_REFINEMENT_ATTEMPTS'),
        'min_length_ratio': config_parser.getfloat('PROCESSING', 'MIN_LENGTH_RATIO'),
        'max_length_ratio': config_parser.getfloat('PROCESSING', 'MAX_LENGTH_RATIO'),
        'enable_consistency_check': config_parser.getboolean('PROCESSING', 'ENABLE_CONSISTENCY_CHECK'),
        'enable_cache': config_parser.getboolean('CACHE', 'ENABLE_CACHE'),
        'output_encoding': config_parser.get('OUTPUT', 'ENCODING')
    }
    config_params['max_workers'] = len(config_params['api_keys'])
    logging.info(f"⚙️ Sử dụng {config_params['max_workers']} luồng dịch, tương ứng với số lượng API key.")

    state_file_path = progress_dir / STATE_FILE
    chunks_to_process, resume_mode, base_filename = [], False, ""

    # Xử lý resume
    if state_file_path.exists():
        logging.info("🔍 Phát hiện một phiên dịch đang dang dở.")
        action = input("   Bạn có muốn tiếp tục không? (y/n): ").lower()
        if action == 'y':
            resume_mode = True
            with open(state_file_path, 'r', encoding='utf-8') as f: state = json.load(f)
            base_filename, all_chunks = state['base_filename'], state['all_chunks']
            completed_indices = set(state['completed_indices'])
            for i, chunk in enumerate(all_chunks):
                if i not in completed_indices: chunks_to_process.append((i, chunk))
            logging.info(f"✅ Tiếp tục dịch '{base_filename}'. Còn lại {len(chunks_to_process)}/{len(all_chunks)} chunks.")
        else:
            logging.info("🗑️ Đã hủy phiên dịch cũ. Bắt đầu lại."); shutil.rmtree(progress_dir)
    
    # Chuẩn bị cho phiên dịch mới
    if not resume_mode:
        if progress_dir.exists(): shutil.rmtree(progress_dir)
        progress_dir.mkdir()
        items_in_input = [f for f in input_dir.iterdir() if not f.name.startswith('.')]
        if not items_in_input: logging.warning(f"📁 Không tìm thấy file hay thư mục nào trong thư mục '{input_dir}'."); return
        target_path = items_in_input[0]
        all_chunks = []
        if target_path.is_file():
            base_filename = target_path.stem
            original_text = smart_chunker.read_and_detect_encoding(str(target_path))
            if not original_text or not original_text.strip(): logging.error(f"❌ Nội dung file rỗng."); return
            all_chunks = smart_chunker.process_text_for_chunking(original_text, config_params['min_chars_per_chunk'], config_params['max_chars_per_chunk'])
        elif target_path.is_dir():
            base_filename = target_path.name
            source_files = sorted(target_path.glob('*.txt'))
            if not source_files: logging.error(f"❌ Không tìm thấy file .txt nào trong thư mục '{target_path.name}'."); return
            for file_path in source_files:
                content = smart_chunker.read_and_detect_encoding(str(file_path))
                if content and content.strip():
                    chunks_from_file = smart_chunker.process_text_for_chunking(content, config_params['min_chars_per_chunk'], config_params['max_chars_per_chunk'])
                    all_chunks.extend(chunks_from_file)
        
        chunks_to_process = list(enumerate(all_chunks))
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump({"base_filename": base_filename, "total_chunks": len(all_chunks),
                       "completed_indices": [], "all_chunks": all_chunks}, f, ensure_ascii=False, indent=2)

    # Nạp prompts và ngữ cảnh
    config = {'parser': config_parser, 'base_filename': base_filename}
    prompts = load_prompts(config_parser, dirs, base_filename)
    
    if not prompts.get('main'):
         logging.critical("❌ Lỗi: Main prompt không được nạp."); return

    # Bắt đầu dịch
    if chunks_to_process:
        api_manager = translator.ApiManager(config_params['api_keys'])
        cache_manager = translator.TranslationCache(str(cache_dir), config_params['enable_cache'])
        with ThreadPoolExecutor(max_workers=config_params['max_workers']) as executor:
            future_to_index = {
                executor.submit(
                    translator.robust_translate,
                    chunk, api_manager, cache_manager, prompts, config_params
                ): index for index, chunk in chunks_to_process
            }
            progress = tqdm(as_completed(future_to_index), total=len(chunks_to_process), desc="🤖 Đang dịch")
            for future in progress:
                index = future_to_index[future]
                try:
                    result, status = future.result()
                    if status == "success":
                        file_writer.save_progress_chunk(result, index, str(progress_dir), config_params['output_encoding'])
                        with open(state_file_path, 'r+', encoding='utf-8') as f:
                            state = json.load(f)
                            if index not in state['completed_indices']: state['completed_indices'].append(index)
                            f.seek(0); json.dump(state, f, ensure_ascii=False, indent=2); f.truncate()
                        progress.set_postfix_str(f"Chunk {index + 1} ✅")
                    elif status == "all_keys_failed":
                        logging.critical("🚨 Tất cả API key đã hết quota."); executor.shutdown(wait=False, cancel_futures=True); break
                    else: 
                        logging.error(f"Chunk {index + 1} thất bại."); 
                        file_writer.save_progress_chunk(result, index, str(progress_dir), config_params['output_encoding'])
                        progress.set_postfix_str(f"Chunk {index + 1} ❌")
                except Exception as exc:
                    logging.error(f"Lỗi khi xử lý chunk {index + 1}: {exc}"); progress.set_postfix_str(f"Chunk {index + 1} ❌")
    
    # Chạy bước kiểm tra sự nhất quán
    if config_params['enable_consistency_check'] and "Không có ghi chú đặc biệt." not in prompts.get('consistency', ''):
        api_manager = translator.ApiManager(config_params['api_keys'])
        cache_manager = translator.TranslationCache(str(cache_dir), config_params['enable_cache'])
        run_consistency_check(progress_dir, api_manager, cache_manager, config_params, prompts)
    else:
        logging.info("ℹ️ Bỏ qua bước kiểm tra sự nhất quán.")

    # Ghép file và hoàn tất
    output_dir = output_dir_base / base_filename
    file_writer.assemble_final_files(progress_dir=str(progress_dir), output_dir=str(output_dir),
        encoding=config_params['output_encoding'])
    
    # Dọn dẹp và lưu trữ
    logging.info("🧹 Bắt đầu dọn dẹp và lưu trữ cuối cùng...")
    try:
        cache_files = [f for f in cache_dir.iterdir() if f.is_file()]
        if cache_files:
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
            archive_dir = cache_dir / f"bin_{timestamp}"
            archive_dir.mkdir()
            for f in cache_files: shutil.move(str(f), str(archive_dir))
            logging.info(f"📦 Đã lưu trữ {len(cache_files)} file cache vào '{archive_dir.name}'")
    except Exception as e:
        logging.warning(f"⚠️ Lỗi khi lưu trữ cache: {e}")
    
    # Chỉ xóa thư mục progress nếu các chunks đã được chuyển đi
    if (output_dir / 'parts').exists():
         try:
            shutil.rmtree(progress_dir)
            logging.info(f"🗑️ Đã xóa thư mục tạm '{progress_dir}'.")
         except Exception as e:
            # Sửa lỗi SyntaxError: f-string
            logging.warning(f"⚠️ Lỗi khi xóa thư mục tạm '{progress_dir}': {e}")

    logging.info("🎉 Dịch thuật hoàn tất! 🎉")