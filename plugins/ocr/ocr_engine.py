# -*- coding: utf-8 -*-

"""
OCR reader module: extract text from scanned PDFs or images based on settings in config/config.yaml.
(Facade pattern: implementation moved to plugins/ocr/modules/)
"""

# Re-exports for backward compatibility
from plugins.ocr.modules.config import (
    load_ocr_config, lazy_import_and_install,
    _ensure_dependencies, _ensure_logger_config,
    _detect_bundled_binaries, _apply_tesseract_cfg,
    _parse_pages, _build_safety_settings,
    NoisyMessageFilter, GoogleLogFilter,
)
from plugins.ocr.modules.image import (
    _image_to_text, _normalize_lang_code, _resolve_language,
)
from plugins.ocr.modules.pdf import (
    detect_pdf_type, extract_text_from_pdf,
    extract_text_blocks_with_position, convert_pdf_with_ocrmypdf,
)
from plugins.ocr.modules.tables import (
    _extract_tables_with_unstructured, _extract_tables_pytesseract_advanced,
    _try_extract_tables_from_pdf_via_ocrmypdf, _extract_tables_from_images_cv,
)
from plugins.ocr.modules.formats import (
    extract_format_hints, extract_paragraphs_with_hints,
    batch_small_paragraphs, convert_pdf_to_docx,
    update_docx_with_processed_text, convert_docx_to_epub,
    create_docx_from_processed_text, create_docx_from_pdf,
    extract_text_and_images_from_pdf, _fix_docx_leading_tabs_and_soft_wraps,
)
from plugins.ocr.modules.ai_processor import (
    ai_cleanup_text, ai_spell_check_and_paragraph_restore,
    ai_cleanup_table_with_coordinates, cleanup_paragraph_with_hints,
    spell_check_paragraph, build_cleanup_prompt_with_hints,
)
from plugins.ocr.modules import config as _cfg

def hybrid_workflow_pdf_to_docx(pdf_path: str, output_path: str, ocr_cfg: dict, pages: Optional[List[int]] = None) -> str:
    """
    Hybrid workflow: PDF → DOCX → Cleanup & Spell Check → DOCX
    
    Args:
        pdf_path: Đường dẫn file PDF input
        output_path: Đường dẫn file DOCX output
        ocr_cfg: Config dictionary
        pages: Danh sách số trang cần process (1-indexed). None = tất cả trang.
    
    Returns:
        str: Đường dẫn file DOCX output
    """
    logger.info("=" * 80)
    logger.info("🚀 BẮT ĐẦU HYBRID WORKFLOW")
    logger.info("=" * 80)
    
    # Step 1: Convert PDF → DOCX
    temp_docx_path = output_path.replace(".docx", "_temp.docx")
    try:
        convert_pdf_to_docx(pdf_path, temp_docx_path, pages)
    except Exception as e:
        logger.error(f"❌ Không thể convert PDF → DOCX: {e}")
        raise
    
    # Step 2: Extract paragraphs với hints
    try:
        paragraphs_data = extract_paragraphs_with_hints(temp_docx_path)
        if not paragraphs_data:
            raise RuntimeError("Không extract được paragraphs từ DOCX")
    except Exception as e:
        logger.error(f"❌ Không thể extract paragraphs: {e}")
        raise
    
    # Step 3: Batch small paragraphs
    batched_paragraphs = batch_small_paragraphs(paragraphs_data, min_chars=50)
    
    # Step 4: Process từng paragraph/batch (Cleanup + Spell Check)
    processed_paragraphs = []
    
    logger.info(f"🔄 Đang process {len(batched_paragraphs)} paragraphs/batches...")
    for idx, para_data in enumerate(batched_paragraphs, 1):
        logger.info(f"Processing {idx}/{len(batched_paragraphs)}...")
        
        # Cleanup
        cleanup_result = cleanup_paragraph_with_hints(para_data, ocr_cfg)
        para_data["cleaned_text"] = cleanup_result["cleaned_text"]
        para_data["should_merge_with_next"] = cleanup_result.get("should_merge_with_next", False)
        
        # Spell check
        spell_checked_text = spell_check_paragraph(para_data, ocr_cfg)
        para_data["spell_checked_text"] = spell_checked_text
        
        processed_paragraphs.append(para_data)
    
    # Step 5: Update DOCX với processed text
    try:
        update_docx_with_processed_text(temp_docx_path, processed_paragraphs, ocr_cfg)
    except Exception as e:
        logger.error(f"❌ Không thể update DOCX: {e}")
        raise
    
    # Step 6: Move temp file to final output
    try:
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(temp_docx_path, output_path)
        logger.info(f"✅ Đã tạo DOCX: {output_path}")
    except Exception as e:
        logger.error(f"❌ Không thể move file: {e}")
        raise
    
    # Step 7: Cleanup intermediate files
    _cleanup_intermediate_files(output_path)
    
    # Return DOCX path
    return output_path

def _get_intermediate_file_path(output_path: str, suffix: str) -> str:
    """Tạo đường dẫn file tạm thời dựa trên output_path và suffix."""
    output_dir = os.path.dirname(output_path) if os.path.dirname(output_path) else "."
    output_basename = os.path.basename(output_path)
    output_name_without_ext = os.path.splitext(output_basename)[0]
    return os.path.join(output_dir, output_name_without_ext + suffix)

def _cleanup_intermediate_files(output_path: str):
    """
    Xóa các file trung gian (_ocred.txt, _cleanup.txt) sau khi đã tạo file final.
    
    Args:
        output_path: Đường dẫn file output final (để tạo tên file trung gian)
    """
    intermediate_files = [
        _get_intermediate_file_path(output_path, "_ocred.txt"),
        _get_intermediate_file_path(output_path, "_cleanup.txt")
    ]
    
    for file_path in intermediate_files:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.debug(f"🗑️  Đã xóa file trung gian: {file_path}")
        except Exception as e:
            logger.debug(f"Không thể xóa file trung gian {file_path}: {e}")

def _check_existing_files(output_path: str) -> dict:
    """Kiểm tra các file đã tồn tại từ phiên làm việc trước."""
    results = {
        "ocred": None,
        "cleanup": None,
        "output": None,
        "all_exist": False
    }
    
    ocred_path = _get_intermediate_file_path(output_path, "_ocred.txt")
    cleanup_path = _get_intermediate_file_path(output_path, "_cleanup.txt")
    
    if os.path.exists(ocred_path):
        results["ocred"] = ocred_path
    if os.path.exists(cleanup_path):
        results["cleanup"] = cleanup_path
    if os.path.exists(output_path):
        results["output"] = output_path
    
    results["all_exist"] = any([results["ocred"], results["cleanup"], results["output"]])
    return results

