"""Client Google Gemini qua REST thuần (httpx, zero SDK)."""

import asyncio
import httpx
import logging
from core.errors import MAX_SAME_KEY_ATTEMPTS, TranslateCancelled, classify
from core.key_rotator import KeyRotator

logger = logging.getLogger(__name__)


async def _post_or_abort(client, url, *, json=None, headers=None, abort=None):
    """POST có thể hủy GIỮA request: abort.set() -> cắt kết nối, raise TranslateCancelled.
    Không abort thì hành vi cũ. CancelledError (BaseException) không bị nuốt bởi
    các except httpx bên dưới."""
    task = asyncio.create_task(client.post(url, json=json, headers=headers))
    if abort is None:
        return await task
    while not task.done():
        if abort.is_set():
            task.cancel()
            raise TranslateCancelled("Đã hủy giữa request — kết nối đã cắt")
        await asyncio.sleep(0.05)
    return task.result()


class GeminiClient:
    def __init__(self, key_rotator: KeyRotator, model: str = "",
                 timeout_seconds: float = 90.0, thinking_budget: int | None = None):
        self.rotator = key_rotator
        self.model = model
        self.timeout = float(timeout_seconds)
        # None/OFF = bỏ hẳn thinkingConfig (dùng default API)
        self.thinking_budget = thinking_budget

    async def translate_chunk(self, prompt: str, on_attempt=None, abort=None) -> str:
        """on_attempt(attempt, key_idx): callback trước mỗi lần gọi HTTP.
        abort (threading.Event): hủy cả request đang bay, không chỉ giữa chunk."""
        self.rotator.start_chunk_attempt()
        same_key_tries = 0

        while True:
            current_key = self.rotator.get_current_key()
            url = (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent?key={current_key}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.3},
            }
            if self.thinking_budget:
                payload["generationConfig"]["thinkingConfig"] = {
                    "thinkingBudget": self.thinking_budget}
            if on_attempt:
                on_attempt(same_key_tries + 1, self.rotator.current_idx)

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await _post_or_abort(client, url, json=payload, abort=abort)

                    if resp.status_code == 429:
                        same_key_tries = 0
                        next_key = self.rotator.try_next_key()
                        if next_key is not None:
                            logger.warning("⚠️ Key hiện tại bị 429. Đang chuyển sang key tiếp theo...")
                            continue
                        raise RuntimeError(
                            "❌ TẤT CẢ API KEY ĐỀU BỊ LỖI 429 (RATE LIMIT)! Vui lòng chạy lại sau ít phút."
                        )

                    resp.raise_for_status()

                    try:
                        data = resp.json()
                        if not isinstance(data, dict):
                            raise ValueError("JSON response không phải object")
                        candidates = data.get("candidates", [])
                        first = candidates[0] if candidates else {}
                        parts = first.get("content", {}).get("parts", []) if isinstance(first, dict) else []
                        text = parts[0].get("text", "") if parts and isinstance(parts[0], dict) else ""
                    except (AttributeError, KeyError, TypeError, ValueError) as e:
                        raise ValueError(f"Cấu trúc response từ AI không hợp lệ ({type(e).__name__})")
                    if not candidates:
                        raise ValueError(
                            "AI không trả về kết quả nội dung (Có thể bị bộ lọc an toàn chặn)!"
                        )
                    if not text or not text.strip():
                        raise ValueError("AI trả về nội dung rỗng!")
                    return text

            except (httpx.ConnectError, httpx.TimeoutException) as e:
                same_key_tries += 1
                if same_key_tries < MAX_SAME_KEY_ATTEMPTS:
                    logger.warning(f"⚠️ Lỗi tạm thời, thử lại cùng key ({same_key_tries + 1}/{MAX_SAME_KEY_ATTEMPTS})...")
                    continue
                if isinstance(e, httpx.ConnectError):
                    raise ConnectionError(
                        "❌ LỖI KẾT NỐI MẠNG! Không thể kết nối tới Google Gemini. Vui lòng kiểm tra mạng."
                    )
                raise TimeoutError(f"❌ QUÁ THỜI GIAN CHỜ ({self.timeout}s)! AI không phản hồi kịp.")
            except httpx.HTTPStatusError as e:
                if classify(status_code=e.response.status_code) == "retry_same":
                    same_key_tries += 1
                    if same_key_tries < MAX_SAME_KEY_ATTEMPTS:
                        logger.warning(f"⚠️ Gemini {e.response.status_code}, thử lại cùng key...")
                        continue
                raise RuntimeError(
                    f"❌ LỖI TỪ GEMINI (Mã HTTP {e.response.status_code}): {e.response.text}"
                )
            except httpx.RequestError as e:
                raise ConnectionError(
                    f"❌ LỖI MẠNG ({type(e).__name__})! Không thể hoàn tất request tới AI."
                )
