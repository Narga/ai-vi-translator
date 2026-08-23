# services/openai_client.py - v6.0.0
# Tác giả: Narga
# Chức năng: Wrapper cho OpenAI-compatible API (OpenAI, OpenRouter, các proxy khác).

"""
OpenAI Client - Lớp trừu tượng hóa cho OpenAI-compatible API.

Hỗ trợ:
- OpenAI trực tiếp (api.openai.com)
- OpenRouter (openrouter.ai)
- Bất kỳ proxy nào tương thích OpenAI API format

Sử dụng:
    client = OpenAIClient(api_key, base_url="https://openrouter.ai/api/v1")
    response = client.generate_content(prompt, model="gpt-4o-mini")
"""

import logging
from typing import Optional, Dict, Any, Tuple, List
from backend.infrastructure.providers.endpoint_policy import EndpointPolicy, classify_endpoint

class OpenAIClient:
    """
    Wrapper cho OpenAI SDK.
    Tương thích với OpenRouter, proxy và mọi dịch vụ OpenAI-compatible.
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        default_model: str = "gpt-4o-mini",
        gateway_api_key: Optional[str] = None,
        credential_mode: str = "default",
        policy: Optional[EndpointPolicy] = None,
    ):
        """
        Khởi tạo OpenAI Client.

        Args:
            api_key (str): OpenAI / OpenRouter API key
            base_url (str, optional): Base URL cho proxy
            default_model (str): Model mặc định
        """
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.gateway_api_key = gateway_api_key
        self.credential_mode = credential_mode
        self.policy = policy or classify_endpoint(base_url)
        self.logger = logging.getLogger(__name__)

        self._initialize_client()

    def _initialize_client(self) -> None:
        """Khởi tạo OpenAI client."""
        try:
            from openai import OpenAI

            sdk_api_key = self.api_key or self.gateway_api_key
            if not sdk_api_key and self.policy.requires_api_key():
                raise ValueError("Chưa cấu hình provider API key hoặc gateway API key")

            # The OpenAI SDK requires a non-empty value even when a local
            # OpenAI-compatible endpoint intentionally has no authentication.
            # The policy prevents this placeholder from being sent as a header.
            sdk_api_key = sdk_api_key or "local-no-auth"

            kwargs: Dict[str, Any] = {
                "api_key": sdk_api_key,
                "base_url": self.policy.normalized_base_url,
            }
            
            headers = self.policy.build_headers(self.api_key, self.gateway_api_key, self.credential_mode)
            if headers:
                kwargs["default_headers"] = headers

            self._client = OpenAI(**kwargs)
            self.logger.debug(
                f"✅ OpenAI Client initialized (base_url={self.policy.normalized_base_url}, policy={self.policy.provider_kind})"
            )
        except ImportError:
            raise ImportError(
                "Thư viện 'openai' chưa được cài đặt. "
                "Vui lòng chạy: pip install openai"
            )

    def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 1.0,
        **kwargs,
    ) -> Tuple[Optional[str], str]:
        """
        Sinh nội dung sử dụng OpenAI-compatible API.

        Args:
            prompt (str): Prompt đầu vào
            model (str, optional): Model override
            temperature (float): Nhiệt độ (default 1.0)

        Returns:
            Tuple[Optional[str], str]: (content, status)
        """
        model_name = model or self.default_model
        model_name = self.policy.normalize_model(model_name)
        
        if not self.policy.validate_model(model_name):
            raise ValueError(f"Model {model_name} không hợp lệ với policy {self.policy.provider_kind}")

        try:
            from openai import APIStatusError, APIConnectionError, APITimeoutError
            
            request_kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                "timeout": kwargs.get("timeout", 600.0),
            }
            # Gemini-only options must never leak into the OpenAI-compatible adapter.
            for key in ("max_tokens", "top_p", "response_format"):
                if key in kwargs and kwargs[key] is not None:
                    request_kwargs[key] = kwargs[key]

            response = self._client.chat.completions.create(**request_kwargs)

            if response and response.choices:
                content = response.choices[0].message.content
                if content:
                    return content.strip(), "success"
            return None, "empty_response"

        except ValueError:
            raise
        except Exception as e:
            from openai import APIStatusError, APIConnectionError, APITimeoutError
            self.logger.error(f"OpenAI Error: {e}")
            
            status = 500
            if hasattr(e, 'status_code'):
                status = e.status_code
            elif isinstance(e, APITimeoutError):
                status = 408
            elif isinstance(e, APIConnectionError):
                status = 503
            
            raise self.policy.classify_error(status, str(e))

    def list_models(self) -> List[str]:
        """
        Liệt kê các models khả dụng từ API.
        """
        try:
            response = self._client.models.list()
            models = []
            for model in response.data:
                models.append(model.id)
            return sorted(models)
        except Exception as e:
            self.logger.error(f"Error listing OpenAI models: {e}")
            status = getattr(e, 'status_code', 500)
            raise self.policy.classify_error(status, str(e))

    def list_models_full(self) -> List[Dict[str, Any]]:
        """
        Liệt kê các models khả dụng với đầy đủ thông tin (OpenRouter-friendly).
        """
        try:
            response = self._client.models.list()
            models = []
            for model in response.data:
                is_cf_model = model.id.startswith("@cf/") or model.id.startswith("workers-ai/@cf/")
                        
                m_dict = {
                    "id": model.id,
                    "name": getattr(model, "name", model.id),
                }
                
                if self.policy.provider_kind == "cloudflare_ai_gateway" and is_cf_model:
                    m_dict["source"] = "cloudflare_workers_ai"
                    m_dict["docs_url"] = "https://developers.cloudflare.com/ai-gateway/usage/providers/workersai/"

                if hasattr(model, "context_length"):
                    m_dict["context_length"] = getattr(model, "context_length")
                if hasattr(model, "pricing"):
                    m_dict["pricing"] = getattr(model, "pricing")
                
                is_free = ":free" in model.id.lower() or "free" in getattr(model, "name", "").lower()
                m_dict["is_free"] = is_free
                
                models.append(m_dict)
            return models
        except Exception as e:
            self.logger.error(f"Error listing OpenAI models (full): {e}")
            status = getattr(e, 'status_code', 500)
            raise self.policy.classify_error(status, str(e))

    def get_sdk_info(self) -> Dict[str, Any]:
        """Trả về thông tin SDK."""
        return {
            "sdk": "openai",
            "model": self.default_model,
            "base_url": self.policy.normalized_base_url,
            "policy": self.policy.provider_kind,
        }

    def reconfigure(self, api_key: str, base_url: Optional[str] = None, gateway_api_key: Optional[str] = None, credential_mode: str = "default") -> None:
        """Cấu hình lại API key và/hoặc base URL."""
        self.api_key = api_key
        if base_url is not None:
            self.base_url = base_url
            self.policy = classify_endpoint(base_url)
        if gateway_api_key is not None:
            self.gateway_api_key = gateway_api_key
        self.credential_mode = credential_mode
        self._initialize_client()
