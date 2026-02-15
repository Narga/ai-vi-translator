# services/async_genai_client.py - v4.0.0
# Tác giả: Narga
# Chức năng: Async wrapper cho Gemini API với aiohttp

"""
Async GenAI Client - Phiên bản bất đồng bộ của GenAIClient.
Sử dụng khi cần gọi nhiều API requests đồng thời.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime


class AsyncGenAIClient:
    """
    Async wrapper cho google-genai SDK.
    Hỗ trợ gọi API bất đồng bộ với semaphore để kiểm soát concurrency.
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "gemini-3-flash-preview",
        thinking_level: str = "MEDIUM",
        max_concurrent: int = 5,
    ):
        """
        Khởi tạo Async GenAI Client.

        Args:
            api_key (str): Gemini API key
            default_model (str): Model mặc định
            thinking_level (str): Mức độ thinking
            max_concurrent (int): Số concurrent requests tối đa
        """
        self.api_key = api_key
        self.default_model = default_model
        self.thinking_level = thinking_level
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._logger = logging.getLogger(__name__)

        self._initialize_client()

    def _initialize_client(self) -> None:
        """Khởi tạo google-genai client."""
        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            self._logger.debug("✅ Async GenAI Client initialized")
        except ImportError:
            raise ImportError(
                "Thư viện 'google-genai' chưa được cài đặt. "
                "Vui lòng chạy: pip install google-genai"
            )

    async def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 1.0,
        thinking_level: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Optional[str], str]:
        """
        Sinh nội dung bất đồng bộ.

        Args:
            prompt (str): Prompt đầu vào
            model (str, optional): Model override
            temperature (float): Nhiệt độ
            thinking_level (str, optional): Override thinking level

        Returns:
            Tuple[Optional[str], str]: (content, status)
        """
        async with self._semaphore:
            model_name = model or self.default_model
            curr_thinking = thinking_level or self.thinking_level

            try:
                generation_config: Dict[str, Any] = {
                    "temperature": temperature,
                }

                if "gemini-3" in model_name.lower():
                    generation_config["thinking_config"] = {
                        "thinking_level": curr_thinking
                    }

                loop = asyncio.get_event_loop()

                def _sync_call():
                    return self._client.models.generate_content(
                        model=model_name, contents=prompt, config=generation_config
                    )

                response = await loop.run_in_executor(None, _sync_call)

                if response and response.text:
                    return response.text.strip(), "success"
                return None, "empty_response"

            except Exception as e:
                self._logger.error(f"Async GenAI Error: {e}")
                return None, f"error: {str(e)}"

    async def batch_generate(
        self, prompts: list[str], model: Optional[str] = None, temperature: float = 1.0
    ) -> list[Tuple[Optional[str], str]]:
        """
        Gọi nhiều prompts đồng thời.

        Args:
            prompts (list[str]): Danh sách prompts
            model (str, optional): Model override
            temperature (float): Nhiệt độ

        Returns:
            List[Tuple[content, status]] - Kết quả cho mỗi prompt
        """
        tasks = [
            self.generate_content(prompt, model, temperature) for prompt in prompts
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                self._logger.error(f"Task {i} failed: {result}")
                processed_results.append((None, f"error: {str(result)}"))
            else:
                processed_results.append(result)

        return processed_results


class AsyncApiManager:
    """
    Async API Manager - Quản lý async API calls với rate limiting.
    """

    def __init__(self, api_keys: list[str], max_rpm: int = 15, max_concurrent: int = 5):
        """
        Khởi tạo AsyncApiManager.

        Args:
            api_keys (list[str]): Danh sách API keys
            max_rpm (int): Giới hạn RPM
            max_concurrent (int): Số concurrent requests tối đa
        """
        self._keys = api_keys
        self._current_key_index = 0
        self._lock = asyncio.Lock()

        # Import sync rate limiter
        from services.api_service import GlobalRPMRateLimiter, TokenBudgetLimiter

        self._rpm_limiter = GlobalRPMRateLimiter(max_rpm=max_rpm)
        self._token_limiter = TokenBudgetLimiter(max_tpm=1_000_000)

        # Tạo clients với round-robin assignment
        self._clients: list[AsyncGenAIClient] = []
        for key in api_keys:
            self._clients.append(
                AsyncGenAIClient(api_key=key, max_concurrent=max_concurrent)
            )

        self._logger = logging.getLogger(__name__)
        self._logger.info(
            f"✅ AsyncApiManager initialized: {len(api_keys)} keys, {max_concurrent} max concurrent"
        )

    async def get_next_client(self) -> Optional[AsyncGenAIClient]:
        """Lấy client tiếp theo (round-robin)."""
        async with self._lock:
            if not self._clients:
                return None

            client = self._clients[self._current_key_index]
            self._current_key_index = (self._current_key_index + 1) % len(self._clients)
            return client

    async def generate_content(
        self, prompt: str, model: Optional[str] = None, temperature: float = 1.0
    ) -> Tuple[Optional[str], str]:
        """
        Gọi API với rate limiting.

        Args:
            prompt (str): Prompt
            model (str, optional): Model
            temperature (float): Nhiệt độ

        Returns:
            Tuple[content, status]
        """
        # Acquire RPM token
        while not self._rpm_limiter.acquire(blocking=False):
            await asyncio.sleep(0.5)

        # Acquire token budget
        text_len = len(prompt)
        estimated_tokens = int(text_len / 2.5)
        while not self._token_limiter.acquire(estimated_tokens, blocking=False):
            await asyncio.sleep(0.5)

        # Get client
        client = await self.get_next_client()
        if not client:
            return None, "no_available_client"

        return await client.generate_content(prompt, model, temperature)

    async def batch_generate(
        self, prompts: list[str], model: Optional[str] = None, temperature: float = 1.0
    ) -> list[Tuple[Optional[str], str]]:
        """
        Gọi nhiều prompts đồng thời.

        Args:
            prompts (list[str]): Danh sách prompts
            model (str, optional): Model
            temperature (float): Nhiệt độ

        Returns:
            List[kết quả]
        """
        tasks = [
            self.generate_content(prompt, model, temperature) for prompt in prompts
        ]

        return await asyncio.gather(*tasks, return_exceptions=True)
