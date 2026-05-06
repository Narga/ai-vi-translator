from . import config

def _normalize_lang_code(lang: str) -> str:
    """
    Chuyển đổi mã ngôn ngữ từ format ngắn (VN, EN, CN) sang Tesseract format (vie, eng, chi).
    Hỗ trợ backward compatibility với format cũ.
    
    Args:
        lang: Language string có thể là "VN", "EN", "CN", "auto", hoặc format cũ "vie", "eng", "chi"
    
    Returns:
        Tesseract language code hoặc "auto"
    """
    if not lang:
        return "vie"
    
    lang = lang.strip().upper()
    
    # Mapping từ format ngắn sang Tesseract
    lang_map = {
        "VN": "vie",
        "EN": "eng", 
        "CN": "chi",
        "VIE": "vie",  # Backward compatibility
        "ENG": "eng",  # Backward compatibility
        "CHI": "chi",  # Backward compatibility
        "AUTO": "auto"
    }
    
    # Xử lý kết hợp ngôn ngữ (VD: "VN+EN" hoặc "vie+eng")
    if "+" in lang:
        parts = lang.split("+")
        normalized_parts = []
        for part in parts:
            part = part.strip().upper()
            normalized = lang_map.get(part, part.lower())  # Fallback về lowercase nếu không map được
            normalized_parts.append(normalized)
        return "+".join(normalized_parts)
    
    # Xử lý single language
    return lang_map.get(lang, lang.lower())  # Fallback về lowercase nếu không map được


def _get_exif_rotation_degrees(img: "config.Image.Image") -> int:
    """Đọc EXIF Orientation nếu có và trả về góc xoay cần thiết (0/90/180/270)."""
    try:
        if hasattr(img, "_getexif") and callable(getattr(img, "_getexif")):
            exif = img._getexif() or {}
            orientation = exif.get(274)  # EXIF Orientation tag
            mapping = {3: 180, 6: 270, 8: 90}  # cần xoay để hiển thị đúng
            return mapping.get(orientation, 0)
    except Exception:
        pass
    return 0


def _detect_orientation_degrees_osd(img: "config.Image.Image") -> int:
    """Dùng Tesseract OSD để phát hiện góc xoay. Trả về 0/90/180/270."""
    try:
        if config.pytesseract is None:
            return 0
        osd = config.pytesseract.image_to_osd(img)
        # OSD text chứa dòng: "Rotate: 90"
        for line in str(osd).splitlines():
            line = line.strip()
            if line.lower().startswith("rotate:"):
                val = line.split(":", 1)[1].strip()
                deg = int("".join(ch for ch in val if ch.isdigit()))
                if deg in (0, 90, 180, 270):
                    return deg
                break
    except Exception:
        pass
    return 0


def _auto_rotate_image(img: "config.Image.Image", ocr_cfg: dict) -> "config.Image.Image":
    """Tự động xoay ảnh dựa trên EXIF và OSD. Ưu tiên EXIF, sau đó OSD nếu cần.
    - ocr.auto_rotate_exif: bật/tắt xoay theo EXIF (default True)
    - ocr.auto_rotate_osd: bật/tắt xoay theo OSD (default True)
    """
    if not isinstance(img, config.Image.Image):
        return img
    auto_exif = bool(ocr_cfg.get("auto_rotate_exif", True))
    auto_osd = bool(ocr_cfg.get("auto_rotate_osd", True))

    rotated = False
    try:
        if auto_exif:
            deg = _get_exif_rotation_degrees(img)
            if deg in (90, 180, 270):
                # PIL.rotate: xoay ngược chiều kim đồng hồ; EXIF deg là cần xoay thuận để đúng hướng
                img = img.rotate(360 - deg, expand=True)
                rotated = True
        if auto_osd:
            deg_osd = _detect_orientation_degrees_osd(img)
            # Nếu OSD báo phải xoay, thực hiện xoay để chữ nằm thẳng đứng
            if deg_osd in (90, 180, 270):
                img = img.rotate(360 - deg_osd, expand=True)
                rotated = True
    except Exception:
        return img
    return img


def _is_cjk_character(char: str) -> bool:
    """
    Kiểm tra xem ký tự có phải là CJK (Chinese, Japanese, Korean) không.
    Dựa trên Unicode ranges cho CJK.
    """
    if not char:
        return False
    code = ord(char)
    # CJK Unified Ideographs: U+4E00–U+9FFF
    # CJK Extension A: U+3400–U+4DBF
    # CJK Extension B: U+20000–U+2A6DF
    # CJK Compatibility: U+F900–U+FAFF
    return (
        0x4E00 <= code <= 0x9FFF or  # CJK Unified Ideographs
        0x3400 <= code <= 0x4DBF or  # CJK Extension A
        0xF900 <= code <= 0xFAFF     # CJK Compatibility
    )


def _count_cjk_characters(text: str) -> int:
    """Đếm số ký tự CJK trong text."""
    return sum(1 for char in text if _is_cjk_character(char))


# DEPRECATED FUNCTIONS REMOVED:
# - _detect_language_from_image (removed - không còn được sử dụng)
# - _detect_language_from_multiple_pages (removed - không còn được sử dụng)


