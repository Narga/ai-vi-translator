# Kế Hoạch: Quản lý Provider & Sửa lỗi UX Tab Cấu hình (v7.3.0)

> **Ngày tạo:** 2026-06-03
> **Trạng thái:** SẴN SÀNG TRIỂN KHAI
> **Phạm vi:** Backend + Frontend — Tab "Cấu hình" + Provider management
> **Ước lượng:** ~10h (4h backend + 3h frontend + 2h tích hợp + 1h docs)

---

## 1. Tổng quan

Bản kế hoạch này giải quyết 7 yêu cầu trong tab Cấu hình + tái cấu trúc toàn bộ hệ thống quản lý provider.

### 1.1. Nhận xét reviewer — bổ sung trước triển khai

Kế hoạch hiện tại đúng hướng: gom API keys/provider config về một nguồn `providers.json`, giữ `app.ini` cho cấu hình xử lý, và sửa bug click-bubble trong tab Cấu hình. Tuy nhiên cần làm rõ vài điểm để model triển khai sau không tự suy diễn:

1. **Không đổi return type của public wrapper đang được nhiều nơi gọi.**
   - `webui.helpers.get_active_provider()` phải tiếp tục trả `"gemini"` hoặc `"openai"`.
   - `ProviderService.get_active_provider()` nên giữ tương thích và trả type string, hoặc nếu cần object thì tạo method mới `get_active_provider_config()`.
   - Lý do: routes, facade, tests hiện tại đang so sánh trực tiếp `provider == "openai"` / `"gemini"`.

2. **Tách rõ `provider type` và `provider id`.**
   - `type`: `"gemini"` hoặc `"openai"` — dùng cho radio UI, route compatibility, chọn client.
   - `id`: `"gemini-default"`, `"openrouter"`, `"xiaomi-mimo"` — dùng cho CRUD provider cụ thể.
   - `/api/provider` legacy chỉ nhận/trả type; `/api/providers/select` nhận/trả id.

3. **OpenAI API Key trong dropdown provider sẽ auto-fill theo xác nhận của bạn.**
   - `GET /api/providers` có thể trả `api_key` đầy đủ cho UI cấu hình nội bộ.
   - UI sẽ fill key khi chọn provider để người dùng sửa nhanh.
   - Cần tránh log hoặc telemetry in full key ra ngoài luồng cấu hình.

4. **Không overwrite khi `providers.json` corrupt.**
   - Nếu JSON parse lỗi, không tạo file rỗng đè lên config cũ.
   - Hành vi nên là: log error, trả lỗi rõ trên API/UI, yêu cầu user sửa file hoặc đổi tên file corrupt thủ công.

5. **Danh sách file cần refactor còn thiếu & đếm sai import sites.**
   - **Đã verify:** `webui.helpers` chỉ có **19 import sites** trong 8 file (không phải 143 như một số tài liệu cũ nói). Xem chi tiết ở section 12.7.
   - Ngoài các file đã nêu, cần kiểm tra và sửa `backend/infrastructure/config/app_config_service.py`, `backend/infrastructure/providers/model_catalog_service.py`, `backend/facade/settings_facade.py`, `webui/routes/projects.py`, `webui/routes/translation.py`, và tests liên quan.
   - **Lưu ý đặc biệt:** `app_config_service.py` cũng có `get_active_provider()`, `set_active_provider()`, `get_openai_base_url()`, `get_openai_model()` — tất cả đọc/ghi từ `app.ini`. Sau migration XÓA `[PROVIDER]` và `[OPENAI]`, các method này sẽ luôn trả fallback sai. PHẢI delegate sang `ProviderService` mới.
   - **Lưu ý:** `model_catalog_service.py` có `get_default_model()` chứa dead code (import `ProviderService` nhưng không dùng) và `get_openai_model()` đọc trực tiếp `app.ini [OPENAI] MODEL`. Cả hai phải được sửa.
   - **Lưu ý:** `webui/routes/translation.py` và `webui/routes/projects.py` KHÔNG CẦN sửa trực tiếp — chúng gọi `helpers.load_api_keys()`, `helpers.load_openai_key()`, `helpers.get_openai_base_url()` v.v. Khi `helpers.py` được refactor thành wrapper gọi `ProviderService`, các route tự tương thích. Chỉ cần kiểm tra message lỗi trong `translation.py` không còn nhắc `.env`/`API.txt`.

6. **Migration nên atomic theo thứ tự an toàn.**
   - Ghi `providers.json.tmp` → validate đọc lại → rename atomic sang `providers.json` → sau đó mới xóa `API.txt` và remove sections legacy trong `app.ini`.
   - Nếu bất kỳ bước nào fail trước rename thành công, giữ nguyên file legacy.

### 1.2. Quyết định đã chốt

**OpenAI API Key trong dropdown provider:**

- Chọn **Phương án B**: auto-fill full key khi chọn provider.
- `GET /api/providers` trả key đầy đủ cho UI cấu hình nội bộ.
- `PUT /api/providers/<id>` cho phép cập nhật key ngay trên form đã auto-fill.
- Các response/log không phục vụ cấu hình vẫn nên tránh lộ secret nếu không cần thiết.

Các phần còn lại trong kế hoạch có thể triển khai ngay theo cấu hình này.

### Quyết định đã chốt (sau Q&A)

| # | Quyết định |
|---|-----------|
| 1 | `providers.json` là **nguồn sự thật duy nhất** cho tất cả provider configs (Gemini + OpenAI-Compatible) |
| 2 | **Xóa `config/API.txt`** sau khi migrate (không backup — dự án cá nhân) |
| 3 | **Xóa sections `[PROVIDER]`, `[OPENAI]`** khỏi `app.ini`; giữ `app.ini` cho PROCESSING, MODEL, CACHE, DIRECTORIES |
| 4 | **Loại bỏ hoàn toàn** fallback `.env` cho API keys |
| 5 | Gemini giữ **1 config** với key rotation (nhiều keys trong array), không cần dropdown |
| 6 | OpenAI-Compatible có **dropdown** chọn provider từ `providers.json` |
| 7 | Đổi tên "QA Model" → **"Review Model"**, ẩn vào **Advanced** |
| 8 | Đưa **Chunk Size** ra khỏi Advanced, thay vị trí cũ của QA Model |
| 9 | Đổi "Chọn Model cho Gemini" → **"Chọn model AI"** |
| 10 | Đổi "OpenAI Compatible" → **"OpenAI Compatible Providers"** |
| 12 | Tên provider chỉ cho phép **chữ, số, dấu cách** (regex: `^[a-zA-Z0-9\s]+$`) |
| 13 | Migration **một chiều, không fallback**: convert → xóa file cũ → không bao giờ quay lại |

---

## 2. Phân tích & Sửa lỗi

### 2.1. Bug UX: Click vào input cũng hiện toast "Đã chuyển sang..."

**Root cause** (`tab_config.html:16`, `tab_config.html:40`):
- Cả khối `.nt-provider-col` có `x-on:click="activeProvider = '...'; UiHelpers.switchProvider('...')"`
- Sự kiện bubble lên cả khi click vào `<textarea>`, `<input>` con
- Nút "Lưu Keys Gemini" đã có `event.stopPropagation()` nhưng textarea/input thì không

**Cách sửa:** Di chuyển `x-on:click` từ `<div>` khối → `<label>` bọc radio button.
```html
<!-- TRƯỚC (sai): click anywhere triggers switchProvider -->
<div x-on:click="activeProvider = 'gemini'; UiHelpers.switchProvider('gemini')">
  <label><input type="radio"> Google Gemini</label>
  <textarea></textarea> <!-- click here also triggers! -->
</div>

<!-- SAU (đúng): chỉ click vào label mới trigger -->
<div>
  <label x-on:click="activeProvider = 'gemini'; UiHelpers.switchProvider('gemini')">
    <input type="radio"> Google Gemini
  </label>
  <textarea></textarea> <!-- click here does NOT trigger -->
</div>
```

### 2.2. Kiến trúc hiện tại (cần refactor)

```
ĐỌC API keys:
├── backend/infrastructure/config/api_key_service.py  → đọc từ API.txt + .env + app.ini
├── backend/infrastructure/providers/provider_service.py → đọc từ app.ini
├── webui/helpers.py  → đọc từ API.txt + .env + app.ini (BỊ TRÙNG với backend)
└── main.py:load_api_keys() → đọc từ API.txt + .env (BỊ TRÙNG)

GHI API keys:
├── webui/helpers.py:save_api_keys() → ghi API.txt
└── webui/routes/settings.py:save_openai_config() → ghi app.ini + API.txt
```

**Vấn đề:** Có 3 nơi đọc/ghi API keys riêng biệt → dễ lạc hậu khi thay đổi.

**Giải pháp:** Mọi hàm đọc/ghi API keys đều đi qua `ProviderService` mới. `webui/helpers.py` và `main.py` trở thành wrapper gọi backend service.

---

## 3. Thiết kế dữ liệu

### 3.1. `config/providers.json` (NGUỒN DUY NHẤT)

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
        "AIzaSyDUMMYKEY1_xxxxxxxxxxxxxxxxxxxxxx",
        "AIzaSyDUMMYKEY2_xxxxxxxxxxxxxxxxxxxxxx"
      ],
      "default_model": "gemini-2.0-flash"
    },
    {
      "id": "openrouter",
      "type": "openai",
      "name": "OpenRouter",
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "sk-or-v1-...",
      "default_model": "openrouter/free"
    },
    {
      "id": "xiaomi",
      "type": "openai",
      "name": "Xiaomi MiMo",
      "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
      "api_key": "",
      "default_model": ""
    }
  ]
}
```

**Schema chi tiết:**

| Field | Type | Bắt buộc | Mô tả |
|-------|------|-----------|-------|
| `version` | int | ✅ | Schema version (hiện tại: 1) |
| `active_id` | string | ✅ | ID của provider đang kích hoạt |
| `providers` | array | ✅ | Danh sách providers |
| `providers[].id` | string | ✅ | Unique ID, slug từ name (vd: "xiaomi-mimo") |
| `providers[].type` | string | ✅ | `"gemini"` hoặc `"openai"` |
| `providers[].name` | string | ✅ | Tên hiển thị. **Validation:** chỉ chữ, số, dấu cách (`^[a-zA-Z0-9\s]+$`) |
| `providers[].api_keys` | string[] | Chỉ gemini | Danh sách keys cho key rotation |
| `providers[].api_key` | string | Chỉ openai | API key đơn |
| `providers[].base_url` | string | Chỉ openai | API base URL |
| `providers[].default_model` | string | Không | Model mặc định khi load models |

**Bảo mật:**
- `providers.json` chứa API keys plaintext → **thêm vào `.gitignore`** để không commit lên repo
- File chỉ tồn tại trên local machine (dự án cá nhân)
- Không log full API key. Log chỉ được phép ghi `api_key_count`, provider id/name, hoặc preview đã mask.
- API response phục vụ màn hình cấu hình nội bộ có thể trả full OpenAI `api_key` để hỗ trợ auto-fill; các response khác vẫn nên sanitize nếu không cần secret.

**Quy tắc sinh `id`:**
- Normalize tên provider: lowercase → trim → thay chuỗi dấu cách bằng `-`.
- Validation name: chỉ chữ, số, dấu cách (`^[a-zA-Z0-9\s]+$`).
- Nếu slug trùng, append hậu tố số: `openrouter`, `openrouter-2`, `openrouter-3`.
- `gemini-default` là provider hệ thống, không cho xóa qua UI/API.

**Atomic write:**
- `save_providers(data)` phải ghi ra `providers.json.tmp`, đọc lại để validate JSON/schema tối thiểu, rồi `replace()` sang `providers.json`.
- Nếu validate fail, xóa file tmp và giữ nguyên file hiện tại.

### 3.2. `config/app.ini` (SAU KHI MIGRATE)

```ini
[MODEL]
MODEL =
QA_MODEL =
THINKING_LEVEL = MEDIUM

