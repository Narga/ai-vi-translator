# Kế hoạch sửa tab Biên tập, tab Thông tin và AI Provider

Ngày lập: 2026-06-11  
Ngày cập nhật: 2026-06-11 (bản v2 — chi tiết hóa toàn bộ)

Phạm vi: kế hoạch thực thi cụ thể, bất cứ model nào cũng có thể thi hành từng bước.

---

## 0. Tổng quan kiến trúc hiện tại

```
Frontend (JS)                          Backend (Python/Flask)
─────────────────                      ─────────────────────
ui-helpers.js                          settings.py
  UiHelpers.switchProvider()             /api/providers (GET/POST)
    → POST /api/provider ❌ 404!         /api/providers/<id> (PUT/DELETE)
  UiHelpers.initProvider()               /api/providers/select (POST)
    → GET /api/provider ❌ 404!          /api/models (GET) — auto-detect provider
                                         /api/openai/models (GET) — openai-only
api-client.js
  ApiClient.loadModels()               projects.py
    → reads DOM radio to choose          /api/projects/<slug>/summarize (POST)
       /api/models or /api/openai/models /api/projects/<slug>/guidelines (GET/PUT)

provider-manager.js                    provider_service.py (ProviderService)
  GeminiProvider, OpenAIProvider         config/providers.json = source of truth
  → dùng /api/providers/* ✅

prompt-manager.js
  PromptManager.aiGenerateContent()
    → hardcoded ids: 'style-guide-model', 'guide-style-guide'
    → tab Dự án dùng prefix 'pm-*' → MIS-MATCH!

project-manager.js
  deleteSelectedSpellFiles() → chỉ xóa spelling
  chưa có deleteSelectedSourceFiles()
```

## 1. Ba nhóm vấn đề cần xử lý

### 1.1. Thiếu nút xóa đã chọn trong tab Biên tập (ĐỘ ƯU TIÊN: thấp, đơn giản nhất)

**Hiện trạng xác nhận bằng code:**
- Tab Kiểm chính tả (`tab_projects.html:175`) có nút gọi `deleteSelectedSpellFiles()` 
- Tab Biên tập (`tab_projects.html:92-98`) có 4 nút: upload, chia chunk, dịch đã chọn, ghép — THIẾU nút xóa
- `deleteSelectedSpellFiles()` ở `project-manager.js:705-724` — hardcode `spelling` section

### 1.2. Generate tab Thông tin hoạt động sai (ĐỘ ƯU TIÊN: trung bình)

**Hiện trạng xác nhận bằng code:**
- Template `tab_projects.html:256-258`: có DUY NHẤT 1 model select `pm-style-guide-model`, 1 nút Generate hardcode gọi `PromptManager.aiGenerateContent('style_guide')`, 1 nút Lưu hardcode `saveGuidelineField('style_guide')`
- `aiGenerateContent()` ở `prompt-manager.js:385-431`:
  - `modelSelMap` tìm id `style-guide-model` (KHÔNG có prefix `pm-`) → **không match** với `pm-style-guide-model` trong template
  - `outputElMap` tìm id `guide-style-guide` (KHÔNG có prefix `pm-`) → **không match** với `pm-guide-style-guide` trong template
  - Body gửi: `{ model, content_type }` — **KHÔNG gửi `source_file`**
- Backend `summarize_project()` (`projects.py:1072-1218`):
  - Nhận `source_file = data.get("source_file", "")` → luôn rỗng
  - Fallback: gom TẤT CẢ `.txt` + `.md` trong `sources/` → không đúng kỳ vọng
  - Response: `{ "success": true, "summary": result }` — dùng key `summary` cho mọi content_type
- **Không có dropdown chọn source file** trong tab Thông tin

### 1.3. Lỗi JSON.parse khi chuyển AI Provider (ĐỘ ƯU TIÊN: cao, nghiêm trọng)

**Hiện trạng xác nhận bằng code:**
- `UiHelpers.switchProvider()` (`ui-helpers.js:191`): `fetch('/api/provider', ...)` → **route không tồn tại** → Flask trả 404 HTML → `r.json()` → crash
- `UiHelpers.initProvider()` (`ui-helpers.js:237`): `fetch('/api/provider')` → **route không tồn tại** → crash
- Backend `settings.py` KHÔNG có route `/api/provider` — chỉ có `/api/providers`, `/api/providers/<id>`, `/api/providers/select`
- `ApiClient.loadModels()` (`api-client.js:49-52`): đọc DOM radio `input[name="active_provider"]:checked` để chọn endpoint → **không đồng bộ với backend**

---

## 2. Quyết định thiết kế đã chốt

| # | Quyết định | Lý do |
|---|-----------|-------|
| D1 | Thêm shim `/api/provider` tạm thời 1 phiên bản | Không phá test cũ, cho phép sửa frontend từng bước |
| D2 | Xóa source file KHÔNG xóa translated cùng tên | An toàn dữ liệu dịch |
| D3 | Generate bắt buộc chọn source file, không tự gom tất cả | UX rõ ràng |
| D4 | Giữ dynamic glossary injection, chưa thêm placeholder phase này | Tránh prompt quá dài |

