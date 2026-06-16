# Kế hoạch sửa lỗi hồi quy: Plugin integration sau khi thực hiện navigation plan

Ngày rà soát: 2026-06-15

## 1. Mục tiêu

Khôi phục trạng thái hoạt động bình thường của workspace dự án và plugin integration sau kế hoạch `2026-06-15-plugin-navigation-management-plan.md`.

Triệu chứng hiện tại:

- Trong tab `Cấu hình`, khối `Quản lý Plugin` không nạp danh sách plugin.
- Khi mở dự án, workspace mất file list/editors.
- Một số nút chức năng trong workspace không bấm được hoặc không phản hồi.

Phạm vi hotfix:

- Sửa lỗi tích hợp UI/plugin/backend route để hệ thống hoạt động lại đúng theo plan.
- Không thay đổi chức năng converter/OCR cốt lõi ngoài phần nối route project-scoped.
- Không refactor lớn plugin architecture trong lần sửa này.
- Không commit tự động, không changelog nếu không có yêu cầu riêng.

## 2. Kết luận rà soát nhanh

Đây là lỗi tích hợp nhiều điểm, không phải một lỗi đơn lẻ. Thứ tự ưu tiên sửa:

1. Khôi phục Alpine workspace state để tab `Biên tập` render lại file list/editors.
2. Sửa lifecycle của plugin list trong `Cấu hình`.
3. Sửa render plugin workspace tabs để không phụ thuộc Alpine directives được inject muộn.
4. Sửa frontend API URL dùng project slug.
5. Sửa backend project-scoped plugin execution để gọi implementation trực tiếp đã có, không gọi wrapper chưa tương thích.

## 2.1. Review sau khi đã áp dụng hotfix lần 1

Ngày review: 2026-06-15

Trạng thái hiện tại theo source:

- [x] Phase 1 đã thực hiện phần code chính: `footer.html` đã init `Alpine.store('workspace')` trước Alpine core; `main.js` đã bỏ listener `alpine:init` muộn; `ProjectManager.openProject()` đã reset `wsTab = 'editor'`.
- [~] Phase 2 đã đổi `@alpine:init` sang `x-init`, nhưng vẫn lỗi runtime: `PluginManager` chưa tồn tại tại thời điểm Alpine chạy `x-init`, nên khối `Quản lý Plugin` bị kẹt ở `Đang tải danh sách plugin...`.
- [~] Phase 3 đã chuyển plugin tabs sang DOM API và thêm guard store, nhưng class/style của plugin tabs vẫn dùng `tab-button pv2 ph3...`, không dùng cùng class `workspace-sub-tab` với `Biên tập/Thông tin/Chỉ dẫn`, gây lệch font/height/case.
- [~] Phase 4 đã sửa URL dùng `encodeURIComponent(slug)`, nhưng còn text fallback/log `OCR Reader` trong `ui-helpers.js`; cần đổi đồng bộ thành `OCR Toolbox`.
- [ ] Phase 5 chưa được thực hiện: `webui/routes/plugins.py` vẫn gọi `plugins.epub_converter.plugin.Plugin().convert(...)` và `plugins.ocr.plugin.Plugin().convert(...)`; lỗi wrapper EPUB/OCR vẫn còn.
- [ ] Phase 7 chưa đủ điều kiện chạy pass vì Phase 2, Phase 5 và Phase 6 còn lỗi/chưa xong.

Root cause hiện tại của lỗi plugin list:

- `plugin_management.html` đang có:

```html
x-init="PluginManager.ensureLoaded().then(...)"
```

- Nhưng `footer.html` load Alpine core trước `plugin-manager.js`:

```html
<script src="... alpine-persist.min.js"></script>
<script src="... alpine.min.js"></script>
...
<script src="... ui-helpers.js"></script>
<script src="... plugin-manager.js"></script>
```

- Alpine scan DOM và chạy `x-init` ngay khi core start. Lúc đó `window.PluginManager` chưa được định nghĩa. Expression lỗi, `loading` không đổi về `false`, nên UI chỉ hiện mãi `Đang tải danh sách plugin...`.

Phương án xử lý ưu tiên:

1. Load các dependency mà Alpine expression cần trước Alpine core:

```html
<script src="{{ url_for('static', filename='js/ui-helpers.js') }}?v={{ app_version }}"></script>
<script src="{{ url_for('static', filename='js/plugin-manager.js') }}?v={{ app_version }}"></script>
<script>
    document.addEventListener('alpine:init', function() {
        Alpine.store('workspace', { wsTab: 'editor' });
    });
</script>
<script src="{{ url_for('static', filename='js/alpine-persist.min.js') }}?v={{ app_version }}"></script>
<script src="{{ url_for('static', filename='js/alpine.min.js') }}?v={{ app_version }}"></script>
```

Sau đó chỉ giữ các app script còn lại sau Alpine:

```html
<script src="{{ url_for('static', filename='js/api-client.js') }}?v={{ app_version }}"></script>
<script src="{{ url_for('static', filename='js/provider-manager.js') }}?v={{ app_version }}"></script>
<script src="{{ url_for('static', filename='js/project-manager.js') }}?v={{ app_version }}"></script>
...
```

2. Giữ `plugin_management.html` dùng `x-init`, nhưng viết guard rõ để không kẹt loading nếu có lỗi:

```html
x-init="Promise.resolve()
    .then(() => {
        if (!window.PluginManager) throw new Error('PluginManager chưa được tải');
        return PluginManager.ensureLoaded();
    })
    .then(p => { plugins = p; loading = false; })
    .catch(e => { error = e.message || String(e); loading = false; })"
```

3. Trong `PluginManager.ensureLoaded()`, kiểm tra `res.ok` trước khi `res.json()` để lỗi API không bị nuốt thành dữ liệu sai:

```js
this._loadPromise = fetch('/api/plugins/list')
    .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
    })
    ...
```

Phương án dự phòng nếu không muốn đổi thứ tự script:

- Không gọi `PluginManager` trực tiếp trong `x-init`. Thay bằng một hàm inline defer đến `DOMContentLoaded` hoặc một custom event `plugin-manager-ready`. Tuy nhiên hướng này phức tạp hơn và dễ tạo race condition mới; ưu tiên vẫn là load `plugin-manager.js` trước Alpine vì Alpine component đang phụ thuộc global này.

## 3. Root causes

### 3.1. P0 — Alpine workspace store được đăng ký quá muộn

File liên quan:

- `webui/templates/partials/footer.html`
- `webui/static/js/main.js`
- `webui/templates/partials/tab_projects.html`

Hiện trạng:

- `footer.html` load `alpine.min.js` trước các script app (`main.js`, `plugin-manager.js`, `project-manager.js`).
- `main.js` lại đăng ký:

```js
document.addEventListener('DOMContentLoaded', function () {
    ...
    document.addEventListener('alpine:init', () => {
        Alpine.store('workspace', { wsTab: 'editor' });
        ...
    });
});
```

Vì Alpine core đã load trước `main.js`, event `alpine:init` nhiều khả năng đã chạy xong trước khi listener này được đăng ký. Kết quả: `Alpine.store('workspace')` không tồn tại.

`tab_projects.html` đang dùng `$store.workspace.wsTab` cho các tab/panel:

- `Biên tập`
- `Thông tin`
- `Chỉ dẫn`
- `eBook Kit`
- `OCR Toolbox`

Nếu `$store.workspace` undefined, Alpine expression lỗi, `x-show` của panel `Biên tập` không hoạt động đúng. Đây là nguyên nhân trực tiếp làm mất file list/editors và làm các nút trong workspace có vẻ không bấm được.

### 3.2. P0 — Plugin management dùng sai lifecycle event

File liên quan:

- `webui/templates/partials/plugin_management.html`

Hiện trạng:

```html
<div ... x-data="{ ... }" @alpine:init="PluginManager.ensureLoaded().then(...)">
```

`alpine:init` là event toàn cục để đăng ký store/plugin trước khi Alpine start, không phải lifecycle event ổn định cho một component đã render. Vì vậy component plugin management có thể không bao giờ gọi `PluginManager.ensureLoaded()`, khiến `loading` giữ nguyên và danh sách plugin không hiện.

### 3.3. P0 — ProjectManager không render plugin tabs khi mở project

File liên quan:

- `webui/static/js/project-manager.js`
- `webui/static/js/plugin-manager.js`

Plan yêu cầu `ProjectManager.openProject(slug)` phải load/cache plugin state và render workspace plugin tabs khi project được mở. Code hiện tại:

- set `window.currentProject = data`;
- render file list;
- không gọi `PluginManager.ensureLoaded()`;
- không gọi `PluginManager.renderWorkspaceTabs()`;
- không reset workspace tab về `editor`.

Kết quả: plugin tabs không xuất hiện ổn định khi mở project, hoặc active tab có thể trỏ tới một plugin tab không còn hợp lệ.

### 3.4. P0 — PluginManager inject Alpine directives bằng `innerHTML` sau khi Alpine đã init

File liên quan:

- `webui/static/js/plugin-manager.js`

Hiện trạng:

```js
container.innerHTML = `
  <button
    x-bind:class="$store.workspace.wsTab === 'ebook-kit' ? ... "
    x-on:click="$store.workspace.wsTab = 'ebook-kit'"
  >
`;
```

Các directive `x-bind` và `x-on` được thêm động sau khi Alpine đã quét DOM. Nếu không gọi `Alpine.initTree(container)`, chúng không được Alpine bind. Kết quả: plugin tab buttons có thể không click được và active style không cập nhật.

Khuyến nghị hotfix: không inject Alpine directives động. Tạo button bằng DOM API và gắn `addEventListener` thường.

### 3.5. P1 — Frontend gọi API project-scoped bằng object thay vì slug

File liên quan:

- `webui/static/js/ui-helpers.js`

Hiện trạng:

```js
fetch(`/api/projects/${window.currentProject}/plugins/epub-converter`, ...)
fetch(`/api/projects/${window.currentProject}/plugins/ocr`, ...)
```

`window.currentProject` là object project, không phải slug. URL thực tế sẽ thành:

```text
/api/projects/[object Object]/plugins/...
```

Đúng phải dùng:

```js
const slug = window.currentProject && window.currentProject.slug;
fetch(`/api/projects/${encodeURIComponent(slug)}/plugins/...`, ...)
```

### 3.6. P1 — Backend route gọi plugin wrapper chưa tương thích với implementation cũ

File liên quan:

- `webui/routes/plugins.py`
- `plugins/epub_converter/plugin.py`
- `plugins/ocr/plugin.py`
- `core/interfaces/__init__.py`

Hiện trạng EPUB:

- Route mới gọi `plugins.epub_converter.plugin.Plugin().convert(...)`.
- Wrapper `Plugin.convert()` detect `to_format` từ `output_path`.
- Route truyền `output_path` là thư mục `workspace/projects/<slug>/output`, không có suffix.
- `to_format` rỗng nên wrapper báo unsupported conversion.
- Ngoài ra `_epub_to_text()` tạo args sai tên field:
  - wrapper dùng `epub_file`, `output_dir`, `single_file`, `preserve_underline`;
  - implementation `convert_epub(args)` cần `epub_path`, `out_dir`, `mode`, `ext`, `underline`, `include_nonspine`, `preserve_dirs`, `prefix_index`.

Hiện trạng OCR:

- Route mới gọi `plugins.ocr.plugin.Plugin().convert(...)`.
- `Plugin.convert()` gọi `self.service_bus.get_service('config')`.
- `core/interfaces.PluginBase` hiện chỉ cấp `logger` và `config`, không cấp `service_bus`.
- Kết quả OCR wrapper có thể lỗi `AttributeError: 'Plugin' object has no attribute 'service_bus'`.

Khuyến nghị hotfix: giữ route project-scoped mới, nhưng bên trong gọi lại implementation trực tiếp như trước commit `8332cf1 feat: restructure plugin navigation`:

- EPUB -> Text: `plugins.epub_converter.epub_to_text.epub2text.convert_epub(args)`
- Text -> EPUB: `plugins.epub_converter.text_to_epub.main.process_book_directory(...)`
- OCR: `plugins.ocr.ocr_engine.ocr_file(...)`

Không sửa lớn plugin wrapper trong hotfix này. Việc chuẩn hóa wrapper/plugin runtime nên làm ở phase riêng sau khi hệ thống ổn định.

### 3.7. P1 — Backend route chưa validate project slug

File liên quan:

- `webui/routes/plugins.py`

Plan yêu cầu plugin là tính năng bổ sung cho project đang mở, nên route project-scoped phải validate slug tồn tại trước khi chạy. Hiện route nhận `<slug>` nhưng không kiểm tra project tồn tại.

Rủi ro:

- URL lỗi như `[object Object]` vẫn đi vào route.
- Default path có thể trỏ tới `workspace/projects/[object Object]/...`.
- Debug khó vì lỗi xuất hiện muộn trong background thread.

### 3.8. P2 — Các lỗi phụ cần xử lý sau P0/P1

File liên quan:

- `webui/routes/plugins.py`
- `webui/static/js/plugin-manager.js`
- `webui/static/js/ui-helpers.js`

Ghi nhận:

- `PATCH /api/plugins/<plugin_id>` với plugin không tồn tại có thể trả `null` HTTP 200. Nên trả 404.
- `cleanup_plugin_progress()` lặp trực tiếp trên `plugin_progress.items()` trong khi background thread có thể mutate. Nên duyệt `list(plugin_progress.items())`.
- Nhãn button/log còn `OCR Reader`; nên đổi đồng bộ thành `OCR Toolbox`.
- `PluginManager.setWorkspaceTab()` gọi `Alpine.store('workspace').wsTab` không guard store tồn tại.

## 4. Phương án sửa theo phase

### Phase 1 — Khôi phục workspace project trước `[x] code done, cần verify UI`

Mục tiêu:

- Mở project phải thấy lại file list/editors.
- Các nút trong tab `Biên tập` hoạt động như trước.
- Chưa cần plugin tabs hoạt động ở phase này.

Thao tác:

1. Trong `webui/templates/partials/footer.html`, thêm script init workspace store trước khi load `alpine.min.js`.

Ví dụ:

```html
<script>
    document.addEventListener('alpine:init', function() {
        Alpine.store('workspace', { wsTab: 'editor' });
    });
</script>
<script src="{{ url_for('static', filename='js/alpine-persist.min.js') }}?v={{ app_version }}"></script>
<script src="{{ url_for('static', filename='js/alpine.min.js') }}?v={{ app_version }}"></script>
```

2. Trong `webui/static/js/main.js`, xóa block đăng ký `document.addEventListener('alpine:init', ...)` nằm trong `DOMContentLoaded`.

