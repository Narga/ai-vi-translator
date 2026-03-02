# main.py - v4.0.0 Pure Plugin Architecture + google-genai SDK
# Tác giả: Narga
# Changelog v4.0.0:
# - Tích hợp google-genai SDK mới (thay thế google-generativeai)
# - Model mặc định: gemini-3-flash-preview
# - Emergency stop và signal handlers cho graceful shutdown

import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from tqdm import tqdm

from core.executor import TranslationExecutor
from services.config_service import ConfigService
from services.emergency_stop import setup_signal_handlers, reset_emergency_stop


def setup_logging(log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / (datetime.now().strftime("%Y-%m-%d_%H-%M") + "_translator.log")

    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logging.info(f"Log: {log_file}")


def load_api_keys(path: str = "config/API.txt") -> List[str]:
    """Load API keys từ .env hoặc file text (legacy)."""

    # Ưu tiên đọc từ .env
    try:
        from dotenv import load_dotenv

        load_dotenv()

        env_keys = []
        # Đọc từ biến môi trường GEMINI_API_KEYS (comma-separated)
        import os

        env_value = os.environ.get("GEMINI_API_KEYS", "")
        if env_value:
            env_keys = [k.strip() for k in env_value.split(",") if k.strip()]
            logging.info(f"✅ Loaded {len(env_keys)} API keys from .env")
            return env_keys
    except ImportError:
        pass  # dotenv chưa cài đặt, fallback sang file

    # Fallback: đọc từ file text
    if not Path(path).exists():
        raise FileNotFoundError(f"API keys not found: {path}")

    keys = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                keys.append(line)

    if not keys:
        raise ValueError(f"No API keys in {path}")
    return keys


def load_prompts() -> Dict[str, str]:
    prompts_dir = Path("prompts")
    prompts = {}

    for key, filename in [
        ("main", "01-main.txt"),
        ("retranslate", "02-retranslate.txt"),
        ("correction", "03-correction.txt"),
    ]:
        filepath = prompts_dir / filename
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                prompts[key] = f.read()
        else:
            prompts[key] = ""

    return prompts


def find_input_files(input_dir: Path) -> List[Path]:
    if not input_dir.exists():
        return []

    files = list(input_dir.glob("*.txt"))
    if files:
        return sorted(files)

    for subdir in input_dir.iterdir():
        if subdir.is_dir() and not subdir.name.startswith("_"):
            txt_files = sorted(subdir.glob("*.txt"))
            if txt_files:
                return txt_files
    return []


def merge_small_files(files: List[Path], min_chunk_size: int = 15000) -> List[Path]:
    """
    Gộp các file nhỏ lại để đủ kích thước tối thiểu của chunk.

    Args:
        files: Danh sách các file cần xử lý
        min_chunk_size: Kích thước tối thiểu mong muốn

    Returns:
        Danh sách file đã gộp (nếu cần) hoặc file gốc
    """
    if not files:
        return []

    # Nếu chỉ có 1 file hoặc file đầu tiên đã đủ lớn, giữ nguyên
    first_file_size = files[0].stat().st_size
    if len(files) == 1 or first_file_size >= min_chunk_size * 0.8:
        logging.info(f"File đầu tiên đủ lớn ({first_file_size:,} chars), không cần gộp")
        return files

    # Đọc tất cả files và tính tổng kích thước
    total_size = 0
    file_contents = []
    for f in files:
        try:
            with open(f, "r", encoding="utf-8") as fp:
                content = fp.read()
                file_contents.append((f, content))
                total_size += len(content)
        except Exception as e:
            logging.warning(f"Không thể đọc file {f}: {e}")

    if total_size < min_chunk_size:
        # Tổng kích thước nhỏ hơn min, gộp thành 1 file
        merged_name = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        merged_path = Path("workspace/input") / merged_name

        merged_content = "\n\n".join([content for _, content in file_contents])

        with open(merged_path, "w", encoding="utf-8") as f:
            f.write(merged_content)

        logging.info(
            f"✅ Gộp {len(files)} files thành 1 file: {merged_name} ({len(merged_content):,} chars)"
        )
        return [merged_path]

    # Nếu tổng lớn hơn min, giữ nguyên
    return files


def main():
    try:
        print("=" * 80)
        print("📚 Novel Translator v5.0.0 | Pure Executor Architecture")
        print("=" * 80)

        # Cài đặt signal handlers cho graceful shutdown
        setup_signal_handlers()
        reset_emergency_stop()  # Reset từ session trước (nếu có)

        config_service = ConfigService(Path("config"))
        setup_logging(
            Path(config_service.get("DIRECTORIES", "LOGS_DIR", fallback="workspace/logs"))
        )

        logging.info("=" * 80)
        logging.info("Starting...")

        api_keys = load_api_keys()
        logging.info(f"API keys: {len(api_keys)}")

        # Build config for Executor
        config = {
            "model_name": config_service.get("MODEL", "MODEL", fallback="gemini-3-flash-preview"),
            "qa_model": config_service.get("MODEL", "QA_MODEL", fallback="gemini-3-flash-preview"),
            "temperature": config_service.get("PROCESSING", "TEMPERATURE", fallback=0.75, value_type=float),
            "chunk_size": config_service.get("PROCESSING", "MAX_CHARS_PER_CHUNK", fallback=22000, value_type=int),
            "use_cache": config_service.get("CACHE", "ENABLE_CACHE", fallback=True, value_type=bool),
            "prompts": load_prompts(),
            "context_char_count": config_service.get("PROCESSING", "CONTEXT_CHAR_COUNT", fallback=500, value_type=int),
        }

        # Glossary paths (nếu tồn tại)
        glossary_candidates = [Path("config/glossary.txt"), Path("glossary.txt")]
        glossary_paths = [p for p in glossary_candidates if p.exists()]

        executor = TranslationExecutor(api_keys=api_keys, config=config, glossary_paths=glossary_paths or None)

        input_dir = Path(config_service.get("DIRECTORIES", "INPUT_DIR", fallback="workspace/input"))
        files = find_input_files(input_dir)

        if not files:
            logging.warning(f"No files in {input_dir}")
            return 0

        logging.info(f"\nFiles: {len(files)}")
        for f in files:
            logging.info(f"  • {f.name}")

        output_dir = Path(
            config_service.get("DIRECTORIES", "OUTPUT_DIR", fallback="workspace/output")
        )
        output_dir.mkdir(parents=True, exist_ok=True)

        ok = fail = 0

        for filepath in files:
            logging.info(f"\n{'=' * 80}\n{filepath.name}\n{'=' * 80}")
            
            try:
                text_content = filepath.read_text(encoding="utf-8")
                logging.info(f"Source: {len(text_content):,} chars")
            except Exception as e:
                logging.error(f"Cannot read file {filepath.name}: {e}")
                fail += 1
                continue

            # Progress bar cho từng file
            from threading import Lock
            pbar_lock = Lock()
            pbar_state = {"bar": None, "last_current": 0}

            def cli_callback(data: dict):
                with pbar_lock:
                    evt_type = data.get("type")
                    if evt_type == "info":
                        pass  # Optionally log infos
                    elif evt_type == "error":
                        logging.error(data.get("message", ""))
                    elif evt_type == "progress":
                        bar = pbar_state["bar"]
                        if bar is None:
                            bar = tqdm(total=data["total"], desc=f"Translating {filepath.name}", unit="chunk")
                            pbar_state["bar"] = bar
                        
                        current = data.get("current", 0)
                        if current > pbar_state["last_current"]:
                            bar.update(current - pbar_state["last_current"])
                            pbar_state["last_current"] = current
                    elif evt_type == "complete":
                        bar = pbar_state["bar"]
                        if bar:
                            bar.close()
                            pbar_state["bar"] = None
                        logging.info(data.get("message", ""))

            out_path = output_dir / (filepath.stem + "_translated.txt")

            result = executor.translate_text(
                text=text_content,
                output_filename=filepath.stem,
                output_file_path=out_path,
                progress_callback=cli_callback
            )

            if result:
                ok += 1
                logging.info(f"✅ Saved: {out_path}")
            else:
                fail += 1

        logging.info(f"\n{'=' * 80}\nComplete!\n{'=' * 80}")
        logging.info(f"Success: {ok}, Failed: {fail}")
        logging.info(f"Output: {output_dir}")

        return 0 if fail == 0 else 1

    except Exception as e:
        logging.critical(f"Error: {e}", exc_info=True)
        print(f"\n❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
