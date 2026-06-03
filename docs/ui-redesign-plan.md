# [ĐÃ HOÀN THÀNH] Kế Hoạch Cải Tiến UI — Novel Translator

> ⚠️ Tài liệu lịch sử — UI redesign đã hoàn tất. Giữ lại để tham khảo quyết định thiết kế.
> **Trạng thái:** Tất cả mục tiêu đã triển khai trong v7.0.0–v7.2.0.

---

## 1. Đánh giá Hiện trạng

### 1.1. Cấu trúc UI hiện tại

```
Header: Brand | Nav (6 tabs) | Stats | Focus Mode
├── Tab "Dự án" (workspace) — 391 dòng HTML
│   ├── Sidebar: Danh sách project
│   └── 5 sub-tabs:
│       ├── Nội dung gốc: Bảng file + Editor đôi (source/translated)
│       ├── Nội dung dịch: Bảng file + Editor đôi (source/translated)
│       ├── Kiểm chính tả: Bảng file + Editor đôi (source/spellcheck)
│       ├── Thông tin: 4 sub-tabs radio (Hướng dẫn/Mối quan hệ/Thuật ngữ/Tóm tắt)
│       └── Chỉ dẫn: 5 sub-tabs radio (Dịch thuật/Tóm tắt/Quan hệ/Thuật ngữ/Chính tả)
├── Tab "Cấu hình" (config) — 178 dòng HTML
├── Tab "Chỉ dẫn AI" (prompts) — 89 dòng HTML
├── Tab "Công cụ" (plugins) — 130 dòng HTML
├── Tab "Nhật ký" (logs) — 33 dòng HTML
└── Tab "Lưu trữ" (archive) — 37 dòng HTML
```

### 1.2. Files hiện tại

| File | Dòng | Ghi chú |
|------|------|---------|
| `main.js` | 3,377 | Monolith, chứa toàn bộ logic |
| `style.css` | 454 | Tachyons + custom CSS |
| `modal.js` | 132 | ModalManager (sẽ merge vào ui-helpers.js) |
| `tab_workspace.html` | 391 | Lớn nhất, chứa 5 sub-tabs |
| `tab_config.html` | 178 | Provider cards + config |
| `tab_prompts.html` | 89 | Prompt library |
| `tab_plugins.html` | 130 | EPUB + OCR |
| `tab_archive.html` | 37 | Archive table |
| `tab_logs.html` | 33 | Log viewer |
| `modals.html` | 127 | 3 modals |
| `footer.html` | 67 | 2 modals + scripts |
| `header.html` | 55 | Nav + stats |

### 1.3. Vấn đề chính

| # | Vấn đề | Mức độ | Ảnh hưởng |
|---|--------|--------|-----------|
| 1 | **3 editor đôi trùng lặp** (workspace, translated, spellcheck) | CAO | ~180 dòng HTML lặp lại, bug fix phải sửa 3 chỗ |
| 2 | **5 sub-tabs trong dự án** | CAO | Người dùng phải click nhiều để chuyển tác vụ |
| 3 | **main.js monolith 3,377 dòng** | CAO | Khó maintain, khó tìm code |
| 4 | **Prompt editor trùng lặp** (tab Chỉ dẫn AI + tab Chỉ dẫn dự án) | TRUNG BÌNH | 2 nơi quản lý cùng 1 kiểu dữ liệu |
| 5 | **Thiếu responsive** | THẤP | Không ưu tiên lúc này |

---

## 2. Nguyên tắc Thiết kế & Kiến trúc Frontend

### 2.1. Nguyên tắc Thiết kế

1. **Tối giản thay vì đổi mới** — Giữ nguyên Tachyons CSS, giữ phong cách Slate & Indigo, tập trung nâng cấp cấu trúc.
2. **Giảm clicks** — Tối ưu hóa điều hướng từ 3-4 clicks xuống còn 1-2 clicks cho các luồng tác vụ dịch/soát lỗi cốt lõi.
3. **Một Editor đôi duy nhất** — Tái sử dụng một khung soạn thảo song ngữ duy nhất cho toàn bộ các tác vụ (Dịch thuật, Soát lỗi).
4. **Phân rã JS Monolith thành Modules** — Tách biệt file `main.js` khổng lồ thành các module ES6 độc lập nhỏ gọn (< 500 dòng/file).
5. **Không phá vỡ hành vi hệ thống (Zero API Changes)** — Giữ nguyên tất cả các API endpoints hiện có của backend.

### 2.2. Kiến trúc Frontend (Alpine.js + ES Modules)

*   **Presentation tĩnh:** Layout chính được sinh bởi Flask/Jinja2.
*   **State & UI Reactivity (Alpine.js):** Sử dụng **Alpine.js 3.14.x** (CDN + local fallback) làm động cơ quản lý trạng thái UI (Tab switching, Sidebar toggle, Modal toggling, Accordion) trực tiếp trên HTML qua các chỉ thị khai báo (`x-data`, `x-show`, `x-model`, `x-on:click`). Loại bỏ hoàn toàn nhu cầu viết code DOM thủ công trong JS.
*   **Logic Nghiệp vụ (ES Modules):** Các tác vụ phức tạp (gọi API, quản lý dự án, ghép file, Server-Sent Events, xử lý text) được phân rã thành các tệp tin JS ES Modules sạch sẽ dưới `webui/static/js/`. Alpine.js gọi tới các module này qua Namespace pattern.

### 2.3. Nguyên tắc Sinh mã & Sửa mã (MANDATORY)

*   **Tham khảo & Tận dụng mã có sẵn:** Trước khi tạo bất kỳ cấu trúc hay hàm nào mới, bắt buộc tham khảo cấu trúc dự án đã tạo bởi `gitnexus` để tận dụng tối đa mã nguồn hiện có.
*   **Chỉ viết mới khi cần thiết:** Chỉ tạo file mới hoặc viết logic mới khi có sự xác nhận rõ ràng trong kế hoạch.
*   **Không sinh mã inline (No Inline Styling):** Tuyệt đối không nhúng style trực tiếp trên thẻ HTML. Sử dụng hệ thống Tachyons CSS của dự án.
*   **Chỉnh sửa tối giản:** Sử dụng công cụ chỉnh sửa có phạm vi hẹp để sửa đúng các dòng cần thiết. Tránh việc ghi đè toàn bộ tệp tin trên các tệp đã tồn tại.
*   **Kiểm tra sau thay đổi:** Thực hiện chạy thử nghiệm và kiểm tra hệ thống sau mỗi giai đoạn chỉnh sửa nhỏ.
*   **Kiểm soát phiên bản:** Không tự động thực hiện commit, không tự động tạo changelog khi thực hiện code, trừ khi có yêu cầu cụ thể từ người dùng.

