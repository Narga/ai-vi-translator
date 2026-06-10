# Kế Hoạch: Refresh dự án, refactor HTML template, sửa lỗi chọn provider

> **Ngày tạo:** 2026-06-08  
> **Cập nhật:** 2026-06-09 — Phase 1 viết lại thành chỉ dẫn chính xác, tách Phase 1B/1C ra kế hoạch riêng  
> **Trạng thái:** ✅ ĐÃ HOÀN THÀNH (Phase 1-3 committed trong v7.4.0)  
> **Phạm vi Phase 1:** CHỈ sửa `plugins/spellcheck/spellchecker.py` + unit test mới  
> **Phạm vi tổng thể:** WebUI project manager, frontend render JS, provider-aware translation/spellcheck runtime, legacy UI route retirement (Phase 1B), provider helper normalization (Phase 1C)  
> **Log tham chiếu:** attachment `pasted-text.txt` lúc 23:06:06-23:06:23

---

## 0. Tóm tắt điều tra ban đầu

### Triệu chứng từ log

Khi người dùng chọn provider khác Gemini, hệ thống vẫn gọi:

- `POST https://generativelanguage.googleapis.com/v1beta/models/mimo-v2.5-pro:generateContent`
- Lỗi `API_KEY_INVALID` từ `googleapis.com`
- Log runtime có dòng `AFC is enabled...`, đây là hành vi của Gemini SDK

Điều này xảy ra cả ở tính năng dịch dự án (Translation) và soát lỗi chính tả (Spellcheck).

### Root cause nghi vấn chính

#### 1. Đối với Dịch thuật (Translation):
Luồng `POST /api/projects/<slug>/translate` đi qua:
`webui/routes/projects.py:translate_project_file` -> Worker `_project_translate_worker` -> `TranslateProjectFilesUseCase` -> `TranslationExecutor` -> `robust_translate` -> `plugins/translation/translator.py:_get_client` -> `GenAIClient`

Các điểm lệch provider:
- `translate_project_file` luôn gọi `load_gemini_keys()`, không đọc active provider.
- `TranslationExecutor` chỉ nhận `api_keys`, không nhận `provider_type`, `base_url`, hoặc provider config.
- `robust_translate/_call_api/_get_client` hard-code `GenAIClient`.
- `config["model_name"]` dùng `data.get("model", get_default_model())`; `get_default_model()` vẫn đọc `config/app.ini` thay vì active provider default model.

#### 2. Đối với Soát lỗi chính tả (Spellcheck):
Luồng `POST /api/projects/<slug>/spellcheck` đi qua:
`webui/routes/projects.py:spellcheck_project_file` -> Worker `_project_spellcheck_worker` -> `SpellcheckProjectFilesUseCase` -> `SpellcheckExecutor` -> `plugins/spellcheck/spellchecker.py:spellcheck_chunk` -> `GenAIClient`

Đánh giá sau phần cập nhật hiện tại:

- `spellcheck_project_file` đã được cập nhật đúng hướng: worker đọc `ProviderService.get_active_provider_config()`, chọn key theo `provider_type`, điền `config["provider_type"]`, `config["base_url"]`, và điền `model_name` từ default model của active provider khi request không gửi model.
- `SpellcheckProjectFilesUseCase` và `SpellcheckExecutor` giữ nguyên `config` và truyền xuống `spellcheck_chunk`, nên dữ liệu provider đã đi tới tầng thấp nhất.
- Điểm gãy còn lại nằm ở `plugins/spellcheck/spellchecker.py`: file này vẫn import `GenAIClient` và `spellcheck_chunk()` vẫn khởi tạo trực tiếp `GenAIClient(api_key=api_key)`. Vì vậy dù `config["provider_type"] == "openai"` và key/base_url đã đúng, runtime vẫn dùng Gemini SDK để gửi request.
- Đây là root cause trực tiếp khiến luồng Kiểm chính tả vẫn có thể gọi `generativelanguage.googleapis.com` sau khi route/worker đã được sửa.

Kết luận: Phần route/provider selection của Spellcheck đã đúng hướng nhưng chưa đủ. Cần sửa tầng client dispatch trong `plugins/spellcheck/spellchecker.py` để tôn trọng `provider_type` và `base_url`.

