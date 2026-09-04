"""Mock test Gemini client. Dùng asyncio.run (stdlib) thay vì pytest-asyncio."""

import asyncio

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from core.ai_client import GeminiClient
from core.key_rotator import KeyRotator


def _resp(status=200, payload=None):
    return httpx.Response(
        status_code=status,
        json=payload or {"candidates": [{"content": {"parts": [{"text": "Bản dịch tiếng Việt"}]}}]},
        request=httpx.Request("POST", "http://test"),
    )


def test_successful_translation():
    async def go():
        client = GeminiClient(KeyRotator(["KEY_1"]))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _resp()
            return await client.translate_chunk("Hello")

    assert asyncio.run(go()) == "Bản dịch tiếng Việt"


def test_429_failover_to_next_key():
    async def go():
        client = GeminiClient(KeyRotator(["KEY_BAD", "KEY_GOOD"]))
        r429 = httpx.Response(status_code=429, request=httpx.Request("POST", "http://test"))
        ok = _resp(payload={"candidates": [{"content": {"parts": [{"text": "Thành công ở key 2"}]}}]})
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [r429, ok]
            return await client.translate_chunk("Hello")

    assert asyncio.run(go()) == "Thành công ở key 2"


def test_all_keys_429_exhausted():
    async def go():
        client = GeminiClient(KeyRotator(["KEY_1"]))
        r429 = httpx.Response(status_code=429, request=httpx.Request("POST", "http://test"))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = r429
            with pytest.raises(RuntimeError, match="TẤT CẢ API KEY ĐỀU BỊ LỖI 429"):
                await client.translate_chunk("Hello")

    asyncio.run(go())


def test_network_connect_error():
    async def go():
        client = GeminiClient(KeyRotator(["KEY_1"]))
        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Network down")):
            with pytest.raises(ConnectionError, match="LỖI KẾT NỐI MẠNG"):
                await client.translate_chunk("Hello")

    asyncio.run(go())


def test_empty_candidates_safety_block():
    async def go():
        client = GeminiClient(KeyRotator(["KEY_1"]))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _resp(payload={"candidates": []})
            with pytest.raises(ValueError, match="bộ lọc an toàn"):
                await client.translate_chunk("Hello")

    asyncio.run(go())
