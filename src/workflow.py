# src/workflow.py - v2.4.2
# Tác giả: Narga
# Chức năng: Module điều phối chính, chứa logic xử lý từ đầu đến cuối.
#            API keys được nạp từ file API.txt riêng biệt.

import json
import logging
import shutil
import time
import sys
import select
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from tqdm import tqdm
from typing import Dict, Any

from . import smart_chunker, translator, file_writer
from .configuration import load_prompts, load_api_keys
from .emergency_stop import check_emergency_stop, reset_emergency_stop
from .monitoring import HealthMonitor
from .statistics import TranslationStatistics, print_api_status
from .text_normalizer import TextNormalizer, detect_source_type

STATE_FILE = "translation_state.json"


def input_with_timeout(prompt: str, timeout: int = 5, default: str = 'y') -> str:
    """
    Nhận input từ người dùng với thời gian chờ tối đa.
    
    Nếu người dùng không nhập trong thời gian quy định,
    tự động trả về giá trị mặc định.
    
    Args:
        prompt (str): Thông điệp hiển thị cho người dùng
        timeout (int): Thời gian chờ tối đa (giây)
        default (str): Giá trị mặc định nếu timeout
        
    Returns:
        str: Giá trị người dùng nhập hoặc giá trị mặc định
    """
    print(prompt, end='', flush=True)
    
    # Đếm ngược
    for i in range(timeout, 0, -1):
        print(f"\r{prompt} ({i}s) ", end='', flush=True)
        
        # Kiểm tra input trong 1 giây
        if sys.platform == 'win32':
            import msvcrt
            start_time = time.time()
            while time.time() - start_time < 1:
                if msvcrt.kbhit():
                    # Đọc tất cả ký tự đã nhập
                    result = msvcrt.getch().decode('utf-8').strip().lower()
                    print()  # Xuống dòng
                    return result
                time.sleep(0.1)
        else:
            # Unix/Linux/MacOS
            ready, _, _ = select.select([sys.stdin], [], [], 1)
            if ready:
                result = sys.stdin.readline().strip().lower()
                return result
    
    print(f"\r{prompt} Tự động chọn '{default}'")
    return default


def run_consistency_check(progress_dir: Path, api_manager, cache_manager, 
                          config_params: Dict[str, Any], prompts: Dict[str, str], 
                          normalizer: TextNormalizer) -> None:
    """
    Điều phối bước kiểm tra và tinh chỉnh sự nhất quán sau khi dịch.
    
    Args:
        progress_dir (Path): Thư mục chứa các chunk đã dịch
        api_manager: Trình quản lý API keys
        cache_manager: Trình quản lý cache
        config_params (Dict): Tham số cấu hình
        prompts (Dict): Dictionary chứa các prompt
        normalizer (TextNormalizer): Đối tượng chuẩn hóa văn bản
    """
    logging.info("🔬 Bắt đầu bước kiểm tra và tinh chỉnh sự nhất quán...")
    
    if check_emergency_stop():
        return
    
    chunk_files = sorted(progress_dir.glob("chunk_*.txt"))
    
    if not chunk_files:
        logging.warning("Không tìm thấy chunk nào để kiểm tra sự nhất quán.")
        return
    
    # Tạo danh sách tác vụ với normalizer
    tasks = [
        (translator.consistency_check_chunk, 
         (chunk_file, api_manager, cache_manager, prompts, config_params, normalizer)) 
        for chunk_file in chunk_files
    ]
    
    with ThreadPoolExecutor(max_workers=config_params['max_workers']) as executor:
        list(tqdm(
            executor.map(lambda p: p[0](*p[1]), tasks), 
            total=len(tasks), 
            desc="🔬 Tinh chỉnh"
        ))
    
    logging.info("✅ Hoàn tất bước kiểm tra sự nhất quán.")


