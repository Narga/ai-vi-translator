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
    ):
        """
        Khởi tạo OpenAI Client.

        Args:
            api_key (str): OpenAI / OpenRouter API key
            base_url (str, optional): Base URL cho proxy (vd: https://openrouter.ai/api/v1)
            default_model (str): Model mặc định
        """
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.logger = logging.getLogger(__name__)

        self._initialize_client()

    def _initialize_client(self) -> None:
        """Khởi tạo OpenAI client."""
        try:
            from openai import OpenAI

            kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url

            self._client = OpenAI(**kwargs)
            self.logger.debug(
                f"✅ OpenAI Client initialized (base_url={self.base_url or 'default'})"
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

        try:
            response = self._client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )

            if response and response.choices:
                content = response.choices[0].message.content
                if content:
                    return content.strip(), "success"
            return None, "empty_response"

        except Exception as e:
            self.logger.error(f"OpenAI Error: {e}")
            return None, f"error: {str(e)}"

    def list_models(self) -> List[str]:
        """
        Liệt kê các models khả dụng từ API.

        Returns:
            List[str]: Danh sách model IDs
        """
        try:
            response = self._client.models.list()
            models = []
            for model in response.data:
                models.append(model.id)
            return sorted(models)
        except Exception as e:
            self.logger.error(f"Error listing OpenAI models: {e}")
            return []

    def get_sdk_info(self) -> Dict[str, Any]:
        """Trả về thông tin SDK."""
        return {
            "sdk": "openai",
            "model": self.default_model,
            "base_url": self.base_url or "https://api.openai.com/v1",
        }

    def reconfigure(self, api_key: str, base_url: Optional[str] = None) -> None:
        """Cấu hình lại API key và/hoặc base URL."""
        self.api_key = api_key
        if base_url is not None:
            self.base_url = base_url
        self._initialize_client()


class AsyncOpenAIClient:
    """
    Async wrapper cho OpenAI SDK.
    Sử dụng khi cần gọi nhiều API requests đồng thời.
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str] = None,
        default_model: str = "gpt-4o-mini",
        max_concurrent: int = 5,
    ):
        """
        Khởi tạo Async OpenAI Client.

        Args:
            api_key (str): API key
            base_url (str, optional): Base URL cho proxy
            default_model (str): Model mặc định
            max_concurrent (int): Số concurrent requests tối đa
        """
        import asyncio

        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._logger = logging.getLogger(__name__)

        self._initialize_client()

    def _initialize_client(self) -> None:
        """Khởi tạo async OpenAI client."""
        try:
            from openai import AsyncOpenAI

            kwargs: Dict[str, Any] = {"api_key": self.api_key}
            if self.base_url:
                kwargs["base_url"] = self.base_url

            self._client = AsyncOpenAI(**kwargs)
            self._logger.debug("✅ Async OpenAI Client initialized")
        except ImportError:
            raise ImportError(
                "Thư viện 'openai' chưa được cài đặt. "
                "Vui lòng chạy: pip install openai"
            )

    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 1.0,
        **kwargs,
    ) -> Tuple[Optional[str], str]:
        """
        Sinh nội dung bất đồng bộ.

        Args:
            prompt (str): Prompt đầu vào
            model (str, optional): Model override
            temperature (float): Nhiệt độ

        Returns:
            Tuple[Optional[str], str]: (content, status)
        """
        async with self._semaphore:
            model_name = model or self.default_model

            try:
                response = await self._client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )

                if response and response.choices:
                    content = response.choices[0].message.content
                    if content:
                        return content.strip(), "success"
                return None, "empty_response"

            except Exception as e:
                self._logger.error(f"Async OpenAI Error: {e}")
                return None, f"error: {str(e)}"
