# main.py - v1.2
# Tác giả: Gemini & Narga
# Cập nhật: Tích hợp và gọi thuật toán cắt file thông minh mới.

import os, sys, configparser, json, shutil, logging
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

import smart_chunker, translator, file_writer

STATE_FILE = "translation_state.json"

def setup_logging(progress_dir: Path):
    """Thiết lập hệ thống logging để ghi lại mọi hoạt động ra file và console."""
    progress_dir.mkdir(exist_ok=True)
    log_filename = datetime.now().strftime('%Y-%m-%d_%H-%M') + '_translator.log'
    log_filepath = progress_dir / log_filename
    for handler in logging.root.handlers[:]: logging.root.removeHandler(handler)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_filepath, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ])
    logging.info(f"File log được lưu tại: {log_filepath}")

def load_prompts_from_files(config: configparser.RawConfigParser, story_specific_notes: str) -> dict:
    """Nạp nội dung từ các file prompt được định nghĩa trong config.ini."""
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
            if '{custom_notes}' in content: prompts[key] = content.format(custom_notes=story_specific_notes)
            elif '{glossary}' in content: prompts[key] = content.format(glossary=story_specific_notes)
            else: prompts[key] = content
            logging.info(f"✅ Đã nạp prompt '{key}' từ file: {filename}")
        else:
            prompts[key] = ""
            logging.warning(f"⚠️ Không tìm thấy file prompt '{filename}' trong thư mục {prompt_dir}")
    return prompts

def load_config():
    """Đọc file cấu hình config.ini một cách an toàn."""
    config = configparser.RawConfigParser(interpolation=None)
    if not os.path.exists('config.ini'): raise FileNotFoundError("Lỗi: Không tìm thấy file 'config.ini'.")
    config.read('config.ini', encoding='utf-8')
    return config

def get_language_name(lang_code: str) -> str:
    """Chuyển đổi mã ngôn ngữ (CN, EN) thành tên đầy đủ."""
    return {"CN": "tiếng Trung", "EN": "tiếng Anh"}.get(lang_code.upper(), "không xác định")

def run_consistency_check(progress_dir: Path, api_manager, cache_manager, config_params: dict, prompts: dict):
    """Hàm điều phối bước kiểm tra và tinh chỉnh sự nhất quán sau khi dịch."""
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
    progress_dir = Path('workspace/progress'); setup_logging(progress_dir)
    logging.info("🚀 Bắt đầu chương trình Dịch Thuật Tiểu Thuyết v1.2 🚀")
    
    try:
        config = load_config()
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
            'cache_dir': config.get('CACHE', 'CACHE_DIR'),
            'output_encoding': config.get('OUTPUT', 'ENCODING'), 
            'create_combined': config.getboolean('OUTPUT', 'CREATE_COMBINED')
        }
    except Exception as e:
        logging.critical(f"❌ Lỗi nghiêm trọng khi đọc file config.ini: {e}"); sys.exit(1)

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
        input_dir = Path('input')
        items_in_input = [f for f in input_dir.iterdir() if not f.name.startswith('.')]
        if not items_in_input: logging.warning("📁 Không tìm thấy file hay thư mục nào trong thư mục 'input'."); sys.exit(0)
        
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

    # Nạp Ghi chú và Prompts
    notes_filename = config.get('PROMPTS', 'story_notes_file', fallback='notes.txt')
    notes_path = Path('input') / base_filename / notes_filename if (Path('input') / base_filename).is_dir() else Path('prompts') / notes_filename
    story_notes = "Không có ghi chú đặc biệt."
    if notes_path.exists():
        story_notes_content = notes_path.read_text(encoding='utf-8').strip()
        if story_notes_content:
            story_notes = story_notes_content
            logging.info(f"📖 Đã nạp ghi chú cho truyện từ: {notes_path}")
    else:
        logging.info(f"ℹ️ Không tìm thấy file ghi chú '{notes_filename}'.")
    
    prompts = load_prompts_from_files(config, story_notes)
    if not prompts.get('main'):
         logging.critical("❌ Lỗi: Main prompt không được nạp."); sys.exit(1)
    
    language_name = get_language_name(config_params['input_lang'])
    for key in prompts:
        if prompts[key] and '{language_name}' in prompts[key]: 
            prompts[key] = prompts[key].format(language_name=language_name)

    # Bắt đầu quá trình dịch
    if chunks_to_process:
        api_manager = translator.ApiManager(config_params['api_keys'])
        cache_manager = translator.TranslationCache(config_params['cache_dir'], config_params['enable_cache'])
        logging.info(f"🌐 Bắt đầu dịch {len(chunks_to_process)} chunk...")
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
                        logging.critical("🚨 Tất cả API key đã hết quota. Dừng chương trình."); executor.shutdown(wait=False, cancel_futures=True); break
                    else: # "failed"
                        logging.error(f"Chunk {index + 1} thất bại, đã lưu bản dịch lỗi."); 
                        file_writer.save_progress_chunk(result, index, str(progress_dir), config_params['output_encoding'])
                        progress.set_postfix_str(f"Chunk {index + 1} ❌")
                except Exception as exc:
                    logging.error(f"Lỗi khi xử lý chunk {index + 1}: {exc}"); progress.set_postfix_str(f"Chunk {index + 1} ❌")
    
    # Chạy bước kiểm tra sự nhất quán sau khi dịch xong
    if config_params['enable_consistency_check'] and story_notes != "Không có ghi chú đặc biệt.":
        api_manager = translator.ApiManager(config_params['api_keys'])
        cache_manager = translator.TranslationCache(config_params['cache_dir'], config_params['enable_cache'])
        run_consistency_check(progress_dir, api_manager, cache_manager, config_params, prompts)
    else:
        logging.info("ℹ️ Bỏ qua bước kiểm tra sự nhất quán (đã tắt hoặc không có file ghi chú).")

    # Ghép file và hoàn tất
    output_dir = Path('output') / base_filename
    file_writer.assemble_final_files(progress_dir=str(progress_dir), output_dir=str(output_dir), base_filename=base_filename,
        encoding=config_params['output_encoding'], create_combined=config_params['create_combined'])
    
    logging.info("🧹 Dọn dẹp file tạm..."); shutil.rmtree(progress_dir, ignore_errors=True)
    logging.info("🎉 Dịch thuật hoàn tất! 🎉")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.warning("\n🛑 Chương trình đã bị dừng. Trạng thái đã được lưu."); sys.exit(0)