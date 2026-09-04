"""Interface chung cho mọi AI provider (quy ước plugin provider)."""

from typing import Protocol


class AIClient(Protocol):
    async def translate_chunk(self, prompt: str) -> str: ...