---

## 3. Thực thi chi tiết — 4 bước theo thứ tự

> **Quy tắc cho model thực thi:**
> - Chạy `git status --short` trước khi bắt đầu
> - KHÔNG revert thay đổi sẵn có của user
> - Mỗi bước xong phải chạy test liên quan trước khi chuyển bước tiếp
> - Chạy `gitnexus_detect_changes()` trước khi commit

---

### BƯỚC 1: Sửa Provider — Khẩn cấp (ước lượng: ~45 phút)

#### 1.1. Thêm shim `/api/provider` vào backend

**File:** `webui/routes/settings.py`  
**Vị trí:** Thêm sau dòng `settings_bp = Blueprint(...)` (khoảng dòng 19), TRƯỚC các route hiện tại.

**Code thêm mới:**

```python
# ------------------------------------------------------------------
# DEPRECATED SHIM: /api/provider — sẽ xóa ở phiên bản tiếp theo
# Frontend cũ vẫn gọi endpoint này. Delegate sang ProviderService.
# ------------------------------------------------------------------

@settings_bp.route("/api/provider", methods=["GET", "POST"])
def legacy_provider_shim():
    """[DEPRECATED] Shim cho frontend cũ. Dùng /api/providers/* thay thế."""
    from backend.infrastructure.providers.provider_service import ProviderService
    provider_service = ProviderService()

    if request.method == "GET":
        active = provider_service.get_active_provider_config()
        if not active:
            return jsonify({"active": "gemini", "provider": {}})
        return jsonify({
            "active": active.get("type", "gemini"),
            "active_id": active.get("id", ""),
            "provider": active,
        })

    # POST: { "provider": "gemini" } hoặc { "provider": "openai" }
    data = request.json or {}
    provider_type = data.get("provider", "gemini")
    try:
        providers = provider_service.get_providers_by_type(provider_type)
        if not providers:
            return jsonify({"error": f"Không tìm thấy provider loại {provider_type}"}), 400
        # Kích hoạt provider đầu tiên của type đó
        provider_service.select_provider(providers[0]["id"])
        return jsonify({"success": True, "active": provider_type, "active_id": providers[0]["id"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
```

**Tại sao thêm shim thay vì sửa frontend ngay:** Shim cho phép UI hoạt động NGAY LẬP TỨC trong khi ta sửa frontend ở bước dưới. Nếu frontend chưa kịp deploy bản mới, shim vẫn giữ cho app không crash.

#### 1.2. Thêm `fetchJson` an toàn vào `ApiClient`

**File:** `webui/static/js/api-client.js`  
**Thay đổi:** Sửa method `fetchJson` hiện tại (dòng 6-11)

**TRƯỚC (dòng 6-11):**
```js
    fetchJson(url, options) {
        return fetch(url, options).then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}: ${r.statusText}`);
            return r.json();
        });
    },
```

**SAU:**
```js
    fetchJson(url, options) {
        return fetch(url, options).then(async r => {
            const text = await r.text();
            let data;
            try {
                data = text ? JSON.parse(text) : {};
            } catch {
                throw new Error(`Server không trả JSON (${r.status}): ${text.slice(0, 120)}`);
            }
            if (!r.ok) throw new Error(data.error || `HTTP ${r.status}`);
            return data;
        });
    },
```

#### 1.3. Sửa `UiHelpers.switchProvider()` — dùng API mới

**File:** `webui/static/js/ui-helpers.js`  
**Thay đổi:** Sửa method `switchProvider` (dòng 175-209)

**TRƯỚC (dòng 175-209):**
```js
    switchProvider(provider) {
        document.querySelectorAll('.nt-provider-col').forEach(col => {
            const isActive = col.dataset.provider === provider;
            if (isActive) {
                col.classList.add('b--blue', 'o-100');
                col.classList.remove('b--light-gray', 'o-60');
                const radio = col.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            } else {
                col.classList.add('b--black-10', 'o-60');
                col.classList.remove('b--blue', 'o-100');
                const radio = col.querySelector('input[type="radio"]');
                if (radio) radio.checked = false;
            }
        });

        fetch('/api/provider', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ provider })
        })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    UiHelpers.showToast(`Đã chuyển sang ${provider === 'gemini' ? 'Google Gemini' : 'OpenAI Compatible'}`, 'success');
                    ApiClient.loadModels();
                    // Cập nhật heading
                    const nameEl = document.getElementById('current-provider-name');
                    if (nameEl) nameEl.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
                } else {
                    UiHelpers.showToast(data.error || 'Lỗi chuyển provider', 'error');
                }
            })
            .catch(e => UiHelpers.showToast(e.message, 'error'));
    },