[PROCESSING]
MAX_CHARS_PER_CHUNK = 20000
TEMPERATURE = 1.0
REQUEST_DELAY = 5
CONTEXT_CHAR_COUNT = 500

[DIRECTORIES]
ARCHIVE_DIR_NAME = _archive
CACHE_DIR = workspace/cache
LOGS_DIR = workspace/logs

[CACHE]
ENABLE_CACHE = true
```

> Không còn `[PROVIDER]` và `[OPENAI]` sections.

### 3.3. Migration Flow (Một chiều, không fallback)

> **Nguyên tắc:** Migration chạy 1 lần duy nhất khi `providers.json` chưa tồn tại. Convert xong → xóa file cũ → không bao giờ quay lại. Dự án cá nhân, local, không cần fallback.

```python
# Chạy trong ProviderService.__init__()
def __init__(self, config_dir=None):
    self._config_dir = config_dir or Path("config")
    self._providers_file = self._config_dir / "providers.json"
    if not self._providers_file.exists():
        self._migrate_from_legacy()  # chỉ chạy 1 lần
```

```
providers.json chưa tồn tại?
  │
  ├── NO → bỏ qua (bình thường)
  │
  └── YES → chạy migration:
      │
      ├── 1. Đọc config/API.txt [GEMINI] → tạo provider "gemini-default"
      ├── 2. Đọc config/API.txt [OPENAI] + app.ini [OPENAI] → tạo provider "openai-default"
      ├── 3. Đọc app.ini [PROVIDER] ACTIVE_PROVIDER → set active_id
      ├── 4. Ghi providers.json bằng atomic write + validate đọc lại
      ├── 5. Xóa config/API.txt (không backup — dự án cá nhân)
      ├── 6. Xóa [PROVIDER] + [OPENAI] khỏi app.ini (giữ PROCESSING/MODEL/CACHE/DIRECTORIES)
      └── 7. Log: "✅ Migrated API config to providers.json"
```

> **Không có fallback.** Nếu `providers.json` bị xóa sau migration → user phải tạo lại provider thủ công qua UI.

**Chi tiết migration bắt buộc:**
- Nếu `API.txt` không có `[GEMINI]` nhưng có key legacy không section, coi toàn bộ key đó là Gemini.
- Nếu không có OpenAI key/base_url cũ thì không bắt buộc tạo OpenAI provider mặc định; UI vẫn cho thêm provider mới.
- Nếu `ACTIVE_PROVIDER = openai` nhưng không migrate được OpenAI provider hợp lệ, set `active_id = "gemini-default"` và log warning.
- Chỉ xóa `API.txt` và remove sections legacy sau khi `providers.json` đã được ghi và validate thành công.
- Nếu `providers.json` đã tồn tại, tuyệt đối không đọc lại `API.txt`/`.env`/`app.ini [OPENAI]` làm fallback.

**Code mẫu — Atomic write (`save_providers`):**

```python
def save_providers(self, data: dict) -> None:
    """Ghi providers.json bằng atomic write + validate."""
    import json, tempfile

    tmp_path = self._providers_file.with_suffix(".json.tmp")

    try:
        # 1. Ghi ra file tmp
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 2. Validate: đọc lại từ tmp, kiểm tra schema tối thiểu
        with open(tmp_path, "r", encoding="utf-8") as f:
            verify = json.load(f)
        if not isinstance(verify.get("providers"), list):
            raise ValueError("providers phải là array")
        if not isinstance(verify.get("active_id"), str):
            raise ValueError("active_id phải là string")

        # 3. Atomic rename
        tmp_path.replace(self._providers_file)

    except Exception as e:
        # Nếu fail, xóa tmp, giữ nguyên file hiện tại
        if tmp_path.exists():
            tmp_path.unlink()
        raise RuntimeError(f"Lưu providers.json thất bại: {e}")
```

**Code mẫu — Bảo vệ `gemini-default` (`delete_provider`):**

```python
def delete_provider(self, provider_id: str) -> bool:
    """Xóa provider. Không cho xóa gemini-default."""
    if provider_id == "gemini-default":
        raise ValueError("Không thể xóa provider Gemini hệ thống")

    data = self.load_providers()
    provider = self.get_provider_by_id(provider_id)
    if not provider:
        raise ValueError(f"Provider '{provider_id}' không tồn tại")

    # Nếu đang xóa provider đang active → auto-chuyển
    if data["active_id"] == provider_id:
        same_type = [p for p in data["providers"]
                     if p["type"] == provider["type"] and p["id"] != provider_id]
        if same_type:
            data["active_id"] = same_type[0]["id"]
        else:
            data["active_id"] = "gemini-default"

    data["providers"] = [p for p in data["providers"] if p["id"] != provider_id]
    self.save_providers(data)
    return True
```

**`.gitignore` — dòng cần thêm:**

```
# Chứa API keys — không commit
config/providers.json
```

> Giữ `config/app.ini` NGOÀI `.gitignore` (intentional — file này chỉ chứa PROCESSING/MODEL/CACHE, không có secrets).

---

## 4. Thiết kế giao diện

### 4.1. Layout mới (Tab Cấu hình)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Cấu hình Hệ thống & AI Provider                  [💾 Lưu Cấu Hình]│
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─── GOOGLE GEMINI ──────────────┐  ┌── OPENAI COMPATIBLE PROVIDERS ──┐│
│  │ (◉) Google Gemini              │  │ ( ) OpenAI Compatible Providers  ││
│  │   [logo]                       │  │   [logo]                        ││
│  │                                │  │                                 ││
│  │   API Keys (mỗi dòng 1 key)   │  │   Provider [▼ OpenRouter     ✕] ││
│  │   ┌──────────────────────┐     │  │                                 ││
│  │   │ textarea              │     │  │   API Key   [•••••••••••    ]   ││
│  │   │                       │     │  │   Base URL  [https://open…  ]   ││
│  │   └──────────────────────┘     │  │                                 ││
│  │                                │  │   ── Thêm Provider mới ──      ││
│  │   [💾 Lưu Keys Gemini]          │  │   [Tên provider       ] [+Thêm]││
│  └────────────────────────────────┘  │                                 ││
│                                      │                                 ││
│                                      │   [💾 Lưu Cấu hình OpenAI]     ││
│                                      └─────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────┤
│  Chọn model AI                                    [⭐ Đánh dấu] [🔄]│
│  [▼ select models từ active provider...]                            │
│  Input limit: ...  │  Output limit: ...                              │
├─────────────────────────────────────────────────────────────────────┤
│  Thiết lập Hệ thống                                                │
│  ┌─ Chunk Size ──────┐  ┌─ Thinking Level ────┐                    │
│  │ [20000]           │  │ [▼ MEDIUM         ]  │                    │
│  └───────────────────┘  └─────────────────────┘                    │
│                                                                     │
│  ▸ Cấu hình nâng cao (Advanced)                                    │
│    ┌─ Context Radius ─┐  ┌─ Review Model ──────┐                   │
│    │ [500]            │  │ [▼ Mặc định       ]  │                   │
│    └──────────────────┘  └─────────────────────┘                   │
│    Temperature: [===●======] 1.0                                    │
│    API Delay: [5] giây    Antilag: [10ms] (readonly)               │
│    [✓] Sử dụng Cache API                                            │
├─────────────────────────────────────────────────────────────────────┤
│  Dọn dẹp hệ thống                                                  │
│  Giải phóng dung lượng bộ nhớ tạm...              [🗑️ Xóa Cache]  │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2. Luồng hoạt động của khối OpenAI Compatible Providers

```
User mở tab Cấu hình
  │
  ├── initProvider() gọi GET /api/providers
  │   └── Nhận danh sách providers + active_id
  │       ├── Render dropdown: chỉ hiện providers có type="openai"
  │       └── Auto-select provider đang active
  │
  ├── User chọn provider từ dropdown
  │   └── onSelectProvider(id)
  │       ├── Tìm provider trong danh sách
  │       ├── Fill Base URL input từ providers.json
  │       ├── Fill API Key input từ providers.json để người dùng sửa nhanh
  │       └── Highlight nút Xóa
  │
  ├── User sửa API Key / Base URL (tùy chọn)
  │
  ├── User bấm "💾 Lưu Cấu hình OpenAI"
  │   └── saveCurrent()
  │       ├── PUT /api/providers/{id} (cập nhật api_key nếu user nhập key mới, base_url, default_model)
  │       ├── POST /api/providers/select {active_id: id}
  │       ├── loadModels() → fetch models từ provider mới
  │       └── Toast "Đã lưu & kích hoạt {name}"
  │
  ├── User bấm "🗑️ Xóa"
  │   └── deleteSelected()
  │       ├── Confirm dialog "Xóa provider {name}?"
  │       ├── DELETE /api/providers/{id}
  │       ├── Không cho xóa gemini-default
  │       ├── Nếu provider đang active → auto-chuyển sang provider cùng type nếu có, nếu không thì gemini-default
  │       └── Re-render dropdown
  │
  └── User nhập tên mới + bấm "+Thêm"
      └── addNew()
          ├── Validate: tên không rỗng, regex hợp lệ, không trùng display name trong cùng type
          ├── POST /api/providers {name, type: "openai"}
          ├── Auto-select provider mới trong dropdown
          └── Focus vào API Key input
