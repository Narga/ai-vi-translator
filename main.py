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
from typing import List, Dict, Any

from tqdm import tqdm

from core import PluginManager, ServiceBus, EventBus
from services.api_service import ApiManager
from services.cache_service import TranslationCache
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


def translate_file(filepath: Path, plugin, prompts: Dict, output_dir: Path) -> bool:
    try:
        logging.info(f"\n{'=' * 80}\n{filepath.name}\n{'=' * 80}")

        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()

        logging.info(f"Source: {len(source)} chars")

        chunks = plugin.chunk_text(source)
        logging.info(f"Chunks: {len(chunks)}")

        translated = []
        prev_context = ""

        for i, chunk in enumerate(tqdm(chunks, desc=f"Translating {filepath.name}", unit="chunk")):
            # logging.info(f"\nChunk {i + 1}/{len(chunks)}")

            context = {
                "prompts": prompts,
                "previous_context": prev_context,
                "chunk_index": i,
            }

            result, status = plugin.process(chunk, context)

            if status == "success" and result:
                translated.append(result)
                ctx_len = plugin.translation_config.get("context_char_count", 500)
                prev_context = result[-ctx_len:] if len(result) > ctx_len else result
                # logging.info(f"✅ Done")
            else:
                logging.error(f"❌ Failed at chunk {i + 1}")
                return False

        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / (filepath.stem + "_translated.txt")

        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n\n".join(translated))

        logging.info(f"\n✅ Saved: {output_file}")
        return True

    except Exception as e:
        logging.error(f"Error: {e}", exc_info=True)
        return False


def main():
    try:
        print("=" * 80)
        print("📚 Novel Translator v4.0.0 | SDK: google-genai | Model: gemini-3-flash-preview")
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

        api_service = ApiManager(api_keys)
        cache_dir = Path(config_service.get("DIRECTORIES", "CACHE_DIR", fallback="workspace/cache"))
        cache_enabled = config_service.get("CACHE", "ENABLE_CACHE", fallback=True, value_type=bool)
        cache_service = TranslationCache(str(cache_dir), enabled=cache_enabled)

        service_bus = ServiceBus()
        service_bus.register_service("config", config_service)
        service_bus.register_service("api", api_service)
        service_bus.register_service("cache", cache_service)
        service_bus.register_service("logger", logging.getLogger())

        event_bus = EventBus(enable_history=True)
        plugin_manager = PluginManager(service_bus, event_bus, Path("plugins"), Path("config"))

        # v4.0.0: Chỉ nạp plugin dịch thuật cho luồng main
        # Tránh nạp OCR, EPUB Converter... không cần thiết làm chậm và nhiễu log
        if not plugin_manager.load_plugin("translation"):
            logging.critical("Failed to load translation plugin")
            return 1

        translation_plugin = plugin_manager.get_plugin("translation")
        if not translation_plugin:
            logging.critical("Translation plugin not found")
            return 1

        prompts = load_prompts()

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

        ok = fail = 0

        for filepath in files:
            if translate_file(filepath, translation_plugin, prompts, output_dir):
                ok += 1
            else:
                fail += 1

        logging.info(f"\n{'=' * 80}\nComplete!\n{'=' * 80}")
        logging.info(f"Success: {ok}, Failed: {fail}")
        logging.info(f"Output: {output_dir}")

        plugin_manager.cleanup_all_plugins()

        return 0 if fail == 0 else 1

    except Exception as e:
        logging.critical(f"Error: {e}", exc_info=True)
        print(f"\n❌ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