---

## 3. Đề xuất Cải tiến

### 3.1. Layout mới: 2 cột sạch sẽ (Sidebar | Editor đôi)

**Hiện tại:** 2 cột (Sidebar + Editor), 5 sub-tabs lồng nhau.

**Đề xuất:** Giữ nguyên 2 cột nhưng dọn dẹp các sub-tabs lồng nhau. Không sử dụng Context Panel cột 3.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Header: Brand | [Dự án][Cấu hình][Chỉ dẫn AI][Công cụ][Nhật ký][Lưu trữ] │
├──────────┬──────────────────────────────────────────────────────────────┤
│ Sidebar  │ [Biên tập] [Kiểm chính tả] [Thông tin] [Chỉ dẫn]           │
│          ├──────────────────────────────────────────────────────────────┤
│          │                                                              │
│ [Gốc]    │ ┌───────────────────────────┬──────────────────────────────┐│
│ [Dịch]   │ │ Bản gốc (Trái - Readonly) │ Kết quả AI (Phải - Editable) ││
│ ──────── │ │                           │                              ││
│ 📄 ch1   │ │ [Wrap][Tìm kiếm]          │ [So sánh][Wrap][Lưu]         ││
│ 📄 ch2   │ │                           │                              ││
│ 📄 ch3   │ └───────────────────────────┴──────────────────────────────┘│
│          │ Token: 1,234 ký tự | 456 từ | [Sao chép] [Tải về]          │
│          │ ────────────────────────────────────────────────────────────│
│          │ Spell Log (collapsible, chỉ hiện ở tab Kiểm chính tả)      │
└──────────┴──────────────────────────────────────────────────────────────┘
```

**Bố cục 2 cột gồm:**
- **Cột trái (Sidebar):** Danh sách tệp tin động theo tab đang chọn. Ở tab "Biên tập" có 2 mini-tabs (Bản gốc / Bản dịch). Ở tab "Kiểm chính tả" có 2 mini-tabs (Chưa soát / Đã soát). **Ẩn khi ở tab "Thông tin" hoặc "Chỉ dẫn".**
- **Cột phải (Main Content):** 
  - Ở tab "Biên tập" và "Kiểm chính tả": Editor đôi song ngữ chiếm trọn chiều rộng. Dưới editor có Spell Log Panel (collapsible, chỉ hiện ở tab Kiểm chính tả).
  - Ở tab "Thông tin": Hiển thị nội dung Thông tin dự án (4 radio sub-tabs: Hướng dẫn/Mối quan hệ/Thuật ngữ/Tóm tắt). Editor đôi ẩn.
  - Ở tab "Chỉ dẫn": Hiển thị nội dung Chỉ dẫn dự án (5 prompt tabs). Editor đôi ẩn.

### 3.2. Gộp 3 editor đôi thành 1 Editor thống nhất & Giải pháp phân tách Sidebar

**Hiện tại:** Mỗi sub-tabs cũ (Nội dung gốc, Nội dung dịch, Kiểm chính tả) có một cặp textarea editor riêng biệt → Trùng lặp code.

**Đề xuất:** Chỉ sử dụng duy nhất **1 cặp editor đôi** dùng chung, thay đổi nội dung động theo tab/file được chọn.

#### A. Cấu trúc hoạt động của Editor đôi thống nhất:

*   **Ô bên trái (Anchor):** Luôn nạp **Bản gốc (Original Text)** từ `sources/` ở chế độ Readonly làm mốc đối chiếu cố định.
*   **Ô bên phải (Editable):** Nạp nội dung tương ứng của AI để người dùng chỉnh sửa:
    - **Tab Biên tập (mini-tab Bản gốc):** Nạp bản dịch thô từng phần (chunk). "Lưu" → lưu chunk.
    - **Tab Biên tập (mini-tab Bản dịch):** Nạp bản dịch hoàn chỉnh (merged file từ `translated/`). "Lưu" → lưu file dịch.
    - **Tab Kiểm chính tả (mini-tab Đã soát):** Nạp bản đã soát lỗi từ `spelling/`. "Lưu" → lưu file đã soát.
*   **Diff View:** So sánh chênh lệch giữa ô trái (Bản gốc) và ô phải (Bản đã dịch/soát).

#### B. Giải pháp Phân tách Sidebar (Tránh chồng chéo mã nguồn):

**Nguyên tắc:** 2 danh sách file (sources/ và translated/) là **2 DOM node riêng biệt**, được ẩn/hiện bằng Alpine.js. Hoàn toàn không chồng chéo mã nguồn.

**1. Tab "Biên tập" — 2 mini-tabs trong Sidebar:**

```html
<!-- Sidebar của tab Biên tập -->
<div x-data="{ sidebarTab: 'sources' }" class="sidebar">
    <!-- Mini-tab buttons -->
    <div class="flex bb b--black-10">
        <button :class="{ 'active': sidebarTab === 'sources' }"
                x-on:click="sidebarTab = 'sources'; ProjectManager.resetSelection()">
            Bản gốc
        </button>
        <button :class="{ 'active': sidebarTab === 'translated' }"
                x-on:click="sidebarTab = 'translated'; ProjectManager.resetSelection()">
            Bản dịch
        </button>
    </div>
    
    <!-- Danh sách Bản gốc (sources/) -->
    <div x-show="sidebarTab === 'sources'" x-cloak>
        <div class="flex gap-2 pa2 bb b--black-10">
            <button x-on:click="ProjectManager.uploadFile()">Tải lên</button>
            <button x-on:click="ProjectManager.showChunkConfig()">Chia chunk</button>
            <button x-on:click="TranslationWorker.translateSelected()">Dịch đã chọn</button>
        </div>
        <div id="source-file-list"><!-- Render by JS --></div>
    </div>
    
    <!-- Danh sách Bản dịch (translated/) -->
    <div x-show="sidebarTab === 'translated'" x-cloak>
        <div class="flex gap-2 pa2 bb b--black-10">
            <button x-on:click="ProjectManager.mergeFiles()">Ghép tập tin</button>
        </div>
        <div id="translated-file-list"><!-- Render by JS --></div>
    </div>