```

### 4.3. Khối Google Gemini (sửa UX click)

> **QUAN TRỌNG — Alpine.js `x-data`:** Div cha `x-data="{ activeProvider: 'gemini' }"` ở `tab_config.html:13` bọc cả 2 col (Gemini + OpenAI). PHẢI giữ nguyên `x-data` ở div cha. Chỉ di chuyển `x-on:click` từ `.nt-provider-col` xuống `<label>`. Alpine `activeProvider` state vẫn dùng cho `:class` binding ở `.nt-provider-col`.

```html
<!-- div cha GIỮ NGUYÊN x-data -->
<div x-data="{ activeProvider: 'gemini' }" class="flex flex-wrap mhn2 mb3">

  <!-- Gemini col: BỎ x-on:click ở div.nt-provider-col, CHUYỂN xuống label -->
  <div id="provider-gemini-col" class="nt-provider-col flex flex-column justify-between h-100 ba br2 bg-white pa3 shadow-1 pointer overflow-hidden transition-all"
       :class="activeProvider === 'gemini' ? 'b--blue o-100' : 'b--black-10 o-60'"
       data-provider="gemini">
    <div class="flex-auto">
      <!-- Click handler CHỈ trên label radio -->
      <div class="flex justify-between items-center mb3">
        <label class="flex items-center pointer"
               x-on:click="activeProvider = 'gemini'; UiHelpers.switchProvider('gemini')">
          <input type="radio" name="active_provider" value="gemini"
                 class="mr2 pointer"
                 :checked="activeProvider === 'gemini'">
          <span class="f5 fw6 dark-gray">Google Gemini</span>
        </label>
      </div>
      <div class="tc pv3 mb2">
        <img src="/static/images/gemini-logo.png" ...>
      </div>
      <div class="mb3">
        <label class="db fw6 lh-copy f7 mb2 gray uppercase tracked">API Keys (mỗi dòng 1 key)</label>
        <textarea id="config-api-keys" class="..." style="height:120px; resize:none"
                  placeholder="AIzaSy..."></textarea>
      </div>
    </div>
    <div class="mt2">
      <button class="..." onclick="event.stopPropagation(); GeminiProvider.saveKeys()">
        💾 Lưu Keys Gemini
      </button>
    </div>
  </div>
```

### 4.4. Khối OpenAI Compatible Providers (TÁI THIẾT KẾ)

```html
<div id="provider-openai-col" class="nt-provider-col ...">
  <div class="flex-auto">
    <!-- Click handler CHỈ trên label radio -->
    <div class="flex justify-between items-center mb3">
      <label class="flex items-center pointer"
             x-on:click="activeProvider = 'openai'; UiHelpers.switchProvider('openai')">
        <input type="radio" name="active_provider" value="openai"
               class="mr2 pointer"
               :checked="activeProvider === 'openai'">
        <span class="f5 fw6 dark-gray">OpenAI Compatible Providers</span>
      </label>
    </div>
    <div class="tc pv3 mb2">
      <img src="/static/images/openai-logo.png" ...>
    </div>

    <!-- Provider dropdown + nút Xóa -->
    <div class="mb3">
      <label class="db fw6 lh-copy f7 mb2 gray uppercase tracked">Provider</label>
      <div class="flex items-center gap-2 mb3">
        <select id="openai-provider-select"
                class="ba b--black-10 br2 pa2 flex-auto f7 outline-0"
                onchange="OpenAIProvider.onSelectProvider(this.value)">
          <option value="">— Chọn provider —</option>
          <!-- JS render: chỉ hiện type="openai" -->
        </select>
        <button class="ba b--red bg-white pa2 br2 pointer f7 red hover-bg-washed-red nowrap shadow-sm"
                onclick="OpenAIProvider.deleteSelected()"
                title="Xóa provider đang chọn">✕</button>
      </div>
    </div>

    <!-- API Key + Base URL (auto-fill khi chọn provider) -->
    <div class="mb3">
      <label class="db fw6 lh-copy f7 mb2 gray uppercase tracked">API Key</label>
      <input type="text" id="openai-api-key"
             class="ba b--black-10 br2 pa2 w-100 code f7 mb3 outline-0"
             placeholder="Nhập API Key">
    </div>
    <div class="mb3">
      <label class="db fw6 lh-copy f7 mb2 gray uppercase tracked">Base URL</label>
      <input type="text" id="openai-base-url"
             class="ba b--black-10 br2 pa2 w-100 f7 outline-0"
             placeholder="https://openrouter.ai/api/v1">
    </div>

    <!-- Thêm provider mới -->
    <div class="bt b--black-10 pt3 mt3">
      <label class="db fw6 lh-copy f7 mb2 gray uppercase tracked">Thêm Provider mới</label>
      <div class="flex items-center gap-2">
        <input type="text" id="new-provider-name"
               class="ba b--black-10 br2 pa2 flex-auto f7 outline-0"
               placeholder="Tên provider (vd: Xiaomi MiMo)">
        <button class="ba b--blue bg-blue white pa2 br2 pointer f7 nowrap hover-bg-dark-blue shadow-sm"
                onclick="OpenAIProvider.addNew()">+ Thêm</button>
      </div>
    </div>
  </div>
  <div class="mt2">
    <button class="ba b--black-10 bg-near-white w-100 pv2 ph3 br2 pointer f7 hover-bg-white fw6 gray"
            onclick="event.stopPropagation(); OpenAIProvider.saveCurrent()">
      💾 Lưu Cấu hình OpenAI
    </button>
  </div>
</div>
```

### 4.5. Các thay đổi khác trong tab Cấu hình

| Vị trí | Trước | Sau |
|--------|-------|-----|
| Heading model | "Chọn Model cho **Gemini**" | "Chọn model **AI**" |
| QA Model | Ngoài "Thiết lập Hệ thống" | Đổi tên "Review Model", ẩn vào Advanced |
| Chunk Size | Trong Advanced | Đưa ra ngoài, thay vị trí QA Model |
| Tooltip Review Model | "Model phụ trách kiểm soát chất lượng..." | "Dùng để rà soát & sửa lỗi bản dịch sau khi hoàn tất." |

---

## 5. Thiết kế API

### 5.1. Endpoints mới

| Method | Path | Request Body | Response | Mô tả |
|--------|------|-------------|----------|--------|
| `GET` | `/api/providers` | — | `{active_id, providers[]}` | Danh sách tất cả providers |
| `POST` | `/api/providers` | `{name, type}` | `{provider}` | Tạo provider mới (type="openai") |
| `PUT` | `/api/providers/<id>` | `{name?, api_key?, base_url?, default_model?}` | `{provider}` | Cập nhật provider |
| `DELETE` | `/api/providers/<id>` | — | `{success}` | Xóa provider |
| `POST` | `/api/providers/select` | `{active_id}` | `{success, active_id}` | Kích hoạt provider |

**Quy ước API quan trọng:**
- `GET /api/providers` trả provider object đầy đủ cho màn hình cấu hình nội bộ, bao gồm full `api_key` của OpenAI và `api_keys` của Gemini.
- `PUT /api/providers/<id>` với provider OpenAI:
  - Nếu body không có field `api_key` → giữ nguyên key cũ.
  - Nếu body có `api_key` là chuỗi rỗng → giữ nguyên key cũ để tránh vô tình xóa secret khi UI gửi form rỗng.
  - Nếu body có `api_key` non-empty → replace key cũ.
- Nếu cần xóa key thật sự, thêm field rõ ràng `clear_api_key: true` thay vì dùng chuỗi rỗng.
- `DELETE /api/providers/gemini-default` trả 400/403, không xóa provider Gemini hệ thống.
- API lỗi validation trả status 400 với `{error, field?}` để frontend hiển thị đúng input lỗi.

### 5.2. Endpoints cần refactor (đọc từ providers.json thay vì app.ini/API.txt)

| Endpoint hiện tại | Thay đổi |
|-------------------|----------|
| `GET /api/provider` | Đọc `active_id` + provider info từ `providers.json` |
| `POST /api/provider` | Legacy: nhận `{provider: "gemini"|"openai"}`. Chọn provider id mặc định của type đó, vẫn giữ backward compat |
| `GET /api/openai/models` | Đọc API key + base URL từ provider đang active trong `providers.json` |
| `GET /api/models` | Tương tự |
| `POST /api/openai/config` | Legacy: cập nhật OpenAI provider đang chọn/active qua ProviderService, không ghi `app.ini`/`API.txt` |
| `GET /api/keys` | Đọc từ `providers.json` thay vì `API.txt` |
| `POST /api/keys` | Ghi vào `providers.json` thay vì `API.txt` |

### 5.3. Response shape: `GET /api/providers`

```json
{
  "active_id": "xiaomi",
  "providers": [
    {
      "id": "gemini-default",
      "type": "gemini",
      "name": "Google Gemini",
      "api_key_count": 2,
      "default_model": "gemini-2.0-flash"
    },
    {
      "id": "openrouter",
      "type": "openai",
      "name": "OpenRouter",
      "base_url": "https://openrouter.ai/api/v1",
      "api_key": "sk-or-v1-xxxxxxxxxxxxxxxx",
      "default_model": "openrouter/free"
    },
    {
      "id": "xiaomi",
      "type": "openai",
      "name": "Xiaomi MiMo",
      "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
      "api_key": "tp-c-xxxxxxxxxxxxxxxx",
      "default_model": ""
    }
  ]
}
```

> **Lưu ý:** API key trả full trong response dành cho màn hình cấu hình nội bộ để hỗ trợ auto-fill; các luồng khác không cần secret thì vẫn nên sanitize.

**Response shape legacy: `GET /api/provider`**

Endpoint này giữ cho frontend cũ và tests cũ không vỡ trong quá trình refactor:

```json
{
  "active": "openai",
  "active_id": "openrouter",
  "providers": [
    {"id": "gemini", "name": "Google Gemini"},
    {"id": "openai", "name": "OpenAI Compatible Providers"}
  ],
  "openai_config": {
    "provider_id": "openrouter",
    "provider_name": "OpenRouter",
    "base_url": "https://openrouter.ai/api/v1",
    "model": "openrouter/free",
    "has_key": true,
    "api_key": "sk-or-v1-xxxxxxxxxxxxxxxx"
  }
}
```

> Response này được phép mang full secret vì đây là màn hình cấu hình nội bộ và bạn đã chọn Phương án B.

---

## 6. Refactor Backend Services

### 6.1. `ProviderService` (REWRITE)

File: `backend/infrastructure/providers/provider_service.py`

> **Lưu ý:** Method hiện tại `get_available_providers()` import `from services.ai_provider import get_available_providers` — import này có thể fail. Khi rewrite, method `get_available_providers()` trong ProviderService mới phải trả data từ `providers.json` (danh sách provider objects), KHÔNG gọi service cũ.

```
Phương thức hiện tại (đọc từ app.ini):
├── get_active_provider() → "gemini" | "openai"
├── set_active_provider(provider)
├── get_openai_base_url()
├── set_openai_base_url(url)
├── get_openai_model()
├── set_openai_model(model)
├── get_openai_runtime_config()
└── get_available_providers() → [dead import, cần xóa logic cũ]