### Ghi chú GitNexus

Đã dùng GitNexus query để tìm luồng provider/project, nhưng index cảnh báo:

`FTS indexes missing - keyword search degraded. Run: gitnexus analyze --repair-fts (or gitnexus analyze --force)`

Trước khi sửa code, cần chạy impact analysis theo AGENTS.md trên các symbol sẽ chỉnh. Nếu cần truy vấn graph tốt hơn, chạy `npx gitnexus analyze --repair-fts` trước.

### Rà soát caller bằng GitNexus

Kết quả rà soát hiện tại để phục vụ kế hoạch loại bỏ fallback:

1. `plugins/spellcheck/spellchecker.py:spellcheck_chunk`
   - Caller trực tiếp duy nhất theo GitNexus:
     - `core/spellcheck_executor.py:SpellcheckExecutor.execute`
   - Caller gián tiếp/user-facing:
     - `webui/routes/projects.py:_project_spellcheck_worker`
     - `webui/routes/projects.py:spellcheck_project_file`
   - Kết luận:
     - Không có nhiều caller rải rác. Việc loại bỏ fallback ở `spellcheck_chunk` có thể làm rất dứt điểm mà không cần giữ hành vi mơ hồ cho nhiều entrypoint khác nhau.

2. Luồng project Translation/Spellcheck trong `webui/routes/projects.py`
   - Cả `translate_project_file` và `spellcheck_project_file` hiện đã đi theo hướng provider-aware ở tầng worker:
     - đọc `ProviderService.get_active_provider_config()`
     - chọn key theo `provider_type`
     - đẩy `provider_type/base_url/model_name` vào `config`
   - Kết luận:
     - Hai luồng project này là ứng viên tốt nhất để áp dụng chính sách `strict no-fallback`.

3. Luồng legacy còn sót cần lưu ý
   - `webui/routes/translation.py:translate_worker`
     - vẫn gọi `ApiKeyService.load_gemini_keys()`
     - vẫn dùng config/model mặc định nghiêng Gemini
   - `webui/routes/translation.py:start_translation`
     - default model vẫn là `gemini-3-flash-preview`
   - `webui/routes/translation.py:translate_text`
     - gọi `load_api_keys()` thay vì active provider selection, nên đây chưa phải strict provider-aware flow
   - `webui/helpers.py:get_default_model`
     - còn được gọi từ nhiều nơi, bao gồm `translate_project_file`, `spellcheck_project_file`, `settings.py`, `translation.py`, `summarize_project`
   - Kết luận:
     - Nếu muốn loại bỏ fallback hoàn toàn trên toàn ứng dụng, không thể chỉ sửa `spellcheck_chunk`; cần xử lý cả `webui/routes/translation.py` và chuẩn hóa lại semantics của `get_default_model()`.

---

## 1. Mục tiêu

1. Thêm nút **Làm mới** cạnh nút **Nhập dự án** trong khối **Quản lý dự án** để reload danh sách dự án, đặc biệt sau restore từ archive.
2. Refactor toàn bộ render HTML bằng string (`innerHTML = '<div>...'`, `map(...).join('')`, template literals chứa HTML) trong JavaScript sang HTML `<template>` chuẩn, ưu tiên các vùng render danh sách/card/modal.
3. Tìm root cause, sửa và verify lỗi chọn OpenAI-compatible provider nhưng runtime dịch thuật và soát lỗi chính tả (spellcheck) vẫn gọi Gemini.
4. Siết toàn bộ UI theo active provider, loại bỏ chỗ dùng route/provider flow cũ trong WebUI.
5. Chuẩn hóa kiến trúc provider và xóa hẳn semantics fallback khỏi helper dùng chung.

---

## 2. Thứ tự ưu tiên đề xuất

### Phase 1 - Sửa provider routing trước

Lý do: Đây là lỗi chức năng trực tiếp, có thể gây gọi sai API/key và retry nhiều lần.

### Phase 1B - Siết toàn bộ UI và dọn legacy routes

Lý do: Nếu chỉ sửa project flow mà UI vẫn còn gọi route cũ, hành vi provider sẽ tiếp tục không nhất quán.

### Phase 1C - Chuẩn hóa helper/provider architecture

Lý do: Cần xóa tận gốc semantics fallback ở helper dùng chung để các route mới không bị kéo về logic cũ.

