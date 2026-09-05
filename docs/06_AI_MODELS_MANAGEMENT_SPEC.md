# ĐẶC TẢ KỸ THUẬT: QUẢN LÝ API KEYS, LẤY DANH SÁCH & CHỌN AI MODELS
*(AI Provider Management, Dynamic Model Listing & Selection Specification)*

---

## 1. TỔNG QUAN & NGUYÊN TẮC THIẾT KẾ

Hệ thống quản lý AI Provider chịu trách nhiệm cấu hình kết nối, bảo vệ khóa API và phân giải danh sách model phục vụ tác vụ dịch thuật và xử lý văn bản bằng AI (Google Gemini, OpenAI, OpenRouter, DeepSeek, Groq, Ollama...).

### 1.1. Ba bài toán cốt lõi
1. **Lưu trữ API Keys an toàn**: Hỗ trợ đa nhà cung cấp (multi-provider), mảng nhiều khóa (multi-key) cho Gemini để xoay vòng khi chạm hạn mức quota (HTTP 429), ghi file an toàn chống hỏng dữ liệu (atomic write), và che giấu khóa bí mật (key masking) khi trả dữ liệu về giao diện người dùng.
2. **Lấy danh sách Models động (Dynamic Model Listing)**: Tự động truy vấn trực tiếp đến API của nhà cung cấp để cập nhật các model mới nhất, áp dụng bộ lọc (loại bỏ model embedding/audio), bộ đệm Cache TTL 5 phút theo hàm băm thông tin xác thực (credential hash), và cơ chế dự phòng an toàn (fail-soft fallback) khi không có mạng.
3. **Chọn và Xác thực Model (Model Selection & Validation)**: Kiểm tra chéo chống nhầm lẫn namespace giữa các nhà cung cấp (cross-namespace validation), cho phép người dùng chọn từ danh sách hoặc tự nhập model tùy chỉnh (custom model), và lưu vết lựa chọn vào cấu hình làm model mặc định.

---

## 2. CẤU TRÚC DỮ LIỆU CHUẨN (`config/providers.json`)

File `config/providers.json` đóng vai trò là nguồn sự thật duy nhất (Single Source of Truth) cho toàn bộ thông tin nhà cung cấp:

```json
{
  "version": 1,
  "active_id": "gemini-default",
  "providers": [
    {
      "id": "gemini-default",
      "type": "gemini",
      "name": "Google Gemini",
      "api_keys": [
        "AIzaSyD-KEY-1...",
        "AIzaSyD-KEY-2..."
      ],
      "default_model": "gemini-2.5-flash"
    },
    {
      "id": "openrouter-main",
      "type": "openai",
      "name": "OpenRouter",
      "api_key": "sk-or-v1-...",
      "base_url": "https://openrouter.ai/api/v1",
      "default_model": "google/gemini-2.5-flash"
    },
    {
      "id": "local-ollama",
      "type": "openai",
      "name": "Local Ollama",
      "api_key": "",
      "base_url": "http://localhost:11434/v1",
      "default_model": "qwen2.5:7b"
    }
  ]
}
```

### Ý nghĩa các trường dữ liệu:
- `version`: Phiên bản cấu trúc schema (hỗ trợ migration nếu nâng cấp sau này).
- `active_id`: ID của provider đang được chọn làm mặc định cho các tác vụ hiện hành.
- `providers`: Mảng danh sách các provider:
  - `id`: Định danh duy nhất (chuỗi slug, chữ thường không dấu, ví dụ: `gemini-default`, `openrouter-1`).
  - `type`: Phân loại giao thức kết nối: `"gemini"` hoặc `"openai"`.
  - `name`: Tên hiển thị thân thiện trên UI.
  - `api_keys` (với Gemini): Danh sách các khóa API để xoay vòng tuần tự khi gặp lỗi 429.
  - `api_key` (với OpenAI): Chuỗi API key đơn lẻ.
  - `base_url`: Endpoint tùy biến của API (bắt buộc với OpenRouter, Groq, Ollama; để trống hoặc null nếu dùng OpenAI chính thống).
  - `default_model`: Tên model mà người dùng đã chọn để chạy.

