"""CLI dịch Phase 1: provider/model explicit, dừng-ngay khi lỗi, log runs vào app.db."""

import argparse
import asyncio
import sys
from pathlib import Path

from core.ai_client import GeminiClient
from core.app_db import log_run
from core.chunker import split_text
from core.config import AppConfig
from core.key_rotator import KeyRotator
from core.openai_client import OpenAICompatClient
from core.prompt_engine import PromptEngine


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Content Translator — Minimalist AI translator")
    ap.add_argument("input", nargs="?")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--project")
    ap.add_argument("--file")
    ap.add_argument("--provider")
    ap.add_argument("--model")
    ap.add_argument("--prompt", default="default_translation.txt")
    return ap.parse_args(argv)


def build_client(provider: str, model: str, keys: list, cfg: dict):
    rotator = KeyRotator(keys)
    if provider == "openai_compat":
        base_url = cfg["providers"]["openai_compat"]["base_url"]
        return OpenAICompatClient(rotator, model=model, base_url=base_url,
                                  timeout_seconds=cfg["timeout_seconds"])
    return GeminiClient(rotator, model=model, timeout_seconds=cfg["timeout_seconds"])


async def main(argv=None) -> int:
    args = parse_args(argv)
    config_mgr = AppConfig()
    cfg = config_mgr.get_config()
    provider = args.provider or cfg.get("default_provider", "gemini")
    model = args.model or cfg.get("default_model", "gemini-2.5-flash")
    keys = config_mgr.get_keys(provider)

    if not keys:
        print(f"⚠️ Chưa tìm thấy API Key cho provider '{provider}' trong config/keys.json hoặc biến môi trường!")
        try:
            user_key = input("👉 Vui lòng nhập API Key của bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n❌ LỖI: Không có API Key thì không thể gọi AI. Thoát chương trình.")
            return 1
        if not user_key:
            print("❌ LỖI: Không có API Key thì không thể gọi AI. Thoát chương trình.")
            return 1
        config_mgr.save_keys(provider, [user_key])
        keys = [user_key]
        print("✅ Đã lưu API Key vào config/keys.json thành công.")

    if args.project and args.file:
        from core.file_handler import SafeFileHandler

        handler = SafeFileHandler()
        try:
            input_path = handler.get_source_path(args.project, args.file)
            output_path = handler.get_translated_path(args.project, args.file)
        except ValueError as e:
            print(f"❌ LỖI ĐƯỜNG DẪN: {e}")
            return 1
    elif args.input and args.output:
        input_path = Path(args.input)
        output_path = Path(args.output)
    else:
        print("Cách dùng:")
        print("  1. Dịch trực tiếp: python run.py input.txt output.txt [--provider gemini --model gemini-2.5-flash]")
        print("  2. Dịch theo dự án: python run.py --project Truyen --file ch01.md [--provider openai_compat --model deepseek-chat]")
        return 1

    if not input_path.exists():
        print(f"❌ LỖI: File không tồn tại: {input_path}")
        return 1

    raw_content = input_path.read_text(encoding="utf-8", errors="replace")
    if not raw_content.strip():
        print("⚠️ CẢNH BÁO: File nguồn rỗng! Không có nội dung cần dịch.")
        return 0

    try:
        prompt_engine = PromptEngine()
        prompt_engine.load_prompt(args.prompt)
    except FileNotFoundError as e:
        print(f"❌ LỖI: {e}")
        return 1

    chunks = split_text(raw_content, max_chars=cfg["max_chunk_chars"])
    total = len(chunks)
    print(f"📄 Bắt đầu dịch: {input_path.name} ({len(raw_content):,} ký tự -> {total} chunk) [{provider}/{model}].")

    ai_client = build_client(provider, model, keys, cfg)
    translated_chunks = []

    for idx, chunk_text in enumerate(chunks, 1):
        print(f"⏳ Đang gửi chunk {idx}/{total} ({len(chunk_text):,} ký tự)...", end="", flush=True)
        prompt = prompt_engine.assemble_prompt(chunk_text, prompt_filename=args.prompt)
        try:
            res = await ai_client.translate_chunk(prompt)
            translated_chunks.append(res)
            print(" [XONG]")
        except Exception as e:
            print(f"\n🛑 LỖI: {e}")
            print("⚠️ CHƯƠNG TRÌNH ĐÃ DỪNG VÀ KHÔNG LƯU TRẠNG THÁI DỞ DANG.")
            print("👉 Bạn hãy kiểm tra lại kết nối / API key và chạy lại lệnh từ đầu.")
            log_run(provider, model, "error", str(e))
            return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(translated_chunks), encoding="utf-8")
    log_run(provider, model, "ok")
    print(f"🎉 HOÀN TẤT! Bản dịch đã lưu tại: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
