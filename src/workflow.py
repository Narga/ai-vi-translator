# src/workflow.py - v2.6.1
# Tác giả: Narga
# Chức năng: Module điều phối chính, chứa logic xử lý từ đầu đến cuối.
#            API keys được nạp từ file API.txt riêng biệt.
#            Hỗ trợ auto-retry chunks lỗi và verification mode.

import json
import logging
import shutil
import time
import sys
import select
from pathlib import Path
from datetime import datetime
from tqdm import tqdm
from typing import Dict, Any

from . import smart_chunker, translator, file_writer
from .configuration import load_prompts, load_api_keys
from .emergency_stop import check_emergency_stop, reset_emergency_stop
from .monitoring import HealthMonitor
from .statistics import TranslationStatistics, print_api_status
from .text_normalizer import TextNormalizer, detect_source_type
from .chinese_detector import find_chinese_files, find_chinese_chunks
from .workflow_helpers import (
    retry_failed_chunks,
    verify_existing_translation,
    run_consistency_check
)

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
                    result = msvcrt.getch().decode('utf-8').strip().lower()
                    print()
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


def run_translation_workflow(config_parser, dirs: Dict[str, Path]) -> None:
    """
    Hàm điều phối toàn bộ quy trình dịch thuật.
    
    Workflow v2.6.1:
    1. Kiểm tra xem có bản dịch cũ không (verification mode)
    2. Nếu không, bắt đầu dịch mới
    3. Dịch theo file-by-file (thư mục) hoặc chunk-by-chunk (file đơn)
    4. Auto-retry các chunks/files lỗi (tối đa 3 vòng)
    5. Consistency check (nếu bật)
    6. Ghép nối và hoàn tất
    
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
    
    # Tìm file/thư mục nguồn
    archive_dir_name = config_params['archive_dir_name']
    items_in_input = [
        f for f in input_dir.iterdir()
        if not f.name.startswith('.') and f.name != archive_dir_name
    ]
    
    if not items_in_input:
        logging.warning(f"📁 Không tìm thấy file/thư mục nào trong '{input_dir}'.")
        return
    
    target_path = items_in_input[0]
    
    # Xác định tên dự án
    if target_path.is_file():
        base_filename = target_path.stem
    else:
        base_filename = target_path.name
    
    output_dir = output_dir_base / base_filename
    
    # ===== KIỂM TRA VERIFICATION MODE =====
    verification_mode = False
    
    if output_dir.exists() and (output_dir / 'parts').exists():
        logging.info("🔍 Phát hiện bản dịch cũ đã tồn tại.")
        verify_choice = input(" Bạn có muốn kiểm tra bản dịch cũ không? (y/n): ").lower()
        
        if verify_choice == 'y':
            verification_mode = True
            
            # Khởi tạo các module
            prompts = load_prompts(config_parser, dirs, base_filename)
            is_text_source = detect_source_type(target_path) if target_path.is_file() else True
            normalizer = TextNormalizer(is_text_source=is_text_source)
            api_manager = translator.ApiManager(config_params['api_keys'])
            cache_manager = translator.TranslationCache(str(cache_dir), config_params['enable_cache'])
            
            # Chạy verification
            verify_existing_translation(
                input_dir, output_dir, base_filename,
                api_manager, cache_manager, prompts,
                config_params, normalizer, statistics
            )
            
            # Kết thúc sau verification
            statistics.print_summary()
            logging.info("🎉 Kiểm tra và cập nhật bản dịch hoàn tất!")
            return
    
    # ===== QUÁ TRÌNH DỊCH MỚI (CHỈ KHI KHÔNG PHẢI VERIFICATION MODE) =====
    # Xóa cache cũ nếu cần
    if cache_dir.exists() and any(cache_dir.iterdir()):
        delete_cache = input_with_timeout(
            f" Phát hiện cache cũ trong '{cache_dir}'. Bạn có muốn xóa không? (y/n):",
            timeout=5,
            default='y'
        )
        
        if delete_cache == 'y':
            shutil.rmtree(cache_dir)
            cache_dir.mkdir()
            logging.info("🗑️  Đã xóa cache cũ.")
    
    # Khởi tạo các module
    prompts = load_prompts(config_parser, dirs, base_filename)
    
    if not prompts.get('main'):
        logging.critical("❌ Lỗi: Main prompt không được nạp.")
        return
    
    is_text_source = detect_source_type(target_path) if target_path.is_file() else True
    normalizer = TextNormalizer(is_text_source=is_text_source)
    api_manager = translator.ApiManager(config_params['api_keys'])
    cache_manager = translator.TranslationCache(str(cache_dir), config_params['enable_cache'])
    
    # ===== XỬ LÝ THEO LOẠI INPUT =====
    if target_path.is_dir():
        # ===== WORKFLOW CHO THƯ MỤC NHIỀU FILE =====
        translate_directory_project(
            target_path, output_dir, api_manager, cache_manager,
            prompts, config_params, normalizer, statistics
        )
    
    else:
        # ===== WORKFLOW CHO FILE ĐƠN (CHIA CHUNK) =====
        translate_single_file_project(
            target_path, output_dir, progress_dir, api_manager, cache_manager,
            prompts, config_params, normalizer, statistics, health_monitor
        )
    
    # ===== IN THỐNG KÊ CUỐI CÙNG =====
    statistics.print_summary()
    logging.info("🎉 Dịch thuật hoàn tất!")


def translate_directory_project(
    source_dir: Path,
    output_dir: Path,
    api_manager,
    cache_manager,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    normalizer: TextNormalizer,
    statistics: TranslationStatistics
) -> None:
    """
    Dịch dự án dạng thư mục (nhiều file .txt riêng lẻ).
    
    Workflow:
    1. Dịch từng file → lưu vào output/parts với tên gốc
    2. Quét file lỗi (còn ký tự tiếng Trung)
    3. Auto-retry file lỗi (tối đa 3 vòng)
    4. Ghép nối thành full.txt
    
    Args:
        source_dir (Path): Thư mục chứa các file nguồn
        output_dir (Path): Thư mục output
        api_manager: Trình quản lý API
        cache_manager: Trình quản lý cache
        prompts (Dict): Dictionary prompt
        config_params (Dict): Tham số cấu hình
        normalizer (TextNormalizer): Đối tượng chuẩn hóa
        statistics (TranslationStatistics): Đối tượng thống kê
    """
    source_files = sorted(source_dir.glob('*.txt'))
    
    if not source_files:
        logging.error(f"❌ Không tìm thấy file .txt nào trong '{source_dir.name}'.")
        return
    
    logging.info(f"🌐 Bắt đầu dịch {len(source_files)} file...")
    
    # Tạo thư mục output/parts
    parts_dir = output_dir / 'parts'
    parts_dir.mkdir(parents=True, exist_ok=True)
    
    progress_bar = tqdm(source_files, desc="🤖 Đang dịch")
    
    for source_file in progress_bar:
        if check_emergency_stop():
            break
        
        try:
            content = source_file.read_text(encoding='utf-8')
            
            if not content.strip():
                logging.warning(f"⚠️  File {source_file.name} rỗng, bỏ qua.")
                continue
            
            # Dịch
            result, status, api_key_used = translator.robust_translate(
                content, api_manager, cache_manager, prompts,
                config_params, "", normalizer
            )
            
            statistics.add_chunk_result(source_file.name, content, status, api_key_used)
            
            if status == "success":
                # Lưu vào output/parts với tên gốc
                file_writer.save_translated_file(
                    result, str(output_dir), source_file.name,
                    config_params['output_encoding']
                )
                progress_bar.set_postfix_str(f"{source_file.name} ✅")
            else:
                logging.error(f"{source_file.name} thất bại: {status}")
                progress_bar.set_postfix_str(f"{source_file.name} ❌")
        
        except Exception as e:
            logging.error(f"Lỗi khi xử lý {source_file.name}: {e}")
    
    print_api_status(api_manager)
    
    # ===== AUTO-RETRY CHO FILE LỖI =====
    logging.info("\n" + "="*80)
    logging.info("🔍 Kiểm tra các file còn sót ký tự tiếng Trung...")
    logging.info("="*80 + "\n")
    
    failed_files = find_chinese_files(parts_dir)
    
    if failed_files:
        logging.warning(f"⚠️  Phát hiện {len(failed_files)} file còn ký tự tiếng Trung:")
        for fp, count in failed_files:
            logging.warning(f"   - {fp.name}: {count} ký tự")
        
        # Tạo map: tên file -> nội dung gốc
        source_files_map = {}
        for source_file in source_files:
            try:
                content = source_file.read_text(encoding='utf-8')
                source_files_map[source_file.name] = content
            except Exception as e:
                logging.error(f"Lỗi khi đọc {source_file.name}: {e}")
        
        # Retry tối đa 3 vòng
        max_retry_rounds = 3
        for round_num in range(1, max_retry_rounds + 1):
            logging.info(f"\n{'='*80}")
            logging.info(f"🔄 Vòng retry {round_num}/{max_retry_rounds}")
            logging.info(f"{'='*80}\n")
            
            progress_bar_retry = tqdm(failed_files, desc=f"🔄 Retry vòng {round_num}")
            
            for file_path, chinese_count in progress_bar_retry:
                if check_emergency_stop():
                    break
                
                filename = file_path.name
                
                if filename not in source_files_map:
                    logging.error(f"❌ Không tìm thấy file gốc: {filename}")
                    continue
                
                original_content = source_files_map[filename]
                
                # Xóa cache cũ
                import hashlib
                cache_key = prompts.get('main', '').replace('{previous_chunk_context}', '') + original_content
                cache_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
                cache_file = Path(cache_manager.cache_dir) / (cache_hash + ".pkl")
                
                if cache_file.exists():
                    cache_file.unlink()
                
                try:
                    result, status, api_key_used = translator.robust_translate(
                        original_content, api_manager, cache_manager, prompts,
                        config_params, "", normalizer
                    )
                    
                    statistics.add_chunk_result(filename, original_content, status, api_key_used)
                    
                    if status == "success":
                        file_path.write_text(result, encoding=config_params['output_encoding'])
                        progress_bar_retry.set_postfix_str(f"{filename} ✅")
                    else:
                        logging.error(f"{filename} retry thất bại: {status}")
                        progress_bar_retry.set_postfix_str(f"{filename} ❌")
                
                except Exception as e:
                    logging.error(f"Lỗi retry {filename}: {e}")
            
            # Quét lại
            failed_files = find_chinese_files(parts_dir)
            
            if not failed_files:
                logging.info(f"✅ Tất cả file đã sạch sau {round_num} vòng retry!")
                break
            
            logging.warning(f"⚠️  Vẫn còn {len(failed_files)} file lỗi sau vòng {round_num}")
        
        if failed_files:
            logging.error(f"❌ Không thể loại bỏ hết ký tự tiếng Trung sau {max_retry_rounds} vòng.")
            logging.error(f"   File lỗi: {[fp.name for fp, _ in failed_files]}")
    else:
        logging.info("✅ Tất cả file đã sạch!")
    
    # Ghép nối file full.txt
    logging.info("📝 Ghép nối các file thành full.txt...")
    file_writer.assemble_final_files(
        str(parts_dir), str(output_dir),
        config_params['output_encoding'], source_is_parts=True
    )


def translate_single_file_project(
    source_file: Path,
    output_dir: Path,
    progress_dir: Path,
    api_manager,
    cache_manager,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    normalizer: TextNormalizer,
    statistics: TranslationStatistics,
    health_monitor: HealthMonitor
) -> None:
    """
    Dịch dự án dạng file đơn (chia thành chunks).
    
    Workflow:
    1. Chia file thành chunks thông minh
    2. Dịch từng chunk với context chaining
    3. Auto-retry chunks lỗi (tối đa 3 vòng)
    4. Consistency check (nếu bật)
    5. Ghép nối thành full.txt
    
    Args:
        source_file (Path): File nguồn
        output_dir (Path): Thư mục output
        progress_dir (Path): Thư mục tạm
        api_manager: Trình quản lý API
        cache_manager: Trình quản lý cache
        prompts (Dict): Dictionary prompt
        config_params (Dict): Tham số cấu hình
        normalizer (TextNormalizer): Đối tượng chuẩn hóa
        statistics (TranslationStatistics): Đối tượng thống kê
        health_monitor (HealthMonitor): Đối tượng giám sát
    """
    logging.info("ℹ️  File đơn: sử dụng workflow chia chunk.")
    
    # Đọc và chia chunk
    original_text = smart_chunker.read_and_detect_encoding(str(source_file))
    
    if not original_text or not original_text.strip():
        logging.error(f"❌ Nội dung file rỗng.")
        return
    
    all_chunks = smart_chunker.process_text_for_chunking(
        original_text,
        config_params['min_chars_per_chunk'],
        config_params['max_chars_per_chunk']
    )
    
    logging.info(f"🌐 Bắt đầu dịch {len(all_chunks)} chunks...")
    
    # Xóa và tạo mới progress_dir
    if progress_dir.exists():
        shutil.rmtree(progress_dir)
    progress_dir.mkdir()
    
    # Lưu state
    state_file_path = progress_dir / STATE_FILE
    with open(state_file_path, 'w', encoding='utf-8') as f:
        json.dump({
            "base_filename": source_file.stem,
            "total_chunks": len(all_chunks),
            "completed_indices": [],
            "all_chunks": all_chunks,
            "source_file_path": str(source_file)
        }, f, ensure_ascii=False, indent=2)
    
    # Dịch từng chunk
    last_translated_text = ""
    progress_bar = tqdm(enumerate(all_chunks), total=len(all_chunks), desc="🤖 Đang dịch")
    
    for index, chunk in progress_bar:
        if check_emergency_stop():
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
            
            statistics.add_chunk_result(index, chunk, status, api_key_used)
            
            if status == "success":
                last_translated_text = result
                file_writer.save_progress_chunk(
                    result, index, str(progress_dir),
                    config_params['output_encoding']
                )
                
                # Cập nhật state
                with open(state_file_path, 'r+', encoding='utf-8') as f:
                    state = json.load(f)
                    if index not in state['completed_indices']:
                        state['completed_indices'].append(index)
                    f.seek(0)
                    json.dump(state, f, ensure_ascii=False, indent=2)
                    f.truncate()
                
                progress_bar.set_postfix_str(f"Chunk {index + 1} ✅")
            
            elif status == "all_keys_exhausted":
                logging.critical("🚨 Tất cả API key đã hết quota.")
                break
            
            else:
                logging.error(f"Chunk {index + 1} thất bại: {status}")
                progress_bar.set_postfix_str(f"Chunk {index + 1} ❌")
        
        except Exception as e:
            logging.error(f"Lỗi chunk {index + 1}: {e}")
    
    health_monitor.update_progress(len(all_chunks))
    print_api_status(api_manager)
    
    # ===== AUTO-RETRY CHO CHUNKS LỖI =====
    logging.info("\n" + "="*80)
    logging.info("🔍 Kiểm tra chunks còn sót ký tự tiếng Trung...")
    logging.info("="*80 + "\n")
    
    failed_chunks = find_chinese_chunks(progress_dir)
    
    if failed_chunks:
        logging.warning(f"⚠️  Phát hiện {len(failed_chunks)} chunks lỗi:")
        for idx, _, count in failed_chunks:
            logging.warning(f"   - Chunk {idx}: {count} ký tự")
        
        max_retry_rounds = 3
        for round_num in range(1, max_retry_rounds + 1):
            logging.info(f"\n{'='*80}")
            logging.info(f"🔄 Vòng retry {round_num}/{max_retry_rounds}")
            logging.info(f"{'='*80}\n")
            
            failed_chunks = retry_failed_chunks(
                failed_chunks, all_chunks, api_manager, cache_manager,
                prompts, config_params, progress_dir, normalizer, statistics
            )
            
            if not failed_chunks:
                logging.info(f"✅ Sạch sau {round_num} vòng!")
                break
            
            logging.warning(f"⚠️  Còn {len(failed_chunks)} chunks lỗi sau vòng {round_num}")
        
        if failed_chunks:
            logging.error(f"❌ Còn {len(failed_chunks)} chunks lỗi sau {max_retry_rounds} vòng.")
    else:
        logging.info("✅ Tất cả chunks đã sạch!")
    
    # ===== CONSISTENCY CHECK =====
    if check_emergency_stop():
        logging.warning("Bỏ qua consistency check.")
    elif config_params['enable_consistency_check'] and "Không có ghi chú đặc biệt." not in prompts.get('consistency', ''):
        run_consistency_check(progress_dir, api_manager, cache_manager, config_params, prompts, normalizer)
    else:
        logging.info("ℹ️  Bỏ qua consistency check.")
    
    # Ghép nối
    file_writer.assemble_final_files(
        str(progress_dir), str(output_dir),
        config_params['output_encoding']
    )
    
    # Dọn dẹp
    try:
        shutil.rmtree(progress_dir)
        logging.info(f"🗑️  Đã xóa thư mục tạm.")
    except Exception as e:
        logging.warning(f"⚠️  Lỗi xóa thư mục tạm: {e}")