</div>
```

**2. Tab "Kiểm chính tả" — 2 mini-tabs trong Sidebar:**

```html
<!-- Sidebar của tab Kiểm chính tả -->
<div x-data="{ spellTab: 'unspellchecked' }" class="sidebar">
    <div class="flex bb b--black-10">
        <button :class="{ 'active': spellTab === 'unspellchecked' }"
                x-on:click="spellTab = 'unspellchecked'; ProjectManager.resetSelection()">
            Chưa soát
        </button>
        <button :class="{ 'active': spellTab === 'spellchecked' }"
                x-on:click="spellTab = 'spellchecked'; ProjectManager.resetSelection()">
            Đã soát
        </button>
    </div>
    
    <!-- Danh sách Chưa soát (translated/) -->
    <div x-show="spellTab === 'unspellchecked'" x-cloak>
        <div class="flex gap-2 pa2 bb b--black-10">
            <button x-on:click="TranslationWorker.spellcheckSelected()">Soát đã chọn</button>
        </div>
        <div id="unspellchecked-file-list"><!-- Render by JS --></div>
    </div>
    
    <!-- Danh sách Đã soát (spelling/) -->
    <div x-show="spellTab === 'spellchecked'" x-cloak>
        <div id="spellchecked-file-list"><!-- Render by JS --></div>
    </div>
</div>
```

**3. Tab "Thông tin" — Ẩn sidebar + editor, hiện nội dung tab:**

```html
<!-- Tab Thông tin: Ẩn sidebar, hiện nội dung thông tin dự án -->
<div x-show="activeTab === 'info'" x-cloak class="flex-auto">
    <!-- Nội dung thông tin dự án (4 radio sub-tabs) -->
    <!-- Giữ nguyên cấu trúc HTML hiện tại -->
</div>
```

**4. Tab "Chỉ dẫn" — Ẩn sidebar + editor, hiện nội dung tab:**

```html
<!-- Tab Chỉ dẫn: Ẩn sidebar, hiện nội dung prompt dự án -->
<div x-show="activeTab === 'prompt'" x-cloak class="flex-auto">
    <!-- Nội dung prompt dự án (5 prompt tabs) -->
    <!-- Giữ nguyên cấu trúc HTML hiện tại -->
</div>
```

**5. Editor Focus Lock & Click Behavior:**
- Khi người dùng toggle mini-tab, editor **KHÔNG bị xóa nội dung** đang sửa.
- Chỉ nạp nội dung mới khi người dùng **click trực tiếp vào file** trong danh sách.
- **Tại tab "Kiểm chính tả":**
  - Khi click vào file ở mini-tab `[Chưa soát]`: Ô bên trái nạp Bản gốc, ô bên phải nạp Bản dịch. Spell Log hiển thị thông báo: *"Chưa có dữ liệu soát lỗi."*
  - Khi click vào file ở mini-tab `[Đã soát]`: Ô bên trái nạp Bản gốc, ô bên phải nạp Bản đã soát lỗi. Spell Log hiển thị nội dung `{filename}_info.txt`.

**6. Reset Checkbox khi chuyển đổi:**
- Khi toggle mini-tab (hoặc chuyển đổi giữa các tab chính), gọi `ProjectManager.resetSelection()` để xóa toàn bộ checkbox.

**7. Spell Log Panel (collapsible):**
- Nằm dưới editor đôi, chỉ hiện ở tab "Kiểm chính tả".
- Hiển thị nội dung tệp tin sửa lỗi `spelling/{filename}_info.txt`.
- Sử dụng `<details><summary>` HTML5 native.

```html
<!-- Spell Log Panel (chỉ hiện ở tab Kiểm chính tả) -->
<div x-show="activeTab === 'spellcheck'" class="mt3">
    <details class="ba b--black-10 br2 bg-near-white">
        <summary class="pa2 pointer f7 fw6 gray uppercase tracked">
            Nhật ký soát lỗi (Spell Log)
        </summary>
        <div id="spell-log-content" class="pa3 f7 code" style="max-height: 200px; overflow-y: auto;">
            Chưa chọn file.
        </div>
    </details>