Block cần xóa gồm:

```js
// Setup Alpine.js workspace store and watcher
document.addEventListener('alpine:init', () => {
    Alpine.store('workspace', { wsTab: 'editor' });

    Alpine.effect(() => {
        const workspaceEl = document.querySelector('[x-data*="activeTab"]');
        ...
        switchProjectTab(activeTab);
    });
});
```

Lý do xóa:

- Store init tại đây quá muộn.
- Watcher đang tham chiếu `activeTab`/`switchProjectTab(activeTab)` theo pattern cũ, không thuộc workspace tab mới.

3. Trong `webui/static/js/project-manager.js`, khi `openProject(slug)` thành công, đảm bảo workspace tab quay về `editor`.

Ví dụ sau khi `window.currentProject = data`:

```js
if (window.PluginManager) {
    PluginManager.setWorkspaceTab('editor');
}
```

Nếu chưa sửa `PluginManager.setWorkspaceTab()` ở phase 3 thì có thể guard trực tiếp:

```js
try {
    if (window.Alpine && Alpine.store('workspace')) {
        Alpine.store('workspace').wsTab = 'editor';
    }
} catch (e) {}
```

Kiểm tra sau phase:

- Mở app.
- Vào `Dự án`.
- Mở một project bất kỳ.
- Thấy lại sidebar file list, source editor, result editor.
- Bấm mini-tabs `Bản gốc/Bản dịch/Soát lỗi` vẫn hoạt động.
- Bấm các nút upload/chia nhỏ/dịch/soát lỗi không bị bất hoạt do lỗi JS global.

Ghi nhận review 2026-06-15:

- [x] `footer.html` đã có inline listener `alpine:init` trước `alpine.min.js`.
- [x] `main.js` đã bỏ block `document.addEventListener('alpine:init', ...)` muộn.
- [x] `ProjectManager.openProject()` đã reset `wsTab = 'editor'`.
- [ ] Chưa có bằng chứng test UI thủ công sau phase; cần verify lại sau khi sửa Phase 2.

### Phase 2 — Sửa plugin list trong Cấu hình `[~] partial, còn lỗi script order`

Mục tiêu:

- Tab `Cấu hình` hiển thị danh sách 4 plugin:
  - Translation
  - Spell Check
  - eBook Kit
  - OCR Toolbox
- Core plugins không toggle được.
- eBook Kit/OCR Toolbox toggle được và state cập nhật.

Thao tác:

1. Trong `webui/templates/partials/plugin_management.html`, đổi `@alpine:init` thành `x-init`.

Gợi ý cấu trúc:

```html
<div
    ...
    x-data="{ plugins: [], loading: true, error: null }"
    x-init="PluginManager.ensureLoaded()
        .then(p => { plugins = p; loading = false; })
        .catch(e => { error = e; loading = false; })"
>
```

2. Vì `PluginManager.ensureLoaded()` hiện catch lỗi và resolve `[]`, vẫn nên set `loading = false` trong cả success/failure.

3. Thêm UI trạng thái lỗi nhẹ nếu `error` có giá trị, hoặc ít nhất không để spinner chạy vô hạn.

4. Khi toggle:

```html
@change="PluginManager.togglePlugin(plugin.id, $event.target.checked)
    .then(updated => Object.assign(plugin, updated))
    .catch(() => { $event.target.checked = plugin.enabled; })"
```

5. Bổ sung bắt buộc sau review: đảm bảo `window.PluginManager` đã tồn tại trước khi Alpine chạy `x-init`.

Thực hiện bằng cách sửa thứ tự script trong `footer.html`:

- Load `ui-helpers.js` trước `plugin-manager.js` vì `PluginManager.ensureLoaded()` có dùng `UiHelpers.showToast(...)` khi lỗi.
- Load `plugin-manager.js` trước `alpine.min.js` vì `plugin_management.html` gọi `PluginManager.ensureLoaded()` trong `x-init`.
- Giữ `api-client.js`, `provider-manager.js`, `project-manager.js`, `editor-component.js`, `prompt-manager.js`, `translation-worker.js`, `main.js` sau Alpine nếu các file này không được Alpine expression gọi lúc init.

Thứ tự mong muốn:

```html
<script src="{{ url_for('static', filename='js/ui-helpers.js') }}?v={{ app_version }}"></script>
<script src="{{ url_for('static', filename='js/plugin-manager.js') }}?v={{ app_version }}"></script>
<script>
    document.addEventListener('alpine:init', function() {
        Alpine.store('workspace', { wsTab: 'editor' });
    });
</script>
<script src="{{ url_for('static', filename='js/alpine-persist.min.js') }}?v={{ app_version }}"></script>
<script src="{{ url_for('static', filename='js/alpine.min.js') }}?v={{ app_version }}"></script>
```

6. Sửa `x-init` có guard lỗi để spinner không kẹt vô hạn nếu dependency/API fail:

