import asyncio
import logging
import os
import re
import sys
import time
from typing import Any, AsyncIterator, Dict, Iterable, List, Optional, Tuple

# Import from package modules
# Note: Use local imports in ocr_reader to avoid circularity if needed, 
# but here we can use relative imports for utility parts.
try:
    from .config_loader import _build_safety_settings
    from .exceptions import AIProcessorError
    from .language_utils import _normalize_lang_code
    from .logging_filters import NoisyMessageFilter, _suppress_google_logs
except ImportError:
    # Fallback for direct execution or complex import paths
    from src.preprocessing.ocr.config_loader import _build_safety_settings
    from src.preprocessing.ocr.exceptions import AIProcessorError
    from src.preprocessing.ocr.language_utils import _normalize_lang_code
    from src.preprocessing.ocr.logging_filters import NoisyMessageFilter, _suppress_google_logs

# Import from other project modules
from src.services.genai_adapter import create_client

logger = logging.getLogger("NovelTranslator")

async def _as_completed_iter(coros: Iterable[Any]) -> AsyncIterator[Any]:
    for fut in asyncio.as_completed(coros):
        yield await fut

def _split_text_at_sentence_boundaries(text: str, max_chunk_size: int) -> List[str]:
    """
    Chia text thành chunks ở ranh giới câu (kết thúc bằng dấu chấm câu).
    Tham khảo thuật toán từ SmartChunker._split_long_paragraph để đảm bảo không cắt giữa câu.
    """
    if not text or len(text) <= max_chunk_size:
        return [text] if text else []

    # Pattern để tìm ranh giới câu: . ! ? (cả tiếng Anh) và 。！？ (tiếng Trung)
    # Hỗ trợ các dấu ngoặc kép có thể đi kèm: ["']? (cho tiếng Anh) và » (cho một số ngôn ngữ)
    sentence_pattern = re.compile(r'([.!?。！？]["\'»]?\s*)')

    # Tìm tất cả các vị trí kết thúc câu
    parts = sentence_pattern.split(text)

    # Ghép lại các phần để tạo sentences (mỗi sentence bao gồm nội dung + dấu câu)
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        if i + 1 < len(parts):
            sentence = (parts[i] + parts[i + 1]).strip()
            if sentence:
                sentences.append(sentence)

    # Xử lý phần cuối cùng nếu không kết thúc bằng dấu câu
    if len(parts) % 2 == 1 and parts[-1].strip():
        sentences.append(parts[-1].strip())

    # Lọc bỏ các câu rỗng
    sentences = [sent for sent in sentences if sent.strip()]

    if not sentences:
        return [text]

    # Gom các sentences thành chunks, đảm bảo không vượt quá max_chunk_size
    chunks = []
    current_chunk = []
    current_size = 0

    for sentence in sentences:
        sent_size = len(sentence)

        # Nếu sentence đơn lẻ quá dài, phải cắt (trường hợp hiếm)
        if sent_size > max_chunk_size:
            # Nếu đang có chunk tích lũy, lưu nó trước
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                current_size = 0

            # Chia sentence dài thành nhiều phần nhỏ hơn
            # Ưu tiên cắt ở khoảng trắng nếu có thể
            words = sentence.split()
            temp_chunk = []
            temp_size = 0

            for word in words:
                word_size = len(word) + 1  # +1 cho space
                if temp_size + word_size > max_chunk_size and temp_chunk:
                    # Lưu chunk hiện tại
                    chunks.append(" ".join(temp_chunk))
                    temp_chunk = [word]
                    temp_size = len(word)
                else:
                    temp_chunk.append(word)
                    temp_size += word_size

            if temp_chunk:
                chunks.append(" ".join(temp_chunk))
        else:
            # Kiểm tra nếu thêm sentence này vào chunk hiện tại có vượt quá max_chunk_size không
            space_needed = 1 if current_chunk else 0
            if (
                current_size + sent_size + space_needed > max_chunk_size
                and current_chunk
            ):
                # Lưu chunk hiện tại và bắt đầu chunk mới
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_size = sent_size
            else:
                # Thêm sentence vào chunk hiện tại
                current_chunk.append(sentence)
                current_size += sent_size + space_needed

    # Lưu chunk cuối cùng nếu có
    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks

def _preprocess_line_breaks(text: str) -> str:
    """
    Preprocessing: Nối lại các câu bị ngắt do line breaks khi convert PDF → TXT.
    """
    lines = text.split("\n")
    if not lines:
        return text

    result_lines = []
    i = 0

    while i < len(lines):
        current_line = lines[i].strip()
        if not current_line:
            result_lines.append("")
            i += 1
            continue

        merged_line = current_line
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if not next_line:
                if re.search(r"[.!?]$", merged_line):
                    break
                if i + 2 < len(lines):
                    next_next_line = lines[i + 2].strip()
                    if next_next_line:
                        first_char = next_next_line[0]
                        next_starts_with_upper = (first_char.isupper() and first_char.isalpha())
                        if next_starts_with_upper or bool(re.match(r"^\d+", next_next_line)) or bool(re.match(r"^[•·\-*]\s", next_next_line)):
                            break
                        next_line = next_next_line
                        i += 1
                    else:
                        break
                else:
                    break

            ends_with_punctuation = bool(re.search(r"[.!?]$", merged_line))
            if not ends_with_punctuation:
                if next_line:
                    first_char = next_line[0]
                    next_starts_with_upper = (first_char.isupper() and first_char.isalpha())
                else:
                    next_starts_with_upper = False

                if not next_starts_with_upper and not bool(re.match(r"^\d+", next_line)) and not bool(re.match(r"^[•·\-*]\s", next_line)):
                    merged_line = merged_line.rstrip() + " " + next_line.lstrip()
                    i += 1
                    continue
            break

        result_lines.append(merged_line)
        i += 1

    return "\n".join(result_lines)