def run_translation_workflow(config_parser, dirs: Dict[str, Path]) -> None:
    """
    Hàm điều phối toàn bộ quy trình dịch thuật.
    
    Args:
        config_parser: Đối tượng ConfigParser chứa cấu hình
        dirs (Dict[str, Path]): Dictionary chứa các đường dẫn thư mục làm việc
    """
    reset_emergency_stop()
    
    # Khởi tạo các module giám sát và thống kê
    health_monitor = HealthMonitor()
    statistics = TranslationStatistics()
    
    # Các đường dẫn thư mục làm việc
    progress_dir = dirs['progress']
    input_dir = dirs['input']
    output_dir_base = dirs['output_base']
    cache_dir = dirs['cache']
    
    # Nạp API keys từ file API.txt
    try:
        api_keys = load_api_keys('API.txt')
    except (FileNotFoundError, ValueError) as e:
        logging.critical(f"❌ {e}")
        return
    
    # Tải các tham số cấu hình
    config_params = {
        'api_keys': api_keys,
        'model_name': config_parser.get('MODEL', 'MODEL'),
        'qa_model': config_parser.get('MODEL', 'QA_MODEL'),
        'consistency_model': config_parser.get('MODEL', 'CONSISTENCY_MODEL'),
        'min_chars_per_chunk': config_parser.getint('PROCESSING', 'MIN_CHARS_PER_CHUNK'),
        'max_chars_per_chunk': config_parser.getint('PROCESSING', 'MAX_CHARS_PER_CHUNK'),
        'temperature': config_parser.getfloat('PROCESSING', 'TEMPERATURE'),
        'request_delay': config_parser.getfloat('PROCESSING', 'REQUEST_DELAY'),
        'max_refinement_attempts': config_parser.getint('PROCESSING', 'MAX_REFINEMENT_ATTEMPTS'),
        'min_length_ratio': config_parser.getfloat('PROCESSING', 'MIN_LENGTH_RATIO'),
        'max_length_ratio': config_parser.getfloat('PROCESSING', 'MAX_LENGTH_RATIO'),
        'enable_consistency_check': config_parser.getboolean('PROCESSING', 'ENABLE_CONSISTENCY_CHECK'),
        'context_char_count': config_parser.getint('PROCESSING', 'CONTEXT_CHAR_COUNT', fallback=0),
        'archive_dir_name': config_parser.get('DIRECTORIES', 'ARCHIVE_DIR_NAME', fallback='_archive'),
        'enable_cache': config_parser.getboolean('CACHE', 'ENABLE_CACHE'),
        'output_encoding': config_parser.get('OUTPUT', 'ENCODING')
    }
    
    config_params['max_workers'] = len(config_params['api_keys'])
    
    state_file_path = progress_dir / STATE_FILE
    chunks_to_process, resume_mode, base_filename = [], False, ""
    all_chunks = []
    source_file_path = None
    
    # ===== XỬ LÝ RESUME HOẶC BẮT ĐẦU MỚI =====
    if state_file_path.exists():
        logging.info("🔍 Phát hiện một phiên dịch đang dang dở.")
        action = input(" Bạn có muốn tiếp tục không? (y/n): ").lower()
        
        if action == 'y':
            resume_mode = True
            with open(state_file_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
            
            base_filename = state['base_filename']
            all_chunks = state['all_chunks']
            completed_indices = set(state['completed_indices'])
            source_file_path = Path(state.get('source_file_path', '')) if state.get('source_file_path') else None
            
            # Lọc ra các chunk chưa hoàn thành
            for i, chunk in enumerate(all_chunks):
                if i not in completed_indices:
                    chunks_to_process.append((i, chunk))
            
            logging.info(f"✅ Tiếp tục dịch '{base_filename}'. Còn lại {len(chunks_to_process)}/{len(all_chunks)} chunks.")
    
    if not resume_mode:
        # Xóa thư mục progress cũ và tạo mới
        if progress_dir.exists():
            shutil.rmtree(progress_dir)
        progress_dir.mkdir()
        
        # Xử lý cache cũ với đếm ngược tự động
        if cache_dir.exists() and any(cache_dir.iterdir()):
            delete_cache = input_with_timeout(
                f" Phát hiện cache cũ trong '{cache_dir}'. Bạn có muốn xóa để bắt đầu lại hoàn toàn không? (y/n):",
                timeout=5,
                default='y'
            )
            
            if delete_cache == 'y':
                shutil.rmtree(cache_dir)
                cache_dir.mkdir()
                logging.info("🗑️  Đã xóa cache cũ.")
        
        # Tìm file/thư mục nguồn
        archive_dir_name = config_params['archive_dir_name']
        items_in_input = [
            f for f in input_dir.iterdir() 
            if not f.name.startswith('.') and f.name != archive_dir_name
        ]
        
        if not items_in_input:
            logging.warning(f"📁 Không tìm thấy file/thư mục nào trong '{input_dir}' (đã bỏ qua '{archive_dir_name}').")
            return
        
        target_path = items_in_input[0]
        
        # Xử lý file đơn
        if target_path.is_file():
            base_filename = target_path.stem
            source_file_path = target_path
            original_text = smart_chunker.read_and_detect_encoding(str(target_path))
            
            if not original_text or not original_text.strip():
                logging.error(f"❌ Nội dung file rỗng.")
                return
            
            all_chunks = smart_chunker.process_text_for_chunking(
                original_text,
                config_params['min_chars_per_chunk'],
                config_params['max_chars_per_chunk']
            )
        
        # Xử lý thư mục chứa nhiều file
        elif target_path.is_dir():
            base_filename = target_path.name
            source_files = sorted(target_path.glob('*.txt'))
            
            if not source_files:
                logging.error(f"❌ Không tìm thấy file .txt nào trong '{target_path.name}'.")
                return
            
            # Xử lý từng file trong thư mục
            for file_path in source_files:
                if check_emergency_stop():
                    break
                
                content = smart_chunker.read_and_detect_encoding(str(file_path))
                
                if content and content.strip():
                    chunks_from_file = smart_chunker.process_text_for_chunking(
                        content,
                        config_params['min_chars_per_chunk'],
                        config_params['max_chars_per_chunk']
                    )
                    all_chunks.extend(chunks_from_file)
        
        chunks_to_process = list(enumerate(all_chunks))
        
        # Lưu trạng thái ban đầu
        with open(state_file_path, 'w', encoding='utf-8') as f:
            json.dump({
                "base_filename": base_filename,
                "total_chunks": len(all_chunks),
                "completed_indices": [],
                "all_chunks": all_chunks,
                "source_file_path": str(source_file_path) if source_file_path else ""
            }, f, ensure_ascii=False, indent=2)
    
    if check_emergency_stop():
        logging.warning("Dừng lại trước khi bắt đầu dịch.")
        return
    
    # ===== TẢI PROMPTS VÀ KHỞI TẠO CÁC MODULE =====
    prompts = load_prompts(config_parser, dirs, base_filename)
    
    if not prompts.get('main'):
        logging.critical("❌ Lỗi: Main prompt không được nạp.")
        return
    
    # Khởi tạo TextNormalizer
    is_text_source = detect_source_type(source_file_path) if source_file_path else True
    normalizer = TextNormalizer(is_text_source=is_text_source)
    
    # ===== QUÁ TRÌNH DỊCH CHÍNH =====
    if chunks_to_process:
        api_manager = translator.ApiManager(config_params['api_keys'])
        cache_manager = translator.TranslationCache(str(cache_dir), config_params['enable_cache'])
        
        logging.info(f"🌐 Bắt đầu dịch {len(chunks_to_process)} chunk (chế độ tuần tự để nối ngữ cảnh)...")
        
        last_translated_text = ""
        progress_bar = tqdm(chunks_to_process, desc="🤖 Đang dịch tuần tự")
        
        for index, chunk in progress_bar:
            if check_emergency_stop():
                logging.warning("Quy trình dịch bị dừng bởi tín hiệu khẩn cấp.")
                break
            
            # Chuẩn bị ngữ cảnh
            context_to_pass = ""
            if config_params['context_char_count'] > 0 and last_translated_text:
                context_to_pass = last_translated_text[-config_params['context_char_count']:]
            
            try:
                result, status, api_key_used = translator.robust_translate(
                    chunk, api_manager, cache_manager, prompts, 
                    config_params, context_to_pass, normalizer
                )
                
                # Ghi nhận thống kê
                statistics.add_chunk_result(index, chunk, status, api_key_used)
                
                if status == "success":
                    last_translated_text = result
                    file_writer.save_progress_chunk(
                        result, index, str(progress_dir), 
                        config_params['output_encoding']
                    )
                    
                    # Cập nhật state file
                    with open(state_file_path, 'r+', encoding='utf-8') as f:
                        state = json.load(f)
                        if index not in state['completed_indices']:
                            state['completed_indices'].append(index)
                        f.seek(0)
                        json.dump(state, f, ensure_ascii=False, indent=2)
                        f.truncate()
                    
                    progress_bar.set_postfix_str(f"Chunk {index + 1} ✅")
                
                elif status == "all_keys_exhausted":
                    logging.critical("🚨 Tất cả API key đã hết quota hoặc gặp lỗi không thể khôi phục.")
                    logging.info("💾 Đã lưu trạng thái. Bạn có thể chạy lại chương trình sau khi quota được làm mới.")
                    break
                
                else:
                    logging.error(f"Chunk {index + 1} thất bại với trạng thái: {status}")
                    file_writer.save_progress_chunk(
                        result, index, str(progress_dir), 
                        config_params['output_encoding']
                    )
                    progress_bar.set_postfix_str(f"Chunk {index + 1} ❌")
            
            except Exception as exc:
                logging.error(f"Lỗi khi xử lý chunk {index + 1}: {exc}")
                statistics.add_chunk_result(index, chunk, "failed", "unknown")
        
        # Cập nhật tiến trình cho HealthMonitor
        completed_count = len(json.load(open(state_file_path))['completed_indices']) if state_file_path.exists() else 0
        health_monitor.update_progress(completed_count)
        
        # In trạng thái API
        print_api_status(api_manager)
    
    # ===== KIỂM TRA SỰ NHẤT QUÁN =====
    if check_emergency_stop():
        logging.warning("Dừng lại trước bước kiểm tra sự nhất quán.")
        return
    
    if config_params['enable_consistency_check'] and "Không có ghi chú đặc biệt." not in prompts.get('consistency', ''):
        api_manager = translator.ApiManager(config_params['api_keys'])
        cache_manager = translator.TranslationCache(str(cache_dir), config_params['enable_cache'])
        run_consistency_check(progress_dir, api_manager, cache_manager, config_params, prompts, normalizer)
    else:
        logging.info("ℹ️  Bỏ qua bước kiểm tra sự nhất quán.")
    
    # ===== GHÉP FILE VÀ HOÀN TẤT =====
    output_dir = output_dir_base / base_filename
    file_writer.assemble_final_files(
        progress_dir=str(progress_dir),
        output_dir=str(output_dir),
        encoding=config_params['output_encoding']
    )
    
    # ===== DỌN DẸP VÀ LƯU TRỮ =====
    logging.info("🧹 Bắt đầu dọn dẹp và lưu trữ cuối cùng...")
    
    try:
        cache_files = [f for f in cache_dir.iterdir() if f.is_file()]
        if cache_files:
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
            archive_dir = cache_dir / f"bin_{timestamp}"
            archive_dir.mkdir()
            
            for f in cache_files:
                shutil.move(str(f), str(archive_dir))
            
            logging.info(f"📦 Đã lưu trữ {len(cache_files)} file cache vào '{archive_dir.name}'")
    
    except Exception as e:
        logging.warning(f"⚠️  Lỗi khi lưu trữ cache: {e}")
    
    # Xóa thư mục tạm nếu đã ghép file thành công
    if (output_dir / 'parts').exists():
        try:
            shutil.rmtree(progress_dir)
            logging.info(f"🗑️  Đã xóa thư mục tạm '{progress_dir}'.")
        except Exception as e:
            logging.warning(f"⚠️  Lỗi khi xóa thư mục tạm '{progress_dir}': {e}")
    
    # ===== IN THỐNG KÊ CUỐI CÙNG =====
    statistics.print_summary()
    
    logging.info("🎉 Dịch thuật hoàn tất! 🎉")