Phương thức mới (đọc từ providers.json):
├── load_providers() → {version, active_id, providers[]}
├── save_providers(data) → atomic write
├── get_active_provider() → "gemini" | "openai" (giữ backward compat)
├── get_active_provider_config() → provider object đang active
├── get_active_provider_type() → "gemini" | "openai"
├── select_provider(id) → set active_id
├── select_provider_by_type(type) → chọn provider mặc định/đầu tiên theo type cho legacy /api/provider
├── add_provider(name, type, ...) → provider object
├── update_provider(id, ...) → provider object
├── delete_provider(id) → bool
├── get_provider_by_id(id) → provider object | None
├── get_providers_by_type(type) → provider[]
├── get_available_providers() → trả data từ providers.json, KHÔNG gọi services.ai_provider
├── get_active_api_keys() → string[] (cho Gemini key rotation)
├── get_active_api_key() → string (cho OpenAI)
├── get_active_base_url() → string | None
├── get_active_default_model() → string
└── _migrate_from_legacy() → chạy migration 1 lần
```

> **Không đổi semantic của `get_active_provider()` trong cùng PR.** Nếu đổi sang object, bắt buộc sửa toàn bộ caller và tests; kế hoạch này chọn giữ string để giảm blast radius.

### 6.2. `ApiKeyService` (REFACTOR → gọi ProviderService)

File: `backend/infrastructure/config/api_key_service.py`

```
Phương thức refactor:
├── load_gemini_keys() → lấy keys từ provider type=gemini (không phụ thuộc active provider)
├── load_openai_key() → ProviderService.get_active_api_key() nếu type=openai
├── load_all_keys() → gom keys từ tất cả providers
├── save_keys(section, keys_text) → gọi ProviderService.update_provider()
├── has_gemini_keys() → check providers.json
├── has_openai_key() → check providers.json
└── get_key_count() → đếm từ providers.json
```

> **Quan trọng:** `ApiKeyService` vẫn tồn tại nhưng bên trong gọi `ProviderService`. Giữ nguyên interface để các phần khác của code không phải sửa.

### 6.3. `webui/helpers.py` (REFACTOR — Chi tiết phức tạp)

> **Quan điểm:** Kế hoạch chỉ lưu API keys trong `providers.json` cho dễ quản lý. Việc refactor `helpers.py` phức tạp ở chỗ: file này được nhiều route/service/test import trực tiếp, và nhiều hàm có fallback chain qua 3 nguồn (API.txt → .env → app.ini) cần được rút gọn.

**Danh sách hàm cần refactor + mức độ phức tạp:**

| Hàm | Phức tạp | Lý do | Cách sửa |
|-----|----------|-------|----------|
| `load_api_keys(section)` | ⚠️ CAO | Được gọi ở 15+ nơi (translation, projects, settings, stats). Hiện đọc từ API.txt theo section. Sau migration phải đọc từ providers.json theo provider type. | 1. Đọc từ providers.json theo type. 2. Giữ nguyên signature để các caller không phải sửa. |
| `load_openai_key()` | ⚠️ CAO | Tương tự `load_api_keys` nhưng cho OpenAI. Có fallback chain 3 lớp (API.txt → .env → app.ini). Cần rút gọn. | 1. Đọc từ providers.json active provider (type=openai). 2. Xóa fallback .env và app.ini. 3. Giữ nguyên signature. |
| `save_api_keys(keys_text, section)` | 🔶 TRUNG BÌNH | Hiện ghi vào API.txt. Sau migration phải ghi vào providers.json. Nhưng section name ("GEMINI"/"OPENAI") không khớp với provider id. Cần map: section="GEMINI" → provider type="gemini". | 1. Tìm provider theo type. 2. Cập nhật api_keys/api_key. 3. Ghi providers.json. 4. Giữ nguyên signature. |
| `get_active_provider()` | 🟢 THẤP | Hiện đọc từ app.ini `[PROVIDER] ACTIVE_PROVIDER`. Đơn giản: đổi sang đọc `active_id` từ providers.json → tra type. | Đọc providers.json → `active_id` → `providers[id].type` |
| `get_openai_base_url()` | 🟢 THẤP | Hiện đọc từ app.ini `[OPENAI] BASE_URL`. Đơn giản: đổi sang đọc từ active provider (type=openai). | Đọc providers.json → active provider → `base_url` |
| `get_openai_model()` | 🟢 THẤP | Hiện đọc từ app.ini `[OPENAI] MODEL`. Đơn giản. | Đọc providers.json → active provider → `default_model` |
| `_parse_api_file()` | ❌ XÓA | Không cần nữa vì API.txt bị xóa. | Xóa hàm + xóa mọi caller. |
| `load_config()` | ✅ GIỮ | Đọc app.ini cho PROCESSING/MODEL/CACHE. Không liên quan API keys. | Giữ nguyên. |

**Điểm phức tạp chính:**

1. **Nhiều điểm gọi trực tiếp** — `load_api_keys`, `get_active_provider`, `load_openai_key` được import ở nhiều file. Nếu đổi tên hàm hoặc đổi return type → phải sửa tất cả callers. **Giải pháp:** giữ nguyên tên và return type, chỉ đổi logic bên trong.

2. **Section mapping** — `save_api_keys(keys_text, section="GEMINI")` dùng section name nhưng providers.json dùng provider id. Cần mapping: `section="GEMINI"` → tìm provider có `type="gemini"` → cập nhật `api_keys`.

3. **Fallback chain bị xóa** — hiện `load_openai_key()` có 3 fallback (API.txt → .env → app.ini). Sau migration chỉ còn 1 nguồn (providers.json). Nếu key rỗng → trả về None, không fallback. Mọi caller cần xử lý None đúng cách.

**Kế hoạch refactor tuần tự (an toàn nhất):**

```
Bước 1: Tạo ProviderService mới (đọc providers.json)
Bước 2: Refactor ApiKeyService → wrapper gọi ProviderService (giữ nguyên interface)
Bước 3: Refactor AppConfigService → delegate 4 provider methods sang ProviderService
Bước 4: Refactor ModelCatalogService → đọc key/url/model qua ProviderService
Bước 5: Refactor SettingsFacade → cập nhật response shape get_provider_info()
Bước 6: Refactor webui/helpers.py → wrapper gọi ApiKeyService (giữ nguyên interface)
Bước 7: Refactor main.py → gọi ApiKeyService (xóa fallback .env + dead `os` import)
Bước 8: Chạy test suite → sửa lỗi
Bước 9: Migration + xóa file cũ
Bước 10: Chạy test suite lần 2 → sửa lỗi
```

> **Quan trọng:** Không xóa API.txt cho đến khi tất cả tests pass. Refactor TỪ TRONG RA NGOÀI (backend service → helpers → routes).

### 6.4. `main.py` (REFACTOR)

> **Bug hiện tại:** `main.py:load_api_keys()` line 71 gọi `os.environ.get()` nhưng `os` không được import ở đầu file. Bug này tự biến mất khi refactor vì hàm sẽ delegate sang `ApiKeyService`. **KHÔNG copy logic cũ vào hàm mới.**

```
├── load_api_keys() → gọi backend ApiKeyService thay vì đọc API.txt trực tiếp
└── Xóa fallback .env + xóa dead import nếu os không còn cần
```

### 6.5. `AppConfigService` (REFACTOR — delegate provider methods)

File: `backend/infrastructure/config/app_config_service.py`

> **CRITICAL:** File này có 4 method đọc/ghi provider config trực tiếp từ `app.ini [PROVIDER]` và `[OPENAI]`. Sau migration xóa 2 sections này, các method sẽ luôn trả fallback sai.

```
Phương thức cần refactor:
├── get_active_provider()  → delegate sang ProviderService.get_active_provider()
├── set_active_provider()  → delegate sang ProviderService.select_provider_by_type()
├── get_openai_base_url()  → delegate sang ProviderService.get_active_base_url()
└── get_openai_model()     → delegate sang ProviderService.get_active_default_model()
```

**Cách sửa:** Import `ProviderService` ở đầu method (lazy import để tránh circular), gọi tương ứng:
```python
def get_active_provider(self) -> str:
    from backend.infrastructure.providers.provider_service import ProviderService
    return ProviderService(self._config_dir).get_active_provider()

def set_active_provider(self, provider: str) -> None:
    from backend.infrastructure.providers.provider_service import ProviderService
    ProviderService(self._config_dir).select_provider_by_type(provider)

def get_openai_base_url(self) -> Optional[str]:
    from backend.infrastructure.providers.provider_service import ProviderService
    return ProviderService(self._config_dir).get_active_base_url()

def get_openai_model(self) -> str:
    from backend.infrastructure.providers.provider_service import ProviderService
    return ProviderService(self._config_dir).get_active_default_model()
```

### 6.6. `ModelCatalogService` (REFACTOR — chuyển đọc qua ProviderService)

File: `backend/infrastructure/providers/model_catalog_service.py`

> **CRITICAL:** File này đọc API key, base_url, model trực tiếp từ `ApiKeyService` (legacy) và `app.ini` (configparser). Sau migration sẽ vỡ.

```
Phương thức cần refactor:
├── get_openai_models()     → đọc api_key qua ProviderService.get_active_api_key()
│                             đọc base_url qua ProviderService.get_active_base_url()
├── get_openai_models_full() → tương tự get_openai_models()
├── get_default_model()      → xóa dead code (import ProviderService không dùng ở line 204)
│                             đọc từ app.ini [MODEL] MODEL — giữ nguyên (section này vẫn còn)
└── get_openai_model()       → đọc qua ProviderService.get_active_default_model()
│                             KHÔNG đọc trực tiếp configparser từ app.ini [OPENAI] MODEL
```

**Chi tiết sửa `get_openai_models()` và `get_openai_models_full()`:**
```python
# TRƯỚC (sai sau migration):
key_service = ApiKeyService(self._config_dir)
api_key = key_service.load_openai_key()  # sẽ trả None vì API.txt đã xóa
base_url = provider_service.get_openai_base_url()  # đọc app.ini [OPENAI] đã xóa

