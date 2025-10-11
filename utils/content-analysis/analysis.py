# utils/content-analysis/analysis.py - v1.1.1
# Tác giả: Narga
# Mô tả:
#   - Tiện ích độc lập phân tích nội dung: gửi 3 prompt (style/glossary/relations)
#     cùng nguồn tới Gemini để sinh:
#       * style_profile.json (tiếng Việt)
#       * glossary.csv (tiếng Việt; giữ đúng schema CSV)
#       * character_relations.csv (tiếng Việt; giữ đúng schema CSV)
#   - Đọc cấu hình từ file config.ini đặt NGAY TRONG cùng thư mục với analysis.py.
#   - Dùng chung API.txt bằng cơ chế tìm ngược thư mục.
#   - Hỗ trợ “AI file cache” (Gemini File API) để tải nguồn lớn 1 lần và tái sử dụng.
#   - Ghim API key theo fileUri đã upload để tránh lỗi 403 khi quay vòng key.
#   - Hỗ trợ SOURCE_PATH là đường dẫn tới tệp hoặc URL http(s); hỗ trợ tên tệp có khoảng trống/ngoặc kép.
#
# Nâng cấp v1.1.1:
#   1) Chuẩn hóa giá trị cấu hình có khoảng trống/ngoặc kép (SOURCE_PATH).
#   2) File API per-key cache: lưu fileUri theo fingerprint của API key; ghim key khi gọi có fileUri.
#   3) Nếu key ghim hết quota → tự động re-upload bằng key kế tiếp rồi gọi lại.
#   4) Hỗ trợ SOURCE_PATH là URL http(s): tải về tạm trước khi upload.
#
# Cấu hình (utils/content-analysis/config.ini ví dụ):
#   [MODEL]
#   MODEL = gemini-2.0-flash
#
#   [PROCESSING]
#   TEMPERATURE = 0.75
#   REQUEST_DELAY = 2
#
#   [CONTENT_ANALYSIS]
#   PROMPTS_DIR = ./utils/content-analysis/prompts/
#   SOURCE_PATH = "./utils/content-analysis/source with space.txt"  ; đường dẫn có khoảng trống
#   OUTPUT_DIR  = ./utils/content-analysis/output/
#   ENABLE_AI_FILE_CACHE = true
#
# Chạy:
#   python utils/content-analysis/analysis.py

import os
import sys
import time
import json
import logging
import configparser
import hashlib
from pathlib import Path
from typing import Tuple, Optional, Dict, List, Union
from urllib.parse import urlparse
from urllib.request import urlopen, Request

try:
    import google.generativeai as genai  # Thư viện Gemini chính thức
except Exception as e:
    raise RuntimeError("Không thể import google.generativeai. Hãy cài đặt theo requirements.") from e

# ------------------------------------------------------------
# TÊN PROMPT & TỆP KẾT QUẢ
# ------------------------------------------------------------
STYLE_PROMPT_FILE = "1_prompt_style_analysis.txt"          # → style_profile.json
GLOSSARY_PROMPT_FILE = "2_prompt_glossary_extraction.txt"  # → glossary.csv
RELATIONS_PROMPT_FILE = "3_prompt_character_relations.txt" # → character_relations.csv

STYLE_OUTPUT_FILE = "style_profile.json"
GLOSSARY_OUTPUT_FILE = "glossary.csv"
RELATIONS_OUTPUT_FILE = "character_relations.csv"

AI_CACHE_INDEX = "ai_cache_index.json"  # map {file_hash: { "uploads":[{"fp":..., "uri":...}], "mtime":..., "size":... }}