</div>
```

### 3.3. Rút gọn 5 sub-tabs xuống 4

**Hiện tại:** 5 sub-tabs (Nội dung gốc, Nội dung dịch, Kiểm chính tả, Thông tin, Chỉ dẫn)

**Đề xuất:** 4 sub-tabs:
- **Biên tập** (Gộp "Nội dung gốc" + "Nội dung dịch" — quản lý qua mini-tabs trong Sidebar)
- **Kiểm chính tả** (So sánh Bản gốc vs Bản soát lỗi — quản lý qua mini-tabs trong Sidebar)
- **Thông tin** (Giữ nguyên 4 radio sub-tabs: Hướng dẫn/Mối quan hệ/Thuật ngữ/Tóm tắt — ẩn sidebar + editor)
- **Chỉ dẫn** (Giữ nguyên 5 prompt tabs — ẩn sidebar + editor)

### 3.4. Tối ưu Prompt Editor (Đóng gói thành Alpine.js Component)

**Đề xuất:**
- Giữ nguyên cấu trúc HTML tĩnh do Jinja2 render.
- Khai báo một đối tượng component **`PromptEditor(isProjectScoped)`** có tính phản ứng của Alpine.js trong module `prompt-manager.js` (gắn vào `window.PromptEditor`).
- HTML liên kết trực tiếp bằng chỉ thị `x-data="PromptEditor(true)"` (cho tab chỉ dẫn dự án) và `x-data="PromptEditor(false)"` (cho tab chỉ dẫn AI hệ thống).
- Tab "Chỉ dẫn AI" (hệ thống) và tab "Chỉ dẫn" (dự án) tiếp tục được lưu trữ độc lập.

### 3.5. Phân rã main.js thành ES Modules + Alpine.js Migration

**Hiện tại:** 1 file `main.js` monolithic 3,377 dòng.

**Đề xuất:** Tách thành 6 modules + Alpine.js quản lý UI state.

| Module | Chức năng chi tiết | Ước tính |
|--------|-------------------|----------|
| `api-client.js` | Các hàm gọi API `/api/*`, xử lý lỗi chung. | ~400 dòng |
| `project-manager.js` | Quản lý dự án (CRUD), render file list, chunk, upload. | ~600 dòng |
| `editor-component.js` | Editor đôi, token estimation, auto-save, dirty state, sync scroll. | ~500 dòng |
| `prompt-manager.js` | Prompt hệ thống & dự án, thư viện prompt theo thể loại. | ~400 dòng |
| `translation-worker.js` | Luồng dịch thuật, soát lỗi, SSE progress, merge. | ~500 dòng |
| `ui-helpers.js` | Toast, Modal (merge từ modal.js), Focus Mode, stats, EPUB/OCR. | ~500 dòng |
| `main.js` | Khởi tạo, import modules, Alpine.js init. | ~200 dòng |

**Namespace Pattern (BẮT BUỘC):**
```javascript
// Trong project-manager.js
const ProjectManager = {
    loadProjects,
    selectProject,
    createProject,
    deleteProject,
    archiveProject,
    showProjectInfoModal,
    saveProjectInfo,
    renderFileList,
    resetSelection,
    uploadFile,
    showChunkConfig,
    confirmChunking,
    renameFile,
    deleteFile,
    mergeFiles,
};
window.ProjectManager = ProjectManager;
```

HTML gọi qua: `x-on:click="ProjectManager.createProject()"` hoặc `onclick="ProjectManager.createProject()"`.

### 3.6. Cải thiện Cấu hình bằng Native Accordion

**Đề xuất:** Tách nhóm cấu hình nâng cao vào thẻ `<details><summary>` HTML5.

```html
<details class="ba b--black-10 br2 bg-white pa3 shadow-1 mb3">
    <summary class="pointer f5 fw6 dark-gray">Cấu hình nâng cao (Advanced)</summary>
    <div class="pt3">
        <!-- QA Model, Thinking Level, Chunk Size, Temperature, Context Radius, API Delay -->
    </div>
</details>
```

### 3.7. Tính năng Tự động lưu bản thảo (Draft Auto-save)

*   **Cơ chế lưu trữ:**
    *   Lắng nghe `input` trên `#result-text`.
    *   Debounce **5 giây**.
    *   Key: `nt_draft_[slug]_[filename]`.
    *   **Giới hạn 3 bản nháp:** Khi bắt đầu lưu bản thảo thứ 4, tự động xóa bản thảo cũ nhất (theo timestamp), kích hoạt Toast cảnh báo.
    *   **Xóa khi lưu thành công:** Khi backend phản hồi Lưu thành công → `localStorage.removeItem(key)`.
*   **Phục hồi & Dọn dẹp nháp bỏ qua:**
    *   Khi `loadFileInEditor(filename)`: kiểm tra sự tồn tại của key nháp trong localStorage.
    *   Nếu có và nội dung nháp khác server → Toast: *"Phát hiện bản thảo lưu nháp. [Khôi phục] | [Bỏ qua]"*.
    *   Nếu người dùng chọn **Khôi phục**: Ghi đè nội dung nháp vào ô soạn thảo bên phải, đánh dấu Dirty.
    *   Nếu người dùng chọn **Bỏ qua**: Giữ nguyên nội dung từ server, đồng thời xóa vĩnh viễn tệp nháp đó khỏi bộ nhớ ngay lập tức để tránh lãng phí slot lưu trữ.

### 3.8. Chỉ báo trạng thái chưa lưu (Dirty State Indicator)

*   **Theo dõi:** `window.dirtyFiles = {}` (Key: filename, Value: boolean).
*   **Hiển thị:** `.file-tree-item.dirty::after { content: " *"; color: var(--primary); font-weight: bold; }`.
*   **Bảo vệ thoát:** `beforeunload` event nếu có thay đổi chưa lưu.

### 3.9. Sync Scroll (Đồng bộ cuộn)

*   **Cơ chế:** Cuộn editor trái → editor phải cuộn theo tỷ lệ %.
*   **Bật/tắt:** Nút "Sync" trong thanh công cụ, trạng thái lưu bằng Alpine.js `$persist`.
*   **Chống vòng lặp:** Lock Flag + setTimeout 50ms.

```javascript
// Trong editor-component.js
function setupSyncScroll(sourceEl, resultEl) {
    let isSyncing = false;
    
    sourceEl.addEventListener('scroll', () => {
        if (isSyncing || !EditorComponent.syncScrollEnabled) return;
        if (document.activeElement !== sourceEl) return;
        isSyncing = true;
        const ratio = sourceEl.scrollTop / (sourceEl.scrollHeight - sourceEl.clientHeight);
        resultEl.scrollTop = ratio * (resultEl.scrollHeight - resultEl.clientHeight);
        setTimeout(() => isSyncing = false, 50);
    });
    
    resultEl.addEventListener('scroll', () => {
        if (isSyncing || !EditorComponent.syncScrollEnabled) return;
        if (document.activeElement !== resultEl) return;
        isSyncing = true;
        const ratio = resultEl.scrollTop / (resultEl.scrollHeight - resultEl.clientHeight);
        sourceEl.scrollTop = ratio * (sourceEl.scrollHeight - sourceEl.clientHeight);
        setTimeout(() => isSyncing = false, 50);
    });
}
```

### 3.10. Alpine.js Migration Blueprint

#### A. Nạp thư viện (trong `footer.html`):

```html
<!-- Alpine.js Local Fallback -->
<script>
    // Fallback nếu CDN lỗi
    window.Alpine || document.write('<script src="{{ url_for("static", filename="js/alpine.min.js") }}"><\/script>');
</script>
<!-- Alpine.js Persist plugin (phải đặt TRƯỚC Alpine core) -->
<script defer src="https://unpkg.com/@alpinejs/persist@3.x.x/dist/cdn.min.js"></script>
<!-- Alpine.js Core -->
<script defer src="https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js"></script>
```

**Bước tải bản local:**
1. Tải `alpine.min.js` từ `https://unpkg.com/alpinejs@3.x.x/dist/cdn.min.js`.
2. Lưu vào `webui/static/js/alpine.min.js`.
3. Tải `@alpinejs/persist` từ `https://unpkg.com/@alpinejs/persist@3.x.x/dist/cdn.min.js`.
4. Lưu vào `webui/static/js/alpine-persist.min.js`.

#### B. State toàn cục cho Workspace:

```html
<!-- Tab container chính trong dự án -->
<div x-data="{ 
    activeTab: $persist('editor').as('nt_active_tab'),
    syncScroll: $persist(true).as('nt_sync_scroll')
}">
    <!-- Sub-tab buttons -->
    <button :class="{ 'active': activeTab === 'editor' }"
            x-on:click="activeTab = 'editor'">Biên tập</button>
    <button :class="{ 'active': activeTab === 'spellcheck' }"
            x-on:click="activeTab = 'spellcheck'">Kiểm chính tả</button>
    <button :class="{ 'active': activeTab === 'info' }"
            x-on:click="activeTab = 'info'">Thông tin</button>
    <button :class="{ 'active': activeTab === 'prompt' }"
            x-on:click="activeTab = 'prompt'">Chỉ dẫn</button>
    
    <!-- Tab content -->
    <div x-show="activeTab === 'editor'" x-cloak>
        <!-- Sidebar + Editor đôi -->
    </div>
    <div x-show="activeTab === 'spellcheck'" x-cloak>
        <!-- Sidebar + Editor đôi + Spell Log -->
    </div>
    <div x-show="activeTab === 'info'" x-cloak>
        <!-- Nội dung Thông tin (ẩn sidebar + editor) -->
    </div>
    <div x-show="activeTab === 'prompt'" x-cloak>
        <!-- Nội dung Chỉ dẫn (ẩn sidebar + editor) -->
    </div>
</div>
```

#### C. State cho Config Tab:

```html
<div x-data="{ activeProvider: 'gemini' }">
    <button :class="{ 'active': activeProvider === 'gemini' }"
            x-on:click="activeProvider = 'gemini'; UiHelpers.switchProvider('gemini')">Gemini</button>
    <button :class="{ 'active': activeProvider === 'openai' }"
            x-on:click="activeProvider = 'openai'; UiHelpers.switchProvider('openai')">OpenAI</button>
    
    <div x-show="activeProvider === 'gemini'">...</div>
    <div x-show="activeProvider === 'openai'">...</div>
</div>
```

#### D. Cách gọi hàm từ ES Modules:

```html
<!-- Trong HTML, gọi qua namespace -->
<button x-on:click="ProjectManager.createProject()">Tạo dự án</button>
<button x-on:click="EditorComponent.saveTranslatedFile()">Lưu</button>
<button x-on:click="TranslationWorker.translateSelected()">Dịch đã chọn</button>

<!-- Alpine.js debounce cho input -->
<textarea x-on:input.debounce.500ms="EditorComponent.updateTokenEstimate()"></textarea>
```

#### E. CSS cho Alpine.js:

```css
/* Ẩn element khi Alpine.js chưa khởi tạo (tránh FOUC) */
[x-cloak] { display: none !important; }
```

---

## 4. Implementation Plan

### Phase 1: Alpine.js Foundation + Editor Thống nhất (Core UI)

**Mục tiêu:** Thiết lập Alpine.js, gộp 3 editor đôi thành 1, tạo sidebar mini-tabs.

**Files sửa:**
- `webui/templates/partials/footer.html` — Thêm Alpine.js CDN + local fallback.
- `webui/templates/partials/tab_workspace.html` — Tái cấu trúc thành layout 2 cột với Alpine.js directives.
- `webui/static/css/style.css` — Thêm CSS cho sidebar mini-tabs, `[x-cloak]`, spell log panel.

**Files tạo mới:**
- `webui/static/js/alpine.min.js` — Bản local fallback.
- `webui/static/js/alpine-persist.min.js` — Bản local fallback cho Persist plugin.

**Bước thực hiện chi tiết:**

1. **Tải Alpine.js bản local:**
   - Tải `alpine.min.js` từ unpkg CDN.
   - Tải `@alpinejs/persist` từ unpkg CDN.
   - Lưu vào `webui/static/js/`.

2. **Thêm Alpine.js vào `footer.html`:**
   - Thêm script tags (local fallback + CDN) trước `modal.js` và `main.js`.
   - Pin version `3.14.x`.

3. **Tái cấu trúc `tab_workspace.html`:**
   - Bọc toàn bộ tab content trong `<div x-data="{ activeTab: 'editor' }">`.
   - Tạo 4 sub-tab buttons với `x-on:click` và `:class`.
   - Tạo 4 tab content divs với `x-show` và `x-cloak`.
   - Xóa 2 editor đôi trùng lặp.
   - Chỉ giữ 1 editor đôi duy nhất với `id="source-text"` và `id="result-text"`.

4. **Tạo Sidebar mini-tabs cho tab "Biên tập":**
   - Bọc sidebar trong `<div x-data="{ sidebarTab: 'sources' }">`.
   - Tạo 2 mini-tab buttons (Bản gốc / Bản dịch).
   - Tạo 2 divs chứa danh sách file với `x-show`.
   - Thêm action buttons tương ứng.

5. **Tạo Sidebar mini-tabs cho tab "Kiểm chính tả":**
   - Bọc sidebar trong `<div x-data="{ spellTab: 'unspellchecked' }">`.
   - Tạo 2 mini-tab buttons (Chưa soát / Đã soát).
   - Tạo 2 divs chứa danh sách file với `x-show`.
   - Thêm Spell Log Panel (collapsible `<details>`) dưới editor.

6. **Ẩn sidebar + editor khi ở tab "Thông tin" và "Chỉ dẫn":**
   - Sử dụng `x-show` để ẩn sidebar và editor khi `activeTab === 'info'` hoặc `activeTab === 'prompt'`.
   - Nội dung tab "Thông tin" và "Chỉ dẫn" chiếm toàn bộ chiều rộng.

7. **Triển khai Editor Focus Lock:**
   - Khi toggle mini-tab, KHÔNG xóa nội dung editor.
   - Chỉ nạp nội dung khi click trực tiếp vào file.

8. **Triển khai Sync Scroll:**
   - Thêm nút "Sync" vào thanh công cụ editor.
   - Dùng Alpine.js `$persist` cho trạng thái bật/tắt.
   - Implement scroll listener trong `editor-component.js`.

**Effort:** 2-3 ngày

### Phase 2: Phân rã main.js thành ES Modules + Alpine.js Migration (Architecture)

**Mục tiêu:** Tách `main.js` monolith thành 6 modules, migration từ inline JS sang Alpine.js directives.

**Files tạo mới:**
- `webui/static/js/api-client.js`
- `webui/static/js/project-manager.js`
- `webui/static/js/editor-component.js`
- `webui/static/js/prompt-manager.js`
- `webui/static/js/translation-worker.js`
- `webui/static/js/ui-helpers.js`

**Files sửa:**
- `webui/templates/partials/footer.html` — Đổi script tags sang module format.
- `webui/templates/partials/tab_workspace.html` — Migration inline events sang Alpine.js.
- `webui/templates/partials/tab_config.html` — Migration provider switching sang Alpine.js.
- `webui/templates/partials/header.html` — Migration stats pill sang Alpine.js.
- `webui/templates/partials/modals.html` — Migration modal toggling sang Alpine.js.
- `webui/static/js/main.js` — Rút gọn làm entry-point.

**Files xóa:**
- `webui/static/js/modal.js` — Merge vào `ui-helpers.js`.

**Bước thực hiện chi tiết:**

1. **Tạo `api-client.js` (~400 dòng):**
   - Di chuyển: `fetchJson()`, `loadApiKeys()`, `saveApiKeys()`, `loadModels()`, `loadAppConfig()`, `saveAppConfig()`, `loadStats()`, `loadArchiveList()`, `loadLogList()`, `clearCache()`.
   - Namespace: `window.ApiClient = { ... }`.

2. **Tạo `project-manager.js` (~600 dòng):**
   - Di chuyển: `loadProjects()`, `selectProject()`, `showCreateProjectDialog()`, `createProject()`, `deleteProject()`, `archiveProject()`, `showProjectInfoModal()`, `saveProjectInfo()`, `renderProjectSources()`, `renderProjectTranslated()`, `selectFile()`, `uploadProjectFile()`, `renameProjectFile()`, `deleteProjectFile()`, `moveProjectFile()`, `showChunkConfig()`, `confirmChunking()`.
   - Thêm mới: `resetSelection()` (xóa checkbox khi toggle mini-tab).
   - Namespace: `window.ProjectManager = { ... }`.

3. **Tạo `editor-component.js` (~500 dòng):**
   - Di chuyển: `loadFileInEditor()`, `saveChunkTranslation()`, `saveTranslatedFile()`, `saveSpellcheckResult()`, `updateTokenEstimate()`, `updateTranslatedTokenEstimate()`, `toggleWordWrap()`, `findInText()`, `showDiffView()`, `copyResult()`, `downloadResult()`, `copyTranslatedResult()`, `downloadTranslatedResult()`, `retranslateFile()`.
   - Thêm mới: Auto-save (debounce 5s, localStorage, limit 3), Dirty State Indicator, Sync Scroll, Spell Log loading.
   - Namespace: `window.EditorComponent = { ... }`.

4. **Tạo `prompt-manager.js` (~400 dòng):**
   - Di chuyển: `loadGenres()`, `selectGenre()`, `createGenre()`, `saveGenre()`, `deleteGenre()`, `cloneGenre()`, `useGenre()`, `loadProjectPrompts()`, `saveProjectPrompts()`, `resetProjectPrompts()`, `importPromptFromLibrary()`, `aiGenerateContent()`, `saveGuidelineField()`.
   - Thêm mới: Alpine component `PromptEditor(isProjectScoped)` và gán vào `window.PromptEditor`.
   - Namespace: `window.PromptManager = { ... }`.

5. **Tạo `translation-worker.js` (~500 dòng):**
   - Di chuyển: `startTranslation()`, `translateSelectedInProject()`, `retranslateFile()`, `spellcheckSelectedInProject()`, `runSpellcheck()`, `handleTranslationSSE()`, `updateProgress()`, `closeProgress()`, `mergeTranslatedFiles()`.
   - Namespace: `window.TranslationWorker = { ... }`.

6. **Tạo `ui-helpers.js` (~500 dòng):**
   - Di chuyển: `showToast()`, `initTabs()` (chuyển thành Alpine.js), `restoreAppState()` (chuyển thành Alpine.js `$persist`), `toggleFocusMode()`, `applyFocusMode()`, `initFocusMode()`, `ModalManager` (merge từ `modal.js`), `switchProvider()`, `initProvider()`, `saveOpenAIConfig()`, `loadStats()`, `restartServer()`, `runEpubConverter()`, `runOcr()`, `toggleEpubForm()`, `markModel()`, `onModelChange()`.
   - Namespace: `window.UiHelpers = { ... }`.

7. **Rút gọn `main.js` (~200 dòng):**
   - Import tất cả modules.
   - `DOMContentLoaded` → gọi init functions.
   - `beforeunload` → dirty state check.
   - Temperature slider event.

8. **Migration inline events sang Alpine.js:**
   - **`tab_workspace.html`:**
     - `onclick="switchProjectTab('workspace')"` → `x-on:click="activeTab = 'editor'"`
     - `onclick="selectAllProjectFiles()"` → `x-on:click="ProjectManager.selectAllSources()"`
     - `onclick="translateSelectedInProject()"` → `x-on:click="TranslationWorker.translateSelected()"`
     - `onclick="startTranslation()"` → `x-on:click="TranslationWorker.startTranslation()"`
     - `onclick="saveChunkTranslation()"` → `x-on:click="EditorComponent.saveChunkTranslation()"`
     - `onclick="copyResult()"` → `x-on:click="EditorComponent.copyResult()"`
     - `onclick="downloadResult()"` → `x-on:click="EditorComponent.downloadResult()"`
     - `onclick="toggleWordWrap('source-text')"` → `x-on:click="EditorComponent.toggleWordWrap('source-text')"`
     - `onclick="findInText('source-text')"` → `x-on:click="EditorComponent.findInText('source-text')"`
     - `onclick="showDiffView(...)"` → `x-on:click="EditorComponent.showDiffView('source-text', 'result-text')"`
     - `oninput="updateTokenEstimate()"` → `x-on:input.debounce.500ms="EditorComponent.updateTokenEstimate()"`
   - **`tab_config.html`:**
     - `onclick="switchProvider('gemini')"` → `x-on:click="activeProvider = 'gemini'; UiHelpers.switchProvider('gemini')"`
     - `onclick="saveAppConfig()"` → `x-on:click="ApiClient.saveAppConfig()"`
     - `onclick="saveApiKeys()"` → `x-on:click="ApiClient.saveApiKeys()"`
     - `onclick="clearCache()"` → `x-on:click="ApiClient.clearCache()"`
   - **`header.html`:**
     - `onclick="toggleFocusMode()"` → `x-on:click="UiHelpers.toggleFocusMode()"`
     - `onclick="restartServer()"` → `x-on:click="UiHelpers.restartServer()"`
   - **`modals.html`:**
     - `onclick="hideChunkConfig()"` → `x-on:click="UiHelpers.hideChunkConfig()"`
     - `onclick="confirmChunking()"` → `x-on:click="ProjectManager.confirmChunking()"`
     - `onclick="closeProgress()"` → `x-on:click="TranslationWorker.closeProgress()"`
     - `onclick="hideProjectInfoModal()"` → `x-on:click="UiHelpers.hideProjectInfoModal()"`
     - `onclick="saveProjectInfo()"` → `x-on:click="ProjectManager.saveProjectInfo()"`
   - **`footer.html`:**
     - `onclick="showCreateProjectDialog()"` → `x-on:click="UiHelpers.showCreateProjectDialog()"`
     - `onclick="createGenre(e)"` → `x-on:click="PromptManager.createGenre()"`
   - **`tab_prompts.html`:**
     - `onclick="saveGenre()"` → `x-on:click="PromptManager.saveGenre()"`
     - `onclick="deleteGenre()"` → `x-on:click="PromptManager.deleteGenre()"`
     - `onclick="cloneGenre()"` → `x-on:click="PromptManager.cloneGenre()"`
     - `onclick="useGenre()"` → `x-on:click="PromptManager.useGenre()"`
   - **`tab_archive.html`:**
     - `onclick="loadArchiveList()"` → `x-on:click="ApiClient.loadArchiveList()"`
   - **`tab_logs.html`:**
     - `onclick="deleteSelectedLogs()"` → `x-on:click="UiHelpers.deleteSelectedLogs()"`
     - `onclick="deleteCurrentLog()"` → `x-on:click="UiHelpers.deleteCurrentLog()"`
   - **`tab_plugins.html`:**
     - `onclick="runEpubConverter()"` → `x-on:click="UiHelpers.runEpubConverter()"`
     - `onclick="runOcr()"` → `x-on:click="UiHelpers.runOcr()"`
     - `onclick="toggleEpubForm()"` → `x-on:click="UiHelpers.toggleEpubForm()"`

9. **Xóa `modal.js`:**
   - Merge toàn bộ `ModalManager` vào `ui-helpers.js`.
   - Xóa file `modal.js`.
   - Cập nhật `footer.html` để bỏ script tag `modal.js`.

10. **Cập nhật `footer.html`:**
    - Thêm Alpine.js CDN + local fallback.
    - Đổi `<script src="main.js">` thành `<script type="module" src="main.js">`.
    - Bỏ script tag `modal.js`.

**Effort:** 3-4 ngày

### Phase 3: Config Accordion & Prompt Manager Integration (UX & Features)

**Mục tiêu:** Cải thiện Config tab, thống nhất Prompt Manager.

**Files sửa:**
- `webui/templates/partials/tab_config.html` — Triển khai `<details>` cho cấu hình nâng cao + Alpine.js provider switching.
- `webui/templates/partials/tab_prompts.html` — Tích hợp `prompt-manager.js` Alpine component.

**Bước thực hiện chi tiết:**

1. **Config Accordion:**
   - Gom input nâng cao (QA Model, Thinking Level, Chunk Size, Temperature, Context Radius, API Delay, Cache) vào `<details>`.
   - Các trường cơ bản (Provider, API Key, Model) luôn hiển thị.

2. **Alpine.js Provider Switching:**
   - Bọc provider cards trong `<div x-data="{ activeProvider: 'gemini' }">`.
   - Dùng `x-show` để hiển thị Gemini/OpenAI sections.
   - Dùng `:class` để đánh dấu active provider card.

3. **Prompt Manager Alpine Component:**
   - Triển khai `PromptEditor(isProjectScoped)` trong `prompt-manager.js`.
   - Gắn vào `window.PromptEditor`.
   - Dùng `x-data="PromptEditor(true)"` cho tab "Chỉ dẫn" dự án.
   - Dùng `x-data="PromptEditor(false)"` cho tab "Chỉ dẫn AI" hệ thống.

**Effort:** 1-2 ngày

### Phase 4: Unit Tests & Polish

**Mục tiêu:** Viết tests cho ES modules, dọn dẹp, kiểm tra.

**Files tạo mới:**
- `tests/unit/test_api_client.js`
- `tests/unit/test_project_manager.js`
- `tests/unit/test_editor_component.js`
- `tests/unit/test_prompt_manager.js`
- `tests/unit/test_translation_worker.js`
- `tests/unit/test_ui_helpers.js`

**Files sửa:**
- `webui/static/css/style.css` — Tối ưu CSS, dọn class dư thừa.
- `webui/templates/partials/modals.html` — Chuẩn hóa modal patterns.
- `webui/templates/partials/footer.html` — Hoàn thiện script loading order.

**Bước thực hiện chi tiết:**

1. **Viết unit tests cho mỗi ES module:**
   - Test API calls (mock fetch).
   - Test project CRUD operations.
   - Test editor functions (token estimation, word wrap, diff view).
   - Test prompt management (load, save, delete, clone).
   - Test translation worker (SSE handling, progress updates).
   - Test UI helpers (toast, modal, focus mode).

2. **Dọn CSS unused:**
   - Kiểm tra Tachyons classes không còn dùng.
   - Xóa CSS trùng lặp.

3. **Kiểm tra rò rỉ bộ nhớ:**
   - SSE connections có được đóng đúng không.
   - Event listeners có bị leak không.

4. **Smoke check toàn bộ functionality:**
   - Test tất cả tabs và mini-tabs.
   - Test dịch thuật, soát lỗi, prompt editing.
   - Test auto-save, dirty state, sync scroll.

5. **Viết tài liệu bàn giao:**
   - Kiến trúc JS module mới.
   - Cách sử dụng Alpine.js trong dự án.
   - Namespace pattern và cách gọi hàm.

**Effort:** 2-3 ngày

---

## 5. Ước tính Tổng thể

| Phase | Effort | Ưu tiên | Dependencies |
|-------|--------|---------|--------------|
| 1: Alpine.js + Editor thống nhất | 2-3 ngày | CAO | None |
| 2: Tách JS + Alpine.js Migration | 3-4 ngày | CAO | Phase 1 |
| 3: Config & Prompts | 1-2 ngày | TRUNG BÌNH | Phase 1 |
| 4: Unit Tests & Polish | 2-3 ngày | TRUNG BÌNH | Phase 1-3 |
| **Tổng** | **8-12 ngày** | | |

---

## 6. Files sẽ sửa đổi

### Sửa đổi:
```
webui/templates/partials/tab_workspace.html  ← Layout 2 cột, Alpine.js directives, gộp editor
webui/templates/partials/tab_config.html     ← Alpine.js provider switching, details/summary
webui/templates/partials/tab_prompts.html    ← Tích hợp PromptEditor Alpine component
webui/templates/partials/header.html         ← Alpine.js directives
webui/templates/partials/modals.html         ← Alpine.js directives
webui/templates/partials/footer.html         ← Alpine.js CDN + local fallback + module scripts
webui/static/css/style.css                   ← CSS cho mini-tabs, x-cloak, spell log
webui/static/js/main.js                      ← Rút gọn entry-point
```

### Tạo mới:
```
webui/static/js/alpine.min.js               ← Local fallback cho Alpine.js Core
webui/static/js/alpine-persist.min.js        ← Local fallback cho Alpine.js Persist
webui/static/js/api-client.js                ← ~400 dòng
webui/static/js/project-manager.js           ← ~600 dòng
webui/static/js/editor-component.js          ← ~500 dòng
webui/static/js/prompt-manager.js            ← ~400 dòng
webui/static/js/translation-worker.js        ← ~500 dòng
webui/static/js/ui-helpers.js                ← ~500 dòng
tests/unit/test_api_client.js                ← Unit tests
tests/unit/test_project_manager.js           ← Unit tests
tests/unit/test_editor_component.js          ← Unit tests
tests/unit/test_prompt_manager.js            ← Unit tests
tests/unit/test_translation_worker.js        ← Unit tests
tests/unit/test_ui_helpers.js                ← Unit tests
```

### Xóa:
```
webui/static/js/modal.js                     ← Đã merge vào ui-helpers.js
```

### Giữ nguyên:
```
webui/templates/partials/tab_archive.html    ← Chỉ đổi onclick → Alpine.js
webui/templates/partials/tab_logs.html       ← Chỉ đổi onclick → Alpine.js
webui/templates/partials/tab_plugins.html    ← Chỉ đổi onclick → Alpine.js
webui/templates/index.html                   ← Không đổi
Tất cả backend routes                        ← Không đổi
```

---

## 7. Success Metrics

| Metric | Hiện tại | Mục tiêu |
|--------|----------|----------|
| Sub-tabs trong dự án | 5 | 4 |
| Editor đôi trùng lặp | 3 | 1 |
| Lines trong main.js | 3,377 | < 300 |
| Clicks để dịch 1 file | 3-4 | 1-2 |
| Files JS | 2 (main.js + modal.js) | 8 |
| Bug fix phải sửa N chỗ | 3 | 1 |
| Inline onclick events | ~50+ | 0 (Alpine.js) |
| Unit test coverage | 0% | > 60% |

---

## 8. Rủi ro & Mitigation

| Rủi ro | Mitigation |
|--------|------------|
| Alpine.js CDN mất mạng | Local fallback (static/js/alpine.min.js) |
| Editor thống nhất phức tạp | Fallback: giữ 2 editor (workspace + spellcheck) |
| Tách JS có thể break functionality | Tách tuần tự, test sau mỗi bước |
| localStorage đầy khi auto-save | Giới hạn 3 bản nháp, tự động xóa cũ nhất |
| FOUC (Flash of Unstyled Content) | Dùng `[x-cloak]` CSS rule |
| modal.js merge gây lỗi | Test kỹ ModalManager sau khi merge |

---

## 9. Không nằm trong phạm vi

- ❌ Responsive/mobile design (ưu tiên thấp)
- ❌ Thay thế Tachyons bằng framework khác
- ❌ Rewrite backend routes
- ❌ Dark mode
- ❌ Accessibility (a11y) improvements
- ❌ Keyboard shortcuts
- ❌ Loading indicators

---

## 10. Quyết định đã chốt (Q&A)

| Tính năng | Quyết định | Chi tiết |
|-----------|-----------|----------|
| Context Panel (cột phải) | **Không** | Không sử dụng cột thứ 3. "Thông tin" và "Chỉ dẫn" giữ nguyên vị trí sub-tabs. |
| Quick Glossary Panel | **Không** | Đã loại bỏ. Bộ thuật ngữ được gửi tự động cho AI. |
| Draft Auto-save | **Có** — debounce 5s, giới hạn 3 bản nháp | localStorage, key `nt_draft_[slug]_[filename]`, tự động xóa bản cũ nhất khi vượt quá. Không kiểm tra kích thước. |
| Dirty State Indicator | **Có** | Dấu `*` cạnh file chưa lưu + cảnh báo `beforeunload`. |
| Sync Scroll | **Có** | Editor trái/phải cuộn đồng bộ + nút bật/tắt + Alpine.js `$persist`. |
| Config Accordion | **Có** | HTML5 `<details>/<summary>` cho cấu hình nâng cao. |
| Sub-tabs Thông tin | **Giữ nguyên** | 4 radio sub-tabs (Hướng dẫn/Mối quan hệ/Thuật ngữ/Tóm tắt). Ẩn sidebar + editor khi ở tab này. |
| Sub-tabs Chỉ dẫn | **Giữ nguyên** | 5 prompt tabs. Ẩn sidebar + editor khi ở tab này. |
| Prompt hệ thống vs dự án | **Giữ nguyên 2 nơi riêng biệt** | Tab "Chỉ dẫn AI" (hệ thống) + tab "Chỉ dẫn" (dự án). |
| Focus Mode | **Giữ nguyên** | Nút header + localStorage persistence. |
| Alpine.js | **Có** — version 3.14.x (latest stable) | Quản lý UI state (tab switching, sidebar toggle, modal, accordion). CDN + local fallback. |
| Editor Focus Lock | **Có** | Khi toggle mini-tab, editor KHÔNG bị xóa nội dung đang sửa. |
| Spell Log Panel | **Có** — collapsible dưới editor | `<details><summary>`, chỉ hiện ở tab Kiểm chính tả. |
| Namespace Pattern | **Có** | Mỗi module export 1 namespace object vào `window`. |
| modal.js | **Merge vào ui-helpers.js** | Xóa file modal.js riêng, merge ModalManager vào ui-helpers.js. |
| Unit tests | **Có** | Viết tests cho tất cả ES modules mới. |
| Keyboard shortcuts | **Không** | Không cần. |
| Loading indicators | **Không** | Không cần. |
| Sidebar khi ở Thông tin/Chỉ dẫn | **Ẩn sidebar** | Nội dung tab chiếm toàn bộ chiều rộng. |

---

## APPROVAL

- [ ] Đồng ý kế hoạch
- [ ] Cần điều chỉnh: _______________
- [ ] Không thực hiện
