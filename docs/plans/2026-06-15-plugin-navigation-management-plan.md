# Kế hoạch: Plugin Management & Project Workspace Integration

Ngày lập: 2026-06-15 · Cập nhật: 2026-06-15T22:10

## 1. Mục tiêu

Xóa bỏ thẻ **Công cụ** trên main navigation. Chuyển chức năng quản lý plugin thành một **khối riêng nằm dưới cùng** trong tab **Cấu hình**. Khi tool plugin được kích hoạt, plugin trở thành tính năng bổ sung cho **mọi dự án**, xuất hiện trong navigation panel của workspace dự án giống các tính năng gốc như dịch và kiểm chính tả.

Trang quản lý plugin cho phép:

- Xem danh sách tất cả plugins (bao gồm cả core features) với: tên, mô tả, phiên bản, người tạo.
- Bật/tắt từng plugin (core plugins mặc định bật, không tắt được).
- Truy cập settings của plugin nếu plugin có cấu hình riêng.
- Khi tool plugin được bật, tự động hiển thị thẻ thao tác plugin trong workspace project đang mở.

### Phân loại plugin

| Loại | Plugin | Hiển thị trong quản lý | Mặc định | Tắt được? | Workspace tab |
|------|--------|----------------------|----------|-----------|---------------|
| Core | Translation | ✅ | Bật | ❌ | Có sẵn trong `Biên tập` |
| Core | Spellcheck | ✅ | Bật | ❌ | Có sẵn trong `Biên tập` |
| Tool | eBook Kit (ex EPUB Converter) | ✅ | Bật | ✅ | ✅ `ebook-kit` |
| Tool | OCR Toolbox (ex OCR Reader) | ✅ | Bật | ✅ | ✅ `ocr-toolbox` |

Khi người dùng mở một dự án và các tool plugin được kích hoạt, workspace project navigation hiển thị:

1. **Biên tập**
2. **Thông tin**
3. **Chỉ dẫn**
4. **eBook Kit** ← chỉ khi enabled
5. **OCR Toolbox** ← chỉ khi enabled

Các plugin này thao tác với **dự án đang mở**: đường dẫn mặc định, danh sách tập tin, API payload, output và settings runtime đều lấy theo project hiện hành.

## 2. Hiện trạng đã ghi nhận

Các điểm liên quan hiện có:

- `webui/templates/partials/header.html`
  - Main navigation đang hard-code 6 thẻ: `Dự án`, `Cấu hình`, `Chỉ dẫn AI`, `Công cụ`, `Nhật ký`, `Lưu trữ`.
  - Thẻ `Công cụ` đang dùng `data-tab="plugins"`.
- `webui/templates/partials/tab_projects.html`
  - Workspace dự án hiện có sub-tabs: `Biên tập`, `Thông tin`, `Chỉ dẫn`.
  - Đây là vị trí tích hợp eBook Kit và OCR Toolbox khi plugin được bật.
- `webui/templates/partials/tab_plugins.html`
  - Đang chứa trực tiếp cả UI `EPUB Converter` và `OCR Reader`.
  - EPUB đang dùng dropdown `Hướng chuyển đổi` để ẩn/hiện form `EPUB -> Text` và `Text -> EPUB`, gây lẫn chức năng.
- `webui/templates/partials/tab_config.html`
  - Hiện có: Provider cards (Gemini/OpenAI), Model Selection, System Config, Advanced Config.
  - Plugin management section sẽ được thêm **dưới cùng** của tab này.
- `webui/routes/plugins.py`
  - Có API chạy EPUB: `POST /api/plugins/epub-converter`.
  - Có API chạy OCR: `POST /api/plugins/ocr`.
  - Có polling progress: `GET /api/plugins/progress/<plugin_id>`.
  - Có list tĩnh: `GET /api/plugins/list`, nhưng chưa có trạng thái bật/tắt, tác giả, settings, hoặc metadata đầy đủ.
- `webui/static/js/ui-helpers.js`
  - Có các hàm `toggleEpubForm`, `runEpubConverter`, `runOcr`, `pollPluginProgress`.
- `webui/static/js/main.js`
  - `initTabs()` bind listener trên `.nav-link[data-tab]` lúc `DOMContentLoaded`.
- `webui/static/js/project-manager.js`
  - `openProject()` đặt `window.currentProject` và render workspace.
  - Workspace sub-tabs hiện dùng Alpine state `wsTab`.
  - `switchPmFileTab()` đang điều khiển các vùng dịch/soát lỗi trong tab `Biên tập`.
- `core/interfaces/` — **directory rỗng** (chỉ có `__pycache__`, không có `.py`). Cả `epub_converter/plugin.py` và `ocr/plugin.py` import `from core.interfaces import ConverterPlugin` → sẽ fail nếu load class.
- Plugin source hiện có:
  - `plugins/epub_converter/plugin.py`: version `3.0.0`, display name `EPUB Converter`.
  - `plugins/ocr/plugin.py`: version `3.0.3`, display name `OCR Reader`.
  - `plugins/spellcheck/spellchecker.py`: core spellcheck, không có plugin.py class.
  - `plugins/translation/`: core translation, có chunker, translator, normalizer.
- `plugins/__init__.py` docstring còn nhắc `consistency_check` và `content_analysis` — không tồn tại trên disk, cần dọn.

## 3. Quyết định thiết kế đã chốt

### 3.1. `core.interfaces` — Tạo lại interface base classes

