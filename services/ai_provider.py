# services/ai_provider.py - v6.0.0
# Tác giả: Narga
# Chức năng: Adapter pattern thống nhất cho nhiều AI providers.

"""
AI Provider - Factory & Adapter cho multi-provider AI support.

Cung cấp giao diện thống nhất cho:
- Google Gemini (google-genai SDK)
- OpenAI-compatible (OpenAI, OpenRouter, proxy)

Sử dụng:
    provider = create_provider("gemini", api_key="...")
    content, status = provider.generate_content(prompt)
"""

import logging
from typing import Optional, Dict, Any, Tuple, List, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class AIProvider(Protocol):
    """Giao diện chung cho mọi AI provider."""

    def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 1.0,
        **kwargs,
    ) -> Tuple[Optional[str], str]:
        """Sinh nội dung từ AI.

        Returns:
            Tuple[Optional[str], str]: (content, status)
        """
        ...

    def get_sdk_info(self) -> Dict[str, Any]:
        """Trả về thông tin SDK/provider hiện tại."""
        ...


def create_provider(
    provider_type: str,
    api_key: str,
    default_model: Optional[str] = None,
    **kwargs,
) -> AIProvider:
    """
    Factory tạo AI provider theo loại.

    Args:
        provider_type: "gemini" hoặc "openai"
        api_key: API key
        default_model: Model mặc định (override mặc định của provider)
        **kwargs: Tham số bổ sung (base_url, thinking_level, ...)

    Returns:
        AIProvider instance

    Raises:
        ValueError: Nếu provider_type không được hỗ trợ
        ImportError: Nếu SDK cần thiết chưa được cài
    """
    if provider_type == "gemini":
        from services.genai_client import GenAIClient

        model = default_model or kwargs.pop("model", "gemini-3-flash-preview")
        thinking_level = kwargs.pop("thinking_level", "MEDIUM")
        return GenAIClient(
            api_key=api_key,
            default_model=model,
            thinking_level=thinking_level,
        )

    elif provider_type == "openai":
        from services.openai_client import OpenAIClient

        model = default_model or kwargs.pop("model", "gpt-4o-mini")
        base_url = kwargs.pop("base_url", None)
        return OpenAIClient(
            api_key=api_key,
            base_url=base_url,
            default_model=model,
        )

    else:
        raise ValueError(
            f"Provider '{provider_type}' không được hỗ trợ. "
            f"Sử dụng 'gemini' hoặc 'openai'."
        )


def get_available_providers() -> List[Dict[str, Any]]:
    """
    Trả về danh sách providers khả dụng (đã cài SDK).

    Returns:
        List[Dict]: Mỗi item chứa name, sdk, available, description
    """
    providers = []

    # Check Gemini SDK
    gemini_available = False
    try:
        import google.genai  # noqa: F401
        gemini_available = True
    except ImportError:
        pass

    providers.append({
        "name": "gemini",
        "display_name": "Google Gemini",
        "sdk": "google-genai",
        "available": gemini_available,
        "description": "Google Gemini AI (gemini-3-flash, gemini-2.0-flash, ...)",
        "icon": "🔷",
    })

    # Check OpenAI SDK
    openai_available = False
    try:
        import openai  # noqa: F401
        openai_available = True
    except ImportError:
        pass

    providers.append({
        "name": "openai",
        "display_name": "OpenAI Compatible",
        "sdk": "openai",
        "available": openai_available,
        "description": "OpenAI, OpenRouter, hoặc bất kỳ proxy tương thích",
        "icon": "🟢",
    })

    return providers


def list_models_for_provider(
    provider_type: str,
    api_key: str,
    base_url: Optional[str] = None,
) -> List[str]:
    """
    Liệt kê models khả dụng cho một provider.

    Args:
        provider_type: "gemini" hoặc "openai"
        api_key: API key
        base_url: Base URL (cho OpenAI-compatible)

    Returns:
        List[str]: Danh sách model names
    """
    if provider_type == "gemini":
        try:
            from google import genai

            client = genai.Client(api_key=api_key)
            models = []
            for model in client.models.list():
                if model and model.name:
                    model_name = model.name.replace("models/", "")
                    if "gemini" in model_name:
                        models.append(model_name)
            return sorted(set(models))
        except Exception as e:
            logger.error(f"Error listing Gemini models: {e}")
            return []

    elif provider_type == "openai":
        try:
            from services.openai_client import OpenAIClient

            client = OpenAIClient(api_key=api_key, base_url=base_url)
            return client.list_models()
        except Exception as e:
            logger.error(f"Error listing OpenAI models: {e}")
            return []

    return []
