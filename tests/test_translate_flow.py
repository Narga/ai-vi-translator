"""Integration luồng dịch 1 chunk: retry/xoay-key/dừng-ngay qua cả 2 client.
Không gọi mạng thật (patch httpx.AsyncClient.post)."""

import asyncio

import httpx
import pytest
from unittest.mock import AsyncMock, patch

from core.ai_client import GeminiClient
from core.key_rotator import KeyRotator
from core.openai_client import OpenAICompatClient


def _gemini_ok(text="Bản dịch Việt có dấu: tiếng Việt"):
    return httpx.Response(
        status_code=200,
        json={"candidates": [{"content": {"parts": [{"text": text}]}}]},
        request=httpx.Request("POST", "http://test"),
    )


def _openai_ok(text="Bản dịch Việt"):
    return httpx.Response(
        status_code=200,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", "http://test"),
    )


def _status(code):
    return httpx.Response(status_code=code, text="err",
                          request=httpx.Request("POST", "http://test"))


def run(coro):
    return asyncio.run(coro)


def test_timeout_roi_thanh_cong_va_bao_attempt():
    async def go():
        seen = []
        client = GeminiClient(KeyRotator(["K1"]), timeout_seconds=5)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as m:
            m.side_effect = [httpx.TimeoutException("chậm"), _gemini_ok()]
            out = await client.translate_chunk("Hi", on_attempt=lambda a, k: seen.append((a, k)))
        return out, m.call_count, seen

    out, calls, seen = run(go())
    assert "tiếng Việt" in out and calls == 2 and seen == [(1, 0), (2, 0)]


def test_500_retry_roi_thanh_cong():
    async def go():
        client = OpenAICompatClient(KeyRotator(["K1"]), model="m", base_url="http://x")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as m:
            m.side_effect = [_status(500), _openai_ok()]
            return await client.translate_chunk("Hi"), m.call_count

    out, calls = run(go())
    assert out == "Bản dịch Việt" and calls == 2


def test_401_dung_ngay_khong_retry():
    async def go():
        client = GeminiClient(KeyRotator(["K1", "K2"]))
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as m:
            m.return_value = _status(401)
            with pytest.raises(RuntimeError, match="Mã HTTP 401"):
                await client.translate_chunk("Hi")
            return m.call_count

    assert run(go()) == 1  # fatal: đúng 1 attempt, không đổi key


def test_timeout_2_lan_lien_tiep_thi_dung():
    async def go():
        client = GeminiClient(KeyRotator(["K1"]), timeout_seconds=5)
        with patch("httpx.AsyncClient.post",
                   side_effect=httpx.TimeoutException("chậm")) as m:
            with pytest.raises(TimeoutError, match="QUÁ THỜI GIAN CHỜ"):
                await client.translate_chunk("Hi")
            return m.call_count

    assert run(go()) == 2  # hết budget 2 attempt/chunk


def test_429_doi_key_roi_thanh_cong():
    async def go():
        client = OpenAICompatClient(KeyRotator(["BAD", "GOOD"]), model="m", base_url="http://x")
        seen = []
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as m:
            m.side_effect = [_status(429), _openai_ok("OK key 2")]
            out = await client.translate_chunk("Hi", on_attempt=lambda a, k: seen.append((a, k)))
        return out, seen

    out, seen = run(go())
    assert out == "OK key 2" and seen == [(1, 0), (1, 1)]  # key mới reset attempt


def test_response_rong_dung_ngay():
    async def go():
        client = OpenAICompatClient(KeyRotator(["K1"]), model="m", base_url="http://x")
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as m:
            m.return_value = _openai_ok("   ")
            with pytest.raises(ValueError, match="rỗng"):
                await client.translate_chunk("Hi")
            return m.call_count

    assert run(go()) == 1


def test_attribute_maps_chunks_to_files():
    import main

    joined = "AAABBB"
    segs = [("a", 0, 3), ("b", 3, 6)]
    assert main._attribute(["AAA", "BBB"], joined, segs) == [["a"], ["b"]]
    assert main._attribute(["AAABBB"], joined, segs) == [["a", "b"]]
    assert main._attribute(["ZZZ"], joined, segs) == [[]]
