# src/workflow_helpers.py - v2.6.1
# Tác giả: Narga
# Chức năng: Module chứa các hàm helper cho workflow.
#            Bao gồm: retry chunks lỗi, verification mode, consistency check.

import json
import logging
import shutil
import hashlib
from pathlib import Path
from tqdm import tqdm
from typing import Dict, Any, List, Tuple

from . import translator, file_writer
from .emergency_stop import check_emergency_stop
from .statistics import TranslationStatistics
from .text_normalizer import TextNormalizer
from .chinese_detector import find_chinese_files, find_chinese_chunks


def retry_failed_chunks(
    failed_chunks: List[Tuple[int, Path, int]],
    all_chunks: List[str],
    api_manager,
    cache_manager,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    progress_dir: Path,
    normalizer: TextNormalizer,
    statistics: TranslationStatistics
) -> List[Tuple[int, Path, int]]:
    """
    Dịch lại các chunks bị lỗi (còn sót ký tự tiếng Trung).
    
    Hàm này nhận danh sách các chunks có lỗi, thực hiện dịch lại từng chunk,
    và trả về danh sách các chunks vẫn còn lỗi sau khi dịch lại.
    
    Args:
        failed_chunks (List[Tuple[int, Path, int]]): Danh sách chunks lỗi (index, path, chinese_count)
        all_chunks (List[str]): Danh sách tất cả chunks gốc
        api_manager: Trình quản lý API keys
        cache_manager: Trình quản lý cache
        prompts (Dict): Dictionary chứa các prompt
        config_params (Dict): Tham số cấu hình
        progress_dir (Path): Thư mục lưu chunks
        normalizer (TextNormalizer): Đối tượng chuẩn hóa văn bản
        statistics (TranslationStatistics): Đối tượng thống kê
        
    Returns:
        List[Tuple[int, Path, int]]: Danh sách chunks vẫn còn lỗi sau khi retry
    """
    if not failed_chunks:
        return []
    
    logging.info(f"🔄 Bắt đầu dịch lại {len(failed_chunks)} chunks bị lỗi...")
    
    progress_bar = tqdm(failed_chunks, desc="🔄 Đang dịch lại chunks lỗi")
    
    for chunk_index, chunk_file, chinese_count in progress_bar:
        if check_emergency_stop():
            logging.warning("Dừng quá trình retry do tín hiệu khẩn cấp.")
            break
        
        # Lấy chunk gốc
        original_chunk = all_chunks[chunk_index]
        
        # Chuẩn bị ngữ cảnh (nếu có)
        context_to_pass = ""
        if config_params['context_char_count'] > 0 and chunk_index > 0:
            # Đọc chunk trước đó để lấy ngữ cảnh
            prev_chunk_file = progress_dir / f"chunk_{chunk_index - 1}.txt"
            if prev_chunk_file.exists():
                prev_content = prev_chunk_file.read_text(encoding='utf-8')
                context_to_pass = prev_content[-config_params['context_char_count']:]
        
        try:
            # Xóa cache cũ của chunk này
            cache_key = prompts.get('main', '').replace('{previous_chunk_context}', context_to_pass) + original_chunk
            cache_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
            
            if hasattr(cache_manager, 'cache_dir'):
                cache_file = Path(cache_manager.cache_dir) / (cache_hash + ".pkl")
                if cache_file.exists():
                    cache_file.unlink()
                    logging.info(f"Đã xóa cache cũ cho chunk {chunk_index}")
            
            # Dịch lại
            result, status, api_key_used = translator.robust_translate(
                original_chunk, api_manager, cache_manager, prompts,
                config_params, context_to_pass, normalizer
            )
            
            # Ghi nhận thống kê
            statistics.add_chunk_result(chunk_index, original_chunk, status, api_key_used)
            
            if status == "success":
                # Lưu kết quả
                file_writer.save_progress_chunk(
                    result, chunk_index, str(progress_dir),
                    config_params['output_encoding']
                )
                progress_bar.set_postfix_str(f"Chunk {chunk_index} ✅ (retry)")
            else:
                logging.error(f"Chunk {chunk_index} retry thất bại với status: {status}")
                progress_bar.set_postfix_str(f"Chunk {chunk_index} ❌ (retry failed)")
        
        except Exception as e:
            logging.error(f"Lỗi khi retry chunk {chunk_index}: {e}")
    
    # Quét lại để tìm chunks vẫn còn lỗi
    still_failed = find_chinese_chunks(progress_dir)
    
    return still_failed


