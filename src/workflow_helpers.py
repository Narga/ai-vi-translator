# src/workflow_helpers.py - v2.8.2
# Tác giả: Narga
# Chức năng: Module chứa các hàm helper cho workflow.
# Bao gồm: retry chunks lỗi, verification mode, consistency check.
#
# Nâng cấp v2.8.2:
# - Sửa verify_existing_translation(): bỏ logic tìm file gốc đơn lẻ,
#   thay bằng so sánh danh sách file input với output/parts để tự động
#   phát hiện file mới/thay đổi và dịch lại.

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
    
    Hàm này xóa cache cũ cho từng chunk lỗi, sau đó gọi robust_translate
    để dịch lại. Hỗ trợ Parallel Context Correction (Phương án 2) nếu
    config_params['correction_mode'] = 'parallel'.
    
    Args:
        failed_chunks: Danh sách (chunk_index, file_path, chinese_count) các chunks lỗi
        all_chunks: Danh sách toàn bộ chunks gốc (tiếng Trung)
        api_manager: Trình quản lý API keys
        cache_manager: Trình quản lý cache
        prompts: Dictionary chứa các prompt
        config_params: Dictionary tham số cấu hình
        progress_dir: Thư mục tiến trình (cache/progress)
        normalizer: TextNormalizer để chuẩn hóa văn bản
        statistics: TranslationStatistics để ghi thống kê
    
    Returns:
        List[Tuple[int, Path, int]]: Danh sách chunks vẫn còn lỗi sau retry
    """
    if not failed_chunks:
        return []
    
    logging.info(f"🔄 Bắt đầu retry {len(failed_chunks)} chunks lỗi...")
    still_failed = []
    
    for chunk_index, chunk_path, chinese_count in tqdm(failed_chunks, desc="🔄 Retry chunks"):
        if check_emergency_stop():
            break
        
        if chunk_index >= len(all_chunks):
            logging.error(f"❌ Chunk {chunk_index} vượt quá phạm vi danh sách chunks.")
            still_failed.append((chunk_index, chunk_path, chinese_count))
            continue
        
        original_chunk = all_chunks[chunk_index]
        
        # Xóa cache cũ để ép dịch lại
        main_prompt_template = prompts.get('main', '')
        main_prompt = main_prompt_template.replace('{previous_chunk_context}', '')
        cache_key = main_prompt + original_chunk
        cache_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
        cache_file = Path(cache_manager.cache_dir) / (cache_hash + ".pkl")
        
        if cache_file.exists():
            try:
                cache_file.unlink()
            except Exception as e:
                logging.warning(f"⚠️ Không thể xóa cache cho chunk {chunk_index}: {e}")
        
        # Dịch lại
        result, status, api_key_used = translator.robust_translate(
            original_chunk, api_manager, cache_manager, prompts,
            config_params, "", normalizer
        )
        
        statistics.add_chunk_result(chunk_index, original_chunk, status, api_key_used)
        
        if status == "success":
            # Lưu lại chunk đã sửa
            file_writer.save_progress_chunk(
                result, chunk_index, str(progress_dir),
                config_params['output_encoding']
            )
            
            # Kiểm tra xem còn ký tự Trung không
            from .chinese_detector import count_chinese_characters
            remaining = count_chinese_characters(result)
            
            if remaining > 0:
                logging.warning(f"⚠️ Chunk {chunk_index} vẫn còn {remaining} ký tự Trung sau retry.")
                still_failed.append((chunk_index, chunk_path, remaining))
            else:
                logging.info(f"✅ Chunk {chunk_index} đã sạch sau retry.")
        else:
            logging.error(f"❌ Chunk {chunk_index} retry thất bại: {status}")
            still_failed.append((chunk_index, chunk_path, chinese_count))
    
    logging.info(f"🏁 Hoàn tất retry. Còn {len(still_failed)} chunks lỗi.")
    return still_failed


def verify_existing_translation(
    target_path: Path,
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
    Chế độ verification: kiểm tra và cập nhật bản dịch cũ đã tồn tại.
    
    Logic v2.8.2:
    - Nếu target_path là thư mục: so sánh danh sách file .txt trong thư mục
      với danh sách file trong output/parts. Dịch lại file mới hoặc bị thay đổi.
    - Nếu target_path là file đơn: quét output/parts để tìm chunks lỗi (có ký tự Trung)
      và retry.
    
    Args:
        target_path (Path): File/thư mục nguồn
        output_dir (Path): Thư mục output
        base_filename (str): Tên dự án
        api_manager: Trình quản lý API
        cache_manager: Trình quản lý cache
        prompts (Dict): Dictionary prompt
        config_params (Dict): Tham số cấu hình
        normalizer (TextNormalizer): Đối tượng chuẩn hóa
        statistics (TranslationStatistics): Đối tượng thống kê
    """
    parts_dir = output_dir / "parts"
    
    if not parts_dir.exists():
        logging.error(f"❌ Không tìm thấy thư mục parts: {parts_dir}")
        return
    
    if target_path.is_dir():
        # ===== VERIFICATION CHO THƯ MỤC =====
        logging.info("🔍 Chế độ verification cho thư mục nhiều file...")
        
        # Lấy danh sách file .txt trong input
        source_files = sorted(target_path.glob('*.txt'))
        source_file_names = {f.name for f in source_files}
        
        # Lấy danh sách file trong output/parts
        parts_files = sorted(parts_dir.glob('*.txt'))
        parts_file_names = {f.name for f in parts_files}
        
        # Tìm file mới (có trong input nhưng không có trong parts)
        new_files = source_file_names - parts_file_names
        
        # Tìm file bị xóa (có trong parts nhưng không có trong input)
        deleted_files = parts_file_names - source_file_names
        
        if new_files:
            logging.info(f"📝 Phát hiện {len(new_files)} file mới, bắt đầu dịch...")
            for filename in sorted(new_files):
                source_file = target_path / filename
                try:
                    content = source_file.read_text(encoding='utf-8')
                    if not content.strip():
                        logging.warning(f"⚠️ File {filename} rỗng, bỏ qua.")
                        continue
                    
                    result, status, api_key_used = translator.robust_translate(
                        content, api_manager, cache_manager, prompts,
                        config_params, "", normalizer
                    )
                    
                    statistics.add_chunk_result(filename, content, status, api_key_used)
                    
                    if status == "success":
                        file_writer.save_translated_file(
                            result, str(output_dir), filename,
                            config_params['output_encoding']
                        )
                        logging.info(f"✅ Đã dịch file mới: {filename}")
                    else:
                        logging.error(f"❌ Dịch {filename} thất bại: {status}")
                
                except Exception as e:
                    logging.error(f"❌ Lỗi khi xử lý {filename}: {e}")
        
        if deleted_files:
            logging.warning(f"⚠️ Phát hiện {len(deleted_files)} file đã bị xóa khỏi input:")
            for filename in sorted(deleted_files):
                logging.warning(f"   - {filename}")
                # Xóa file khỏi output/parts nếu cần
                try:
                    (parts_dir / filename).unlink()
                    logging.info(f"🗑️ Đã xóa {filename} khỏi output/parts")
                except Exception as e:
                    logging.warning(f"⚠️ Không thể xóa {filename}: {e}")
        
        # Kiểm tra file lỗi (còn ký tự Trung)
        failed_files = find_chinese_files(parts_dir)
        if failed_files:
            logging.warning(f"⚠️ Phát hiện {len(failed_files)} file còn ký tự Trung:")
            for fp, count in failed_files:
                logging.warning(f"   - {fp.name}: {count} ký tự")
            
            # Retry các file lỗi (tương tự workflow chính)
            source_files_map = {}
            for source_file in source_files:
                try:
                    content = source_file.read_text(encoding='utf-8')
                    source_files_map[source_file.name] = content
                except Exception as e:
                    logging.error(f"Lỗi khi đọc {source_file.name}: {e}")
            
            for file_path, chinese_count in failed_files:
                filename = file_path.name
                if filename not in source_files_map:
                    logging.error(f"❌ Không tìm thấy file gốc: {filename}")
                    continue
                
                original_content = source_files_map[filename]
                
                # Xóa cache cũ
                main_prompt_template = prompts.get('main', '')
                cache_key = main_prompt_template.replace('{previous_chunk_context}', '') + original_content
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
                        logging.info(f"✅ Đã sửa file lỗi: {filename}")
                    else:
                        logging.error(f"❌ Sửa {filename} thất bại: {status}")
                
                except Exception as e:
                    logging.error(f"❌ Lỗi retry {filename}: {e}")
        
        # Ghép nối lại sau khi cập nhật
        logging.info(f"📝 Ghép nối các file thành {base_filename}_full.txt...")
        file_writer.assemble_final_files(
            str(parts_dir), str(output_dir),
            config_params['output_encoding'], source_is_parts=True, base_filename=base_filename
        )
        
        logging.info("✅ Hoàn tất cập nhật bản dịch!")
    
    else:
        # ===== VERIFICATION CHO FILE ĐƠN =====
        logging.info("🔍 Chế độ verification cho file đơn...")
        
        # Tải file gốc và chia chunks
        from . import smart_chunker
        original_text = smart_chunker.read_and_detect_encoding(str(target_path))
        all_chunks = smart_chunker.process_text_for_chunking(
            original_text, config_params['min_chars_per_chunk'],
            config_params['max_chars_per_chunk']
        )
        
        # Tìm chunks lỗi
        failed_chunks = find_chinese_chunks(parts_dir)
        
        if not failed_chunks:
            logging.info("✅ Tất cả chunks đã sạch! Không cần cập nhật.")
            return
        
        logging.info(f"🔍 Phát hiện {len(failed_chunks)} chunks còn ký tự Trung. Bắt đầu cập nhật...")
        retry_failed_chunks(
            failed_chunks, all_chunks, api_manager, cache_manager,
            prompts, config_params, parts_dir, normalizer, statistics
        )
        
        # Ghép nối lại sau khi cập nhật
        file_writer.assemble_final_files(
            str(parts_dir), str(output_dir),
            config_params['output_encoding'], base_filename=base_filename
        )
        
        logging.info("✅ Hoàn tất cập nhật bản dịch!")