def _load_resume_file(file_path: str, step_name: str) -> Optional[str]:
    """Load file từ phiên trước để resume."""
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"✅ Đã load file {step_name}: {file_path}")
        return content
    except Exception as e:
        logger.warning(f"Không thể load file {step_name} ({file_path}): {e}")
        return None

def _show_completion_menu(cleanup_failed: int, spell_check_failed: int, output_path: str = None) -> str:
    """Hiển thị menu lựa chọn sau khi OCR hoàn tất. Trả về 'retry', 'save', hoặc 'exit'."""
    import threading
    
    has_failures = cleanup_failed > 0 or spell_check_failed > 0
    user_choice = None
    user_choice_lock = threading.Lock()
    user_choice_done = threading.Event()
    
    def _auto_save_timer():
        nonlocal user_choice
        time.sleep(600)  # 10 phút = 600 giây
        with user_choice_lock:
            if user_choice is None:
                logger.info("\n⏰ Tự động lưu file sau 10 phút...")
                user_choice = "save"
                user_choice_done.set()
    
    auto_save_thread = threading.Thread(target=_auto_save_timer, daemon=True)
    auto_save_thread.start()
    
    if not has_failures:
        # Không có lỗi, chỉ có option save/exit
        logger.info("\n" + "=" * 80)
        logger.info("✅ OCR hoàn tất không có lỗi!")
        logger.info("=" * 80)
        logger.info("Lựa chọn:")
        logger.info("  1. Lưu file (tự động lưu sau 10 phút nếu không chọn)")
        logger.info("  2. Thoát không lưu")
        logger.info("=" * 80)
        
        while not user_choice_done.is_set():
            try:
                choice = input("\nNhập lựa chọn (1/2): ").strip()
                with user_choice_lock:
                    if choice == "1":
                        user_choice = "save"
                        user_choice_done.set()
                        break
                    elif choice == "2":
                        user_choice = "exit"
                        user_choice_done.set()
                        break
                    else:
                        logger.warning("Lựa chọn không hợp lệ. Vui lòng nhập 1 hoặc 2.")
            except (EOFError, KeyboardInterrupt):
                with user_choice_lock:
                    user_choice = "save"
                    user_choice_done.set()
                break
    else:
        # Có lỗi, hiển thị đầy đủ 3 options
        logger.info("\n" + "=" * 80)
        logger.info("⚠️  OCR hoàn tất với một số lỗi:")
        if cleanup_failed > 0:
            logger.info(f"  - AI Cleanup: {cleanup_failed} chunks failed")
        if spell_check_failed > 0:
            logger.info(f"  - AI Spell Check: {spell_check_failed} chunks failed")
        logger.info("=" * 80)
        logger.info("Lựa chọn:")
        logger.info("  1. Retry các chunk failed")
        logger.info("  2. Lưu file (tự động lưu sau 10 phút nếu không chọn)")
        logger.info("  3. Thoát không lưu")
        logger.info("=" * 80)
        
        while not user_choice_done.is_set():
            try:
                choice = input("\nNhập lựa chọn (1/2/3): ").strip()
                with user_choice_lock:
                    if choice == "1":
                        user_choice = "retry"
                        user_choice_done.set()
                        break
                    elif choice == "2":
                        user_choice = "save"
                        user_choice_done.set()
                        break
                    elif choice == "3":
                        user_choice = "exit"
                        user_choice_done.set()
                        break
                    else:
                        logger.warning("Lựa chọn không hợp lệ. Vui lòng nhập 1, 2 hoặc 3.")
            except (EOFError, KeyboardInterrupt):
                with user_choice_lock:
                    user_choice = "save"
                    user_choice_done.set()
                break
    
    # Đợi user chọn hoặc auto-save
    user_choice_done.wait()
    return user_choice if user_choice else "save"

def ocr_image(image_path: str, config_path: str = "config/config.yaml") -> str:
    ocr_cfg = _detect_bundled_binaries(load_ocr_config(config_path))
    _ensure_dependencies(ocr_cfg)
    if Image is None:
        raise RuntimeError("Pillow not installed. Please install pillow.")
    _apply_tesseract_cfg(ocr_cfg)
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)
    logger.info(f"OCR: Đang nhận dạng ảnh: {image_path}")
    img = Image.open(image_path)
    # Auto-detect language/variant nếu cần
    raw_lang = ocr_cfg.get("lang", "vie")
    normalized_lang = _normalize_lang_code(raw_lang)
    
    # Chỉ detect Chinese variant nếu lang="CN" hoặc "chi" (không có auto-detect)
    needs_chinese_variant_detection = ("chi" in normalized_lang.lower() and 
                                       "chi_sim" not in normalized_lang and 
                                       "chi_tra" not in normalized_lang)
    
    if needs_chinese_variant_detection:
        # Chỉ detect Chinese variant (giản thể/phồn thể)
        resolved_lang = _resolve_language(raw_lang, ocr_cfg, sample_img=img)
        text = _image_to_text(img, ocr_cfg, lang_override=resolved_lang)
    else:
        # Chỉ normalize, không cần detect
        resolved_lang = _resolve_language(raw_lang, ocr_cfg, sample_img=None)
        text = _image_to_text(img, ocr_cfg, lang_override=resolved_lang)
    return text