# SAU (đúng):
from backend.infrastructure.providers.provider_service import ProviderService
provider_service = ProviderService(self._config_dir)
api_key = provider_service.get_active_api_key()
base_url = provider_service.get_active_base_url()
```

### 6.7. `SettingsFacade` (REFACTOR — cập nhật response shape)

File: `backend/facade/settings_facade.py`

```
Phương thức cần refactor:
├── get_provider_info()  → đọc từ ProviderService mới, thêm active_id + full api_key
├── get_models()         → đọc provider qua ProviderService (đã delegate, ít thay đổi)
├── get_api_keys()       → delegate qua ApiKeyService (đã delegate)
└── save_api_keys()      → delegate qua ApiKeyService (đã delegate)
```

**Chi tiết `get_provider_info()` sau refactor — response shape legacy `GET /api/provider`:**
```python
def get_provider_info(self) -> Dict[str, Any]:
    from backend.infrastructure.providers.provider_service import ProviderService
    provider_service = ProviderService(self._config_dir)

    active_type = provider_service.get_active_provider()  # "gemini" | "openai"
    active_config = provider_service.get_active_provider_config()  # full provider object
    providers_list = [
        {"id": "gemini", "name": "Google Gemini"},
        {"id": "openai", "name": "OpenAI Compatible Providers"},
    ]

    result = {
        "active": active_type,
        "active_id": active_config["id"],
        "providers": providers_list,
    }

    # Nếu active provider là openai, trả thêm openai_config
    if active_type == "openai":
        result["openai_config"] = {
            "provider_id": active_config["id"],
            "provider_name": active_config["name"],
            "base_url": active_config.get("base_url", ""),
            "model": active_config.get("default_model", ""),
            "has_key": bool(active_config.get("api_key")),
            "api_key": active_config.get("api_key", ""),  # full key cho cấu hình nội bộ
        }
    else:
        # Gemini active: vẫn trả openai_config cho UI fill sẵn nếu cần
        openai_providers = provider_service.get_providers_by_type("openai")
        if openai_providers:
            first_openai = openai_providers[0]
            result["openai_config"] = {
                "provider_id": first_openai["id"],
                "provider_name": first_openai["name"],
                "base_url": first_openai.get("base_url", ""),
                "model": first_openai.get("default_model", ""),
                "has_key": bool(first_openai.get("api_key")),
                "api_key": first_openai.get("api_key", ""),
            }
        else:
            result["openai_config"] = {
                "base_url": "", "model": "", "has_key": False, "api_key": "",
            }

    return result
```

---

## 7. Frontend Modules

### 7.1. Module mới: `webui/static/js/provider-manager.js`

```javascript
// Namespace: window.GeminiProvider + window.OpenAIProvider

const GeminiProvider = {
    saveKeys()         // Lưu Gemini keys vào providers.json (xem code bên dưới)
};

const OpenAIProvider = {
    loadProviders()          // GET /api/providers → render dropdown
    onSelectProvider(id)     // Chọn provider → fill API Key + Base URL
    addNew()                 // POST /api/providers → tạo mới
    deleteSelected()         // DELETE /api/providers/{id} → xóa
    saveCurrent()            // Lưu + kích hoạt provider (xem flow bên dưới)
    getSelectedProvider()    // Helper: lấy provider object đang chọn
};

window.GeminiProvider = GeminiProvider;
window.OpenAIProvider = OpenAIProvider;
```

**Code mẫu — `saveCurrent()` flow chi tiết:**

```javascript
saveCurrent() {
    const select = document.getElementById('openai-provider-select');
    const id = select.value;
    if (!id) { UiHelpers.showToast('Chưa chọn provider', 'error'); return; }

    const name = document.getElementById('new-provider-name')?.value || '';
    const apiKey = document.getElementById('openai-api-key').value.trim();
    const baseUrl = document.getElementById('openai-base-url').value.trim();

    // 1. Cập nhật provider (PUT) — chỉ gửi field có giá trị
    const body = {};
    if (apiKey) body.api_key = apiKey;       // rỗng → giữ nguyên key cũ
    if (baseUrl) body.base_url = baseUrl;

    fetch(`/api/providers/${encodeURIComponent(id)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }

        // 2. Kích hoạt provider (POST select)
        return fetch('/api/providers/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ active_id: id })
        });
    })
    .then(r => r && r.json())
    .then(data => {
        if (data && data.success) {
            UiHelpers.showToast(`Đã lưu & kích hoạt ${select.options[select.selectedIndex].text}`, 'success');
            ApiClient.loadModels();  // 3. Reload models cho provider mới
        }
    })
    .catch(e => UiHelpers.showToast(e.message, 'error'));
}
```

**Code mẫu — `GeminiProvider.saveKeys()`:**

```javascript
saveKeys() {
    const textarea = document.getElementById('config-api-keys');
    const keysText = textarea.value.trim();
    if (!keysText) { UiHelpers.showToast('Chưa nhập API key', 'error'); return; }

    fetch('/api/providers')
        .then(r => r.json())
        .then(data => {
            const gemini = data.providers.find(p => p.type === 'gemini');
            if (!gemini) { UiHelpers.showToast('Không tìm thấy Gemini provider', 'error'); return; }

            const keys = keysText.split('\n').map(k => k.trim()).filter(Boolean);
            return fetch(`/api/providers/${gemini.id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ api_keys: keys })
            });
        })
        .then(r => r && r.json())
        .then(data => {
            if (data && !data.error) UiHelpers.showToast('Đã lưu Gemini keys', 'success');
        })
        .catch(e => UiHelpers.showToast(e.message, 'error'));
}
```

**Code mẫu — `OpenAIProvider.addNew()`:**

```javascript
addNew() {
    const nameInput = document.getElementById('new-provider-name');
    const name = nameInput.value.trim();
    if (!name) { UiHelpers.showToast('Chưa nhập tên provider', 'error'); return; }
    if (!/^[a-zA-Z0-9\s]+$/.test(name)) {
        UiHelpers.showToast('Tên chỉ được chứa chữ, số và dấu cách', 'error'); return;
    }

    fetch('/api/providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, type: 'openai' })
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) { UiHelpers.showToast(data.error, 'error'); return; }
        OpenAIProvider.loadProviders(() => {
            document.getElementById('openai-provider-select').value = data.provider.id;
            OpenAIProvider.onSelectProvider(data.provider.id);
        });
        nameInput.value = '';
        UiHelpers.showToast(`Đã thêm "${name}"`, 'success');
    })
    .catch(e => UiHelpers.showToast(e.message, 'error'));
}
```

> Codebase hiện tại dùng global namespace (`ApiClient`, `UiHelpers`) qua script thường, chưa dùng ES module import/export. Vì vậy `provider-manager.js` nên là IIFE/global script tương thích, được load sau `api-client.js` và `ui-helpers.js`, trước khi người dùng mở tab Cấu hình.

### 7.2. Thay đổi trong `main.js`

```javascript
// Thêm import/register:
// <script src="/static/js/provider-manager.js"></script>

