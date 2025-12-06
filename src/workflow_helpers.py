# src/workflow_helpers.py - v2.6.1
# Tác giả: Narga
# Chức năng: Module chứa các hàm helper cho workflow.
# Bao gồm: retry chunks lỗi, verification mode, consistency check, và tiện ích chuẩn hóa tên file.
# Lưu ý: Đã thay input() bằng io_utils.input_with_timeout (default 'y') để tránh chặn tiến trình khi chạy headless.

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
from .io_utils import input_with_timeout

def normalize_output_filename(name: str) -> str:
    """
    Chuẩn hóa tên file đầu ra (trong output/parts) về tên nguồn để ánh xạ.
    - Loại bỏ hậu tố '_translated' nếu tồn tại trước phần mở rộng.
    - Giữ nguyên phần mở rộng (mặc định .txt).
    - Trả về chuỗi tên đã chuẩn hóa.

    Ví dụ:
        "chapter_01_translated.txt"  -> "chapter_01.txt"
        "chunk_00001_translated.txt" -> "chunk_00001.txt"
    """
    p = Path(name)
    stem = p.stem
    if stem.endswith('_translated'):
        stem = stem[: -len('_translated')]
    return f"{stem}{p.suffix}"

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
    Dịch lại các chunks bị lỗi (còn sót ký tự tiếng Trung) theo chỉ số chunk.
    - Xóa cache cũ của từng chunk trước khi dịch lại để buộc sinh bản dịch mới.
    - Cập nhật thống kê mức chunk.
    - Sau vòng retry, quét lại các chunk còn lỗi và trả về danh sách lỗi còn lại.

    Returns:
        List[Tuple[int, Path, int]]: Danh sách các chunks vẫn còn lỗi sau khi retry.
    """
    if not failed_chunks:
        return []

    logging.info(f"🔄 Bắt đầu dịch lại {len(failed_chunks)} chunks bị lỗi...")

    progress_bar = tqdm(failed_chunks, desc="🔄 Đang dịch lại chunks lỗi")
    for chunk_index, chunk_file, chinese_count in progress_bar:
        if check_emergency_stop():
            logging.warning("Dừng quá trình retry do tín hiệu khẩn cấp.")
            break

        original_chunk = all_chunks[chunk_index]
        # Chuẩn bị ngữ cảnh (nếu có)
        context_to_pass = ""
        if config_params['context_char_count'] > 0 and chunk_index > 0:
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
    Chế độ kiểm tra bản dịch cũ và dịch lại các file có lỗi.
    - Áp dụng cho dự án dạng thư mục (nhiều file nguồn riêng lẻ).
    - Với dự án file đơn (đã chia chunk), chặn từ sớm để tránh retry vô nghĩa.
    - Chuẩn hóa tên file đầu ra (strip '_translated') trước khi ánh xạ về nguồn.

    Hành vi:
    1) Quét output/parts để tìm file còn ký tự Trung.
    2) Hỏi người dùng (không chặn) có muốn retry không (default 'y').
    3) Lập map tên_nguồn -> nội_dung_gốc, rồi ánh xạ các file lỗi về nguồn.
    4) Xóa cache tương ứng và dịch lại từng file lỗi, tối đa 3 vòng.
    5) Ghép lại full.txt sau khi hoàn tất.
    """
    logging.info("🔍 Bắt đầu chế độ kiểm tra bản dịch cũ...")

    parts_dir = output_dir / 'parts'
    if not parts_dir.exists():
        logging.error(f"❌ Không tìm thấy thư mục parts: {parts_dir}")
        return

    # Quét tìm file lỗi
    failed_files = find_chinese_files(parts_dir)
    if not failed_files:
        logging.info("✅ Không phát hiện file nào có ký tự tiếng Trung. Bản dịch sạch!")
        return

    logging.warning(f"⚠️ Phát hiện {len(failed_files)} file còn sót ký tự tiếng Trung:")
    for file_path, chinese_count in failed_files:
        logging.warning(f" - {file_path.name}: {chinese_count} ký tự")

    # Hỏi người dùng theo kiểu non-blocking
    user_choice = input_with_timeout("\n Bạn có muốn dịch lại các file này không? (y/n): ", timeout=5, default='y')
    if user_choice != 'y':
        logging.info("Người dùng từ chối dịch lại. Bỏ qua.")
        return

    # Xác định nguồn dữ liệu (file đơn hay thư mục)
    source_path = input_dir / (base_filename + '.txt')
    if not source_path.exists():
        source_path = input_dir / base_filename
    if not source_path.exists():
        logging.error(f"❌ Không tìm thấy file hoặc thư mục nguồn dưới tên dự án: {base_filename}")
        return

    # File đơn: chặn sớm để tránh retry vô nghĩa
    if source_path.is_file():
        logging.error("❌ Verification mode chỉ hỗ trợ dự án có nhiều file input riêng lẻ.")
        logging.error("   Dự án file đơn đã được chia chunk => hãy dùng cơ chế retry chunks trong workflow.")
        return

    # Thư mục: nạp toàn bộ map tên file nguồn -> nội dung
    source_files_map = {}
    for input_file in sorted(source_path.glob('*.txt')):
        try:
            content = input_file.read_text(encoding='utf-8')
            source_files_map[input_file.name] = content
        except Exception as e:
            logging.error(f"Lỗi khi đọc file {input_file.name}: {e}")

    # Gộp thêm một map so khớp lower-case để dự phòng sai khác hoa/thường
    lower_map = {k.lower(): v for k, v in source_files_map.items()}

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

            # Chuẩn hóa tên parts để tìm về tên nguồn
            normalized_name = normalize_output_filename(file_path.name)
            original_content = source_files_map.get(normalized_name)
            if original_content is None:
                # Dự phòng: so khớp lower-case
                original_content = lower_map.get(normalized_name.lower())

            if original_content is None:
                logging.error(f"❌ Không tìm thấy file gốc tương ứng cho: {file_path.name} -> {normalized_name}")
                continue

            # Xóa cache cũ của file này
            cache_key = prompts.get('main', '').replace('{previous_chunk_context}', '') + original_content
            cache_hash = hashlib.md5(cache_key.encode('utf-8')).hexdigest()
            cache_file = Path(cache_manager.cache_dir) / (cache_hash + ".pkl")
            if cache_file.exists():
                cache_file.unlink()
                logging.info(f"Đã xóa cache cũ cho {normalized_name}")

            try:
                # Dịch lại file
                result, status, api_key_used = translator.robust_translate(
                    original_content, api_manager, cache_manager, prompts,
                    config_params, "", normalizer
                )

                # Ghi nhận thống kê (dùng normalized_name làm id)
                statistics.add_chunk_result(normalized_name, original_content, status, api_key_used)

                if status == "success":
                    # Ghi đè kết quả vào chính file parts (giữ nguyên tên hiện tại)
                    file_path.write_text(result, encoding=config_params['output_encoding'])
                    progress_bar.set_postfix_str(f"{file_path.name} ✅")
                else:
                    logging.error(f"{file_path.name} retry thất bại với status: {status}")
                    progress_bar.set_postfix_str(f"{file_path.name} ❌")
            except Exception as e:
                logging.error(f"Lỗi khi retry {file_path.name}: {e}")

        # Quét lại để tìm file còn lỗi
        failed_files = find_chinese_files(parts_dir)
        if not failed_files:
            logging.info(f"✅ Tất cả file đã sạch sau {round_num} vòng retry!")
            break
        logging.warning(f"⚠️ Vẫn còn {len(failed_files)} file lỗi sau vòng {round_num}")

    if failed_files:
        logging.error(f"❌ Không thể loại bỏ hết ký tự tiếng Trung sau {max_retry_rounds} vòng retry.")
        logging.error(f"   Các file vẫn còn lỗi: {[fp.name for fp, _ in failed_files]}")

    # Ghép nối lại file full.txt (source_is_parts=True vì đang làm việc trên parts)
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
    - Duyệt toàn bộ chunk_*.txt trong progress_dir và chạy QA nếu có prompt.
    - Dùng ThreadPoolExecutor giới hạn bởi max_workers để tận dụng đa key song song.
    """
    logging.info("🔬 Bắt đầu bước kiểm tra và tinh chỉnh sự nhất quán...")
    if check_emergency_stop():
        return

    chunk_files = sorted(progress_dir.glob("chunk_*.txt"))
    if not chunk_files:
        logging.warning("Không tìm thấy chunk nào để kiểm tra sự nhất quán.")
        return

    from concurrent.futures import ThreadPoolExecutor
    tasks = [
        (translator.consistency_check_chunk, (chunk_file, api_manager, cache_manager, prompts, config_params, normalizer))
        for chunk_file in chunk_files
    ]

    with ThreadPoolExecutor(max_workers=config_params['max_workers']) as executor:
        list(tqdm(
            executor.map(lambda p: p[0](*p[1]), tasks),
            total=len(tasks),
            desc="🔬 Tinh chỉnh"
        ))

    logging.info("✅ Hoàn tất bước kiểm tra sự nhất quán.")
