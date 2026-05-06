from . import config
from .config import _build_safety_settings, NoisyMessageFilter, _suppress_google_logs

def build_cleanup_prompt_with_hints(text: str, hints: dict) -> str:
    """
    Build cleanup prompt với format hints chi tiết.
    
    Args:
        text: Paragraph text
        hints: Format hints dict
    
    Returns:
        str: Prompt với hints
    """
    hint_descriptions = []
    
    # Style hints
    style = hints.get("style", "")
    if style.startswith("Heading"):
        hint_descriptions.append(f"Style: {style} (có thể là header/title)")
    elif style == "Normal":
        hint_descriptions.append("Style: Normal (nội dung chính)")
    
    # Font size hints
    font_size = hints.get("font_size")
    if font_size:
        if font_size < 10:
            hint_descriptions.append(f"Font rất nhỏ ({font_size}pt) - có thể là footer/page number")
        elif font_size > 14:
            hint_descriptions.append(f"Font lớn ({font_size}pt) - có thể là header/title")
    
    # Bold hints
    if hints.get("is_bold"):
        hint_descriptions.append("Bold - có thể là header/title")
    
    # Position hints
    position = hints.get("position_hint", "middle")
    if position == "top":
        hint_descriptions.append("Vị trí: Đầu trang - có thể là header")
    elif position == "bottom":
        hint_descriptions.append("Vị trí: Cuối trang - có thể là footer/page number")
    
    # Alignment hints
    alignment = hints.get("alignment", "left")
    if alignment == "center":
        hint_descriptions.append("Căn giữa - có thể là title/header")
    
    prompt = f"""Bạn là AI chuyên dọn dẹp văn bản OCR/scan.

THÔNG TIN FORMATTING:
{chr(10).join('- ' + d for d in hint_descriptions) if hint_descriptions else '- Không có thông tin đặc biệt'}

Dựa trên formatting này, xác định:
- Nếu là header/footer/page number → XÓA
- Nếu là nội dung chính → GIỮ LẠI và cleanup noise

Nhiệm vụ:
1. Loại bỏ header/footer lặp lại ở mỗi trang
2. Loại bỏ số trang, watermark
3. Loại bỏ các ký tự rác, vệt đen vô nghĩa từ quá trình scan
4. Chuẩn hóa khoảng trắng thừa
5. Giữ nguyên nội dung chính của văn bản
6. Giữ nguyên định dạng đoạn văn

Trả về chỉ văn bản đã được dọn dẹp, không giải thích thêm.

Văn bản cần dọn dẹp:
{text}"""
    
    return prompt

def cleanup_paragraph_with_hints(para_data: dict, ocr_cfg: dict) -> dict:
    """
    Cleanup một paragraph/batch với format hints.
    
    Args:
        para_data: Paragraph dict với type "single" hoặc "batch"
        ocr_cfg: Config dictionary
    
    Returns:
        dict: {
            "cleaned_text": str,
            "should_merge_with_next": bool  # Nếu AI merge với paragraph sau
        }
    """
    cleanup_cfg = ocr_cfg.get("ai_cleanup", {})
    if not cleanup_cfg.get("enabled", False):
        return {
            "cleaned_text": para_data["text"],
            "should_merge_with_next": False
        }
    
    # Get API keys
    api_keys = cleanup_cfg.get("api_keys", [])
    if not api_keys:
        api_keys = ocr_cfg.get("_root_api_keys", [])
    if not api_keys:
        logger.warning("Không có API keys cho cleanup, bỏ qua")
        return {
            "cleaned_text": para_data["text"],
            "should_merge_with_next": False
        }
    
    model_name = cleanup_cfg.get("model", "gemini-2.5-flash")
    timeout_s = cleanup_cfg.get("timeout", 60.0)
    
    # Get safety settings
    safety_level = cleanup_cfg.get("safety_level") or ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
    safety_settings = _build_safety_settings(safety_level)
    
    # Build prompt với hints
    text = para_data["text"]
    hints = para_data.get("hints", {})
    prompt = build_cleanup_prompt_with_hints(text, hints)
    
    # Call AI cleanup (dùng async function)
    try:
        # Use first API key (có thể parallelize sau nếu cần)
        cleaned_text = asyncio.run(_cleanup_chunk_async(
            text, api_keys[0], model_name, prompt, 0, 1, timeout_s, safety_settings
        ))
        
        # Simple heuristic: Nếu cleaned text ngắn hơn nhiều → có thể đã merge hoặc xóa
        # Không có cách chính xác để detect merge, tạm thời return False
        # Có thể cải thiện bằng cách prompt AI explicit về merge
        
        return {
            "cleaned_text": cleaned_text,
            "should_merge_with_next": False  # TODO: Implement merge detection
        }
    except Exception as e:
        logger.warning(f"Cleanup paragraph thất bại: {e}")
        return {
            "cleaned_text": text,
            "should_merge_with_next": False
        }

def spell_check_paragraph(para_data: dict, ocr_cfg: dict) -> str:
    """
    Spell check một paragraph/batch.
    
    Args:
        para_data: Paragraph dict (có thể là processed sau cleanup)
        ocr_cfg: Config dictionary
    
    Returns:
        str: Spell-checked text
    """
    spell_check_cfg = ocr_cfg.get("ai_spell_check", {})
    if not spell_check_cfg.get("enabled", False):
        return para_data.get("cleaned_text", para_data["text"])
    
    # Get API keys
    api_keys = spell_check_cfg.get("api_keys", [])
    if not api_keys:
        api_keys = ocr_cfg.get("_root_api_keys", [])
    if not api_keys:
        logger.warning("Không có API keys cho spell check, bỏ qua")
        return para_data.get("cleaned_text", para_data["text"])
    
    model_name = spell_check_cfg.get("model", "gemini-2.5-flash")
    timeout_s = spell_check_cfg.get("timeout", 60.0)
    
    # Get safety settings
    safety_level = spell_check_cfg.get("safety_level") or ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
    safety_settings = _build_safety_settings(safety_level)
    
    text = para_data.get("cleaned_text", para_data["text"])
    
    # Build spell check prompt (giống như ai_spell_check_and_paragraph_restore)
    # Lấy prompt từ existing function hoặc tạo mới
    prompt = """Bạn là AI chuyên soát lỗi chính tả và phục hồi cấu trúc paragraph cho văn bản OCR/scan.

Nhiệm vụ:
1. Soát lỗi chính tả do OCR
2. Phục hồi cấu trúc paragraph hợp lý
3. Nối các câu bị ngắt paragraph (nếu cần)
4. Giữ nguyên nội dung và ý nghĩa

Trả về chỉ văn bản đã được soát và phục hồi, không giải thích thêm.

Văn bản cần phân tích và xử lý:
""" + text
    
    try:
        # Use async spell check function (cần check xem có sẵn không)
        # Tạm thời dùng _cleanup_chunk_async với spell check prompt
        spell_checked_text = asyncio.run(_cleanup_chunk_async(
            text, api_keys[0], model_name, prompt, 0, 1, timeout_s, safety_settings
        ))
        return spell_checked_text
    except Exception as e:
        logger.warning(f"Spell check paragraph thất bại: {e}")
        return text

