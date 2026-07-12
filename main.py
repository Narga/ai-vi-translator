# main.py - v7.0.0 Pure Plugin Architecture + google-genai SDK
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
from backend.infrastructure.config.app_config_service import AppConfigService
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
    """Load Gemini API keys. Delegates to ApiKeyService (providers.json)."""
    from backend.infrastructure.config.api_key_service import ApiKeyService
    keys = ApiKeyService(Path("config")).load_gemini_keys()
    if keys:
        logging.info(f"✅ Loaded {len(keys)} API keys from providers.json")
    return keys


def load_prompts(project_dir: Path = None) -> Dict[str, str]:
    prompts = {}

    # Ưu tiên load từ project
    if project_dir:
        prompt_dir = project_dir / "prompt"
        if prompt_dir.exists():
            for key, filename in [
                ("main", "main_prompt.txt"),
            ]:
                fp = prompt_dir / filename
                if fp.exists():
                    prompts[key] = fp.read_text(encoding="utf-8").strip()

    # Fallback/Update với global prompts
    prompts_root = Path("workspace/prompts/default")
    for key, filename in [
        ("main", "main_prompt.txt"),
    ]:
        if key not in prompts:
            filepath = prompts_root / filename
            if filepath.exists():
                prompts[key] = filepath.read_text(encoding="utf-8").strip()
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
        merged_name = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        merged_path = input_dir / merged_name

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
        import argparse
        parser = argparse.ArgumentParser(description="Novel Translator CLI")
        parser.add_argument("--project", "-p", default="default-project", help="Project slug")
        parser.add_argument("--input", "-i", help="Input directory (optional)")
        parser.add_argument("--output", "-o", help="Output directory (optional)")
        parser.add_argument("--config", "-c", default="config/app.ini", help="Config file")
        parser.add_argument("--dry-run", action="store_true", help="Dry run")
        parser.add_argument("--resume", help="Resume from checkpoint")
        parser.add_argument("--force", action="store_true", help="Force translate")
        parser.add_argument("--quiet", "-q", action="store_true", help="Quiet mode")
        
        # Parse known args to avoid conflict with cli.py wrapper
        args, unknown = parser.parse_known_args()

        print("=" * 80)
        print("📚 Novel Translator v7.0.0 | Pure Executor Architecture")
        print(f"Project: {args.project}")
        print("=" * 80)

        # Cài đặt signal handlers cho graceful shutdown
        setup_signal_handlers()
        reset_emergency_stop()

        config_service = AppConfigService(Path("config"))
        setup_logging(
            Path(config_service.get("DIRECTORIES", "LOGS_DIR", fallback="workspace/logs"))
        )

        pdir = Path("workspace/projects") / args.project
        if not pdir.exists():
            from webui.helpers import ensure_default_project
            if args.project == "default-project":
                ensure_default_project()
            else:
                print(f"❌ Dự án '{args.project}' không tồn tại.")
                return 1

        api_keys = load_api_keys()
        
        # Build config for Executor
        config = {
            "model_name": config_service.get("MODEL", "MODEL", fallback="gemini-3-flash-preview"),
            "qa_model": config_service.get("MODEL", "QA_MODEL", fallback="gemini-3-flash-preview"),
            "temperature": config_service.get("PROCESSING", "TEMPERATURE", fallback=0.75, value_type=float),
            "chunk_size": config_service.get("PROCESSING", "MAX_CHARS_PER_CHUNK", fallback=22000, value_type=int),
            "prompts": load_prompts(pdir),
            "context_char_count": config_service.get("PROCESSING", "CONTEXT_CHAR_COUNT", fallback=500, value_type=int),
        }

        # Glossary paths (Dùng từ project profile)
        glossary_filenames = ["glossary.txt", "characters.txt"]
        glossary_paths = [pdir / "profile" / gf for gf in glossary_filenames if (pdir / "profile" / gf).exists()]

        executor = TranslationExecutor(api_keys=api_keys, config=config, glossary_paths=glossary_paths or None)

        input_dir = Path(args.input) if args.input else pdir / "sources"
        files = find_input_files(input_dir)

        if not files:
            logging.warning(f"No files in {input_dir}")
            return 0

        logging.info(f"\nFiles: {len(files)}")
        for f in files:
            logging.info(f"  • {f.name}")

        output_dir = Path(args.output) if args.output else pdir / "translated"
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