```

**SAU:**
```js
    switchProvider(provider) {
        document.querySelectorAll('.nt-provider-col').forEach(col => {
            const isActive = col.dataset.provider === provider;
            if (isActive) {
                col.classList.add('b--blue', 'o-100');
                col.classList.remove('b--light-gray', 'o-60');
                const radio = col.querySelector('input[type="radio"]');
                if (radio) radio.checked = true;
            } else {
                col.classList.add('b--black-10', 'o-60');
                col.classList.remove('b--blue', 'o-100');
                const radio = col.querySelector('input[type="radio"]');
                if (radio) radio.checked = false;
            }
        });

        // Tìm provider id phù hợp từ danh sách providers
        ApiClient.fetchJson('/api/providers')
            .then(data => {
                const providers = data.providers || [];
                const match = providers.find(p => p.type === provider);
                if (!match) {
                    UiHelpers.showToast(`Không tìm thấy provider loại ${provider}`, 'error');
                    return;
                }
                return ApiClient.fetchJson('/api/providers/select', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ active_id: match.id })
                });
            })
            .then(data => {
                if (data && data.success) {
                    UiHelpers.showToast(`Đã chuyển sang ${provider === 'gemini' ? 'Google Gemini' : 'OpenAI Compatible'}`, 'success');
                    ApiClient.loadModels();
                    const nameEl = document.getElementById('current-provider-name');
                    if (nameEl) nameEl.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
                }
            })
            .catch(e => UiHelpers.showToast(e.message, 'error'));
    },