```html
x-init="Promise.resolve()
    .then(() => {
        if (!window.PluginManager) throw new Error('PluginManager chưa được tải');
        return PluginManager.ensureLoaded();
    })
    .then(p => { plugins = p; loading = false; })
    .catch(e => { error = e.message || String(e); loading = false; })"
```

7. Sửa `PluginManager.ensureLoaded()` check HTTP status:

```js
.then(res => {
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
})
```

Kiểm tra sau phase:

- Vào `Cấu hình`.
- Danh sách plugin hiện ra.
- eBook Kit/OCR Toolbox hiển thị đúng name, description, version, author.
- Toggle một plugin, reload trang, state vẫn giữ.
- Toggle lỗi phải revert checkbox hoặc báo toast.

Ghi nhận review 2026-06-15:

- [x] `plugin_management.html` đã đổi sang `x-init`.
- [x] Toggle đã dùng `Object.assign(plugin, updated)` và revert checkbox khi lỗi.
- [ ] Còn lỗi P0: `plugin-manager.js` vẫn load sau Alpine nên `x-init` gọi `PluginManager` quá sớm.
- [ ] Cần thêm guard lỗi trong `x-init` và `ensureLoaded()` để không kẹt loading.

### Phase 3 — Sửa PluginManager workspace tabs `[~] partial, logic ổn hơn nhưng style chưa thống nhất`

Mục tiêu:

- Khi project đang mở và plugin enabled, workspace nav có:
  - `Biên tập`
  - `Thông tin`
  - `Chỉ dẫn`
  - `eBook Kit`
  - `OCR Toolbox`
- Plugin tabs click được, active style đúng.
- Tắt plugin khi đang đứng trong plugin tab thì tự quay về `Biên tập`.

Thao tác:

1. Trong `webui/static/js/plugin-manager.js`, thêm helper guard workspace store.

Gợi ý:

```js
getWorkspaceStore() {
    try {
        if (!window.Alpine) return null;
        return Alpine.store('workspace') || null;
    } catch (e) {
        return null;
    }
},
```

2. Sửa `setWorkspaceTab(tabName)` dùng helper trên, không throw nếu store chưa sẵn sàng.

```js
setWorkspaceTab(tabName) {
    const store = this.getWorkspaceStore();
    if (!store) return false;
    store.wsTab = tabName;
    this.syncWorkspaceTabButtons();
    return true;
},
```

3. Sửa `renderWorkspaceTabs()` không inject Alpine directives bằng `innerHTML`.

Gợi ý:

```js
renderWorkspaceTabs() {
    if (!window.currentProject) return;
    const container = document.getElementById('pm-plugin-workspace-tabs');
    if (!container) return;

    container.innerHTML = '';
    this.getEnabledWorkspacePlugins().forEach(plugin => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'workspace-sub-tab';
        btn.dataset.workspaceTab = plugin.workspace_tab;
        btn.textContent = plugin.name;
        btn.addEventListener('click', () => this.setWorkspaceTab(plugin.workspace_tab));
        container.appendChild(btn);
    });

    this.syncWorkspaceTabButtons();
},
```

4. Thêm `syncWorkspaceTabButtons()` để cập nhật active class cho plugin buttons.

```js
syncWorkspaceTabButtons() {
    const store = this.getWorkspaceStore();
    const active = store ? store.wsTab : 'editor';
    document.querySelectorAll('#pm-plugin-workspace-tabs [data-workspace-tab]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.workspaceTab === active);
    });
},
```

5. Sau khi toggle plugin:

- update cache;
- render lại workspace tabs nếu đang có project;
- nếu plugin vừa tắt và active tab bằng `updatedPlugin.workspace_tab`, set về `editor`.

6. Trong `webui/static/js/project-manager.js`, sau khi project data load xong và `window.currentProject = data`, gọi:

```js
if (window.PluginManager) {
    PluginManager.ensureLoaded().then(() => PluginManager.renderWorkspaceTabs());
}
```

Không để plugin load failure làm hỏng open project. Nếu promise lỗi, chỉ log/toast nhẹ và vẫn giữ workspace `Biên tập`.

7. Trong `backToList()`, reset workspace tab về `editor` và clear plugin tab container.

Gợi ý:

```js
if (window.PluginManager) {
    PluginManager.setWorkspaceTab('editor');
}
const pluginTabs = document.getElementById('pm-plugin-workspace-tabs');
if (pluginTabs) pluginTabs.innerHTML = '';
```

8. Bổ sung bắt buộc sau review: plugin tabs phải dùng đúng class `workspace-sub-tab`, không dùng `tab-button pv2 ph3...`.

Sửa `renderWorkspaceTabs()`:

```js
btn.className = 'workspace-sub-tab';
```

Sửa `syncWorkspaceTabButtons()`:

```js
btn.classList.toggle('active', btn.dataset.workspaceTab === active);
```

Không set lại toàn bộ `className` thành chuỗi Tachyons khác nhau vì sẽ làm lệch font/height/case với các tab gốc.

Kiểm tra sau phase:

- Bật eBook Kit/OCR Toolbox trong `Cấu hình`.
- Mở project, thấy hai tab plugin sau `Chỉ dẫn`.
- Click `eBook Kit`, panel eBook Kit hiện full-width.
- Click `OCR Toolbox`, panel OCR Toolbox hiện full-width.
- Click lại `Biên tập`, file list/editors hiện lại.
- Tắt eBook Kit khi đang đứng ở tab eBook Kit, workspace tự về `Biên tập`.

Ghi nhận review 2026-06-15:

- [x] `PluginManager.getWorkspaceStore()` đã có guard.
- [x] `setWorkspaceTab()` không throw khi store thiếu.
- [x] `renderWorkspaceTabs()` đã dùng DOM API, không inject Alpine directives.
- [x] `ProjectManager.openProject()` đã gọi `PluginManager.ensureLoaded().then(...renderWorkspaceTabs())`.
- [x] `ProjectManager.backToList()` đã reset tab và clear plugin tab container.
- [ ] Còn lỗi UI: plugin tabs vẫn dùng class `tab-button ...`, không dùng `workspace-sub-tab`; cần sửa để thống nhất typography.

### Phase 4 — Sửa frontend API dùng project slug `[~] mostly done, còn text OCR Reader`

Mục tiêu:

- eBook Kit/OCR Toolbox luôn gọi API theo project đang mở.
- Không còn URL `[object Object]`.

Thao tác:

1. Trong `webui/static/js/ui-helpers.js`, thêm helper lấy current project slug cho plugin actions.

Gợi ý:

```js
getCurrentProjectSlugForPlugin() {
    const slug = window.currentProject && window.currentProject.slug;
    if (!slug) {
        UiHelpers.showToast('Vui lòng mở một dự án trước khi chạy plugin', 'error');
        return null;
    }
    return slug;
},
```

Nếu không muốn thêm method mới, đặt local trong từng function cũng được, nhưng phải thống nhất.

2. Trong `runEpubToText()`, `runTextToEpub()`, `runProjectOcr()`, thay:

```js
fetch(`/api/projects/${window.currentProject}/plugins/...`, ...)
```

bằng:

```js
const slug = window.currentProject && window.currentProject.slug;
if (!slug) { ... return; }
fetch(`/api/projects/${encodeURIComponent(slug)}/plugins/...`, ...)
```

3. Đổi text button/log còn `OCR Reader` thành `OCR Toolbox`.

Kiểm tra sau phase:

- Mở DevTools Network.
- Chạy eBook Kit/OCR Toolbox.
- Request URL phải có dạng `/api/projects/<slug>/plugins/...`.
- Không có request `/api/projects/[object Object]/...`.

Ghi nhận review 2026-06-15:

- [x] `UiHelpers.getCurrentProjectSlug()` đã được thêm.
- [x] `runEpubToText()`, `runTextToEpub()`, `runProjectOcr()` đã dùng `encodeURIComponent(slug)`.
- [ ] Còn text `OCR Reader` tại các trạng thái button/log trong `runProjectOcr()`; cần đổi thành `OCR Toolbox`.

### Phase 5 — Sửa backend plugin execution project-scoped `[ ] not done`

Mục tiêu:

- Giữ route mới:
  - `POST /api/projects/<slug>/plugins/epub-converter`
  - `POST /api/projects/<slug>/plugins/ocr`
- Không dùng route cũ `/api/plugins/epub-converter` và `/api/plugins/ocr`.
- Bên trong route dùng implementation trực tiếp đã chạy được trước đây.

Thao tác EPUB:

1. Trong `webui/routes/plugins.py`, ở `run_epub_converter(slug)`, bỏ gọi:

```py
from plugins.epub_converter.plugin import Plugin
plugin = Plugin()
plugin.initialize(...)
plugin.convert(...)
```

2. Với `direction == "epub_to_text"`, gọi trực tiếp:

```py
from plugins.epub_converter.epub_to_text.epub2text import convert_epub

class Args:
    pass

args = Args()
args.epub_path = data.get("epub_path", "")
args.out_dir = data.get("out_dir") or f"workspace/projects/{slug}/output"
args.mode = data.get("mode", "single")
args.ext = data.get("ext", "txt")
args.underline = data.get("underline", False)
args.include_nonspine = data.get("include_nonspine", False)
args.preserve_dirs = data.get("preserve_dirs", False)
args.prefix_index = data.get("prefix_index", True)

convert_epub(args)
```

3. Với `direction == "text_to_epub"`, gọi trực tiếp:

```py
from plugins.epub_converter.text_to_epub.main import process_book_directory

directory = Path(data.get("directory") or f"workspace/projects/{slug}/translated")
use_markdown = data.get("use_markdown", False)
split_chapters = data.get("split_chapters", True)

process_book_directory(directory, use_markdown, split_chapters)
```

4. Đảm bảo output dir mặc định tồn tại trước khi convert:

```py
Path(f"workspace/projects/{slug}/output").mkdir(parents=True, exist_ok=True)
```

