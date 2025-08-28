# main.py - v1.2.3
# Tác giả: Gemini & Narga
# Cập nhật: Thêm tính năng nạp file dịch mẫu (sample.txt) để AI học theo văn phong.

import os, sys, configparser, json, shutil, logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import smart_chunker, translator, file_writer

STATE_FILE = "translation_state.json"

def setup_logging(progress_dir: Path):
    # Thiết lập hệ thống logging
    progress_dir.mkdir(exist_ok=True, parents=True)
    log_filename = datetime.now().strftime('%Y-%m-%d_%H-%M') + '_translator.log'
    log_filepath = progress_dir / log_filename
    for handler in logging.root.handlers[:]: logging.root.removeHandler(handler)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ])
    logging.info(f"File log được lưu tại: {log_filepath}")

def load_prompts_from_files(config: configparser.RawConfigParser, story_notes: str, style_sample: str) -> dict:
    """
    Nạp nội dung từ các file prompt, đồng thời chèn ghi chú và văn phong mẫu.
    """
    prompts = {}
    prompt_dir = Path('prompts')
    prompt_keys = {
        'main': config.get('PROMPTS', 'main_prompt_file'),
        'retranslate': config.get('PROMPTS', 'retranslate_prompt_file'),
        'correction': config.get('PROMPTS', 'correction_prompt_file'),
        'consistency': config.get('PROMPTS', 'consistency_check_prompt_file')
    }
    for key, filename in prompt_keys.items():
        file_path = prompt_dir / filename
        if file_path.exists():
            content = file_path.read_text(encoding='utf-8').strip()
            # Chèn các nội dung động vào prompt
            content = content.format(
                custom_notes=story_notes,
                glossary=story_notes,
                style_sample=style_sample
            )
            prompts[key] = content
            logging.info(f"✅ Đã nạp prompt '{key}' từ file: {filename}")
        else:
            prompts[key] = ""
            logging.warning(f"⚠️ Không tìm thấy file prompt '{filename}' trong thư mục {prompt_dir}")
    return prompts

def load_config():
    """Đọc file cấu hình config.ini."""
    config = configparser.RawConfigParser(interpolation=None)
    if not os.path.exists('config.ini'): raise FileNotFoundError("Lỗi: Không tìm thấy file 'config.ini'.")
    config.read('config.ini', encoding='utf-8')
    return config

def get_language_name(lang_code: str) -> str:
    """Chuyển đổi mã ngôn ngữ thành tên đầy đủ."""
    return {"CN": "tiếng Trung", "EN": "tiếng Anh"}.get(lang_code.upper(), "không xác định")

def run_consistency_check(progress_dir: Path, api_manager, cache_manager, config_params: dict, prompts: dict):
    """Hàm điều phối bước kiểm tra và tinh chỉnh sự nhất quán."""
    logging.info("🔬 Bắt đầu bước kiểm tra và tinh chỉnh sự nhất quán...")
    chunk_files = sorted(progress_dir.glob("chunk_*.txt"))
    if not chunk_files:
        logging.warning("Không tìm thấy chunk nào để kiểm tra sự nhất quán.")
        return
    tasks = []
    for chunk_file in chunk_files:
        tasks.append((
            translator.consistency_check_chunk,
            (chunk_file, api_manager, cache_manager, prompts, config_params)
        ))
    with ThreadPoolExecutor(max_workers=config_params['max_workers']) as executor:
        list(tqdm(executor.map(lambda p: p[0](*p[1]), tasks), total=len(tasks), desc="🔬 Tinh chỉnh"))
    logging.info("✅ Hoàn tất bước kiểm tra sự nhất quán.")

