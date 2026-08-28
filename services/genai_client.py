# services/genai_client.py - v4.0.0
# Tác giả: Narga
# Chức năng: Wrapper thống nhất cho Gemini API, hỗ trợ cả google-genai SDK mới và google-generativeai SDK cũ.

"""
GenAI Client - Lớp trừu tượng hóa cho Gemini API.

Hỗ trợ google-genai SDK.

Sử dụng:
    client = GenAIClient(api_key, sdk="google-genai")
    response = client.generate_content(prompt, model="<model-do-người-dùng-cấu-hình>")
"""

import logging
from typing import Optional, Dict, Any, Tuple
from enum import Enum


class SDKType(Enum):
    """Enum cho các loại SDK được hỗ trợ."""

    GOOGLE_GENAI = "google-genai"  # SDK mới (khuyến nghị)
    GOOGLE_GENERATIVEAI = "google-generativeai"  # SDK cũ (legacy)


class GenAIClient:
    """
    Wrapper cho google-genai SDK (Pure Python SDK).
    Tối ưu cho Gemini 3 Flash Preview.
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "",
        thinking_level: str = "MEDIUM",
    ):
        """
        Khởi tạo GenAI Client (chỉ hỗ trợ google-genai mới).

        Args:
            api_key (str): Gemini API key
            default_model (str): Model mặc định
            thinking_level (str): Mức độ thinking (MINIMAL/LOW/MEDIUM/HIGH)
        """
        self.api_key = api_key
        self.default_model = default_model
        self.thinking_level = thinking_level
        self.logger = logging.getLogger(__name__)

        # Khởi tạo client trực tiếp
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Khởi tạo google-genai client."""
        try:
            from google import genai

            self._client = genai.Client(api_key=self.api_key)
            self.logger.debug("✅ GenAI Client initialized")
        except ImportError:
            raise ImportError(
                "Thư viện 'google-genai' chưa được cài đặt. "
                "Vui lòng chạy: pip install google-genai"
            )

    def generate_content(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 1.0,  # Default for Gemini 3
        thinking_level: Optional[str] = None,
        **kwargs,
    ) -> Tuple[Optional[str], str]:
        """
        Sinh nội dung sử dụng google-genai SDK.

        Args:
            prompt (str): Prompt đầu vào
            model (str, optional): Model override
            temperature (float): Nhiệt độ (default 1.0)
            thinking_level (str, optional): Override thinking level

        Returns:
            Tuple[Optional[str], str]: (content, status)
        """
        model_name = model or self.default_model
        curr_thinking = (thinking_level or self.thinking_level or "MEDIUM").strip()

        try:
            generation_config: Dict[str, Any] = {
                "temperature": temperature,
            }

            # Kiểm tra tùy chọn OFF / NONE / DISABLED để tắt hẳn thinking_config
            is_thinking_off = curr_thinking.upper() in ("OFF", "NONE", "DISABLED", "FALSE", "0")

            if not is_thinking_off:
                generation_config["thinking_config"] = {"thinking_level": curr_thinking}

            response = self._client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=generation_config,  # type: ignore[arg-type]
            )

            if response and response.text:
                return response.text.strip(), "success"

            # Fallback: đọc parts thủ công (tránh bỏ sót khi response.text = None)
            if response and response.candidates:
                candidate = response.candidates[0]
                if candidate.content and candidate.content.parts:
                    # Ưu tiên lấy text part không phải thought
                    text_parts = [
                        p.text for p in candidate.content.parts
                        if p.text and not getattr(p, "thought", False)
                    ]
                    # Nếu không có text_parts riêng, lấy tất cả parts có chứa text
                    if not text_parts:
                        text_parts = [p.text for p in candidate.content.parts if p.text]

                    combined = "".join(text_parts).strip()
                    if combined:
                        self.logger.debug(
                            "response.text was None but parts fallback succeeded"
                        )
                        return combined, "success"

                    self.logger.warning(
                        f"response has {len(candidate.content.parts)} parts "
                        f"but all are empty. model={model_name}, thinking_off={is_thinking_off}"
                    )
            return None, "empty_response"

        except Exception as e:
            self.logger.error(f"GenAI Error: {e}")
            # Re-raise để translator.py xử lý chuyển key khi gặp 429/quota
            raise

    def get_sdk_info(self) -> Dict[str, Any]:
        """Trả về thông tin SDK."""
        return {
            "sdk": "google-genai",
            "model": self.default_model,
            "thinking": self.thinking_level,
        }

    def reconfigure(self, api_key: str) -> None:
        """Cấu hình lại API key."""
        self.api_key = api_key
        self._initialize_client()