Thao tác OCR:

1. Trong `run_ocr(slug)`, bỏ gọi `plugins.ocr.plugin.Plugin().convert(...)`.

2. Gọi trực tiếp:

```py
from plugins.ocr.ocr_engine import ocr_file

result = ocr_file(
    input_path,
    pages=pages,
    output_path=output_path,
    skip_steps=skip_steps,
    process_mode=process_mode
)
```

3. Giữ logic kiểm tra:

- input path tồn tại;
- output path mặc định là `workspace/projects/<slug>/output/ocr_result.txt`;
- kết quả có `result.get("text")` thì status `done`, lưu `char_count`.

Project slug validation:

1. Trước khi tạo background thread, validate project tồn tại.

Tìm service/helper hiện có trong project routes. Nếu có `ProjectService`, dùng cùng cách các route `/api/projects/<slug>` đang dùng. Nếu chưa có helper, kiểm tra tối thiểu:

```py
project_dir = Path("workspace/projects") / slug
if not project_dir.exists() or not project_dir.is_dir():
    return jsonify({"error": "Dự án không tồn tại"}), 404
```

2. Không dùng slug để build path nếu chưa validate.

Progress cleanup:

1. Sửa `cleanup_plugin_progress()`:

```py
for pid, info in list(plugin_progress.items()):
    ...
```

2. Khi xóa:

```py
plugin_progress.pop(pid, None)
```

Unknown plugin update:

1. Trong `update_plugin(plugin_id)`, nếu plugin id không nằm trong danh sách metadata hợp lệ và không phải core, trả 404 thay vì tạo entry mới.

Ghi nhận review 2026-06-15:

- [ ] `run_epub_converter(slug)` vẫn import `from plugins.epub_converter.plugin import Plugin` và gọi `plugin.convert(...)`.
- [ ] `run_ocr(slug)` vẫn import `from plugins.ocr.plugin import Plugin` và gọi `plugin.convert(...)`.
- [ ] `cleanup_plugin_progress()` vẫn duyệt trực tiếp `plugin_progress.items()`.
- [ ] `update_plugin(plugin_id)` vẫn có thể tạo state cho plugin id lạ rồi trả `null`.
- [ ] Chưa validate project slug trước khi tạo `plugin_id`/background thread.

Kiểm tra sau phase:

- `GET /api/plugins/list` trả đủ metadata.
- Tắt eBook Kit, gọi route EPUB trả 403.
- Gọi route với slug không tồn tại trả 404 trước khi tạo progress id.
- Bật eBook Kit, chạy EPUB -> Text với file test nhỏ, progress done/error rõ ràng.
- Bật OCR Toolbox, gọi OCR với input không tồn tại trả progress error rõ ràng, không crash server.

### Phase 6 — Chuẩn hóa typography workspace tabs và bottom status bar `[ ] new after review`

Mục tiêu:

- `Biên tập`, `Thông tin`, `Chỉ dẫn`, `eBook Kit`, `OCR Toolbox` có cùng font size, weight, line-height, height, casing.
- Giữ đúng casing tự nhiên theo nhãn: `Biên tập`, `Thông tin`, `Chỉ dẫn`, `eBook Kit`, `OCR Toolbox`. Không ép uppercase.
- Khu vực status bar `Bản gốc: 0 ký tự | 0 từ | ~0 tokens` có cỡ chữ tương ứng với text phụ/button trong cùng workspace, không lớn hơn hẳn các khu vực khác.

Root cause UI hiện tại:

- `.workspace-sub-tab` trong `webui/static/css/style.css` đang có `text-transform: uppercase` và `letter-spacing: 0.03em`, làm 3 tab gốc bị ép kiểu khác nhãn plugin.
- Plugin tabs do `PluginManager.renderWorkspaceTabs()` tạo lại dùng class `tab-button pv2 ph3...`, không dùng `.workspace-sub-tab`, nên font/height/active style lệch với tab gốc.
- Status bar trong `tab_projects.html` dòng `Bản gốc: ...` không có class font size (`f7`) và không có CSS riêng, nên inherit lớn hơn so với label/button xung quanh.

Thao tác:

1. Sửa `.workspace-sub-tab` trong `webui/static/css/style.css`:

```css
.workspace-sub-tab {
    padding: 0.65rem 0.9rem;
    font-size: 0.8125rem;
    line-height: 1.25rem;
    font-weight: 600;
    text-transform: none;
    letter-spacing: 0;
    ...
}
```

2. Sửa `PluginManager.renderWorkspaceTabs()` để plugin tabs dùng cùng class:

```js
btn.className = 'workspace-sub-tab';
```

3. Sửa `PluginManager.syncWorkspaceTabButtons()` để chỉ toggle class `active`, không rewrite className bằng Tachyons:

```js
btn.classList.toggle('active', btn.dataset.workspaceTab === active);
```

4. Thêm class/CSS cho bottom status bar. Ưu tiên CSS để tránh rải Tachyons inline:

```css
.workspace-bottom-status {
    font-size: 0.75rem;
    line-height: 1.25rem;
    color: var(--text-muted);
}

.workspace-bottom-status strong {
    font-size: inherit;
    line-height: inherit;
}
```

5. Trong `webui/templates/partials/tab_projects.html`, thêm class vào các wrapper hoặc span status:

```html
<div id="pm-translation-bottom-bar" class="... workspace-bottom-status">
...
<div id="pm-spellcheck-bottom-bar" class="... workspace-bottom-status">
```

6. Kiểm tra không có tab nào bị cao/thấp khác nhau khi bật/tắt plugin.

Kiểm tra sau phase:

- Mở project với cả hai plugin enabled.
- Nhìn cùng hàng tab: 5 nhãn có cùng baseline/height/font weight.
- Không có nhãn bị ép uppercase.
- `Bản gốc: 0 ký tự | 0 từ | ~0 tokens` cùng cỡ với text phụ/button quanh nó, không nổi quá lớn.
- Resize browser hẹp hơn, tab không wrap/đè lên toolbar.

### Phase 7 — Test hồi quy bắt buộc `[ ] blocked until Phase 2/5/6 pass`

Mục tiêu:

- Đảm bảo sửa plugin không làm hỏng flow dự án gốc.

Test API tối thiểu:

1. `GET /api/plugins/list`
   - HTTP 200.
   - Có 4 plugin.
   - `epub_converter.name == "eBook Kit"`.
   - `ocr.name == "OCR Toolbox"`.

2. `PATCH /api/plugins/translation`
   - HTTP 400, không cho tắt core plugin.

3. `PATCH /api/plugins/not-real`
   - HTTP 404.

4. `POST /api/projects/not-real/plugins/epub-converter`
   - HTTP 404.

5. Tắt `epub_converter`, gọi route EPUB với project thật:
   - HTTP 403.

6. Bật lại `epub_converter`, gọi route EPUB với input missing:
   - HTTP 200 tạo progress id hoặc HTTP 400 tùy cách validate đồng bộ.
   - Progress cuối cùng `error`, message nói rõ file không tồn tại.

Test UI thủ công:

1. Reload app.
2. Vào `Cấu hình`.
3. Plugin list hiện, toggle hoạt động.
4. Vào `Dự án`, mở project.
5. File list/editors hiện.
6. Mini-tabs `Bản gốc/Bản dịch/Soát lỗi` hoạt động.
7. Bật eBook Kit/OCR Toolbox, project workspace có thêm tabs.
8. Click plugin tabs và quay lại `Biên tập` không mất editors.
9. Tắt plugin đang active, workspace tự về `Biên tập`.
10. Chạy plugin action, Network URL dùng `<slug>`, không có `[object Object]`.

## 5. Chỉ dẫn triển khai cho model sửa code

- Trước khi sửa function/class/method theo AGENTS.md, chạy GitNexus impact analysis cho symbol sẽ sửa và báo blast radius.
- Mỗi phase chỉ sửa đúng file cần thiết.
- Ưu tiên `replace_file_content` nếu model có tool đó; trong Codex dùng `apply_patch`.
- Không dùng `write_to_file` trên file đã tồn tại.
- Không commit, không tạo changelog.
- Sau mỗi phase phải chạy kiểm tra tương ứng trước khi sang phase sau.
- Nếu Phase 1 chưa pass, không làm Phase 2+.
- Nếu UI vẫn trắng workspace sau Phase 1, ưu tiên kiểm tra console error `$store.workspace` trước khi sửa thứ khác.
- Không refactor plugin wrapper trong hotfix. Wrapper có thể được sửa ở kế hoạch riêng sau khi route project-scoped đã ổn định.

## 6. Tiêu chí hoàn thành

Hotfix được xem là hoàn thành khi:

- `Cấu hình` nạp được danh sách plugin.
- Mở project không mất file list/editors.
- Các chức năng gốc `Biên tập`, `Thông tin`, `Chỉ dẫn`, dịch và kiểm chính tả vẫn hoạt động.
- eBook Kit/OCR Toolbox chỉ xuất hiện trong workspace khi enabled.
- Plugin panels thao tác theo project đang mở, dùng đúng project slug/path mặc định.
- Project-scoped plugin API validate project slug và trạng thái enabled.
- Không còn request `/api/projects/[object Object]/plugins/...`.
- Backend không gọi `plugins.epub_converter.plugin.Plugin().convert(...)` hoặc `plugins.ocr.plugin.Plugin().convert(...)` trong hotfix route.

## 7. Việc để sau, không thuộc hotfix

- Chuẩn hóa plugin runtime/service bus thật sự cho `plugins/*/plugin.py`.
- Thiết kế settings schema chi tiết cho OCR Toolbox.
- Tách progress store khỏi global dict hoặc thêm lock/thread-safe queue.
- Mở rộng TTL cleanup thành job định kỳ nếu cần.
- Viết E2E Playwright đầy đủ cho toàn bộ workspace tabs.