def run_consistency_check(
    progress_dir: Path,
    api_manager,
    cache_manager,
    config_params: Dict[str, Any],
    prompts: Dict[str, str],
    normalizer: TextNormalizer
) -> None:
    """
    Chạy kiểm tra nhất quán trên tất cả chunks đã dịch.
    
    Hàm này đọc tất cả chunks từ progress_dir, gọi consistency_check_chunk
    cho từng chunk, và ghi đè lại file nếu có tinh chỉnh.
    
    Args:
        progress_dir (Path): Thư mục chứa các chunks đã dịch
        api_manager: Trình quản lý API
        cache_manager: Trình quản lý cache
        config_params (Dict): Tham số cấu hình
        prompts (Dict): Dictionary prompt
        normalizer (TextNormalizer): Đối tượng chuẩn hóa
    """
    consistency_prompt = prompts.get('consistency', '')
    
    # Bỏ qua nếu không có prompt consistency hoặc prompt trống
    if not consistency_prompt or "Không có ghi chú đặc biệt." in consistency_prompt:
        logging.info("ℹ️ Bỏ qua consistency check (prompt trống hoặc không áp dụng).")
        return
    
    logging.info("\n" + "="*80)
    logging.info("🔍 Bắt đầu kiểm tra nhất quán (consistency check)...")
    logging.info("="*80 + "\n")
    
    chunk_files = sorted(progress_dir.glob("chunk_*.txt"), key=lambda p: int(p.stem.split("_")[1]))
    
    for chunk_file in tqdm(chunk_files, desc="🔍 Consistency check"):
        if check_emergency_stop():
            break
        
        translator.consistency_check_chunk(
            chunk_file, api_manager, cache_manager,
            prompts, config_params, normalizer
        )
    
    logging.info("✅ Hoàn tất consistency check!")