async def _cleanup_chunk_async(chunk: str, api_key: str, model_name: str, prompt: str, chunk_idx: int, total_chunks: int, timeout_s: float, safety_settings: Optional[List[dict]] = None) -> str:
    """
    Cleanup một chunk text bằng AI (async).
    
    Args:
        safety_settings: Optional safety settings để pass vào GenerativeModel (nếu None sẽ dùng default)
    """
    # Suppress logs TRƯỚC khi import
    _suppress_google_logs()
    # Đảm bảo stderr filter đang active
    if not isinstance(sys.stderr, NoisyMessageFilter):
        original_stderr = sys.stderr if not isinstance(sys.stderr, NoisyMessageFilter) else getattr(sys.stderr, 'original_stream', sys.stderr)
        sys.stderr = NoisyMessageFilter(original_stderr)
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    # Pass safety_settings vào GenerativeModel (nếu có)
    model = genai.GenerativeModel(model_name, safety_settings=safety_settings) if safety_settings else genai.GenerativeModel(model_name)
    
    # Run trong thread pool và áp timeout để tránh treo vô hạn
    loop = asyncio.get_event_loop()
    response = await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: model.generate_content(prompt + chunk)
        ),
        timeout=timeout_s
    )
    
    # Kiểm tra response có hợp lệ không
    if not response or not response.candidates or len(response.candidates) == 0:
        raise ValueError(f"AI cleanup chunk {chunk_idx}/{total_chunks}: No candidates returned")
    
    # Kiểm tra prompt_feedback nếu có
    if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
        if hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
            raise ValueError(f"AI cleanup chunk {chunk_idx}/{total_chunks}: Blocked by safety filter: {response.prompt_feedback.block_reason}")
    
    result = response.text.strip()
    return result

def _format_table_with_coordinates(metadata_path: str) -> str:
    """
    Format bảng với marker tọa độ để AI xử lý.
    
    Format: [CELL R=row C=col]text_part_1[SEP]text_part_2[END CELL]
    
    Args:
        metadata_path: Đường dẫn file JSON metadata
        
    Returns:
        str: Text đã format với marker tọa độ
    """
    try:
        import json
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        cells = metadata.get("cells", [])
        if not cells:
            return ""
        
        # Nhóm theo (row, col)
        cell_dict = {}
        for cell in cells:
            key = (cell["row"], cell["col"])
            if key not in cell_dict:
                cell_dict[key] = []
            cell_dict[key].extend(cell["cell_text_parts"])
        
        # Format: [CELL R=row C=col]text1[SEP]text2[END CELL]
        formatted_lines = []
        for (row, col), parts in sorted(cell_dict.items()):
            cell_texts = [part["text"].strip() for part in parts if part.get("text", "").strip()]
            if cell_texts:
                combined = " ".join(cell_texts)  # Ghép các phần text trong cùng ô
                formatted_lines.append(f"[CELL R={row} C={col}]{combined}[END CELL]")
        
        return "\n".join(formatted_lines)
    except Exception as e:
        logger.warning(f"Không thể format bảng với tọa độ: {e}")
        return ""

def _format_table_row_with_markers(row: List[str], num_cols: int) -> str:
    """
    Format một hàng bảng với marker | phân cách giữa các ô.
    
    Đảm bảo:
    - Mỗi hàng có đúng num_cols cột (pad với chuỗi rỗng nếu thiếu)
    - Marker | chỉ ở giữa các ô, không có ở đầu và cuối
    - Format: cell1|cell2|cell3
    - Xử lý các trường hợp đặc biệt: None, empty list, non-string values
    
    Args:
        row: List các ô trong hàng (có thể chứa None hoặc non-string)
        num_cols: Số cột mong muốn
        
    Returns:
        str: Hàng đã format với marker | (ví dụ: "cell1|cell2|cell3")
    """
    # Đảm bảo row là list
    if not isinstance(row, list):
        row = []
    
    # Convert tất cả cell thành string và loại bỏ None
    row_str_list = [str(cell) if cell is not None else "" for cell in row]
    
    # Đảm bảo hàng có đúng num_cols cột
    if len(row_str_list) < num_cols:
        # Pad với chuỗi rỗng nếu thiếu
        row_str_list = row_str_list + [""] * (num_cols - len(row_str_list))
    elif len(row_str_list) > num_cols:
        # Cắt bớt nếu thừa (chỉ lấy num_cols cột đầu)
        row_str_list = row_str_list[:num_cols]
    
    # Format với marker | (không có | ở đầu và cuối)
    # Đảm bảo không có cell nào là None hoặc không phải string
    result = "|".join(row_str_list)
    
    # Debug log nếu cần
    if not result or "|" not in result:
        logger.debug(f"⚠️  Format table row: row={row}, num_cols={num_cols}, result='{result}'")
    
    return result

def _update_csv_with_cleaned_cells(csv_path: str, cleaned_cells: List[dict]) -> None:
    """
    Cập nhật CSV với text đã được AI cleanup.
    Format: cell1|cell2|cell3 (marker | phân cách cột)
    
    Args:
        csv_path: Đường dẫn file CSV
        cleaned_cells: List các dict {row, col, cleaned_text}
    """
    try:
        # Đọc CSV hiện tại (format: cell1|cell2|cell3)
        rows = []
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            for line in f:
                line = line.rstrip('\n\r')
                if line:
                    cells = line.split('|')
                    rows.append(cells)
        
        # Tạo dict mapping (row, col) -> cleaned_text
        cell_map = {(cell["row"], cell["col"]): cell["cleaned_text"] for cell in cleaned_cells}
        
        # Cập nhật các ô có trong cell_map
        for row_idx, row in enumerate(rows):
            for col_idx in range(len(row)):
                if (row_idx, col_idx) in cell_map:
                    # Ghép paragraph trong ô thành một paragraph
                    cleaned_text = cell_map[(row_idx, col_idx)]
                    rows[row_idx][col_idx] = " ".join(cleaned_text.split())
        
        # Ghi lại CSV với format marker |
        # Tìm số cột tối đa để đảm bảo nhất quán
        max_cols = max(len(row) for row in rows) if rows else 0
        
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            for row in rows:
                # Format với helper function để đảm bảo đúng số cột
                row_str = _format_table_row_with_markers(row, max_cols)
                f.write(row_str + "\n")
    except Exception as e:
        logger.warning(f"Không thể cập nhật CSV: {e}")