### Phase 2 - Thêm nút Làm mới

Lý do: Nhỏ, ít rủi ro, giúp người dùng tự đồng bộ danh sách sau restore/import/archive.

### Phase 3 - HTML `<template>` refactor

Lý do: Refactor diện rộng, nên làm sau khi provider bug đã có test bảo vệ để tránh trộn rủi ro.

---

## 3. Phase 1 - Sửa lỗi provider bị ép về Gemini cho Dịch thuật & Soát lỗi chính tả

### 3.1. Impact analysis bắt buộc trước khi sửa

Chạy GitN### 3.2. Thiết kế fix — CHỈ SỬA 1 FILE DUY NHẤT

> [!IMPORTANT]
> **Phạm vi thay đổi Phase 1:** CHỈ SỬA `plugins/spellcheck/spellchecker.py`.
> KHÔNG sửa `webui/routes/projects.py` — worker đã đúng.
> KHÔNG sửa `core/spellcheck_executor.py` — nó truyền `config` nguyên vẹn.
> KHÔNG sửa `plugins/translation/translator.py` — đã sửa xong ở phiên trước.
> KHÔNG sửa bất kỳ file nào khác trong Phase 1.

#### Lý do chỉ cần sửa 1 file

Luồng dữ liệu hiện tại đã đúng từ route đến executor:

```
_project_spellcheck_worker (projects.py:1388-1430)
  → đọc ProviderService.get_active_provider_config()  ✅
  → điền config["provider_type"], config["base_url"]   ✅
  → điền config["model_name"] từ active provider       ✅
  → truyền config xuống SpellcheckProjectFilesUseCase   ✅
    → SpellcheckExecutor(api_keys, config)              ✅
      → spellcheck_chunk(text, prompt, api_manager, config)
        → GenAIClient(api_key=api_key)  ❌ BUG Ở ĐÂY
```

Chỉ cần sửa `spellcheck_chunk()` để nó đọc `config["provider_type"]` và tạo đúng client.

### 3.3. Code thay thế hoàn chỉnh cho `plugins/spellcheck/spellchecker.py`

Thay **TOÀN BỘ NỘI DUNG** file bằng code dưới đây:

```python
# plugins/spellcheck/spellchecker.py
import logging
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cache client theo (provider_type, api_key, base_url, model_name)
# để tránh khởi tạo lại client mỗi chunk
_client_cache: Dict[str, Any] = {}


def _get_client(api_key: str, config: Dict[str, Any]) -> Any:
    """
    Lấy hoặc tạo Client (GenAI hoặc OpenAI) cho API key (có cache).
    Pattern giống plugins/translation/translator.py:_get_client.

    Args:
        api_key: API key
        config: Dict chứa provider_type, model_name, base_url, thinking_level

    Returns:
        Client instance (GenAIClient hoặc OpenAIClient)
    """
    global _client_cache

    provider_type = config.get("provider_type", "gemini")
    base_url = config.get("base_url") or ""
    default_model = config.get("model_name", "gemini-1.5-flash")
    thinking_level = config.get("thinking_level", "MEDIUM")

    # Cache key phân biệt đầy đủ để tránh dùng nhầm client
    cache_key = f"{provider_type}_{api_key}_{base_url}_{default_model}"

    if cache_key not in _client_cache:
        if provider_type == "openai":
            from services.openai_client import OpenAIClient
            _client_cache[cache_key] = OpenAIClient(
                api_key=api_key, base_url=base_url, default_model=default_model
            )
        else:
            from services.genai_client import GenAIClient
            _client_cache[cache_key] = GenAIClient(
                api_key=api_key, default_model=default_model, thinking_level=thinking_level
            )

    return _client_cache[cache_key]


def spellcheck_chunk(
    text: str,
    prompt: str,
    api_manager: Any,
    config: Dict[str, Any]
) -> Tuple[str, str, str]:
    """
    Gửi một đoạn văn bản đi soát lỗi chính tả.
    Hoàn toàn độc lập với dịch thuật.

    Returns:
        Tuple[result_text, status, api_key_used]
    """
    api_key = api_manager.get_next_available_key()
    if not api_key:
        return "", "no_api_key", ""

    # Cấu hình model
    model_name = config.get("model_name", "gemini-1.5-flash")
    temperature = config.get("temperature", 0.0)

    # Build prompt (Không thêm bất kỳ header ẩn nào liên quan đến dịch)
    full_prompt = f"{prompt}\n\n{text}"

    try:
        client = _get_client(api_key, config)
        result, status = client.generate_content(
            prompt=full_prompt,
            model=model_name,
            temperature=temperature
        )
        if status == "success" and result:
            return result.strip(), "success", api_key
        return "", status or "empty_response", api_key
    except Exception as e:
        logger.error(f"Lỗi Spellcheck API: {str(e)}")
        return "", str(e), api_key
```