# ------------------------------------------------------------
# TIỀN TỐ CHỈ DẪN: ÉP TIẾNG VIỆT & ĐỘ BAO PHỦ
# ------------------------------------------------------------
def build_instruction_prefix(task_name: str) -> str:
    return (
        f"[CHỈ DẪN CHUNG CHO NHIỆM VỤ {task_name}]\n"
        "- Luôn trả lời HOÀN TOÀN bằng tiếng Việt, ngoại trừ tên riêng và Hán tự nếu schema yêu cầu giữ nguyên.\n"
        "- TUÂN THỦ tuyệt đối định dạng đầu ra được mô tả trong prompt (CSV/JSON), không thêm thừa dòng/khóa.\n"
        "- Trích xuất ĐẦY ĐỦ, không bỏ sót, bao quát toàn bộ nguồn văn bản; ưu tiên độ chính xác và nhất quán thuật ngữ.\n"
        "- Với CSV: GIỮ NGUYÊN header đúng như prompt, nhưng tất cả giá trị nội dung phải là tiếng Việt.\n"
        "- Với JSON: GIỮ NGUYÊN tên khóa như prompt, mọi nội dung chuỗi phải là tiếng Việt.\n"
        "- Nếu thông tin thiếu trong nguồn, để trống trường đó (không tự bịa).\n"
        "- Không trả lời giải thích ngoài nội dung dữ liệu yêu cầu.\n"
    )

# ------------------------------------------------------------
# TIỆN ÍCH CẤU HÌNH & ĐƯỜNG DẪN
# ------------------------------------------------------------
def _strip_quotes(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = value.strip()
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1].strip()
    return v

def load_local_config() -> Tuple[configparser.ConfigParser, Dict[str, str], Dict[str, str]]:
    """
    Đọc file config.ini cạnh analysis.py.
    Trả về:
        parser,
        paths = { "prompts_dir": abs, "output_dir": abs, "source_path": abs_or_url_string },
        options = { "enable_ai_file_cache": "true"/"false" }
    """
    here = Path(__file__).parent.resolve()
    config_path = here / "config.ini"
    if not config_path.exists():
        raise FileNotFoundError(f"Thiếu file cấu hình: {config_path}")

    parser = configparser.ConfigParser()
    with open(config_path, "r", encoding="utf-8") as f:
        parser.read_file(f)

    default_prompts_dir = str((here / "prompts").resolve())
    default_output_dir = str((here / "output").resolve())

    prompts_dir_val = _strip_quotes(parser.get("CONTENT_ANALYSIS", "PROMPTS_DIR", fallback=default_prompts_dir))
    output_dir_val = _strip_quotes(parser.get("CONTENT_ANALYSIS", "OUTPUT_DIR", fallback=default_output_dir))
    source_path_val = _strip_quotes(parser.get("CONTENT_ANALYSIS", "SOURCE_PATH", fallback=None))
    if not source_path_val:
        source_path_val = _strip_quotes(parser.get("CONTENT_ANALYSIS", "SOURCE_DIR", fallback=None))
    if not source_path_val:
        # fallback cuối cùng
        candidate = here / "source-cn.txt"
        if candidate.exists():
            source_path_val = str(candidate)
        else:
            raise FileNotFoundError(
                "Không tìm thấy cấu hình nguồn. Hãy đặt [CONTENT_ANALYSIS].SOURCE_PATH "
                "trỏ TỚI TỆP nguồn (bao gồm cả tên file)."
            )

    paths = {
        "prompts_dir": str(Path(prompts_dir_val).resolve()) if not urlparse(prompts_dir_val).scheme else prompts_dir_val,
        "output_dir": str(Path(output_dir_val).resolve()),
        # source_path có thể là file path hoặc URL http(s)
        "source_path": source_path_val if urlparse(source_path_val).scheme else str(Path(source_path_val).resolve())
    }
    Path(paths["output_dir"]).mkdir(parents=True, exist_ok=True)

    options = {
        "enable_ai_file_cache": parser.get("CONTENT_ANALYSIS", "ENABLE_AI_FILE_CACHE", fallback="true").strip().lower()
    }
    return parser, paths, options

