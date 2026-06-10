# plugins/spellcheck/spellchecker.py
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cache client theo (provider_type, api_key, base_url, model_name)
# để tránh khởi tạo lại client mỗi chunk
_client_cache: Dict[str, Any] = {}


def _get_client(api_key: str, config: Dict[str, Any]) -> Any:
    """
    Lấy hoặc tạo Client (GenAI hoặc OpenAI) cho API key (có cache).
    Pattern giống plugins/translation/translator.py:_get_client.

    Args:
        api_key: API key
        config: Dict chứa provider_type, model_name, base_url, thinking_level

    Returns:
        Client instance (GenAIClient hoặc OpenAIClient)
    """
    global _client_cache

    provider_type = config.get("provider_type", "gemini")
    base_url = config.get("base_url") or ""
    default_model = config.get("model_name", "gemini-1.5-flash")
    thinking_level = config.get("thinking_level", "MEDIUM")

    # Cache key phân biệt đầy đủ để tránh dùng nhầm client
    cache_key = f"{provider_type}_{api_key}_{base_url}_{default_model}"

    if cache_key not in _client_cache:
        if provider_type == "openai":
            from services.openai_client import OpenAIClient
            _client_cache[cache_key] = OpenAIClient(
                api_key=api_key, base_url=base_url, default_model=default_model
            )
        else:
            from services.genai_client import GenAIClient
            _client_cache[cache_key] = GenAIClient(
                api_key=api_key, default_model=default_model, thinking_level=thinking_level
            )

    return _client_cache[cache_key]


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
        client = _get_client(api_key, config)
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