**Bối cảnh**: `core/interfaces/` hiện là directory rỗng. Cả `epub_converter/plugin.py` và `ocr/plugin.py` đều `from core.interfaces import ConverterPlugin` nhưng import sẽ fail vì file không tồn tại. Route hiện tại gọi trực tiếp implementation (`epub2text.convert_epub`, `ocr_engine.ocr_file`) nên chưa bị lỗi runtime.

**Quyết định**: Tạo lại `core/interfaces/__init__.py` với base classes (`PluginBase`, `ConverterPlugin`). Lý do:

- **Tối ưu cho phát triển plugin độc lập**: Interface base class là contract mà plugin authors code against. Không có nó, mỗi plugin tự quyết structure → không có chuẩn, không validate được lifecycle.
- **Registry có thể introspect plugin**: Load class → đọc `name`, `version`, `display_name`, `get_capabilities()` tự động thay vì hard-code metadata.
- **Extensibility**: Third-party plugins trong tương lai chỉ cần implement `PluginBase` → registry tự discover.

Scope trong plan này: tạo lại interface cơ bản đủ để plugins import không fail. Không refactor route logic sang plugin class (giữ nguyên direct calls).

### 3.2. `plugin_progress` dict — Giữ lại, thêm TTL cleanup nhẹ

**`plugin_progress` là gì**: Global dict trong `plugins.py` lưu trạng thái chạy từng plugin execution dài hơi:

```python
plugin_progress = {}  # plugin_id -> {status, messages[], result}
```

Mỗi lần gọi API chạy plugin, hệ thống:
1. Tạo `plugin_id` ngẫu nhiên (UUID 8 ký tự)
2. Plugin chạy trong background `Thread`
3. Frontend poll `GET /api/plugins/progress/<plugin_id>` mỗi 1 giây để lấy messages/status
4. Khi status = `done` hoặc `error`, frontend dừng poll

**Mục đích**: Cho UI biết plugin đang chạy đến đâu mà không khóa request HTTP. EPUB/OCR có thể chạy lâu; nếu không có `plugin_progress`, frontend chỉ có thể chờ response đồng bộ, dễ timeout và không có log tiến trình.

**Vấn đề**: Memory leak — entries không bao giờ bị xóa. Mỗi lần chạy plugin thêm 1 entry chứa toàn bộ log messages.

**Giải pháp trong plan này**: Thêm metadata thời gian (`created_at`, `updated_at`) và cleanup nhẹ trong cùng module route: trước khi tạo/poll progress thì xóa entries đã kết thúc quá 30 phút. Việc này không đổi tính năng, chỉ tránh việc log cũ nằm mãi trong RAM sau nhiều lần chạy.

### 3.3. Scope bật/tắt plugin — Tắt hẳn API

**Quyết định**: Khi plugin bị tắt, API execution trả `403 Forbidden` với message rõ ràng.

Lý do chọn tắt API thay vì chỉ ẩn UI:

- **Nhất quán**: Trạng thái UI ↔ API đồng bộ. Không có tình huống plugin bị tắt nhưng vẫn gọi được qua curl/script.
- **Chi phí thấp**: Chỉ cần 1 decorator/guard check `enabled` state trước khi chạy plugin logic. Centralized, không cần sửa từng route riêng lẻ.
- **Không ảnh hưởng gì**: Nếu để API mà không gọi, không gây lỗi nhưng tạo surface attack không cần thiết. Tắt hẳn sạch hơn.

Implementation: Tạo decorator `@require_plugin_enabled("plugin_id")` dùng chung cho tất cả plugin routes.

### 3.4. Project workspace navigation động

**Vị trí tích hợp**: eBook Kit và OCR Toolbox không nằm trên main navigation. Khi người dùng mở một dự án, hai plugin này xuất hiện trong project workspace sub-tabs, cùng hàng với `Biên tập`, `Thông tin`, `Chỉ dẫn`.

**Plugin state cache (frontend)**: Plugin state ít thay đổi, nên load 1 lần lúc `DOMContentLoaded` qua `GET /api/plugins/list` và cache vào `window.pluginState`. Invalidate cache chỉ khi user toggle plugin trong Cấu hình. `ProjectManager.openProject()` đọc từ cache thay vì gọi API mỗi lần mở project → giảm latency.

**PluginManager frontend contract**:
- Tạo namespace frontend nhẹ, ví dụ `window.PluginManager`, để quản lý plugin state thay vì rải logic trong nhiều file.
- `PluginManager.ensureLoaded()`:
  - Nếu `window.pluginState` đã có dữ liệu hợp lệ thì trả ngay.
  - Nếu đang có request load plugin state thì trả lại cùng Promise, tránh gọi trùng API.
  - Nếu chưa có dữ liệu thì gọi `GET /api/plugins/list`, cache vào `window.pluginState`, rồi resolve.
  - Nếu load lỗi, set `window.pluginState = { plugins: [], loaded: false, error }`, hiển thị toast lỗi nhẹ, và render workspace không có tool plugin tabs thay vì làm hỏng màn hình dự án.
- `ProjectManager.openProject(slug)` phải `await PluginManager.ensureLoaded()` trước khi render workspace plugin tabs; nếu project đã render trước khi plugin state load xong, `PluginManager.ensureLoaded()` phải trigger render lại workspace tabs sau khi resolve.
- Khi toggle plugin trong `Cấu hình`, cập nhật server trước; nếu thành công thì update `window.pluginState`, gọi `PluginManager.renderWorkspaceTabs()` nếu đang có `window.currentProject`.