def _detect_chinese_variant(img: "config.Image.Image", ocr_cfg: dict) -> str:
    """
    Tự động nhận biết tiếng Trung giản thể hay phồn thể.
    Returns: "chi_sim" hoặc "chi_tra"
    """
    psm = int(ocr_cfg.get("psm", 3) or 3)
    config = f"--psm {psm}"
    
    try:
        # OCR với cả 2 ngôn ngữ và so sánh confidence
        # Simplified Chinese
        data_sim = config.pytesseract.image_to_data(img, lang="chi_sim", config=config, output_type=config.pytesseract.Output.DICT)
        confidences_sim = [int(conf) for conf in data_sim['conf'] if int(conf) > 0]
        avg_conf_sim = sum(confidences_sim) / len(confidences_sim) if confidences_sim else 0
        # Đếm số ký tự được nhận dạng (có confidence > 0)
        char_count_sim = sum(1 for i, text_item in enumerate(data_sim['text']) if text_item.strip() and int(data_sim['conf'][i]) > 0)
        
        # Traditional Chinese
        data_tra = config.pytesseract.image_to_data(img, lang="chi_tra", config=config, output_type=config.pytesseract.Output.DICT)
        confidences_tra = [int(conf) for conf in data_tra['conf'] if int(conf) > 0]
        avg_conf_tra = sum(confidences_tra) / len(confidences_tra) if confidences_tra else 0
        # Đếm số ký tự được nhận dạng (có confidence > 0)
        char_count_tra = sum(1 for i, text_item in enumerate(data_tra['text']) if text_item.strip() and int(data_tra['conf'][i]) > 0)
        
        # Quyết định dựa trên confidence và số ký tự
        # Ưu tiên confidence, nếu gần bằng nhau thì ưu tiên số ký tự nhiều hơn
        score_sim = avg_conf_sim * 0.7 + (char_count_sim / max(char_count_sim + char_count_tra, 1)) * 30 * 0.3
        score_tra = avg_conf_tra * 0.7 + (char_count_tra / max(char_count_sim + char_count_tra, 1)) * 30 * 0.3
        
        if score_sim > score_tra:
            detected = "chi_sim"
            logger.debug(f"Chinese variant detected: Simplified (conf: {avg_conf_sim:.1f}, chars: {char_count_sim})")
        else:
            detected = "chi_tra"
            logger.debug(f"Chinese variant detected: Traditional (conf: {avg_conf_tra:.1f}, chars: {char_count_tra})")
        
        return detected
    except Exception as e:
        # Fallback: mặc định là Simplified (phổ biến hơn)
        logger.warning(f"Không thể detect Chinese variant: {e}. Mặc định dùng chi_sim")
        return "chi_sim"


def _resolve_language(lang: str, ocr_cfg: dict, sample_img: Optional["config.Image.Image"] = None) -> str:
    """
    Resolve language code, chỉ hỗ trợ Chinese variant detection (giản thể/phồn thể).
    Auto-detect ngôn ngữ đã được loại bỏ do kém hiệu quả.
    
    Args:
        lang: Language string từ config (có thể là "VN", "EN", "CN", "VN+EN", "chi", "chi_sim", "chi_tra", etc.)
        ocr_cfg: OCR config
        sample_img: Optional sample image để detect Chinese variant (chỉ khi lang="CN" hoặc "chi")
    
    Returns:
        Resolved language string cho Tesseract (e.g., "chi_sim", "chi_tra", "vie+eng")
    """
    if not lang:
        return "vie"
    
    # Normalize: VN/EN/CN → vie/eng/chi
    lang = _normalize_lang_code(lang)
    
    # Loại bỏ auto-detect: nếu config là "auto", cảnh báo và fallback về "vie"
    if lang == "auto" or lang.startswith("auto+"):
        logger.warning(f"Auto-detect ngôn ngữ đã bị loại bỏ do kém hiệu quả. "
                      f"Config '{lang}' không được hỗ trợ. Vui lòng chỉ định rõ ngôn ngữ (VN/EN/CN). "
                      f"Fallback về 'vie'.")
        lang = "vie"
    
    # Chỉ hỗ trợ detect Chinese variant (giản thể/phồn thể) khi lang="CN" hoặc "chi"
    # Kiểm tra nếu có "chi" (cần detect variant: Simplified vs Traditional)
    if "chi" in lang.lower() and "chi_sim" not in lang and "chi_tra" not in lang:
        # Cần detect variant
        if sample_img is not None:
            detected_variant = _detect_chinese_variant(sample_img, ocr_cfg)
            # Replace "chi" bằng variant detected
            lang = lang.replace("chi", detected_variant).replace("Chi", detected_variant)
            # Clean up duplicate "+" nếu có
            lang = lang.replace(f"{detected_variant}+{detected_variant}", detected_variant)
            logger.info(f"Auto-detected Chinese variant: {detected_variant} → Language: {lang}")
        else:
            # Không có sample image → mặc định Simplified
            detected_variant = "chi_sim"
            lang = lang.replace("chi", detected_variant).replace("Chi", detected_variant)
            logger.info(f"No sample image for detection, defaulting to chi_sim → Language: {lang}")
    
    return lang


def _image_to_text(img: "config.Image.Image", ocr_cfg: dict, lang_override: Optional[str] = None) -> str:
    """
    OCR một ảnh thành text.
    
    Args:
        img: PIL config.Image object
        ocr_cfg: OCR config dictionary
        lang_override: Optional resolved language string (đã detect variant nếu cần)
    """
    # Auto-rotate trước khi OCR (dựa vào EXIF và OSD của Tesseract)
    try:
        if bool(ocr_cfg.get("auto_rotate", True)):
            img = _auto_rotate_image(img, ocr_cfg)
    except Exception:
        pass

    lang = lang_override
    if lang is None:
        raw_lang = ocr_cfg.get("lang", "vie+eng")
        lang = _resolve_language(raw_lang, ocr_cfg, sample_img=img)
    
    psm = int(ocr_cfg.get("psm", 3) or 3)
    config = f"--psm {psm}"
    return config.pytesseract.image_to_string(img, lang=lang, config=config)
