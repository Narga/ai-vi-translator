from . import config
from .image import _image_to_text, _normalize_lang_code

def detect_pdf_type(pdf_path: str, ocr_cfg: Optional[dict] = None) -> str:
    """
    Phát hiện PDF là scan hay text-based.
    Returns: "text" hoặc "scan"
    
    Logic cải thiện:
    - Sample nhiều trang hơn (5 trang đầu + 1 trang giữa + 1 trang cuối) để tăng độ chính xác
    - Threshold thấp hơn (20 ký tự thay vì 100) để không bỏ sót text-based ít text ở đầu
    - Timeout tăng lên 20 giây để xử lý PDF lớn
    - Kiểm tra chất lượng text: Nếu có text có thể extract được (dù ít) → text-based
    - Retry nếu file chưa sẵn sàng (đặc biệt khi chạy trên web)
    - CẢI TIẾN: Cache kết quả để tránh detect lại nhiều lần cho cùng một file
    """
    import threading
    import time
    
    # CẢI TIẾN: Kiểm tra cache trước khi detect lại
    pdf_path_normalized = os.path.abspath(pdf_path) if os.path.exists(pdf_path) else pdf_path
    if pdf_path_normalized in _pdf_type_cache:
        cached_result, cached_time = _pdf_type_cache[pdf_path_normalized]
        if time.time() - cached_time < _cache_timeout:
            logger.debug(f"✅ Dùng kết quả cache cho PDF type: {cached_result} (cache age: {time.time() - cached_time:.1f}s)")
            return cached_result
        else:
            # Cache hết hạn, xóa và detect lại
            del _pdf_type_cache[pdf_path_normalized]
            logger.debug(f"Cache đã hết hạn cho {pdf_path_normalized}, detect lại...")
    
    # Đảm bảo file tồn tại và có thể đọc được (retry nếu cần)
    max_retries = 3
    retry_delay = 0.2
    for attempt in range(max_retries):
        try:
            if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
                # Thử mở file để đảm bảo không bị lock
                with open(pdf_path, 'rb') as test_file:
                    test_file.read(1)
                break
        except (IOError, PermissionError) as e:
            if attempt < max_retries - 1:
                logger.debug(f"File chưa sẵn sàng, retry {attempt + 1}/{max_retries}: {e}")
                time.sleep(retry_delay)
            else:
                logger.warning(f"Không thể đọc file sau {max_retries} lần thử: {e}")
                return "scan"
    
    result_container = {"result": None, "done": False}
    exception_container = {"exception": None}
    
    def _detect_inner():
        """Hàm detect chạy trong thread riêng với timeout"""
        try:
            if pdfplumber is not None:
                logger.debug("Thử dùng pdfplumber...")
                try:
                    with config.pdfplumber.open(pdf_path) as pdf:
                        total_pages = len(pdf.pages)
                        if total_pages == 0:
                            logger.warning(f"PDF không có trang nào: {pdf_path}")
                            result_container["result"] = "scan"
                            result_container["done"] = True
                            return
                        
                        logger.debug(f"PDF có {total_pages} trang, bắt đầu sample...")
                        total_chars = 0
                        pages_with_text = 0
                        
                        # Sample nhiều điểm: 5 trang đầu + 1 trang giữa + 1 trang cuối
                        sample_indices = list(range(min(5, total_pages)))  # 5 trang đầu
                        if total_pages > 10:
                            sample_indices.append(total_pages // 2)  # Trang giữa
                        if total_pages > 5:
                            sample_indices.append(total_pages - 1)  # Trang cuối
                        
                        # Loại bỏ trùng lặp và sort
                        sample_indices = sorted(set(sample_indices))
                        logger.debug(f"Sample {len(sample_indices)} trang: {[i+1 for i in sample_indices]}")
                        
                        for idx in sample_indices:
                            try:
                                page = pdf.pages[idx]
                                text = page.extract_text()
                                if text and text.strip():
                                    text_len = len(text.strip())
                                    total_chars += text_len
                                    pages_with_text += 1
                                    logger.debug(f"Trang {idx+1}: {text_len} ký tự")
                                    # Nếu có trang nào có > 50 ký tự → chắc chắn text-based
                                    if text_len > 50:
                                        result_container["result"] = "text"
                                        result_container["done"] = True
                                        logger.info(f"✅ Phát hiện text-based: Trang {idx+1} có {text_len} ký tự")
                                        return
                            except Exception as e:
                                logger.debug(f"Lỗi khi extract trang {idx+1}: {e}")
                                continue
                        
                        # Nếu có text ở nhiều trang (>= 2) hoặc tổng > 20 ký tự → text-based
                        if pages_with_text >= 2 or total_chars > 20:
                            result_container["result"] = "text"
                            logger.info(f"✅ Phát hiện text-based: {pages_with_text} trang có text, tổng {total_chars} ký tự")
                        else:
                            result_container["result"] = "scan"
                            logger.info(f"📷 Phát hiện scan: Chỉ {pages_with_text} trang có text, tổng {total_chars} ký tự")
                        result_container["done"] = True
                        return
                except Exception as e:
                    logger.warning(f"pdfplumber failed: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    pass
            
            # Fallback: dùng PyPDF2
            if PyPDF2 is not None:
                try:
                    logger.debug("Thử dùng PyPDF2 (fallback)...")
                    with open(pdf_path, 'rb') as f:
                        reader = config.PyPDF2.PdfReader(f)
                        total_pages = len(reader.pages)
                        if total_pages == 0:
                            logger.warning(f"PDF không có trang nào (PyPDF2): {pdf_path}")
                            result_container["result"] = "scan"
                            result_container["done"] = True
                            return
                        
                        logger.debug(f"PDF có {total_pages} trang (PyPDF2), bắt đầu sample...")
                        total_chars = 0
                        pages_with_text = 0
                        
                        # Sample nhiều điểm
                        sample_indices = list(range(min(5, total_pages)))
                        if total_pages > 10:
                            sample_indices.append(total_pages // 2)
                        if total_pages > 5:
                            sample_indices.append(total_pages - 1)
                        
                        sample_indices = sorted(set(sample_indices))
                        logger.debug(f"Sample {len(sample_indices)} trang (PyPDF2): {[i+1 for i in sample_indices]}")
                        
                        for idx in sample_indices:
                            try:
                                page = reader.pages[idx]
                                text = page.extract_text()
                                if text and text.strip():
                                    text_len = len(text.strip())
                                    total_chars += text_len
                                    pages_with_text += 1
                                    logger.debug(f"Trang {idx+1} (PyPDF2): {text_len} ký tự")
                                    if text_len > 50:
                                        result_container["result"] = "text"
                                        result_container["done"] = True
                                        logger.info(f"✅ Phát hiện text-based (PyPDF2): Trang {idx+1} có {text_len} ký tự")
                                        return
                            except Exception as e:
                                logger.debug(f"Lỗi khi extract trang {idx+1} (PyPDF2): {e}")
                                continue
                        
                        if pages_with_text >= 2 or total_chars > 20:
                            result_container["result"] = "text"
                            logger.info(f"✅ Phát hiện text-based (PyPDF2): {pages_with_text} trang có text, tổng {total_chars} ký tự")
                        else:
                            result_container["result"] = "scan"
                            logger.info(f"📷 Phát hiện scan (PyPDF2): Chỉ {pages_with_text} trang có text, tổng {total_chars} ký tự")
                        result_container["done"] = True
                        return
                except Exception as e:
                    logger.warning(f"PyPDF2 failed: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    pass
            
            # Nếu không thể detect → giả định là scan
            result_container["result"] = "scan"
            result_container["done"] = True
        except Exception as e:
            exception_container["exception"] = e
            logger.debug(f"Exception trong _detect_inner: {e}")
            result_container["result"] = "scan"
            result_container["done"] = True
    
    # Chạy trong thread với timeout tăng lên 20 giây
    thread = threading.Thread(target=_detect_inner, daemon=True)
    thread.start()
    thread.join(timeout=20.0)  # Timeout 20 giây (tăng từ 10s)
    
    if not result_container["done"]:
        # Timeout xảy ra - thử cách đơn giản hơn: chỉ check 1 trang đầu
        logger.warning(f"Timeout khi detect PDF type sau 20 giây, thử cách đơn giản hơn: {pdf_path}")
        try:
            if pdfplumber is not None:
                with config.pdfplumber.open(pdf_path) as pdf:
                    if len(pdf.pages) > 0:
                        text = pdf.pages[0].extract_text()
                        if text and len(text.strip()) > 10:
                            logger.info("Phát hiện text-based (quick check trang đầu)")
                            return "text"
            elif PyPDF2 is not None:
                with open(pdf_path, 'rb') as f:
                    reader = config.PyPDF2.PdfReader(f)
                    if len(reader.pages) > 0:
                        text = reader.pages[0].extract_text()
                        if text and len(text.strip()) > 10:
                            logger.info("Phát hiện text-based (quick check trang đầu)")
                            return "text"
        except Exception:
            pass
        logger.warning("Giả định là scan sau timeout")
        return "scan"
    
    if exception_container["exception"]:
        logger.debug(f"Exception khi detect PDF type: {exception_container['exception']}")
    
    if result_container["result"]:
        result = result_container["result"]
        # CẢI TIẾN: Lưu kết quả vào cache
        pdf_path_normalized = os.path.abspath(pdf_path) if os.path.exists(pdf_path) else pdf_path
        _pdf_type_cache[pdf_path_normalized] = (result, time.time())
        return result
    
    # Fallback cuối cùng
    logger.warning(f"Không thể detect PDF type, giả định là scan: {pdf_path}")
    result = "scan"
    # CẢI TIẾN: Lưu kết quả vào cache
    pdf_path_normalized = os.path.abspath(pdf_path) if os.path.exists(pdf_path) else pdf_path
    _pdf_type_cache[pdf_path_normalized] = (result, time.time())
    return result

def extract_text_from_pdf(pdf_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> str:
    """
    Extract text từ PDF có text layer (không cần OCR).
    
    Args:
        pdf_path: Đường dẫn file PDF
        ocr_cfg: Config dictionary
        pages: Danh sách số trang cần extract (1-indexed). None = tất cả trang.
    """
    texts: List[str] = []
    
    # Ưu tiên pdfplumber (chính xác hơn)
    if pdfplumber is not None:
        try:
            with config.pdfplumber.open(pdf_path) as pdf:
                total = len(pdf.pages)
                logger.info(f"Extract text: Tổng số trang: {total}")
                
                # Filter pages nếu có chỉ định
                if pages:
                    # Validate pages (phải trong khoảng [1, total])
                    valid_pages = [p for p in pages if 1 <= p <= total]
                    invalid_pages = [p for p in pages if p < 1 or p > total]
                    if invalid_pages:
                        logger.warning(f"Các trang không hợp lệ (nằm ngoài 1-{total}): {invalid_pages}. Bỏ qua.")
                    if not valid_pages:
                        logger.error("Không có trang hợp lệ nào để extract.")
                        return ""
                    logger.info(f"Extract text: Chỉ extract {len(valid_pages)} trang: {valid_pages}")
                    pages_to_extract = sorted(set(valid_pages))
                else:
                    pages_to_extract = list(range(1, total + 1))
                
                show_progress = bool(ocr_cfg.get("show_progress", True))
                
                if show_progress and tqdm is not None and len(pages_to_extract) > 1:
                    for page_num in config.tqdm(pages_to_extract, desc="Extract text", unit="trang"):
                        page = pdf.pages[page_num - 1]  # pdfplumber dùng 0-indexed
                        text = page.extract_text()
                        if text:
                            texts.append(text.strip())
                else:
                    for page_num in pages_to_extract:
                        page = pdf.pages[page_num - 1]  # pdfplumber dùng 0-indexed
                        text = page.extract_text()
                        if text:
                            texts.append(text.strip())
                        if len(texts) % 50 == 0:
                            logger.info(f"Extract text: {len(texts)}/{len(pages_to_extract)} trang")
                return "\n\n".join(texts)
        except Exception as e:
            logger.warning(f"pdfplumber failed: {e}, trying PyPDF2...")
    
    # Fallback: PyPDF2
    if PyPDF2 is not None:
        try:
            with open(pdf_path, 'rb') as f:
                reader = config.PyPDF2.PdfReader(f)
                total = len(reader.pages)
                logger.info(f"Extract text: Tổng số trang: {total}")
                
                # Filter pages nếu có chỉ định
                if pages:
                    valid_pages = [p for p in pages if 1 <= p <= total]
                    invalid_pages = [p for p in pages if p < 1 or p > total]
                    if invalid_pages:
                        logger.warning(f"Các trang không hợp lệ (nằm ngoài 1-{total}): {invalid_pages}. Bỏ qua.")
                    if not valid_pages:
                        logger.error("Không có trang hợp lệ nào để extract.")
                        return ""
                    logger.info(f"Extract text: Chỉ extract {len(valid_pages)} trang: {valid_pages}")
                    pages_to_extract = sorted(set(valid_pages))
                else:
                    pages_to_extract = list(range(1, total + 1))
                
                show_progress = bool(ocr_cfg.get("show_progress", True))
                
                if show_progress and tqdm is not None and len(pages_to_extract) > 1:
                    for page_num in config.tqdm(pages_to_extract, desc="Extract text", unit="trang"):
                        page = reader.pages[page_num - 1]  # PyPDF2 dùng 0-indexed
                        text = page.extract_text()
                        if text:
                            texts.append(text.strip())
                else:
                    for page_num in pages_to_extract:
                        page = reader.pages[page_num - 1]  # PyPDF2 dùng 0-indexed
                        text = page.extract_text()
                        if text:
                            texts.append(text.strip())
                        if len(texts) % 50 == 0:
                            logger.info(f"Extract text: {len(texts)}/{len(pages_to_extract)} trang")
                return "\n\n".join(texts)
        except Exception as e:
            logger.error(f"PyPDF2 failed: {e}")
            raise
    
    raise RuntimeError("Không có thư viện extract PDF text. Cài pdfplumber hoặc PyPDF2.")

def extract_text_blocks_with_position(pdf_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> tuple[List[dict], int]:
    """
    Extract text blocks với Y-position từ PDF (dùng pdfplumber hoặc PyMuPDF).
    
    Returns:
        tuple: (text_blocks_by_page, total_pages) trong đó text_blocks_by_page là dict:
            {page_num: [{"text": str, "y_position": float, "x_position": float, "bbox": tuple}, ...]}
    """
    text_blocks_by_page = {}
    total_pages = 0
    
    # Ưu tiên pdfplumber (có bbox chính xác hơn)
    if pdfplumber is not None:
        try:
            with config.pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                
                if pages:
                    pages_to_extract = sorted(set([p for p in pages if 1 <= p <= total_pages]))
                else:
                    pages_to_extract = list(range(1, total_pages + 1))
                
                for page_num in pages_to_extract:
                    page = pdf.pages[page_num - 1]
                    text_blocks = []
                    
                    # Extract text với bbox từ pdfplumber
                    words = page.extract_words()
                    if words:
                        # Group words thành blocks dựa trên Y-position (same line)
                        current_block = []
                        current_y = None
                        
                        for word in words:
                            word_y = word.get("top", 0)  # Y-position của word
                            word_text = word.get("text", "")
                            word_x = word.get("x0", 0)
                            
                            # Nếu Y khác biệt nhiều (> threshold), tạo block mới
                            if current_y is None or abs(word_y - current_y) > 5:  # 5px threshold
                                if current_block:
                                    # Save previous block
                                    block_text = " ".join([w["text"] for w in current_block])
                                    block_y = current_block[0].get("top", 0)
                                    block_x = min([w.get("x0", 0) for w in current_block])
                                    block_bbox = (
                                        min([w.get("x0", 0) for w in current_block]),
                                        current_block[0].get("top", 0),
                                        max([w.get("x1", 0) for w in current_block]),
                                        max([w.get("bottom", 0) for w in current_block])
                                    )
                                    text_blocks.append({
                                        "text": block_text,
                                        "y_position": block_y,
                                        "x_position": block_x,
                                        "bbox": block_bbox
                                    })
                                current_block = [word]
                                current_y = word_y
                            else:
                                current_block.append(word)
                        
                        # Save last block
                        if current_block:
                            block_text = " ".join([w["text"] for w in current_block])
                            block_y = current_block[0].get("top", 0)
                            block_x = min([w.get("x0", 0) for w in current_block])
                            block_bbox = (
                                min([w.get("x0", 0) for w in current_block]),
                                current_block[0].get("top", 0),
                                max([w.get("x1", 0) for w in current_block]),
                                max([w.get("bottom", 0) for w in current_block])
                            )
                            text_blocks.append({
                                "text": block_text,
                                "y_position": block_y,
                                "x_position": block_x,
                                "bbox": block_bbox
                            })
                    
                    text_blocks_by_page[page_num] = text_blocks
                
                return text_blocks_by_page, total_pages
        except Exception as e:
            logger.warning(f"pdfplumber extract text blocks failed: {e}, fallback to PyMuPDF...")
    
    # Fallback: PyMuPDF (extract text blocks với bbox)
    if fitz is not None:
        try:
            doc = config.fitz.open(pdf_path)
            total_pages = len(doc)
            
            if pages:
                pages_to_extract = sorted(set([p for p in pages if 1 <= p <= total_pages]))
            else:
                pages_to_extract = list(range(1, total_pages + 1))
            
            for page_num in pages_to_extract:
                page = doc[page_num - 1]
                text_blocks = []
                
                # Extract text blocks với bbox từ PyMuPDF
                blocks = page.get_text("dict")  # Get text as dict with bbox info
                if blocks and "blocks" in blocks:
                    for block in blocks["blocks"]:
                        if "lines" in block:  # Text block
                            block_text = ""
                            min_y = float('inf')
                            min_x = float('inf')
                            max_x = float('-inf')
                            max_y = float('-inf')
                            
                            for line in block["lines"]:
                                for span in line.get("spans", []):
                                    span_text = span.get("text", "")
                                    bbox = span.get("bbox", [0, 0, 0, 0])
                                    
                                    if span_text:
                                        block_text += span_text + " "
                                    
                                    # Update bbox
                                    min_y = min(min_y, bbox[1])  # top (Y)
                                    min_x = min(min_x, bbox[0])  # left (X)
                                    max_x = max(max_x, bbox[2])  # right
                                    max_y = max(max_y, bbox[3])  # bottom
                            
                            if block_text.strip():
                                text_blocks.append({
                                    "text": block_text.strip(),
                                    "y_position": min_y,
                                    "x_position": min_x,
                                    "bbox": (min_x, min_y, max_x, max_y)
                                })
                
                text_blocks_by_page[page_num] = text_blocks
            
            doc.close()
            return text_blocks_by_page, total_pages
        except Exception as e:
            logger.warning(f"PyMuPDF extract text blocks failed: {e}")
    
    # Fallback: không có position, return empty
    logger.warning("Không thể extract text blocks với position. Trả về empty.")
    return {}, total_pages if total_pages > 0 else 0

def convert_pdf_with_ocrmypdf(pdf_path: str, output_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> str:
    """
    Convert PDF → PDF searchable bằng OCRmyPDF (thêm OCR layer).
    
    Args:
        pdf_path: Đường dẫn file PDF input
        output_path: Đường dẫn file PDF output (searchable)
        ocr_cfg: Config dictionary
        pages: Danh sách số trang cần OCR (1-indexed). None = tất cả trang.
    
    Returns:
        str: Đường dẫn file PDF đã tạo (searchable)
    
    Raises:
        RuntimeError: Nếu OCRmyPDF chưa được cài đặt hoặc conversion fail
    """
    global ocrmypdf, ocrmypdf_available
    
    if not ocrmypdf_available or ocrmypdf is None:
        raise RuntimeError("OCRmyPDF chưa được cài đặt. Cài ocrmypdf để dùng fallback workflow.")
    
    logger.info(f"🔍 Đang dùng OCRmyPDF để tạo PDF searchable: {pdf_path}")
    
    # Validate input PDF
    if not os.path.exists(pdf_path):
        raise RuntimeError(f"File PDF không tồn tại: {pdf_path}")
    
    file_size = os.path.getsize(pdf_path)
    if file_size < 100:
        raise RuntimeError(f"File PDF quá nhỏ hoặc không hợp lệ: {pdf_path} ({file_size} bytes)")
    
    # Kiểm tra magic bytes (PDF signature)
    try:
        with open(pdf_path, 'rb') as f:
            header = f.read(4)
            if header != b'%PDF':
                raise RuntimeError(f"File không phải PDF hợp lệ (magic bytes: {header}): {pdf_path}")
    except Exception as e:
        raise RuntimeError(f"Không thể đọc file PDF: {e}")
    
    try:
        # Tạo temp file nếu output_path trùng với input_path
        temp_output = None
        if os.path.abspath(pdf_path) == os.path.abspath(output_path):
            temp_output = output_path + ".tmp"
            final_output = output_path
        else:
            final_output = output_path
        
        # Chuẩn bị command cho OCRmyPDF (gọi qua subprocess)
        cmd = ["ocrmypdf"]
        
        # Language settings từ config
        # Normalize language code từ config format (VN/EN/CN) sang OCRmyPDF format (vie/eng/chi_sim)
        raw_lang = ocr_cfg.get("lang", "eng")
        if raw_lang:
            # Sử dụng hàm normalize đã có để convert format
            lang_normalized = _normalize_lang_code(raw_lang)
            # OCRmyPDF hỗ trợ multiple languages với dấu +, ví dụ: "vie+eng"
            cmd.extend(["-l", lang_normalized])
            if lang_normalized != raw_lang:
                logger.debug(f"Normalized language code: '{raw_lang}' → '{lang_normalized}'")
        
        # Deskew option (làm thẳng trang nghiêng)
        if ocr_cfg.get("deskew", False):
            cmd.append("--deskew")
        
        # Rotate pages option
        if ocr_cfg.get("rotate_pages", False):
            cmd.append("--rotate-pages")
        
        # Jobs (multi-core)
        jobs = ocr_cfg.get("jobs", 1)
        if jobs and jobs > 1:
            cmd.extend(["--jobs", str(jobs)])
        
        # Skip text pages (tối ưu cho PDF đã có text layer)
        if ocr_cfg.get("skip_text", False):
            cmd.append("--skip-text")
            logger.debug("OCRmyPDF: Bật --skip-text (bỏ qua pages đã có text)")
        
        # Force OCR (khi cần OCR lại cả text layer)
        if ocr_cfg.get("force_ocr", False):
            cmd.append("--force-ocr")
            logger.debug("OCRmyPDF: Bật --force-ocr (OCR lại cả text layer)")
        
        # Optimize output file
        optimize_level = ocr_cfg.get("optimize_level", None)
        optimize_flag_added = False
        if optimize_level is not None:
            try:
                lvl = int(optimize_level)
                if lvl > 0:
                    cmd.extend(["--optimize", str(lvl)])
                    optimize_flag_added = True
                    logger.debug(f"OCRmyPDF: --optimize {lvl}")
                else:
                    logger.debug("OCRmyPDF: optimize_level=0 → không tối ưu để tránh lỗi extract_images")
            except Exception:
                pass
        elif ocr_cfg.get("optimize", True):  # Mặc định bật optimize nếu không có optimize_level
            cmd.append("--optimize")
            optimize_flag_added = True
            logger.debug("OCRmyPDF: Bật --optimize (tối ưu kích thước file)")
        
        # Extra args cho OCRmyPDF (nếu có)
        extra_args = ocr_cfg.get("ocrmypdf_extra_args", [])
        if isinstance(extra_args, (list, tuple)) and extra_args:
            cmd.extend([str(a) for a in extra_args])
            logger.debug(f"OCRmyPDF: Thêm extra args: {extra_args}")
        
        # Pages (OCRmyPDF hỗ trợ pages thông qua --pages)
        # Format: "1,3,5" hoặc "1-5" hoặc "1,3-5"
        if pages:
            valid_pages = sorted(set(pages))
            # Tối ưu format: "1-3" thay vì "1,2,3" nếu liên tục
            pages_ranges = []
            i = 0
            while i < len(valid_pages):
                start = valid_pages[i]
                end = start
                # Tìm chuỗi liên tục
                while i + 1 < len(valid_pages) and valid_pages[i + 1] == end + 1:
                    i += 1
                    end = valid_pages[i]
                
                if start == end:
                    pages_ranges.append(str(start))
                else:
                    pages_ranges.append(f"{start}-{end}")
                i += 1
            
            pages_str = ",".join(pages_ranges)
            cmd.extend(["--pages", pages_str])
            logger.info(f"Chỉ OCR {len(valid_pages)} trang: {valid_pages} (format: {pages_str})")
        
        # Add input và output paths
        cmd.append(pdf_path)
        cmd.append(temp_output if temp_output else final_output)
        
        # Gọi OCRmyPDF qua subprocess (command line)
        logger.info(f"Chạy OCRmyPDF: {' '.join(cmd)}")
        
        # Đảm bảo Ghostscript trong PATH cho subprocess
        env = os.environ.copy()
        current_path = env.get("PATH", "")
        
        # Tìm Ghostscript tự động
        gs_bin_path = None
        # Thử các đường dẫn phổ biến
        possible_paths = [
            r"C:\Program Files\gs\gs10.06.0\bin",
            r"C:\Program Files\gs\gs10.05.0\bin",
            r"C:\Program Files\gs\gs10.04.0\bin",
            r"C:\Program Files (x86)\gs\gs10.06.0\bin",
            r"C:\Program Files (x86)\gs\gs10.05.0\bin",
        ]
        
        # Tìm trong Program Files
        if sys.platform == "win32":
            import glob
            for pattern in [r"C:\Program Files\gs\gs*\bin", r"C:\Program Files (x86)\gs\gs*\bin"]:
                matches = glob.glob(pattern)
                if matches:
                    # Sort để lấy version mới nhất
                    matches.sort(reverse=True)
                    gs_bin_path = matches[0]
                    logger.info(f"✅ Tìm thấy Ghostscript: {gs_bin_path}")
                    break
        
        # Nếu không tìm thấy, thử các đường dẫn phổ biến
        if not gs_bin_path:
            for path in possible_paths:
                if os.path.exists(path) and os.path.exists(os.path.join(path, "gswin64c.exe")):
                    gs_bin_path = path
                    logger.info(f"✅ Tìm thấy Ghostscript: {gs_bin_path}")
                    break
        
        # Thêm vào PATH nếu tìm thấy (luôn thêm vào đầu để đảm bảo ưu tiên)
        if gs_bin_path:
            # Luôn thêm vào đầu PATH để đảm bảo subprocess tìm thấy
            env["PATH"] = gs_bin_path + os.pathsep + current_path
            logger.info(f"✅ Đã thêm Ghostscript vào PATH cho subprocess: {gs_bin_path}")
            
            # Verify Ghostscript có hoạt động trong env này không
            try:
                test_result = subprocess.run(
                    ["gswin64c", "--version"],
                    capture_output=True,
                    text=True,
                    env=env,
                    timeout=5
                )
                if test_result.returncode == 0:
                    logger.info(f"✅ Verified Ghostscript: {test_result.stdout.strip()}")
                else:
                    logger.warning(f"⚠️  Ghostscript test failed trong subprocess env")
            except Exception as e:
                logger.debug(f"Không thể verify Ghostscript: {e}")
        else:
            logger.warning("⚠️  Không tìm thấy Ghostscript, OCRmyPDF có thể fail")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # Timeout 1 giờ
            env=env  # Pass environment với PATH đã cập nhật
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            # Log chi tiết lỗi để debug
            logger.debug(f"OCRmyPDF stderr: {result.stderr[:500] if result.stderr else 'None'}")
            logger.debug(f"OCRmyPDF stdout: {result.stdout[:500] if result.stdout else 'None'}")
            # Retry nếu lỗi do extract_images/optimize
            em_lower = (error_msg or "").lower()
            if ("extract_images" in em_lower) or ("optimize.py" in em_lower):
                logger.warning("⚠️  OCRmyPDF lỗi khi tối ưu ảnh (extract_images). Thử lại với --optimize 0...")
                # Loại bỏ các cờ optimize khỏi cmd và đặt optimize 0
                cmd_no_opt = [a for a in cmd if a != "--optimize"]
                # Nếu có dạng --optimize <level>, loại bỏ cả level đi
                try:
                    while "--optimize" in cmd_no_opt:
                        idx = cmd_no_opt.index("--optimize")
                        # Bỏ cả tham số tiếp theo nếu là số
                        del cmd_no_opt[idx]
                        if idx < len(cmd_no_opt) and str(cmd_no_opt[idx]).isdigit():
                            del cmd_no_opt[idx]
                except Exception:
                    pass
                # Thêm optimize 0 để tắt tối ưu
                cmd_retry = []
                for a in cmd_no_opt:
                    cmd_retry.append(a)
                cmd_retry.insert(1, "--optimize")
                cmd_retry.insert(2, "0")
                logger.info(f"Thử lại: {' '.join(cmd_retry)}")
                result_retry = subprocess.run(
                    cmd_retry,
                    capture_output=True,
                    text=True,
                    timeout=3600,
                    env=env
                )
                if result_retry.returncode == 0:
                    # Gán result để tiếp tục các bước sau
                    result = result_retry
                else:
                    logger.debug(f"Retry stderr: {result_retry.stderr[:500] if result_retry.stderr else 'None'}")
                    raise subprocess.CalledProcessError(result_retry.returncode, cmd_retry, output=result_retry.stdout, stderr=result_retry.stderr)
            else:
                raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stdout, stderr=result.stderr)
        
        # Move temp file nếu cần
        if temp_output and os.path.exists(temp_output):
            if os.path.exists(final_output):
                os.remove(final_output)
            os.rename(temp_output, final_output)
        
        # Validate output file
        if not os.path.exists(final_output):
            raise RuntimeError(f"OCRmyPDF conversion thất bại: File output không tồn tại: {final_output}")
        
        file_size = os.path.getsize(final_output)
        if file_size < 100:  # PDF tối thiểu phải > 100 bytes
            raise RuntimeError(f"OCRmyPDF conversion thất bại: File output quá nhỏ ({file_size} bytes)")
        
        logger.info(f"✅ Đã tạo PDF searchable bằng OCRmyPDF: {final_output} ({file_size} bytes)")
        return final_output
        
    except FileNotFoundError:
        raise RuntimeError(
            "OCRmyPDF không được tìm thấy trên PATH.\n"
            "Cài đặt: pip install ocrmypdf\n"
            "Đảm bảo OCRmyPDF đã được cài đặt và có trong PATH."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("OCRmyPDF timeout sau 1 giờ. File có thể quá lớn hoặc có vấn đề.")
    except subprocess.CalledProcessError as e:
        error_output = e.stderr if e.stderr else (e.stdout if e.stdout else str(e))
        # Log chi tiết để debug
        logger.debug(f"OCRmyPDF error (exit code {e.returncode}): {error_output[:1000]}")
        if 'ghostscript' in error_output.lower() or 'gswin64c' in error_output.lower() or 'gs' in error_output.lower():
            raise RuntimeError(
                "OCRmyPDF cần Ghostscript nhưng không tìm thấy trên PATH.\n"
                "💡 Cài đặt Ghostscript:\n"
                "   - Windows: choco install ghostscript\n"
                "   - Hoặc tải từ: https://www.ghostscript.com/download/gsdnld.html\n"
                "   - Đảm bảo thêm Ghostscript vào PATH sau khi cài đặt"
            )
        elif 'tesseract' in error_output.lower():
            raise RuntimeError(
                "OCRmyPDF cần Tesseract OCR nhưng không tìm thấy.\n"
                "💡 Cài đặt Tesseract:\n"
                "   - Windows: choco install tesseract\n"
                "   - Hoặc tải từ: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "   - Đảm bảo thêm Tesseract vào PATH sau khi cài đặt"
            )
        else:
            raise RuntimeError(f"OCRmyPDF thất bại (exit code {e.returncode}): {error_output}")
    except Exception as e:
        error_msg = str(e)
        if 'ghostscript' in error_msg.lower() or 'gswin64c' in error_msg.lower() or 'gs' in error_msg.lower():
            raise RuntimeError(
                "OCRmyPDF cần Ghostscript nhưng không tìm thấy trên PATH.\n"
                "💡 Cài đặt Ghostscript:\n"
                "   - Windows: choco install ghostscript\n"
                "   - Hoặc tải từ: https://www.ghostscript.com/download/gsdnld.html\n"
                "   - Đảm bảo thêm Ghostscript vào PATH sau khi cài đặt"
            )
        logger.error(f"❌ Lỗi khi dùng OCRmyPDF: {error_msg}")
        import traceback
        logger.debug(traceback.format_exc())
        raise