def main():
    """Hàm chính điều phối toàn bộ quy trình."""
    try:
        config = load_config()
        input_dir = Path(config.get('DIRECTORIES', 'INPUT_DIR'))
        output_dir_base = Path(config.get('DIRECTORIES', 'OUTPUT_DIR'))
        cache_dir = Path(config.get('DIRECTORIES', 'CACHE_DIR'))
        progress_dir = Path(config.get('DIRECTORIES', 'PROGRESS_DIR'))

        for dir_path in [input_dir, output_dir_base, cache_dir, progress_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)
            
        config_params = {
            'api_keys': [key.strip() for key in config.get('API', 'GEMINI_API_KEYS').split(',') if key.strip()],
            'model_name': config.get('MODEL', 'MODEL'), 'input_lang': config.get('INPUT', 'INPUT_LANG'),
            'min_chars_per_chunk': config.getint('PROCESSING', 'MIN_CHARS_PER_CHUNK'),
            'max_chars_per_chunk': config.getint('PROCESSING', 'MAX_CHARS_PER_CHUNK'),
            'temperature': config.getfloat('PROCESSING', 'TEMPERATURE'),
            'request_delay': config.getfloat('PROCESSING', 'REQUEST_DELAY'),
            'max_refinement_attempts': config.getint('PROCESSING', 'MAX_REFINEMENT_ATTEMPTS'),
            'min_length_ratio': config.getfloat('PROCESSING', 'MIN_LENGTH_RATIO'),
            'max_length_ratio': config.getfloat('PROCESSING', 'MAX_LENGTH_RATIO'),
            'enable_consistency_check': config.getboolean('PROCESSING', 'ENABLE_CONSISTENCY_CHECK'),
            'enable_cache': config.getboolean('CACHE', 'ENABLE_CACHE'),
            'output_encoding': config.get('OUTPUT', 'ENCODING')
        }
    except Exception as e:
        print(f"CRITICAL: Lỗi nghiêm trọng khi đọc file config.ini: {e}"); sys.exit(1)
    
    setup_logging(progress_dir)
    logging.info("🚀 Bắt đầu chương trình Dịch Thuật Tiểu Thuyết v1.2.3 🚀")
    
    if not config_params['api_keys']:
        logging.critical("❌ Lỗi: Không có API key nào được cung cấp trong config.ini."); sys.exit(1)
    config_params['max_workers'] = len(config_params['api_keys'])
    logging.info(f"⚙️ Sử dụng {config_params['max_workers']} luồng dịch, tương ứng với số lượng API key.")

    state_file_path = progress_dir / STATE_FILE
    chunks_to_process, resume_mode, base_filename = [], False, ""

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
            logging.info("🗑️ Đã hủy phiên dịch cũ. Bắt đầu lại."); shutil.rmtree(progress_dir, ignore_errors=True); setup_logging(progress_dir)
    
    if not resume_mode:
        shutil.rmtree(progress_dir, ignore_errors=True); setup_logging(progress_dir)
        items_in_input = [f for f in input_dir.iterdir() if not f.name.startswith('.')]
        if not items_in_input: logging.warning(f"📁 Không tìm thấy file hay thư mục nào trong thư mục '{input_dir}'."); sys.exit(0)
        target_path = items_in_input[0]
        all_chunks = []
        if target_path.is_file():
            base_filename = target_path.stem
            original_text = smart_chunker.read_and_detect_encoding(str(target_path))
            if not original_text or not original_text.strip(): logging.error(f"❌ Nội dung file rỗng."); sys.exit(1)
            all_chunks = smart_chunker.process_text_for_chunking(original_text, config_params['min_chars_per_chunk'], config_params['max_chars_per_chunk'])
        elif target_path.is_dir():
            base_filename = target_path.name
            source_files = sorted(target_path.glob('*.txt'))
            if not source_files: logging.error(f"❌ Không tìm thấy file .txt nào trong thư mục '{target_path.name}'."); sys.exit(1)
            for file_path in source_files:
                content = smart_chunker.read_and_detect_encoding(str(file_path))
                if content and content.strip():
                    chunks_from_file = smart_chunker.process_text_for_chunking(content, config_params['min_chars_per_chunk'], config_params['max_chars_per_chunk'])
                    all_chunks.extend(chunks_from_file)
        
        chunks_to_process = list(enumerate(all_chunks))
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump({"base_filename": base_filename, "total_chunks": len(all_chunks),
                       "completed_indices": [], "all_chunks": all_chunks}, f, ensure_ascii=False, indent=2)

    # === NẠP GHI CHÚ VÀ VĂN PHONG MẪU ===
    notes_filename = config.get('PROMPTS', 'story_notes_file')
    sample_filename = config.get('PROMPTS', 'style_sample_file')
    
    # Xác định đường dẫn ưu tiên: trong thư mục truyện trước, sau đó đến thư mục prompts
    story_dir_path = input_dir / base_filename if (input_dir / base_filename).is_dir() else None
    
    def load_context_file(filename, default_text):
        if story_dir_path and (story_dir_path / filename).exists():
            path_to_load = story_dir_path / filename
        else:
            path_to_load = Path('prompts') / filename

        if path_to_load.exists():
            content = path_to_load.read_text(encoding='utf-8').strip()
            if content:
                logging.info(f"📖 Đã nạp file ngữ cảnh: {path_to_load}")
                return content
        return default_text

    story_notes = load_context_file(notes_filename, "Không có ghi chú đặc biệt.")
    style_sample = load_context_file(sample_filename, "Không có văn phong mẫu nào được cung cấp.")
    
    prompts = load_prompts_from_files(config, story_notes, style_sample)
    if not prompts.get('main'):
         logging.critical("❌ Lỗi: Main prompt không được nạp."); sys.exit(1)
    
    language_name = get_language_name(config_params['input_lang'])
    for key in prompts:
        if prompts[key] and '{language_name}' in prompts[key]: 
            prompts[key] = prompts[key].format(language_name=language_name)

    # Bắt đầu quá trình dịch
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
    if config_params['enable_consistency_check'] and story_notes != "Không có ghi chú đặc biệt.":
        api_manager = translator.ApiManager(config_params['api_keys'])
        cache_manager = translator.TranslationCache(str(cache_dir), config_params['enable_cache'])
        run_consistency_check(progress_dir, api_manager, cache_manager, config_params, prompts)
    else:
        logging.info("ℹ️ Bỏ qua bước kiểm tra sự nhất quán.")

    # Ghép file và hoàn tất
    output_dir = output_dir_base / base_filename
    file_writer.assemble_final_files(progress_dir=str(progress_dir), output_dir=str(output_dir),
        encoding=config_params['output_encoding'])
    
    # Lưu trữ cache và dọn dẹp
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
    
    if not Path(output_dir / 'parts').exists():
         try:
            shutil.rmtree(progress_dir)
            logging.info(f"🗑️ Đã xóa thư mục tạm '{progress_dir}'.")
         except Exception as e:
            logging.warning(f"⚠️ Lỗi khi xóa thư mục tạm '{progress_dir}': {e}")

    logging.info("🎉 Dịch thuật hoàn tất! 🎉")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("\n🛑 Chương trình đã bị dừng. Trạng thái đã được lưu."); sys.exit(0)