```

#### 1.4. Sửa `UiHelpers.initProvider()` — dùng API mới

**File:** `webui/static/js/ui-helpers.js`  
**Thay đổi:** Sửa method `initProvider` (dòng 236-265)

**TRƯỚC (dòng 236-265):**
```js
    initProvider() {
        fetch('/api/provider')
            .then(r => r.json())
            .then(data => {
                if (data.active) {
                    const provider = data.active;
                    // ... rest of init code
```

**SAU:**
```js
    initProvider() {
        ApiClient.fetchJson('/api/providers')
            .then(data => {
                const activeId = data.active_id || '';
                const providers = data.providers || [];
                const active = providers.find(p => p.id === activeId);
                const provider = active ? active.type : 'gemini';

                const radio = document.querySelector(`input[name="active_provider"][value="${provider}"]`);
                if (radio) radio.checked = true;

                document.querySelectorAll('.nt-provider-col').forEach(col => {
                    col.classList.toggle('nt-provider-active', col.dataset.provider === provider);
                });

                const badge = document.getElementById('provider-active-badge');
                if (badge) {
                    badge.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';
                    badge.className = 'f7 fw6 ph2 pv1 br2 ' +
                        (provider === 'gemini' ? 'bg-light-green dark-green' : 'bg-lightest-blue dark-blue');
                }
                const nameEl = document.getElementById('current-provider-name');
                if (nameEl) nameEl.textContent = provider === 'gemini' ? 'Gemini' : 'OpenAI';

                // Load OpenAI providers dropdown (new in v7.3.0)
                if (typeof OpenAIProvider !== 'undefined') {
                    OpenAIProvider.loadProviders();
                }
            })
            .catch(e => console.error('Failed to load provider info:', e));
    },
```

#### 1.5. Sửa `ApiClient.loadModels()` — dùng endpoint thống nhất

**File:** `webui/static/js/api-client.js`  
**Thay đổi:** Sửa logic chọn URL trong `loadModels()` (dòng 48-52)

**TRƯỚC (dòng 48-52):**
```js
        // Xác định provider đang active
        const activeProvider = document.querySelector('input[name="active_provider"]:checked');
        const provider = activeProvider ? activeProvider.value : 'gemini';

        const url = provider === 'openai' ? '/api/openai/models?full=true' : '/api/models?full=true';
```

**SAU:**
```js
        // Dùng endpoint thống nhất — backend tự detect active provider
        const url = '/api/models?full=true';
```

**Lý do:** Route `GET /api/models` ở `settings.py:22-59` đã có logic `get_active_provider()` để tự detect. Không cần frontend đọc DOM radio.

#### 1.6. Test bước 1

```bash
pytest tests/unit/test_provider_services.py tests/smoke/test_webui_app_factory.py -v
```

**Manual UI:**
1. Mở Config, chuyển Gemini ↔ OpenAI — không còn lỗi JSON.parse
2. Load models hiển thị đúng theo provider active
3. Chọn OpenAI provider cụ thể, lưu cấu hình, load models lại

---

### BƯỚC 2: Thêm nút xóa đã chọn cho tab Biên tập (ước lượng: ~15 phút)

#### 2.1. Tổng quát hóa hàm xóa file

**File:** `webui/static/js/project-manager.js`  
**Thay đổi:** Sửa `deleteSelectedSpellFiles()` (dòng 705-724) thành wrapper + thêm hàm tổng quát

**TRƯỚC (dòng 705-724):**
```js
    async deleteSelectedSpellFiles() {
        const selected = window.selectedFiles;
        if (!selected || selected.size === 0) {
            UiHelpers.showToast('Chưa chọn tập tin nào', 'error');
            return;
        }
        const count = selected.size;
        if (!await showConfirm('Xóa vĩnh viễn ' + count + ' tập tin đã chọn?', { danger: true })) return;
        const slug = window.currentProject.slug;
        const promises = [...selected].map(filename =>
            fetch(`/api/projects/${slug}/file/spelling/${filename}`, {
                method: 'DELETE', headers: { 'Content-Type': 'application/json' }
            }).then(r => r.json())
        );
        Promise.all(promises).then(() => {
            selected.clear();
            ProjectManager.openProject(slug);
            UiHelpers.showToast('Đã xóa ' + count + ' tập tin', 'success');
        });
    },
```

**SAU:**
```js
    async deleteSelectedFiles(section = 'sources') {
        const selected = window.selectedFiles;
        if (!selected || selected.size === 0) {
            UiHelpers.showToast('Chưa chọn tập tin nào', 'error');
            return;
        }
        if (!window.currentProject) {
            UiHelpers.showToast('Chưa chọn dự án', 'error');
            return;
        }
        const count = selected.size;
        if (!await showConfirm(`Xóa vĩnh viễn ${count} tập tin trong ${section}?`, { danger: true })) return;
        const slug = window.currentProject.slug;
        let successCount = 0;
        let failCount = 0;
        const promises = [...selected].map(filename =>
            fetch(`/api/projects/${slug}/file/${section}/${filename}`, {
                method: 'DELETE', headers: { 'Content-Type': 'application/json' }
            })
                .then(r => r.json())
                .then(data => { if (data.success !== false) successCount++; else failCount++; })
                .catch(() => failCount++)
        );
        await Promise.all(promises);
        selected.clear();
        ProjectManager.openProject(slug);
        if (failCount > 0) {
            UiHelpers.showToast(`Đã xóa ${successCount}, lỗi ${failCount} tập tin`, 'error');
        } else {
            UiHelpers.showToast(`Đã xóa ${count} tập tin`, 'success');
        }
    },

    async deleteSelectedSpellFiles() {
        return this.deleteSelectedFiles('spelling');
    },

    async deleteSelectedSourceFiles() {
        return this.deleteSelectedFiles('sources');
    },
```

#### 2.2. Thêm nút xóa vào toolbar tab Biên tập

**File:** `webui/templates/partials/tab_projects.html`  
**Thay đổi:** Thêm nút sau nút "Ghép tập tin" (dòng 97), TRƯỚC `</div>` đóng của `icon-toolbar` (dòng 98)

**TRƯỚC (dòng 97-98):**
```html
                                <button onclick="ProjectManager.mergeTranslatedFiles()" title="Ghép tập tin">...</button>
                            </div>
```

**SAU (thêm 1 dòng giữa):**
```html
                                <button onclick="ProjectManager.mergeTranslatedFiles()" title="Ghép tập tin"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8 6h13"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M3 6h.01"/><path d="M3 12h.01"/><path d="M3 18h.01"/></svg></button>
                                <button onclick="ProjectManager.deleteSelectedSourceFiles()" title="Xóa đã chọn"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg></button>
                            </div>
```

> **Lưu ý:** SVG icon xóa lấy từ nút xóa đã có sẵn trong tab Kiểm chính tả (dòng 175), đảm bảo nhất quán giao diện.

#### 2.3. Test bước 2

**Manual UI:**
1. Vào Dự án > Biên tập
2. Chọn 0 file → bấm xóa → toast "Chưa chọn tập tin nào"
3. Chọn 1+ source file → bấm xóa → confirm → xóa thành công
4. Chuyển tab Kiểm chính tả → xóa vẫn hoạt động bình thường (không hồi quy)
5. File trong `translated/` cùng tên KHÔNG bị xóa

---

### BƯỚC 3: Sửa Generate tab Thông tin (ước lượng: ~45 phút)

#### 3.1. Sửa template tab Thông tin — thêm dropdown source file, dùng 1 model select chung, Generate/Lưu theo subtab active

**File:** `webui/templates/partials/tab_projects.html`  
**Thay đổi:** Thay thế TOÀN BỘ block toolbar tab Thông tin (dòng 248-260)

**TRƯỚC (dòng 248-260):**
```html
                <div class="flex items-center justify-between gap-2 mb3 bb b--black-10 pb2 flex-shrink-0">
                    <div class="flex flex-wrap gap2">
                        <button class="ph3 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white active" onclick="ProjectManager.showPmInfoTab('style-guide')">Hướng dẫn</button>
                        <button class="ph3 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="ProjectManager.showPmInfoTab('relationship')">Mối quan hệ</button>
                        <button class="ph3 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="ProjectManager.showPmInfoTab('glossary')">Thuật ngữ</button>
                        <button class="ph3 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="ProjectManager.showPmInfoTab('summary')">Tóm tắt</button>
                    </div>
                    <div class="flex items-center gap-2">
                        <select id="pm-style-guide-model" class="model-select-sm f7 ba b--black-10 br2 ph2 bg-white outline-0" style="width: 150px;"><option value="">— Chọn Model —</option></select>
                        <button class="pointer ph3 pv1 f7 bn white bg-purple br2 fw6 nowrap" onclick="PromptManager.aiGenerateContent('style_guide')">Generate</button>
                        <button class="pointer ph3 pv1 f7 bn white bg-green br2 fw6" onclick="PromptManager.saveGuidelineField('style_guide')">Lưu</button>
                    </div>
                </div>
```

**SAU:**
```html
                <div class="flex items-center justify-between gap-2 mb3 bb b--black-10 pb2 flex-shrink-0">
                    <div class="flex flex-wrap gap2">
                        <button class="pm-info-tab-btn ph3 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white active" onclick="ProjectManager.showPmInfoTab('style-guide')" data-info-tab="style_guide">Hướng dẫn</button>
                        <button class="pm-info-tab-btn ph3 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="ProjectManager.showPmInfoTab('relationship')" data-info-tab="relationship">Mối quan hệ</button>
                        <button class="pm-info-tab-btn ph3 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="ProjectManager.showPmInfoTab('glossary')" data-info-tab="glossary">Thuật ngữ</button>
                        <button class="pm-info-tab-btn ph3 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="ProjectManager.showPmInfoTab('summary')" data-info-tab="summary">Tóm tắt</button>
                    </div>
                    <div class="flex items-center gap-2">
                        <select id="pm-info-source-file" class="f7 ba b--black-10 br2 ph2 bg-white outline-0" style="width: 140px;">
                            <option value="">— Chọn file nguồn —</option>
                        </select>
                        <select id="pm-info-model" class="model-select-sm f7 ba b--black-10 br2 ph2 bg-white outline-0" style="width: 150px;"><option value="">— Chọn Model —</option></select>
                        <button class="pointer ph3 pv1 f7 bn white bg-purple br2 fw6 nowrap" onclick="PromptManager.aiGenerateFromInfoTab()">Generate</button>
                        <button class="pointer ph3 pv1 f7 bn white bg-green br2 fw6" onclick="PromptManager.saveGuidelineFromInfoTab()">Lưu</button>
                    </div>
                </div>
```

**Thay đổi quan trọng:**
- Mỗi nút subtab có `data-info-tab` attribute để JS biết subtab active
- Thêm `<select id="pm-info-source-file">` — dropdown chọn file nguồn
- Model select đổi id từ `pm-style-guide-model` → `pm-info-model` (chung cho tất cả subtab)
- Generate gọi `PromptManager.aiGenerateFromInfoTab()` thay vì hardcode `style_guide`
- Lưu gọi `PromptManager.saveGuidelineFromInfoTab()` thay vì hardcode

#### 3.2. Cập nhật `showPmInfoTab()` — lưu active tab vào window

**File:** `webui/static/js/project-manager.js`  
**Thay đổi:** Sửa method `showPmInfoTab` (dòng 455-457)

**TRƯỚC:**
```js
    showPmInfoTab(tabName) {
        this._showPanel('pm-info-panel-', ['style-guide', 'relationship', 'glossary', 'summary'], tabName);
    },
```

**SAU:**
```js
    showPmInfoTab(tabName) {
        this._showPanel('pm-info-panel-', ['style-guide', 'relationship', 'glossary', 'summary'], tabName);
        // Map tab UI name → backend content_type
        const tabToContentType = {
            'style-guide': 'style_guide',
            'relationship': 'relationship',
            'glossary': 'glossary',
            'summary': 'summary',
        };
        window.pmActiveInfoTab = tabToContentType[tabName] || 'style_guide';

        // Toggle active class trên các nút subtab
        document.querySelectorAll('.pm-info-tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.infoTab === window.pmActiveInfoTab);
        });

        // Load nội dung từ backend nếu cần
        PromptManager.loadGuidelineTab(tabName);
    },
```

#### 3.3. Populate dropdown source file khi mở project

**File:** `webui/static/js/project-manager.js`  
**Thay đổi:** Thêm code SAU dòng `ProjectManager.renderPmSpellcheckFileList(data.sources || []);` (dòng 296)

**Thêm ngay sau dòng 296:**
```js
            // Populate dropdown source file cho tab Thông tin
            const sourceSelect = document.getElementById('pm-info-source-file');
            if (sourceSelect) {
                sourceSelect.innerHTML = '<option value="">— Chọn file nguồn —</option>';
                (data.sources || []).forEach(f => {
                    const opt = document.createElement('option');
                    opt.value = f.name;
                    opt.textContent = f.name;
                    sourceSelect.appendChild(opt);
                });
            }
```

#### 3.4. Thêm `aiGenerateFromInfoTab()` và `saveGuidelineFromInfoTab()` vào PromptManager

**File:** `webui/static/js/prompt-manager.js`  
**Thay đổi:** Thêm 2 method MỚI vào object `PromptManager` — thêm TRƯỚC dấu `};` cuối file (trước dòng 432)

**Code thêm (chèn trước `};` ở dòng 432):**
```js

    aiGenerateFromInfoTab() {
        if (!window.currentProject) { UiHelpers.showToast('Chưa chọn dự án!', 'error'); return; }
        const fieldKey = window.pmActiveInfoTab || 'style_guide';

        // Lấy source file từ dropdown chung
        const sourceSelect = document.getElementById('pm-info-source-file');
        const sourceFile = sourceSelect ? sourceSelect.value : '';
        if (!sourceFile) {
            UiHelpers.showToast('Vui lòng chọn tập tin nguồn trước khi Generate', 'error');
            return;
        }

        // Lấy model từ dropdown chung
        const modelSel = document.getElementById('pm-info-model');
        const model = modelSel ? modelSel.value : '';

        // Map fieldKey → output element id (prefix pm-guide-)
        const outputElMap = {
            'style_guide': 'pm-guide-style-guide',
            'relationship': 'pm-guide-relationship',
            'glossary': 'pm-guide-glossary',
            'summary': 'pm-guide-summary',
        };
        const outputEl = document.getElementById(outputElMap[fieldKey]);
        if (outputEl) { outputEl.placeholder = '⏳ AI đang tạo nội dung...'; outputEl.disabled = true; }

        fetch(`/api/projects/${window.currentProject.slug}/summarize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model, source_file: sourceFile, content_type: fieldKey })
        })
            .then(async r => {
                const isJson = r.headers.get('content-type')?.includes('application/json');
                const data = isJson ? await r.json() : null;
                if (!r.ok) throw new Error(data?.error || `Lỗi server: ${r.status}`);
                return data;
            })
            .then(data => {
                if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
                const content = data.content || data.summary;
                if (data.success && content) {
                    if (outputEl) outputEl.value = content;
                    const assetFile = data.asset_file || fieldKey + '.txt';
                    UiHelpers.showToast(`Đã tạo và lưu vào assets/${assetFile}`, 'success');
                } else {
                    UiHelpers.showToast(data.error || 'AI không trả về kết quả', 'error');
                }
            })
            .catch(e => {
                if (outputEl) { outputEl.disabled = false; outputEl.placeholder = ''; }
                UiHelpers.showToast('Lỗi: ' + e.message, 'error');
            });
    },

    saveGuidelineFromInfoTab() {
        const fieldKey = window.pmActiveInfoTab || 'style_guide';
        // Map fieldKey → saveGuidelineField key
        const saveKeyMap = {
            'style_guide': 'style_guide',
            'relationship': 'relationship',
            'glossary': 'glossary',
            'summary': 'summary',
        };
        PromptManager.saveGuidelineField(saveKeyMap[fieldKey] || fieldKey);
    },
```

#### 3.5. Populate model select `pm-info-model` trong `loadModels()`

**File:** `webui/static/js/api-client.js`  
**Thay đổi:** Thêm `pm-info-model` vào mảng `contentTabModels` (dòng 117)

**TRƯỚC (dòng 117):**
```js
                const contentTabModels = ['style-guide-model', 'relationship-model', 'glossary-model', 'summary-model', 'pm-style-guide-model'];
```

**SAU:**
```js
                const contentTabModels = ['style-guide-model', 'relationship-model', 'glossary-model', 'summary-model', 'pm-style-guide-model', 'pm-info-model'];
```

#### 3.6. Cập nhật response backend `summarize_project()` — thêm key `content` và `asset_file`

**File:** `webui/routes/projects.py`  
**Thay đổi:** Sửa response thành công (dòng 1212)

**TRƯỚC (dòng 1212):**
```python
            return jsonify({"success": True, "summary": result})
```

**SAU:**
```python
            return jsonify({
                "success": True,
                "summary": result,  # backward compat
                "content": result,
                "content_type": content_type,
                "asset_file": asset_filename,
                "source_file": source_file,
            })
```

#### 3.7. Test bước 3

**Manual UI:**
1. Vào Dự án > Thông tin
2. Kiểm tra dropdown "Chọn file nguồn" có hiển thị danh sách files trong `sources/`
3. Bấm Generate mà chưa chọn file → toast "Vui lòng chọn tập tin nguồn"
4. Chọn file + model, bấm Generate → nội dung hiển thị trong textarea
5. Chuyển subtab (Hướng dẫn → Mối quan hệ → Thuật ngữ → Tóm tắt) → Generate ghi vào đúng textarea
6. Kiểm tra `assets/*.txt` được cập nhật
7. Toast hiển thị "Đã tạo và lưu vào assets/style_guide.txt"

---

### BƯỚC 4: Chuẩn hóa project context trong prompt dịch (ước lượng: ~30 phút)

> **CHÚ Ý:** Bước này có phạm vi TRUNG BÌNH. Chỉ tạo service mới và sửa integration point trong `translate_project_file()`. KHÔNG sửa `robust_translate()` hay `GlossaryService` — chúng vẫn hoạt động như cũ.

#### 4.1. Tạo `ProjectContextService`

**File MỚI:** `backend/infrastructure/config/project_context_service.py`

```python
"""Service đọc và render project context (assets) vào prompt dịch."""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ProjectContextService:
    """Đọc file assets và chèn vào prompt dịch."""

    ASSET_FILES = {
        "translation_guidelines": "style_guide.txt",
        "project_summary": "summary.txt",
    }
    # glossary.txt và relationship.txt được xử lý riêng bởi GlossaryService

    PLACEHOLDER_MAP = {
        "{translation_guidelines}": "translation_guidelines",
        "{project_summary}": "project_summary",
        "{project_context}": "__all__",
    }

    def load_context(self, project_dir: Path) -> Dict[str, str]:
        """Đọc tất cả asset files, trả dict key→content.
        Bỏ qua file rỗng hoặc chỉ có comment template (bắt đầu bằng #).
        """
        assets_dir = project_dir / "assets"
        context = {}
        for key, filename in self.ASSET_FILES.items():
            fp = assets_dir / filename
            if not fp.exists():
                continue
            content = fp.read_text(encoding="utf-8").strip()
            if not content or content.startswith("#"):
                continue
            context[key] = content
        return context

    def render_prompt(self, main_prompt: str, context: Dict[str, str]) -> str:
        """Chèn context vào prompt.

        Quy tắc:
        - Nếu prompt có placeholder → replace placeholder
        - Nếu prompt KHÔNG có placeholder → append context cuối prompt
        - {project_context} → chèn tất cả context gộp lại
        """
        if not context:
            return main_prompt

        has_placeholder = False

        for placeholder, context_key in self.PLACEHOLDER_MAP.items():
            if placeholder in main_prompt:
                has_placeholder = True
                if context_key == "__all__":
                    all_content = self._build_all_context(context)
                    main_prompt = main_prompt.replace(placeholder, all_content)
                else:
                    main_prompt = main_prompt.replace(
                        placeholder, context.get(context_key, "")
                    )

        # Fallback: append nếu không có placeholder
        if not has_placeholder:
            append_block = self._build_all_context(context)
            if append_block:
                main_prompt += "\n\n" + append_block

        return main_prompt

    def _build_all_context(self, context: Dict[str, str]) -> str:
        """Gộp tất cả context thành 1 block text."""
        parts = []
        if "translation_guidelines" in context:
            parts.append(f"# Hướng dẫn phong cách\n{context['translation_guidelines']}")
        if "project_summary" in context:
            parts.append(f"# Tóm tắt dự án\n{context['project_summary']}")
        return "\n\n".join(parts)
```

#### 4.2. Dùng `ProjectContextService` trong `translate_project_file()`

**File:** `webui/routes/projects.py`  
**Thay đổi:** Thay thế block đọc `style_guide.txt` thủ công (dòng 1253-1262)

**TRƯỚC (dòng 1250-1262):**
```python
    prompt_service = PromptService()
    prompts = prompt_service.load_merged_prompts(pdir)

    # Load assets context
    assets_context = ""
    for pfile in ["style_guide.txt"]:
        fp = pdir / "assets" / pfile
        if fp.exists():
            content = fp.read_text(encoding="utf-8").strip()
            if content and not content.startswith("#"):
                assets_context += f"\n\n# Hướng dẫn phong cách\n{content}"
    if assets_context.strip():
        prompts["main"] += assets_context
```

**SAU:**
```python
    prompt_service = PromptService()
    prompts = prompt_service.load_merged_prompts(pdir)

    # Load project context (style_guide, summary) và chèn vào prompt
    from backend.infrastructure.config.project_context_service import ProjectContextService
    context_service = ProjectContextService()
    project_context = context_service.load_context(pdir)
    if project_context:
        prompts["main"] = context_service.render_prompt(prompts["main"], project_context)
```

#### 4.3. Thêm unit test cho `ProjectContextService`

**File MỚI:** `tests/unit/test_project_context_service.py`

```python
"""Unit tests cho ProjectContextService."""

import pytest
from pathlib import Path
from backend.infrastructure.config.project_context_service import ProjectContextService


@pytest.fixture
def tmp_project(tmp_path):
    """Tạo project dir tạm."""
    assets = tmp_path / "assets"
    assets.mkdir()
    return tmp_path


@pytest.fixture
def service():
    return ProjectContextService()


class TestLoadContext:
    def test_empty_assets(self, service, tmp_project):
        ctx = service.load_context(tmp_project)
        assert ctx == {}

    def test_reads_style_guide(self, service, tmp_project):
        (tmp_project / "assets" / "style_guide.txt").write_text("Dùng tone trang trọng")
        ctx = service.load_context(tmp_project)
        assert ctx["translation_guidelines"] == "Dùng tone trang trọng"

    def test_reads_summary(self, service, tmp_project):
        (tmp_project / "assets" / "summary.txt").write_text("Câu chuyện về...")
        ctx = service.load_context(tmp_project)
        assert ctx["project_summary"] == "Câu chuyện về..."

    def test_skips_empty_file(self, service, tmp_project):
        (tmp_project / "assets" / "style_guide.txt").write_text("   ")
        ctx = service.load_context(tmp_project)
        assert "translation_guidelines" not in ctx

    def test_skips_comment_template(self, service, tmp_project):
        (tmp_project / "assets" / "style_guide.txt").write_text("# Template comment only")
        ctx = service.load_context(tmp_project)
        assert "translation_guidelines" not in ctx


class TestRenderPrompt:
    def test_no_context(self, service):
        prompt = "Dịch văn bản sau:"
        result = service.render_prompt(prompt, {})
        assert result == prompt

    def test_placeholder_replaced(self, service):
        prompt = "Hướng dẫn: {translation_guidelines}\n\nDịch:"
        ctx = {"translation_guidelines": "Dùng tone nhẹ nhàng"}
        result = service.render_prompt(prompt, ctx)
        assert "Dùng tone nhẹ nhàng" in result
        assert "{translation_guidelines}" not in result

    def test_project_context_placeholder(self, service):
        prompt = "Context: {project_context}\n\nDịch:"
        ctx = {"translation_guidelines": "Tone X", "project_summary": "Summary Y"}
        result = service.render_prompt(prompt, ctx)
        assert "Tone X" in result
        assert "Summary Y" in result
        assert "{project_context}" not in result

    def test_fallback_append(self, service):
        prompt = "Dịch văn bản sau:"
        ctx = {"translation_guidelines": "Tone trang trọng"}
        result = service.render_prompt(prompt, ctx)
        assert result.startswith("Dịch văn bản sau:")
        assert "Tone trang trọng" in result
        assert "# Hướng dẫn phong cách" in result
```

#### 4.4. Test bước 4

```bash
pytest tests/unit/test_project_context_service.py -v
pytest tests/unit/test_provider_services.py tests/smoke/test_webui_app_factory.py -v
```

**Manual test dịch:**
1. Tạo file `assets/style_guide.txt` với nội dung "Dùng tone trang trọng"
2. Dịch 1 file — kiểm tra log prompt có "# Hướng dẫn phong cách" + "Dùng tone trang trọng"
3. Xóa nội dung `assets/style_guide.txt` — dịch lại — prompt KHÔNG có block hướng dẫn
4. Nếu prompt dịch có `{translation_guidelines}` → placeholder được thay
5. Nếu prompt dịch KHÔNG có placeholder → context append cuối

---

## 4. Kiểm thử tổng hợp cuối cùng

### 4.1. Automated tests

```bash
pytest tests/ -v --tb=short 2>&1 | head -80
```

### 4.2. Manual UI Checklist

| # | Thao tác | Kết quả mong đợi |
|---|---------|-----------------|
| 1 | Config → chuyển Gemini ↔ OpenAI ↔ Gemini | Không lỗi JSON.parse, toast thành công |
| 2 | Config → chọn OpenAI provider cụ thể → Lưu → Load models | Models hiển thị đúng |
| 3 | Dự án > Biên tập → chọn nhiều source file → bấm xóa | Files bị xóa, translated giữ nguyên |
| 4 | Dự án > Thông tin → chọn file nguồn + model → Generate từng tab | Textarea có nội dung, toast có tên asset file |
| 5 | Kiểm tra `assets/*.txt` | File được tạo/cập nhật đúng |
| 6 | Dịch 1 file có `style_guide.txt` | Log prompt có guideline |
| 7 | Dịch 1 file có glossary terms trong chunk | Log có "Nhúng X thuật ngữ glossary" |

### 4.3. Trước khi commit

```bash
gitnexus_detect_changes(scope="all")
```

Xác nhận thay đổi chỉ nằm trong:
- Provider config/select/model loading
- Project info generate
- Project file list delete
- Translation prompt/project context

---

## 5. Rủi ro và giảm thiểu

| Rủi ro | Mức độ | Giảm thiểu |
|--------|--------|-----------|
| ProviderService là hub MEDIUM impact | Trung bình | Ưu tiên sửa frontend + shim, hạn chế đổi data schema |
| Inline HTML/Alpine caller không được GitNexus bắt hết | Trung bình | Manual UI test bắt buộc (checklist ở mục 4.2) |
| Xóa nhầm translated khi xóa source | Cao | Code chỉ xóa section truyền vào, mặc định `sources` |
| `pm-style-guide-model` cũ không còn được populate | Thấp | Thêm `pm-info-model` vào mảng, giữ `pm-style-guide-model` trong mảng cũ nếu cần backward compat |
| Prompt context quá dài | Trung bình | Chỉ chèn `style_guide` + `summary`, glossary vẫn dynamic injection |
| Backward compat `/api/provider` | Thấp | Shim deprecated hoạt động song song |

---

## 6. Tóm tắt file cần thay đổi

| File | Thao tác | Bước |
|------|---------|------|
| `webui/routes/settings.py` | Thêm shim `/api/provider` | 1.1 |
| `webui/static/js/api-client.js` | Sửa `fetchJson`, sửa `loadModels`, thêm `pm-info-model` | 1.2, 1.5, 3.5 |
| `webui/static/js/ui-helpers.js` | Sửa `switchProvider`, `initProvider` | 1.3, 1.4 |
| `webui/static/js/project-manager.js` | Thêm `deleteSelectedFiles`, `deleteSelectedSourceFiles`, sửa `showPmInfoTab`, populate source select | 2.1, 3.2, 3.3 |
| `webui/templates/partials/tab_projects.html` | Thêm nút xóa tab Biên tập, sửa toolbar tab Thông tin | 2.2, 3.1 |
| `webui/static/js/prompt-manager.js` | Thêm `aiGenerateFromInfoTab`, `saveGuidelineFromInfoTab` | 3.4 |
| `webui/routes/projects.py` | Sửa response `summarize_project`, sửa assets context loading | 3.6, 4.2 |
| `backend/infrastructure/config/project_context_service.py` | **[MỚI]** ProjectContextService | 4.1 |
| `tests/unit/test_project_context_service.py` | **[MỚI]** Unit tests | 4.3 |
