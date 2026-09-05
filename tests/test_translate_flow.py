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


def test_run_chunks_cancelled_between_chunks():
    import threading
    import main
    from core.errors import TranslateCancelled

    calls = []
    ev = threading.Event()

    class FakeClient:
        async def translate_chunk(self, prompt, on_attempt=None, abort=None):
            calls.append(prompt)
            if on_attempt:
                on_attempt(1, 0)
            ev.set()  # hủy ngay sau chunk đầu
            return "XONG:" + prompt

    async def go():
        with pytest.raises(TranslateCancelled):
            await main._run_chunks(FakeClient(), ["p1", "p2", "p3"], [[None]] * 3,
                                   0, 1, lambda e, p: None, cancel=ev)

    run(go())
    assert calls == ["p1"]  # dừng đúng sau chunk đầu, không chạy tiếp


def test_split_marked_by_file():
    import main

    text = "===== FILE: a.md =====\nNội dung A.\n\n===== FILE: b.md =====\nNội dung B."
    out, regs = main._split_marked(text, ["a.md", "b.md"])
    assert out == {"a.md": "Nội dung A.", "b.md": "Nội dung B."}
    assert len(regs) == 2
    assert main._split_marked("không marker gì", ["a.md"])[0] == {}
    # marker tên lạ bị bỏ qua, không crash
    out, _ = main._split_marked("===== FILE: stranger.md =====\nX.", ["a.md"])
    assert out == {}


def test_split_output_fallback_no_markers():
    import main

    outs = ["DỊCH A", "DỊCH B"]
    segs = [["a.md"], ["b.md"]]
    assert main._split_output(outs, segs, ["a.md", "b.md"]) == {"a.md": "DỊCH A", "b.md": "DỊCH B"}
    # marker thiếu 1 file -> file đó chỉ nhận chunk ngoài region file khác
    outs = ["===== FILE: a.md =====\nA1", "B1 không marker"]
    segs = [["a.md"], ["b.md"]]
    out = main._split_output(outs, segs, ["a.md", "b.md"])
    assert out["a.md"] == "A1\n\nB1 không marker" and out["b.md"] == ""


def test_abort_mid_request():
    import threading
    import time
    from core.ai_client import GeminiClient
    from core.errors import TranslateCancelled
    from core.key_rotator import KeyRotator

    async def slow_post(*a, **k):
        await asyncio.sleep(5)
        return _gemini_ok()

    async def go():
        import httpx
        from unittest.mock import AsyncMock, patch
        ev = threading.Event()
        client = GeminiClient(KeyRotator(["K1"]), timeout_seconds=30)
        async def trigger():
            await asyncio.sleep(0.1)
            ev.set()
        asyncio.ensure_future(trigger())
        t0 = time.monotonic()
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as m:
            m.side_effect = slow_post
            with pytest.raises(TranslateCancelled):
                await client.translate_chunk("Hi", abort=ev)
        return time.monotonic() - t0

    assert run(go()) < 2.0  # hủy tức thì, không chờ hết 5s