// Trong initTabs():
if (targetId === 'config') {
    ApiClient.loadApiKeys();      // Gemini keys
    OpenAIProvider.loadProviders(); // OpenAI providers dropdown
}
```

### 7.3. Thay đổi trong `ui-helpers.js`

```
├── switchProvider() → GIỮ POST /api/provider (đổi active type trên backend),
│   GIỮ toast "Đã chuyển sang..." (chỉ trigger khi click radio/label,
│   KHÔNG trigger khi click input/textarea — đã fix ở HTML section 4.3).
│   Sau POST thành công gọi loadModels().
├── initProvider() → gọi OpenAIProvider.loadProviders() + loadApiKeys()
├── saveOpenAIConfig() → XÓA, thay bằng OpenAIProvider.saveCurrent()
└── saveAppConfig() → giữ nguyên (lưu PROCESSING/MODEL/CACHE)
```

**Lưu ý quan trọng về toast:**
- Yêu cầu gốc: "Bấm vào khối Gemini hoặc OpenAI Compatible mới hiện thông báo 'Đã chuyển sang...', hiện tại bấm vào input form cũng hiện thông báo (sai)"
- Cách sửa: KHÔNG xóa toast, chỉ di chuyển click handler từ `<div>` → `<label>` (xem section 2.1 + 4.3)
- Kết quả: click vào radio/label → hiện toast, click vào input/textarea → không hiện toast

**Bug pre-existing cần fix trong refactor `switchProvider()`:**
Hiện tại `switchProvider()` KHÔNG cập nhật `<span id="current-provider-name">` ở heading. Nếu user chuyển từ Gemini → OpenAI, heading vẫn hiển thị "Chọn model Gemini" cho đến khi reload trang. Cần thêm dòng cập nhật heading trong callback của switchProvider:

```javascript
// Thêm vào switchProvider() — sau khi POST /api/provider thành công:
const nameEl = document.getElementById('current-provider-name');
if (nameEl) nameEl.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
```

**Chi tiết `switchProvider()` sau refactor:**
```javascript
switchProvider(provider) {
    // 1. Đổi UI: radio, border, opacity
    document.querySelectorAll('.nt-provider-col').forEach(col => {
        const isActive = col.dataset.provider === provider;
        col.classList.toggle('b--blue', isActive);
        col.classList.toggle('o-100', isActive);
        col.classList.toggle('b--light-gray', !isActive);
        col.classList.toggle('o-60', !isActive);
        const radio = col.querySelector('input[type="radio"]');
        if (radio) radio.checked = isActive;
    });

    // 2. POST /api/provider để backend đồng bộ active type
    fetch('/api/provider', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            // Toast chỉ hiện khi click radio/label (không hiện khi click input/textarea)
            UiHelpers.showToast(`Đã chuyển sang ${provider === 'gemini' ? 'Google Gemini' : 'OpenAI Compatible'}`, 'success');
            ApiClient.loadModels();  // reload models cho provider mới
        } else {
            UiHelpers.showToast(data.error || 'Lỗi chuyển provider', 'error');
        }
    })
    .catch(e => UiHelpers.showToast(e.message, 'error'));
}
```

**Lưu ý tương thích UI:**
- Badge/current provider name phải hiển thị theo type, còn dropdown hiển thị provider id/name cụ thể.
- Radio provider type là nguồn điều khiển trạng thái runtime duy nhất của app; dropdown chỉ chọn/cập nhật provider record cho type đó.
- Khi đổi radio provider type, backend phải được sync ngay qua `/api/provider` để các endpoint models/info đọc cùng một active type.

### 7.4. Thay đổi trong `api-client.js`

```
├── loadModels() → đọc provider type từ radio, gọi đúng endpoint
│   Nếu provider type = "openai" → /api/openai/models?full=true
│   Nếu provider type = "gemini" → /api/models?full=true
└── loadApiKeys() → GET /api/keys?section=GEMINI (giữ nguyên)
```

**Chi tiết `loadModels()` sau refactor:**
- `loadModels()` chỉ dựa trên active provider type hiện tại trên radio.
- Với Gemini: dùng `/api/models?provider=gemini&full=true`.
- Với OpenAI: dùng `/api/openai/models?full=true`, và endpoint này phải tự đọc provider OpenAI đang active (`active_id`) từ `providers.json`.
- Nếu user đang chỉnh OpenAI provider trong dropdown nhưng chưa bấm lưu/kích hoạt, UI chỉ auto-fill key/base_url; model list vẫn phản ánh provider đang active hiện tại sau khi radio sync.
- `GET /api/model-info/<model_name>` cũng phải đọc active provider từ `providers.json` thông qua helper/service mới.

---

## 8. Kế hoạch triển khai

### Phase 1: Backend — ProviderService rewrite (4h)

**Files cần sửa:**
- `backend/infrastructure/providers/provider_service.py` — REWRITE
- `backend/infrastructure/config/api_key_service.py` — REFACTOR
- `backend/infrastructure/config/app_config_service.py` — delegate `get_active_provider()`, `set_active_provider()`, `get_openai_base_url()`, `get_openai_model()` sang ProviderService (xem Section 6.5)
- `backend/infrastructure/providers/model_catalog_service.py` — refactor `get_openai_models()`, `get_openai_models_full()`, `get_openai_model()` đọc qua ProviderService; xóa dead code ở `get_default_model()` (xem Section 6.6)
- `backend/facade/settings_facade.py` — refactor `get_provider_info()` để trả response shape mới với `active_id` + full `api_key` (xem Section 6.7)
- `webui/routes/settings.py` — thêm endpoints mới + refactor endpoints cũ
- `webui/routes/projects.py` — KHÔNG CẦN sửa trực tiếp (đã cover bởi refactor helpers.py); chỉ verify sau refactor
- `webui/routes/translation.py` — KHÔNG CẦN sửa trực tiếp (đã cover bởi refactor helpers.py); chỉ verify message lỗi không còn nhắc `.env`/`API.txt`
- `webui/helpers.py` — refactor thành wrapper
- `main.py` — refactor load_api_keys(), xóa fallback .env + fix missing `import os` (bug hiện tại)
- `tests/unit/test_provider_services.py`, `tests/unit/test_config_services.py`, `tests/unit/test_helpers.py` — cập nhật test theo providers.json

**Files cần tạo:**
- Không cần tạo Python module mới (ProviderService đã tồn tại)
- `config/providers.json` được tạo runtime bởi migration/UI, nhưng phải nằm trong `.gitignore`

**Files cần xóa:**
- `config/API.txt` — xóa trực tiếp, không backup (dự án cá nhân)
- Sections `[PROVIDER]`, `[OPENAI]` trong `config/app.ini` (giữ PROCESSING/MODEL/CACHE/DIRECTORIES)

**Test cases:**
- Migration từ app.ini + API.txt → providers.json
- Migration không xóa legacy file nếu ghi/validate providers.json fail
- get_active_provider() trả về đúng provider
- get_active_provider_config() trả về provider object đúng active_id
- select_provider() cập nhật active_id
- add/update/delete provider
- Không xóa được gemini-default
- PUT OpenAI provider với `api_key=""` giữ nguyên key cũ để tránh vô tình xóa secret khi form submit rỗng
- providers.json nằm trong .gitignore

### Phase 2: Frontend — UI mới + provider-manager.js (3h)

**Files cần tạo:**
- `webui/static/js/provider-manager.js` — global script/IIFE mới (`window.GeminiProvider`, `window.OpenAIProvider`)

**Files cần sửa:**
- `webui/templates/partials/tab_config.html` — tái cấu trúc UI
- `webui/static/js/ui-helpers.js` — refactor switchProvider, initProvider
- `webui/static/js/api-client.js` — refactor loadModels
- `webui/static/js/main.js` — register module mới

**Test cases:**
- Click vào input không trigger toast
- Dropdown hiển thị đúng providers
- Chọn provider → Base URL auto-fill; API Key xử lý theo quyết định A/B ở mục 1.2
- Thêm provider mới → dropdown cập nhật
- Xóa provider → dropdown cập nhật
- "Chọn model AI" load models từ provider đang active

### Phase 3: Tích hợp & Kiểm thử (2h)

**Test end-to-end:**
- Tạo provider Xiaomi → chọn → loadModels() hiện models Xiaomi
- Chuyển provider → models reload
- Migration: server cũ → server mới không mất config
- Backward compat: các phần khác của app vẫn hoạt động (translation, spellcheck)

### Phase 4: Tài liệu (1h)

- `CHANGELOG.md` — thêm v7.3.0
- `docs/ROADMAP.md` — đánh dấu hoàn thành
- `docs/DEVELOPMENT.md` — thêm section Provider Management
- `docs/MANUAL.md` — hướng dẫn quản lý nhiều provider
- `pyproject.toml` → 7.3.0

---

## 9. Rủi ro & giảm thiểu

| Rủi ro | Tác động | Giảm thiểu |
|--------|----------|------------|
| Migration mất config | User phải nhập lại API keys | Migration chỉ chạy khi providers.json chưa tồn tại; log rõ ràng |
| `providers.json` bị corrupt | Không load được providers | Fail closed: không overwrite file corrupt; API trả lỗi rõ; user sửa/đổi tên file thủ công |
| `providers.json` bị xóa nhầm | Mất toàn bộ config | Không có fallback — user phải tạo lại provider thủ công qua UI |
| Refactor vỡ tests hiện tại | Tests fail | Chạy full test suite sau mỗi bước refactor |
| Legacy callers kỳ vọng provider string | Route/model selection lỗi runtime | Giữ `get_active_provider()` trả string; thêm method mới cho provider object |
| Secret bị lộ qua GET API | API key hiện trong DevTools/log | Chỉ trả full key cho màn hình cấu hình nội bộ; không log full key; sanitize các response không cần secret |

---

## 10. Lệnh commit dự kiến

```bash
git add -A && \
git commit -m "feat(provider): v7.3.0 quản lý nhiều provider + sửa UX click khối provider

Backend:
- Rewrite ProviderService: đọc/ghi từ providers.json (single source of truth)
- Refactor ApiKeyService: gọi ProviderService thay vì đọc API.txt
- API mới: /api/providers (GET/POST/PUT/DELETE) + /api/providers/select
- Migration một chiều: convert → xóa file cũ → không fallback
- Xóa API.txt, xóa [PROVIDER]+[OPENAI] khỏi app.ini
- Loại bỏ fallback .env cho API keys
- Refactor webui/helpers.py + main.py: wrapper gọi backend services

Frontend:
- Sửa UX: click vào input/textarea không trigger toast chuyển provider
- Đổi tên 'OpenAI Compatible' → 'OpenAI Compatible Providers'
- Thêm dropdown chọn provider (từ providers.json) + nút Xóa
- Thêm input tên provider mới + nút Thêm
- Tự động fill Base URL khi chọn provider; API Key xử lý theo quyết định bảo mật A/B
- Tạo provider-manager.js global script (GeminiProvider + OpenAIProvider)
- Validate tên provider: chỉ chữ, số, dấu cách
- Đổi 'Chọn Model cho Gemini' → 'Chọn model AI'
- Đổi 'QA Model' → 'Review Model', ẩn vào Advanced
- Đưa Chunk Size ra khỏi Advanced

Docs:
- Cập nhật CHANGELOG, ROADMAP, DEVELOPMENT, MANUAL cho v7.3.0
- Bump pyproject.toml → 7.3.0"
```

---

## 11. Checklist cho model thực hiện

- [ ] Đọc toàn bộ kế hoạch này trước khi bắt đầu
- [ ] OpenAI API key auto-fill full trong UI cấu hình nội bộ
- [ ] Phase 1: Viết unit test cho ProviderService MỚI trước khi refactor
- [ ] Phase 1: Migration chạy trong `ProviderService.__init__()`, guard `if not providers_file.exists()`
- [ ] Phase 1: Ghi `providers.json` bằng atomic write (tmp → validate → rename) trước khi xóa legacy files
- [ ] Phase 1: Bảo vệ `gemini-default` — không cho xóa qua UI/API (xem code mẫu section 3.3)
- [ ] Phase 1: Migration một chiều — convert → xóa file cũ → không fallback
- [ ] Phase 1: Thêm `config/providers.json` vào `.gitignore` (giữ `config/app.ini` NGOÀI gitignore — intentional)
- [ ] Phase 1: Refactor tuần tự 10 bước: ProviderService → ApiKeyService → AppConfigService → ModelCatalogService → SettingsFacade → helpers.py → main.py → tests → migration → tests lần 2
- [ ] Phase 1: `AppConfigService` — delegate 4 provider methods sang ProviderService (xem Section 6.5)
- [ ] Phase 1: `ModelCatalogService` — refactor đọc key/url/model qua ProviderService, xóa dead code (xem Section 6.6)
- [ ] Phase 1: `SettingsFacade.get_provider_info()` — cập nhật response shape (xem Section 6.7)
- [ ] Phase 1: `ProviderService.get_available_providers()` — trả data từ providers.json, KHÔNG import services.ai_provider
- [ ] Phase 1: `main.py` — không copy logic cũ (có bug missing `import os`), delegate sang ApiKeyService
- [ ] Phase 1: `translation.py`, `projects.py` — KHÔNG cần sửa trực tiếp, chỉ verify sau refactor helpers.py
- [ ] Phase 1: Giữ public wrappers tương thích (`get_active_provider()` trả string)
- [ ] Phase 1: **KHÔNG xóa API.txt cho đến khi tất cả tests pass**
- [ ] Phase 2: `switchProvider()` — GIỮ POST `/api/provider`, GIỮ toast (xem Section 7.3 + bug heading fix)
- [ ] Phase 2: HTML — giữ nguyên `x-data` ở div cha, chỉ chuyển `x-on:click` xuống `<label>` (xem Section 4.3)
- [ ] Phase 2: Validate tên provider: `^[a-zA-Z0-9\s]+$`
- [ ] Phase 2: Đăng ký `provider-manager.js` như global script/IIFE đúng thứ tự load
- [ ] Phase 3: Chạy `pytest` toàn bộ test suite
- [ ] Phase 3: Test thủ công: tạo/xóa/chuyển provider, load models
- [ ] Phase 3: Test migration fail path: không mất `API.txt`/`app.ini` nếu ghi providers.json lỗi
- [ ] Phase 4: Bump version trong `pyproject.toml` TRƯỚC khi commit
- [ ] Không commit secrets (API keys) vào git — kiểm tra `.gitignore`

---

## 12. Chi tiết triển khai cụ thể (bổ sung từ review)

> Phần này cung cấp code mẫu + chỉ dẫn chính xác cho model thực hiện, dựa trên codebase thực tế đã verify.

### 12.1. `tab_config.html` — Thay đổi chính xác theo line range

**A. Sửa click handler (xóa bug UX):**

| Dòng hiện tại | Sửa |
|---------------|-----|
| 16 (Gemini col) | Xóa `x-on:click="activeProvider = 'gemini'; UiHelpers.switchProvider('gemini')"` khỏi `<div id="provider-gemini-col" ...>` |
| 19 (label Gemini) | Thêm `x-on:click="activeProvider = 'gemini'; UiHelpers.switchProvider('gemini')"` vào `<label class="flex items-center pointer">` |
| 40 (OpenAI col) | Xóa `x-on:click="activeProvider = 'openai'; UiHelpers.switchProvider('openai')"` khỏi `<div id="provider-openai-col" ...>` |
| 43 (label OpenAI) | Thêm `x-on:click="activeProvider = 'openai'; UiHelpers.switchProvider('openai')"` vào `<label class="flex items-center pointer">` |
| 45 (text OpenAI) | Đổi `"OpenAI Compatible"` → `"OpenAI Compatible Providers"` |
| 53 (placeholder API Key) | Đổi `"Nhập API Key hoặc để trống nếu cấu hình qua ENV"` → `"Nhập API Key"` (bỏ nhắc ENV) |
| 57 (text Base URL) | Xóa `<small class="silver mt1 db f7">Để trống nếu dùng trực tiếp OpenAI</small>` (gây nhầm lẫn) |

**B. Move Chunk Size ra ngoài Advanced, Move QA Model vào Advanced:**

Trước khi sửa, cấu trúc hiện tại (dòng 84-170):
- Dòng 87-95: `QA Model` field (NGOÀI details)
- Dòng 96-108: `Thinking Level` field (NGOÀI details, giữ nguyên)
- Dòng 112-169: `<details>Advanced</details>` chứa Chunk Size, Context Radius, Temperature, API Delay, Antilag, Cache

Sau khi sửa:
- Dòng 87-95: **Chunk Size** (chuyển từ Advanced ra, thay vị trí cũ)
- Dòng 96-108: `Thinking Level` (giữ nguyên)
- Dòng 112-169: `<details>Advanced</details>` chứa **Review Model** (đổi tên từ QA Model), Context Radius, Temperature, API Delay, Antilag, Cache

**Mã HTML chính xác cần thay:**

```html
<!-- Dòng 87-95: THAY "QA Model" → "Chunk Size" -->
<div class="w-100 w-50-ns ph2 mb3">
    <label class="db fw6 lh-copy f7 mb2 gray uppercase tracked">
        Chunk Size
        <span class="nt-tooltip-container">
            <span class="nt-help-icon" data-tooltip="Số ký tự tối đa cho mỗi đoạn văn bản AI xử lý một lần.">ⓘ</span>
        </span>
    </label>
    <input type="number" id="chunk-size" name="PROCESSING.MAX_CHARS_PER_CHUNK" min="1000" class="ba b--black-10 br2 pa2 w-100 f7 outline-0">