async def _cleanup_chunk_async(
    chunk: str,
    api_key: str,
    model_name: str,
    prompt: str,
    chunk_idx: int,
    total_chunks: int,
    timeout_s: float,
    safety_settings: Optional[List[Dict[str, Any]]] = None,
    use_new_sdk: bool = True,
) -> str:
    """Cleanup một chunk text bằng AI (async)."""
    _suppress_google_logs()
    if not isinstance(sys.stderr, NoisyMessageFilter):
        original_stderr = getattr(sys.stderr, "original_stream", sys.stderr)
        sys.stderr = NoisyMessageFilter(original_stderr)

    client = create_client(api_key=api_key, use_new_sdk=use_new_sdk)
    try:
        response = await asyncio.wait_for(
            client.generate_content_async(
                prompt=prompt + chunk,
                model_name=model_name,
                safety_settings=safety_settings,
            ),
            timeout=timeout_s,
        )

        if not response or not response.candidates:
            raise AIProcessorError(f"AI cleanup chunk {chunk_idx}/{total_chunks}: No candidates returned")

        if hasattr(response, "prompt_feedback") and response.prompt_feedback:
            if hasattr(response.prompt_feedback, "block_reason") and response.prompt_feedback.block_reason:
                raise AIProcessorError(f"AI cleanup chunk {chunk_idx}/{total_chunks}: Blocked by safety filter: {response.prompt_feedback.block_reason}")

        return response.text.strip()
    finally:
        try:
            await client.aclose()
        except Exception:
            pass

async def _ai_cleanup_parallel(
    text_chunks: List[str],
    api_keys: List[str],
    model_name: str,
    prompt: str,
    max_parallel: int,
    delay: float,
    show_progress: bool,
    timeout_s: float,
    max_retries: int,
    progress_interval: float,
    safety_settings: Optional[List[Dict[str, Any]]] = None,
    quota_cooldown_seconds: float = 60.0,
    key_manager: Any = None,
    phase_timeout_seconds: float = 3600.0,
) -> Tuple[str, int, int, List[int]]:
    """Xử lý song song nhiều chunks. phase_timeout_seconds: hết thời gian thì dừng phase, trả về phần đã xử lý."""
    key_queue: Optional[asyncio.Queue] = None
    if key_manager is None:
        key_queue = asyncio.Queue()
        for k in api_keys:
            await key_queue.put(k)

    semaphore = asyncio.Semaphore(max_parallel)
    total = len(text_chunks)
    failures = 0
    failed_indices: List[int] = []
    deadline_ts = time.time() + phase_timeout_seconds if phase_timeout_seconds > 0 else float("inf")

    async def _return_key_after_cooldown(k: str, sec: float) -> None:
        await asyncio.sleep(sec)
        if key_queue is not None:
            await key_queue.put(k)

    # Giới hạn số lần chờ key (tránh treo khi hết key): tối đa 20 lần ~ 30s
    max_no_key_waits = 20

    async def process_chunk(chunk: str, chunk_idx: int) -> Tuple[int, str]:
        nonlocal failures, failed_indices
        async with semaphore:
            retries = 0
            no_key_waits = 0
            api_key = None
            while retries < max_retries:
                if deadline_ts != float("inf") and time.time() > deadline_ts:
                    logger.warning(
                        f"AI Cleanup chunk {chunk_idx}: hết thời gian phase ({phase_timeout_seconds:.0f}s), bỏ qua chunk."
                    )
                    failures += 1
                    failed_indices.append(chunk_idx)
                    return (chunk_idx, chunk)
                return_key_to_pool = True
                try:
                    if key_manager is not None:
                        # [QUOTA GUARD] Check total health before waiting
                        active_keys = getattr(key_manager, "get_active_key_count", lambda: 1)()
                        if active_keys == 0:
                            logger.critical(f"AI Cleanup chunk {chunk_idx}: HỆ THỐNG DỪNG do không còn key khả dụng (Quota Exhausted/RPD).")
                            failures += 1
                            failed_indices.append(chunk_idx)
                            return (chunk_idx, chunk)

                        # [v9.1] get_available_key is async
                        api_key = await key_manager.get_available_key()
                        if not api_key:
                            no_key_waits += 1
                            if no_key_waits >= max_no_key_waits:
                                logger.warning(
                                    f"AI Cleanup chunk {chunk_idx}: không có key sau {max_no_key_waits} lần chờ, bỏ qua chunk."
                                )
                                failures += 1
                                failed_indices.append(chunk_idx)
                                return (chunk_idx, chunk)
                            if no_key_waits == 1 or no_key_waits % 5 == 0:
                                quota_summary = key_manager.get_quota_status_summary() if hasattr(key_manager, "get_quota_status_summary") else {}
                                wait_reason = "Quota/RPM Limit"
                                if quota_summary.get("available_keys", 1) == 0:
                                    wait_reason = "Hết Quota ngày (RPD) hoặc Rate Limit"
                                logger.info(
                                    f"AI Cleanup: đang chờ key khả dụng ({wait_reason})... (chunk {chunk_idx}, lần chờ {no_key_waits}/{max_no_key_waits})"
                                )
                            await asyncio.sleep(min(delay * (no_key_waits + 1), 15.0))
                            continue
                    else:
                        api_key = await key_queue.get()
                    
                    # Log key allocation
                    masked_key = key_manager._mask_key(api_key) if hasattr(key_manager, "_mask_key") else ("..." + api_key[-4:] if api_key else "None")
                    logger.info(f"AI Cleanup [ALLOC]: Chunk #{chunk_idx} sử dụng Key {masked_key}")

                    cleaned = await _cleanup_chunk_async(
                        chunk, api_key, model_name, prompt, chunk_idx, len(text_chunks), timeout_s, safety_settings
                    )
                    if key_manager and api_key:
                        await key_manager.return_key(_WORKER_ID_AI_CLEANUP, api_key, is_error=False)
                        logger.debug(f"AI Cleanup [SUCCESS]: Trả Key {masked_key} sau khi hoàn tất Chunk #{chunk_idx}")
                    return (chunk_idx, cleaned)
                except Exception as e:
                    err_msg = str(e).upper()
                    masked_key = key_manager._mask_key(api_key) if (hasattr(key_manager, "_mask_key") and api_key) else ("..." + api_key[-4:] if api_key else "None")
                    if key_manager and api_key:
                        err_type = key_manager.handle_exception(api_key, e) if hasattr(key_manager, "handle_exception") else "generation_error"
                        await key_manager.return_key(_WORKER_ID_AI_CLEANUP, api_key, is_error=True, error_type=err_type, error_message=str(e))
                        logger.warning(f"AI Cleanup [ERROR]: Key {masked_key} lỗi tại Chunk #{chunk_idx} ({err_type}).")
                        api_key = None
                    elif "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                        return_key_to_pool = False
                        logger.warning(
                            f"AI Cleanup chunk {chunk_idx}: key 429/RESOURCE_EXHAUSTED, đưa key vào cooldown {quota_cooldown_seconds:.0f}s."
                        )
                        if api_key:
                            asyncio.create_task(_return_key_after_cooldown(api_key, quota_cooldown_seconds))
                        api_key = None
                    retries += 1
                    if retries < max_retries:
                        await asyncio.sleep(delay * retries)
                    else:
                        failures += 1
                        failed_indices.append(chunk_idx)
                        return (chunk_idx, chunk)
                finally:
                    if api_key and return_key_to_pool and key_queue is not None:
                        await key_queue.put(api_key)
                    await asyncio.sleep(delay)
            return (chunk_idx, chunk)

    tasks = [process_chunk(chunk, idx) for idx, chunk in enumerate(text_chunks)]
    results = []
    if show_progress:
        start_ts = time.time()
        last_log = start_ts
        completed = 0
        async for res in _as_completed_iter(tasks):
            results.append(res)
            completed += 1
            now = time.time()
            if (now - last_log) >= max(5.0, progress_interval):
                elapsed = now - start_ts
                avg = elapsed / completed if completed > 0 else 0.0
                remaining = max(len(tasks) - completed, 0) * avg
                logger.info(f"AI Cleanup: {completed}/{len(tasks)} chunks \u2022 TB {avg:.2f}s/chunk \u2022 ETA ~{remaining:.0f}s")
                last_log = now
    else:
        results = await asyncio.gather(*tasks)

    cleaned_chunks = sorted(results, key=lambda x: x[0])
    result_text = "\n\n".join([text for _, text in cleaned_chunks])
    return (result_text, total - failures, failures, failed_indices)

