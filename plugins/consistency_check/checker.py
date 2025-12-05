# src/translators/consistency.py - v2.6.1
# Tác giả: Narga
# Chức năng: Kiểm tra và tinh chỉnh sự nhất quán (consistency) cho file chunk đã dịch.

import logging
from pathlib import Path
from typing import Dict, Any, Optional

from .api_manager import ApiManager
from .cache_manager import TranslationCache
from .core import _call_api  # tái sử dụng cơ chế gọi API

def consistency_check_chunk(
    chunk_file: Path,
    api_manager: ApiManager,
    cache: TranslationCache,
    prompts: Dict[str, str],
    config_params: Dict[str, Any],
    normalizer: Optional[object] = None
) -> None:
    """
    Kiểm tra và tinh chỉnh sự nhất quán của một file chunk đã dịch:
      - Bỏ qua nếu không có prompt consistency hoặc prompt trống/ghi chú mặc định.
      - Dùng cache để tránh trùng lặp chi phí.
      - Ghi đè file nếu có kết quả tốt hơn.
    """
    try:
        translated_text = chunk_file.read_text(encoding='utf-8')
        if not translated_text.strip():
            return

        consistency_prompt = prompts.get('consistency', '')
        if not consistency_prompt or "Không có ghi chú đặc biệt." in consistency_prompt:
            return

        logging.info(f"Kiểm tra sự nhất quán cho file {chunk_file.name}...")

        cache_key = consistency_prompt + translated_text
        cached_result = cache.get(cache_key)
        if cached_result:
            final_text = cached_result
        else:
            final_text, status, _ = _call_api(
                translated_text, consistency_prompt, api_manager,
                config_params, model_override=config_params.get('consistency_model')
            )
            if status != "success" or not final_text:
                logging.warning(f"Không thể tinh chỉnh sự nhất quán cho {chunk_file.name}.")
                return
            cache.set(cache_key, final_text)

        if normalizer:
            try:
                final_text = normalizer.normalize(final_text)
            except Exception as e:
                logging.warning(f"⚠️ Lỗi khi chuẩn hóa văn bản cho {chunk_file.name}: {e}")

        chunk_file.write_text(final_text, encoding='utf-8')
    except Exception as e:
        logging.error(f"Lỗi trong quá trình kiểm tra sự nhất quán của file {chunk_file.name}: {e}")
