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


def test_malformed_shapes_map_to_value_error():
    bad_payloads = [
        [1, 2, 3],  # JSON non-object
        {"candidates": "not-a-list"},
        {"candidates": [{"content": {"parts": []}}]},
        {"candidates": [{"content": {"parts": [{"text": "   "}]}}]},  # whitespace-only
        {"candidates": [{"content": {"parts": ["raw-string"]}}]},
    ]

    async def go(payload):
        client = GeminiClient(KeyRotator(["K1"]))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = _resp(payload=payload)
            with pytest.raises(ValueError):
                await client.translate_chunk("Hello")

    for p in bad_payloads:
        asyncio.run(go(p))


def test_500_retries_exact_budget_then_raises():
    async def go():
        client = GeminiClient(KeyRotator(["K1"]))
        r500 = httpx.Response(status_code=500, text="err",
                              request=httpx.Request("POST", "http://test"))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [r500, _resp()]
            out = await client.translate_chunk("Hello")
            return out, mock_post.call_count

    out, calls = asyncio.run(go())
    assert out == "Bản dịch tiếng Việt" and calls == 2  # 1 lần đầu + 1 retry (budget=2)


def test_400_series_stop_immediately():
    async def go():
        client = GeminiClient(KeyRotator(["K1", "K2"]))
        r400 = httpx.Response(status_code=400, text="bad",
                              request=httpx.Request("POST", "http://test"))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = r400
            with pytest.raises(RuntimeError):
                await client.translate_chunk("Hello")
            return mock_post.call_count

    assert asyncio.run(go()) == 1


def test_generic_request_error_maps_to_connection_error():
    async def go():
        client = GeminiClient(KeyRotator(["K1"]))
        with patch("httpx.AsyncClient.post", side_effect=httpx.RemoteProtocolError("boom")):
            with pytest.raises(ConnectionError, match="LỖI MẠNG"):
                await client.translate_chunk("Hello")

    asyncio.run(go())


def test_error_messages_never_leak_key():
    async def go():
        key = "sk-SECRET-KEY-12345"
        client = GeminiClient(KeyRotator([key]))
        r500 = httpx.Response(status_code=500, text="err",
                              request=httpx.Request("POST", "http://test"))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [r500, r500, r500]
            try:
                await client.translate_chunk("Hello")
            except Exception as e:
                assert key not in str(e)
                return True
        return False

    assert asyncio.run(go())
