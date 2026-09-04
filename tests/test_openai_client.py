"""Mock test OpenAI-compatible client. Dùng asyncio.run (stdlib)."""

import asyncio

import httpx
from unittest.mock import AsyncMock, patch

from core.key_rotator import KeyRotator
from core.openai_client import OpenAICompatClient


def _mk(text="ok"):
    return httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", "http://test"),
    )


def test_openai_success():
    async def go():
        c = OpenAICompatClient(KeyRotator(["K1"]), model="m", base_url="http://x")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as p:
            p.return_value = _mk("Bản dịch")
            return await c.translate_chunk("Hi")

    assert asyncio.run(go()) == "Bản dịch"


def test_openai_429_failover():
    async def go():
        c = OpenAICompatClient(KeyRotator(["BAD", "GOOD"]), model="m", base_url="http://x")
        r429 = httpx.Response(status_code=429, request=httpx.Request("POST", "http://test"))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as p:
            p.side_effect = [r429, _mk("ok2")]
            return await c.translate_chunk("Hi")

    assert asyncio.run(go()) == "ok2"