**Cơ chế hiển thị**:
- `window.pluginState` là source of truth phía frontend cho trạng thái `enabled`.
- Khi `ProjectManager.openProject()` tải dữ liệu dự án, đọc `window.pluginState` để render/ẩn workspace tabs.
- Khi user bật/tắt plugin ở `Cấu hình`, cập nhật `window.pluginState`, đồng thời render lại workspace plugin tabs nếu có `window.currentProject`.
- Nếu plugin bị tắt khi user đang đứng trong tab plugin, workspace quay về `Biên tập`.

**Toolbar column toggles**: Toolbar `#pm-workspace-column-toggles` (nút ẩn/hiện cột file, nguồn, bản dịch) chỉ hiển thị khi `$store.workspace.wsTab === 'editor'`. Khi workspace tab là plugin tab, toolbar ẩn vì plugin panels dùng layout full-width riêng, không liên quan đến hệ thống cột editor.

### 3.5. Plugin panels — Layout full-width độc lập

Plugin workspace panels (eBook Kit, OCR Toolbox) sử dụng **layout full-width riêng**, hoàn toàn tách biệt khỏi hệ thống 3 cột (file sidebar + source editor + result editor) của tab `Biên tập`:

- Trong `tab_projects.html`, plugin panels phải là sibling cùng cấp với các panel hiện có:
  - panel `editor`
  - panel `info`
  - panel `prompt`
  - panel `ebook-kit`
  - panel `ocr-toolbox`
- Không thao tác trực tiếp để ẩn/hiện `.workspace-layout-3col`. Vì `.workspace-layout-3col` đã nằm bên trong panel `editor`, chỉ cần điều khiển panel cấp cao bằng `$store.workspace.wsTab`.
- Khi `$store.workspace.wsTab === 'ebook-kit'` hoặc `'ocr-toolbox'`, panel plugin full-width hiển thị, còn panel `editor` tự ẩn.
- Plugin panel tự quản lý layout nội bộ (form inputs, log, progress) mà không phụ thuộc vào sidebar hay editor columns.
- CSS cần xử lý: panel plugin dùng `flex-auto` chiếm toàn bộ không gian workspace, tương tự panel `info` và `prompt` hiện tại.

Template shape đề xuất:

```html
<div x-show="$store.workspace.wsTab === 'editor'" class="flex-auto flex flex-column overflow-hidden">
    <!-- workspace-layout-3col hiện có -->
</div>
<div x-show="$store.workspace.wsTab === 'info'" class="flex-auto flex flex-column overflow-hidden pa3">
    <!-- panel Thông tin hiện có -->
</div>
<div x-show="$store.workspace.wsTab === 'prompt'" class="flex-auto flex flex-column overflow-hidden pa3">
    <!-- panel Chỉ dẫn hiện có -->
</div>
{% include 'partials/workspace_ebook_kit.html' %}
{% include 'partials/workspace_ocr_toolbox.html' %}
```

Trong hai partial plugin, root panel dùng `x-show="$store.workspace.wsTab === 'ebook-kit'"` hoặc `ocr-toolbox`.

### 3.6. Workspace state — Guard check cho tab đã tắt

Workspace hiện dùng Alpine state `wsTab`. Khi thêm plugin tabs động, cần tránh trạng thái `wsTab = "ebook-kit"` hoặc `"ocr-toolbox"` còn tồn tại sau khi plugin bị tắt.

Giải pháp:
- Chuyển workspace tab state từ local `x-data="{ wsTab: 'editor' }"` sang `Alpine.store('workspace', { wsTab: 'editor' })` hoặc một store tương đương được init trước khi workspace render.
- Template dùng `$store.workspace.wsTab` thay cho biến local `wsTab` để JS ngoài component có thể điều khiển workspace tab một cách ổn định.
- Khi plugin disabled hoặc project context không hợp lệ, gọi helper `PluginManager.setWorkspaceTab('editor')` hoặc set trực tiếp `$store.workspace.wsTab = 'editor'`.
- Không dùng `display:none` cho tab button plugin nếu plugin disabled; remove/không render button.
- Nếu active workspace tab trỏ tới plugin disabled, tự chuyển về `editor`.
- Không lưu plugin workspace tab như state toàn cục; nếu có persist thì persist theo project slug và validate lại với plugin state trước khi restore.

### 3.7. eBook Kit subtab — Dùng CSS-radio pattern

Hiện tại workspace đã có CSS-radio subtab pattern (`.nt-tab-radio`). eBook Kit sẽ dùng lại pattern này cho 2 subtab: `EPUB → Text` và `Text → EPUB`. Không tạo tab system mới.

### 3.8. Config persistence — Dual system

- `config/plugins.json` → lưu `enabled` state cho tất cả plugins (registry/UI state). JSON vì dữ liệu là danh sách đơn giản.
- `config/plugins/*.ini` → lưu plugin-specific settings (đã có pattern trong `ConfigService.get_plugin_config()`). Giữ nguyên.
- Hai hệ thống không conflict: `plugins.json` chỉ quản lý `enabled`, `*.ini` chỉ quản lý settings nội bộ.

## 4. Nguyên tắc sinh mã & sửa mã

- Tham khảo cấu trúc dự án đã tạo bởi GitNexus để sinh mã mới, tận dụng tối đa mã có sẵn.
- Chỉ viết mới khi được xác nhận hoặc nêu trong kế hoạch.
- **Không sinh mã inline:** sử dụng classless/SUDS và hệ thống template của dự án.
- **Chỉnh sửa tối giản:** mỗi giai đoạn chỉ chỉnh sửa đúng dòng cần thiết bằng `replace_file_content`. Không dùng `write_to_file` trên file đã có.
- **Kiểm tra sau thay đổi:** sau mỗi giai đoạn phải kiểm tra hệ thống còn hoạt động.
- **Kiểm soát phiên bản:** không tự động commit, không tự động tạo changelog trừ khi có yêu cầu cụ thể.
- Trước khi sửa function/class/method, bắt buộc chạy GitNexus impact analysis theo `AGENTS.md`; nếu HIGH/CRITICAL thì báo trước khi sửa.
- Trước khi commit nếu sau này có yêu cầu commit, bắt buộc chạy `gitnexus_detect_changes()`.