def ai_cleanup_table_with_coordinates(metadata_path: str, ocr_cfg: dict) -> dict:
    """
    Sử dụng AI để cleanup và ghép text trong các ô bảng có nhiều dòng.
    
    Args:
        metadata_path: Đường dẫn file JSON metadata
        ocr_cfg: Config OCR
        
    Returns:
        dict: {"cells": [{row, col, cleaned_text}], "success": bool}
    """
    cleanup_cfg = ocr_cfg.get("ai_cleanup", {})
    if not cleanup_cfg.get("enabled", False):
        return {"cells": [], "success": False}
    
    api_keys = cleanup_cfg.get("api_keys", [])
    if not api_keys:
        api_keys = ocr_cfg.get("_root_api_keys", [])
    if not api_keys:
        logger.warning("AI cleanup enabled nhưng không có API keys. Bỏ qua cleanup bảng.")
        return {"cells": [], "success": False}
    
    try:
        import json
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        
        # Format bảng với marker tọa độ
        formatted_text = _format_table_with_coordinates(metadata_path)
        if not formatted_text:
            return {"cells": [], "success": False}
        
        # Prompt cho AI
        prompt = """Bạn là AI chuyên xử lý bảng dữ liệu từ OCR.

NHIỆM VỤ:
1. Ghép các phần text có cùng tọa độ (R=row, C=col) thành một ô hoàn chỉnh
2. GHÉP TẤT CẢ PARAGRAPH TRONG CÙNG MỘT Ô THÀNH MỘT PARAGRAPH (ưu tiên tính toàn vẹn nội dung)
3. Loại bỏ ký tự rác, lỗi OCR (ký tự đặc biệt không có nghĩa, ký tự lạ)
4. Chuẩn hóa khoảng trắng (một khoảng trắng giữa các từ)
5. Giữ nguyên số liệu, ngày tháng, đơn vị, dấu phẩy, dấu chấm
6. Sửa lỗi chính tả phổ biến (ví dụ: "chíh" → "chính", "Hanh phúc" → "Hạnh phúc")

ĐỊNH DẠNG ĐẦU VÀO:
[CELL R=row C=col]text_part_1 text_part_2[END CELL]

ĐỊNH DẠNG ĐẦU RA (BẮT BUỘC):
[CELL R=row C=col]text_đã_ghép_và_cleanup[END CELL]

QUY TẮC QUAN TRỌNG:
- BẮT BUỘC giữ nguyên format [CELL R=... C=...]...[END CELL] trong output
- GHÉP TẤT CẢ PARAGRAPH TRONG CÙNG MỘT Ô THÀNH MỘT PARAGRAPH (thay \n bằng space)
- Ưu tiên tính toàn vẹn nội dung của ô hơn là tính chính xác của việc phân paragraph
- Ghép tất cả text trong cùng một ô (cùng R và C) thành một chuỗi liên tục (không có xuống dòng)
- Loại bỏ ký tự đặc biệt không cần thiết (nhưng giữ: số, dấu phẩy, dấu chấm, dấu gạch ngang, dấu ngoặc)
- Chuẩn hóa khoảng trắng (một khoảng trắng giữa các từ, loại bỏ khoảng trắng thừa)
- Sửa lỗi OCR phổ biến: "chíh" → "chính", "Hanh" → "Hạnh", "Tư do" → "Tự do", "đông" → "đồng"

Bảng cần xử lý:
"""
        
        # Gọi AI với API key đầu tiên
        api_key = api_keys[0]
        model_name = cleanup_cfg.get("model", "gemini-2.5-flash")
        timeout_s = float(cleanup_cfg.get("ai_timeout_seconds", 120))
        
        _suppress_google_logs()
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        
        response = model.generate_content(prompt + formatted_text)
        if not response or not response.candidates:
            logger.warning("AI cleanup bảng: Không có response")
            return {"cells": [], "success": False}
        
        # Kiểm tra finish_reason
        candidate = response.candidates[0]
        if hasattr(candidate, 'finish_reason') and candidate.finish_reason:
            if candidate.finish_reason == 1:  # SAFETY hoặc BLOCKED
                logger.warning(f"AI cleanup bảng: Response bị block (finish_reason={candidate.finish_reason})")
                return {"cells": [], "success": False}
        
        # Lấy text từ response
        try:
            cleaned_text = response.text.strip()
        except Exception as text_err:
            logger.warning(f"AI cleanup bảng: Không thể lấy text từ response: {text_err}")
            # Thử lấy từ parts
            if candidate.parts:
                cleaned_text = " ".join([part.text for part in candidate.parts if hasattr(part, 'text') and part.text]).strip()
            else:
                return {"cells": [], "success": False}
        
        # Parse kết quả: tìm [CELL R=... C=...]...[END CELL]
        import re
        # Hỗ trợ cả [END CELL] và [/END CELL], và cả trường hợp không có marker
        # Pattern 1: [CELL R=... C=...]...[END CELL]
        pattern1 = r'\[CELL R=(\d+) C=(\d+)\](.*?)\[END CELL\]'
        matches1 = re.findall(pattern1, cleaned_text, re.DOTALL)
        # Pattern 2: [CELL R=... C=...]...[/END CELL]
        pattern2 = r'\[CELL R=(\d+) C=(\d+)\](.*?)\[/END CELL\]'
        matches2 = re.findall(pattern2, cleaned_text, re.DOTALL)
        # Gộp kết quả, ưu tiên pattern1
        matches = matches1 if matches1 else matches2
        
        cleaned_cells = []
        for row_str, col_str, text in matches:
            try:
                row = int(row_str)
                col = int(col_str)
                cleaned_cells.append({
                    "row": row,
                    "col": col,
                    "cleaned_text": text.strip()
                })
            except ValueError:
                continue
        
        logger.info(f"✅ AI cleanup bảng: Đã xử lý {len(cleaned_cells)} ô")
        return {"cells": cleaned_cells, "success": True}
        
    except Exception as e:
        logger.warning(f"Lỗi khi cleanup bảng bằng AI: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return {"cells": [], "success": False}

def ai_cleanup_text(text: str, ocr_cfg: dict) -> str:
    """
    Sử dụng AI để dọn rác text (header/footer, vệt đen từ scan, noise...).
    Hỗ trợ nhiều API keys để xử lý song song.
    """
    cleanup_cfg = ocr_cfg.get("ai_cleanup", {})
    cleanup_enabled = cleanup_cfg.get("enabled", False)
    if not cleanup_enabled:
        return text
    
    # Lấy API keys (ưu tiên từ ai_cleanup.api_keys, fallback về api_keys từ root config)
    api_keys = cleanup_cfg.get("api_keys", [])
    if not api_keys:
        # Đọc từ _root_api_keys đã lưu khi load config
        api_keys = ocr_cfg.get("_root_api_keys", [])
    
    if not api_keys:
        logger.warning("AI cleanup enabled nhưng không có API keys. Bỏ qua cleanup.")
        return text
    
    model_name = cleanup_cfg.get("model", "gemini-2.5-flash")
    max_parallel = cleanup_cfg.get("max_parallel_workers", 5)
    # Giới hạn worker theo số API keys sẵn có
    if api_keys:
        max_parallel = max(1, min(max_parallel, len(api_keys)))
    chunk_size = cleanup_cfg.get("chunk_size", 50000)
    delay = cleanup_cfg.get("delay_between_requests", 0.5)
    max_retries = cleanup_cfg.get("max_retries", 3)
    timeout_s = float(cleanup_cfg.get("ai_timeout_seconds", 120))
    show_progress = bool(ocr_cfg.get("show_progress", True))
    progress_interval = float(ocr_cfg.get("progress_log_interval_seconds", 60))
    
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
    
    try:
        # Chia nhỏ text nếu quá dài
        if len(text) <= chunk_size:
            # Text ngắn, xử lý trực tiếp
            logger.info("AI Cleanup: Text ngắn, xử lý trực tiếp (1 chunk)")
            # Suppress logs TRƯỚC khi import
            _suppress_google_logs()
            # Đảm bảo stderr filter đang active
            if not isinstance(sys.stderr, NoisyMessageFilter):
                original_stderr = sys.stderr if not isinstance(sys.stderr, NoisyMessageFilter) else getattr(sys.stderr, 'original_stream', sys.stderr)
                sys.stderr = NoisyMessageFilter(original_stderr)
            # Build safety settings từ config
            safety_level = ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
            safety_settings = _build_safety_settings(safety_level)
            
            import google.generativeai as genai
            genai.configure(api_key=api_keys[0])
            model = genai.GenerativeModel(model_name, safety_settings=safety_settings)
            response = model.generate_content(prompt + text)
            
            # Kiểm tra nếu response bị block (mặc dù đã set BLOCK_NONE, nhưng vẫn check để an toàn)
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                block_reason = getattr(response.prompt_feedback, 'block_reason', None)
                if block_reason:
                    logger.warning(f"AI Cleanup bị block: {block_reason}. Sử dụng text gốc.")
                    return (text, [0], [text])  # Return text gốc với failed index
            
            if not hasattr(response, 'candidates') or not response.candidates:
                logger.warning("AI Cleanup không có candidates. Sử dụng text gốc.")
                return (text, [0], [text])  # Return text gốc với failed index
            
            logger.info("AI Cleanup: Hoàn tất. Thành công: 1/1 chunk, Thất bại: 0/1 chunk.")
            cleaned_text = response.text.strip()
            return (cleaned_text, [], [text])  # (result_text, failed_indices, original_chunks)
        
        # Build safety settings từ config
        safety_level = ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
        safety_settings = _build_safety_settings(safety_level)
        
        # Text dài, chia nhỏ ở ranh giới câu và xử lý song song
        text_chunks = _split_text_at_sentence_boundaries(text, chunk_size)
        total_chunks = len(text_chunks)
        logger.info(f"AI Cleanup: Chia thành {total_chunks} chunks (ở ranh giới câu), xử lý song song với {len(api_keys)} API keys")
        logger.info(f"AI Cleanup: Safety level: {safety_level}")
        logger.info("AI Cleanup: Bắt đầu xử lý...")
        
        # Chạy async cleanup với safety settings
        result_text, success_count, failure_count, failed_indices = asyncio.run(_ai_cleanup_parallel(text_chunks, api_keys, model_name, prompt, max_parallel, delay, show_progress, timeout_s, max_retries, progress_interval, safety_settings))
        logger.info(f"AI Cleanup: Hoàn tất. Thành công: {success_count}/{total_chunks} chunks, Thất bại: {failure_count}/{total_chunks} chunks (đã lưu nội dung gốc).")
        
        # Tự động retry các chunks failed sau khi hoàn tất tất cả chunks khác
        if failure_count > 0:
            auto_retry = cleanup_cfg.get("auto_retry_failed", True)  # Mặc định: true
            if auto_retry:
                logger.info(f"AI Cleanup: Tự động retry {failure_count} chunks failed...")
                retry_results, still_failed = _retry_failed_chunks_cleanup(
                    failed_indices,
                    text_chunks,
                    api_keys,
                    model_name,
                    prompt,
                    ocr_cfg
                )
                
                # Merge lại text từ retry results
                if retry_results:
                    cleanup_chunks_list = list(text_chunks)
                    for idx, retry_text in retry_results.items():
                        if idx < len(cleanup_chunks_list):
                            cleanup_chunks_list[idx] = retry_text
                    result_text = "\n\n".join(cleanup_chunks_list)
                    
                    retry_success = len(retry_results) - len(still_failed)
                    logger.info(f"AI Cleanup Auto Retry: {retry_success}/{failure_count} chunks retry thành công.")
                    if still_failed:
                        logger.warning(f"AI Cleanup Auto Retry: {len(still_failed)} chunks vẫn failed sau retry.")
                        # Cập nhật failed_indices với still_failed
                        failed_indices = still_failed
                    else:
                        logger.info(f"AI Cleanup Auto Retry: Tất cả chunks failed đã được retry thành công!")
                        failed_indices = []  # Tất cả đã thành công
                else:
                    logger.warning("AI Cleanup Auto Retry: Không có kết quả retry.")
        
        # Trả về text đã merge, failed_indices, và toàn bộ chunks (để có thể rebuild sau retry)
        return (result_text, failed_indices, text_chunks)
        
    except Exception as e:
        logger.error(f"AI cleanup failed: {e}. Trả về text gốc.")
        return (text, [], [])  # Trả về tuple nhất quán

async def _ai_cleanup_parallel(text_chunks: List[str], api_keys: List[str], model_name: str, prompt: str, max_parallel: int, delay: float, show_progress: bool, timeout_s: float, max_retries: int, progress_interval: float, safety_settings: Optional[List[dict]] = None) -> tuple[str, int, int, List[int]]:
    """
    Xử lý song song nhiều chunks với nhiều API keys.
    
    Args:
        safety_settings: Optional safety settings để pass vào GenerativeModel
    """
    # Tạo queue cho API keys
    key_queue = asyncio.Queue()
    for key in api_keys:
        await key_queue.put(key)
    
    cleaned_chunks: List[tuple[int, str]] = []  # (index, cleaned_text)
    semaphore = asyncio.Semaphore(max_parallel)
    total = len(text_chunks)
    failures = 0
    failed_indices: List[int] = []
    
    async def process_chunk(chunk: str, chunk_idx: int) -> tuple[int, str]:
        nonlocal failures, failed_indices  # Khai báo nonlocal ở đầu function
        async with semaphore:
            retries = 0
            api_key = None
            last_error = None
            while retries < max_retries:
                try:
                    api_key = await key_queue.get()
                    cleaned = await _cleanup_chunk_async(chunk, api_key, model_name, prompt, chunk_idx, len(text_chunks), timeout_s, safety_settings)
                    # Thành công - return ngay
                    return (chunk_idx, cleaned)
                except Exception as e:
                    last_error = e
                    retries += 1
                    if retries < max_retries:
                        logger.debug(f"AI cleanup chunk {chunk_idx} failed (attempt {retries}/{max_retries}): {type(e).__name__}: {e}. Retrying...")
                        await asyncio.sleep(delay * retries)
                    else:
                        # Đã retry hết
                        failures += 1
                        failed_indices.append(chunk_idx)
                        logger.warning(f"AI cleanup chunk {chunk_idx} failed after {max_retries} retries with {type(e).__name__}: {e}")
                        return (chunk_idx, chunk)  # Trả về chunk gốc
                finally:
                    if api_key:
                        try:
                            await key_queue.put(api_key)  # Trả key về queue dù thành công hay lỗi
                        except Exception:
                            pass
                    await asyncio.sleep(delay)
            
            # Nếu đến đây (không nên xảy ra)
            failures += 1
            failed_indices.append(chunk_idx)
            logger.warning(f"AI cleanup chunk {chunk_idx} failed after all retries. Last error: {last_error}")
            return (chunk_idx, chunk)
    
    # Tạo tasks cho tất cả chunks
    tasks = [process_chunk(chunk, idx) for idx, chunk in enumerate(text_chunks)]
    
    # Xử lý và log tiến độ định kỳ
    results = []
    if show_progress:
        start_ts = time.time()
        last_log = start_ts
        completed = 0
        async for result in _as_completed_iter(tasks):
            results.append(result)
            completed += 1
            now = time.time()
            if (now - last_log) >= max(5.0, progress_interval):
                elapsed = now - start_ts
                avg = elapsed / completed if completed > 0 else 0.0
                remaining = max(len(tasks) - completed, 0) * avg
                logger.info(f"AI Cleanup: {completed}/{len(tasks)} chunks • TB {avg:.2f}s/chunk • ETA ~{remaining:.0f}s")
                last_log = now
    else:
        results = await asyncio.gather(*tasks)
    cleaned_chunks = sorted(results, key=lambda x: x[0])
    success_count = total - failures
    if failures > 0:
        logger.warning(f"AI Cleanup: {failures}/{total} chunks failed. Tiếp tục với nội dung gốc cho các chunk lỗi.")
    
    # Ghép các chunks theo thứ tự
    result_text = "\n\n".join([text for _, text in cleaned_chunks])
    return (result_text, success_count, failures, failed_indices)

async def _as_completed_iter(coros):
    for fut in asyncio.as_completed(coros):
        yield await fut

def _split_text_at_sentence_boundaries(text: str, max_chunk_size: int) -> List[str]:
    """
    Chia text thành chunks ở ranh giới câu (kết thúc bằng dấu chấm câu).
    Tham khảo thuật toán từ SmartChunker._split_long_paragraph để đảm bảo không cắt giữa câu.
    
    Args:
        text: Văn bản cần chia
        max_chunk_size: Kích thước tối đa của mỗi chunk (tính theo ký tự)
    
    Returns:
        List[str]: Danh sách các chunks đã được chia ở ranh giới câu
    """
    import re
    
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
                chunks.append(' '.join(current_chunk))
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
                    chunks.append(' '.join(temp_chunk))
                    temp_chunk = [word]
                    temp_size = len(word)
                else:
                    temp_chunk.append(word)
                    temp_size += word_size
            
            if temp_chunk:
                chunks.append(' '.join(temp_chunk))
        else:
            # Kiểm tra nếu thêm sentence này vào chunk hiện tại có vượt quá max_chunk_size không
            # Nếu đã có sentences trong chunk, cần thêm 1 ký tự cho space khi join
            space_needed = 1 if current_chunk else 0
            if current_size + sent_size + space_needed > max_chunk_size and current_chunk:
                # Lưu chunk hiện tại và bắt đầu chunk mới
                chunks.append(' '.join(current_chunk))
                current_chunk = [sentence]
                current_size = sent_size
            else:
                # Thêm sentence vào chunk hiện tại
                current_chunk.append(sentence)
                current_size += sent_size + space_needed
    
    # Lưu chunk cuối cùng nếu có
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    # Nếu không chia được gì (trường hợp hiếm), trả về toàn bộ text
    if not chunks:
        return [text]
    
    return chunks

def _preprocess_line_breaks(text: str) -> str:
    """
    Preprocessing: Nối lại các câu bị ngắt do line breaks khi convert PDF → TXT.
    Chỉ xử lý các trường hợp rõ ràng, các trường hợp phức tạp sẽ để AI xử lý.
    """
    import re
    
    lines = text.split('\n')
    if not lines:
        return text
    
    result_lines = []
    i = 0
    
    while i < len(lines):
        current_line = lines[i].strip()
        
        # Nếu dòng rỗng → giữ nguyên (đây là paragraph break)
        if not current_line:
            result_lines.append('')
            i += 1
            continue
        
        # Bắt đầu từ dòng hiện tại, cố gắng nối các dòng tiếp theo nếu thỏa điều kiện
        merged_line = current_line
        
        # Kiểm tra và nối các dòng tiếp theo liên tục
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            
            # Nếu dòng tiếp theo rỗng
            if not next_line:
                # Kiểm tra xem có phải paragraph break thực sự không
                # Nếu dòng hiện tại kết thúc bằng dấu câu → paragraph break thực sự
                if re.search(r'[.!?]$', merged_line):
                    break
                
                # Nếu không, có thể là line break do PDF format, kiểm tra dòng sau nữa
                if i + 2 < len(lines):
                    next_next_line = lines[i + 2].strip()
                    if next_next_line:
                        # Kiểm tra dòng sau dòng trống
                        first_char = next_next_line[0]
                        next_starts_with_upper = first_char.isupper() and first_char.isalpha()
                        next_starts_with_number = bool(re.match(r'^\d+', next_next_line))
                        next_starts_with_bullet = bool(re.match(r'^[•·\-*]\s', next_next_line))
                        
                        # Nếu dòng sau dòng trống bắt đầu bằng chữ hoa/số/bullet → paragraph break thực sự
                        if next_starts_with_upper or next_starts_with_number or next_starts_with_bullet:
                            break
                        
                        # Nếu dòng sau dòng trống bắt đầu bằng chữ thường → có thể là câu bị ngắt
                        # Bỏ qua dòng trống và tiếp tục với dòng sau
                        next_line = next_next_line
                        i += 1  # Skip dòng trống
                    else:
                        # Không còn dòng nào → dừng
                        break
                else:
                    # Không còn dòng nào → dừng
                    break
            
            # Dòng hiện tại (đã merged) KHÔNG kết thúc bằng dấu kết thúc câu
            ends_with_punctuation = bool(re.search(r'[.!?]$', merged_line))
            
            if not ends_with_punctuation:
                # Kiểm tra nếu dòng tiếp theo bắt đầu bằng chữ hoa
                # Dùng phương pháp đơn giản: kiểm tra ký tự đầu tiên có phải chữ hoa không
                if next_line:
                    first_char = next_line[0]
                    # Kiểm tra nếu là chữ cái và viết hoa (hỗ trợ Unicode)
                    next_starts_with_upper = first_char.isupper() and first_char.isalpha()
                else:
                    next_starts_with_upper = False
                
                next_starts_with_number = bool(re.match(r'^\d+', next_line))
                next_starts_with_bullet = bool(re.match(r'^[•·\-*]\s', next_line))
                
                # Nếu dòng tiếp theo KHÔNG bắt đầu bằng chữ hoa VÀ không phải số/bullet
                # → Có thể là câu bị ngắt, nối lại
                if not next_starts_with_upper and not next_starts_with_number and not next_starts_with_bullet:
                    # Nối với dòng tiếp theo
                    merged_line = merged_line.rstrip() + ' ' + next_line.lstrip()
                    i += 1
                    # Tiếp tục kiểm tra dòng tiếp theo
                    continue
            
            # Không thỏa điều kiện nối → dừng
            break
        
        # Lưu dòng đã merged (hoặc dòng gốc nếu không merge)
        result_lines.append(merged_line)
        i += 1
    
    return '\n'.join(result_lines)

async def _spell_check_chunk_async(chunk: str, api_key: str, model_name: str, prompt: str, chunk_idx: int, total_chunks: int, timeout_s: float, safety_settings: Optional[List[dict]] = None) -> str:
    """
    Soát lỗi chính tả và phục hồi paragraph cho một chunk text bằng AI (async).
    
    Args:
        safety_settings: Optional safety settings để pass vào GenerativeModel (nếu None sẽ dùng default)
    """
    # Suppress logs TRƯỚC khi import
    _suppress_google_logs()
    # Đảm bảo stderr filter đang active
    if not isinstance(sys.stderr, NoisyMessageFilter):
        original_stderr = sys.stderr if not isinstance(sys.stderr, NoisyMessageFilter) else getattr(sys.stderr, 'original_stream', sys.stderr)
        sys.stderr = NoisyMessageFilter(original_stderr)
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    # Pass safety_settings vào GenerativeModel (nếu có)
    model = genai.GenerativeModel(model_name, safety_settings=safety_settings) if safety_settings else genai.GenerativeModel(model_name)
    
    # Run trong thread pool và áp timeout để tránh treo vô hạn
    loop = asyncio.get_event_loop()
    response = await asyncio.wait_for(
        loop.run_in_executor(
            None,
            lambda: model.generate_content(prompt + chunk)
        ),
        timeout=timeout_s
    )
    # Kiểm tra response có hợp lệ không
    if not response or not response.candidates or len(response.candidates) == 0:
        raise ValueError(f"AI spell check chunk {chunk_idx}/{total_chunks}: No candidates returned")
    
    # Kiểm tra prompt_feedback nếu có
    if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
        if hasattr(response.prompt_feedback, 'block_reason') and response.prompt_feedback.block_reason:
            raise ValueError(f"AI spell check chunk {chunk_idx}/{total_chunks}: Blocked by safety filter: {response.prompt_feedback.block_reason}")
    
    result = response.text.strip()
    return result

async def _ai_spell_check_parallel(text_chunks: List[str], api_keys: List[str], model_name: str, prompt: str, max_parallel: int, delay: float, show_progress: bool, timeout_s: float, max_retries: int, progress_interval: float, safety_settings: Optional[List[dict]] = None) -> tuple[str, int, int, List[int]]:
    """
    Xử lý song song nhiều chunks với nhiều API keys cho spell check.
    
    Args:
        safety_settings: Optional safety settings để pass vào GenerativeModel
    """
    # Tạo queue cho API keys
    key_queue = asyncio.Queue()
    for key in api_keys:
        await key_queue.put(key)
    
    processed_chunks: List[tuple[int, str]] = []  # (index, processed_text)
    semaphore = asyncio.Semaphore(max_parallel)
    total = len(text_chunks)
    failures = 0
    failed_indices: List[int] = []
    
    async def process_chunk(chunk: str, chunk_idx: int) -> tuple[int, str]:
        nonlocal failures, failed_indices  # Khai báo nonlocal ở đầu function
        async with semaphore:
            retries = 0
            api_key = None
            last_error = None
            while retries < max_retries:
                try:
                    api_key = await key_queue.get()
                    processed = await _spell_check_chunk_async(chunk, api_key, model_name, prompt, chunk_idx, len(text_chunks), timeout_s, safety_settings)
                    # Thành công - return ngay
                    return (chunk_idx, processed)
                except Exception as e:
                    last_error = e
                    retries += 1
                    if retries < max_retries:
                        logger.debug(f"AI spell check chunk {chunk_idx} failed (attempt {retries}/{max_retries}): {type(e).__name__}: {e}. Retrying...")
                        await asyncio.sleep(delay * retries)
                    else:
                        # Đã retry hết
                        failures += 1
                        failed_indices.append(chunk_idx)
                        logger.warning(f"AI spell check chunk {chunk_idx} failed after {max_retries} retries with {type(e).__name__}: {e}")
                        return (chunk_idx, chunk)  # Trả về chunk gốc
                finally:
                    if api_key:
                        try:
                            await key_queue.put(api_key)  # Trả key về queue dù thành công hay lỗi
                        except Exception:
                            pass
                    await asyncio.sleep(delay)
            
            # Nếu đến đây (không nên xảy ra)
            failures += 1
            failed_indices.append(chunk_idx)
            logger.warning(f"AI spell check chunk {chunk_idx} failed after all retries. Last error: {last_error}")
            return (chunk_idx, chunk)
    
    # Tạo tasks cho tất cả chunks
    tasks = [process_chunk(chunk, idx) for idx, chunk in enumerate(text_chunks)]
    
    # Xử lý và log tiến độ định kỳ
    results = []
    if show_progress:
        start_ts = time.time()
        last_log = start_ts
        completed = 0
        async for result in _as_completed_iter(tasks):
            results.append(result)
            completed += 1
            now = time.time()
            if (now - last_log) >= max(5.0, progress_interval):
                elapsed = now - start_ts
                avg = elapsed / completed if completed > 0 else 0.0
                remaining = max(len(tasks) - completed, 0) * avg
                logger.info(f"AI Spell Check: {completed}/{len(tasks)} chunks • TB {avg:.2f}s/chunk • ETA ~{remaining:.0f}s")
                last_log = now
    else:
        results = await asyncio.gather(*tasks)
    processed_chunks = sorted(results, key=lambda x: x[0])
    success_count = total - failures
    
    if failures > 0:
        logger.warning(f"AI Spell Check: {failures}/{total} chunks failed. Tiếp tục với nội dung gốc cho các chunk lỗi.")
    else:
        logger.info(f"AI Spell Check: Tất cả {total} chunks đã được xử lý thành công.")
    
    # Ghép các chunks theo thứ tự
    result_text = "\n\n".join([text for _, text in processed_chunks])
    return (result_text, success_count, failures, failed_indices)

def _merge_split_table_rows(tables_by_page: dict, ocr_cfg: dict) -> dict:
    """
    Merge các hàng bị cắt từ ô phía trên trong bảng sau spell check.
    
    Logic:
    - Kiểm tra từng hàng trong bảng
    - Nếu hàng có nhiều ô trống ở đầu và chỉ có 1-2 ô có nội dung → có thể là hàng bị cắt
    - Sử dụng AI để đánh giá xem hàng này có phải là phần tiếp theo của hàng trên không
    - Nếu đúng, merge vào ô tương ứng của hàng trên
    
    Args:
        tables_by_page: {page_num: {"rows": [[cell1, cell2, ...], ...], "num_cols": int}}
        ocr_cfg: Config dictionary
    
    Returns:
        dict: Tables đã được merge (cùng format)
    """
    if not tables_by_page:
        return {}
    
    spell_check_cfg = ocr_cfg.get("ai_spell_check", {})
    if not spell_check_cfg.get("enabled", False):
        return tables_by_page
    
    # Lấy API keys
    api_keys = spell_check_cfg.get("api_keys", [])
    if not api_keys:
        api_keys = ocr_cfg.get("_root_api_keys", [])
    if not api_keys:
        logger.warning("Không có API keys để merge hàng bị cắt → bỏ qua")
        return tables_by_page
    
    model_name = spell_check_cfg.get("model", "gemini-2.5-flash")
    safety_level = ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
    
    merged_tables = {}
    
    for page_num, table_info in tables_by_page.items():
        rows = table_info.get("rows", [])
        num_cols = table_info.get("num_cols", 0)
        
        if not rows or num_cols == 0:
            merged_tables[page_num] = table_info
            continue
        
        # Phân tích từng hàng để tìm hàng bị cắt
        merged_rows = []
        i = 0
        while i < len(rows):
            current_row = rows[i]
            
            # Kiểm tra xem hàng này có phải là hàng bị cắt không
            # Dấu hiệu: nhiều ô trống ở đầu, chỉ có 1-2 ô cuối có nội dung
            non_empty_count = sum(1 for cell in current_row if cell and cell.strip())
            empty_prefix_count = sum(1 for cell in current_row if not cell or not cell.strip())
            
            # Nếu có >= 2 ô trống ở đầu và chỉ có 1-2 ô có nội dung → có thể là hàng bị cắt
            if empty_prefix_count >= 2 and non_empty_count <= 2 and i > 0:
                # Kiểm tra với hàng trên bằng AI
                prev_row = merged_rows[-1] if merged_rows else rows[i-1]
                
                # Tạo prompt để AI đánh giá
                prompt = f"""Bạn là AI chuyên phân tích cấu trúc bảng. Nhiệm vụ: Đánh giá xem hàng sau có phải là phần tiếp theo (bị cắt) của hàng trước không.

HÀNG TRƯỚC: {'|'.join(prev_row)}
HÀNG SAU: {'|'.join(current_row)}

QUY TẮC:
- Nếu hàng sau là phần tiếp theo của một ô trong hàng trước (bị cắt xuống dòng) → Trả về "MERGE"
- Nếu hàng sau là hàng mới độc lập → Trả về "KEEP"

Chỉ trả về một từ: "MERGE" hoặc "KEEP", không giải thích thêm."""
                
                try:
                    _suppress_google_logs()
                    if not isinstance(sys.stderr, NoisyMessageFilter):
                        original_stderr = sys.stderr if not isinstance(sys.stderr, NoisyMessageFilter) else getattr(sys.stderr, 'original_stream', sys.stderr)
                        sys.stderr = NoisyMessageFilter(original_stderr)
                    
                    safety_settings = _build_safety_settings(safety_level)
                    
                    import google.generativeai as genai
                    genai.configure(api_key=api_keys[0])
                    model = genai.GenerativeModel(model_name, safety_settings=safety_settings)
                    response = model.generate_content(prompt)
                    
                    decision = response.text.strip().upper()
                    
                    if decision == "MERGE":
                        # Merge hàng sau vào hàng trước
                        # Tìm ô nào trong hàng trước cần merge (thường là ô cuối cùng có nội dung)
                        last_non_empty_col = -1
                        for col_idx in range(len(prev_row) - 1, -1, -1):
                            if prev_row[col_idx] and prev_row[col_idx].strip():
                                last_non_empty_col = col_idx
                                break
                        
                        # Merge nội dung từ hàng sau vào ô tương ứng của hàng trước
                        if last_non_empty_col >= 0:
                            # Tìm ô đầu tiên có nội dung trong hàng sau
                            first_non_empty_col = -1
                            for col_idx in range(len(current_row)):
                                if current_row[col_idx] and current_row[col_idx].strip():
                                    first_non_empty_col = col_idx
                                    break
                            
                            if first_non_empty_col >= 0:
                                # Merge vào ô cuối cùng có nội dung của hàng trước
                                content_to_merge = current_row[first_non_empty_col].strip()
                                if content_to_merge:
                                    prev_row[last_non_empty_col] = (prev_row[last_non_empty_col] + " " + content_to_merge).strip()
                                    logger.debug(f"Đã merge hàng {i+1} vào hàng {i} (cột {last_non_empty_col})")
                                # Bỏ qua hàng hiện tại (đã merge)
                                i += 1
                                continue
                except Exception as e:
                    logger.debug(f"Không thể dùng AI để merge hàng {i+1}: {e}")
                    # Nếu AI fail, giữ nguyên hàng
            
            # Không merge → thêm hàng vào kết quả
            merged_rows.append(current_row)
            i += 1
        
        merged_tables[page_num] = {
            "page": page_num,
            "rows": merged_rows,
            "num_cols": num_cols
        }
        logger.info(f"Đã xử lý merge hàng cho bảng trang {page_num}: {len(rows)} → {len(merged_rows)} hàng")
    
    return merged_tables

def ai_spell_check_and_paragraph_restore(text: str, ocr_cfg: dict) -> str:
    """
    Sử dụng AI để soát lỗi chính tả và phục hồi cấu trúc paragraph.
    Đặc biệt chú ý bảo vệ toàn vẹn nội dung (không thay đổi ý nghĩa).
    Hỗ trợ nhiều API keys để xử lý song song.
    """
    spell_check_cfg = ocr_cfg.get("ai_spell_check", {})
    spell_check_enabled = spell_check_cfg.get("enabled", False)
    if not spell_check_enabled:
        return text
    
    # Ghi chú: Không dùng preprocessing rule-based vì AI sẽ phân tích ngữ cảnh tốt hơn
    # Hàm _preprocess_line_breaks vẫn được giữ lại nếu cần dùng trong tương lai
    # text = _preprocess_line_breaks(text)  # Tạm tắt để AI làm toàn bộ
    
    # Lấy API keys (ưu tiên từ ai_spell_check.api_keys, fallback về api_keys từ root config)
    api_keys = spell_check_cfg.get("api_keys", [])
    if not api_keys:
        # Đọc từ _root_api_keys đã lưu khi load config
        api_keys = ocr_cfg.get("_root_api_keys", [])
    
    if not api_keys:
        logger.warning("AI spell check enabled nhưng không có API keys. Bỏ qua spell check.")
        return text
    
    model_name = spell_check_cfg.get("model", "gemini-2.5-flash")
    max_parallel = spell_check_cfg.get("max_parallel_workers", 5)
    # Giới hạn worker theo số API keys sẵn có
    if api_keys:
        max_parallel = max(1, min(max_parallel, len(api_keys)))
    chunk_size = spell_check_cfg.get("chunk_size", 50000)
    delay = spell_check_cfg.get("delay_between_requests", 0.5)
    max_retries = spell_check_cfg.get("max_retries", 3)
    timeout_s = float(spell_check_cfg.get("ai_timeout_seconds", 120))
    show_progress = bool(ocr_cfg.get("show_progress", True))
    progress_interval = float(ocr_cfg.get("progress_log_interval_seconds", 60))
    
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
    
    try:
        # Chia nhỏ text nếu quá dài
        if len(text) <= chunk_size:
            # Text ngắn, xử lý trực tiếp
            logger.info("AI Spell Check: Text ngắn, xử lý trực tiếp (1 chunk)")
            # Suppress logs TRƯỚC khi import
            _suppress_google_logs()
            # Đảm bảo stderr filter đang active
            if not isinstance(sys.stderr, NoisyMessageFilter):
                original_stderr = sys.stderr if not isinstance(sys.stderr, NoisyMessageFilter) else getattr(sys.stderr, 'original_stream', sys.stderr)
                sys.stderr = NoisyMessageFilter(original_stderr)
            # Build safety settings từ config
            safety_level = ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
            safety_settings = _build_safety_settings(safety_level)
            
            import google.generativeai as genai
            genai.configure(api_key=api_keys[0])
            model = genai.GenerativeModel(model_name, safety_settings=safety_settings)
            response = model.generate_content(prompt + text)
            
            # Kiểm tra nếu response bị block (mặc dù đã set BLOCK_NONE, nhưng vẫn check để an toàn)
            if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                block_reason = getattr(response.prompt_feedback, 'block_reason', None)
                if block_reason:
                    logger.warning(f"AI Spell Check bị block: {block_reason}. Sử dụng text gốc.")
                    return (text, [0], [text])  # Return text gốc với failed index
            
            if not hasattr(response, 'candidates') or not response.candidates:
                logger.warning("AI Spell Check không có candidates. Sử dụng text gốc.")
                return (text, [0], [text])  # Return text gốc với failed index
            
            logger.info("AI Spell Check: Hoàn tất. Thành công: 1/1 chunk, Thất bại: 0/1 chunk.")
            checked_text = response.text.strip()
            return (checked_text, [], [text])  # (result_text, failed_indices, original_chunks)
        
        # Build safety settings từ config
        safety_level = ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
        safety_settings = _build_safety_settings(safety_level)
        
        # Text dài, chia nhỏ ở ranh giới câu và xử lý song song
        text_chunks = _split_text_at_sentence_boundaries(text, chunk_size)
        total_chunks = len(text_chunks)
        logger.info(f"AI Spell Check: Chia thành {total_chunks} chunks (ở ranh giới câu), xử lý song song với {len(api_keys)} API keys")
        logger.info(f"AI Spell Check: Safety level: {safety_level}")
        logger.info("AI Spell Check: Bắt đầu xử lý...")
        
        # Chạy async spell check với safety settings
        result_text, success_count, failure_count, failed_indices = asyncio.run(_ai_spell_check_parallel(text_chunks, api_keys, model_name, prompt, max_parallel, delay, show_progress, timeout_s, max_retries, progress_interval, safety_settings))
        logger.info(f"AI Spell Check: Hoàn tất. Thành công: {success_count}/{total_chunks} chunks, Thất bại: {failure_count}/{total_chunks} chunks (đã lưu nội dung gốc).")
        
        # Tự động retry các chunks failed sau khi hoàn tất tất cả chunks khác
        if failure_count > 0:
            auto_retry = spell_check_cfg.get("auto_retry_failed", True)  # Mặc định: true
            if auto_retry:
                logger.info(f"AI Spell Check: Tự động retry {failure_count} chunks failed...")
                retry_results, still_failed = _retry_failed_chunks_spell_check(
                    failed_indices,
                    text_chunks,
                    api_keys,
                    model_name,
                    prompt,
                    ocr_cfg
                )
                
                # Merge lại text từ retry results
                if retry_results:
                    spell_check_chunks_list = list(text_chunks)
                    for idx, retry_text in retry_results.items():
                        if idx < len(spell_check_chunks_list):
                            spell_check_chunks_list[idx] = retry_text
                    result_text = "\n\n".join(spell_check_chunks_list)
                    
                    retry_success = len(retry_results) - len(still_failed)
                    logger.info(f"AI Spell Check Auto Retry: {retry_success}/{failure_count} chunks retry thành công.")
                    if still_failed:
                        logger.warning(f"AI Spell Check Auto Retry: {len(still_failed)} chunks vẫn failed sau retry.")
                        # Cập nhật failed_indices với still_failed
                        failed_indices = still_failed
                    else:
                        logger.info(f"AI Spell Check Auto Retry: Tất cả chunks failed đã được retry thành công!")
                        failed_indices = []  # Tất cả đã thành công
                else:
                    logger.warning("AI Spell Check Auto Retry: Không có kết quả retry.")
        
        # Trả về text đã merge, failed_indices, và toàn bộ chunks (để có thể rebuild sau retry)
        return (result_text, failed_indices, text_chunks)
        
    except Exception as e:
        logger.error(f"AI spell check failed: {e}. Trả về text gốc.")
        return (text, [], [])  # Trả về tuple nhất quán

def _retry_failed_chunks_cleanup(failed_indices: List[int], all_chunks: List[str], api_keys: List[str], model_name: str, prompt: str, ocr_cfg: dict) -> tuple[dict[int, str], List[int]]:
    """Retry các chunk failed cho AI Cleanup. Trả về dict {idx: processed_text} và danh sách still_failed."""
    if not failed_indices or not all_chunks:
        return ({}, [])
    
    cleanup_cfg = ocr_cfg.get("ai_cleanup", {})
    timeout_s = float(cleanup_cfg.get("ai_timeout_seconds", 240))
    
    failed_chunks = [(idx, all_chunks[idx]) for idx in failed_indices if idx < len(all_chunks)]
    logger.info(f"AI Cleanup Retry: Đang retry {len(failed_chunks)} chunks failed...")
    
    # Build safety settings từ config
    safety_level = ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
    safety_settings = _build_safety_settings(safety_level)
    
    async def _retry_chunk(idx: int, chunk: str) -> tuple[int, str]:
        for key in api_keys:
            try:
                result = await _cleanup_chunk_async(chunk, key, model_name, prompt, idx, len(failed_chunks), timeout_s, safety_settings)
                return (idx, result)
            except Exception:
                continue
        return (idx, chunk)  # Fallback về chunk gốc
    
    tasks = [_retry_chunk(idx, chunk) for idx, chunk in failed_chunks]
    results = asyncio.run(asyncio.gather(*tasks))
    
    retry_results = {idx: text for idx, text in results}
    still_failed = [idx for idx in failed_indices if retry_results.get(idx) == all_chunks[idx]]
    
    logger.info(f"AI Cleanup Retry: {len(failed_indices) - len(still_failed)}/{len(failed_indices)} chunks retry thành công.")
    if still_failed:
        logger.warning(f"AI Cleanup Retry: {len(still_failed)} chunks vẫn failed sau retry.")
    
    return (retry_results, still_failed)

def _retry_failed_chunks_spell_check(failed_indices: List[int], all_chunks: List[str], api_keys: List[str], model_name: str, prompt: str, ocr_cfg: dict) -> tuple[dict[int, str], List[int]]:
    """Retry các chunk failed cho AI Spell Check. Trả về dict {idx: processed_text} và danh sách still_failed."""
    if not failed_indices or not all_chunks:
        return ({}, [])
    
    spell_check_cfg = ocr_cfg.get("ai_spell_check", {})
    timeout_s = float(spell_check_cfg.get("ai_timeout_seconds", 240))
    
    failed_chunks = [(idx, all_chunks[idx]) for idx in failed_indices if idx < len(all_chunks)]
    logger.info(f"AI Spell Check Retry: Đang retry {len(failed_chunks)} chunks failed...")
    
    # Build safety settings từ config
    safety_level = ocr_cfg.get("safety_level", "BLOCK_ONLY_HIGH")
    safety_settings = _build_safety_settings(safety_level)
    
    async def _retry_chunk(idx: int, chunk: str) -> tuple[int, str]:
        for key in api_keys:
            try:
                result = await _spell_check_chunk_async(chunk, key, model_name, prompt, idx, len(failed_chunks), timeout_s, safety_settings)
                return (idx, result)
            except Exception:
                continue
        return (idx, chunk)  # Fallback về chunk gốc
    
    tasks = [_retry_chunk(idx, chunk) for idx, chunk in failed_chunks]
    results = asyncio.run(asyncio.gather(*tasks))
    
    retry_results = {idx: text for idx, text in results}
    still_failed = [idx for idx in failed_indices if retry_results.get(idx) == all_chunks[idx]]
    
    logger.info(f"AI Spell Check Retry: {len(failed_indices) - len(still_failed)}/{len(failed_indices)} chunks retry thành công.")
    if still_failed:
        logger.warning(f"AI Spell Check Retry: {len(still_failed)} chunks vẫn failed sau retry.")
    
    return (retry_results, still_failed)