---

## 3. LOGIC & GIẢI THUẬT CHI TIẾT

### 3.1. Quản lý & Lưu trữ API Keys an toàn

#### A. Kỹ thuật Ghi file nguyên tử (Atomic Write)
Để tránh trường hợp file cấu hình bị rỗng hoặc lỗi cú pháp JSON do tiến trình bị tắt đột ngột giữa lúc đang ghi:
1. Ghi toàn bộ dữ liệu cấu hình mới ra file tạm thời: `config/providers.json.tmp`.
2. Đọc lại file tạm và kiểm tra tính hợp lệ của schema (phải là JSON hợp lệ, trường `providers` phải là mảng, `active_id` phải tồn tại trong danh sách).
3. Nếu file `config/providers.json` hiện tại đang tồn tại, sao chép thành `config/providers.json.bak` để làm điểm khôi phục dự phòng.
4. Thực thi lệnh hoán đổi tệp nguyên tử `os.replace("config/providers.json.tmp", "config/providers.json")`.

#### B. Cơ chế Sentinel Protection (giữ key đang sửa — single-user, KHÔNG mask mặc định)
Trên WebUI keys hiện **đầy đủ** để sửa trực tiếp (manifesto §7 — không mask, không fingerprint).
Khi người dùng bấm nút "Lưu", backend (`update_provider_keys_and_model`) lưu nguyên danh sách đang sửa:
- Dòng bị xóa = xóa key; dòng trống bị bỏ qua.
- Không có chuyện "giữ key cũ khi gửi rỗng" — UI luôn gửi toàn bộ danh sách hiện tại.

#### C. Che giấu khóa (Key Masking — OPT-IN, mặc định TẮT)
`masked_providers(mask=False)`: mặc định trả FULL key. Chỉ khi gọi với `mask=True`
(mục đích log/share) mới che:
- Nếu độ dài chuỗi key $\le 8$: Trả về `****`.
- Nếu độ dài chuỗi key $> 8$: Trả về `4 ký tự đầu + "..." + 4 ký tự cuối`.

---

### 3.2. Lấy danh sách Models động (Dynamic Fetching & Caching)

#### A. Cơ chế Cache TTL kết hợp Credential Hashing
- Việc gửi yêu cầu lấy danh sách models liên tục gây chậm UI và tiêu tốn quota không cần thiết.
- **Thời gian sống của cache (TTL)**: 300 giây (5 phút).
- **Khóa Cache (Cache Key)**: `(provider_id, sha256(credentials))`
  - `credentials` được ghép từ: `api_keys + api_key + base_url`.
- **Cơ chế Tự động hủy cache (Auto-Invalidation)**: Khi người dùng đổi API key hoặc Base URL, giá trị SHA256 thay đổi $\rightarrow$ Khóa cache thay đổi $\rightarrow$ Lần gọi tiếp theo sẽ tự động truy vấn API mới mà không cần xóa cache thủ công.

#### B. Quy trình truy vấn Google Gemini
1. Lấy khóa đầu tiên trong danh sách `api_keys`. Nếu không có key, trả về danh sách fallback tĩnh.
2. Gửi yêu cầu HTTP GET:
   ```http
   GET https://generativelanguage.googleapis.com/v1beta/models?key={api_key}
   ```
3. Lọc danh sách trả về:
   - Loại bỏ tiền tố `models/` khỏi `name`.
   - Chỉ giữ lại các model có tên bắt đầu bằng `gemini-` hoặc `gemma-`.
   - Kiểm tra mảng `supportedGenerationMethods`: Bắt buộc phải chứa `"generateContent"` (loại bỏ các model embedding, imagen, aqa).
4. Sắp xếp danh sách theo thứ tự chữ cái giảm dần (đưa các phiên bản mới nhất như `gemini-2.5-*` lên đầu).

#### C. Quy trình truy vấn OpenAI-Compatible (OpenRouter, Groq, DeepSeek, Ollama...)
1. Xác định `base_url`: Nếu không cấu hình, mặc định dùng `https://api.openai.com/v1`.
2. Gửi yêu cầu HTTP GET:
   ```http
   GET {base_url}/models
   Authorization: Bearer {api_key}
   ```
