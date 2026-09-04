"""Client Google Gemini qua REST thuần (httpx, zero SDK)."""

import httpx
import logging
from core.key_rotator import KeyRotator

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, key_rotator: KeyRotator, model: str = "",
                 timeout_seconds: float = 90.0, thinking_budget: int | None = None):
        self.rotator = key_rotator
        self.model = model
        self.timeout = float(timeout_seconds)
        # None/OFF = bỏ hẳn thinkingConfig (dùng default API)
        self.thinking_budget = thinking_budget

    async def translate_chunk(self, prompt: str) -> str:
        self.rotator.start_chunk_attempt()

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

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(url, json=payload)

                    if resp.status_code == 429:
                        next_key = self.rotator.try_next_key()
                        if next_key is not None:
                            logger.warning("⚠️ Key hiện tại bị 429. Đang chuyển sang key tiếp theo...")
                            continue
                        raise RuntimeError(
                            "❌ TẤT CẢ API KEY ĐỀU BỊ LỖI 429 (RATE LIMIT)! Vui lòng chạy lại sau ít phút."
                        )

                    resp.raise_for_status()

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ValueError(
                            "AI không trả về kết quả nội dung (Có thể bị bộ lọc an toàn chặn)!"
                        )
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if not parts or "text" not in parts[0]:
                        raise ValueError("Cấu trúc response từ AI không chứa trường text!")
                    return parts[0]["text"]

            except httpx.ConnectError:
                raise ConnectionError(
                    "❌ LỖI KẾT NỐI MẠNG! Không thể kết nối tới Google Gemini. Vui lòng kiểm tra mạng."
                )
            except httpx.TimeoutException:
                raise TimeoutError(f"❌ QUÁ THỜI GIAN CHỜ ({self.timeout}s)! AI không phản hồi kịp.")
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"❌ LỖI TỪ GEMINI (Mã HTTP {e.response.status_code}): {e.response.text}"
                )