</div>

<!-- Trong <details> (sau dòng 116): THÊM "Review Model" -->
<div class="w-100 w-50-ns ph2 mb3">
    <label class="db fw6 lh-copy f7 mb2 gray uppercase tracked">
        Review Model
        <span class="nt-tooltip-container">
            <span class="nt-help-icon" data-tooltip="Dùng để rà soát & sửa lỗi bản dịch sau khi hoàn tất.">ⓘ</span>
        </span>
    </label>
    <select id="cfg-qa-model" name="MODEL.QA_MODEL" class="ba b--black-10 br2 pa2 w-100 f7 outline-0"></select>
</div>
```

**C. Đổi heading dòng 71:**

```html
<!-- TRƯỚC -->
<h3 class="f5 fw6 mt0 mb3 dark-gray">Chọn Model cho <span id="current-provider-name" class="blue fw7">Gemini</span></h3>

<!-- SAU -->
<h3 class="f5 fw6 mt0 mb3 dark-gray">Chọn model <span id="current-provider-name" class="blue fw7">AI</span></h3>
```

**D. Thêm block OpenAI Provider dropdown (sau dòng 50, trước dòng 52):**

Xem code mẫu đầy đủ ở section 4.4 trong plan — chèn vào giữa logo và field API Key.

### 12.2. Endpoint `/api/keys` — Mapping `section` → `type`

Endpoint hiện tại: `webui/routes/settings.py:367-393`

| Query param | Sau migration |
|-------------|---------------|
| `?section=GEMINI` | Map sang provider có `type="gemini"` → trả `api_keys` array joined bằng `\n` |
| `?section=OPENAI` | Map sang provider đang active có `type="openai"` → trả `api_key` (string) wrapped trong 1 dòng |
| `?section=<id>` (mới) | Map sang provider có `id=<id>` → trả `api_keys` hoặc `api_key` tùy type |

**Code refactor `/api/keys` (viết lại route):**

```python
@settings_bp.route("/api/keys", methods=["GET", "POST"])
@handle_route_errors
def manage_api_keys():
    """Lấy hoặc lưu danh sách API keys theo provider type (mặc định: gemini)."""
    section = request.args.get("section", "GEMINI").upper()

    if request.method == "GET":
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService()

        if section == "OPENAI":
            # Trả single key cho active OpenAI provider
            active = provider_service.get_active_provider_config()
            if active and active.get("type") == "openai":
                api_key = active.get("api_key", "")
                return jsonify({"content": api_key, "provider_id": active["id"]})
            return jsonify({"content": ""})

        # GEMINI (default)
        # Lấy keys từ provider type=gemini (không phụ thuộc active)
        providers = provider_service.get_providers_by_type("gemini")
        all_keys = []
        for p in providers:
            all_keys.extend(p.get("api_keys", []))
        return jsonify({"content": "\n".join(all_keys)})

    # POST
    from backend.infrastructure.providers.provider_service import ProviderService
    provider_service = ProviderService()

    data = request.json
    keys_text = data.get("content", "")

    if section == "OPENAI":
        # Lưu vào active OpenAI provider
        active = provider_service.get_active_provider_config()
        if active and active.get("type") == "openai":
            api_key = keys_text.strip()
            if api_key:
                provider_service.update_provider(active["id"], api_key=api_key)
            return jsonify({"success": True})
        return jsonify({"error": "Không có OpenAI provider đang active"}), 400

    # GEMINI
    keys = [k.strip() for k in keys_text.splitlines() if k.strip()]
    providers = provider_service.get_providers_by_type("gemini")
    if not providers:
        return jsonify({"error": "Không tìm thấy Gemini provider"}), 400
    # Cập nhật provider đầu tiên (gemini-default)
    provider_service.update_provider(providers[0]["id"], api_keys=keys)
    return jsonify({"success": True})
```

### 12.3. `app.ini` — Xóa sections bằng `configparser.remove_section()`

Sau migration, `app.ini` chỉ còn `[MODEL]`, `[PROCESSING]`, `[DIRECTORIES]`, `[CACHE]`. **Code xóa sections:**

```python
# Trong ProviderService._migrate_from_legacy() — SAU khi providers.json đã ghi thành công
def _cleanup_app_ini(self) -> None:
    """Xóa [PROVIDER], [OPENAI], [API] sections khỏi app.ini (giữ format + comments)."""
    import configparser
    config = configparser.ConfigParser()
    config.optionxform = str  # Preserve case
    app_ini = self._config_dir / "app.ini"
    if not app_ini.exists():
        return
    config.read(app_ini, encoding="utf-8")

    # Xóa các sections legacy
    for section in ("PROVIDER", "OPENAI", "API"):
        if config.has_section(section):
            config.remove_section(section)

    # Ghi lại (configparser bảo toàn comments nếu dùng RawConfigParser)
    # Nếu cần giữ comments, dùng RawConfigParser:
    # raw = configparser.RawConfigParser()
    with open(app_ini, "w", encoding="utf-8") as f:
        config.write(f)
```

**Lưu ý quan trọng về comments:**
- `configparser.ConfigParser` KHÔNG giữ inline comments khi ghi lại.
- Nếu `app.ini` hiện tại có comments (ví dụ `# Cấu hình Gemini`), comments sẽ mất.
- **Verify app.ini hiện tại trước khi migrate:** Đọc file, nếu có comments → dùng `RawConfigParser` hoặc giữ nguyên file nếu không có comments quan trọng.

### 12.4. Active provider fallback khi `active_id` missing

Trong `ProviderService.get_active_provider()`, cần handle trường hợp `active_id` trong `providers.json` không match provider nào:

```python
def get_active_provider(self) -> str:
    """Trả type string ('gemini' | 'openai') của active provider. Fallback an toàn."""
    data = self.load_providers()

    active_id = data.get("active_id")
    providers = data.get("providers", [])

    # Tìm provider có id = active_id
    active = next((p for p in providers if p.get("id") == active_id), None)

    if active:
        return active.get("type", "gemini")

    # Fallback 1: chọn provider đầu tiên có type=gemini
    gemini_first = next((p for p in providers if p.get("type") == "gemini"), None)
    if gemini_first:
        logger.warning(f"active_id '{active_id}' không tồn tại, fallback sang '{gemini_first['id']}'")
        return "gemini"

    # Fallback 2: chọn provider đầu tiên bất kỳ
    if providers:
        first_type = providers[0].get("type", "gemini")
        logger.warning(f"Không có Gemini provider, fallback sang provider đầu tiên: {first_type}")
        return first_type

    # Fallback 3: trả gemini (mặc định hệ thống)
    return "gemini"
```

**Tương tự cho `get_active_provider_config()`:**
```python
def get_active_provider_config(self) -> Optional[dict]:
    """Trả full provider object đang active. Fallback chain giống get_active_provider()."""
    data = self.load_providers()
    active_id = data.get("active_id")
    providers = data.get("providers", [])

    active = next((p for p in providers if p.get("id") == active_id), None)
    if active:
        return active

    # Fallback: provider đầu tiên
    return providers[0] if providers else None
```

### 12.5. `select_provider_by_type()` cho legacy `/api/provider` POST

Endpoint `/api/provider` POST hiện nhận `{provider: "gemini"|"openai"}` — KHÔNG có id. Logic mới:

```python
def select_provider_by_type(self, type: str) -> Optional[str]:
    """
    Chọn provider mặc định theo type (cho legacy /api/provider POST).
    Trả về id của provider được chọn, hoặc None nếu không có provider nào thuộc type đó.
    """
    if type not in ("gemini", "openai"):
        raise ValueError(f"Invalid provider type: {type}")

    data = self.load_providers()
    providers = data.get("providers", [])

    # Ưu tiên 1: provider có key (api_keys hoặc api_key) của type này
    same_type = [p for p in providers if p.get("type") == type]
    with_key = [p for p in same_type if p.get("api_key") or p.get("api_keys")]
    if with_key:
        chosen_id = with_key[0]["id"]
    elif same_type:
        chosen_id = same_type[0]["id"]
    else:
        return None  # Không có provider thuộc type này

    # Set active_id
    data["active_id"] = chosen_id
    self.save_providers(data)
    return chosen_id
```

### 12.6. `add_provider()` — Signature và validation

