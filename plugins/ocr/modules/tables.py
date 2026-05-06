from . import config
from .image import _normalize_lang_code
from .pdf import convert_pdf_with_ocrmypdf

def _extract_tables_with_unstructured(pdf_path: str, output_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> dict:
    """
    Extract bảng từ PDF bằng unstructured.io (độ chính xác 95-98%).
    
    Đây là phương pháp được khuyến cáo nhất theo Grok review:
    - Sử dụng unstructured.io với OCRmyPDF để tự động detect layout
    - Tự động gộp multi-line cell
    - Phát hiện chính xác bảng không có đường kẻ
    - Không cần tự viết alignment phức tạp
    
    Returns:
        dict: {page_num: {"rows": [[cell1, cell2, ...], ...], "num_cols": int}}
    """
    try:
        # Lazy import unstructured
        try:
            from unstructured.partition.pdf import partition_pdf
            from unstructured.documents.elements import Table
        except ImportError:
            logger.warning("⚠️  unstructured.io chưa được cài đặt. Cài bằng: pip install unstructured[pdf]")
            logger.warning("💡 Hoặc dùng phương pháp fallback (pytesseract + DBSCAN)")
            return {}
        
        logger.info("🔍 Đang extract bảng bằng unstructured.io (độ chính xác cao)...")
        
        tables_by_page = {}
        
        # Partition PDF với strategy hi_res (OCR + layout detection)
        try:
            elements = partition_pdf(
                filename=pdf_path,
                strategy="hi_res",  # Quan trọng: dùng OCR + layout detection
                infer_table_structure=True,  # Bật nhận diện bảng
                languages=["vie", "eng"],  # Hỗ trợ tiếng Việt và Anh
            )
        except Exception as e:
            logger.warning(f"⚠️  unstructured.io partition thất bại: {e}")
            logger.warning("💡 Fallback về phương pháp khác...")
            return {}
        
        # Extract tables từ elements
        current_page = 1
        for element in elements:
            if isinstance(element, Table):
                # Convert table thành list of rows
                rows = []
                if hasattr(element, 'metadata') and element.metadata.page_number:
                    current_page = element.metadata.page_number
                
                # Lấy text từ table (unstructured đã gộp multi-line cell)
                if hasattr(element, 'text_as_html'):
                    # Parse HTML table
                    import re
                    html_text = element.text_as_html
                    # Simple HTML table parser (có thể cải thiện)
                    # Tìm tất cả <tr>...</tr>
                    tr_pattern = r'<tr[^>]*>(.*?)</tr>'
                    tr_matches = re.findall(tr_pattern, html_text, re.DOTALL | re.IGNORECASE)
                    
                    for tr_match in tr_matches:
                        # Tìm tất cả <td>...</td> hoặc <th>...</th>
                        td_pattern = r'<t[dh][^>]*>(.*?)</t[dh]>'
                        td_matches = re.findall(td_pattern, tr_match, re.DOTALL | re.IGNORECASE)
                        
                        # Clean HTML tags và whitespace
                        cells = []
                        for td_text in td_matches:
                            # Loại bỏ HTML tags
                            cell_text = re.sub(r'<[^>]+>', '', td_text)
                            # Clean whitespace
                            cell_text = " ".join(cell_text.split())
                            cells.append(cell_text)
                        
                        if cells:
                            rows.append(cells)
                elif hasattr(element, 'text'):
                    # Fallback: parse từ text (ít chính xác hơn)
                    lines = element.text.split('\n')
                    for line in lines:
                        if line.strip():
                            # Giả định delimiter là tab hoặc nhiều spaces
                            cells = [c.strip() for c in re.split(r'\t+|\s{2,}', line) if c.strip()]
                            if cells:
                                rows.append(cells)
                
                if rows:
                    # Tìm số cột tối đa
                    max_cols = max(len(row) for row in rows) if rows else 0
                    
                    # Pad các hàng để có cùng số cột
                    normalized_rows = []
                    for row in rows:
                        normalized_row = row + [""] * (max_cols - len(row)) if len(row) < max_cols else row[:max_cols]
                        normalized_rows.append(normalized_row)
                    
                    tables_by_page[current_page] = {
                        "page": current_page,
                        "rows": normalized_rows,
                        "num_cols": max_cols
                    }
                    logger.info(f"✅ unstructured.io: Đã extract bảng trang {current_page}: {len(normalized_rows)} hàng, {max_cols} cột")
        
        if tables_by_page:
            logger.info(f"✅ unstructured.io: Hoàn tất extract {len(tables_by_page)} bảng")
            return tables_by_page
        else:
            logger.info("ℹ️  unstructured.io: Không tìm thấy bảng")
            return {}
            
    except Exception as e:
        logger.warning(f"⚠️  Lỗi khi extract bảng bằng unstructured.io: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return {}

def _extract_tables_pytesseract_advanced(img: "config.Image.Image", ocr_cfg: dict, page_num: int = 1) -> List[List[str]]:
    """
    Extract bảng từ ảnh bằng pytesseract với DBSCAN clustering (cải thiện từ Grok).
    
    Cải thiện so với cách cũ:
    - Dùng image_to_data với level=5 (word)
    - Cluster theo X để tìm cột (DBSCAN tự động tìm số cột)
    - Cluster theo Y để tìm hàng
    - Gộp các word thuộc cùng ô (multi-line, multi-word)
    
    Returns:
        List[List[str]]: List các hàng, mỗi hàng là list các ô
    """
    try:
        import pytesseract
        import numpy as np
        from sklearn.cluster import DBSCAN
    except ImportError as e:
        logger.warning(f"⚠️  Thiếu dependency cho advanced pytesseract: {e}")
        return []
    
    # Lấy config
    lang = ocr_cfg.get("lang", "vie")
    psm = ocr_cfg.get("psm", 6)  # PSM 6 tốt hơn cho bảng
    
    # Extract data với pytesseract
    try:
        data = config.pytesseract.image_to_data(
            img, lang=lang, output_type=config.pytesseract.Output.DICT,
            config=f"--psm {psm} --oem 3"
        )
    except Exception as e:
        logger.warning(f"⚠️  pytesseract image_to_data thất bại: {e}")
        return []
    
    # Lọc chỉ word có text và conf > 30
    words = []
    for i in range(len(data.get("text", []))):
        conf = int(data.get("conf", [0])[i]) if i < len(data.get("conf", [])) else 0
        text = data.get("text", [""])[i] if i < len(data.get("text", [])) else ""
        
        if conf > 30 and text.strip():
            left = data.get("left", [0])[i] if i < len(data.get("left", [])) else 0
            top = data.get("top", [0])[i] if i < len(data.get("top", [])) else 0
            width = data.get("width", [0])[i] if i < len(data.get("width", [])) else 0
            height = data.get("height", [0])[i] if i < len(data.get("height", [])) else 0
            
            words.append({
                "text": text.strip(),
                "left": left,
                "top": top,
                "width": width,
                "height": height,
                "right": left + width,
                "bottom": top + height,
                "x_center": left + width // 2,
                "y_center": top + height // 2,
            })
    
    if not words:
        logger.debug(f"Trang {page_num}: Không có word nào được detect")
        return []
    
    # 1. Cluster cột theo X (DBSCAN tự động tìm số cột)
    X_coords = np.array([[w["x_center"]] for w in words])
    clustering = DBSCAN(eps=30, min_samples=2).fit(X_coords)  # eps=30 pixels
    col_labels = clustering.labels_
    
    # 2. Gán từng word vào cột
    col_to_words = {}
    for label, word in zip(col_labels, words):
        if label != -1:  # Không phải noise
            col_to_words.setdefault(label, []).append(word)
    
    if not col_to_words:
        logger.debug(f"Trang {page_num}: Không tìm thấy cột hợp lệ")
        return []
    
    # Sắp xếp cột từ trái sang phải
    sorted_cols = sorted(col_to_words.items(), key=lambda x: np.mean([w["x_center"] for w in x[1]]))
    
    # 3. Với mỗi cột → cluster hàng theo Y
    row_groups_by_col = []
    
    for col_idx, (label, col_words) in enumerate(sorted_cols):
        Y_coords = np.array([[w["y_center"]] for w in col_words])
        row_clustering = DBSCAN(eps=20, min_samples=1).fit(Y_coords)
        row_labels = row_clustering.labels_
        
        # Gán word vào hàng trong cột này
        row_dict = {}
        for row_label, word in zip(row_labels, col_words):
            row_dict.setdefault(row_label, []).append(word)
        
        # Sắp xếp các hàng theo Y
        sorted_rows = sorted(row_dict.items(), key=lambda x: np.mean([w["y_center"] for w in x[1]]))
        row_groups_by_col.append(sorted_rows)
    
    # 4. Ghép các hàng tương ứng giữa các cột → tạo bảng
    if not row_groups_by_col:
        return []
    
    max_rows = max(len(rows) for rows in row_groups_by_col)
    table_rows = []
    
    for row_idx in range(max_rows):
        row_cells = []
        for col_group in row_groups_by_col:
            if row_idx < len(col_group):
                cell_words = sorted(col_group[row_idx][1], key=lambda w: w["left"])
                cell_text = " ".join(w["text"] for w in cell_words).strip()
            else:
                cell_text = ""
            row_cells.append(cell_text)
        
        # Chỉ thêm hàng nếu có ít nhất một ô có nội dung
        if any(cell.strip() for cell in row_cells):
            table_rows.append(row_cells)
    
    return table_rows

def _try_extract_tables_from_pdf_via_ocrmypdf(pdf_path: str, output_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> dict:
    """Tạo searchable PDF bằng OCRmyPDF rồi thử extract bảng bằng pdfplumber.
    
    Trả về dict {page_num: {"rows": [...], "num_cols": int}} thay vì tạo CSV file.
    
    Lưu ý: Đây là bước nhẹ, chỉ thực hiện khi tables.reconstruct = true.
    
    Returns:
        dict: {page_num: {"rows": [[cell1, cell2, ...], ...], "num_cols": int}}
    """
    try:
        if pdfplumber is None:
            logger.warning("⚠️  pdfplumber không khả dụng → bỏ qua extract bảng")
            return {}
        
        # Strategy 1: Thử extract từ PDF gốc trước (có thể có text layer ẩn)
        source_pdf = None
        use_searchable = False
        
        logger.info("🔍 Thử extract bảng từ PDF gốc trước...")
        try:
            with config.pdfplumber.open(pdf_path) as pdf:
                test_page = pdf.pages[0] if len(pdf.pages) > 0 else None
                if test_page:
                    test_tables = test_page.extract_tables()
                    if test_tables:
                        logger.info("✅ PDF gốc có text layer → extract trực tiếp từ PDF gốc")
                        source_pdf = pdf_path
                        use_searchable = False
                    else:
                        raise ValueError("PDF gốc không có text layer")
                else:
                    raise ValueError("PDF không có trang")
        except Exception as e:
            logger.debug(f"PDF gốc không có text layer: {e}")
            # Strategy 2: Tạo searchable PDF bằng OCRmyPDF
            if not ocrmypdf_available:
                logger.warning("⚠️  OCRmyPDF không khả dụng và PDF gốc không có text layer")
                logger.warning("💡 Để extract bảng từ PDF scan, cần cài Ghostscript:")
                logger.warning("   - Windows: choco install ghostscript")
                logger.warning("   - Hoặc tải từ: https://www.ghostscript.com/download/gsdnld.html")
                # Không return, để tiếp tục đến fallback OpenCV
                source_pdf = None
            else:
                temp_searchable_pdf = os.path.splitext(output_path)[0] + "_searchable_for_tables.pdf"
                logger.info(f"📄 Tạo searchable PDF để extract bảng: {temp_searchable_pdf}")
                try:
                    # Tạo searchable PDF (nhanh vì chỉ phục vụ table detect)
                    # Override optimize=0 để tránh lỗi extract_images trong optimize.py
                    ocr_cfg_no_opt = dict(ocr_cfg)
                    ocr_cfg_no_opt["optimize"] = False
                    ocr_cfg_no_opt["optimize_level"] = 0
                    convert_pdf_with_ocrmypdf(pdf_path, temp_searchable_pdf, ocr_cfg_no_opt, pages)
                    source_pdf = temp_searchable_pdf
                    use_searchable = True
                except Exception as e:
                    logger.warning(f"⚠️  Không thể tạo searchable PDF: {e}")
                    logger.warning("💡 Có thể cần cài Ghostscript để extract bảng từ PDF scan")
                    # Không return, để tiếp tục đến fallback OpenCV
                    source_pdf = None
        
        if source_pdf is None:
            # Fallback cuối: trích bảng từ ảnh bằng OpenCV nếu được cấu hình
            tables_mode = (ocr_cfg.get("tables") or {}).get("mode", "auto")
            if tables_mode in ("auto", "opencv_grid"):
                logger.info("🧭 Fallback: Dùng OpenCV để trích xuất bảng trực tiếp từ ảnh")
                try:
                    tables_dict = _extract_tables_from_images_cv(pdf_path, output_path, ocr_cfg, pages)
                    return tables_dict  # Trả về dict thay vì None
                except Exception as cv_err:
                    logger.warning(f"⚠️  Fallback OpenCV thất bại: {cv_err}")
                    return {}
            logger.warning("⚠️  Không thể xác định source PDF để extract bảng")
            return {}
        
        logger.info("🔍 Bắt đầu extract bảng từ PDF...")
        # Extract tables per page - lưu vào dict thay vì CSV
        base = os.path.splitext(output_path)[0]
        found_any = False
        total_tables = 0
        tables_by_page = {}  # {page_num: {"rows": [...], "num_cols": int}}
        
        if not os.path.exists(source_pdf):
            logger.warning(f"⚠️  PDF không tồn tại: {source_pdf}")
            return {}
        
        with config.pdfplumber.open(source_pdf) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"📖 Đang scan {total_pages} trang để tìm bảng...")
            
            # Nếu có pages chỉ định, chỉ xử lý những trang đó
            page_indices = list(range(total_pages))
            if pages:
                # Convert 1-indexed to 0-indexed
                page_indices = [p - 1 for p in pages if 1 <= p <= total_pages]
                logger.info(f"📄 Chỉ extract bảng từ {len(page_indices)} trang: {pages}")
            
            for page_idx in page_indices:
                try:
                    page = pdf.pages[page_idx]
                    # Thử cả lattice và stream strategy
                    tables = page.extract_tables()
                    if not tables:
                        # Thử với strategy khác
                        try:
                            tables = page.extract_tables(strategy="lattice")
                        except Exception:
                            try:
                                tables = page.extract_tables(strategy="stream")
                            except Exception:
                                tables = []
                    
                    if not tables:
                        logger.debug(f"Trang {page_idx + 1}: Không tìm thấy bảng")
                        continue
                    
                    found_any = True
                    table_count = len(tables)
                    total_tables += table_count
                    logger.info(f"📊 Trang {page_idx + 1}: Tìm thấy {table_count} bảng")
                    
                    # Gộp tất cả tables trên trang thành một bảng lớn
                    all_rows = []
                    max_cols = 0
                    for tbl_idx, tbl in enumerate(tables, start=1):
                        if tbl_idx > 1:
                            # Thêm hàng trống giữa các bảng
                            all_rows.append([""] * max_cols)
                        for row in tbl:
                            if row:  # Skip empty rows
                                cleaned_row = [(cell or "").strip() for cell in row]
                                all_rows.append(cleaned_row)
                                max_cols = max(max_cols, len(cleaned_row))
                    
                    # Pad các hàng để có cùng số cột
                    for row in all_rows:
                        while len(row) < max_cols:
                            row.append("")
                    
                    tables_by_page[page_idx + 1] = {
                        "page": page_idx + 1,
                        "rows": all_rows,
                        "num_cols": max_cols
                    }
                    logger.info(f"🗂️  Đã extract bảng trang {page_idx + 1}: {len(all_rows)} hàng, {max_cols} cột")
                except Exception as e:
                    logger.warning(f"⚠️  Extract bảng lỗi ở trang {page_idx + 1}: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
                    continue
        
        # Cleanup temp và trả về kết quả
        if found_any:
            logger.info(f"✅ Hoàn tất extract bảng: {total_tables} bảng từ {len(tables_by_page)} trang")
            # Cleanup temp (chỉ nếu dùng searchable PDF)
            if use_searchable:
                try:
                    if os.path.exists(source_pdf) and ocr_cfg.get("cleanup_temp_searchable_pdf", True):
                        os.remove(source_pdf)
                        logger.debug(f"🗑️  Đã xóa temp searchable PDF: {source_pdf}")
                except Exception as e:
                    logger.debug(f"Không thể xóa temp file: {e}")
            return tables_by_page
        else:
            logger.info("ℹ️  Không tìm thấy bảng trong PDF (có thể PDF không có bảng hoặc OCR chưa đủ tốt)")
            return {}
    except Exception as e:
        logger.error(f"❌ _try_extract_tables_from_pdf_via_ocrmypdf lỗi: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return {}

def _extract_tables_from_images_cv(pdf_path: str, output_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> dict:
    """Fallback: Trích xuất bảng từ ảnh PDF bằng OpenCV (phát hiện lưới).

    - Render PDF → ảnh bằng pdf2image (dựa vào poppler_path trong config)
    - Dùng OpenCV morphology để tìm đường kẻ dọc/ngang → xác định ô
    - Trả về dict {page_num: {rows, num_cols, metadata}} thay vì tạo CSV file
    
    Returns:
        dict: {page_num: {"rows": [[cell1, cell2, ...], ...], "num_cols": int, "metadata": [...]}}
    """
    try:
        from pdf2image import convert_from_path as _convert_from_path
    except Exception as e:
        logger.warning(f"⚠️  Thiếu pdf2image: {e}")
        return {}
    try:
        import cv2
        import numpy as np
    except Exception as e:
        logger.warning(f"⚠️  Thiếu OpenCV/numpy: {e}")
        return

    poppler_path = ocr_cfg.get("poppler_path") or os.environ.get("POPPLER_PATH")
    dpi = int(ocr_cfg.get("dpi", 250))

    # Xác định trang cần render
    try:
        from PyPDF2 import PdfReader as _PdfReader
        total = len(_PdfReader(open(pdf_path, 'rb')).pages)
    except Exception:
        total = None
    if pages:
        page_indices = [p for p in pages if p >= 1 and (total is None or p <= total)]
    else:
        page_indices = [1]

    images = _config.convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path, first_page=min(page_indices),
                                last_page=max(page_indices))

    base = os.path.splitext(output_path)[0]
    exported = 0
    tables_by_page = {}  # {page_num: {"rows": [...], "num_cols": int, "metadata": [...]}}
    for i, pil_img in enumerate(images, start=min(page_indices)):
        # Chuyển PIL → OpenCV BGR
        img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Nhị phân hoá & đảo màu (để line rõ hơn)
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                   cv2.THRESH_BINARY, 15, -2)
        bw_inv = 255 - bw

        # Tách đường kẻ dọc
        vertical = bw_inv.copy()
        rows = vertical.shape[0]
        vertical_size = max(1, rows // 40)
        verticalStructure = cv2.getStructuringElement(cv2.MORPH_RECT, (1, vertical_size))
        vertical = cv2.erode(vertical, verticalStructure)
        vertical = cv2.dilate(vertical, verticalStructure)

        # Tách đường kẻ ngang
        horizontal = bw_inv.copy()
        cols = horizontal.shape[1]
        horizontal_size = max(1, cols // 40)
        horizontalStructure = cv2.getStructuringElement(cv2.MORPH_RECT, (horizontal_size, 1))
        horizontal = cv2.erode(horizontal, horizontalStructure)
        horizontal = cv2.dilate(horizontal, horizontalStructure)

        # Kết hợp để được lưới
        grid = cv2.addWeighted(vertical, 0.5, horizontal, 0.5, 0.0)
        grid = cv2.threshold(grid, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        # Tìm contours để suy ra các ô
        contours, _ = cv2.findContours(grid, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        # Lọc bbox lớn nhỏ, gom theo hàng/cột bằng heuristic
        boxes = []
        h, w = grid.shape
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            if cw * ch < (h * w) * 0.0005:
                continue
            if cw < 20 or ch < 15:
                continue
            boxes.append((x, y, cw, ch))
        if not boxes:
            logger.info(f"Trang {i}: Không phát hiện bảng bằng OpenCV")
            continue

        # Sắp xếp theo Y trước để tiện xử lý
        boxes.sort(key=lambda b: (b[1], b[0]))
        heights = [ch for (_, _, _, ch) in boxes]
        widths = [cw for (_, _, cw, _) in boxes]
        med_h = int(np.median(heights)) if heights else 20
        med_w = int(np.median(widths)) if widths else 40
        # Tham số từ config
        ocr_tables_cfg = (ocr_cfg.get("tables") or {}).get("ocr", {})
        row_merge_factor = float(ocr_tables_cfg.get("row_merge_factor", 0.5))
        col_merge_factor = float(ocr_tables_cfg.get("col_merge_factor", 0.6))
        min_cell_area_ratio = float(ocr_tables_cfg.get("min_cell_area_ratio", 0.0005))
        # Lọc box nhỏ theo tỉ lệ trang
        page_area = h * w
        boxes = [(x, y, cw, ch) for (x, y, cw, ch) in boxes if (cw * ch) >= page_area * min_cell_area_ratio]
        # Ngưỡng gom hàng/cột
        y_threshold = max(8, int(med_h * row_merge_factor))

        # Ổn định cột: lấy từ hàng đại diện có nhiều ô nhất để cố định số cột
        # Nếu không có rows_list (vì gom theo boxes), dùng toàn bộ boxes
        sorted_by_row = []
        temp_row = []
        last_y_center = None
        for box in boxes:
            y_center = box[1] + box[3] // 2
            if last_y_center is None or abs(y_center - last_y_center) <= y_threshold:
                temp_row.append(box)
            else:
                sorted_by_row.append(temp_row)
                temp_row = [box]
            last_y_center = y_center
        if temp_row:
            sorted_by_row.append(temp_row)

        # Phát hiện cột: sử dụng hàng đại diện để có số cột chính xác
        representative = max(sorted_by_row, key=lambda r: len(r)) if sorted_by_row else []
        if representative:
            rep_centers = sorted([x + cw // 2 for (x, _, cw, _) in representative])
            col_bins = []
            x_thresh = max(12, int(med_w * col_merge_factor))
            for xc in rep_centers:
                if not col_bins or abs(xc - col_bins[-1]) > x_thresh:
                    col_bins.append(xc)
        else:
            # Fallback: dùng toàn bộ boxes
            x_centers = sorted([x + cw // 2 for (x, _, cw, _) in boxes])
            if not x_centers:
                logger.info(f"Trang {i}: Không có cột hợp lệ sau phát hiện")
                continue
            col_bins = []
            x_thresh = max(12, int(med_w * col_merge_factor))
            for xc in x_centers:
                if not col_bins or abs(xc - col_bins[-1]) > x_thresh:
                    col_bins.append(xc)
        num_cols = len(col_bins)

        # Tạo row bins dựa trên center Y của boxes (trước khi merge)
        row_centers = sorted([y + ch // 2 for (_, y, _, ch) in boxes])
        row_bins = []
        for yc in row_centers:
            if not row_bins or abs(yc - row_bins[-1]) > y_threshold:
                row_bins.append(yc)
        num_rows = len(row_bins)
        if num_rows == 0 or num_cols == 0:
            logger.info(f"Trang {i}: Không tạo được lưới hàng/cột")
            continue

        # OCR từng ô để lấy nội dung text
        try:
            import pytesseract
            tesseract_cmd = ocr_cfg.get("tesseract_cmd")
            if tesseract_cmd:
                config.pytesseract.config.pytesseract.tesseract_cmd = tesseract_cmd
            lang = ocr_cfg.get("lang", "vie")
            lang_normalized = _normalize_lang_code(lang)
            psm = ocr_cfg.get("psm", 6)
            # Tham số cải thiện cho bảng kém chất lượng
            ocr_tables_cfg = (ocr_cfg.get("tables") or {}).get("ocr", {})
            upscale_factor = int(ocr_tables_cfg.get("upscale_factor", 2))  # Phóng to ảnh để OCR tốt hơn
            use_clahe = bool(ocr_tables_cfg.get("use_clahe", True))        # Tăng tương phản cục bộ
            primary_psm = int(ocr_tables_cfg.get("primary_psm", psm))      # PSM chính (mặc định lấy từ ocr.psm)
            fallback_psm = int(ocr_tables_cfg.get("fallback_psm", 7))      # PSM fallback (single line)
            try_numeric_whitelist = bool(ocr_tables_cfg.get("try_numeric_whitelist", True))
        except Exception as e:
            logger.warning(f"⚠️  Không thể import pytesseract: {e}")
            pytesseract = None

        # Bước quan trọng: Nhóm các box có overlap hoặc gần nhau thành một ô
        # Điều này xử lý trường hợp text trong một ô bị ngắt dòng và được detect thành nhiều box
        def _boxes_overlap_or_near(box1, box2, overlap_threshold=0.4, near_threshold=2.0):
            """Kiểm tra hai box có overlap hoặc gần nhau không (thuộc cùng một ô)
            
            Chỉ merge khi:
            - Overlap đáng kể (>40%) theo cả hai chiều X và Y (chắc chắn cùng ô)
            - HOẶC cùng cột (dist_x rất nhỏ <30%) và khoảng cách Y nhỏ (<2.0x chiều cao trung bình)
            - HOẶC overlap X đáng kể (>40%) và khoảng cách Y nhỏ (text nhiều dòng trong cùng ô)
            """
            x1, y1, w1, h1 = box1
            x2, y2, w2, h2 = box2
            
            # Tính overlap theo chiều X và Y
            x_overlap = max(0, min(x1 + w1, x2 + w2) - max(x1, x2))
            y_overlap = max(0, min(y1 + h1, y2 + h2) - max(y1, y2))
            
            # Overlap ratio theo từng chiều
            overlap_x_ratio = x_overlap / min(w1, w2) if min(w1, w2) > 0 else 0
            overlap_y_ratio = y_overlap / min(h1, h2) if min(h1, h2) > 0 else 0
            
            # Nếu overlap đáng kể theo CẢ HAI chiều → chắc chắn cùng một ô
            if overlap_x_ratio >= overlap_threshold and overlap_y_ratio >= overlap_threshold:
                return True
            
            # Kiểm tra khoảng cách gần nhau (cho trường hợp text nhiều dòng trong cùng một ô)
            # Tính khoảng cách giữa các tâm
            center1_x, center1_y = x1 + w1 / 2, y1 + h1 / 2
            center2_x, center2_y = x2 + w2 / 2, y2 + h2 / 2
            
            # Khoảng cách tuyệt đối
            dist_x_abs = abs(center1_x - center2_x)
            dist_y_abs = abs(center1_y - center2_y)
            
            # Khoảng cách chuẩn hóa theo kích thước box
            avg_w = (w1 + w2) / 2
            avg_h = (h1 + h2) / 2
            
            dist_x_ratio = dist_x_abs / avg_w if avg_w > 0 else float('inf')
            dist_y_ratio = dist_y_abs / avg_h if avg_h > 0 else float('inf')
            
            # Trường hợp 1: Cùng cột (dist_x rất nhỏ) và khoảng cách Y hợp lý (text nhiều dòng trong cùng ô)
            # Chỉ merge nếu khoảng cách Y không quá lớn (<1.5x chiều cao trung bình)
            if (dist_x_ratio < 0.25 and dist_y_ratio < 1.5 and 
                overlap_x_ratio > 0.15):  # Có ít nhất 15% overlap X
                return True
            
            # Trường hợp 2: Overlap X đáng kể (>40%) và khoảng cách Y nhỏ (<1.5x) - text nhiều dòng trong cùng ô
            if overlap_x_ratio >= overlap_threshold and dist_y_ratio < 1.5:
                return True
            
            return False
        
        # Nhóm các box thành các cell groups
        cell_groups = []
        used_boxes = set()
        
        for i, box in enumerate(boxes):
            if i in used_boxes:
                continue
            
            # Tạo nhóm mới với box này
            group = [box]
            used_boxes.add(i)
            
            # Tìm tất cả các box khác có overlap hoặc gần với box này
            changed = True
            while changed:
                changed = False
                for j, other_box in enumerate(boxes):
                    if j in used_boxes:
                        continue
                    
                    # Kiểm tra overlap với bất kỳ box nào trong nhóm
                    for group_box in group:
                        if _boxes_overlap_or_near(group_box, other_box):
                            group.append(other_box)
                            used_boxes.add(j)
                            changed = True
                            break
            
            cell_groups.append(group)
        
        # Tính bounding box tổng hợp cho mỗi nhóm (để gán vào row/col chính xác hơn)
        # CẢI TIẾN: Filter các merged cells quá lớn (có thể span nhiều cột/hàng)
        merged_cells = []
        avg_cell_width = np.median([b[2] for b in boxes]) if boxes else med_w
        avg_cell_height = np.median([b[3] for b in boxes]) if boxes else med_h
        
        for group in cell_groups:
            if not group:
                continue
            
            # Tính bounding box bao phủ toàn bộ nhóm
            min_x = min(b[0] for b in group)
            min_y = min(b[1] for b in group)
            max_x = max(b[0] + b[2] for b in group)
            max_y = max(b[1] + b[3] for b in group)
            merged_box = (min_x, min_y, max_x - min_x, max_y - min_y)
            mw, mh = max_x - min_x, max_y - min_y
            
            # CẢI TIẾN: Filter các merged cells quá lớn
            # Nếu merged cell có width > 3x avg_cell_width hoặc height > 3x avg_cell_height
            # → có thể là nhiều cells bị merge nhầm → skip hoặc split
            if mw > avg_cell_width * 3.5 or mh > avg_cell_height * 3.5:
                # Cell quá lớn → có thể là header/footer hoặc nhiều cells bị merge nhầm
                # Chỉ giữ lại nếu có ít parts (có thể là cell thực sự lớn)
                if len(group) <= 2:
                    # Có thể là cell lớn hợp lệ (ví dụ: header)
                    merged_cells.append({
                        "merged_box": merged_box,
                        "parts": group
                    })
                else:
                    # Quá nhiều parts → có thể là merge nhầm → skip
                    logger.debug(f"Skipping merged cell quá lớn: {mw}x{mh} với {len(group)} parts")
                    continue
            else:
                merged_cells.append({
                    "merged_box": merged_box,
                    "parts": group  # Các box gốc trong nhóm
                })
        
        # Tạo bảng với nội dung OCR và metadata tọa độ dựa trên row/column bins
        table_cells = [
            [
                {"text": "", "cell_text_parts": []}
                for _ in range(num_cols)
            ]
            for _ in range(num_rows)
        ]

        # CẢI TIẾN: Tracking các cells đã được gán để tránh duplicate
        # Sử dụng set để track (row_idx, col_idx) đã được sử dụng bởi merged_cell nào
        cell_assignment_map = {}  # {(row_idx, col_idx): merged_cell_index}
        
        # Xử lý từng merged cell
        for merged_cell_idx, merged_cell in enumerate(merged_cells):
            merged_box = merged_cell["merged_box"]
            parts = merged_cell["parts"]
            
            x, y, cw, ch = merged_box
            
            # WORKFLOW MỚI: OCR trên toàn bộ merged box (ô đã ghép) thay vì từng phần riêng lẻ
            # Điều này đảm bảo context đầy đủ và spell check chính xác hơn
            cell_img = gray[max(0, y):min(gray.shape[0], y + ch), max(0, x):min(gray.shape[1], x + cw)]
            if cell_img.size == 0:
                continue

            combined_text = ""
            cell_text_parts_list = []
            
            if pytesseract is not None:
                try:
                    # OCR trên toàn bộ merged cell (ô đã ghép)
                    work = cell_img.copy()
                    if use_clahe:
                        try:
                            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                            work = clahe.apply(work)
                        except Exception:
                            pass
                    try:
                        work = cv2.medianBlur(work, 3)
                    except Exception:
                        pass
                    try:
                        _, work_bin = cv2.threshold(work, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        work = work_bin
                    except Exception:
                        pass
                    if upscale_factor and upscale_factor > 1:
                        try:
                            work = cv2.resize(work, None, fx=upscale_factor, fy=upscale_factor, interpolation=cv2.INTER_CUBIC)
                        except Exception:
                            pass
                    padding = 6
                    padded = cv2.copyMakeBorder(work, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=255)
                    
                    # Dùng PSM phù hợp với ô nhiều dòng
                    cfg_primary = f'--oem 1 --psm {primary_psm}'
                    text1 = config.pytesseract.image_to_string(padded, lang=lang_normalized, config=cfg_primary).strip()

                    def _clean_multiline(t: str) -> str:
                        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
                        return "\n".join(lines)

                    best_text = _clean_multiline(text1)

                    def _is_poor(t: str) -> bool:
                        if not t:
                            return True
                        alnum = sum(ch.isalnum() for ch in t)
                        return len(t) < 3 or alnum < max(1, len(t) // 3)

                    if _is_poor(best_text):
                        cfg_fb = f'--oem 1 --psm {fallback_psm}'
                        text2 = config.pytesseract.image_to_string(padded, lang=lang_normalized, config=cfg_fb).strip()
                        text2 = _clean_multiline(text2)
                        if len(text2) > len(best_text):
                            best_text = text2
                    if try_numeric_whitelist and _is_poor(best_text):
                        cfg_num = f'--oem 1 --psm {fallback_psm} -c tessedit_char_whitelist=0123456789.,-/%()'
                        text3 = config.pytesseract.image_to_string(padded, lang=lang_normalized, config=cfg_num).strip()
                        text3 = _clean_multiline(text3)
                        if len(text3) > len(best_text):
                            best_text = text3
                    
                    combined_text = best_text
                    
                    # CẢI TIẾN: Validation text quality trước khi lưu
                    # Filter các text quá ngắn hoặc có quá nhiều ký tự đặc biệt (có thể là noise)
                    def _is_valid_cell_text(text: str) -> bool:
                        """Kiểm tra text có hợp lệ không"""
                        if not text or len(text.strip()) < 2:
                            return False
                        
                        text_clean = text.strip()
                        
                        # Đếm số ký tự alphanumeric và tiếng Việt
                        vietnamese_chars = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ'
                        alnum_count = sum(1 for c in text_clean if c.isalnum() or c in vietnamese_chars)
                        
                        # Đếm các ký tự đặc biệt lạ (noise từ OCR)
                        noise_chars = '°‹Ÿ¬`^«£ÀÊSẼẴaAaPẨ€+—_*•…"\''
                        noise_count = sum(1 for c in text_clean if c in noise_chars)
                        
                        # Đếm các ký tự hợp lệ (chữ cái, số, dấu câu thông thường, khoảng trắng)
                        valid_chars = '.,;:!?()[]{}-/\\'
                        valid_count = alnum_count + sum(1 for c in text_clean if c in valid_chars or c.isspace())
                        
                        # Nếu có quá nhiều ký tự noise (>25% text) → có thể là noise
                        if len(text_clean) > 0 and noise_count / len(text_clean) > 0.25:
                            return False
                        
                        # Nếu có quá ít ký tự hợp lệ (<25% text) → có thể là noise
                        if len(text_clean) > 0 and valid_count / len(text_clean) < 0.25:
                            return False
                        
                        # Nếu có quá ít ký tự alphanumeric (<15% text) → có thể là noise
                        if len(text_clean) > 0 and alnum_count / len(text_clean) < 0.15:
                            return False
                        
                        # Kiểm tra nếu text chỉ chứa các ký tự đặc biệt và số ít chữ cái
                        # Ví dụ: "|||'‹ ° Cu|toi PÓ Tô Ÿ CC ST 4ì||"
                        if len(text_clean) > 10 and alnum_count < len(text_clean) * 0.2:
                            # Nếu có nhiều ký tự đặc biệt và ít chữ cái → noise
                            return False
                        
                        return True
                    
                    # Chỉ lưu nếu text hợp lệ
                    if _is_valid_cell_text(combined_text):
                        cell_text_parts_list.append({
                            "text": combined_text,
                            "x": int(x),
                            "y": int(y),
                            "w": int(cw),
                            "h": int(ch)
                        })
                    else:
                        # Text không hợp lệ → skip cell này
                        logger.debug(f"Skipping merged_cell {merged_cell_idx}: Text không hợp lệ (quá ngắn hoặc noise): '{combined_text[:50]}'")
                        continue
                except Exception as ocr_err:
                    logger.debug(f"OCR merged cell ({x},{y}) thất bại: {ocr_err}")
                    combined_text = ""
            
            # CẢI TIẾN: Nếu không có text hợp lệ từ OCR, skip cell này
            if not cell_text_parts_list:
                logger.debug(f"Skipping merged_cell {merged_cell_idx}: Không có text hợp lệ từ OCR")
                continue
            
            # Lấy combined_text từ cell_text_parts_list
            combined_text = " ".join([part["text"] for part in cell_text_parts_list])
            
            # Xác định row/col theo bins dựa trên merged box
            # CẢI TIẾN: Sử dụng cả x_center và phạm vi của cell để gán cột chính xác hơn
            x_center = x + cw // 2
            y_center = y + ch // 2
            x_left = x
            x_right = x + cw
            y_top = y
            y_bottom = y + ch
            
            # CẢI TIẾN: Tính overlap với từng cột để tìm cột có overlap lớn nhất
            # Thay vì chỉ tìm col_bin trong phạm vi, tính overlap thực tế
            col_scores = []
            for k in range(num_cols):
                col_bin_x = col_bins[k]
                # Tính overlap giữa cell và cột (giả định cột có width = khoảng cách đến cột kế tiếp)
                if k < num_cols - 1:
                    col_width = col_bins[k + 1] - col_bin_x
                else:
                    # Cột cuối: dùng khoảng cách từ cột trước
                    col_width = col_bin_x - col_bins[k - 1] if k > 0 else cw
                
                col_left = col_bin_x - col_width // 2
                col_right = col_bin_x + col_width // 2
                
                # Tính overlap
                overlap_left = max(x_left, col_left)
                overlap_right = min(x_right, col_right)
                overlap_width = max(0, overlap_right - overlap_left)
                overlap_ratio = overlap_width / max(cw, col_width) if max(cw, col_width) > 0 else 0
                
                # CẢI TIẾN: Penalty nếu cell quá rộng so với cột (có thể span nhiều cột)
                width_ratio = cw / col_width if col_width > 0 else 1.0
                if width_ratio > 2.5:
                    # Cell quá rộng so với cột → có thể span nhiều cột → giảm điểm số
                    overlap_ratio *= 0.5
                
                # Điểm số = overlap_ratio - distance_penalty
                distance = abs(x_center - col_bin_x)
                distance_penalty = distance / (cw + col_width) if (cw + col_width) > 0 else 0
                score = overlap_ratio - distance_penalty * 0.3
                
                col_scores.append((score, k))
            
            # Chọn cột có điểm số cao nhất
            col_scores.sort(reverse=True)
            best_score = col_scores[0][0] if col_scores else -1
            
            # CẢI TIẾN: Nếu điểm số quá thấp (<0.2), có thể cell này không phù hợp với bất kỳ cột nào
            # → có thể là noise hoặc cell quá lớn → skip
            if best_score < 0.2:
                logger.debug(f"Skipping merged_cell {merged_cell_idx}: Điểm số cột quá thấp ({best_score:.2f}), có thể là noise")
                continue
            
            col_idx = col_scores[0][1] if col_scores else 0
            
            # Tương tự cho row: tính overlap với từng hàng
            row_scores = []
            for k in range(num_rows):
                row_bin_y = row_bins[k]
                # Tính overlap giữa cell và hàng
                if k < num_rows - 1:
                    row_height = row_bins[k + 1] - row_bin_y
                else:
                    row_height = row_bin_y - row_bins[k - 1] if k > 0 else ch
                
                row_top = row_bin_y - row_height // 2
                row_bottom = row_bin_y + row_height // 2
                
                # Tính overlap
                overlap_top = max(y_top, row_top)
                overlap_bottom = min(y_bottom, row_bottom)
                overlap_height = max(0, overlap_bottom - overlap_top)
                overlap_ratio = overlap_height / max(ch, row_height) if max(ch, row_height) > 0 else 0
                
                # CẢI TIẾN: Penalty nếu cell quá cao so với hàng (có thể span nhiều hàng)
                height_ratio = ch / row_height if row_height > 0 else 1.0
                if height_ratio > 2.5:
                    # Cell quá cao so với hàng → có thể span nhiều hàng → giảm điểm số
                    overlap_ratio *= 0.5
                
                # Điểm số = overlap_ratio - distance_penalty
                distance = abs(y_center - row_bin_y)
                distance_penalty = distance / (ch + row_height) if (ch + row_height) > 0 else 0
                score = overlap_ratio - distance_penalty * 0.3
                
                row_scores.append((score, k))
            
            # Chọn hàng có điểm số cao nhất
            row_scores.sort(reverse=True)
            best_row_score = row_scores[0][0] if row_scores else -1
            
            # CẢI TIẾN: Nếu điểm số quá thấp (<0.2), có thể cell này không phù hợp với bất kỳ hàng nào
            # → có thể là noise hoặc cell quá lớn → skip
            if best_row_score < 0.2:
                logger.debug(f"Skipping merged_cell {merged_cell_idx}: Điểm số hàng quá thấp ({best_row_score:.2f}), có thể là noise")
                continue
            
            row_idx = row_scores[0][1] if row_scores else 0

            # QUAN TRỌNG: Kiểm tra conflict và xử lý
            # CẢI TIẾN: Kiểm tra xem vị trí này đã được gán cho merged_cell khác chưa
            conflict_key = (row_idx, col_idx)
            has_conflict = conflict_key in cell_assignment_map
            if has_conflict:
                # Vị trí này đã được gán → kiểm tra xem có phải cùng một cell không
                existing_cell_idx = cell_assignment_map[conflict_key]
                existing_cell = merged_cells[existing_cell_idx]
                existing_box = existing_cell["merged_box"]
                ex, ey, ecw, ech = existing_box
                existing_x_center = ex + ecw // 2
                existing_y_center = ey + ech // 2
                
                # Tính overlap giữa hai cells
                overlap_x = max(0, min(x_right, ex + ecw) - max(x_left, ex))
                overlap_y = max(0, min(y_bottom, ey + ech) - max(y_top, ey))
                overlap_area = overlap_x * overlap_y
                current_area = cw * ch
                existing_area = ecw * ech
                overlap_ratio = overlap_area / min(current_area, existing_area) if min(current_area, existing_area) > 0 else 0
                
                # Nếu overlap > 50% → có thể là cùng một cell → merge
                # Nếu không → tìm vị trí khác
                if overlap_ratio < 0.5:
                    # Đây là cell khác → tìm vị trí trống phù hợp
                    # Ưu tiên 1: Tìm cột trống trong cùng hàng có overlap tốt nhất
                    best_empty_col = None
                    best_col_score = -1
                    for c_idx in range(num_cols):
                        if not table_cells[row_idx][c_idx]["text"] and (row_idx, c_idx) not in cell_assignment_map:
                            col_bin_x = col_bins[c_idx]
                            # Tính overlap với cột này
                            if x_left <= col_bin_x <= x_right:
                                # Có overlap → điểm số cao
                                score = 1.0
                            else:
                                # Không overlap → điểm số thấp hơn (dựa trên khoảng cách)
                                dist = abs(x_center - col_bin_x)
                                score = max(0, 1.0 - dist / (cw * 2))
                            
                            if score > best_col_score:
                                best_col_score = score
                                best_empty_col = c_idx
                    
                    # Ưu tiên 2: Nếu không có cột trống tốt trong cùng hàng, tìm hàng trống trong cùng cột
                    if best_empty_col is None or best_col_score < 0.3:
                        best_empty_row = None
                        best_row_score = -1
                        for r_idx in range(num_rows):
                            if not table_cells[r_idx][col_idx]["text"] and (r_idx, col_idx) not in cell_assignment_map:
                                row_bin_y = row_bins[r_idx]
                                # Tính overlap với hàng này
                                if y_top <= row_bin_y <= y_bottom:
                                    score = 1.0
                                else:
                                    dist = abs(y_center - row_bin_y)
                                    score = max(0, 1.0 - dist / (ch * 2))
                                
                                if score > best_row_score:
                                    best_row_score = score
                                    best_empty_row = r_idx
                        
                        if best_empty_row is not None and best_row_score >= 0.3:
                            row_idx = best_empty_row
                        elif best_empty_col is not None:
                            col_idx = best_empty_col
                        else:
                            # Không tìm được vị trí tốt → skip cell này
                            logger.debug(f"Skipping merged_cell {merged_cell_idx}: Không tìm được vị trí trống phù hợp")
                            continue
                    else:
                        col_idx = best_empty_col
            
            # Đảm bảo row_idx và col_idx hợp lệ
            if row_idx < 0 or row_idx >= num_rows:
                logger.debug(f"Row index {row_idx} out of range [0, {num_rows}), skipping cell")
                continue
            if col_idx < 0 or col_idx >= num_cols:
                logger.debug(f"Col index {col_idx} out of range [0, {num_cols}), skipping cell")
                continue
            
            entry = table_cells[row_idx][col_idx]
            
            # CẢI TIẾN: Kiểm tra xem vị trí này đã có cell khác chưa
            # Nếu có và không phải cùng cell → đã được xử lý ở trên (tìm vị trí trống)
            # Nếu có và là cùng cell → merge text
            if combined_text:
                combined_text_normalized = " ".join(combined_text.split())
                
                if entry["text"]:
                    # Kiểm tra xem đây có phải là cùng một cell không
                    existing_x_center = None
                    existing_y_center = None
                    existing_x_left = None
                    existing_x_right = None
                    existing_y_top = None
                    existing_y_bottom = None
                    
                    if entry["cell_text_parts"]:
                        for part in entry["cell_text_parts"]:
                            if "x" in part and "w" in part:
                                px = part["x"]
                                pw = part["w"]
                                if existing_x_left is None or px < existing_x_left:
                                    existing_x_left = px
                                if existing_x_right is None or px + pw > existing_x_right:
                                    existing_x_right = px + pw
                                existing_x_center = px + pw // 2
                            if "y" in part and "h" in part:
                                py = part["y"]
                                ph = part["h"]
                                if existing_y_top is None or py < existing_y_top:
                                    existing_y_top = py
                                if existing_y_bottom is None or py + ph > existing_y_bottom:
                                    existing_y_bottom = py + ph
                                existing_y_center = py + ph // 2
                    
                    # Tính overlap để xác định có phải cùng cell không
                    if existing_x_left is not None and existing_x_right is not None and existing_y_top is not None and existing_y_bottom is not None:
                        # Tính overlap
                        overlap_x = max(0, min(x_right, existing_x_right) - max(x_left, existing_x_left))
                        overlap_y = max(0, min(y_bottom, existing_y_bottom) - max(y_top, existing_y_top))
                        overlap_area = overlap_x * overlap_y
                        current_area = cw * ch
                        existing_area = (existing_x_right - existing_x_left) * (existing_y_bottom - existing_y_top)
                        overlap_ratio = overlap_area / min(current_area, existing_area) if min(current_area, existing_area) > 0 else 0
                        
                        # Nếu overlap > 50% → cùng một cell → merge text
                        if overlap_ratio >= 0.5:
                            entry["text"] = entry["text"] + " " + combined_text_normalized
                            entry["cell_text_parts"].extend(cell_text_parts_list)
                        else:
                            # Khác cell → không nên xảy ra vì đã xử lý ở trên, nhưng log để debug
                            logger.debug(f"Conflict: Cell at ({x_center}, {y_center}) conflicts with existing, overlap={overlap_ratio:.2f}")
                            # Giữ cell có text dài hơn hoặc diện tích lớn hơn
                            existing_area_sum = sum(part.get("w", 0) * part.get("h", 0) for part in entry["cell_text_parts"])
                            if len(combined_text_normalized) > len(entry["text"]) * 1.2 or current_area > existing_area_sum * 1.2:
                                entry["text"] = combined_text_normalized
                                entry["cell_text_parts"] = cell_text_parts_list
                    else:
                        # Không có metadata cũ → thay thế
                        entry["text"] = combined_text_normalized
                        entry["cell_text_parts"] = cell_text_parts_list
                else:
                    # Ô trống → gán trực tiếp
                    entry["text"] = combined_text_normalized
                    entry["cell_text_parts"] = cell_text_parts_list
            else:
                # Không có text nhưng vẫn lưu metadata (để đánh dấu vị trí cell)
                if not entry["cell_text_parts"]:
                    entry["cell_text_parts"] = cell_text_parts_list
            
            # Đánh dấu vị trí này đã được sử dụng (sau khi đã gán thành công)
            cell_assignment_map[(row_idx, col_idx)] = merged_cell_idx

        # Chỉ giữ lại những hàng có nội dung
        # QUAN TRỌNG: Giữ nguyên vị trí cột để tránh tịnh tiến dữ liệu khi có ô trống
        # CẢI TIẾN: Filter các hàng có quá nhiều ô trống ở đầu (có thể là noise)
        table_data = []
        metadata_cells = []
        row_index_map = {}
        for original_row_idx, row_entries in enumerate(table_cells):
            # Giữ nguyên vị trí cột: row_values[col_idx] = entry[col_idx]["text"]
            # Điều này đảm bảo ô trống ở giữa không làm dịch chuyển các ô bên phải
            row_values = []
            for col_idx in range(num_cols):
                if col_idx < len(row_entries):
                    cell_text = row_entries[col_idx]["text"]
                    # CẢI TIẾN: Cleanup text trước khi thêm vào
                    if cell_text:
                        # Loại bỏ các ký tự đặc biệt lạ ở đầu/cuối
                        cell_text = cell_text.strip()
                        
                        # Đếm các ký tự hợp lệ và invalid
                        vietnamese_chars = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ'
                        noise_chars = '°‹Ÿ¬`^«£ÀÊSẼẴaAaPẨ€+—_*•…"\''
                        invalid_chars = noise_chars + '~…®©œƒŠšŸŒŽžÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ'
                        
                        alnum_count = sum(1 for c in cell_text if c.isalnum() or c in vietnamese_chars)
                        invalid_count = sum(1 for c in cell_text if c in invalid_chars)
                        
                        # Nếu text chỉ chứa ký tự đặc biệt lạ → coi như trống
                        if len(cell_text) > 0:
                            alnum_ratio = alnum_count / len(cell_text)
                            invalid_ratio = invalid_count / len(cell_text)
                            
                            # Quá ít ký tự hợp lệ (<15%) → coi như trống
                            if alnum_ratio < 0.15:
                                cell_text = ""
                            # Hoặc có quá nhiều ký tự invalid (>20%) và ít alphanumeric (<30%)
                            elif invalid_ratio > 0.2 and alnum_ratio < 0.3:
                                cell_text = ""
                            # Hoặc với cell ngắn (<15 ký tự), nếu có nhiều invalid (>15%) → coi như trống
                            elif len(cell_text) < 15 and invalid_ratio > 0.15:
                                cell_text = ""
                    row_values.append(cell_text)
                else:
                    # Nếu thiếu cột → thêm ô trống (không làm dịch chuyển)
                    row_values.append("")
            
            # CẢI TIẾN: Filter các hàng có quá nhiều ô trống ở đầu (>= 50% số cột)
            # và chỉ có ít nội dung → có thể là noise
            non_empty_count = sum(1 for val in row_values if val and val.strip())
            empty_prefix_count = sum(1 for val in row_values[:num_cols//2] if not val or not val.strip())
            
            # Nếu có >= 50% cột đầu trống và chỉ có <= 1 ô có nội dung → có thể là noise
            if empty_prefix_count >= num_cols * 0.5 and non_empty_count <= 1:
                logger.debug(f"Skipping row {original_row_idx}: Quá nhiều ô trống ở đầu ({empty_prefix_count}/{num_cols//2}), chỉ có {non_empty_count} ô có nội dung")
                continue
            
            # CẢI TIẾN: Filter các hàng có quá nhiều ký tự đặc biệt lạ (noise từ OCR)
            # Kiểm tra tổng hợp toàn bộ hàng
            row_text = " ".join(row_values)
            vietnamese_chars = 'àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđĐ'
            noise_chars = '°‹Ÿ¬`^«£ÀÊSẼẴaAaPẨ€+—_*•…"\''
            # Mở rộng danh sách noise chars để bao gồm các ký tự không hợp lệ khác
            invalid_chars = noise_chars + '~…®©œƒŠšŸŒŽžÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ'
            
            alnum_count = sum(1 for c in row_text if c.isalnum() or c in vietnamese_chars)
            noise_count = sum(1 for c in row_text if c in noise_chars)
            invalid_count = sum(1 for c in row_text if c in invalid_chars)
            
            # Đếm các ký tự hợp lệ (alphanumeric + dấu câu thông thường + khoảng trắng)
            valid_punctuation = '.,;:!?()[]{}-/\\'
            valid_count = alnum_count + sum(1 for c in row_text if c in valid_punctuation or c.isspace())
            
            # CẢI TIẾN: Áp dụng filter cho cả hàng ngắn (>= 5 ký tự)
            if len(row_text) >= 5:
                noise_ratio = noise_count / len(row_text) if len(row_text) > 0 else 0
                alnum_ratio = alnum_count / len(row_text) if len(row_text) > 0 else 0
                invalid_ratio = invalid_count / len(row_text) if len(row_text) > 0 else 0
                valid_ratio = valid_count / len(row_text) if len(row_text) > 0 else 0
                
                # CẢI TIẾN: Filter các hàng ngắn có nhiều ký tự đặc biệt
                if len(row_text) < 30:
                    # Với hàng ngắn, threshold thấp hơn vì dễ bị nhiễu
                    # Filter 1: Invalid ratio cao (>15%)
                    if invalid_ratio > 0.15:
                        logger.debug(f"Skipping row {original_row_idx}: Hàng ngắn có nhiều ký tự invalid ({invalid_ratio:.2%})")
                        continue
                    # Filter 2: Noise ratio cao (>10%) và alphanumeric thấp (<50%)
                    if noise_ratio > 0.1 and alnum_ratio < 0.5:
                        logger.debug(f"Skipping row {original_row_idx}: Hàng ngắn có nhiều noise ({noise_ratio:.2%}), alphanumeric thấp ({alnum_ratio:.2%})")
                        continue
                    # Filter 3: Noise ratio cao (>8%) và alphanumeric thấp (<60%)
                    if noise_ratio > 0.08 and alnum_ratio < 0.6:
                        logger.debug(f"Skipping row {original_row_idx}: Hàng ngắn có nhiều noise ({noise_ratio:.2%}), alphanumeric thấp ({alnum_ratio:.2%})")
                        continue
                    # Filter 4: Invalid ratio cao (>12%) và valid ratio thấp (<80%)
                    if invalid_ratio > 0.12 and valid_ratio < 0.8:
                        logger.debug(f"Skipping row {original_row_idx}: Hàng ngắn có nhiều invalid ({invalid_ratio:.2%}), valid thấp ({valid_ratio:.2%})")
                        continue
                
                # CẢI TIẾN: Filter mạnh hơn - nếu có nhiều ký tự invalid (>20%) và ít valid (<60%)
                if invalid_ratio > 0.2 and valid_ratio < 0.6:
                    logger.debug(f"Skipping row {original_row_idx}: Quá nhiều ký tự invalid ({invalid_ratio:.2%}), ít valid ({valid_ratio:.2%})")
                    continue
                
                if noise_ratio > 0.3 and alnum_ratio < 0.2:
                    logger.debug(f"Skipping row {original_row_idx}: Quá nhiều ký tự noise ({noise_ratio:.2%}), ít alphanumeric ({alnum_ratio:.2%})")
                    continue
                
                # Nếu hàng có quá ít alphanumeric (<15%) và có nhiều ký tự đặc biệt
                if alnum_ratio < 0.15 and noise_count > 5:
                    logger.debug(f"Skipping row {original_row_idx}: Quá ít alphanumeric ({alnum_ratio:.2%}), nhiều ký tự đặc biệt ({noise_count})")
                    continue
                
                # CẢI TIẾN: Nếu có nhiều ký tự đặc biệt (>15%) và tỷ lệ valid thấp (<50%)
                # Điều này sẽ catch các hàng như "|||'‹ ° Cu|toi PÓ Tô Ÿ CC ST 4ì||"
                if invalid_ratio > 0.15 and valid_ratio < 0.5:
                    logger.debug(f"Skipping row {original_row_idx}: Nhiều ký tự invalid ({invalid_ratio:.2%}), tỷ lệ valid thấp ({valid_ratio:.2%})")
                    continue
                
                # CẢI TIẾN: Nếu có nhiều ký tự invalid (>18%) và có nhiều ký tự đặc biệt không hợp lệ
                # Ngay cả khi tỷ lệ valid cao, nếu có quá nhiều ký tự đặc biệt thì vẫn là noise
                if invalid_ratio > 0.18 and invalid_count > 10:
                    logger.debug(f"Skipping row {original_row_idx}: Nhiều ký tự invalid ({invalid_ratio:.2%}, {invalid_count} ký tự)")
                    continue
                
                # CẢI TIẾN: Nếu có nhiều ký tự noise (>12%) và tỷ lệ alphanumeric không cao (<40%)
                # Điều này sẽ catch các hàng có nhiều ký tự đặc biệt nhưng vẫn có một số chữ cái
                if noise_ratio > 0.12 and alnum_ratio < 0.4 and len(row_text) > 20:
                    logger.debug(f"Skipping row {original_row_idx}: Nhiều ký tự noise ({noise_ratio:.2%}), alphanumeric thấp ({alnum_ratio:.2%})")
                    continue
                
                # CẢI TIẾN: Filter các hàng có quá nhiều ký tự đặc biệt không hợp lệ ngay cả khi tỷ lệ alphanumeric cao
                # Ví dụ: "||||toi PÓ Tô Ÿ CC ST 4ì||" có alnum_ratio cao nhưng có nhiều ký tự đặc biệt
                if invalid_count > 5 and invalid_ratio > 0.12:
                    # Nếu có nhiều ký tự invalid và tỷ lệ valid không đủ cao (<70%)
                    if valid_ratio < 0.7:
                        logger.debug(f"Skipping row {original_row_idx}: Nhiều ký tự invalid ({invalid_count}, {invalid_ratio:.2%}), valid ratio thấp ({valid_ratio:.2%})")
                        continue
                
                # CẢI TIẾN: Filter các hàng có noise ratio cao (>15%) ngay cả khi alphanumeric ratio trung bình
                # Ví dụ: "|T:€=+ X2 «—t P1 ' 7E 0 tư ƯỜNG|||||" có noise_ratio 20%
                if noise_ratio > 0.15 and alnum_ratio < 0.55:
                    logger.debug(f"Skipping row {original_row_idx}: Noise ratio cao ({noise_ratio:.2%}), alphanumeric thấp ({alnum_ratio:.2%})")
                    continue
                
                # CẢI TIẾN: Filter các hàng có invalid ratio cao (>18%) ngay cả khi valid ratio cao
                # Điều này catch các hàng có nhiều ký tự đặc biệt không hợp lệ
                if invalid_ratio > 0.18:
                    logger.debug(f"Skipping row {original_row_idx}: Invalid ratio quá cao ({invalid_ratio:.2%})")
                    continue
            
            # Chỉ thêm hàng nếu có ít nhất một ô có nội dung hợp lệ
            if any(val.strip() for val in row_values):
                new_row_idx = len(table_data)
                row_index_map[original_row_idx] = new_row_idx
                table_data.append(row_values)
                # Lưu metadata cho các ô có nội dung
                for col_idx, entry in enumerate(row_entries):
                    if col_idx < len(row_values) and entry.get("cell_text_parts"):
                        metadata_cells.append({
                            "row": new_row_idx,
                            "col": col_idx,
                            "cell_text_parts": entry["cell_text_parts"]
                        })

        # Lưu table_data vào kết quả (không xuất CSV trung gian)
        if table_data:
            # Đảm bảo tất cả các hàng có cùng số cột (pad với chuỗi rỗng nếu thiếu)
            max_cols = max(len(row) for row in table_data) if table_data else num_cols
            if max_cols == 0:
                max_cols = num_cols  # Fallback về num_cols từ grid detection
            
            # Chuẩn hóa dữ liệu bảng
            normalized_table = []
            for row in table_data:
                normalized_row = []
                for col_idx in range(max_cols):
                    if col_idx < len(row):
                        cell = row[col_idx]
                        if cell:
                            # Ghép paragraph trong ô thành một paragraph
                            normalized_cell = " ".join(cell.split())
                            normalized_row.append(normalized_cell)
                        else:
                            normalized_row.append("")
                    else:
                        # Pad với chuỗi rỗng nếu thiếu cột
                        normalized_row.append("")
                normalized_table.append(normalized_row)
            
            tables_by_page[i] = {
                "page": i,
                "rows": normalized_table,
                "num_cols": max_cols,
                "metadata": metadata_cells
            }
            exported += 1
            logger.info(f"🗂️  Đã extract bảng (OpenCV+OCR) trang {i}: {len(normalized_table)} hàng, {max_cols} cột")
        else:
            logger.info(f"Trang {i}: Phát hiện bảng nhưng không có nội dung text sau OCR")

    if exported == 0:
        logger.info("ℹ️  OpenCV fallback không tìm thấy bảng nào")
        return {}
    else:
        logger.info(f"✅ OpenCV fallback: Đã extract {exported} bảng từ {len(tables_by_page)} trang")
        return tables_by_page