def ocr_pdf(pdf_path: str, config_path: str = "config/config.yaml", pages: Optional[List[int]] = None) -> tuple[str, int]:
    ocr_cfg = _detect_bundled_binaries(load_ocr_config(config_path))
    _ensure_dependencies(ocr_cfg)
    if convert_from_path is None:
        raise RuntimeError("pdf2image not installed. Please install pdf2image and poppler if needed.")
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)
    _apply_tesseract_cfg(ocr_cfg)

    # Tối ưu DPI: giảm mặc định từ 300 → 250
    dpi = int(ocr_cfg.get("dpi", 250) or 250)
    poppler_path = ocr_cfg.get("poppler_path")
    
    # Config cho batch processing và memory optimization
    max_batch_size = int(ocr_cfg.get("render_batch_size", 20))  # Render tối đa 20 trang/batch
    image_format = ocr_cfg.get("image_format", "jpeg").lower()  # jpeg hoặc png
    jpeg_quality = int(ocr_cfg.get("jpeg_quality", 85))  # Quality 85-90 cho OCR
    memory_optimize = ocr_cfg.get("memory_optimize", True)

    # Resume/caching: sử dụng thư mục cùng tên file input để lưu/trích xuất ảnh các trang
    pdf_p = Path(pdf_path)
    cache_dir = pdf_p.with_suffix("")  # cùng tên với file, bỏ đuôi .pdf
    
    # Helper function để render và save với batch processing, format tối ưu, và memory management
    def _render_and_save_batch(first_page: int, last_page: int, image_format: str, jpeg_quality: int, memory_optimize: bool) -> dict[int, Path]:
        """Render một batch pages và save với format tối ưu. Trả về dict: page_idx → Path."""
        result: dict[int, Path] = {}
        try:
            # CẢI TIẾN: Error handling tốt hơn cho Poppler
            # Dùng biến local để tránh UnboundLocalError khi gán lại poppler_path
            actual_poppler_path = poppler_path
            try:
                if actual_poppler_path and isinstance(actual_poppler_path, str) and actual_poppler_path.strip():
                    # Kiểm tra Poppler path có tồn tại không
                    poppler_bin = os.path.join(actual_poppler_path, "pdftoppm.exe" if sys.platform == "win32" else "pdftoppm")
                    if not os.path.exists(poppler_bin):
                        logger.warning(f"⚠️  Poppler path không hợp lệ: {actual_poppler_path}")
                        logger.warning(f"💡 Đang thử không dùng poppler_path...")
                        actual_poppler_path = None
                    
                    if actual_poppler_path:
                        imgs = convert_from_path(pdf_path, dpi=dpi, poppler_path=actual_poppler_path,
                                                  first_page=first_page, last_page=last_page, thread_count=1)
                    else:
                        imgs = convert_from_path(pdf_path, dpi=dpi, first_page=first_page, last_page=last_page, thread_count=1)
                else:
                    imgs = convert_from_path(pdf_path, dpi=dpi, first_page=first_page, last_page=last_page, thread_count=1)
            except Exception as poppler_err:
                error_msg = str(poppler_err).lower()
                if "poppler" in error_msg or "pdftoppm" in error_msg or "pdftocairo" in error_msg:
                    logger.error(f"❌ Lỗi Poppler khi render batch {first_page}-{last_page}: {poppler_err}")
                    logger.error("💡 Hướng dẫn cài đặt Poppler:")
                    logger.error("   - Windows: Tải từ https://github.com/oschwartz10612/poppler-windows/releases")
                    logger.error("   - Hoặc dùng: choco install poppler")
                    logger.error("   - Sau khi cài, thêm đường dẫn bin vào config.yaml (poppler_path)")
                    raise RuntimeError(f"Poppler không khả dụng: {poppler_err}. Vui lòng cài đặt Poppler và cấu hình poppler_path trong config.yaml")
                else:
                    # Lỗi khác (có thể là PDF corrupt, permission, etc.)
                    logger.error(f"❌ Lỗi khi convert PDF sang ảnh (batch {first_page}-{last_page}): {poppler_err}")
                    raise
            
            # CẢI TIẾN: Memory handling tốt hơn trong loop
            for offset, img in enumerate(imgs):
                idx = first_page + offset
                # Chọn extension dựa trên format
                ext = ".jpg" if image_format == "jpeg" else ".png"
                out_path = cache_dir / f"page_{idx:04d}{ext}"
                
                try:
                    # Save với format và compression tối ưu
                    if image_format == "jpeg":
                        # Convert RGBA/RGB nếu cần (JPEG không hỗ trợ alpha)
                        if img.mode in ('RGBA', 'LA', 'P'):
                            # Tạo nền trắng cho alpha channel
                            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'P':
                                img = img.convert('RGBA')
                            rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                            # CẢI TIẾN: Giải phóng img cũ trước khi gán mới
                            if memory_optimize:
                                del img
                                gc.collect()
                            img = rgb_img
                        img.save(str(out_path), format='JPEG', quality=jpeg_quality, optimize=True)
                    else:
                        # PNG với optimize
                        img.save(str(out_path), format='PNG', optimize=True)
                    
                    result[idx] = out_path
                    
                    # CẢI TIẾN: Memory management - giải phóng ngay sau khi save
                    if memory_optimize:
                        if 'img' in locals():
                            del img
                        if offset % 5 == 0:  # Garbage collect mỗi 5 images
                            gc.collect()
                except Exception as e:
                    logger.warning(f"Không thể lưu ảnh cache {out_path}: {e}")
                    # Giải phóng memory ngay cả khi lỗi
                    if memory_optimize and 'img' in locals():
                        del img
                        gc.collect()
            
            # CẢI TIẾN: Final garbage collect sau batch
            if memory_optimize:
                if 'imgs' in locals():
                    del imgs
                gc.collect()
        except RuntimeError:
            # Re-raise RuntimeError từ Poppler (đã có hướng dẫn)
            raise
        except Exception as e:
            logger.error(f"Render batch {first_page}-{last_page} thất bại: {e}")
            # Giải phóng memory nếu có
            if memory_optimize:
                if 'imgs' in locals():
                    del imgs
                gc.collect()
        return result
    
    def _split_range_into_batches(range_start: int, range_end: int, batch_size: int) -> List[tuple[int, int]]:
        """Chia một range lớn thành các batches nhỏ."""
        batches = []
        current = range_start
        while current <= range_end:
            batch_end = min(current + batch_size - 1, range_end)
            batches.append((current, batch_end))
            current = batch_end + 1
        return batches

    def _list_cached_images(dir_path: Path) -> List[Path]:
        if not dir_path.exists() or not dir_path.is_dir():
            return []
        image_exts = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
        files = [p for p in dir_path.iterdir() if p.suffix.lower() in image_exts]
        if not files:
            return []
        def sort_key(p: Path):
            name = p.stem
            digits = "".join(ch for ch in name if ch.isdigit())
            return (int(digits) if digits else 0, name)
        return sorted(files, key=sort_key)

    cached_images = _list_cached_images(cache_dir)

    # Lấy tổng số trang PDF để so sánh cache và thực hiện resume nếu thiếu
    def _get_total_pages(pdf_file: str) -> Optional[int]:
        try:
            if pdfplumber is not None:
                with pdfplumber.open(pdf_file) as pdf:
                    return len(pdf.pages)
        except Exception:
            pass
        try:
            if PyPDF2 is not None:
                with open(pdf_file, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    return len(reader.pages)
        except Exception:
            pass
        return None

    total_pages = _get_total_pages(pdf_path)
    if total_pages is not None:
        logger.info(f"OCR: PDF có {total_pages} trang. Ảnh cache hiện có: {len(cached_images)}")
    else:
        logger.info(f"OCR: Không xác định được tổng số trang. Ảnh cache hiện có: {len(cached_images)}")
    
    # Filter pages nếu có chỉ định
    if pages and total_pages is not None:
        valid_pages = [p for p in pages if 1 <= p <= total_pages]
        invalid_pages = [p for p in pages if p < 1 or p > total_pages]
        if invalid_pages:
            logger.warning(f"Các trang không hợp lệ (nằm ngoài 1-{total_pages}): {invalid_pages}. Bỏ qua.")
        if not valid_pages:
            logger.error("Không có trang hợp lệ nào để OCR.")
            return ("", 0)
        pages_to_ocr = sorted(set(valid_pages))
        logger.info(f"OCR: Chỉ OCR {len(pages_to_ocr)} trang: {pages_to_ocr}")
    elif pages:
        # Không biết total_pages nhưng có pages chỉ định → dùng pages đó
        pages_to_ocr = sorted(set([p for p in pages if p > 0]))
        logger.info(f"OCR: Chỉ OCR {len(pages_to_ocr)} trang (theo chỉ định): {pages_to_ocr}")
    else:
        pages_to_ocr = None  # Tất cả trang

    # Map chỉ số trang → đường dẫn ảnh (cache) hoặc ảnh render mới
    index_to_image_path: dict[int, Path] = {}
    # Parse chỉ số từ tên ảnh cache kiểu page_0001.png
    for p in cached_images:
        name = p.stem
        digits = "".join(ch for ch in name if ch.isdigit())
        if digits:
            try:
                idx = int(digits)
                # Chỉ lấy cache nếu trang đó nằm trong pages_to_ocr (hoặc pages_to_ocr = None)
                if pages_to_ocr is None or idx in pages_to_ocr:
                    index_to_image_path[idx] = p
            except Exception:
                continue

    # Render bổ sung cho các trang thiếu nếu biết total_pages
    if total_pages is not None:
        # Tính missing pages: nếu có pages_to_ocr thì chỉ tính trong đó, ngược lại tính tất cả
        if pages_to_ocr is not None:
            target_pages = set(pages_to_ocr)
            missing = [i for i in target_pages if i not in index_to_image_path]
        else:
            missing = [i for i in range(1, total_pages + 1) if i not in index_to_image_path]
        if missing:
            logger.info(f"OCR: Phát hiện thiếu {len(missing)}/{total_pages} ảnh → render phần còn thiếu")
            # Tạo thư mục cache nếu cần
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            # Gom missing pages thành các khoảng liên tiếp để render theo range
            ranges: List[tuple[int, int]] = []
            start = prev = None
            for m in missing:
                if start is None:
                    start = prev = m
                elif m == prev + 1:
                    prev = m
                else:
                    ranges.append((start, prev))
                    start = prev = m
            if start is not None:
                ranges.append((start, prev))

            # Render với batch processing để giảm memory usage
            for first, last in ranges:
                # Chia range lớn thành batches nhỏ
                batches = _split_range_into_batches(first, last, max_batch_size)
                for batch_first, batch_last in batches:
                    logger.info(f"OCR: Render bổ sung trang {batch_first}–{batch_last}/{last} (dpi={dpi}, format={image_format})")
                    batch_results = _render_and_save_batch(batch_first, batch_last, image_format, jpeg_quality, memory_optimize)
                    index_to_image_path.update(batch_results)
    # Nếu vẫn chưa có ảnh nào (không có cache và không biết total), render
    if not index_to_image_path:
        if pages_to_ocr is not None and total_pages is not None:
            # Chỉ render các trang được chỉ định
            logger.info(f"OCR: Chuyển PDF → ảnh (dpi={dpi}) cho {len(pages_to_ocr)} trang: {pages_to_ocr}")
            # Gom pages_to_ocr thành ranges để render hiệu quả
            ranges: List[tuple[int, int]] = []
            pages_sorted = sorted(pages_to_ocr)
            start = prev = None
            for p in pages_sorted:
                if start is None:
                    start = prev = p
                elif p == prev + 1:
                    prev = p
                else:
                    ranges.append((start, prev))
                    start = prev = p
            if start is not None:
                ranges.append((start, prev))
            
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            
            # Render với batch processing để giảm memory usage
            for first, last in ranges:
                # Chia range lớn thành batches nhỏ
                batches = _split_range_into_batches(first, last, max_batch_size)
                for batch_first, batch_last in batches:
                    logger.info(f"OCR: Render trang {batch_first}–{batch_last}/{last} (dpi={dpi}, format={image_format})")
                    batch_results = _render_and_save_batch(batch_first, batch_last, image_format, jpeg_quality, memory_optimize)
                    index_to_image_path.update(batch_results)
        else:
            # Render toàn bộ (không có pages filter) - CHIA THÀNH BATCHES để tránh ngốn RAM
            if total_pages is not None:
                logger.info(f"OCR: Chuyển PDF → ảnh (dpi={dpi}, format={image_format}): {total_pages} trang - render theo batch {max_batch_size} trang/batch")
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                # Chia toàn bộ PDF thành batches
                batches = _split_range_into_batches(1, total_pages, max_batch_size)
                for batch_first, batch_last in batches:
                    logger.info(f"OCR: Render batch {batch_first}–{batch_last}/{total_pages}")
                    batch_results = _render_and_save_batch(batch_first, batch_last, image_format, jpeg_quality, memory_optimize)
                    index_to_image_path.update(batch_results)
            else:
                # Không biết total_pages, phải render hết (vẫn cố gắng dùng thread_count=1 để giảm memory)
                logger.info(f"OCR: Chuyển PDF → ảnh (dpi={dpi}, format={image_format}): không biết số trang, render toàn bộ")
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                except Exception:
                    pass
                if poppler_path and isinstance(poppler_path, str) and poppler_path.strip():
                    all_imgs = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path, thread_count=1)
                else:
                    all_imgs = convert_from_path(pdf_path, dpi=dpi, thread_count=1)
                
                # Save với format tối ưu và memory management
                ext = ".jpg" if image_format == "jpeg" else ".png"
                for idx, img in enumerate(all_imgs, start=1):
                    out_path = cache_dir / f"page_{idx:04d}{ext}"
                    try:
                        if image_format == "jpeg":
                            if img.mode in ('RGBA', 'LA', 'P'):
                                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                if img.mode == 'P':
                                    img = img.convert('RGBA')
                                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                                img = rgb_img
                            img.save(str(out_path), format='JPEG', quality=jpeg_quality, optimize=True)
                        else:
                            img.save(str(out_path), format='PNG', optimize=True)
                        index_to_image_path[idx] = out_path
                        if memory_optimize:
                            del img
                            if idx % 5 == 0:
                                gc.collect()
                    except Exception as e:
                        logger.warning(f"Không thể lưu ảnh cache {out_path}: {e}")
                if memory_optimize:
                    del all_imgs
                    gc.collect()

    # Tạo danh sách ảnh theo thứ tự trang để OCR
    if pages_to_ocr is not None:
        # Chỉ OCR các trang được chỉ định (và có sẵn ảnh)
        ordered_indices = sorted([idx for idx in pages_to_ocr if idx in index_to_image_path])
    elif total_pages is None:
        # Không biết tổng trang: dùng thứ tự theo index hiện có
        ordered_indices = sorted(index_to_image_path.keys())
    else:
        ordered_indices = list(range(1, total_pages + 1))

    # Auto-detect language/variant nếu cần (chỉ một lần cho toàn bộ PDF)
    resolved_lang = None
    raw_lang = ocr_cfg.get("lang", "vie")
    # Normalize trước để check "auto" và "chi"
    normalized_lang = _normalize_lang_code(raw_lang)
    
    # Chỉ detect Chinese variant nếu lang="CN" hoặc "chi" (không có auto-detect)
    needs_chinese_variant_detection = ("chi" in normalized_lang.lower() and 
                                       "chi_sim" not in normalized_lang and 
                                       "chi_tra" not in normalized_lang)
    
    if needs_chinese_variant_detection and ordered_indices:
        # Chinese variant detection: chỉ cần 1 trang đầu để detect giản thể/phồn thể
        first_page_idx = ordered_indices[0]
        first_page_path = index_to_image_path.get(first_page_idx)
        if first_page_path:
            try:
                logger.info(f"Đang nhận biết Chinese variant (giản thể/phồn thể) từ trang đầu (lang config: {raw_lang})...")
                with Image.open(str(first_page_path)) as sample_img:
                    resolved_lang = _resolve_language(raw_lang, ocr_cfg, sample_img=sample_img)
                logger.info(f"Đã detect Chinese variant: {resolved_lang}")
            except Exception as e:
                logger.warning(f"Không thể detect Chinese variant từ trang đầu: {e}. Dùng mặc định chi_sim.")
                resolved_lang = _resolve_language(raw_lang, ocr_cfg, sample_img=None)
        else:
            resolved_lang = _resolve_language(raw_lang, ocr_cfg, sample_img=None)
    else:
        # Không cần detect variant, chỉ normalize
        resolved_lang = _resolve_language(raw_lang, ocr_cfg, sample_img=None)
    
    texts: List[str] = []
    total = len(ordered_indices)
    logger.info(f"OCR: Tổng số trang cần xử lý: {total}")
    show_progress = bool(ocr_cfg.get("show_progress", True))
    progress_interval = float(ocr_cfg.get("progress_log_interval_seconds", 60))
    if show_progress and tqdm is not None and total > 1:
        start_ts = time.time()
        with tqdm(total=total, desc="OCR PDF", unit="trang") as pbar:
            for i, page_idx in enumerate(ordered_indices, start=1):
                p = index_to_image_path.get(page_idx)
                if p is None:
                    logger.warning(f"Thiếu ảnh cho trang {page_idx}, bỏ qua")
                    pbar.update(1)
                    continue
                try:
                    # Thử mở ảnh với LOAD_TRUNCATED_IMAGES để xử lý ảnh bị truncated
                    try:
                        with Image.open(str(p)) as img:
                            # Thử load full image với LOAD_TRUNCATED_IMAGES nếu bị truncated
                            img.load()  # Load toàn bộ image data
                            text = _image_to_text(img, ocr_cfg, lang_override=resolved_lang)
                    except Exception as load_error:
                        # Nếu vẫn lỗi, thử với LOAD_TRUNCATED_IMAGES flag
                        if "truncated" in str(load_error).lower():
                            logger.warning(f"Ảnh trang {page_idx} bị truncated, thử load với LOAD_TRUNCATED_IMAGES...")
                            with Image.open(str(p)) as img:
                                # Pillow tự động xử lý truncated images nếu có thể
                                try:
                                    # Thử verify=False để bỏ qua một số checks
                                    img.verify()
                                    img = Image.open(str(p))  # Reopen sau verify
                                    text = _image_to_text(img, ocr_cfg, lang_override=resolved_lang)
                                except Exception:
                                    # Nếu vẫn lỗi, thử render lại từ PDF
                                    logger.warning(f"Không thể load ảnh truncated trang {page_idx}, thử render lại từ PDF...")
                                    try:
                                        # Xóa file cache bị lỗi
                                        if p.exists():
                                            try:
                                                p.unlink()
                                                logger.debug(f"Đã xóa file cache bị lỗi: {p}")
                                            except Exception:
                                                pass
                                        
                                        # Render lại từ PDF (single page - dùng format tối ưu)
                                        if poppler_path and isinstance(poppler_path, str) and poppler_path.strip():
                                            imgs = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path, 
                                                                    first_page=page_idx, last_page=page_idx, thread_count=1)
                                        else:
                                            imgs = convert_from_path(pdf_path, dpi=dpi, first_page=page_idx, last_page=page_idx, thread_count=1)
                                        
                                        if imgs and len(imgs) > 0:
                                            img = imgs[0]
                                            # Lưu lại vào cache với format tối ưu
                                            try:
                                                cache_dir.mkdir(parents=True, exist_ok=True)
                                                if image_format == "jpeg":
                                                    if img.mode in ('RGBA', 'LA', 'P'):
                                                        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                                        if img.mode == 'P':
                                                            img = img.convert('RGBA')
                                                        rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                                                        img = rgb_img
                                                    img.save(str(p), format='JPEG', quality=jpeg_quality, optimize=True)
                                                else:
                                                    img.save(str(p), format='PNG', optimize=True)
                                                logger.info(f"Đã render lại và lưu cache cho trang {page_idx}")
                                            except Exception as save_err:
                                                logger.debug(f"Không thể lưu cache lại: {save_err}")
                                            
                                            # OCR lại (trước khi giải phóng memory)
                                            text = _image_to_text(img, ocr_cfg, lang_override=resolved_lang)
                                            
                                            # Giải phóng memory sau khi OCR xong
                                            if memory_optimize:
                                                del img, imgs
                                                gc.collect()
                                        else:
                                            logger.warning(f"Không thể render lại trang {page_idx} từ PDF")
                                            text = ""
                                    except Exception as render_error:
                                        logger.warning(f"Không thể render lại trang {page_idx}: {render_error}")
                                        text = ""
                        else:
                            raise load_error  # Nếu không phải truncated error, re-raise
                except Exception as e:
                    logger.warning(f"Không thể mở/OCR ảnh cho trang {page_idx} ({p}): {e}")
                    text = ""
                texts.append(text)
                elapsed = time.time() - start_ts
                avg = elapsed / i if i > 0 else 0.0
                remaining = max(total - i, 0) * avg
                pbar.set_postfix(avg_s_per_page=f"{avg:.2f}", eta=f"{remaining:.0f}s")
                pbar.update(1)
    else:
        start_ts = time.time()
        last_log = start_ts
        for i, page_idx in enumerate(ordered_indices, start=1):
            p = index_to_image_path.get(page_idx)
            if p is None:
                logger.warning(f"Thiếu ảnh cho trang {page_idx}, bỏ qua")
                continue
            try:
                # Thử mở ảnh với xử lý truncated images
                try:
                    with Image.open(str(p)) as img:
                        img.load()  # Load toàn bộ image data
                        texts.append(_image_to_text(img, ocr_cfg, lang_override=resolved_lang))
                except Exception as load_error:
                    # Nếu bị truncated, thử các cách khắc phục
                    if "truncated" in str(load_error).lower():
                        logger.warning(f"Ảnh trang {page_idx} bị truncated, thử load với LOAD_TRUNCATED_IMAGES...")
                        try:
                            with Image.open(str(p)) as img:
                                img.verify()
                                img = Image.open(str(p))  # Reopen sau verify
                                texts.append(_image_to_text(img, ocr_cfg, lang_override=resolved_lang))
                        except Exception:
                            # Thử render lại từ PDF
                            logger.warning(f"Không thể load ảnh truncated trang {page_idx}, thử render lại từ PDF...")
                            try:
                                # Xóa file cache bị lỗi
                                if p.exists():
                                    try:
                                        p.unlink()
                                    except Exception:
                                        pass
                                
                                # Render lại từ PDF (single page - dùng format tối ưu)
                                if poppler_path and isinstance(poppler_path, str) and poppler_path.strip():
                                    imgs = convert_from_path(pdf_path, dpi=dpi, poppler_path=poppler_path, 
                                                            first_page=page_idx, last_page=page_idx, thread_count=1)
                                else:
                                    imgs = convert_from_path(pdf_path, dpi=dpi, first_page=page_idx, last_page=page_idx, thread_count=1)
                                
                                if imgs and len(imgs) > 0:
                                    img = imgs[0]
                                    # Lưu lại vào cache với format tối ưu
                                    try:
                                        cache_dir.mkdir(parents=True, exist_ok=True)
                                        if image_format == "jpeg":
                                            if img.mode in ('RGBA', 'LA', 'P'):
                                                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                                                if img.mode == 'P':
                                                    img = img.convert('RGBA')
                                                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                                                img = rgb_img
                                            img.save(str(p), format='JPEG', quality=jpeg_quality, optimize=True)
                                        else:
                                            img.save(str(p), format='PNG', optimize=True)
                                    except Exception:
                                        pass
                                
                                    # OCR lại (trước khi giải phóng memory)
                                    texts.append(_image_to_text(img, ocr_cfg, lang_override=resolved_lang))
                                    
                                    # Giải phóng memory sau khi OCR xong
                                    if memory_optimize:
                                        del img, imgs
                                        gc.collect()
                                else:
                                    logger.warning(f"Không thể render lại trang {page_idx} từ PDF")
                                    texts.append("")
                            except Exception as render_error:
                                logger.warning(f"Không thể render lại trang {page_idx}: {render_error}")
                                texts.append("")
                    else:
                        raise load_error
            except Exception as e:
                logger.warning(f"Không thể mở/OCR ảnh cho trang {page_idx} ({p}): {e}")
                texts.append("")
            now = time.time()
            if now - last_log >= max(5.0, progress_interval):  # báo cáo định kỳ
                elapsed = now - start_ts
                avg = elapsed / i if i > 0 else 0.0
                remaining = max(total - i, 0) * avg
                logger.info(f"OCR: Trang {i}/{total} • TB {avg:.2f}s/trang • ETA ~{remaining:.0f}s")
                last_log = now
        elapsed = time.time() - start_ts
        avg = elapsed / total if total > 0 else 0.0
        logger.info(f"OCR: Hoàn tất {total} trang • TB {avg:.2f}s/trang")
    # Trả về số trang đã thực sự OCR (không phải total_pages)
    pages_processed = len(ordered_indices)
    return ("\n\n".join(texts), pages_processed)