def verify_existing_translation(
    input_dir: Path,
    output_dir: Path,
    base_filename: str,
    api_manager,
    cache_manager,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    normalizer: TextNormalizer,
    statistics: TranslationStatistics
) -> None:
    """
    Kiểm tra bản dịch cũ và chỉ dịch lại các file có lỗi.
    
    Hàm này được gọi khi người dùng chọn verification mode.
    Nó quét tất cả file trong output/parts, tìm file còn ký tự tiếng Trung,
    và chỉ dịch lại những file đó.
    
    Args:
        input_dir (Path): Thư mục chứa file nguồn
        output_dir (Path): Thư mục output chứa bản dịch cũ
        base_filename (str): Tên dự án
        api_manager: Trình quản lý API keys
        cache_manager: Trình quản lý cache
        prompts (Dict): Dictionary chứa các prompt
        config_params (Dict): Tham số cấu hình
        normalizer (TextNormalizer): Đối tượng chuẩn hóa văn bản
        statistics (TranslationStatistics): Đối tượng thống kê
    """
    logging.info("🔍 Bắt đầu chế độ kiểm tra bản dịch cũ...")
    
    # Xác định thư mục parts
    parts_dir = output_dir / 'parts'
    
    if not parts_dir.exists():
        logging.error(f"❌ Không tìm thấy thư mục parts: {parts_dir}")
        return
    
    # Quét tìm file lỗi
    failed_files = find_chinese_files(parts_dir)
    
    if not failed_files:
        logging.info("✅ Không phát hiện file nào có ký tự tiếng Trung. Bản dịch sạch!")
        return
    
    logging.warning(f"⚠️  Phát hiện {len(failed_files)} file còn sót ký tự tiếng Trung:")
    for file_path, chinese_count in failed_files:
        logging.warning(f"   - {file_path.name}: {chinese_count} ký tự")
    
    # Hỏi người dùng có muốn dịch lại không
    user_choice = input("\n Bạn có muốn dịch lại các file này không? (y/n): ").lower()
    
    if user_choice != 'y':
        logging.info("Người dùng từ chối dịch lại. Bỏ qua.")
        return
    
    # Xác định nguồn dữ liệu (file đơn hay thư mục)
    source_path = input_dir / (base_filename + '.txt')
    if not source_path.exists():
        source_path = input_dir / base_filename
    
    if not source_path.exists():
        logging.error(f"❌ Không tìm thấy file nguồn: {source_path}")
        return
    
    # Tạo map: tên file -> nội dung gốc
    source_files_map = {}
    
    if source_path.is_file():
        # File đơn: không thể ánh xạ file-to-file (đã chia chunk)
        logging.error("❌ Verification mode chỉ hỗ trợ dự án có nhiều file input riêng lẻ.")
        logging.error("   File đơn đã được chia chunk, không thể ánh xạ trở lại file gốc.")
        return
    
    elif source_path.is_dir():
        # Thư mục: đọc tất cả file .txt
        for input_file in sorted(source_path.glob('*.txt')):
            try:
                content = input_file.read_text(encoding='utf-8')
                source_files_map[input_file.name] = content
            except Exception as e:
                logging.error(f"Lỗi khi đọc file {input_file.name}: {e}")
    
    # Retry các file lỗi (tối đa 3 vòng)
    max_retry_rounds = 3
    
    for round_num in range(1, max_retry_rounds + 1):
        logging.info(f"\n{'='*80}")
        logging.info(f"🔄 Vòng retry {round_num}/{max_retry_rounds}")
        logging.info(f"{'='*80}\n")
        
        progress_bar = tqdm(failed_files, desc=f"🔄 Retry vòng {round_num}")
        
        for file_path, chinese_count in progress_bar:
            if check_emergency_stop():
                logging.warning("Dừng quá trình retry do tín hiệu khẩn cấp.")
                break
            
            filename = file_path.name
            
            # Lấy nội dung gốc
            if filename not in source_files_map:
                logging.error(f"❌ Không tìm thấy file gốc tương ứng: {filename}")
                continue
            
            original_content = source_files_map[filename]
            
            # Xóa cache cũ của file này
            cache_key = prompts.get('main', '').replace('{previous_chunk_context}', '') + original_content
            cache_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
            cache_file = Path(cache_manager.cache_dir) / (cache_hash + ".pkl")
            
            if cache_file.exists():
                cache_file.unlink()
                logging.info(f"Đã xóa cache cũ cho {filename}")
            
            try:
                # Dịch lại file
                result, status, api_key_used = translator.robust_translate(
                    original_content, api_manager, cache_manager, prompts,
                    config_params, "", normalizer
                )
                
                # Ghi nhận thống kê (dùng filename làm "chunk")
                statistics.add_chunk_result(filename, original_content, status, api_key_used)
                
                if status == "success":
                    # Lưu kết quả (ghi đè file cũ)
                    file_path.write_text(result, encoding=config_params['output_encoding'])
                    progress_bar.set_postfix_str(f"{filename} ✅")
                else:
                    logging.error(f"{filename} retry thất bại với status: {status}")
                    progress_bar.set_postfix_str(f"{filename} ❌")
            
            except Exception as e:
                logging.error(f"Lỗi khi retry {filename}: {e}")
        
        # Quét lại để tìm file vẫn còn lỗi
        failed_files = find_chinese_files(parts_dir)
        
        if not failed_files:
            logging.info(f"✅ Tất cả file đã sạch sau {round_num} vòng retry!")
            break
        
        logging.warning(f"⚠️  Vẫn còn {len(failed_files)} file lỗi sau vòng {round_num}")
    
    if failed_files:
        logging.error(f"❌ Không thể loại bỏ hết ký tự tiếng Trung sau {max_retry_rounds} vòng retry.")
        logging.error(f"   Các file vẫn còn lỗi: {[fp.name for fp, _ in failed_files]}")
    
    # Ghép nối lại file full.txt
    logging.info("📝 Ghép nối lại file full.txt...")
    file_writer.assemble_final_files(
        str(parts_dir), str(output_dir),
        config_params['output_encoding'], source_is_parts=True
    )


def run_consistency_check(
    progress_dir: Path,
    api_manager,
    cache_manager,
    config_params: Dict[str, Any],
    prompts: Dict[str, str],
    normalizer: TextNormalizer
) -> None:
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
    from concurrent.futures import ThreadPoolExecutor
    
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