# ------------------------------------------------------------
# API.TXT (DÙNG CHUNG)
# ------------------------------------------------------------
def find_file_upwards(filename: str, start_from: Path, max_levels: int = 6) -> Optional[Path]:
    current = start_from.resolve()
    for _ in range(max_levels + 1):
        candidate = current / filename
        if candidate.exists():
            return candidate
        current = current.parent
    return None

def load_api_keys() -> List[str]:
    here = Path(__file__).parent
    api_path = find_file_upwards("API.txt", here, max_levels=6)
    if api_path is None:
        local_candidate = here / "API.txt"
        if local_candidate.exists():
            api_path = local_candidate
    if api_path is None:
        raise FileNotFoundError("Không tìm thấy 'API.txt' ở thư mục gốc hoặc cạnh analysis.py.")

    keys: List[str] = []
    with open(api_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            keys.append(line)
    if not keys:
        raise ValueError("API.txt không chứa API key hợp lệ.")
    return keys

# ------------------------------------------------------------
# TẢI NGUỒN QUA URL (HỖ TRỢ GOOGLE DRIVE LINK DẠNG TẢI TRỰC TIẾP)
# ------------------------------------------------------------
def download_source_if_url(source_path: str, work_dir: Path) -> Path:
    """
    Nếu SOURCE_PATH là URL http(s), tải về tạm vào work_dir và trả về Path tệp đã tải.
    Lưu ý:
      - Link Google Drive cần là dạng "tải trực tiếp" công khai; các link yêu cầu đăng nhập/confirm sẽ thất bại.
    """
    parsed = urlparse(source_path)
    if parsed.scheme not in ("http", "https"):
        return Path(source_path)

    # Tải về với tên dựa trên hash của URL để tránh va chạm
    url_hash = hashlib.md5(source_path.encode("utf-8")).hexdigest()[:12]
    filename = parsed.path.split("/")[-1] or f"downloaded_{url_hash}.txt"
    local_path = work_dir / f"{url_hash}_{filename}"
    if local_path.exists():
        return local_path

    logging.info(f"Tải nguồn từ URL: {source_path}")
    req = Request(source_path, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as resp, open(local_path, "wb") as out:
        out.write(resp.read())
    logging.info(f"Đã lưu nguồn tạm: {local_path}")
    return local_path

# ------------------------------------------------------------
# AI FILE CACHE (GEMINI FILE API) VỚI GHIM KEY
# ------------------------------------------------------------
def key_fingerprint(api_key: str) -> str:
    """Tạo fingerprint an toàn từ API key (không lộ key): SHA1 rút gọn 12 hex."""
    return hashlib.sha1(api_key.encode("utf-8")).hexdigest()[:12]

def compute_file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def load_ai_cache_index(dir_of_script: Path) -> Dict[str, dict]:
    index_path = dir_of_script / AI_CACHE_INDEX
    if not index_path.exists():
        return {}
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_ai_cache_index(dir_of_script: Path, index: Dict[str, dict]) -> None:
    index_path = dir_of_script / AI_CACHE_INDEX
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")

def find_uploaded_uri_for_fp(index: Dict[str, dict], fhash: str, fp: str) -> Optional[str]:
    rec = index.get(fhash)
    if not rec:
        return None
    for u in rec.get("uploads", []):
        if u.get("fp") == fp:
            return u.get("uri")
    return None

def register_uploaded_uri(index: Dict[str, dict], fhash: str, fp: str, uri: str, src_stat) -> None:
    rec = index.get(fhash, {})
    uploads = rec.get("uploads", [])
    # thay hoặc thêm entry cho fp
    found = False
    for u in uploads:
        if u.get("fp") == fp:
            u["uri"] = uri
            found = True
            break
    if not found:
        uploads.append({"fp": fp, "uri": uri})
    rec["uploads"] = uploads
    rec["mtime"] = int(src_stat.st_mtime)
    rec["size"] = src_stat.st_size
    index[fhash] = rec

def upload_with_specific_key(api_key: str, source_path: Path, request_delay: float) -> Optional[str]:
    try:
        if request_delay > 0:
            time.sleep(request_delay)
        genai.configure(api_key=api_key)
        uploaded = genai.upload_file(path=str(source_path))
        file_uri = getattr(uploaded, "uri", None) or getattr(uploaded, "file_uri", None)
        if not file_uri:
            raise RuntimeError("Upload trả về không có file_uri.")
        return file_uri
    except Exception as e:
        logging.warning(f"Upload bằng key fp={key_fingerprint(api_key)} thất bại: {e}")
        return None

def ensure_ai_uploaded_file_for_any_key(
    api_keys: List[str],
    source_path: Path,
    request_delay: float
) -> Tuple[Optional[str], Optional[str]]:
    """
    Bảo đảm có fileUri cho ít nhất 1 key trong danh sách:
      - Ưu tiên dùng lại upload có sẵn (bất kỳ key nào trong api_keys).
      - Nếu chưa có, thử upload bằng key đầu tiên (rồi lần lượt các key sau).
    Trả về: (file_uri, key_fp_used)
    """
    here = Path(__file__).parent.resolve()
    index = load_ai_cache_index(here)
    fhash = compute_file_hash(source_path)

    # 1) Tìm upload sẵn có cho bất kỳ key trong danh sách
    for k in api_keys:
        fp = key_fingerprint(k)
        uri = find_uploaded_uri_for_fp(index, fhash, fp)
        if uri:
            return uri, fp

    # 2) Upload lần đầu với các key
    last_err = None
    for k in api_keys:
        uri = upload_with_specific_key(k, source_path, request_delay)
        if uri:
            # lưu index
            stat = source_path.stat()
            register_uploaded_uri(index, fhash, key_fingerprint(k), uri, stat)
            save_ai_cache_index(here, index)
            return uri, key_fingerprint(k)
        else:
            last_err = "upload_failed"

    logging.error("Không thể upload nguồn bằng bất kỳ key nào.")
    return None, None

# ------------------------------------------------------------
# GỌI GEMINI (CÓ/NHỎN GHIM KEY)
# ------------------------------------------------------------
def call_gemini_with_key(
    content_payload: Union[str, list],
    model_name: str,
    temperature: float,
    api_key: str,
    request_delay: float = 0.0,
    max_attempts: int = 2
) -> Tuple[Optional[str], Optional[str]]:
    """
    Gọi Gemini bằng MỘT key (ghim key):
      - Trả về (result_text, error_message); error_message = None nếu thành công.
    """
    err_msg = None
    for attempt in range(1, max_attempts + 1):
        try:
            if request_delay > 0:
                time.sleep(request_delay)
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel(model_name)
            generation_config = genai.types.GenerationConfig(temperature=float(temperature))
            resp = model.generate_content(content_payload, generation_config=generation_config)
            if not resp or not getattr(resp, "text", None):
                raise RuntimeError("Phản hồi rỗng hoặc thiếu 'text'.")
            return resp.text.strip(), None
        except Exception as e:
            err_msg = str(e)
            logging.warning(f"[Pinned key fp={key_fingerprint(api_key)}] Lỗi '{err_msg}' (thử {attempt}/{max_attempts})...")
            time.sleep(3.0)
    return None, err_msg

def error_is_quota_or_rate(err: Optional[str]) -> bool:
    if not err:
        return False
    low = err.lower()
    return any(tok in low for tok in ("rate limit", "quota", "429", "resource_exhausted"))

# ------------------------------------------------------------
# GHÉP PROMPT + NGUỒN
# ------------------------------------------------------------
def build_request_text(prompt_text: str, instruction_prefix: str, source_text: str) -> str:
    body = f"{instruction_prefix}\n\n{prompt_text}".strip()
    token = "{SOURCE_TEXT}"
    if token.lower() in prompt_text.lower():
        if token in body:
            return body.replace(token, source_text)
        return body.lower().replace(token.lower(), source_text)
    else:
        return f"{body}\n\n===== SOURCE_CN BEGIN =====\n{source_text}\n===== SOURCE_CN END =====\n"

def build_request_parts_with_file(prompt_text: str, instruction_prefix: str, file_uri: str) -> list:
    full_prompt = (
        f"{instruction_prefix}\n\n"
        f"{prompt_text}\n\n"
        "Lưu ý: Toàn bộ nội dung nguồn đã được đính kèm dưới dạng tệp. "
        "Hãy phân tích và trích xuất DỰA TRÊN TỆP ĐÍNH KÈM, không yêu cầu tải lại nội dung."
    ).strip()
    # Theo SDK, có thể truyền dict dạng file_data.file_uri
    return [full_prompt, {"file_data": {"file_uri": file_uri}}]

# ------------------------------------------------------------
# QUY TRÌNH CHÍNH
# ------------------------------------------------------------
def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    # 1) Cấu hình
    parser, paths, options = load_local_config()
    model_name = parser.get("MODEL", "MODEL", fallback="gemini-2.0-flash")
    temperature = parser.getfloat("PROCESSING", "TEMPERATURE", fallback=0.5)
    request_delay = parser.getfloat("PROCESSING", "REQUEST_DELAY", fallback=0.0)

    prompts_dir = Path(paths["prompts_dir"])
    output_dir = Path(paths["output_dir"])
    source_path_val = paths["source_path"]

    enable_ai_file_cache = options["enable_ai_file_cache"] in ("1", "true", "yes")

    logging.info(f"MODEL = {model_name}; TEMPERATURE = {temperature}; REQUEST_DELAY = {request_delay}s")
    logging.info(f"PROMPTS_DIR = {prompts_dir}")
    logging.info(f"SOURCE_PATH = {source_path_val}")
    logging.info(f"OUTPUT_DIR = {output_dir}")
    logging.info(f"ENABLE_AI_FILE_CACHE = {enable_ai_file_cache}")

    # 2) API keys
    api_keys = load_api_keys()
    logging.info(f"Đã nạp {len(api_keys)} API key từ API.txt")

    # 3) Đọc prompts
    style_prompt_path = prompts_dir / STYLE_PROMPT_FILE
    glossary_prompt_path = prompts_dir / GLOSSARY_PROMPT_FILE
    relations_prompt_path = prompts_dir / RELATIONS_PROMPT_FILE
    for p in [style_prompt_path, glossary_prompt_path, relations_prompt_path]:
        if not p.exists():
            raise FileNotFoundError(f"Thiếu prompt: {p}")

    style_prompt = style_prompt_path.read_text(encoding="utf-8", errors="replace")
    glossary_prompt = glossary_prompt_path.read_text(encoding="utf-8", errors="replace")
    relations_prompt = relations_prompt_path.read_text(encoding="utf-8", errors="replace")

    # 4) Chuẩn bị nguồn: URL -> tải về; PATH -> dùng trực tiếp
    here = Path(__file__).parent.resolve()
    parsed = urlparse(source_path_val)
    if parsed.scheme in ("http", "https"):
        src_file_path = download_source_if_url(source_path_val, here)
    else:
        src_file_path = Path(source_path_val)
        if not src_file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy nguồn: {src_file_path}")

    # 5) Dùng File API nếu bật; nếu không thì nhúng toàn văn
    use_file_api = enable_ai_file_cache
    pinned_key: Optional[str] = None
    file_uri: Optional[str] = None

    if use_file_api:
        # Bảo đảm có ít nhất một upload và ghi nhớ key fp tương ứng
        uri, fp = ensure_ai_uploaded_file_for_any_key(api_keys, src_file_path, request_delay)
        if uri and fp:
            file_uri = uri
            # tìm chính key tương ứng fingerprint
            for k in api_keys:
                if key_fingerprint(k) == fp:
                    pinned_key = k
                    break
        if not file_uri or not pinned_key:
            logging.warning("File API không sẵn sàng (upload thất bại). Fallback nhúng trực tiếp nội dung.")
            use_file_api = False

    if not use_file_api:
        source_text = src_file_path.read_text(encoding="utf-8", errors="replace")
    else:
        source_text = ""  # không dùng khi có file_uri

    # 6) Gọi Gemini cho từng prompt, ghim key khi có fileUri
    tasks = [
        ("STYLE", style_prompt, output_dir / STYLE_OUTPUT_FILE),
        ("GLOSSARY", glossary_prompt, output_dir / GLOSSARY_OUTPUT_FILE),
        ("RELATIONS", relations_prompt, output_dir / RELATIONS_OUTPUT_FILE),
    ]

    for name, prompt_text, out_path in tasks:
        logging.info(f"➡️ Bắt đầu tác vụ {name} → {out_path.name}")
        instr = build_instruction_prefix(name)

        if use_file_api and file_uri and pinned_key:
            # Gọi bằng pinned_key; nếu quota → thử key kế tiếp: re-upload + gọi lại
            current_key_index = next((i for i, k in enumerate(api_keys) if k == pinned_key), 0)
            attempts_over_keys = 0
            result_text = None
            last_err = None

            while attempts_over_keys < len(api_keys):
                payload = build_request_parts_with_file(prompt_text, instr, file_uri)
                result_text, err = call_gemini_with_key(
                    content_payload=payload,
                    model_name=model_name,
                    temperature=temperature,
                    api_key=api_keys[current_key_index],
                    request_delay=request_delay,
                    max_attempts=2
                )
                if result_text is not None:
                    break  # thành công
                last_err = err

                if error_is_quota_or_rate(err):
                    # chuyển key: upload lại bằng key mới rồi thử tiếp
                    current_key_index = (current_key_index + 1) % len(api_keys)
                    new_key = api_keys[current_key_index]
                    new_uri = upload_with_specific_key(new_key, src_file_path, request_delay)
                    if new_uri:
                        # cập nhật cache index
                        idx = load_ai_cache_index(here)
                        stat = src_file_path.stat()
                        register_uploaded_uri(idx, compute_file_hash(src_file_path), key_fingerprint(new_key), new_uri, stat)
                        save_ai_cache_index(here, idx)
                        file_uri = new_uri
                        pinned_key = new_key
                        attempts_over_keys += 1
                        continue
                    else:
                        attempts_over_keys += 1
                        continue
                else:
                    # lỗi khác không phải quota → dừng sớm, để báo lỗi
                    break

            if result_text is None:
                raise RuntimeError(f"Tất cả key đều thất bại cho tác vụ {name}. Lỗi cuối: {last_err}")

        else:
            # Nhúng trực tiếp nội dung nguồn (không ghim key, dùng quay vòng là không cần thiết ở đây)
            payload = build_request_text(prompt_text, instr, source_text)
            # Dùng một key duy nhất theo vòng cho đơn giản
            result_text, err = call_gemini_with_key(
                content_payload=payload,
                model_name=model_name,
                temperature=temperature,
                api_key=api_keys[0],
                request_delay=request_delay,
                max_attempts=2
            )
            if result_text is None:
                # fallback thử vài key tiếp theo
                for k in api_keys[1:]:
                    result_text, err = call_gemini_with_key(
                        content_payload=payload,
                        model_name=model_name,
                        temperature=temperature,
                        api_key=k,
                        request_delay=request_delay,
                        max_attempts=2
                    )
                    if result_text is not None:
                        break
                if result_text is None:
                    raise RuntimeError(f"Thất bại khi nhúng trực tiếp cho tác vụ {name}. Lỗi cuối: {err}")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result_text, encoding="utf-8")
        logging.info(f"✅ Hoàn tất {name}: đã ghi {out_path}")

if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        logging.exception(f"Lỗi khi chạy content-analysis: {exc}")
        sys.exit(1)