3. Lấy mảng `data` từ JSON phản hồi và trích xuất trường `id` của từng model.
4. Với OpenRouter, có thể trích xuất thêm metadata: `name`, `context_length`, `pricing`, và cờ `is_free` (nếu model id chứa `:free`).

#### D. Xử lý dự phòng an toàn (Fail-Soft Fallback)
Khi kết nối API thất bại (mất mạng, key sai, endpoint 404, quota 429):
- Bắt ngoại lệ, không để ứng dụng crash.
- Trả về danh sách model tĩnh đã cấu hình sẵn (`FALLBACK_MODELS`).
- Đính kèm model hiện tại đang cấu hình (`default_model`) vào danh sách nếu chưa có.
- Trả về cờ `source: "fallback"` kèm chi tiết thông báo lỗi `error` để UI hiển thị cảnh báo nhẹ cho người dùng.

---

### 3.3. Lựa chọn & Xác thực Model (Model Validation)

#### A. Kiểm tra Namespace (Cross-Namespace Protection)
- **Với Provider type `gemini`**: Tên model bắt buộc phải bắt đầu bằng hoặc chứa `gemini-` hoặc `gemma-`. Từ chối nếu người dùng gõ `gpt-4o`, `claude-3-5`, v.v.
- **Với Provider type `openai` chuẩn (OpenAI, DeepSeek, Groq...)**: Không chấp nhận model bắt đầu bằng `gemini-` hoặc `gemma-` trực tiếp, trừ khi đi qua gateway tổng hợp như OpenRouter (có tiền tố `google/gemini-...`).

#### B. Hỗ trợ Tự do nhập Model (Custom Model Input)
- Giao diện cung cấp ô chọn `<input list="model-list">` (Datalist / Combobox) cho phép:
  1. Chọn nhanh từ danh sách dynamic fetch về.
  2. Tự nhập tên model bất kỳ (phục vụ trường hợp nhà cung cấp ra mắt model mới trong ngày mà API `/models` chưa kịp phản ánh).

#### C. Lưu vết lựa chọn
- Khi người dùng chọn hoặc đổi model, hệ thống cập nhật trường `default_model` của provider trong `providers.json`. Mọi tác vụ dịch sau đó sẽ đọc trực tiếp giá trị này.

---

## 4. MODULE TRIỂN KHAI HOÀN CHỈNH (PYTHON CODE)

Mã nguồn dưới đây là một module độc lập, hoàn chỉnh, có thể tích hợp trực tiếp vào dự án mới:

```python
"""
AI Provider Manager: Lưu trữ API Keys, Dynamic Model Listing & Model Selection.
Hỗ trợ Google Gemini & OpenAI-Compatible (OpenRouter, Groq, Ollama, DeepSeek).
"""

import os
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)


class AIProviderManager:
    CACHE_TTL_SECONDS = 300  # Bộ đệm 5 phút

    # Danh mục dự phòng khi mất kết nối mạng hoặc key lỗi
    FALLBACK_MODELS = {
        "gemini": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        "openai": [
            "gpt-4o",
            "gpt-4o-mini",
        ]
    }

    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "providers.json"
        self._cache: Dict[Tuple[str, str], Tuple[float, List[str]]] = {}
        self._ensure_config_exists()

    # ------------------------------------------------------------------
    # 1. Quản lý File Cấu hình (Atomic Write & Validation)
    # ------------------------------------------------------------------
    def _ensure_config_exists(self) -> None:
        if not self.config_file.exists():
            default_data = {
                "version": 1,
                "active_id": "gemini-default",
                "providers": [
                    {
                        "id": "gemini-default",
                        "type": "gemini",
                        "name": "Google Gemini",
                        "api_keys": [],
                        "default_model": "gemini-2.5-flash"
                    }
                ]
            }
            self.save_config(default_data)

    def load_config(self) -> Dict[str, Any]:
        if not self.config_file.exists():
            self._ensure_config_exists()
        with open(self.config_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_config(self, data: Dict[str, Any]) -> None:
        """Lưu cấu hình an toàn bằng kỹ thuật Atomic Write + Backup."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = self.config_file.with_suffix(".json.tmp")
        bak_path = self.config_file.with_suffix(".json.bak")

        # Ghi file tạm
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Backup file cũ nếu tồn tại
        if self.config_file.exists():
            import shutil
            shutil.copy2(self.config_file, bak_path)

        # Thay thế nguyên tử
        os.replace(str(tmp_path), str(self.config_file))

    # ------------------------------------------------------------------
    # 2. Cập nhật API Keys & Lựa chọn Model
    # ------------------------------------------------------------------
    def update_provider_keys_and_model(
        self,
        provider_id: str,
        api_keys: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        selected_model: Optional[str] = None,
    ) -> bool:
        """
        Cập nhật thông tin provider với cơ chế Sentinel Protection
        (không ghi đè nếu truyền key rỗng hoặc key bị masked).
        """
        config = self.load_config()
        provider = next((p for p in config["providers"] if p["id"] == provider_id), None)
        if not provider:
            raise ValueError(f"Provider ID '{provider_id}' không tồn tại.")

        # Xử lý mảng keys (Gemini)
        if api_keys is not None:
            valid_keys = [k.strip() for k in api_keys if k.strip() and not k.startswith("****") and "..." not in k]
            if valid_keys:
                provider["api_keys"] = valid_keys

        # Xử lý key đơn lẻ (OpenAI)
        if api_key is not None:
            clean_k = api_key.strip()
            if clean_k and not clean_k.startswith("****") and "..." not in clean_k:
                provider["api_key"] = clean_k

        if base_url is not None:
            provider["base_url"] = base_url.strip().rstrip("/")

        if selected_model is not None and selected_model.strip():
            model_clean = selected_model.strip()
            self._validate_model_namespace(provider["type"], model_clean, provider.get("base_url", ""))
            provider["default_model"] = model_clean

        self.save_config(config)
        return True

    def set_active_provider(self, provider_id: str) -> None:
        """Đổi provider đang hoạt động."""
        config = self.load_config()
        if not any(p["id"] == provider_id for p in config["providers"]):
            raise ValueError(f"Provider ID '{provider_id}' không tồn tại.")
        config["active_id"] = provider_id
        self.save_config(config)

    # ------------------------------------------------------------------
    # 3. Lấy danh sách Models từ API (Kèm Cache 5 phút & Fallback)
    # ------------------------------------------------------------------
    def list_models_for_provider(self, provider_id: str) -> Dict[str, Any]:
        """
        Lấy danh sách model khả dụng cho provider.
        Tự động đọc từ Cache TTL nếu key và thông tin kết nối chưa đổi.
        """
        config = self.load_config()
        provider = next((p for p in config["providers"] if p["id"] == provider_id), None)
        if not provider:
            raise ValueError(f"Provider ID '{provider_id}' không tồn tại.")

        # Khởi tạo khóa băm cho Cache
        cred_str = f"{provider.get('api_keys')}-{provider.get('api_key')}-{provider.get('base_url')}"
        cred_hash = hashlib.sha256(cred_str.encode("utf-8")).hexdigest()[:16]
        cache_key = (provider_id, cred_hash)

        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_models = self._cache[cache_key]
            if now - cached_time < self.CACHE_TTL_SECONDS:
                return {
                    "provider_id": provider_id,
                    "models": cached_models,
                    "selected_model": provider.get("default_model", ""),
                    "source": "cache",
                    "error": None
                }

        # Gọi live API
        models = []
        error_msg = None
        source = "api"

        try:
            if provider["type"] == "gemini":
                models = self._fetch_gemini_models(provider.get("api_keys", []))
            else:
                models = self._fetch_openai_models(
                    provider.get("api_key", ""),
                    provider.get("base_url", "")
                )
        except Exception as e:
            logger.warning(f"Lỗi truy vấn models từ API của {provider_id}: {e}")
            error_msg = str(e)
            source = "fallback"
            models = self.FALLBACK_MODELS.get(provider["type"], [])

        # Đảm bảo model đang chọn luôn hiện diện trong danh sách
        current_model = provider.get("default_model", "")
        if current_model and current_model not in models:
            models.insert(0, current_model)

        # Lưu cache nếu lấy thành công từ API
        if source == "api" and models:
            self._cache[cache_key] = (now, models)

        return {
            "provider_id": provider_id,
            "models": models,
            "selected_model": current_model,
            "source": source,
            "error": error_msg
        }

    # ------------------------------------------------------------------
    # 4. HTTP Fetchers cho Gemini & OpenAI
    # ------------------------------------------------------------------
    def _fetch_gemini_models(self, api_keys: List[str]) -> List[str]:
        if not api_keys or not api_keys[0]:
            return self.FALLBACK_MODELS["gemini"]

        key = api_keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
            data = resp.json()

        models = []
        for item in data.get("models", []):
            methods = item.get("supportedGenerationMethods", [])
            # Chỉ lấy model sinh văn bản
            if "generateContent" in methods:
                name = item.get("name", "").replace("models/", "")
                if name.startswith("gemini-") or name.startswith("gemma-"):
                    models.append(name)
        return sorted(models, reverse=True) if models else self.FALLBACK_MODELS["gemini"]

    def _fetch_openai_models(self, api_key: str, base_url: str) -> List[str]:
        base = base_url.strip().rstrip("/") if base_url else "https://api.openai.com/v1"
        url = f"{base}/models"
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")
            data = resp.json()

        models = [item["id"] for item in data.get("data", []) if "id" in item]
        return sorted(models) if models else self.FALLBACK_MODELS["openai"]

    # ------------------------------------------------------------------
    # 5. Helpers: Xác thực Namespace & Masking Key
    # ------------------------------------------------------------------
    def _validate_model_namespace(self, provider_type: str, model: str, base_url: str) -> None:
        if provider_type == "gemini":
            if not (model.startswith("gemini-") or model.startswith("gemma-")):
                raise ValueError(f"Model '{model}' không hợp lệ cho nhà cung cấp Google Gemini.")
        elif provider_type == "openai":
            # Nếu không phải gateway tổng hợp (như OpenRouter), chặn model có tiền tố gemini-
            if not ("openrouter.ai" in base_url or "/" in model):
                if model.startswith(("gemini-", "gemma-")):
                    raise ValueError(f"Model '{model}' thuộc Google Gemini, không hợp lệ cho OpenAI provider chuẩn.")

    @staticmethod
    def mask_key(key: str) -> str:
        """Che giấu chuỗi API key khi trả về UI."""
        if not key:
            return ""
        if len(key) <= 8:
            return "****"
        return f"{key[:4]}...{key[-4:]}"
```

