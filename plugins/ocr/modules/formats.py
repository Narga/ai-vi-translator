from . import config
from .pdf import extract_text_blocks_with_position

def extract_format_hints(para, para_index: int, total_paragraphs: int) -> dict:
    """
    Extract format hints chi tiết từ paragraph.
    
    Args:
        para: python-docx Paragraph object
        para_index: Index của paragraph trong document
        total_paragraphs: Tổng số paragraphs
    
    Returns:
        dict: {
            "style": str,
            "font_size": float,
            "is_bold": bool,
            "is_italic": bool,
            "alignment": str,
            "position_hint": str  # "top", "middle", "bottom"
        }
    """
    hints = {
        "style": para.style.name if para.style else "Normal",
        "font_size": None,
        "is_bold": False,
        "is_italic": False,
        "alignment": "left",
        "position_hint": "middle"
    }
    
    # Get alignment
    if para.alignment is not None and WD_PARAGRAPH_ALIGNMENT is not None:
        if para.alignment == config.WD_PARAGRAPH_ALIGNMENT.LEFT:
            hints["alignment"] = "left"
        elif para.alignment == config.WD_PARAGRAPH_ALIGNMENT.CENTER:
            hints["alignment"] = "center"
        elif para.alignment == config.WD_PARAGRAPH_ALIGNMENT.RIGHT:
            hints["alignment"] = "right"
        elif para.alignment == config.WD_PARAGRAPH_ALIGNMENT.JUSTIFY:
            hints["alignment"] = "justify"
    
    # Get font info từ runs
    if para.runs:
        # Use first run (hoặc most common format)
        first_run = para.runs[0]
        
        if first_run.font.size:
            hints["font_size"] = first_run.font.size.pt
        
        hints["is_bold"] = first_run.font.bold is True
        hints["is_italic"] = first_run.font.italic is True
    
    # Estimate position: first 20% = top, last 20% = bottom, else = middle
    if total_paragraphs > 0:
        position_ratio = para_index / total_paragraphs
        if position_ratio < 0.2:
            hints["position_hint"] = "top"
        elif position_ratio > 0.8:
            hints["position_hint"] = "bottom"
        else:
            hints["position_hint"] = "middle"
    
    return hints

def is_in_table(para) -> bool:
    """Check nếu paragraph nằm trong table."""
    try:
        parent = para._element.getparent()
        if parent is not None:
            # Check nếu parent là table element
            return parent.tag.endswith('tbl')
    except Exception:
        pass
    return False

def extract_images_from_paragraph(para) -> List[dict]:
    """
    Extract images từ paragraph.
    
    Returns:
        List[dict]: [
            {
                "run_index": int,
                "image_data": bytes,
                "width": float,  # inches (estimate)
                "height": float,  # inches (estimate)
                "run": Run  # Reference để re-insert sau
            },
            ...
        ]
    """
    images = []
    
    try:
        for run_idx, run in enumerate(para.runs):
            # Check nếu run có image (check for blip element)
            blips = run._element.xpath('.//a:blip')
            if blips:
                try:
                    # Get image relationship ID
                    blip = blips[0]
                    rId = blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                    
                    if rId and hasattr(para.part, 'rels') and rId in para.part.rels:
                        # Get image blob từ relationship
                        image_part_rel = para.part.rels[rId]
                        image_blob = image_part_rel.target_part.blob
                        
                        # Estimate image dimensions từ run
                        width_inches = 4.0  # Default
                        height_inches = 3.0  # Default
                        
                        # Try to get actual dimensions từ image
                        try:
                            if Image is not None:
                                import io
                                img = config.Image.open(io.BytesIO(image_blob))
                                width_inches = img.width / 96.0  # Convert pixels to inches (96 DPI)
                                height_inches = img.height / 96.0
                                img.close()
                        except Exception:
                            pass
                        
                        images.append({
                            "run_index": run_idx,
                            "image_data": image_blob,
                            "width": width_inches,
                            "height": height_inches,
                            "run": run
                        })
                except Exception as e:
                    logger.debug(f"Không thể extract image từ run {run_idx}: {e}")
                    continue
    except Exception as e:
        logger.debug(f"Lỗi khi extract images từ paragraph: {e}")
    
    return images

def extract_paragraphs_with_hints(docx_path: str) -> List[dict]:
    """
    Extract paragraphs từ DOCX với format hints chi tiết và images.
    Skip tables.
    
    Returns:
        List[dict]: [
            {
                "index": int,
                "text": str,
                "hints": dict,
                "images": List[dict],
                "has_images": bool,
                "para_object": Paragraph
            },
            ...
        ]
    """
    if Document is None:
        raise RuntimeError("python-docx chưa được cài đặt.")
    
    doc = config.Document(docx_path)
    paragraphs_data = []
    
    # Get all paragraphs (not in tables)
    all_paragraphs = [para for para in doc.paragraphs if not is_in_table(para)]
    total_paragraphs = len(all_paragraphs)
    
    for para_idx, para in enumerate(all_paragraphs):
        # Extract format hints
        hints = extract_format_hints(para, para_idx, total_paragraphs)
        
        # Extract images
        images = extract_images_from_paragraph(para)
        
        paragraphs_data.append({
            "index": len(paragraphs_data),
            "text": para.text,
            "hints": hints,
            "images": images,
            "has_images": len(images) > 0,
            "para_object": para
        })
    
    logger.info(f"📝 Đã extract {len(paragraphs_data)} paragraphs từ DOCX (đã skip tables)")
    return paragraphs_data

def batch_small_paragraphs(paragraphs_data: List[dict], min_chars: int = 50) -> List[dict]:
    """
    Batch các paragraphs nhỏ lại với nhau để tối ưu API calls.
    
    Args:
        paragraphs_data: List các paragraph dicts
        min_chars: Ngưỡng để xem là paragraph nhỏ (default: 50)
    
    Returns:
        List[dict]: Batched paragraphs với type "batch" hoặc "single"
    """
    batched = []
    current_batch = []
    
    for para in paragraphs_data:
        # Batch nếu paragraph nhỏ và không có images
        if len(para["text"]) < min_chars and not para.get("has_images", False):
            current_batch.append(para)
        else:
            # Paragraph lớn hoặc có images → process riêng
            if current_batch:
                # Merge batch
                batched.append({
                    "type": "batch",
                    "text": "\n\n".join([p["text"] for p in current_batch]),
                    "original_indices": [p["index"] for p in current_batch],
                    "para_objects": [p["para_object"] for p in current_batch],
                    "images_list": [p["images"] for p in current_batch],
                    "hints": current_batch[0]["hints"]
                })
                current_batch = []
            
            batched.append({
                "type": "single",
                **para
            })
    
    # Handle remaining batch
    if current_batch:
        batched.append({
            "type": "batch",
            "text": "\n\n".join([p["text"] for p in current_batch]),
            "original_indices": [p["index"] for p in current_batch],
            "para_objects": [p["para_object"] for p in current_batch],
            "images_list": [p["images"] for p in current_batch],
            "hints": current_batch[0]["hints"]
        })
    
    if batched:
        batch_count = sum(1 for b in batched if b["type"] == "batch")
        single_count = sum(1 for b in batched if b["type"] == "single")
        logger.info(f"📦 Đã batch: {batch_count} batches, {single_count} single paragraphs")
    
    return batched