# Worker ID dùng cho quy trình phụ khi dùng key_manager chung (tránh trùng với translation workers)
_WORKER_ID_AI_CLEANUP = 998
_WORKER_ID_SPELL_CHECK = 997


async def ai_cleanup_text(
    text: str, ocr_cfg: Dict[str, Any], key_manager: Any = None
) -> Tuple[str, List[int], List[str]]:
    """Sử dụng AI để dọn rác text. Nếu key_manager được truyền thì dùng chung quản lý key với quy trình chính."""
    cleanup_cfg = ocr_cfg.get("ai_cleanup", {})
    if not cleanup_cfg.get("enabled", False):
        return text, [], []

    api_keys = cleanup_cfg.get("api_keys", []) or ocr_cfg.get("_root_api_keys", [])
    if key_manager is not None:
        api_keys = getattr(key_manager, "api_keys", api_keys) or api_keys
    if not api_keys:
        logger.warning("AI cleanup enabled nhưng không có API keys. Bỏ qua.")
        return text, [], []

    model_name = cleanup_cfg.get("model", "gemini-2.5-flash")
    chunk_size = cleanup_cfg.get("chunk_size", 50000)
    max_parallel = min(cleanup_cfg.get("max_parallel_workers", 5), len(api_keys))
    delay = cleanup_cfg.get("delay_between_requests", 0.5)
    timeout_s = float(cleanup_cfg.get("ai_timeout_seconds", 120))
    max_retries = cleanup_cfg.get("max_retries", 3)
    show_progress = bool(ocr_cfg.get("show_progress", True))
    progress_interval = float(ocr_cfg.get("progress_log_interval_seconds", 60))

    raw_lang = ocr_cfg.get("lang", "vie")
    normalized_lang = _normalize_lang_code(raw_lang)
    is_chinese = "chi" in normalized_lang.lower()

    if is_chinese:
        prompt = """Bạn là một AI chuyên dọn dẹp văn bản OCR/scan tiếng Trung. Nhiệm vụ:

1. LOẠI BỎ HEADER/FOOTER/PAGE NUMBER:
   - Xóa header/footer lặp lại ở mỗi trang
   - Xóa số trang (ví dụ: "22", "二668", "/", "8300a")
   - Xóa watermark, logo

2. LOẠI BỎ KÝ TỰ RÁC VÀ NOISE:
   - Xóa các ký tự đơn lẻ vô nghĩa (ví dụ: "色", "只", "呆", "At", "XY", "G", "Ca", "Li", "ee", "AA", "ba", "yy")
   - Xóa các ký tự Latin lạc vào (ví dụ: "we", "Ms", "es", "rs", "xx", "KW", "sg", "ecC", "it", "oo", "oo0r")
   - Xóa các ký tự đặc biệt không phải tiếng Trung (ví dụ: "<S", "]", "[", "(", ")", "~", "|", "/", "\\", "*", "#", "?", "!")
   - Xóa các số đơn lẻ không có ngữ cảnh (ví dụ: "1", "2", "3", "4", "5", "6", "7", "8", "9", "0")
   - Xóa các chuỗi ký tự lặp lại vô nghĩa (ví dụ: "eeeeeeee", "2222222222", "oooooo", "aaaaaa")

3. SỬA LỖI OCR PHỔ BIẾN:
   - Sửa các ký tự bị nhận dạng sai do OCR (ví dụ: "騙" → "編", "納" → "綱", "忠" → "臨", "准" → "瘡")
   - Sửa các ký tự bị thiếu nét hoặc thừa nét
   - Sửa các ký tự bị nhầm lẫn (ví dụ: "門" → "陽", "示" → "強", "淹" → "陰", "泗" → "燥", "蒸" → "濕")
   - Giữ nguyên các ký tự đúng, không sửa nhầm

4. CHUẨN HÓA ĐỊNH DẠNG:
   - Loại bỏ khoảng trắng thừa giữa các từ
   - Giữ nguyên khoảng trắng giữa các câu và đoạn văn
   - Giữ nguyên định dạng đoạn văn (paragraph breaks)
   - Loại bỏ các dòng trống thừa

5. BẢO TOÀN NỘI DUNG:
   - TUYỆT ĐỐI KHÔNG xóa nội dung chính (tên thuốc, công dụng, tính chất, v.v.)
   - KHÔNG thay đổi ý nghĩa của văn bản
   - GIỮ NGUYÊN các số liệu, ngày tháng, địa chỉ quan trọng
   - GIỮ NGUYÊN tên riêng, thuật ngữ y học

QUY TẮC QUAN TRỌNG:
- Nếu không chắc chắn một ký tự có phải là rác hay không, HÃY GIỮ LẠI
- Ưu tiên bảo toàn nội dung hơn là xóa sạch mọi thứ
- Chỉ xóa những gì RÕ RÀNG là rác hoặc noise

Trả về chỉ văn bản đã được dọn dẹp, không giải thích thêm.

Văn bản cần dọn dẹp:
"""
    else:
        prompt = """Bạn là một AI chuyên dọn dẹp văn bản OCR/scan. Nhiệm vụ:
1. Loại bỏ header/footer lặp lại ở mỗi trang
2. Loại bỏ các ký tự rác, vệt đen vô nghĩa từ quá trình scan
3. Loại bỏ số trang, watermark
4. Giữ nguyên nội dung chính của văn bản
5. Chuẩn hóa khoảng trắng thừa
6. Giữ nguyên định dạng đoạn văn

Trả về chỉ văn bản đã được dọn dẹp, không giải thích thêm.

Văn bản cần dọn dẹp:
"""

    safety_settings = _build_safety_settings(ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH"))
    
    if len(text) <= chunk_size:
        # Xử lý đơn giản cho text ngắn
        # [v9.1] get_available_key is async
        key = await key_manager.get_available_key() if key_manager else None
        if key is None and key_manager is None:
            key = api_keys[0] if api_keys else None
        if key is None:
            logger.warning("Không lấy được key cho AI cleanup (short path).")
            return text, [0], [text]
        cleanup_failed = False
        err_type, err_msg = "generation_error", ""
        try:
            client = create_client(api_key=key, use_new_sdk=True)
            response = await client.generate_content_async(prompt=prompt + text, model_name=model_name, safety_settings=safety_settings)
            return response.text.strip(), [], [text]
        except Exception as e:
            logger.error(f"AI cleanup failed: {e}")
            cleanup_failed = True
            err_type = key_manager.handle_exception(key, e) if (key_manager and hasattr(key_manager, "handle_exception")) else "generation_error"
            err_msg = str(e)
            return text, [0], [text]
        finally:
            if key_manager and key:
                await key_manager.return_key(_WORKER_ID_AI_CLEANUP, key, is_error=cleanup_failed, error_type=err_type, error_message=err_msg)

    quota_cooldown_s = float(cleanup_cfg.get("quota_cooldown_seconds", 60))
    # Timeout toàn phase: tránh treo hàng giờ khi hết key / 429 liên tục (mặc định 1h)
    phase_timeout_s = float(cleanup_cfg.get("ai_cleanup_phase_timeout_seconds", 3600))
    if phase_timeout_s > 0:
        logger.info(f"AI Cleanup: timeout toàn phase = {phase_timeout_s:.0f}s (quá thời gian sẽ trả về phần đã xử lý).")
    text_chunks = _split_text_at_sentence_boundaries(text, chunk_size)
    result_text, success, failures, failed_indices = await _ai_cleanup_parallel(
        text_chunks, api_keys, model_name, prompt, max_parallel, delay, show_progress, timeout_s, max_retries, progress_interval, safety_settings, quota_cooldown_s, key_manager=key_manager, phase_timeout_seconds=phase_timeout_s
    )

    if failures > 0:
        logger.warning(
            f"AI Cleanup: {success}/{len(text_chunks)} chunks thành công, {failures} thất bại (429/key exhausted/timeout). Các chunk lỗi giữ nguyên bản gốc."
        )
    # Chỉ retry khi tỷ lệ thất bại không quá cao (tránh gọi thêm hàng loạt request → 429 spam)
    max_failures_for_retry = max(1, len(text_chunks) // 3)
    do_retry = (
        failures > 0
        and cleanup_cfg.get("auto_retry_failed", True)
        and (failures <= max_failures_for_retry)
    )
    if not do_retry and failures > 0 and cleanup_cfg.get("auto_retry_failed", True):
        logger.info(
            f"AI Cleanup: bỏ qua retry (thất bại {failures} > ngưỡng {max_failures_for_retry}, tránh 429 thêm)."
        )
    if do_retry and key_manager is not None:
        active = getattr(key_manager, "get_active_key_count", lambda: len(api_keys))()
        total_keys = len(api_keys)
        if total_keys and active < max(5, total_keys // 4):
            do_retry = False
            logger.info(
                f"AI Cleanup: bỏ qua retry {failures} chunk (chỉ còn {active}/{total_keys} key active, tránh 429 thêm)."
            )
    if do_retry:
        retry_results, still_failed = await _retry_failed_chunks_cleanup(failed_indices, text_chunks, api_keys, model_name, prompt, ocr_cfg)
        if retry_results:
            chunks_list = list(text_chunks)
            for idx, retry_text in retry_results.items():
                if idx < len(chunks_list): chunks_list[idx] = retry_text
            result_text = "\n\n".join(chunks_list)
            failed_indices = still_failed

    return result_text, failed_indices, text_chunks

async def _spell_check_chunk_async(
    chunk: str, api_key: str, model_name: str, prompt: str, chunk_idx: int, total_chunks: int, timeout_s: float, safety_settings: Optional[List[Dict[str, Any]]] = None, use_new_sdk: bool = True
) -> str:
    """Soát lỗi chính tả bằng AI (async)."""
    _suppress_google_logs()
    client = create_client(api_key=api_key, use_new_sdk=use_new_sdk)
    try:
        response = await asyncio.wait_for(
            client.generate_content_async(prompt=prompt + chunk, model_name=model_name, safety_settings=safety_settings),
            timeout=timeout_s
        )
        return response.text.strip()
    finally:
        try: await client.aclose()
        except Exception: pass

async def _ai_spell_check_parallel(
    text_chunks: List[str],
    api_keys: List[str],
    model_name: str,
    prompt: str,
    max_parallel: int,
    delay: float,
    show_progress: bool,
    timeout_s: float,
    max_retries: int,
    progress_interval: float,
    safety_settings: Optional[List[Dict[str, Any]]] = None,
    key_manager: Any = None,
    phase_timeout_seconds: float = 0.0,
) -> Tuple[str, int, int, List[int]]:
    """Xử lý song song nhiều chunks cho spell check. Nếu key_manager có: dùng get_available_key/return_key chung."""
    key_queue: Optional[asyncio.Queue] = None
    if key_manager is None:
        key_queue = asyncio.Queue()
        for k in api_keys:
            await key_queue.put(k)
    semaphore = asyncio.Semaphore(max_parallel)
    total, failures, failed_indices = len(text_chunks), 0, []
    deadline_ts = (time.time() + phase_timeout_seconds) if phase_timeout_seconds > 0 else float("inf")
    max_no_key_waits = 20

    async def process_chunk(chunk: str, chunk_idx: int) -> Tuple[int, str]:
        nonlocal failures, failed_indices
        async with semaphore:
            retries = 0
            no_key_waits = 0
            api_key = None
            while retries < max_retries:
                if deadline_ts != float("inf") and time.time() > deadline_ts:
                    logger.warning(
                        f"AI Soát lỗi chính tả chunk {chunk_idx}: hết thời gian phase ({phase_timeout_seconds:.0f}s), bỏ qua chunk."
                    )
                    failures += 1
                    failed_indices.append(chunk_idx)
                    return (chunk_idx, chunk)
                if key_manager is not None:
                    # [QUOTA GUARD] Check total health before waiting
                    active_keys = getattr(key_manager, "get_active_key_count", lambda: 1)()
                    if active_keys == 0:
                        logger.critical(f"AI Soát lỗi chính tả chunk {chunk_idx}: HỆ THỐNG DỪNG do không còn key khả dụng (Quota Exhausted/RPD).")
                        failures += 1
                        failed_indices.append(chunk_idx)
                        return (chunk_idx, chunk)

                    # [v9.1] get_available_key is async
                    api_key = await key_manager.get_available_key()
                    if not api_key:
                        no_key_waits += 1
                        if no_key_waits >= max_no_key_waits:
                            logger.warning(
                                f"AI Soát lỗi chính tả chunk {chunk_idx}: không có key sau {max_no_key_waits} lần chờ, bỏ qua chunk."
                            )
                            failures += 1
                            failed_indices.append(chunk_idx)
                            return (chunk_idx, chunk)
                        if no_key_waits == 1 or no_key_waits % 5 == 0:
                            quota_summary = key_manager.get_quota_status_summary() if hasattr(key_manager, "get_quota_status_summary") else {}
                            wait_reason = "Quota/RPM Limit"
                            if quota_summary.get("available_keys", 1) == 0:
                                wait_reason = "Hết Quota ngày (RPD) hoặc Rate Limit"
                            logger.info(
                                f"AI Soát lỗi chính tả: đang chờ key khả dụng ({wait_reason})... (chunk {chunk_idx}, lần chờ {no_key_waits}/{max_no_key_waits})"
                            )
                        await asyncio.sleep(min(delay * (no_key_waits + 1), 15.0))
                        continue
                else:
                    api_key = await key_queue.get()
                
                # Log key allocation
                masked_key = key_manager._mask_key(api_key) if hasattr(key_manager, "_mask_key") else ("..." + api_key[-4:] if api_key else "None")
                logger.info(f"AI Soát lỗi [ALLOC]: Chunk #{chunk_idx} sử dụng Key {masked_key}")

                try:
                    res = await _spell_check_chunk_async(chunk, api_key, model_name, prompt, chunk_idx, total, timeout_s, safety_settings)
                    if key_manager and api_key:
                        await key_manager.return_key(_WORKER_ID_SPELL_CHECK, api_key, is_error=False)
                        logger.debug(f"AI Soát lỗi [SUCCESS]: Trả Key {masked_key} sau khi hoàn tất Chunk #{chunk_idx}")
                    return (chunk_idx, res)
                except Exception as e:
                    masked_key = key_manager._mask_key(api_key) if (hasattr(key_manager, "_mask_key") and api_key) else ("..." + api_key[-4:] if api_key else "None")
                    if key_manager and api_key:
                        err_type = key_manager.handle_exception(api_key, e) if hasattr(key_manager, "handle_exception") else "generation_error"
                        await key_manager.return_key(_WORKER_ID_SPELL_CHECK, api_key, is_error=True, error_type=err_type, error_message=str(e))
                        logger.warning(f"AI Soát lỗi [ERROR]: Key {masked_key} lỗi tại Chunk #{chunk_idx} ({err_type}).")
                    api_key = None
                    retries += 1
                    if retries < max_retries:
                        await asyncio.sleep(delay * retries)
                finally:
                    if key_manager is None and api_key:
                        await key_queue.put(api_key)
                    await asyncio.sleep(delay)
            failures += 1
            failed_indices.append(chunk_idx)
            return (chunk_idx, chunk)

    tasks = [process_chunk(chunk, idx) for idx, chunk in enumerate(text_chunks)]
    results = []
    if show_progress:
        async for r in _as_completed_iter(tasks): results.append(r)
    else:
        results = await asyncio.gather(*tasks)
    
    processed = sorted(results, key=lambda x: x[0])
    return "\n\n".join([t for _, t in processed]), total - failures, failures, failed_indices

async def ai_spell_check_and_paragraph_restore(
    text: str, ocr_cfg: Dict[str, Any], key_manager: Any = None
) -> Tuple[str, List[int], List[str]]:
    """Sử dụng AI để soát lỗi chính tả. Nếu key_manager được truyền thì dùng chung quản lý key với quy trình chính."""
    cfg = ocr_cfg.get("ai_spell_check", {})
    if not cfg.get("enabled", False): return text, [], []
    
    api_keys = cfg.get("api_keys", []) or ocr_cfg.get("_root_api_keys", [])
    if key_manager is not None:
        api_keys = getattr(key_manager, "api_keys", api_keys) or api_keys
    if not api_keys: return text, [], []

    model_name = cfg.get("model", "gemini-2.5-flash")
    chunk_size = cfg.get("chunk_size", 50000)
    max_parallel = min(cfg.get("max_parallel_workers", 5), len(api_keys))
    timeout_s = float(cfg.get("ai_timeout_seconds", 120))
    show_progress = bool(ocr_cfg.get("show_progress", True))
    
    raw_lang = ocr_cfg.get("lang", "vie")
    normalized_lang = _normalize_lang_code(raw_lang)
    is_chinese = "chi" in normalized_lang.lower()

    if is_chinese:
        prompt = """Bạn là một AI chuyên soát lỗi chính tả và phục hồi cấu trúc văn bản OCR tiếng Trung. Nhiệm vụ chính của bạn là PHÂN TÍCH NGỮ CẢNH và SỬA LỖI OCR.

=== NHIỆM VỤ CHÍNH: SỬA LỖI OCR TIẾNG TRUNG (Ưu tiên cao nhất) ===

Bạn cần ĐỌC KỸ NỘI DUNG và SỬA các lỗi OCR phổ biến:

A. SỬA LỖI KÝ TỰ BỊ NHẬN DẠNG SAI:
   - Các ký tự có hình dạng tương tự bị nhầm lẫn:
     * "騙" → "編" (biên soạn)
     * "納" → "綱" (cương mục)
     * "忠" → "臨" (lâm sàng)
     * "准" → "瘡" (sang độc)
     * "門" → "陽" (dương)
     * "示" → "強" (cường)
     * "淹" → "陰" (âm)
     * "泗" → "燥" (táo)
     * "蒸" → "濕" (thấp)
     * "寐" → "霖" (lâm)
     * "語" → "醫" (y)
     * "間" → "藥" (dược)
     * "生" → "物" (vật)
   
   - Các ký tự bị thiếu nét hoặc thừa nét do OCR
   - Các ký tự bị nhầm giữa giản thể và phồn thể (nếu cần)

B. SỬA LỖI TỪ VỰNG:
   - Sửa các từ bị nhận dạng sai thành từ đúng trong ngữ cảnh
   - Ví dụ: "察中有本草" → có thể là "本草綱目" (nếu ngữ cảnh phù hợp)
   - Ví dụ: "原色圖譜六22" → "原色圖譜" (xóa số lạc vào)
   - Ví dụ: "閃1過" → "閃過" hoặc xóa nếu không có nghĩa

C. PHỤC HỒI CẤU TRÚC VĂN BẢN:
   - Nối các câu bị ngắt do layout phức tạp (2 cột)
   - Giữ nguyên paragraph breaks hợp lý
   - Loại bỏ các dòng trống thừa

=== CÁC NHIỆM VỤ KHÁC ===

1. BẢO VỆ TOÀN VẸN NỘI DUNG:
   - TUYỆT ĐỐI KHÔNG thay đổi ý nghĩa của văn bản
   - KHÔNG thêm, bớt, hoặc diễn giải lại nội dung
   - KHÔNG thay đổi thứ tự từ trong câu
   - GIỮ NGUYÊN tên thuốc, công dụng, tính chất, liều lượng
   - GIỮ NGUYÊN số liệu, ngày tháng, địa chỉ
2. PHỤC HỒI CẤU TRÚC PARAGRAPH:
   - Sau khi sửa lỗi OCR, xác định các ngắt đoạn hợp lý
   - Mỗi đoạn văn nên có một ý chính hoàn chỉnh
   - Giữ nguyên các dòng trống giữa các đoạn đã được xác định là có chủ đích
   - Đảm bảo các câu trong một đoạn có liên quan với nhau

3. ĐỊNH DẠNG:
   - Giữ nguyên các dấu câu quan trọng (，。、；：！？)
   - Chuẩn hóa khoảng trắng thừa giữa các từ (nhưng không thay đổi paragraph breaks hợp lý)
   - Đảm bảo mỗi câu kết thúc bằng dấu câu thích hợp

=== NGUYÊN TẮC QUAN TRỌNG ===

- SỬ DỤNG SỨC MẠNH PHÂN TÍCH NGỮ CẢNH: Đọc và hiểu nội dung y học, không chỉ dựa vào quy tắc cú pháp
- QUYẾT ĐỊNH THÔNG MINH: Mỗi quyết định sửa hay không sửa phải dựa trên phân tích ngữ cảnh cụ thể
- NHẤT QUÁN: Áp dụng cùng một tiêu chuẩn phân tích cho toàn bộ văn bản
- BẢO TOÀN Ý NGHĨA: Chỉ sửa lỗi OCR, KHÔNG thay đổi nội dung hoặc ý nghĩa
- NẾU KHÔNG CHẮC CHẮN: Hãy giữ nguyên ký tự gốc, không sửa nhầm

Trả về chỉ văn bản đã được soát và sửa lỗi OCR, không giải thích thêm.

Văn bản cần phân tích và xử lý:
"""
    else:
        prompt = """Bạn là một AI chuyên soát lỗi chính tả và phục hồi cấu trúc văn bản OCR. Nhiệm vụ chính của bạn là PHÂN TÍCH NGỮ CẢNH và QUYẾT ĐỊNH THÔNG MINH.

=== NHIỆM VỤ CHÍNH: PHÂN TÍCH VÀ PHỤC HỒI CÂU BỊ NGẮT (Ưu tiên cao nhất) ===

Bạn cần ĐỌC KỸ NỘI DUNG và PHÂN TÍCH để phân biệt:

A. CÂU BỊ NGẮT DO CONVERT PDF → TXT (CẦN NỐI LẠI):
   - Đọc ngữ cảnh: Nếu dòng trước chưa hoàn thành ý và dòng sau tiếp nối ý đó → nối lại
   - Ví dụ: 
     * "Our client is also the owner of Vietnam Trade Mark Registration No. 315843 for "MICROBAN"
       in Class 5 covering..." 
     → Phân tích: "in Class 5" tiếp nối câu trước → NỐI LẠI thành một câu
   
   - Dấu hiệu cần nối:
     * Dòng trước không kết thúc bằng dấu câu (. ! ?) HOẶC kết thúc bằng dấu phẩy, hai chấm
     * Dòng sau bắt đầu bằng chữ thường (tiếp nối câu trước)
     * Nội dung dòng sau về mặt ngữ pháp và ngữ nghĩa là phần tiếp theo của câu trước
     * Đọc toàn bộ ngữ cảnh để hiểu rõ mối quan hệ

B. NGẮT PARAGRAPH CÓ CHỦ ĐÍCH (KHÔNG NỐI):
   - Đọc ngữ cảnh: Nếu dòng sau là ý mới, chủ đề mới, hoặc đoạn văn mới → KHÔNG nối
   - Ví dụ:
     * "...attached as Exhibit 1.
       
       Khách hàng của chúng tôi là chủ sở hữu..."
     → Phân tích: Đây là đoạn mới (chuyển từ tiếng Anh sang tiếng Việt) → KHÔNG NỐI
   
   - Dấu hiệu KHÔNG nối:
     * Dòng trước kết thúc bằng dấu chấm (. ! ?) và dòng sau bắt đầu bằng chữ hoa
     * Dòng sau là câu đầu tiên của một đoạn mới (ý tưởng mới, chủ đề mới)
     * Có sự thay đổi rõ ràng về ngữ cảnh (ví dụ: chuyển từ phần này sang phần khác)
     * Đọc toàn bộ ngữ cảnh để xác định đây là ngắt đoạn có chủ đích

QUY TRÌNH PHÂN TÍCH:
1. ĐỌC toàn bộ văn bản để hiểu cấu trúc và ngữ cảnh
2. PHÂN TÍCH từng vị trí ngắt dòng:
   - Xem xét nội dung trước và sau dòng ngắt
   - Đánh giá mối quan hệ ngữ pháp và ngữ nghĩa
   - Xác định đây là câu bị ngắt hay ngắt đoạn có chủ đích
3. QUYẾT ĐỊNH:
   - Nếu là câu bị ngắt → NỐI lại (thay line break bằng space)
   - Nếu là ngắt đoạn có chủ đích → GIỮ NGUYÊN (có thể thêm dòng trống nếu cần)
4. ÁP DỤNG nhất quán cho toàn bộ văn bản

=== CÁC NHIỆM VỤ KHÁC ===

1. SOÁT LỖI CHÍNH TẢ:
   - Sửa các lỗi chính tả do OCR (ví dụ: "Kíng" → "Kính", "hang" → "hàng")
   - Sửa các lỗi chính tả thông thường
   - KHÔNG thay đổi từ ngữ chuyên ngành, tên riêng, địa danh
   - KHÔNG thay đổi số liệu, ngày tháng, địa chỉ

2. PHỤC HỒI CẤU TRÚC PARAGRAPH:
   - Sau khi đã nối các câu bị ngắt, xác định các ngắt đoạn hợp lý
   - Mỗi đoạn văn nên có một ý chính hoàn chỉnh
   - Giữ nguyên các dòng trống giữa các đoạn đã được xác định là có chủ đích
   - Đảm bảo các câu trong một đoạn có liên quan với nhau

3. BẢO VỆ TOÀN VẸN NỘI DUNG:
   - TUYỆT ĐỐI KHÔNG thay đổi ý nghĩa của văn bản
   - KHÔNG thêm, bớt, hoặc diễn giải lại nội dung
   - KHÔNG thay đổi thứ tự từ trong câu (chỉ nối lại khi cần)
   - GIỮ NGUYÊN định dạng đặc biệt (bullet points, numbered lists, bảng)
   - GIỮ NGUYÊN các từ viết hoa nếu chúng là tên riêng, thuật ngữ

4. ĐỊNH DẠNG:
   - Giữ nguyên định dạng văn bản song ngữ (nếu có)
   - Giữ nguyên các dấu câu quan trọng
   - Chuẩn hóa khoảng trắng thừa giữa các từ (nhưng không thay đổi paragraph breaks hợp lý)
   - Đảm bảo mỗi câu kết thúc bằng dấu câu thích hợp

=== NGUYÊN TẮC QUAN TRỌNG ===

- SỬ DỤNG SỨC MẠNH PHÂN TÍCH NGỮ CẢNH: Đọc và hiểu nội dung, không chỉ dựa vào quy tắc cú pháp
- QUYẾT ĐỊNH THÔNG MINH: Mỗi quyết định nối hay không nối phải dựa trên phân tích ngữ cảnh cụ thể
- NHẤT QUÁN: Áp dụng cùng một tiêu chuẩn phân tích cho toàn bộ văn bản
- BẢO TOÀN Ý NGHĨA: Chỉ điều chỉnh cấu trúc, KHÔNG thay đổi nội dung hoặc ý nghĩa

Trả về chỉ văn bản đã được soát và phục hồi, không giải thích thêm.

Văn bản cần phân tích và xử lý:
"""
    safety_settings = _build_safety_settings(ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH"))
    phase_timeout_s = float(cfg.get("phase_timeout_seconds", 3600))
    if phase_timeout_s > 0:
        logger.info(f"AI Soát lỗi chính tả: timeout toàn phase = {phase_timeout_s:.0f}s (quá thời gian sẽ trả về phần đã xử lý).")

    text_chunks = _split_text_at_sentence_boundaries(text, chunk_size)
    result_text, success, failures, failed_indices = await _ai_spell_check_parallel(
        text_chunks, api_keys, model_name, prompt, max_parallel, 0.5, show_progress, timeout_s, 3, 60, safety_settings, key_manager=key_manager, phase_timeout_seconds=phase_timeout_s
    )

    if failures > 0 and cfg.get("auto_retry_failed", True):
        retry_results, still_failed = await _retry_failed_chunks_spell_check(failed_indices, text_chunks, api_keys, model_name, prompt, ocr_cfg)
        if retry_results:
            chunks_list = list(text_chunks)
            for idx, retry_text in retry_results.items():
                if idx < len(chunks_list): chunks_list[idx] = retry_text
            result_text = "\n\n".join(chunks_list)
            failed_indices = still_failed

    return result_text, failed_indices, text_chunks

async def _retry_failed_chunks_cleanup(failed_indices: List[int], all_chunks: List[str], api_keys: List[str], model_name: str, prompt: str, ocr_cfg: Dict[str, Any]) -> Tuple[Dict[int, str], List[int]]:
    """Retry các chunk failed cho AI Cleanup."""
    if not failed_indices: return {}, []
    safety_settings = _build_safety_settings(ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH"))
    timeout_s = float(ocr_cfg.get("ai_cleanup", {}).get("ai_timeout_seconds", 240))
    
    results = {}
    for idx in failed_indices:
        chunk = all_chunks[idx]
        for key in api_keys:
            try:
                res = await _cleanup_chunk_async(chunk, key, model_name, prompt, idx, len(failed_indices), timeout_s, safety_settings)
                results[idx] = res
                break
            except Exception: continue
        if idx not in results: results[idx] = chunk
    
    retry_dict = results
    still_failed = [i for i in failed_indices if retry_dict[i] == all_chunks[i]]
    return retry_dict, still_failed

async def _retry_failed_chunks_spell_check(failed_indices: List[int], all_chunks: List[str], api_keys: List[str], model_name: str, prompt: str, ocr_cfg: Dict[str, Any]) -> Tuple[Dict[int, str], List[int]]:
    """Retry các chunk failed cho AI Spell Check."""
    if not failed_indices: return {}, []
    safety_settings = _build_safety_settings(ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH"))
    timeout_s = float(ocr_cfg.get("ai_spell_check", {}).get("ai_timeout_seconds", 240))
    
    results = {}
    for idx in failed_indices:
        chunk = all_chunks[idx]
        for key in api_keys:
            try:                   
                res = await _spell_check_chunk_async(chunk, key, model_name, prompt, idx, len(failed_indices), timeout_s, safety_settings)
                results[idx] = res
                break
            except Exception: continue
        if idx not in results: results[idx] = chunk
    
    retry_dict = results
    still_failed = [i for i in failed_indices if retry_dict[i] == all_chunks[i]]
    return retry_dict, still_failed