### 3.4. Giải thích từng thay đổi so với file hiện tại

| Dòng cũ | Thay đổi | Lý do |
|----------|----------|-------|
| `from services.genai_client import GenAIClient` (dòng 4) | **XÓA** import trực tiếp ở đầu file | GenAIClient giờ được import lazy bên trong `_get_client` |
| (không có) | **THÊM** hàm `_get_client()` và `_client_cache` | Dispatch client theo `config["provider_type"]`, cache theo key đầy đủ |
| `client = GenAIClient(api_key=api_key)` (dòng 33) | **ĐỔI** thành `client = _get_client(api_key, config)` | Dùng provider-aware dispatch thay vì hard-code Gemini |

**Những gì KHÔNG đổi:**
- Signature hàm `spellcheck_chunk(text, prompt, api_manager, config)` → giữ nguyên
- Return type `Tuple[str, str, str]` → giữ nguyên
- Logic xử lý kết quả (`if status == "success"`) → giữ nguyên
- Cách build prompt (`full_prompt`) → giữ nguyên

### 3.5. Tại sao dùng `config.get("provider_type", "gemini")` thay vì raise lỗi

> [!WARNING]
> **KHÔNG dùng strict mode (raise lỗi khi thiếu provider_type) cho Phase 1.**
>
> Lý do: `spellcheck_chunk` có thể được gọi từ ngữ cảnh khác ngoài WebUI project flow trong tương lai. Dùng fallback `"gemini"` giữ backward compatibility hoàn toàn — giống hệt pattern đã chạy thành công ở `plugins/translation/translator.py:_get_client` dòng 44.
>
> Strict mode (Đề xuất 2, 3) sẽ được áp dụng trong kế hoạch riêng sau khi đã migrate toàn bộ caller.

### 3.6. Các file KHÔNG SỬA trong Phase 1

Xác nhận rõ để tránh sửa nhầm:

| File | Trạng thái | Lý do |
|------|-----------|-------|
| `webui/routes/projects.py` | ✅ ĐÃ ĐÚNG | `_project_spellcheck_worker` đã đọc `ProviderService`, điền `provider_type/base_url/model_name` vào config |
| `core/spellcheck_executor.py` | ✅ ĐÃ ĐÚNG | Truyền `self.config` nguyên vẹn xuống `spellcheck_chunk` |
| `backend/application/use_cases/spellcheck_project_files_use_case.py` | ✅ ĐÃ ĐÚNG | Truyền `self._config` nguyên vẹn xuống `SpellcheckExecutor` |
| `plugins/translation/translator.py` | ✅ ĐÃ SỬA | `_get_client` đã dispatch theo `provider_type` từ phiên trước |
| `webui/routes/translation.py` | ⏸️ CHƯA SỬA | Legacy route — nằm ngoài phạm vi Phase 1, sẽ xử lý trong kế hoạch riêng |
| `webui/helpers.py` | ⏸️ CHƯA SỬA | Helper cũ — nằm ngoài phạm vi Phase 1, sẽ xử lý trong kế hoạch riêng |

### 3.7. Unit test — tạo file mới `tests/unit/test_spellcheck_provider.py`

Tạo file test mới kiểm tra dispatch provider:

```python
# tests/unit/test_spellcheck_provider.py
# Unit tests cho spellcheck provider dispatch

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSpellcheckGetClient:
    """Test _get_client dispatch theo provider_type."""

    def setup_method(self):
        """Reset client cache trước mỗi test."""
        from plugins.spellcheck import spellchecker
        spellchecker._client_cache.clear()

    @patch("plugins.spellcheck.spellchecker.GenAIClient", autospec=True)
    def test_gemini_provider_creates_genai_client(self, mock_genai_cls):
        """Config provider_type=gemini phải tạo GenAIClient."""
        # Patch import path bên trong _get_client
        with patch("services.genai_client.GenAIClient", mock_genai_cls):
            from plugins.spellcheck.spellchecker import _get_client
            config = {"provider_type": "gemini", "model_name": "gemini-2.0-flash", "base_url": ""}
            _get_client("test-key", config)
            mock_genai_cls.assert_called_once_with(
                api_key="test-key", default_model="gemini-2.0-flash", thinking_level="MEDIUM"
            )

    @patch("services.openai_client.OpenAIClient", autospec=True)
    def test_openai_provider_creates_openai_client(self, mock_openai_cls):
        """Config provider_type=openai phải tạo OpenAIClient."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "base_url": "https://openrouter.ai/api/v1",
        }
        _get_client("test-openai-key", config)
        mock_openai_cls.assert_called_once_with(
            api_key="test-openai-key",
            base_url="https://openrouter.ai/api/v1",
            default_model="gpt-4o-mini",
        )

    @patch("services.openai_client.OpenAIClient", autospec=True)
    def test_openai_provider_does_not_create_genai(self, mock_openai_cls):
        """Config provider_type=openai KHÔNG được tạo GenAIClient."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {
            "provider_type": "openai",
            "model_name": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
        }
        with patch("services.genai_client.GenAIClient") as mock_genai_cls:
            _get_client("test-key", config)
            mock_genai_cls.assert_not_called()

    def test_default_provider_type_is_gemini(self):
        """Khi config thiếu provider_type, mặc định là gemini."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {"model_name": "gemini-2.0-flash"}
        with patch("services.genai_client.GenAIClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = _get_client("test-key", config)
            mock_cls.assert_called_once()

    def test_client_cache_reuse(self):
        """Gọi _get_client 2 lần với cùng config phải trả cùng instance."""
        from plugins.spellcheck.spellchecker import _get_client
        config = {"provider_type": "gemini", "model_name": "gemini-2.0-flash"}
        with patch("services.genai_client.GenAIClient") as mock_cls:
            mock_cls.return_value = MagicMock()
            client1 = _get_client("key1", config)
            client2 = _get_client("key1", config)
            assert client1 is client2
            assert mock_cls.call_count == 1  # Chỉ tạo 1 lần

    def test_client_cache_different_provider(self):
        """Cùng key nhưng khác provider_type phải tạo client khác."""
        from plugins.spellcheck.spellchecker import _get_client
        with patch("services.genai_client.GenAIClient") as mock_genai:
            mock_genai.return_value = MagicMock()
            with patch("services.openai_client.OpenAIClient") as mock_openai:
                mock_openai.return_value = MagicMock()
                c1 = _get_client("key1", {"provider_type": "gemini", "model_name": "m1"})
                c2 = _get_client("key1", {"provider_type": "openai", "model_name": "m1", "base_url": "http://x"})
                assert c1 is not c2


class TestSpellcheckChunkInterface:
    """Test spellcheck_chunk giữ nguyên interface."""

    def test_import(self):
        """Test import spellcheck_chunk."""
        from plugins.spellcheck.spellchecker import spellcheck_chunk
        assert callable(spellcheck_chunk)

    def test_return_type_on_no_key(self):
        """Khi không có key, trả Tuple[str, str, str]."""
        from plugins.spellcheck.spellchecker import spellcheck_chunk
        mock_manager = MagicMock()
        mock_manager.get_next_available_key.return_value = None
        result = spellcheck_chunk("text", "prompt", mock_manager, {})
        assert isinstance(result, tuple)
        assert len(result) == 3
        assert result[1] == "no_api_key"
```

### 3.8. Lệnh thực thi — chạy theo đúng thứ tự

**Bước 1: Chạy test hiện tại để đảm bảo baseline xanh**

```bash
pytest tests/unit/test_helpers.py::TestCoreImports::test_import_spellcheck_executor -v
```

Expected: `PASSED`

**Bước 2: Ghi đè `plugins/spellcheck/spellchecker.py` bằng code ở mục 3.3**

Dùng `write_to_file` với `Overwrite=true` cho file `plugins/spellcheck/spellchecker.py`.