def split_batched_result(batched_text: str, original_count: int) -> List[str]:
    """
    Split batched result về số paragraphs ban đầu (estimate).
    
    Args:
        batched_text: Text đã được process (có thể có nhiều paragraphs)
        original_count: Số paragraphs ban đầu
    
    Returns:
        List[str]: List các paragraphs (có thể không đúng số lượng)
    """
    # Simple: Split by double newlines
    paragraphs = batched_text.split('\n\n')
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    # Nếu số paragraphs không match → distribute đều hoặc keep như cũ
    if len(paragraphs) != original_count:
        # Estimate: Nếu có ít hơn, có thể AI đã merge
        # Nếu có nhiều hơn, có thể AI đã split
        # Tạm thời return như cũ
        pass
    
    return paragraphs

def convert_pdf_to_docx(pdf_path: str, output_path: str, pages: Optional[List[int]] = None) -> str:
    """
    Convert PDF → DOCX trực tiếp bằng pdf2docx.
    
    Args:
        pdf_path: Đường dẫn file PDF input
        output_path: Đường dẫn file DOCX output
        pages: Danh sách số trang cần convert (1-indexed). None = tất cả trang.
    
    Returns:
        str: Đường dẫn file DOCX đã tạo
    
    Raises:
        RuntimeError: Nếu pdf2docx chưa được cài đặt
    """
    if Converter is None:
        raise RuntimeError("pdf2docx chưa được cài đặt. Cài pdf2docx để dùng convert PDF → DOCX.")
    
    logger.info(f"📄 Đang convert PDF → DOCX: {pdf_path}")
    
    try:
        cv = Converter(pdf_path)
        
        # pdf2docx hỗ trợ pages thông qua start_page và end_page
        # Nếu có pages chỉ định, convert chỉ những trang đó
        if pages:
            valid_pages = sorted(set(pages))
            logger.info(f"Chỉ convert {len(valid_pages)} trang: {valid_pages}")
            
            # Convert từ start đến end của pages
            start_page = min(valid_pages)
            end_page = max(valid_pages)
            cv.convert(output_path, start=start_page, end=end_page)
        else:
            cv.convert(output_path)
        
        cv.close()
        
        # Validate output file
        if not os.path.exists(output_path):
            raise RuntimeError(f"Conversion thất bại: File output không tồn tại: {output_path}")
        
        file_size = os.path.getsize(output_path)
        if file_size < 100:  # DOCX tối thiểu phải > 100 bytes
            raise RuntimeError(f"Conversion thất bại: File output quá nhỏ ({file_size} bytes)")
        
        logger.info(f"✅ Đã convert PDF → DOCX: {output_path} ({file_size} bytes)")
        return output_path
        
    except AttributeError as attr_error:
        # Lỗi do version không tương thích (ví dụ: 'Rect' object has no attribute 'get_area')
        error_msg = str(attr_error)
        logger.error(f"❌ Lỗi version không tương thích: {error_msg}")
        logger.warning("💡 Lỗi do pdf2docx và PyMuPDF không tương thích.")
        logger.warning("💡 Giải pháp: pip install PyMuPDF==1.26.4")
        raise RuntimeError(f"Lỗi version không tương thích (pdf2docx/PyMuPDF): {error_msg}")
    except Exception as e:
        logger.error(f"❌ Lỗi khi convert PDF → DOCX: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        raise

def update_paragraph_in_place(para, new_text: str):
    """
    Update paragraph text nhưng giữ nguyên formatting từ original runs.
    
    Args:
        para: python-docx Paragraph object
        new_text: Text mới để replace
    """
    if not para.runs:
        # No runs → add new text với default formatting
        para.add_run(new_text)
        return
    
    # Strategy: Giữ formatting từ first run (hoặc most common)
    first_run = para.runs[0]
    
    # Save formatting
    font_format = {
        "bold": first_run.font.bold,
        "italic": first_run.font.italic,
        "size": first_run.font.size,
        "name": first_run.font.name
    }
    
    # Clear paragraph
    para.clear()
    
    # Add new text với formatting
    run = para.add_run(new_text)
    
    # Apply formatting
    if font_format["bold"]:
        run.font.bold = True
    if font_format["italic"]:
        run.font.italic = True
    if font_format["size"]:
        run.font.size = font_format["size"]
    if font_format["name"]:
        run.font.name = font_format["name"]

def re_insert_images_to_paragraph(para, images: List[dict]):
    """
    Re-insert images vào paragraph sau khi process text.
    
    Args:
        para: python-docx Paragraph object
        images: List of image dicts từ extract_images_from_paragraph()
    """
    import io
    
    if not images:
        return
    
    for img_info in images:
        try:
            image_bytes = img_info.get("image_data")
            if not image_bytes or len(image_bytes) < 10:
                continue
            
            width_inches = img_info.get("width", 4.0)
            height_inches = img_info.get("height", 3.0)
            
            # Add image vào paragraph
            run = para.add_run()
            img_stream = io.BytesIO(image_bytes)
            img_stream.seek(0)
            
            try:
                if width_inches > 0.1 and height_inches > 0.1:
                    # Use width (maintain aspect ratio)
                    max_width = 6.0  # Max 6 inches
                    run.add_picture(img_stream, width=config.Inches(min(width_inches, max_width)))
                else:
                    run.add_picture(img_stream, width=config.Inches(4.0))
            except Exception as pic_error:
                logger.warning(f"Không thể re-insert image vào paragraph: {pic_error}")
                continue
                
        except Exception as e:
            logger.warning(f"Lỗi khi re-insert image: {e}")
            continue

def update_docx_with_processed_text(docx_path: str, processed_paragraphs: List[dict], ocr_cfg: dict) -> str:
    """
    Update DOCX với processed text, giữ nguyên formatting và images.
    
    Args:
        docx_path: Đường dẫn file DOCX input/output (sẽ được update in-place)
        processed_paragraphs: List các processed paragraph dicts
        ocr_cfg: Config dictionary
    
    Returns:
        str: Đường dẫn file DOCX đã update
    """
    if Document is None:
        raise RuntimeError("python-docx chưa được cài đặt.")
    
    logger.info(f"🔄 Đang update DOCX với processed text: {docx_path}")
    
    doc = config.Document(docx_path)
    
    # Process từng paragraph/batch
    para_idx = 0
    
    for processed in processed_paragraphs:
        if processed["type"] == "batch":
            # Batch: Split result và update từng paragraph
            cleaned_text = processed.get("cleaned_text", processed["text"])
            spell_checked_text = processed.get("spell_checked_text", cleaned_text)
            
            # Split batched result
            para_objects = processed["para_objects"]
            images_list = processed.get("images_list", [])
            
            split_paragraphs = split_batched_result(spell_checked_text, len(para_objects))
            
            # Update từng paragraph trong batch
            for i, para_obj in enumerate(para_objects):
                if i < len(split_paragraphs):
                    para_text = split_paragraphs[i]
                else:
                    # Not enough split → use remaining text hoặc empty
                    para_text = "" if i > 0 else spell_checked_text
                
                # Update paragraph
                if para_text.strip():
                    update_paragraph_in_place(para_obj, para_text)
                    
                    # Re-insert images từ paragraph này
                    if i < len(images_list):
                        re_insert_images_to_paragraph(para_obj, images_list[i])
                else:
                    # Empty paragraph → clear
                    para_obj.clear()
            
        else:
            # Single paragraph
            para_obj = processed["para_object"]
            cleaned_text = processed.get("cleaned_text", processed["text"])
            spell_checked_text = processed.get("spell_checked_text", cleaned_text)
            images = processed.get("images", [])
            
            # Update text
            if spell_checked_text.strip():
                update_paragraph_in_place(para_obj, spell_checked_text)
                
                # Re-insert images
                re_insert_images_to_paragraph(para_obj, images)
            else:
                # Empty → clear
                para_obj.clear()
        
        # Handle merge
        if processed.get("should_merge_with_next") and para_idx + 1 < len(processed_paragraphs):
            # Merge với paragraph sau: update current với merged text, clear next
            next_processed = processed_paragraphs[para_idx + 1]
            merged_text = spell_checked_text + " " + next_processed.get("spell_checked_text", next_processed["text"])
            
            # Update current paragraph với merged text
            if processed["type"] == "single":
                update_paragraph_in_place(processed["para_object"], merged_text)
            elif processed["type"] == "batch" and processed["para_objects"]:
                # Update last paragraph trong batch
                update_paragraph_in_place(processed["para_objects"][-1], merged_text)
            
            # Clear next paragraph
            if next_processed["type"] == "single":
                next_processed["para_object"].clear()
            elif next_processed["type"] == "batch" and next_processed["para_objects"]:
                # Clear first paragraph trong batch
                next_processed["para_objects"][0].clear()
        
        para_idx += 1
    
    # Save updated DOCX
    try:
        doc.save(docx_path)
        logger.info(f"✅ Đã update DOCX: {docx_path}")
        return docx_path
    except Exception as e:
        logger.error(f"❌ Không thể save updated DOCX: {e}")
        raise

def convert_docx_to_epub(docx_path: str, epub_path: str, ocr_cfg: dict) -> str:
    """
    Convert DOCX → EPUB using pypandoc.
    
    Args:
        docx_path: Đường dẫn file DOCX input
        epub_path: Đường dẫn file EPUB output
        ocr_cfg: Config dictionary
    
    Returns:
        str: Đường dẫn file EPUB đã tạo
    
    Raises:
        RuntimeError: Nếu pypandoc chưa được cài đặt hoặc conversion fail
    """
    try:
        import pypandoc
    except ImportError:
        raise RuntimeError("pypandoc chưa được cài đặt. Cài pypandoc để convert DOCX → EPUB.")
    
    logger.info(f"📚 Đang convert DOCX → EPUB: {docx_path}")
    
    try:
        pypandoc.convert_file(
            docx_path,
            'epub',
            outputfile=epub_path,
            extra_args=['--standalone']
        )
        
        # Validate output
        if not os.path.exists(epub_path):
            raise RuntimeError(f"Conversion thất bại: File EPUB không tồn tại: {epub_path}")
        
        file_size = os.path.getsize(epub_path)
        if file_size < 1000:  # EPUB tối thiểu > 1KB
            raise RuntimeError(f"Conversion thất bại: File EPUB quá nhỏ ({file_size} bytes)")
        
        logger.info(f"✅ Đã convert DOCX → EPUB: {epub_path} ({file_size} bytes)")
        return epub_path
        
    except Exception as e:
        logger.error(f"❌ Lỗi khi convert DOCX → EPUB: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        raise

def extract_text_and_images_from_pdf(pdf_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> tuple[List[dict], int]:
    """
    Extract text và images từ PDF có text layer.
    
    Args:
        pdf_path: Đường dẫn file PDF
        ocr_cfg: Config dictionary
        pages: Danh sách số trang cần extract (1-indexed). None = tất cả trang.
    
    Returns:
        tuple: (pages_data, total_pages) trong đó pages_data là list of dict với keys:
            - page_num: số trang (1-indexed)
            - text: text content
            - images: list of image data (bytes) với position info
    """
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) chưa được cài đặt. Cài PyMuPDF để hỗ trợ extract images.")
    
    pages_data: List[dict] = []
    
    try:
        doc = config.fitz.open(pdf_path)
        total = len(doc)
        logger.info(f"Extract text và images: Tổng số trang: {total}")
        
        # Filter pages nếu có chỉ định
        if pages:
            valid_pages = [p for p in pages if 1 <= p <= total]
            invalid_pages = [p for p in pages if p < 1 or p > total]
            if invalid_pages:
                logger.warning(f"Các trang không hợp lệ (nằm ngoài 1-{total}): {invalid_pages}. Bỏ qua.")
            if not valid_pages:
                logger.error("Không có trang hợp lệ nào để extract.")
                return [], 0
            logger.info(f"Extract text và images: Chỉ extract {len(valid_pages)} trang: {valid_pages}")
            pages_to_extract = sorted(set(valid_pages))
        else:
            pages_to_extract = list(range(1, total + 1))
        
        show_progress = bool(ocr_cfg.get("show_progress", True))
        
        if show_progress and tqdm is not None and len(pages_to_extract) > 1:
            iterator = config.tqdm(pages_to_extract, desc="Extract text & images", unit="trang")
        else:
            iterator = pages_to_extract
        
        for page_num in iterator:
            page = doc[page_num - 1]  # fitz dùng 0-indexed
            
            # Extract text
            text = page.get_text().strip()
            
            # Extract images với position
            images = []
            image_list = page.get_images(full=True)
            page_rect = page.rect  # Page dimensions
            
            for img_idx, img in enumerate(image_list):
                try:
                    # img là tuple: (xref, smask, width, height, bpc, colorspace, alt. colorspace, name, filter, referencer)
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image_ext = base_image["ext"]
                    
                    # Extract image position từ PDF
                    # PyMuPDF không trực tiếp cho image position, nhưng ta có thể estimate từ image rect
                    # Hoặc dùng image_list với position nếu có
                    y_position = 0  # Default, sẽ được cập nhật nếu có thông tin
                    x_position = 0
                    
                    # Thử extract image rect từ page (nếu có)
                    try:
                        # Get image rectangles từ page
                        image_rects = page.get_image_rects(xref)
                        if image_rects:
                            # Lấy rect đầu tiên (thường chỉ có 1)
                            rect = image_rects[0]
                            y_position = rect.y0  # Top Y position
                            x_position = rect.x0  # Left X position
                    except Exception:
                        # Estimate position: images thường ở giữa hoặc theo thứ tự
                        y_position = page_rect.height * 0.3 + (img_idx * page_rect.height * 0.2)
                        x_position = page_rect.width * 0.5  # Center
                    
                    images.append({
                        "data": image_bytes,
                        "ext": image_ext,
                        "xref": xref,
                        "width": img[2],
                        "height": img[3],
                        "y_position": y_position,
                        "x_position": x_position
                    })
                except Exception as e:
                    logger.debug(f"Không thể extract image {img_idx} từ trang {page_num}: {e}")
                    continue
            
            pages_data.append({
                "page_num": page_num,
                "text": text,
                "images": images
            })
            
            if not show_progress and len(pages_data) % 50 == 0:
                logger.info(f"Extract text và images: {len(pages_data)}/{len(pages_to_extract)} trang")
        
        doc.close()
        return pages_data, total
        
    except Exception as e:
        logger.error(f"PyMuPDF failed: {e}")
        raise

def create_docx_from_processed_text(pdf_path: str, output_path: str, processed_text: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> str:
    """
    Tạo file DOCX từ text đã được xử lý (cleanup/spell check) và images từ PDF.
    
    Args:
        pdf_path: Đường dẫn file PDF input (để extract images)
        output_path: Đường dẫn file DOCX output
        processed_text: Text đã được cleanup và spell check
        ocr_cfg: Config dictionary
        pages: Danh sách số trang cần extract (1-indexed). None = tất cả trang.
    
    Returns:
        str: Đường dẫn file DOCX đã tạo
    """
    if Document is None:
        raise RuntimeError("python-docx chưa được cài đặt. Cài python-docx để tạo DOCX output.")
    
    logger.info(f"📄 Tạo DOCX từ text đã xử lý và images: {pdf_path}")
    
    # Extract images từ PDF (không cần text vì đã có processed_text)
    pages_data, total_pages = extract_text_and_images_from_pdf(pdf_path, ocr_cfg, pages)
    
    if not pages_data:
        raise ValueError("Không có dữ liệu nào được extract từ PDF.")
    
    # Tạo images_dict từ pages_data và collect all_images
    images_dict = {}
    all_images = []
    for page_info in pages_data:
        page_num = page_info["page_num"]
        images_dict[page_num] = page_info.get("images", [])
        all_images.extend([(page_num, img_info) for img_info in page_info["images"]])
    
    # Kiểm tra xem có sử dụng HTML intermediate workflow không
    use_html_workflow = ocr_cfg.get("use_html_intermediate_workflow", True)  # Default: True
    
    # Nếu có images và use_html_workflow, thử dùng HTML workflow để đảm bảo vị trí chính xác
    if use_html_workflow and all_images and len(all_images) > 0:
        logger.info("📄 Sử dụng HTML intermediate workflow để đảm bảo vị trí text và images chính xác...")
        
        # Extract text blocks với Y-position từ PDF gốc để có position chính xác
        logger.info("🔍 Đang extract text blocks với position từ PDF...")
        text_blocks_by_page, _ = extract_text_blocks_with_position(pdf_path, ocr_cfg, pages)
        
        # Tạo all_items_with_position: kết hợp text paragraphs và images với position chính xác
        all_items_with_position = []
        
        # Chia processed_text thành paragraphs (giữ thứ tự)
        text_paragraphs = processed_text.split('\n\n')
        text_paragraphs = [p.strip() for p in text_paragraphs if p.strip()]
        
        # Map processed paragraphs với original text blocks dựa trên similarity
        # Strategy: Match processed paragraphs với original text blocks bằng fuzzy matching
        processed_para_idx = 0
        
        for page_info in pages_data:
            page_num = page_info["page_num"]
            original_blocks = text_blocks_by_page.get(page_num, [])
            
            # Nếu có original blocks với position, map processed paragraphs với chúng
            if original_blocks:
                # Match processed paragraphs với original blocks
                # Simple strategy: giả định thứ tự paragraphs được giữ nguyên sau cleanup/spell check
                # Có thể cải thiện bằng fuzzy matching nếu cần
                
                # Estimate số paragraphs per block
                if len(original_blocks) > 0:
                    # Chia processed paragraphs đều cho các blocks
                    paras_per_block = max(1, len(text_paragraphs) // max(1, sum(len(text_blocks_by_page.get(p, [])) for p in pages_data if pages_data)))
                else:
                    paras_per_block = len(text_paragraphs)
                
                block_idx = 0
                for original_block in original_blocks:
                    # Tìm processed paragraph tương ứng (simple sequential matching)
                    if processed_para_idx < len(text_paragraphs):
                        # Có thể cải thiện bằng fuzzy matching
                        para_text = text_paragraphs[processed_para_idx]
                        processed_para_idx += 1
                        
                        all_items_with_position.append({
                            "type": "text",
                            "content": para_text,
                            "page_num": page_num,
                            "y_position": original_block.get("y_position", 0),
                            "x_position": original_block.get("x_position", 0)
                        })
                    
                    # Thêm images nằm sau block này (nếu có)
                    # Images với Y-position < block Y-position đã được xử lý
                    block_y = original_block.get("y_position", 0)
                    
                    # Tìm images của trang này có Y-position gần block này
                    for img_info in page_info.get("images", []):
                        img_y = img_info.get("y_position", 0)
                        img_x = img_info.get("x_position", 0)
                        
                        # Nếu image có Y-position trong khoảng hợp lý với block này, thêm vào
                        # (Images thường nằm giữa các text blocks)
                        # Chỉ thêm nếu chưa được thêm (check bằng xref)
                        if "xref" in img_info:
                            # Check xem image này đã được thêm chưa
                            already_added = any(
                                item.get("type") == "image" and 
                                item.get("img_info", {}).get("xref") == img_info["xref"]
                                for item in all_items_with_position
                            )
                            
                            if not already_added:
                                # Estimate: nếu image Y gần block Y, thêm ngay sau block
                                if abs(img_y - block_y) < 200:  # 200px threshold
                                    all_items_with_position.append({
                                        "type": "image",
                                        "img_info": img_info,
                                        "page_num": page_num,
                                        "y_position": img_y,
                                        "x_position": img_x
                                    })
            else:
                # Không có original blocks với position → dùng estimate cũ
                # Chia processed paragraphs đều cho các trang
                paragraphs_per_page = max(1, len(text_paragraphs) // len(pages_data)) if pages_data else len(text_paragraphs)
                start_idx = (page_num - (pages_data[0]["page_num"] if pages_data else 1)) * paragraphs_per_page
                end_idx = min(start_idx + paragraphs_per_page, len(text_paragraphs))
                
                for para_text in text_paragraphs[start_idx:end_idx]:
                    all_items_with_position.append({
                        "type": "text",
                        "content": para_text,
                        "page_num": page_num,
                        "y_position": 100 * (page_num - (pages_data[0]["page_num"] if pages_data else 1)) * 50,  # Estimate
                        "x_position": 0
                    })
            
            # Thêm các images còn lại của trang này (chưa được thêm)
            for img_info in page_info.get("images", []):
                if "xref" in img_info:
                    already_added = any(
                        item.get("type") == "image" and 
                        item.get("img_info", {}).get("xref") == img_info["xref"]
                        for item in all_items_with_position
                    )
                    
                    if not already_added:
                        y_position = img_info.get("y_position", 500 * page_num)
                        x_position = img_info.get("x_position", 0)
                        
                        all_items_with_position.append({
                            "type": "image",
                            "img_info": img_info,
                            "page_num": page_num,
                            "y_position": y_position,
                            "x_position": x_position
                        })
        
        # Sort theo (y_position, x_position) để đảm bảo thứ tự đúng
        all_items_with_position.sort(key=lambda x: (x.get("page_num", 0) * 10000 + x.get("y_position", 0), x.get("x_position", 0)))
        
        logger.info(f"📊 Đã thu thập {len([i for i in all_items_with_position if i['type'] == 'text'])} text blocks và {len([i for i in all_items_with_position if i['type'] == 'image'])} images với position")
        
        # Thử tạo DOCX qua HTML workflow
        try:
            html_path = _create_html_from_items(all_items_with_position, output_path)
            success = _convert_html_to_docx_with_pandoc(html_path, output_path, ocr_cfg)
            
            if success:
                logger.info(f"✅ Đã tạo DOCX qua HTML intermediate workflow: {output_path}")
                # Cleanup HTML temp file
                try:
                    if os.path.exists(html_path):
                        os.remove(html_path)
                        logger.debug(f"Đã xóa file HTML temp: {html_path}")
                except Exception:
                    pass
                return output_path
            else:
                logger.warning("⚠️ HTML → DOCX conversion thất bại, fallback về python-docx trực tiếp...")
        except Exception as html_error:
            logger.warning(f"⚠️ HTML intermediate workflow thất bại: {html_error}")
            logger.warning("⚠️ Fallback về python-docx trực tiếp...")
            import traceback
            logger.debug(traceback.format_exc())
    
    # Fallback: Dùng python-docx trực tiếp (workflow cũ)
    # Tạo DOCX document
    try:
        doc = config.Document()
    except Exception as e:
        raise RuntimeError(f"Không thể tạo Document object: {e}")
    
    # Set document properties (optional)
    try:
        doc.core_properties.title = os.path.splitext(os.path.basename(pdf_path))[0]
    except Exception:
        pass
    import io
    show_progress = bool(ocr_cfg.get("show_progress", True))
    
    # Bước 1: Chèn tất cả images từ tất cả các trang (giữ nguyên thứ tự)
    images_added_count = 0
    if all_images:
        logger.info(f"🖼️  Đang chèn {len(all_images)} images vào DOCX...")
        for page_num, img_info in (config.tqdm(all_images, desc="Chèn images", unit="ảnh") if (show_progress and tqdm and len(all_images) > 1) else all_images):
            try:
                image_bytes = img_info.get("data")
                if not image_bytes or len(image_bytes) == 0:
                    logger.warning(f"Image data rỗng từ trang {page_num}, bỏ qua")
                    continue
                
                if len(image_bytes) < 10:
                    logger.warning(f"Image từ trang {page_num} quá nhỏ ({len(image_bytes)} bytes), bỏ qua")
                    continue
                
                image_ext = img_info.get("ext", "png")
                
                # Validate image data - kiểm tra magic bytes
                is_valid = False
                magic_msg = ""
                if image_ext.lower() in ("jpeg", "jpg"):
                    if len(image_bytes) >= 2 and image_bytes[:2] == b'\xff\xd8':
                        is_valid = True
                    else:
                        magic_msg = f"Magic bytes: {image_bytes[:2].hex() if len(image_bytes) >= 2 else 'too short'} (expected: ffd8)"
                elif image_ext.lower() == "png":
                    if len(image_bytes) >= 8 and image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                        is_valid = True
                    else:
                        magic_msg = f"Magic bytes: {image_bytes[:8].hex() if len(image_bytes) >= 8 else 'too short'} (expected: 89504e47...)"
                elif image_ext.lower() in ("gif", "bmp", "tiff", "webp"):
                    is_valid = True
                else:
                    # Format khác, chấp nhận nhưng log warning
                    logger.debug(f"Image từ trang {page_num} có format không chuẩn: {image_ext}")
                    is_valid = True
                
                if not is_valid:
                    logger.warning(f"Image từ trang {page_num} không phải {image_ext.upper()} hợp lệ. {magic_msg}")
                    continue
                
                # Log thông tin image trước khi thử add
                logger.debug(f"Thử thêm image từ trang {page_num}: ext={image_ext}, size={len(image_bytes)} bytes, width={img_width}, height={img_height}")
                
                # Kiểm tra magic bytes của image data
                if len(image_bytes) >= 2:
                    first_bytes = image_bytes[:8] if len(image_bytes) >= 8 else image_bytes[:2]
                    logger.debug(f"Image magic bytes: {first_bytes.hex()}")
                
                # Thử load image với PIL để validate trước khi add vào DOCX
                try:
                    from PIL import Image as PILImage
                    pil_img = PILconfig.Image.open(io.BytesIO(image_bytes))
                    pil_img.verify()  # Verify image integrity
                    pil_img.close()
                    logger.debug(f"✅ Image từ trang {page_num} đã được validate bằng PIL")
                except Exception as pil_error:
                    logger.warning(f"⚠️  Image từ trang {page_num} không thể validate bằng PIL: {pil_error}")
                    # Vẫn thử add vào DOCX vì có thể PIL không hỗ trợ format này nhưng python-docx có thể
                
                # Tạo image từ bytes
                img_stream = io.BytesIO(image_bytes)
                img_stream.seek(0)
                
                # Validate stream có data (đã check ở trên nhưng double-check)
                if len(image_bytes) == 0:
                    logger.warning(f"Image bytes rỗng từ trang {page_num}")
                    continue
                
                # Thêm image vào document
                para = doc.add_paragraph()
                run = para.add_run()
                
                # Tính toán kích thước image (giữ tỷ lệ)
                img_width = img_info.get("width", 0)
                img_height = img_info.get("height", 0)
                
                try:
                    if img_width > 0 and img_height > 0:
                        max_width_inches = 6.0
                        aspect_ratio = img_height / img_width
                        
                        if img_width > 500:
                            width_inches = min(max_width_inches, img_width / 96.0)
                            height_inches = width_inches * aspect_ratio
                        else:
                            width_inches = img_width / 96.0
                            height_inches = img_height / 96.0
                        
                        if width_inches > 0.1 and height_inches > 0.1:
                            run.add_picture(img_stream, width=config.Inches(min(width_inches, max_width_inches)))
                            images_added_count += 1
                        else:
                            run.add_picture(img_stream, width=config.Inches(4.0))
                            images_added_count += 1
                    else:
                        run.add_picture(img_stream, width=config.Inches(4.0))
                        images_added_count += 1
                    
                    para_format = para.paragraph_format
                    para_format.space_after = config.Pt(6)
                except Exception as pic_error:
                    import traceback
                    error_details = traceback.format_exc()
                    error_msg = str(pic_error)
                    logger.warning(f"❌ Không thể add picture vào DOCX từ trang {page_num}: {error_msg}")
                    logger.warning(f"   Image info: ext={image_ext}, size={len(image_bytes)} bytes, width={img_width}, height={img_height}")
                    # Log full traceback ở debug level
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Chi tiết lỗi add_picture:\n{error_details}")
                    continue
                
            except Exception as e:
                logger.warning(f"Không thể thêm image vào DOCX từ trang {page_num}: {e}")
                continue
    
    if all_images and images_added_count == 0:
        logger.warning(f"Không có image nào được thêm vào DOCX (tổng {len(all_images)} images)")
    
    # Bước 2: Chèn text đã được xử lý (processed_text)
    text_added = False
    if processed_text and processed_text.strip():
        logger.info("📝 Đang chèn text đã được xử lý vào DOCX...")
        paragraphs = processed_text.split('\n\n')
        
        for para_text in paragraphs:
            para_text = para_text.strip()
            if para_text:
                para = doc.add_paragraph(para_text)
                para_format = para.paragraph_format
                para_format.space_after = config.Pt(6)
                text_added = True
    
    # Đảm bảo document có nội dung
    has_content = text_added or images_added_count > 0
    
    if not has_content:
        logger.warning("Document không có nội dung. Thêm paragraph mặc định...")
        try:
            doc.add_paragraph("(Không có nội dung từ PDF)")
        except Exception:
            pass
    
    # Save DOCX
    try:
        doc.save(output_path)
        logger.info(f"✅ Đã tạo DOCX: {output_path}")
        logger.info(f"   📊 Thống kê: {images_added_count} images, {len(processed_text.split())} từ")
        return output_path
    except Exception as e:
        logger.error(f"❌ Không thể lưu DOCX: {e}")
        raise

def create_docx_from_pdf(pdf_path: str, output_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None, apply_cleanup: bool = True, apply_spell_check: bool = True) -> str:
    from .ai_processor import ai_cleanup_text, ai_spell_check_and_paragraph_restore
    """
    Tạo file DOCX từ PDF có text layer, giữ lại cả text và images.
    Có thể áp dụng cleanup và spell check cho text trước khi tạo DOCX.
    
    LƯU Ý: Hàm này được giữ lại để backward compatibility, nhưng workflow mới nên dùng:
    - extract_text_and_images_from_pdf() để extract
    - ocr_file() để xử lý text
    - create_docx_from_processed_text() để tạo DOCX
    
    Args:
        pdf_path: Đường dẫn file PDF input
        output_path: Đường dẫn file DOCX output
        ocr_cfg: Config dictionary
        pages: Danh sách số trang cần extract (1-indexed). None = tất cả trang.
        apply_cleanup: Có áp dụng AI cleanup cho text không (mặc định: True)
        apply_spell_check: Có áp dụng AI spell check cho text không (mặc định: True)
    
    Returns:
        str: Đường dẫn file DOCX đã tạo
    """
    if Document is None:
        raise RuntimeError("python-docx chưa được cài đặt. Cài python-docx để tạo DOCX output.")
    
    logger.info(f"Tạo DOCX từ PDF: {pdf_path}")
    
    # Extract text và images
    pages_data, total_pages = extract_text_and_images_from_pdf(pdf_path, ocr_cfg, pages)
    
    if not pages_data:
        raise ValueError("Không có dữ liệu nào được extract từ PDF.")
    
    # Extract images với thông tin vị trí Y để chèn đúng vị trí
    # Sử dụng images từ pages_data (đã có trong extract_text_and_images_from_pdf)
    # Tạo images_dict từ pages_data để có structure tương thích
    images_dict = {}
    for page_info in pages_data:
        page_num = page_info["page_num"]
        images_dict[page_num] = page_info.get("images", [])
    
    # Xử lý text: ghép text từ tất cả các trang và apply cleanup/spell check nếu cần
    all_text = "\n\n".join([page_info["text"] for page_info in pages_data])
    processed_text = all_text  # Mặc định là text gốc
    
    if apply_cleanup or apply_spell_check:
        logger.info("Đang xử lý text với AI (cleanup và spell check)...")
        
        # Apply cleanup nếu enabled
        cleanup_cfg = ocr_cfg.get("ai_cleanup", {})
        if apply_cleanup and cleanup_cfg.get("enabled", False):
            logger.info("🧹 Đang chạy AI Cleanup...")
            result = ai_cleanup_text(all_text, ocr_cfg)
            if isinstance(result, tuple):
                all_text, cleanup_failed_indices, cleanup_original_chunks = result
                cleanup_failed = len(cleanup_failed_indices)
                if cleanup_failed > 0:
                    logger.warning(f"AI Cleanup: {cleanup_failed} chunks failed")
            else:
                all_text = result
            logger.info("✅ Hoàn tất AI Cleanup")
        
        # Apply spell check nếu enabled
        spell_check_cfg = ocr_cfg.get("ai_spell_check", {})
        if apply_spell_check and spell_check_cfg.get("enabled", False):
            logger.info("✍️  Đang chạy AI Spell Check...")
            result = ai_spell_check_and_paragraph_restore(all_text, ocr_cfg)
            if isinstance(result, tuple):
                all_text, spell_check_failed_indices, spell_check_original_chunks = result
                spell_check_failed = len(spell_check_failed_indices)
                if spell_check_failed > 0:
                    logger.warning(f"AI Spell Check: {spell_check_failed} chunks failed")
            else:
                all_text = result
            logger.info("✅ Hoàn tất AI Spell Check")
        
        # Sau khi xử lý, text đã được cleanup và spell check
        # Ta sẽ lưu toàn bộ text đã xử lý và chèn vào DOCX sau tất cả images
        # Để giữ liên kết giữa images và text, ta sẽ:
        # 1. Chèn images từ tất cả các trang (giữ nguyên thứ tự)
        # 2. Chèn toàn bộ text đã xử lý sau tất cả images
        processed_text = all_text
    
    # Tạo DOCX document
    try:
        doc = config.Document()
    except Exception as e:
        raise RuntimeError(f"Không thể tạo Document object: {e}")
    
    # Set document properties (optional)
    try:
        doc.core_properties.title = os.path.splitext(os.path.basename(pdf_path))[0]
    except Exception:
        pass
    
    # python-docx tự động tạo một paragraph trống khi khởi tạo config.Document()
    # Ta sẽ để nó như vậy và chỉ thêm nội dung khi cần
    
    show_progress = bool(ocr_cfg.get("show_progress", True))
    total_items = len(pages_data)
    
    if show_progress and tqdm is not None:
        iterator = config.tqdm(pages_data, desc="Tạo DOCX", unit="trang")
    else:
        iterator = pages_data
    
    import io
    
    # Nếu có text đã được xử lý (cleanup/spell check), ta sẽ chèn text sau tất cả images
    has_processed_text = apply_cleanup or apply_spell_check
    
    # Bước 1: Chèn tất cả images từ tất cả các trang (giữ nguyên thứ tự)
    all_images = []
    for page_info in pages_data:
        all_images.extend([(page_info["page_num"], img_info) for img_info in page_info["images"]])
    
    # Chèn images
    images_added_count = 0
    if all_images:
        for page_num, img_info in (config.tqdm(all_images, desc="Chèn images", unit="ảnh") if (show_progress and tqdm and len(all_images) > 1) else all_images):
            try:
                image_bytes = img_info.get("data")
                if not image_bytes or len(image_bytes) == 0:
                    logger.warning(f"Image data rỗng từ trang {page_num}, bỏ qua")
                    continue
                
                if len(image_bytes) < 10:  # Image quá nhỏ, có thể không hợp lệ
                    logger.warning(f"Image từ trang {page_num} quá nhỏ ({len(image_bytes)} bytes), bỏ qua")
                    continue
                
                image_ext = img_info.get("ext", "png")
                
                # Validate image data - kiểm tra magic bytes
                is_valid = False
                if image_ext.lower() in ("jpeg", "jpg"):
                    if len(image_bytes) >= 2 and image_bytes[:2] == b'\xff\xd8':
                        is_valid = True
                elif image_ext.lower() == "png":
                    if len(image_bytes) >= 8 and image_bytes[:8] == b'\x89PNG\r\n\x1a\n':
                        is_valid = True
                elif image_ext.lower() in ("gif", "bmp", "tiff", "webp"):
                    # Chấp nhận các format khác mà không validate magic bytes (để python-docx xử lý)
                    is_valid = True
                else:
                    # Format khác, thử add anyway
                    is_valid = True
                
                if not is_valid:
                    logger.warning(f"Image từ trang {page_num} không phải {image_ext.upper()} hợp lệ, bỏ qua")
                    continue
                
                # Tạo image từ bytes
                img_stream = io.BytesIO(image_bytes)
                img_stream.seek(0)  # Đảm bảo stream ở đầu file
                
                # Thêm image vào document
                # Giới hạn kích thước để vừa với page width
                para = doc.add_paragraph()
                run = para.add_run()
                
                # Tính toán kích thước image (giữ tỷ lệ)
                img_width = img_info.get("width", 0)
                img_height = img_info.get("height", 0)
                
                try:
                    if img_width > 0 and img_height > 0:
                        # Giới hạn width tối đa là 6 inches (khoảng 15cm)
                        max_width_inches = 6.0
                        aspect_ratio = img_height / img_width
                        
                        if img_width > 500:  # Nếu image lớn, scale xuống
                            width_inches = min(max_width_inches, img_width / 96.0)  # Giả định 96 DPI
                            height_inches = width_inches * aspect_ratio
                        else:
                            width_inches = img_width / 96.0
                            height_inches = img_height / 96.0
                        
                        # Đảm bảo kích thước hợp lệ (min 0.1 inches, max 7 inches)
                        if width_inches > 0.1 and height_inches > 0.1:
                            run.add_picture(img_stream, width=config.Inches(min(width_inches, max_width_inches)))
                            images_added_count += 1
                        else:
                            run.add_picture(img_stream, width=config.Inches(4.0))
                            images_added_count += 1
                    else:
                        # Nếu không có thông tin size, dùng default
                        run.add_picture(img_stream, width=config.Inches(4.0))
                        images_added_count += 1
                    
                    # Thêm spacing sau image
                    para_format = para.paragraph_format
                    para_format.space_after = config.Pt(6)
                except Exception as pic_error:
                    # Nếu add_picture thất bại, xóa paragraph trống
                    logger.warning(f"Không thể add picture vào DOCX từ trang {page_num}: {pic_error}")
                    # Không cần xóa paragraph vì python-docx sẽ xử lý
                    continue
                
            except Exception as e:
                logger.warning(f"Không thể thêm image vào DOCX từ trang {page_num}: {e}")
                import traceback
                logger.debug(traceback.format_exc())
                continue
    
    if all_images and images_added_count == 0:
        logger.warning(f"Không có image nào được thêm vào DOCX (tổng {len(all_images)} images)")
    
    # Bước 2: Chèn text đã được xử lý (nếu có) hoặc text gốc từ từng trang
    text_added = False
    if has_processed_text:
        # Chèn toàn bộ text đã được xử lý sau tất cả images
        if processed_text and processed_text.strip():
            logger.info("Đang chèn text đã được xử lý vào DOCX...")
            # Chia text thành paragraphs (dựa trên double newlines)
            paragraphs = processed_text.split('\n\n')
            
            for para_text in paragraphs:
                para_text = para_text.strip()
                if para_text:
                    para = doc.add_paragraph(para_text)
                    para_format = para.paragraph_format
                    para_format.space_after = config.Pt(6)
                    text_added = True
    else:
        # Không có xử lý → chèn text gốc từ từng trang cùng với images
        for page_info in iterator:
            page_num = page_info["page_num"]
            text = page_info["text"]
            
            # Thêm text của trang này
            if text and text.strip():
                # Chia text thành paragraphs (dựa trên double newlines)
                paragraphs = text.split('\n\n')
                
                for para_text in paragraphs:
                    para_text = para_text.strip()
                    if para_text:
                        para = doc.add_paragraph(para_text)
                        para_format = para.paragraph_format
                        para_format.space_after = config.Pt(6)
                        text_added = True
            
            # Thêm page break sau mỗi trang (trừ trang cuối) - chỉ khi có text hoặc images
            if page_num < pages_data[-1]["page_num"]:
                doc.add_page_break()
            
            if not show_progress and (page_num % 50 == 0 or page_num == total_items):
                logger.info(f"Đã xử lý {page_num}/{total_items} trang")
    
    # Đảm bảo document có ít nhất một paragraph hợp lệ (nếu không có gì cả)
    # Kiểm tra xem có nội dung gì không (images hoặc text)
    has_content = text_added or images_added_count > 0
    
    if not has_content:
        logger.warning("Document không có nội dung (không có text và images). Thêm paragraph mặc định...")
        try:
            # Thêm paragraph có nội dung
            # Không xóa paragraph trống vì có thể gây lỗi cấu trúc DOCX
            doc.add_paragraph("(Không có nội dung từ PDF)")
        except Exception as e:
            logger.warning(f"Không thể thêm paragraph mặc định: {e}")
            # Fallback: thử thêm vào paragraph đầu tiên nếu có
            try:
                if len(doc.paragraphs) > 0:
                    doc.paragraphs[0].text = "(Không có nội dung)"
                else:
                    doc.add_paragraph("(Không có nội dung)")
            except Exception:
                pass
    
    # Validate document trước khi save
    try:
        # Kiểm tra xem document có hợp lệ không
        # Document phải có ít nhất một element (paragraph với text hoặc images được embed)
        total_elements = len(doc.paragraphs)
        if total_elements == 0:
            logger.warning("Document trống, thêm paragraph mặc định")
            doc.add_paragraph("(Không có nội dung)")
        else:
            # Kiểm tra xem có paragraph nào có nội dung không (text hoặc runs - có thể chứa images)
            has_any_content = False
            for para in doc.paragraphs:
                # Kiểm tra text
                if para.text.strip():
                    has_any_content = True
                    break
                # Kiểm tra runs (có thể chứa images hoặc inline shapes)
                if len(para.runs) > 0:
                    # Nếu có runs, giả định là có nội dung (images hoặc text)
                    has_any_content = True
                    break
            
            if not has_any_content:
                logger.warning("Tất cả paragraphs đều trống, thêm paragraph mặc định")
                # Sử dụng paragraph đầu tiên nếu có, hoặc tạo mới
                try:
                    if len(doc.paragraphs) > 0:
                        # Thêm text vào paragraph đầu tiên
                        para = doc.paragraphs[0]
                        if not para.text.strip():
                            para.add_run("(Không có nội dung)")
                        else:
                            doc.add_paragraph("(Không có nội dung)")
                    else:
                        doc.add_paragraph("(Không có nội dung)")
                except Exception:
                    # Fallback: chỉ tạo paragraph mới
                    try:
                        doc.add_paragraph("(Không có nội dung)")
                    except Exception:
                        pass
    except Exception as e:
        logger.warning(f"Không thể validate document: {e}")
    
    # Lưu file
    logger.info(f"Đang lưu DOCX: {output_path}")
    try:
        doc.save(output_path)
        logger.info(f"✅ Đã tạo DOCX thành công: {output_path}")
        
        # Validate file sau khi save (kiểm tra file size)
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                raise ValueError("File DOCX có kích thước 0 bytes - không hợp lệ")
            logger.info(f"📄 File size: {file_size:,} bytes")
    except Exception as e:
        logger.error(f"❌ Lỗi khi lưu DOCX: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
    
    return output_path

def _fix_docx_leading_tabs_and_soft_wraps(docx_path: str) -> None:
    """
    Khắc phục các tab thừa đầu dòng do soft-wrap khi convert PDF→DOCX (pdf2docx).
    Quy tắc an toàn (không xâm phạm layout nhiều):
    - Nếu một paragraph bắt đầu bằng tab (\t) và ký tự đầu tiên có nghĩa sau tab là chữ thường/không phải số/bullet,
      và paragraph trước đó KHÔNG kết thúc bằng dấu câu (., !, ?), thì loại bỏ các tab/space đầu paragraph đó.
    - Không merge/xóa paragraph để tránh rủi ro layout; chỉ loại bỏ tab đầu dòng gây xấu văn bản.
    """
    try:
        if Document is None:
            return
        doc = config.Document(docx_path)
        prev_text = ""
        for para in doc.paragraphs:
            full_text = para.text or ""
            try:
                import re
            except Exception:
                re = None
            
            # Bỏ qua đoạn có URL để tránh phá hyperlink/format
            if re and re.search(r"https?://\S+", full_text):
                prev_text = full_text
                continue
            
            # 1) Loại tab nội tuyến trong từng run để giữ hyperlink và format
            for run in getattr(para, 'runs', []):
                if not run.text:
                    continue
                if re:
                    new_run_text = re.sub(r"\s*\t+\s*", " ", run.text)
                else:
                    new_run_text = run.text.replace("\t", " ")
                if new_run_text != run.text:
                    run.text = new_run_text
            
            # Cập nhật lại full_text sau bước (1)
            full_text = para.text or ""
            stripped = full_text.lstrip("\t ")
            starts_with_tab = (full_text != stripped)
            prev_ends_with_punct = bool(re.search(r"[.!?]$", prev_text.strip())) if (re and prev_text) else False
            is_bullet_like = bool(re.match(r"^[•·\-*]\s", stripped)) or bool(re.match(r"^\d+[.)]\s", stripped)) if re else False
            
            # 2) Loại tab/space đầu đoạn (continuation của câu trước), chỉ tác động lên runs đầu
            if starts_with_tab and not prev_ends_with_punct and not is_bullet_like:
                remaining_to_strip = len(full_text) - len(stripped)
                # Bỏ qua nếu stripping làm rỗng hoàn toàn (an toàn)
                if remaining_to_strip > 0 and stripped:
                    for run in getattr(para, 'runs', []):
                        if remaining_to_strip <= 0:
                            break
                        if not run.text:
                            continue
                        run_len = len(run.text)
                        # Tính số ký tự whitespace đầu run có thể cắt
                        prefix = 0
                        while prefix < run_len and remaining_to_strip > 0 and run.text[prefix] in ('\t', ' '):
                            prefix += 1
                            remaining_to_strip -= 1
                        if prefix > 0:
                            run.text = run.text[prefix:]
                        # Nếu run không còn whitespace đầu và vẫn còn remaining_to_strip, tiếp tục sang run kế
            
            prev_text = para.text or ""
        doc.save(docx_path)
    except Exception:
        # Không chặn pipeline nếu chỉnh sửa thất bại
        pass

def _create_html_from_items(all_items_with_position: List[dict], output_path: str) -> str:
    """
    Tạo file HTML từ all_items_with_position (text + images).
    Images được embed dưới dạng base64 để không cần temp files.
    
    Args:
        all_items_with_position: List các items (text hoặc image) đã được sort theo (Y, X)
        output_path: Đường dẫn file DOCX output (để tạo HTML temp file cùng folder)
    
    Returns:
        str: Đường dẫn file HTML đã tạo
    """
    import base64
    import html
    
    html_path = output_path.replace('.docx', '_temp.html')
    if html_path == output_path:  # Nếu không phải .docx
        html_path = output_path + '_temp.html'
    
    logger.info(f"📄 Tạo HTML trung gian: {html_path}")
    
    html_parts = ['<!DOCTYPE html>\n<html>\n<head>\n<meta charset="UTF-8">\n']
    html_parts.append('<style>\n')
    html_parts.append('body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }\n')
    html_parts.append('p { margin-bottom: 6pt; }\n')
    html_parts.append('img { max-width: 6in; height: auto; margin: 6pt 0; display: block; }\n')
    html_parts.append('</style>\n</head>\n<body>\n')
    
    images_count = 0
    text_count = 0
    
    for item in all_items_with_position:
        if item["type"] == "text":
            content = item["content"]
            # Escape HTML và thay thế line breaks
            content = html.escape(content)
            content = content.replace('\n\n', '</p><p>')
            content = content.replace('\n', '<br>')
            html_parts.append(f'<p>{content}</p>\n')
            text_count += 1
        elif item["type"] == "image":
            img_info = item["img_info"]
            image_bytes = img_info.get("data")
            if image_bytes and len(image_bytes) >= 10:
                image_ext = img_info.get("ext", "png").lower()
                if image_ext == "jpg":
                    image_ext = "jpeg"
                
                # Convert image bytes to base64
                try:
                    base64_data = base64.b64encode(image_bytes).decode('utf-8')
                    data_uri = f"data:image/{image_ext};base64,{base64_data}"
                    
                    # Get image dimensions for sizing
                    img_width = img_info.get("width", 0)
                    img_height = img_info.get("height", 0)
                    
                    if img_width > 0 and img_height > 0:
                        max_width_px = 576  # 6 inches at 96 DPI
                        if img_width > max_width_px:
                            aspect_ratio = img_height / img_width
                            display_width = max_width_px
                            display_height = int(max_width_px * aspect_ratio)
                        else:
                            display_width = img_width
                            display_height = img_height
                        
                        html_parts.append(f'<img src="{data_uri}" width="{display_width}" height="{display_height}" alt="Image from page {item["page_num"]}">\n')
                    else:
                        html_parts.append(f'<img src="{data_uri}" alt="Image from page {item["page_num"]}">\n')
                    
                    images_count += 1
                    logger.debug(f"✅ Đã embed image {images_count} vào HTML (trang {item['page_num']}, size: {len(image_bytes)} bytes)")
                except Exception as e:
                    logger.warning(f"⚠️ Không thể convert image từ trang {item['page_num']} sang base64: {e}")
            else:
                logger.warning(f"⚠️ Image từ trang {item['page_num']} không có data hợp lệ (size: {len(image_bytes) if image_bytes else 0} bytes)")
    
    html_parts.append('</body>\n</html>')
    
    html_content = ''.join(html_parts)
    
    try:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.info(f"✅ Đã tạo HTML: {text_count} paragraphs, {images_count} images")
        return html_path
    except Exception as e:
        logger.error(f"❌ Không thể tạo HTML file: {e}")
        raise

def _convert_html_to_docx_with_pandoc(html_path: str, output_path: str, ocr_cfg: dict) -> bool:
    """
    Convert HTML sang DOCX bằng pandoc.
    
    Args:
        html_path: Đường dẫn file HTML input
        output_path: Đường dẫn file DOCX output
        ocr_cfg: Config dictionary
    
    Returns:
        bool: True nếu thành công, False nếu thất bại
    """
    try:
        import pypandoc
    except ImportError:
        logger.warning("⚠️ pypandoc chưa được cài đặt. Cài pypandoc để dùng HTML intermediate workflow.")
        return False
    
    try:
        logger.info(f"🔄 Đang convert HTML → DOCX bằng pandoc...")
        # Pandoc options để preserve images và formatting
        extra_args = [
            '--standalone',
            '--wrap=none',  # Không wrap lines
        ]
        
        pypandoc.convert_file(
            html_path,
            'docx',
            outputfile=output_path,
            extra_args=extra_args
        )
        
        logger.info(f"✅ Đã convert HTML → DOCX thành công bằng pandoc")
        return True
    except Exception as e:
        logger.warning(f"⚠️ Pandoc conversion thất bại: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False