```python
def add_provider(
    self,
    name: str,
    type: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    api_keys: Optional[List[str]] = None,
    default_model: Optional[str] = None,
) -> dict:
    """
    Tạo provider mới. Tự sinh id từ name.
    """
    if type not in ("gemini", "openai"):
        raise ValueError(f"Invalid type: {type}")

    # Validate name
    if not re.match(r"^[a-zA-Z0-9\s]+$", name):
        raise ValueError("Tên chỉ được chứa chữ, số và dấu cách")

    # Sinh id từ name
    base_id = re.sub(r"\s+", "-", name.strip().lower())
    base_id = re.sub(r"[^a-z0-9\-]", "", base_id)  # Bỏ ký tự đặc biệt
    if not base_id:
        raise ValueError("Tên provider không hợp lệ sau khi normalize")

    data = self.load_providers()

    # Resolve id trùng
    existing_ids = {p["id"] for p in data["providers"]}
    new_id = base_id
    suffix = 2
    while new_id in existing_ids:
        new_id = f"{base_id}-{suffix}"
        suffix += 1

    # Bảo vệ gemini-default
    if new_id == "gemini-default":
        raise ValueError("Không thể tạo provider với id 'gemini-default' (id hệ thống)")

    # Tạo provider object
    provider = {
        "id": new_id,
        "type": type,
        "name": name.strip(),
    }
    if type == "openai":
        provider["api_key"] = api_key or ""
        provider["base_url"] = base_url or ""
    else:  # gemini
        provider["api_keys"] = api_keys or []
    provider["default_model"] = default_model or ""

    data["providers"].append(provider)
    self.save_providers(data)

    return provider
```

### 12.7. `webui/helpers.py` — Concrete refactor map

Đã verify: 5 file import `webui.helpers` (không phải 143):
- `webui/routes/settings.py` (10 imports)
- `webui/routes/projects.py` (3 imports)
- `webui/routes/translation.py` (2 imports)
- `main.py` (1 import)
- `backend/facade/settings_facade.py` (1 import)
- `webui/__init__.py` (1 import, chỉ `ensure_default_project`)
- `core/executor.py` (1 import, chỉ `calculate_stats`)
- `tests/unit/test_helpers.py` (multiple test imports)

**Tổng: 19 import sites, không phải 143 như plan nói.**

**Code refactor mẫu cho `webui/helpers.py` (giữ signature, đổi logic):**

```python
# webui/helpers.py - v5.1.0 (refactored)
# Wrapper layer — tất cả logic thực sự ở backend services.
# File này CHỈ giữ signature để backward compat với 19 import sites.

from backend.infrastructure.providers.provider_service import ProviderService
from backend.infrastructure.config.api_key_service import ApiKeyService
from backend.infrastructure.config.app_config_service import AppConfigService
import configparser
from pathlib import Path
import re
import logging

logger = logging.getLogger(__name__)

AVAILABLE_GEMINI_MODELS = [...]  # giữ nguyên
AVAILABLE_OPENAI_MODELS = [...]  # giữ nguyên


def get_app_version():
    """GIỮ NGUYÊN — đọc từ CHANGELOG.md."""
    # ... code cũ giữ nguyên ...


def load_config():
    """GIỮ NGUYÊN — đọc app.ini cho PROCESSING/MODEL/CACHE."""
    config = configparser.ConfigParser()
    config.optionxform = str
    config_file = Path("config/app.ini")
    if config_file.exists():
        config.read(config_file, encoding="utf-8")
    return config


def get_default_chunk_size():
    """GIỮ NGUYÊN."""
    config = load_config()
    try:
        return config.getint("PROCESSING", "MAX_CHARS_PER_CHUNK", fallback=100000)
    except Exception:
        return 100000


def get_default_model():
    """GIỮ NGUYÊN — đọc [MODEL] MODEL section (vẫn còn trong app.ini)."""
    config = load_config()
    try:
        return config.get("MODEL", "MODEL", fallback="gemini-2.0-flash-exp")
    except Exception:
        return "gemini-2.0-flash-exp"


def get_active_provider():
    """REFACTOR — gọi ProviderService."""
    try:
        return ProviderService().get_active_provider()
    except Exception as e:
        logger.debug(f"get_active_provider fallback: {e}")
        return "gemini"


def load_openai_key():
    """REFACTOR — đọc từ active OpenAI provider trong providers.json.
    Trả về string hoặc chuỗi rỗng (KHÔNG trả None — giữ backward compat với code cũ).
    Lưu ý: Code cũ trả None khi không tìm thấy key. Code mới trả "".
    Đã verify callers: settings.py (if not api_key), openai_client (if api_key),
    get_available_openai_models (if api_key) — tất cả đều dùng truthiness check
    nên "" và None đều xử lý giống nhau. Không có caller nào phân biệt None vs ""."""
    try:
        active = ProviderService().get_active_provider_config()
        if active and active.get("type") == "openai":
            return active.get("api_key", "")
    except Exception as e:
        logger.debug(f"load_openai_key error: {e}")
    return ""  # String rỗng thay vì None


def get_openai_base_url():
    """REFACTOR — gọi ProviderService."""
    try:
        return ProviderService().get_active_base_url()
    except Exception:
        return None


def get_openai_model():
    """REFACTOR — gọi ProviderService."""
    try:
        return ProviderService().get_active_default_model()
    except Exception:
        return "gpt-4o-mini"


def _parse_api_file(filepath):
    """❌ XÓA — không còn cần vì API.txt bị xóa.
    Nếu xóa hoàn toàn: tất cả caller phải được sửa.
    Verify callers trước khi xóa."""
    # Callers: webui/routes/settings.py:376 (trong manage_api_keys) — sẽ được refactor
    # + tests/unit/test_helpers.py:140-174 (4 test cases) — cần xóa class TestHelpersParseApiFile
    # Sau refactor /api/keys endpoint + xóa test, caller này sẽ được sửa → có thể xóa _parse_api_file
    raise NotImplementedError("_parse_api_file đã bị xóa sau migration v7.3.0")


def get_available_models():
    """GIỮ NGUYÊN signature — chỉ thay đổi logic gọi services."""
    provider = get_active_provider()
    if provider == "openai":
        return get_available_openai_models()
    return get_available_gemini_models()


def get_available_gemini_models():
    """GIỮ NGUYÊN signature — logic bên trong không đổi nhiều."""
    # ... giữ code cũ, chỉ thay get_default_model() đã được refactor ...


def get_available_openai_models():
    """GIỮ NGUYÊN signature."""
    # ... giữ code cũ ...


def load_api_keys(section=None):
    """REFACTOR — trả về list of keys.
    Nếu section=None: flatten tất cả providers (GEMINI + OPENAI) — giữ semantic cũ.
    Nếu section='GEMINI': keys từ Gemini providers.
    Nếu section='OPENAI': [active api_key] wrapped trong list."""
    try:
        provider_service = ProviderService()
        if section is None:
            # Flatten ALL keys from ALL providers (GEMINI + OPENAI)
            # Giữ semantic cũ: calculate_stats() dùng load_api_keys() để đếm tổng keys
            all_keys = []
            for p in provider_service.load_providers().get("providers", []):
                if p.get("type") == "gemini":
                    all_keys.extend(p.get("api_keys", []))
                else:
                    if p.get("api_key"):
                        all_keys.append(p["api_key"])
            return all_keys
        # Có section cụ thể
        type_name = "gemini" if section.upper() == "GEMINI" else "openai"
        providers = provider_service.get_providers_by_type(type_name)
        keys = []
        for p in providers:
            if type_name == "openai":
                if p.get("api_key"):
                    keys.append(p["api_key"])
            else:
                keys.extend(p.get("api_keys", []))
        return keys
    except Exception as e:
        logger.debug(f"load_api_keys error: {e}")
        return []


def save_api_keys(keys_text, section="GEMINI"):
    """REFACTOR — gọi ProviderService thay vì ghi API.txt."""
    try:
        provider_service = ProviderService()
        if section.upper() == "OPENAI":
            active = provider_service.get_active_provider_config()
            if active and active.get("type") == "openai":
                api_key = keys_text.strip()
                if api_key:
                    provider_service.update_provider(active["id"], api_key=api_key)
                return True
            return False
        # GEMINI
        keys = [k.strip() for k in keys_text.splitlines() if k.strip()]
        providers = provider_service.get_providers_by_type("gemini")
        if providers:
            provider_service.update_provider(providers[0]["id"], api_keys=keys)
            return True
        return False
    except Exception as e:
        logger.error(f"save_api_keys error: {e}")
        return False


# calculate_stats, load_prompts, save_prompts, ensure_default_project: GIỮ NGUYÊN
# (không liên quan provider management)
```

### 12.8. Note quan trọng về `webui/__init__.py:86`

```python
# webui/__init__.py:86 — import ensure_default_project
# Hàm này KHÔNG bị refactor (không liên quan provider).
# Chỉ cần đảm bảo import path vẫn hoạt động.
```

### 12.9. Test files đã verify tồn tại

| File test | Trạng thái | Cần cập nhật |
|-----------|------------|--------------|
| `tests/unit/test_helpers.py` | ✅ Tồn tại (217 lines) | 1. Xóa class `TestHelpersParseApiFile` (dòng 135-183) — `_parse_api_file` bị xóa. 2. Cập nhật `test_load_api_keys_returns_list` dùng providers.json fixture. 3. Cập nhật `test_get_active_provider_returns_string` dùng providers.json fixture. |
| `tests/unit/test_provider_services.py` | ✅ Tồn tại (7.4K) | Viết lại toàn bộ test cho ProviderService mới (providers.json-based) |
| `tests/unit/test_config_services.py` | ✅ Tồn tại (8.6K) | Cập nhật test cho AppConfigService sau khi delegate sang ProviderService |

### 12.10. Cảnh báo quan trọng khi sửa `app.ini`

- **`config/app.ini` hiện tại** có section `[API]` rỗng (line 4) — KHÔNG có comments. Sau migration sẽ bị xóa.
- **`config/app.ini` KHÔNG có comments** ở các sections còn giữ (verified). An toàn để dùng `configparser` thường.
- Sau migration, **KHÔNG được** ghi lại `app.ini` với format mới nếu chưa xóa xong legacy sections — sẽ duplicate.

### 12.11. Lệnh kiểm tra trước khi commit

```bash
# 1. Chạy test suite
pytest tests/unit/ -v

# 2. Verify providers.json hợp lệ
python -c "import json; print(json.load(open('config/providers.json')))"

# 3. Verify app.ini đã sạch
grep -E "^\[(PROVIDER|OPENAI|API)\]" config/app.ini
# Kết quả mong đợi: KHÔNG có output (sections đã bị xóa)

# 4. Verify API.txt đã xóa
ls config/API.txt 2>&1
# Kết quả mong đợi: "No such file or directory"

# 5. Verify .gitignore đã có providers.json
grep "providers.json" .gitignore
# Kết quả mong đợi: "config/providers.json"

# 6. Verify app.ini vẫn ngoài .gitignore
grep "app.ini" .gitignore
# Kết quả mong đợi: KHÔNG có output

# 7. Verify không có secrets trong git diff
git diff config/
# Kết quả mong đợi: KHÔNG có API key nào hiển thị
```