**Bước 3: Tạo file test mới `tests/unit/test_spellcheck_provider.py` bằng code ở mục 3.7**

Dùng `write_to_file` cho file `tests/unit/test_spellcheck_provider.py`.

**Bước 4: Chạy test mới**

```bash
pytest tests/unit/test_spellcheck_provider.py -v
```

Expected: Tất cả `PASSED`

**Bước 5: Chạy regression test cũ**

```bash
pytest tests/unit/test_helpers.py tests/unit/test_provider_services.py tests/unit/test_translate_use_case.py -v
```

Expected: Tất cả `PASSED` — không test nào bị vỡ

**Bước 6: Xóa import `ApiKeyService` không còn dùng trong `spellcheck_project_file`**

Trong `webui/routes/projects.py`, dòng 1343 có:
```python
    from backend.infrastructure.config.api_key_service import ApiKeyService
```

Xóa dòng này vì `spellcheck_project_file` không còn dùng `ApiKeyService` — worker đã dùng `ProviderService` trực tiếp. Nếu dòng này vẫn tồn tại, nó chỉ gây import thừa, không gây lỗi, nên có thể bỏ qua nếu không chắc chắn.

**Bước 7: Verify bằng `gitnexus_detect_changes`**

```bash
gitnexus_detect_changes(scope="all")
```

Expected: Chỉ 2 file thay đổi:
- `plugins/spellcheck/spellchecker.py` (modified)
- `tests/unit/test_spellcheck_provider.py` (new)

Nếu xuất hiện file khác → DỪNG LẠI, kiểm tra lại.

### 3.9. Verify thủ công

1. Tạo/đặt `config/providers.json` có:
   - `gemini-default` với key giả hoặc cũ
   - OpenAI-compatible provider active với key/base_url test
2. Chọn OpenAI provider trong UI, chọn model OpenAI.
3. Dịch một file project nhỏ và Soát lỗi một file project nhỏ.
4. Kiểm tra log:
   - Không có `generativelanguage.googleapis.com` trong cả 2 tiến trình.
   - Không có `AFC is enabled`.
   - Có log từ `OpenAIClient` hoặc request tới OpenAI-compatible base URL.
5. Chuyển lại Gemini và dịch/soát lỗi thử để bảo toàn flow cũ.

---

## 3A. Phase 1B & 1C — TÁCH THÀNH KẾ HOẠCH RIÊNG

> [!CAUTION]
> **Phase 1B (siết legacy routes) và Phase 1C (chuẩn hóa helper) CHƯA ĐƯỢC TRIỂN KHAI trong kế hoạch này.**
>
> Lý do:
> - Phase 1B xóa legacy routes (`/api/translate`, `/api/provider`) sẽ **làm vỡ nút Dịch ở workspace mặc định** và **radio chuyển provider** nếu frontend chưa migrate xong.
> - Phase 1C đổi semantics `get_default_model()` sẽ **ảnh hưởng 8+ caller** bao gồm `summarize_project`, `get_available_gemini_models`, settings routes.
>
> **Điều kiện để mở Phase 1B/1C:**
> 1. Phase 1 đã deploy và verify xong
> 2. Tạo kế hoạch riêng cho Phase 1B với sub-steps có gate kiểm tra
> 3. Mỗi sub-step phải có lệnh `rg` verify caller trước khi xóa route
> 4. Smoke test UI giữa mỗi sub-step
>
> Tài liệu phân tích rủi ro chi tiết Phase 1B/1C đã được lưu riêng để tham khảo khi lập kế hoạch sau.

Các thông tin điều tra về legacy routes, caller inventory, helper semantics vẫn giữ nguyên trong tài liệu này (mục 3A.1 → 3B.4 phía dưới) để làm tài liệu tham khảo khi lập kế hoạch Phase 1B/1C.

---

## 4. Phase 2 - Nút Làm mới danh sách dự án

### 4.1. Hiện trạng

Trong `webui/templates/partials/tab_projects.html`, khối **Quản lý dự án** đang có nút:

- `Nhập dự án` với `onclick="document.querySelector('[data-tab=archive]').click()"`

Danh sách dự án render bằng:

- `ProjectManager.loadProjectCards()`