## 5. Thiết kế đích

### 5.1. Plugin Management (trong tab Cấu hình)

Khối mới nằm dưới cùng `tab_config.html`, sau Advanced Config:

- Bảng/list plugin gồm:
  - Icon + Tên hiển thị.
  - Mô tả.
  - Phiên bản.
  - Người tạo.
  - Badge "Core" cho core plugins.
  - Trạng thái bật/tắt (toggle switch, disabled cho core plugins).
  - Nút `Settings` nếu plugin khai báo có settings.
- Toggle bật/tắt plugin lưu trạng thái bền vững vào `config/plugins.json`.
- Khi bật tool plugin, workspace của mọi dự án thêm thẻ plugin tương ứng (realtime nếu đang mở dự án).
- Khi tắt tool plugin, thẻ plugin biến mất khỏi workspace project + API execution trả 403.

### 5.2. Workspace tab eBook Kit

Tách khỏi plugin list, trở thành sub-tab full-width trong workspace dự án:

- Workspace tab label: **eBook Kit**.
- `wsTab`: `ebook-kit`.
- Panel full-width nằm trong `#projects-workspace-view`, cùng cấp với panel `info`, `prompt`. Khi active, ẩn `.workspace-layout-3col` và hiển thị panel plugin thay thế.
- Chia thành 2 subtab dùng CSS-radio pattern (`.nt-tab-radio`):
  - **EPUB → Text**
  - **Text → EPUB**
- Không dùng dropdown `Hướng chuyển đổi` nữa.
- Mỗi subtab chỉ hiển thị input/option thuộc đúng hướng chuyển đổi.
- Nút chạy ghi rõ hướng:
  - `Chạy EPUB → Text`
  - `Chạy Text → EPUB`
- API chạy theo project hiện hành: `POST /api/projects/<slug>/plugins/epub-converter`, payload đặt `direction` theo subtab hiện hành.
- Backend lấy default paths theo `<slug>` nếu payload không truyền path tùy chỉnh.

### 5.3. Workspace tab OCR Toolbox

Tách khỏi plugin list, trở thành sub-tab full-width trong workspace dự án:

- Workspace tab label: **OCR Toolbox**.
- `wsTab`: `ocr-toolbox`.
- Panel full-width nằm trong `#projects-workspace-view`, cùng cấp với panel `info`, `prompt`. Khi active, ẩn `.workspace-layout-3col` và hiển thị panel plugin thay thế.
- Dùng lại form OCR hiện tại, đổi nhãn từ `OCR Reader` sang `OCR Toolbox`.
- API chạy theo project hiện hành: `POST /api/projects/<slug>/plugins/ocr`.
- Backend lấy default output theo `<slug>` nếu payload không truyền path tùy chỉnh.

### 5.4. Dự án đang thao tác

Các plugin thao tác với tập tin nằm trong **dự án đang được chọn** (`window.currentProject.slug` trên frontend, `slug` project trên backend). Không dùng slug cố định `default-project` cho workflow plugin.

- Dùng `WorkspaceService` / `ProjectService` hiện có thay vì hard-code path mới.
- Vì plugin tab nằm trong workspace dự án, điều kiện mặc định là đã có `window.currentProject`; nếu state bị mất, UI phải quay về danh sách dự án hoặc yêu cầu mở dự án trước.
- Đường dẫn mặc định theo project đang thao tác:
  - EPUB -> Text output: `workspace/projects/<slug>/output`; người dùng có thể sửa đường dẫn khi chạy.
  - Text -> EPUB input: `workspace/projects/<slug>/translated`; người dùng có thể sửa đường dẫn khi chạy.
  - Text -> EPUB output: `workspace/projects/<slug>/output`; người dùng có thể sửa đường dẫn khi chạy.
  - OCR output: `workspace/projects/<slug>/output`; người dùng có thể sửa đường dẫn khi chạy.
- Các input/output path do người dùng nhập phải được validate rõ ràng; nếu cho phép path ngoài project thì UI cần thể hiện đây là thao tác có chủ ý.
- Sau khi plugin tạo/sửa file trong project, gọi lại `ProjectManager.openProject(slug)` hoặc endpoint refresh tương đương để danh sách file và thống kê dự án cập nhật.

## 6. Dữ liệu plugin đề xuất

Tạo một nguồn metadata tập trung cho plugin, ví dụ trong backend:

```json
[
  {
    "id": "translation",
    "name": "Translation",
    "description": "Dịch thuật văn bản sử dụng AI (Gemini/OpenAI).",
    "version": "3.0.0",
    "author": "Novel Translator",
    "enabled": true,
    "is_core": true,
    "has_settings": false,
    "workspace_tab": null
  },
  {
    "id": "spellcheck",
    "name": "Spell Check",
    "description": "Kiểm tra chính tả và sửa lỗi bản dịch bằng AI.",
    "version": "3.0.0",
    "author": "Novel Translator",
    "enabled": true,
    "is_core": true,
    "has_settings": false,
    "workspace_tab": null
  },
  {
    "id": "epub_converter",
    "workspace_tab": "ebook-kit",
    "name": "eBook Kit",
    "legacy_name": "EPUB Converter",
    "description": "Chuyển đổi EPUB sang Text/Markdown và đóng gói Text/Markdown thành EPUB.",
    "version": "3.0.0",
    "author": "Novel Translator",
    "enabled": true,
    "is_core": false,
    "has_settings": false
  },
  {
    "id": "ocr",
    "workspace_tab": "ocr-toolbox",
    "name": "OCR Toolbox",
    "legacy_name": "OCR Reader",
    "description": "Nhận dạng ký tự từ PDF/ảnh, hỗ trợ cleanup và spell check bằng AI.",
    "version": "3.0.3",
    "author": "Novel Translator",
    "enabled": true,
    "is_core": false,
    "has_settings": true
  }
]
```

Persistence:

- `config/plugins.json` → lưu `{ "plugin_id": { "enabled": true } }` cho mỗi plugin.
- `config/plugins/*.ini` → lưu plugin-specific settings (giữ nguyên pattern `ConfigService.get_plugin_config()`).

## 7. API cần có

Giữ các API chạy plugin hiện tại, bổ sung API quản lý:

- `GET /api/plugins/list`
  - Trả metadata đầy đủ: `id`, `name`, `description`, `version`, `author`, `enabled`, `is_core`, `has_settings`, `workspace_tab`.
- `PATCH /api/plugins/<plugin_id>`
  - Body: `{ "enabled": true|false }`.
  - Từ chối nếu `is_core = true` (core plugins không tắt được).
  - Lưu trạng thái vào `config/plugins.json`.
  - Trả lại metadata plugin sau cập nhật.
- `GET /api/plugins/<plugin_id>/settings`
  - Chỉ dùng khi `has_settings = true`.
  - Trả schema/settings hiện có.
- `PUT /api/plugins/<plugin_id>/settings`
  - Lưu settings nếu plugin hỗ trợ.

Plugin execution APIs (đổi sang project-scoped routes):

- `POST /api/projects/<slug>/plugins/epub-converter` — thêm `@require_plugin_enabled("epub_converter")`, validate project slug, dùng paths mặc định theo project.
- `POST /api/projects/<slug>/plugins/ocr` — thêm `@require_plugin_enabled("ocr")`, validate project slug, dùng output mặc định theo project.
- `GET /api/plugins/progress/<plugin_id>` — giữ nguyên để frontend poll tiến trình theo `plugin_id`.
- Khi plugin bị tắt → trả `403 {"error": "Plugin 'eBook Kit' đã bị tắt"}`.

> **Ghi chú route cũ**: Routes cũ (`POST /api/plugins/epub-converter`, `POST /api/plugins/ocr`) không cần backward compatibility. Sau khi frontend/tests/docs đã chuyển sang route project-scoped, xóa route cũ khỏi `webui/routes/plugins.py` thay vì giữ shim. Kết quả mong muốn sau xóa: caller cũ nhận 404 mặc định của Flask; không cần tạo response 410 riêng. Trước khi xóa, phải rà soát toàn bộ codebase (JS, tests, scripts, docs) để xác nhận không còn nơi nào gọi route cũ.

Có thể trì hoãn settings chi tiết ở phase sau nếu chưa có schema plugin settings ổn định; UI chỉ cần disable/hide nút settings khi chưa hỗ trợ.

## 8. Các giai đoạn triển khai

### Phase 1: core.interfaces + Plugin registry + API quản lý

Mục tiêu:

- Tạo lại `core/interfaces/__init__.py` với `PluginBase`, `ConverterPlugin` base classes.
- Chuẩn hóa metadata cho tất cả 4 plugins (translation, spellcheck, epub_converter, ocr).
- Đổi label hiển thị: `EPUB Converter` → `eBook Kit`, `OCR Reader` → `OCR Toolbox`.
- Thêm trạng thái bật/tắt có lưu trữ (`config/plugins.json`).
- Tạo decorator `@require_plugin_enabled()`.
- Tạo project-scoped execution APIs cho plugin, nhận `slug` từ URL và validate project trước khi chạy.
- Dọn docstring `plugins/__init__.py` (xóa reference tới `consistency_check`, `content_analysis`).
- Chuẩn bị helper lấy project đang thao tác và default plugin paths theo slug, chưa đổi UI lớn ở phase này.
- Thêm TTL cleanup nhẹ cho `plugin_progress` để dọn progress/log cũ đã kết thúc.

File dự kiến:

- **[NEW]** `core/interfaces/__init__.py`
- **[MODIFY]** `webui/routes/plugins.py`
- **[NEW]** `config/plugins.json` (hoặc auto-generate lần đầu)
- **[MODIFY]** `plugins/__init__.py` (dọn docstring)

Kiểm tra sau phase:

- Gọi `GET /api/plugins/list` thấy 4 plugins đủ tên, mô tả, version, author, enabled, is_core.
- Toggle một tool plugin rồi reload server/UI vẫn giữ trạng thái.
- Core plugins từ chối disable qua API (`PATCH` trả 400).
- Hành vi execution của EPUB/OCR không đổi khi plugin enabled; URL đổi sang project-scoped route và payload luôn gắn với project slug.
- Project-scoped API chạy EPUB/OCR trả 403 khi plugin disabled.
- Project-scoped API trả lỗi rõ khi `slug` không tồn tại hoặc project đã bị archive/delete.
- Helper path trả đúng default: EPUB/OCR output vào `output`, Text -> EPUB input từ `translated`.
- Progress polling vẫn hoạt động; progress/log cũ hơn TTL bị xóa an toàn.