def ocr_file(input_path: str, config_path: str = "config/config.yaml", pages: Optional[List[int]] = None, output_path: Optional[str] = None, skip_steps: Optional[dict] = None, process_mode: str = "process") -> str:
    """
    Extract text từ file PDF hoặc ảnh.
    Tự động detect PDF scan vs text-based để tối ưu.
    
    Args:
        output_path: Đường dẫn file output (để tạo tên file tạm thời)
        skip_steps: Dict với keys 'ocr', 'cleanup', 'spell_check' để skip các bước đã hoàn tất
        process_mode: "fast" = convert trực tiếp PDF→DOCX (chỉ cho text-based), "process" = extract→cleanup→spell check
    """
    _ensure_logger_config()
    pipeline_start_time = time.time()
    total_pages_processed = 0
    cleanup_stats = {"success": 0, "failed": 0}
    spell_check_stats = {"success": 0, "failed": 0}
    extracted_tables = {}
    
    if skip_steps is None:
        skip_steps = {}
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(input_path)
    
    ocr_cfg = _detect_bundled_binaries(load_ocr_config(config_path))
    # Apply environment overrides for tables
    try:
        tables_override = os.environ.get("OCR_TABLES_RECONSTRUCT")
        if tables_override is not None:
            ocr_cfg.setdefault("tables", {})
            ocr_cfg["tables"]["reconstruct"] = tables_override == "1"
    except Exception:
        pass
    _ensure_dependencies(ocr_cfg)
    
    ext = os.path.splitext(input_path)[-1].lower()
    
    # Xử lý PDF
    if ext == ".pdf":
        auto_detect = ocr_cfg.get("auto_detect_pdf_type", True)
        
        if auto_detect:
            logger.info(f"Đang phát hiện loại PDF: {input_path}")
            pdf_type = detect_pdf_type(input_path, ocr_cfg)
            logger.info(f"PDF type: {pdf_type}")
            
            if pdf_type == "text":
                # Mode "fast": Convert trực tiếp PDF → DOCX (chỉ khi output_path là DOCX)
                if process_mode == "fast" and output_path and output_path.endswith(".docx"):
                    logger.info("📄 PDF text-based + Mode 'fast' → Convert trực tiếp PDF → DOCX...")
                    try:
                        # Đảm bảo dependencies đã được load
                        _ensure_dependencies(ocr_cfg)
                        convert_pdf_to_docx(input_path, output_path, pages)
                        
                        # Post-fix: loại bỏ tab thừa đầu dòng do soft-wrap
                        try:
                            _fix_docx_leading_tabs_and_soft_wraps(output_path)
                        except Exception:
                            pass
                        
                        # Return dict với text rỗng (đã convert trực tiếp)
                        return {
                            "text": "",
                            "cleanup_failed": 0,
                            "cleanup_failed_indices": [],
                            "cleanup_original_chunks": [],
                            "cleanup_all_chunks": [],
                            "spell_check_failed": 0,
                            "spell_check_failed_indices": [],
                            "spell_check_original_chunks": [],
                            "spell_check_all_chunks": [],
                            "ocr_cfg": ocr_cfg,
                            "direct_converted": True,  # Flag để web app biết đã convert trực tiếp
                        }
                    except Exception as e:
                        logger.warning(f"Convert trực tiếp thất bại: {e}, fallback về mode 'process'")
                        import traceback
                        logger.debug(traceback.format_exc())
                        # Fallback về mode process
                        process_mode = "process"
                
                # Mode "process": Extract text → cleanup → spell check
                logger.info("PDF có text layer → Extract text trực tiếp (nhanh)")
                text = extract_text_from_pdf(input_path, ocr_cfg, pages)
                # Đếm số trang đã xử lý
                if pages:
                    # Validate và đếm số trang hợp lệ
                    try:
                        if pdfplumber is not None:
                            with pdfplumber.open(input_path) as pdf:
                                total = len(pdf.pages)
                                valid_pages = [p for p in pages if 1 <= p <= total]
                                total_pages_processed = len(valid_pages)
                        elif PyPDF2 is not None:
                            with open(input_path, 'rb') as f:
                                reader = PyPDF2.PdfReader(f)
                                total = len(reader.pages)
                                valid_pages = [p for p in pages if 1 <= p <= total]
                                total_pages_processed = len(valid_pages)
                        else:
                            total_pages_processed = len(pages)  # Fallback
                    except Exception:
                        total_pages_processed = len(pages)  # Fallback
                else:
                    try:
                        if pdfplumber is not None:
                            with pdfplumber.open(input_path) as pdf:
                                total_pages_processed = len(pdf.pages)
                        elif PyPDF2 is not None:
                            with open(input_path, 'rb') as f:
                                reader = PyPDF2.PdfReader(f)
                                total_pages_processed = len(reader.pages)
                    except Exception:
                        total_pages_processed = 0
            else:
                logger.info("📷 PDF scan → Sử dụng OCR")
                text, total_pages_processed = ocr_pdf(input_path, config_path, pages)
                # After OCR, try table reconstruction if enabled
                try:
                    tables_cfg = ocr_cfg.get("tables", {})
                    if tables_cfg.get("reconstruct", False) and output_path:
                        logger.info("🗂️  Bắt đầu extract bảng từ PDF scan...")
                        
                        # Strategy: Ưu tiên unstructured.io (95-98% chính xác)
                        # Fallback về ocrmypdf + pdfplumber, cuối cùng là OpenCV + pytesseract advanced
                        extracted_tables = {}
                        table_mode = tables_cfg.get("mode", "auto")
                        
                        # Strategy 1: unstructured.io (nếu có và mode cho phép)
                        if table_mode in ("auto", "unstructured"):
                            try:
                                extracted_tables = _extract_tables_with_unstructured(input_path, output_path, ocr_cfg, pages)
                                if extracted_tables:
                                    logger.info(f"✅ unstructured.io: Đã extract {len(extracted_tables)} bảng từ PDF")
                            except Exception as e:
                                logger.debug(f"unstructured.io không khả dụng hoặc thất bại: {e}")
                                if table_mode == "unstructured":
                                    # Nếu user chỉ định unstructured nhưng không có → báo lỗi
                                    logger.warning("⚠️  unstructured.io không khả dụng. Cài bằng: pip install unstructured[pdf]")
                        
                        # Strategy 2: ocrmypdf + pdfplumber (fallback nếu unstructured không có kết quả)
                        if not extracted_tables and table_mode in ("auto", "ocrmypdf_then_extract"):
                            try:
                                extracted_tables = _try_extract_tables_from_pdf_via_ocrmypdf(input_path, output_path, ocr_cfg, pages)
                                if extracted_tables:
                                    logger.info(f"✅ ocrmypdf+pdfplumber: Đã extract {len(extracted_tables)} bảng từ PDF")
                            except Exception as e:
                                logger.debug(f"ocrmypdf+pdfplumber thất bại: {e}")
                        
                        # Strategy 3: OpenCV + pytesseract advanced (fallback cuối cùng)
                        if not extracted_tables and table_mode in ("auto", "opencv_grid", "pytesseract_advanced"):
                            try:
                                # Thử dùng pytesseract advanced nếu có sklearn
                                try:
                                    from sklearn.cluster import DBSCAN
                                    # Sử dụng hàm advanced pytesseract trong _extract_tables_from_images_cv
                                    extracted_tables = _extract_tables_from_images_cv(input_path, output_path, ocr_cfg, pages)
                                    if extracted_tables:
                                        logger.info(f"✅ OpenCV+pytesseract advanced: Đã extract {len(extracted_tables)} bảng từ PDF")
                                except ImportError:
                                    # Fallback về OpenCV grid detection cũ
                                    extracted_tables = _extract_tables_from_images_cv(input_path, output_path, ocr_cfg, pages)
                                    if extracted_tables:
                                        logger.info(f"✅ OpenCV grid: Đã extract {len(extracted_tables)} bảng từ PDF")
                            except Exception as e:
                                logger.debug(f"OpenCV fallback thất bại: {e}")
                        
                        if extracted_tables:
                            logger.info(f"✅ Tổng cộng đã extract {len(extracted_tables)} bảng từ PDF")
                    else:
                        logger.debug(f"Table extraction disabled: reconstruct={tables_cfg.get('reconstruct', False)}, output_path={output_path}")
                except Exception as e:
                    logger.warning(f"⚠️  Lỗi khi extract bảng: {e}")
                    import traceback
                    logger.debug(traceback.format_exc())
        else:
            # Force OCR nếu auto_detect = false
            text, total_pages_processed = ocr_pdf(input_path, config_path, pages)
    # Xử lý ảnh
    elif ext in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
        text = ocr_image(input_path, config_path)
        total_pages_processed = 1  # Một ảnh = 1 trang
    else:
        raise ValueError(f"Unsupported input format for OCR: {ext}")
    
    # Lưu file sau bước OCR nếu chưa skip và có output_path
    if not skip_steps.get("ocr", False) and output_path:
        ocred_path = _get_intermediate_file_path(output_path, "_ocred.txt")
        try:
            with open(ocred_path, "w", encoding="utf-8") as f:
                f.write(text)
            logger.info(f"💾 Đã lưu kết quả OCR: {ocred_path}")
        except Exception as e:
            logger.warning(f"Không thể lưu file OCR: {e}")
    
    # Áp dụng AI cleanup nếu enabled
    cleanup_cfg = ocr_cfg.get("ai_cleanup", {})
    cleanup_failed = 0
    cleanup_failed_indices = []
    cleanup_original_chunks = []
    
    if cleanup_cfg.get("enabled", False) and not skip_steps.get("cleanup", False):
        result = ai_cleanup_text(text, ocr_cfg)
        if isinstance(result, tuple):
            text, cleanup_failed_indices, cleanup_original_chunks = result
            cleanup_failed = len(cleanup_failed_indices)
        else:
            text = result
        
        # Lưu file sau bước cleanup nếu có output_path
        if output_path:
            cleanup_path = _get_intermediate_file_path(output_path, "_cleanup.txt")
            try:
                with open(cleanup_path, "w", encoding="utf-8") as f:
                    f.write(text)
                logger.info(f"💾 Đã lưu kết quả Cleanup: {cleanup_path}")
            except Exception as e:
                logger.warning(f"Không thể lưu file Cleanup: {e}")
    elif skip_steps.get("cleanup", False):
        logger.info("⏭️  Bỏ qua bước Cleanup (đã có file từ phiên trước)")
    
    # Áp dụng AI spell check và paragraph restoration nếu enabled
    spell_check_cfg = ocr_cfg.get("ai_spell_check", {})
    spell_check_failed = 0
    spell_check_failed_indices = []
    spell_check_original_chunks = []
    
    if spell_check_cfg.get("enabled", False) and not skip_steps.get("spell_check", False):
        result = ai_spell_check_and_paragraph_restore(text, ocr_cfg)
        if isinstance(result, tuple):
            text, spell_check_failed_indices, spell_check_original_chunks = result
            spell_check_failed = len(spell_check_failed_indices)
        else:
            text = result
    elif skip_steps.get("spell_check", False):
        logger.info("⏭️  Bỏ qua bước Spell Check (đã có file từ phiên trước)")
    
    # Log tổng kết
    total_time = time.time() - pipeline_start_time
    hours = int(total_time // 3600)
    minutes = int((total_time % 3600) // 60)
    seconds = int(total_time % 60)
    time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
    
    logger.info("=" * 80)
    logger.info("📊 TỔNG KẾT OCR PIPELINE")
    logger.info(f"⏱️  Tổng thời gian: {time_str} ({total_time:.2f} giây)")
    logger.info(f"📄 Số trang đã OCR: {total_pages_processed}")
    if cleanup_cfg.get("enabled", False):
        if cleanup_failed > 0:
            logger.info(f"🧹 AI Cleanup: {cleanup_failed} chunks failed (đã lưu nội dung gốc)")
        else:
            logger.info(f"🧹 AI Cleanup: Hoàn tất không có lỗi")
    if spell_check_cfg.get("enabled", False):
        if spell_check_failed > 0:
            logger.info(f"✅ AI Spell Check: {spell_check_failed} chunks failed (đã lưu nội dung gốc)")
        else:
            logger.info(f"✅ AI Spell Check: Hoàn tất không có lỗi")
    logger.info("=" * 80)
    
    # Lưu lại cấu trúc chunks để có thể merge lại sau retry
    cleanup_all_chunks = cleanup_original_chunks if cleanup_original_chunks else []
    spell_check_all_chunks = spell_check_original_chunks if spell_check_original_chunks else []
    
    # Xử lý merge hàng bị cắt trong bảng sau spell check (nếu có)
    if extracted_tables and spell_check_cfg.get("enabled", False):
        logger.info("🔧 Đang merge các hàng bị cắt trong bảng...")
        extracted_tables = _merge_split_table_rows(extracted_tables, ocr_cfg)
    
    # Trả về text và thông tin failures để menu xử lý
    return {
        "text": text,
        "cleanup_failed": cleanup_failed,
        "cleanup_failed_indices": cleanup_failed_indices,
        "cleanup_original_chunks": cleanup_original_chunks,
        "cleanup_all_chunks": cleanup_all_chunks,  # Tất cả chunks (để merge lại)
        "spell_check_failed": spell_check_failed,
        "spell_check_failed_indices": spell_check_failed_indices,
        "spell_check_original_chunks": spell_check_original_chunks,
        "spell_check_all_chunks": spell_check_all_chunks,  # Tất cả chunks (để merge lại)
        "extracted_tables": extracted_tables,  # Bảng đã extract và xử lý
        "ocr_cfg": ocr_cfg
    }

