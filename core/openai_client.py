"""Client OpenAI-compatible (OpenRouter/Groq/DeepSeek/Ollama) qua httpx thuần."""

import httpx
import logging
from core.errors import MAX_SAME_KEY_ATTEMPTS, classify
from core.key_rotator import KeyRotator

logger = logging.getLogger(__name__)


class OpenAICompatClient:
    def __init__(self, key_rotator: KeyRotator, model: str, base_url: str,
                 timeout_seconds: float = 90.0):
        self.rotator = key_rotator
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout_seconds)

    async def translate_chunk(self, prompt: str, on_attempt=None) -> str:
        """on_attempt(attempt, key_idx): callback trước mỗi lần gọi HTTP (để UI hiện tiến độ)."""
        self.rotator.start_chunk_attempt()
        same_key_tries = 0

        while True:
            key = self.rotator.get_current_key()
            url = f"{self.base_url}/chat/completions"
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
            }
            headers = {"Authorization": f"Bearer {key}"}
            if on_attempt:
                on_attempt(same_key_tries + 1, self.rotator.current_idx)
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload, headers=headers)

                    if resp.status_code == 429:
                        same_key_tries = 0
                        nxt = self.rotator.try_next_key()
                        if nxt is not None:
                            logger.warning("⚠️ Key OpenAI-compat bị 429, đổi key...")
                            continue
                        raise RuntimeError(
                            "❌ TẤT CẢ OPENAI-COMPAT KEY ĐỀU 429! Chạy lại sau ít phút."
                        )

                    resp.raise_for_status()
                    data = resp.json()
                    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                    if not text or not text.strip():
                        raise ValueError("AI không trả về nội dung (response rỗng)!")
                    return text

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                same_key_tries += 1
                if same_key_tries < MAX_SAME_KEY_ATTEMPTS:
                    logger.warning(f"⚠️ Lỗi tạm thời, thử lại cùng key ({same_key_tries + 1}/{MAX_SAME_KEY_ATTEMPTS})...")
                    continue
                if isinstance(e, httpx.ConnectError):
                    raise ConnectionError("❌ LỖI KẾT NỐI tới OpenAI-compatible endpoint!")
                raise TimeoutError(f"❌ QUÁ THỜI GIAN CHỜ ({self.timeout}s)! AI không phản hồi kịp.")
            except httpx.HTTPStatusError as e:
                if classify(status_code=e.response.status_code) == "retry_same":
                    same_key_tries += 1
                    if same_key_tries < MAX_SAME_KEY_ATTEMPTS:
                        logger.warning(f"⚠️ OpenAI-compat {e.response.status_code}, thử lại cùng key...")
                        continue
                raise RuntimeError(
                    f"❌ LỖI TỪ OPENAI-COMPAT (Mã HTTP {e.response.status_code}): {e.response.text}"
                )