---

## 5. HƯỚNG DẪN TÍCH HỢP CHO DỰ ÁN MỚI

### 5.1. Tích hợp vào WebUI / API Settings
- **GET `/api/settings/providers`**:
  - Đọc `config = manager.load_config()`.
  - Trả FULL keys (`masked_providers(mask=False)` — mặc định, đúng manifesto §7).
  - Trả về danh sách provider và `active_id` cho giao diện.
- **GET `/api/settings/models?provider_id={id}`**:
  - Gọi `manager.list_models_for_provider(provider_id)`.
  - Đổ danh sách `models` vào Dropdown / Datalist.
- **POST `/api/settings/save`**:
  - Nhận payload chứa `provider_id`, `api_keys`, `selected_model` $\rightarrow$ Gọi `manager.update_provider_keys_and_model(...)`.

### 5.2. Tích hợp vào Worker Dịch thuật (Translation Execution)
```python
# Đọc cấu hình khi bắt đầu phiên dịch
manager = AIProviderManager()
config = manager.load_config()
active_p = next(p for p in config["providers"] if p["id"] == config["active_id"])

model = active_p.get("default_model")
if active_p["type"] == "gemini":
    keys = active_p.get("api_keys", [])
    # Xoay vòng keys khi gặp HTTP 429:
    # for key in keys: try send... except 429: continue
elif active_p["type"] == "openai":
    key = active_p.get("api_key")
    base_url = active_p.get("base_url")
    # Gửi request với model và key tương ứng
```