Restore archive hiện gọi:

- `ProjectManager.restoreProject(filename)`
- Sau success có `ApiClient.loadArchives()`
- Có `ProjectManager.loadProjectCards()`, nhưng nếu người dùng đang ở archive tab hoặc UI chưa đồng bộ thì cần nút refresh thủ công tại tab project.

### 4.2. Thiết kế UI

Thêm nút **Làm mới** cạnh **Nhập dự án**:

- Vị trí: `tab_projects.html`, `.flex gap-2` trong header cột phải.
- Hành vi: gọi `ProjectManager.refreshProjectCards()`.
- Text: `↻ Làm mới` hoặc icon hiện có nếu chuẩn hóa sau.
- Trạng thái loading:
  - Disable button trong lúc fetch.
  - Đổi text tạm thành `Đang tải...`.
  - Toast success/error ngắn.

### 4.3. Thiết kế JS

Thêm method:

- `ProjectManager.refreshProjectCards(options = {})`
  - Gọi `loadProjectCards()`.
  - Tùy chọn `{ silent: true }` cho nơi khác gọi không toast.

Nên refactor nhẹ `loadProjectCards()` sang async để refresh có thể await:

- `async loadProjectCards()`
- Throw/catch rõ trong method.

Không bắt buộc nhưng nên cập nhật các nơi sau dùng refresh/silent:

- Sau `importProject()`
- Sau `restoreProject()`
- Sau archive/delete project

### 4.4. Verify

1. Mở tab Quản lý dự án.
2. Bấm **Làm mới**:
   - Danh sách reload.
   - Không mất layout.
   - Empty state vẫn đúng.
3. Restore một archive.
4. Quay lại tab Quản lý dự án, bấm **Làm mới**, project xuất hiện.
5. Network tab có `GET /api/projects`.

---

## 5. Phase 3 - Refactor HTML string sang `<template>`

### 5.1. Phạm vi cần quét

Quét toàn bộ JavaScript, loại trừ vendor:

```bash
rg -n "innerHTML|insertAdjacentHTML|outerHTML|map\\(.*=>|`\\s*<|'<[a-zA-Z]" webui/static/js -g '!alpine*.js'
```

Các file đã thấy có HTML string đáng chú ý:

- `webui/static/js/project-manager.js`
- `webui/static/js/api-client.js`
- `webui/static/js/prompt-manager.js`
- `webui/static/js/editor-component.js`
- `webui/static/js/translation-worker.js`

Không refactor các trường hợp chỉ đổi text button đơn giản nếu có thể thay bằng `textContent` hoặc class loading.

### 5.2. Nguyên tắc refactor

1. Mỗi repeated item dùng một `<template id="...">` trong partial HTML liên quan.
2. JS clone bằng:
   - `const node = template.content.firstElementChild.cloneNode(true)`
   - Fill text bằng `textContent`
   - Fill attributes bằng `dataset`, `href`, `value`, `checked`, `classList`
3. Không nhúng user data vào HTML string.
4. Event handler:
   - Ưu tiên `addEventListener` trên clone.
   - Hoặc dùng event delegation ở container nếu list lớn.
5. Empty/error/loading states:
   - Dùng template riêng hoặc helper tạo node bằng DOM API.
6. Xóa dần inline `onclick` trong dynamic HTML; static HTML có thể để lại cho phase riêng nếu muốn giữ scope.

### 5.3. Template đề xuất

Trong `tab_projects.html`:

- `#tpl-project-card`
- `#tpl-project-empty-state`
- `#tpl-project-error-state`
- `#tpl-file-item-compact`
- `#tpl-translated-file-item`
- `#tpl-spellchecked-file-item`

Trong `tab_archive.html`:

- `#tpl-archive-row`
- `#tpl-archive-empty-row`
- `#tpl-archive-error-row`

Trong `tab_prompts.html` hoặc `index.html` nếu global:

- `#tpl-prompt-genre-card`
- `#tpl-prompt-empty-state`

Trong `modals.html` hoặc gần editor:

- `#tpl-diff-overlay`

### 5.4. Helper JS đề xuất

Tạo helper nhỏ trong `ui-helpers.js` hoặc file riêng:

- `UiHelpers.cloneTemplate(id)`
- `UiHelpers.replaceChildren(container, nodes)`
- `UiHelpers.setHidden(el, hidden)`
- `UiHelpers.createStateNode(message, className)`

Giữ helper nhỏ, không tạo framework riêng.

### 5.5. Thứ tự refactor an toàn

1. `ProjectManager.loadProjectCards()`
   - Card dự án là nơi có user content và nhiều inline HTML.
2. Archive list trong `ApiClient.loadArchives()`
   - Có restore/delete/download actions.
3. Project file lists:
   - `renderPmFileList`
   - `renderPmTranslatedList`
   - `renderPmSpellcheckFileList`
   - `renderPmSpellcheckedList`
4. Prompt manager:
   - Genre/library lists.
5. Editor overlay/modal:
   - `EditorComponent.showDiffView` nếu đang dựng overlay bằng string.
6. Button loading states:
   - Chuyển từ `btn.innerHTML = '...'` sang DOM/CSS spinner hoặc `textContent`.

### 5.6. Test/verify frontend

1. Smoke test bằng trình duyệt:
   - Load app.
   - Tab Quản lý dự án render project cards.
   - Empty state render đúng khi không có project.
   - Mở project, file list render đúng.
   - Chọn checkbox, rename/delete action vẫn hoạt động.
   - Archive tab restore/delete/download vẫn hoạt động.
2. Security regression:
   - Project title/author/description chứa `<script>` hoặc `<img onerror=...>` chỉ hiển thị text, không execute.
3. Performance sanity:
   - Với nhiều project/files, render không bị giật đáng kể.
4. Visual:
   - Không lệch layout, không mất class active/status.

---

## 6. Kiểm thử tổng hợp sau khi hoàn thành

Chạy:

```bash
pytest
```

Nếu test toàn bộ quá lâu, tối thiểu:

```bash
pytest tests/unit/test_provider_services.py tests/unit/test_translate_use_case.py tests/smoke/test_webui_app_factory.py
```

Sau mọi code change và trước commit:

```bash
gitnexus_detect_changes(scope="all")
```

Nếu commit xong và cần cập nhật index:

```bash
npx gitnexus analyze
```

Nếu trước đó `.gitnexus/meta.json` có `stats.embeddings > 0`, dùng:

```bash
npx gitnexus analyze --embeddings
```

---

## 7. Rủi ro và cách giảm rủi ro

### Provider fix

Rủi ro:

- CLI hoặc old translation tab đang phụ thuộc mặc định Gemini.
- Cache key hiện chứa model/prompt nhưng chưa chắc chứa provider/base_url.
- OpenAI-compatible có nhiều base URL/model format khác nhau.

Giảm rủi ro:

- Default `provider_type="gemini"` nếu thiếu config.
- Thêm provider/base_url vào cache key nếu cache hiện chưa phân biệt đủ.
- Mock client trong unit test để không gọi network.

### Template refactor

Rủi ro:

- Mất event handler inline.
- Mất trạng thái checkbox/active item.
- Template đặt sai partial nên JS không tìm thấy khi tab chưa render.

Giảm rủi ro:

- Refactor từng cụm, verify ngay.
- Dùng event delegation ở container.
- Helper `cloneTemplate` throw lỗi rõ nếu thiếu template.

### Nút Làm mới

Rủi ro thấp:

- Nếu `loadProjectCards()` vẫn promise chain và không return promise, loading state khó chính xác.

Giảm rủi ro:

- Chuyển `loadProjectCards()` sang async hoặc return fetch promise.

---

## 8. Definition of Done

- Có nút **Làm mới** cạnh **Nhập dự án** trong tab Quản lý dự án.
- Bấm **Làm mới** gọi `GET /api/projects` and cập nhật danh sách.
- Restore archive xong có thể thấy project mới sau reload/refresh.
- Active OpenAI-compatible provider không còn gọi Gemini endpoint đối với cả luồng dịch thuật và soát lỗi chính tả.
- Active Gemini provider vẫn dịch được và soát lỗi được như trước.
- Các render list/card chính không còn dựng HTML bằng string nối trực tiếp; dùng `<template>` + DOM API.
- Test unit/smoke liên quan pass.
- `gitnexus_detect_changes(scope="all")` xác nhận phạm vi thay đổi đúng kỳ vọng trước commit.
