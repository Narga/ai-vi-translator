# plugins/spellcheck/spellchecker.py
import logging
from typing import Tuple, Dict, Any, Optional
from services.genai_client import GenAIClient

logger = logging.getLogger(__name__)

def spellcheck_chunk(
    text: str,
    prompt: str,
    api_manager: Any,
    config: Dict[str, Any]
) -> Tuple[str, str, str]:
    """
    Gửi một đoạn văn bản đi soát lỗi chính tả.
    Hoàn toàn độc lập với dịch thuật.
    
    Returns:
        Tuple[result_text, status, api_key_used]
    """
    api_key = api_manager.get_next_available_key()
    if not api_key:
        return "", "no_api_key", ""

    # Cấu hình model
    model_name = config.get("model_name", "gemini-1.5-flash")
    temperature = config.get("temperature", 0.0)

    # Build prompt (Không thêm bất kỳ header ẩn nào liên quan đến dịch)
    full_prompt = f"{prompt}\n\n{text}"

    try:
        client = GenAIClient(api_key=api_key)
        result, status = client.generate_content(
            prompt=full_prompt,
            model=model_name,
            temperature=temperature
        )
        if status == "success" and result:
            return result.strip(), "success", api_key
        return "", status or "empty_response", api_key
    except Exception as e:
        logger.error(f"Lỗi Spellcheck API: {str(e)}")
        return "", str(e), api_key
