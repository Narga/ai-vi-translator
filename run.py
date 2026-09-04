"""CLI dịch Phase 1: provider/model lấy từ providers.json (SSOT), --provider/--model override."""

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
from core.provider_manager import AIProviderManager


def parse_args(argv=None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Content Translator — Minimalist AI translator")
    ap.add_argument("input", nargs="?")
    ap.add_argument("output", nargs="?")
    ap.add_argument("--project")
    ap.add_argument("--file")
    ap.add_argument("--provider", help="Provider id trong providers.json (mặc định: active_id)")
    ap.add_argument("--model", help="Model override (mặc định: default_model của provider)")
    ap.add_argument("--prompt", default="default_translation.txt")
    return ap.parse_args(argv)


def build_client(provider: dict, model: str, keys: list, timeout: float):
    """Dựng client theo provider record. thinking chỉ Gemini đọc (openai bỏ qua)."""
    rotator = KeyRotator(keys)
    if provider.get("type") == "openai":
        return OpenAICompatClient(rotator, model=model, base_url=provider.get("base_url", ""),
                                  timeout_seconds=timeout)
    thinking = AIProviderManager.THINKING_BUDGETS.get((provider.get("thinking") or "OFF").upper(), 0) or None
    return GeminiClient(rotator, model=model, timeout_seconds=timeout, thinking_budget=thinking)


async def main(argv=None) -> int:
    args = parse_args(argv)
    cfg = AppConfig().get_config()
    mgr = AIProviderManager()

    try:
        provider = mgr.get_by_id(args.provider) if args.provider else mgr.get_active()
    except ValueError as e:
        print(f"❌ LỖI: {e}")
        return 1
    ptype = provider.get("type", "gemini")
    model = args.model or provider.get("default_model", "")
    if args.model:  # override phải qua namespace validation
        try:
            mgr._validate_model_namespace(ptype, model, provider.get("base_url", ""))
        except ValueError as e:
            print(f"❌ LỖI: {e}")
            return 1
    if not model:
        print(f"❌ LỖI: Provider '{provider['id']}' chưa chọn model. Mở WebUI Cấu Hình hoặc docs/06 để chọn từ danh sách live.")
        return 1

    keys = mgr.get_keys(provider)
    if not keys:
        print(f"⚠️ Chưa tìm thấy API Key cho provider '{provider['id']}'!")
        try:
            user_key = input("👉 Vui lòng nhập API Key của bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n❌ LỖI: Không có API Key thì không thể gọi AI. Thoát chương trình.")
            return 1
        if not user_key:
            print("❌ LỖI: Không có API Key thì không thể gọi AI. Thoát chương trình.")
            return 1
        if ptype == "gemini":
            mgr.update_provider_keys_and_model(provider["id"], api_keys=[user_key])
        else:
            mgr.update_provider_keys_and_model(provider["id"], api_key=user_key)
        keys = [user_key]
        print("✅ Đã lưu API Key vào config/providers.json thành công.")

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
    print(f"📄 Bắt đầu dịch: {input_path.name} ({len(raw_content):,} ký tự -> {total} chunk) [{provider['id']}/{model}].")

    ai_client = build_client(provider, model, keys, cfg["timeout_seconds"])
    translated_chunks = []
    delay = cfg.get("api_delay_seconds", 2.0)

    for idx, chunk_text in enumerate(chunks, 1):
        if idx > 1 and delay > 0:
            await asyncio.sleep(delay)  # giãn request, tránh 429
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
            log_run(provider["id"], model, "error", str(e))
            return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(translated_chunks), encoding="utf-8")
    log_run(provider["id"], model, "ok")
    print(f"🎉 HOÀN TẤT! Bản dịch đã lưu tại: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