### Phase 2: Tách UI + Workspace động — Plugin management vào Cấu hình + plugin tabs trong workspace dự án

Mục tiêu:

- Xóa thẻ `Công cụ` khỏi main nav.
- Chuyển UI quản lý plugin thành partial riêng, include dưới cùng trong `tab_config.html`.
- Thêm workspace sub-tab `eBook Kit` và `OCR Toolbox` trong `projects-workspace-view`, hiển thị động theo plugin enabled state.
- Đổi nhãn OCR: `OCR Reader` → `OCR Toolbox`.
- Plugin panels dùng layout full-width, hoàn toàn tách biệt khỏi file sidebar/editor columns.
- Toolbar `#pm-workspace-column-toggles` chỉ hiển thị khi `$store.workspace.wsTab === 'editor'`.
- Form plugin lấy mặc định path từ `window.currentProject.slug`.
- Load plugin state 1 lần lúc `DOMContentLoaded`, cache vào `window.pluginState`. `openProject()` đọc từ cache.
- Khi toggle plugin trong Cấu hình: cập nhật `window.pluginState` + render lại workspace tabs nếu đang mở project.
- Nếu active `$store.workspace.wsTab` trỏ tới plugin disabled, tự chuyển về `editor` qua `PluginManager.setWorkspaceTab('editor')`.
- Nếu workspace state mất project, plugin panel không chạy và yêu cầu mở lại dự án.
- Rà soát codebase để xác nhận không còn nơi nào gọi route cũ (`/api/plugins/epub-converter`, `/api/plugins/ocr`), cập nhật sang route mới nếu phát hiện.

Chi tiết triển khai bắt buộc:

1. **Tạo workspace Alpine store**
   - Init store trước khi workspace tương tác, ví dụ trong `main.js` sau Alpine sẵn sàng:
     ```js
     document.addEventListener('alpine:init', () => {
         Alpine.store('workspace', { wsTab: 'editor' });
     });
     ```
   - Trong `tab_projects.html`, thay mọi `wsTab === '...'` bằng `$store.workspace.wsTab === '...'`.
   - Thay `x-on:click="wsTab = 'editor'"` bằng `x-on:click="$store.workspace.wsTab = 'editor'"`.

2. **Tạo `PluginManager` frontend namespace**
   - Tạo file mới `webui/static/js/plugin-manager.js` để tách rõ plugin state/render logic khỏi `ui-helpers.js`.
   - Include `plugin-manager.js` trong `webui/templates/partials/footer.html` sau `ui-helpers.js` và trước `project-manager.js`, để `ProjectManager.openProject()` dùng được `PluginManager`.
   - API tối thiểu:
     - `PluginManager.ensureLoaded()`
     - `PluginManager.getEnabledWorkspacePlugins()`
     - `PluginManager.renderWorkspaceTabs()`
     - `PluginManager.setWorkspaceTab(tabName)`
     - `PluginManager.togglePlugin(pluginId, enabled)`
   - `ensureLoaded()` phải chống duplicate request bằng cache Promise.
   - `renderWorkspaceTabs()` chỉ render plugin tabs khi `window.currentProject` tồn tại.

3. **Chuyển plugin management UI vào Cấu hình**
   - Tạo `webui/templates/partials/plugin_management.html`.
   - Include partial này ở cuối `webui/templates/partials/tab_config.html`.
   - Partial quản lý chỉ chứa list/toggle/settings entrypoint, không chứa form chạy EPUB/OCR.

4. **Tích hợp workspace tabs**
   - Trong vùng workspace tab buttons hiện có (`Biên tập`, `Thông tin`, `Chỉ dẫn`), thêm container cho plugin tab buttons do JS render, ví dụ `id="pm-plugin-workspace-tabs"`.
   - Plugin tab buttons do `PluginManager.renderWorkspaceTabs()` tạo theo thứ tự metadata.
   - Khi plugin disabled, remove button khỏi DOM; không dùng CSS hide.

5. **Tích hợp workspace panels**
   - Tạo `workspace_ebook_kit.html` và `workspace_ocr_toolbox.html`.
   - Include hai partial trong `tab_projects.html` làm sibling cùng cấp với panel `editor`, `info`, `prompt`.
   - Root panel dùng `x-show="$store.workspace.wsTab === 'ebook-kit'"` / `ocr-toolbox`.
   - Panel plugin không dùng file sidebar/editor columns.

6. **Toolbar editor columns**
   - `#pm-workspace-column-toggles` chỉ hiện khi `$store.workspace.wsTab === 'editor'`.
   - Có thể dùng `x-show="$store.workspace.wsTab === 'editor'"` ngay trên toolbar.

7. **Route migration**
   - Cập nhật `UiHelpers.runEpub...` và `UiHelpers.runOcr...` gọi `/api/projects/${window.currentProject.slug}/plugins/...`.
   - Trước khi gọi API, nếu không có `window.currentProject?.slug`, show toast và dừng.
   - Rà soát bằng `rg "/api/plugins/(epub-converter|ocr)"` và cập nhật mọi caller/tests/docs còn sót.
   - Sau khi không còn caller, xóa route cũ khỏi backend.

File dự kiến:

- **[MODIFY]** `webui/templates/partials/header.html` (xóa thẻ Công cụ)
- **[MODIFY]** `webui/templates/partials/tab_config.html` (thêm plugin management section via include)
- **[MODIFY]** `webui/templates/partials/tab_projects.html` (thêm workspace tab buttons, ẩn toolbar khi plugin tab active)
- **[MODIFY]** `webui/templates/partials/footer.html` (include `plugin-manager.js` trước `project-manager.js`)
- **[NEW]** `webui/templates/partials/plugin_management.html` (partial quản lý plugin, include trong `tab_config.html`)
- **[NEW]** `webui/templates/partials/workspace_ebook_kit.html` (partial panel eBook Kit full-width)
- **[NEW]** `webui/templates/partials/workspace_ocr_toolbox.html` (partial panel OCR Toolbox full-width)
- **[DELETE]** `webui/templates/partials/tab_plugins.html` (nội dung tách ra, file cũ xóa)
- **[MODIFY]** `webui/templates/index.html` (bỏ include `tab_plugins.html`)
- **[MODIFY]** `webui/static/js/main.js` (load plugin state vào `window.pluginState` lúc init)
- **[NEW]** `webui/static/js/plugin-manager.js` (`PluginManager.ensureLoaded`, render/guard workspace tabs)
- **[MODIFY]** `webui/static/js/project-manager.js` (render/guard workspace plugin tabs từ cache, toggle toolbar)
- **[MODIFY]** `webui/static/js/ui-helpers.js` (run plugin helpers gọi project-scoped API nếu giữ helper cũ)

Kiểm tra sau phase:

- Thẻ `Công cụ` không còn trên main nav.
- Tab `Cấu hình` có khối plugin management ở dưới cùng, hiển thị 4 plugins.
- Khi mở dự án, workspace có `Biên tập`, `Thông tin`, `Chỉ dẫn`, và thêm `eBook Kit`/`OCR Toolbox` nếu enabled.
- Plugin enabled → workspace tab xuất hiện đúng thứ tự sau `Chỉ dẫn`.
- Plugin disabled → workspace tab biến mất. Nếu đang đứng ở tab đó → quay về `Biên tập`.
- Plugin panels hiển thị full-width, không có file sidebar hay editor columns.
- Toolbar column toggles ẩn khi ở plugin tab, hiện lại khi quay về `Biên tập`.
- eBook Kit/OCR Toolbox không xuất hiện ở main nav.
- OCR chạy được từ workspace tab `OCR Toolbox`, output mặc định vào `workspace/projects/<slug>/output`.
- Không còn UI EPUB/OCR inline trong Cấu hình.
- Reload trang: plugin state + workspace tab đúng theo `config/plugins.json`.
- Nếu `GET /api/plugins/list` chậm hoặc lỗi, mở dự án không vỡ màn hình; plugin tabs render lại khi cache load thành công.
- JS ngoài Alpine đổi được workspace tab thông qua `$store.workspace.wsTab` hoặc `PluginManager.setWorkspaceTab()`.
- Không còn code nào gọi route cũ `/api/plugins/epub-converter` hoặc `/api/plugins/ocr`.
- Route cũ bị xóa khỏi backend; gọi route cũ nhận 404 mặc định.

### Phase 3: eBook Kit chia 2 subtab chức năng

Mục tiêu:

- Thay dropdown hướng chuyển đổi bằng 2 subtab dùng CSS-radio pattern (`.nt-tab-radio`):
  - `EPUB → Text`
  - `Text → EPUB`
- Mỗi subtab có form riêng, log riêng hoặc log chung nhưng rõ nguồn.
- Tách `runEpubConverter()` thành:
  - `runEpubToText()`
  - `runTextToEpub()`

File dự kiến:

- **[MODIFY]** `webui/templates/partials/workspace_ebook_kit.html`
- **[MODIFY]** `webui/static/js/ui-helpers.js`
- **[MODIFY]** `webui/static/js/project-manager.js` nếu cần restore/guard subtab trong project workspace.

Kiểm tra sau phase:

- `EPUB → Text` gửi payload `direction: "epub_to_text"`.
- `Text → EPUB` gửi payload `direction: "text_to_epub"`.
- Payload/API luôn gắn với project slug hiện hành: `/api/projects/<slug>/plugins/epub-converter`.
- `EPUB → Text` mặc định output vào `workspace/projects/<slug>/output`.
- `Text → EPUB` mặc định đọc từ `workspace/projects/<slug>/translated` và xuất vào `workspace/projects/<slug>/output`.
- Không còn trường option của hướng này lẫn vào hướng kia.
- Log/progress vẫn polling qua `/api/plugins/progress/<plugin_id>`.
- Sau khi chạy xong, project workspace refresh danh sách file/output liên quan.

### Phase 4: Settings plugin nếu có

Mục tiêu:

- Nút `Settings` chỉ hiện khi plugin có `has_settings = true`.
- OCR Toolbox có thể khai báo settings như language, cleanup mặc định, spell check mặc định, output format.
- eBook Kit có thể để `has_settings = false` giai đoạn đầu.

File dự kiến:

- **[MODIFY]** `webui/routes/plugins.py`
- **[MODIFY]** `services/config_service.py` nếu tận dụng `get_plugin_config()`
- **[MODIFY]** `webui/templates/partials/plugin_management.html`
- Có thể dùng modal trong `webui/templates/partials/modals.html`.

Kiểm tra sau phase:

- Plugin không có settings không hiện nút settings.
- Plugin có settings mở modal/panel được.
- Lưu settings reload vẫn giữ.
- Settings là mặc định toàn cục hoặc plugin-specific; khi chạy trong project, giá trị runtime vẫn ưu tiên thông số/đường dẫn của project đang thao tác.
- Settings không được ghi đè default project paths đã chốt, trừ khi user chủ động sửa settings.

### Phase 5: Kiểm thử và regression

Kiểm tra tối thiểu sau mỗi phase:

- `python -m pytest tests/smoke`
- Nếu phase đụng vào route/plugin API: thêm hoặc cập nhật unit tests liên quan `webui/routes/plugins.py`.
- Smoke thủ công WebUI:
  - Mở app.
  - Vào `Cấu hình`, cuộn xuống khối plugin management.
  - Bật/tắt từng tool plugin.
  - Mở một dự án và kiểm tra workspace tabs cập nhật realtime.
  - Chạy thử EPUB direction bằng input hợp lệ nhỏ.
  - Chạy thử OCR nếu môi trường có Tesseract; nếu không, xác nhận lỗi hiển thị rõ.
  - Xác nhận plugin dùng đúng slug, paths, file list và thông số của dự án đang thao tác.

## 9. Rủi ro và lưu ý

| Rủi ro | Tác động | Giải pháp trong kế hoạch |
|--------|----------|--------------------------|
| `core.interfaces` đang rỗng nhưng plugin classes import `ConverterPlugin` | Registry/introspection plugin sẽ fail nếu load class | Phase 1 tạo lại `core/interfaces/__init__.py` với `PluginBase`, `ConverterPlugin` tối thiểu; chưa refactor route chạy plugin sang class để tránh mở rộng scope. |
| `GET /api/plugins/list` hiện trả list tĩnh với cấu trúc cũ (`sub_tools`, `icon`) | Frontend cũ hoặc code phụ thuộc shape cũ có thể bị vỡ | Phase 1 giữ backward-compatible fields nếu còn dùng, đồng thời thêm fields mới (`enabled`, `is_core`, `workspace_tab`, `has_settings`). Unit test kiểm response shape. |
| Plugin enabled/disabled nhưng API vẫn gọi được | UI và backend lệch trạng thái; plugin bị tắt vẫn chạy qua script/curl | Phase 1 thêm `@require_plugin_enabled()` cho execution APIs; disabled plugin trả 403 rõ ràng. |
| Plugin state cache chưa load hoặc load lỗi khi mở project | Workspace có thể render thiếu tab plugin hoặc vỡ JS | Phase 2 tạo `PluginManager.ensureLoaded()` có Promise cache, fallback không render tool tabs khi lỗi, và render lại workspace sau khi load thành công. |
| `wsTab` là Alpine local state nên JS ngoài component không set được ổn định | Toggle plugin không thể tự chuyển tab về `Biên tập`, code dễ phụ thuộc DOM | Phase 2 chuyển sang `Alpine.store('workspace')`; mọi template dùng `$store.workspace.wsTab`, JS dùng `PluginManager.setWorkspaceTab()`. |
| Plugin phải thao tác theo dự án hiện hành, không phải path rời | Nếu backend không nhận slug, có thể ghi nhầm project hoặc dùng `workspace/input` cũ | Phase 1/2 đổi execution API sang `/api/projects/<slug>/plugins/...`, validate slug, default paths theo project: output vào `output`, Text -> EPUB đọc từ `translated`. |
| Workspace tab plugin bị tắt khi người dùng đang đứng trong tab đó | UI có thể kẹt ở panel không còn hợp lệ | Phase 2 render workspace plugin tabs theo plugin state; nếu active `$store.workspace.wsTab` là plugin disabled thì chuyển về `editor` qua `PluginManager.setWorkspaceTab('editor')`. |
| Project bị archive/delete hoặc `window.currentProject` mất khi đang ở plugin panel | Plugin có thể chạy thiếu context hoặc ghi sai nơi | Phase 2 guard ở UI và backend: không có project thì không chạy; backend validate project tồn tại trước mọi execution. |
| Route cũ còn sót caller sau khi chuyển project-scoped API | Một số nút/test/docs vẫn gọi route không còn tồn tại | Phase 2 bắt buộc `rg "/api/plugins/(epub-converter|ocr)"`, cập nhật toàn bộ caller/tests/docs, sau đó xóa route cũ; route cũ trả 404 mặc định. |
| OCR phụ thuộc Tesseract/dependency hệ thống | Test hoặc runtime có thể fail ở máy thiếu OCR dependency | Test tự động chỉ kiểm API/payload/error handling; smoke OCR thực tế ghi rõ điều kiện có Tesseract. UI phải hiển thị lỗi dependency dễ hiểu. |
| `plugin_progress` giữ log/status trong RAM và không tự xóa | Sau nhiều lần chạy plugin, RAM tăng vì log cũ không còn được dùng vẫn nằm trong dict | Phase 1 thêm TTL cleanup nhẹ: mỗi progress entry có `created_at/updated_at`; khi tạo hoặc poll progress, xóa entries đã `done/error` quá 30 phút. Mục đích chỉ là dọn log tiến trình cũ, không thay đổi chức năng plugin. |
| Tách eBook Kit thành hai hướng conversion có thể làm lệch payload hiện tại | EPUB -> Text hoặc Text -> EPUB có thể gửi thiếu field so với API cũ | Phase 3 giữ contract payload hiện có, chỉ tách UI và helper JS; test từng direction xác nhận `direction` và fields tương ứng. |

## 10. Thứ tự ưu tiên khuyến nghị

1. Tạo lại `core/interfaces` + registry/API quản lý plugin (source of truth).
2. Xóa `Công cụ`, đưa plugin management vào `Cấu hình` + tích hợp eBook Kit/OCR Toolbox vào workspace dự án + navigation động + rà soát route cũ.
3. Chia eBook Kit thành 2 subtab conversion (CSS-radio pattern).
4. Bổ sung settings plugin sau khi workflow chính ổn định.
