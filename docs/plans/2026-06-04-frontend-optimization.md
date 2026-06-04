# Kế Hoạch: Tinh giản & Tối ưu Frontend (v7.4.0)

> **Ngày tạo:** 2026-06-04
> **Trạng thái:** CHỜ DUYỆT
> **Phạm vi:** HTML templates, JavaScript modules, CSS

---

## Tổng quan

Rà soát toàn bộ frontend code phát hiện:
- **8 lỗi nghiêm trọng** (broken features)
- **11 chỗ trùng lặp** (~400 dòng redundant)
- **200+ dòng dead code** (JS + CSS không dùng)
- **10 cơ hội tối ưu** (giảm ~30% codebase)

---

## 1. Lỗi nghiêm trọng (Fix ngay)

### 1.1. Ctrl+S save — targets element sai
- **File:** `main.js:146-152`
- **Vấn đề:** `#result-text` và `#spell-result-text` không tồn tại. Đúng là `#pm-result-text` và `#pm-spell-result-text`
- **Hậu quả:** Ctrl+S save hoàn toàn không hoạt động

### 1.2. AutoSave — bind vào element sai
- **File:** `project-manager.js:14`
- **Vấn đề:** `AutoSave.init()` attach vào `#result-text` (không tồn tại)
- **Hậu quả:** Auto-save không bao giờ kích hoạt

### 1.3. PromptManager.loadProjectPrompts — ghi vào ID sai
- **File:** `prompt-manager.js:186-191`
- **Vấn đề:** Ghi vào `#proj-prompt-main` nhưng HTML dùng `#pm-proj-prompt-main`
- **Hậu quả:** Textarea prompt dự án luôn trống

### 1.4. saveProjectPrompts — đọc từ ID sai
- **File:** `prompt-manager.js:221-225`
- **Vấn đề:** Đọc từ `#proj-prompt-main` (sai), nên `#pm-proj-prompt-main`
- **Hậu quả:** Lưu prompt gửi giá trị rỗng

### 1.5. deleteGenre — reference element không tồn tại
- **File:** `prompt-manager.js:170`
- **Vấn đề:** `getElementById('genre-empty-state')` trả null → TypeError
- **Hậu quả:** Xóa thể loại throw exception

### 1.6. switchProvider — dùng CSS class sai
- **File:** `ui-helpers.js:179-185`
- **Vấn đề:** JS dùng `b--light-gray` nhưng HTML dùng `b--black-10` cho inactive
- **Hậu quả:** Visual glitch khi chuyển provider

### 1.7. main.js:227-249 — bind vào button ID không tồn tại
- **File:** `main.js:227-249`
- **Vấn đề:** `#translate-btn`, `#btn-copy-result`, `#download-btn`... đều không tồn tại (remnants old workspace)
- **Hậu quả:** Dead event listeners, có thể throw silent errors

### 1.8. prompt-library-select — populate element sai
- **File:** `prompt-manager.js:200-212`
- **Vấn đề:** Populate `#prompt-library-select` nhưng chỉ `#pm-prompt-library-select` tồn tại
- **Hậu quả:** Dropdown prompt library không bao giờ có options

---

## 2. Code trùng lặp

### 2.1. SVG Icons — ~40 bản copy inline
- **Vị trí:** `tab_projects.html` (wrap ×6, search ×6, upload ×3, delete ×2, chunk ×2, translate ×2...)
- **Giải pháp:** Sử dụng `Icons` object đã có trong `project-manager.js`, render qua `innerHTML`

### 2.2. Editor tab + Spellcheck tab — ~160 dòng HTML trùng
- **Vị trí:** `tab_projects.html:82-157` vs `tab_projects.html:162-240`
- **Giải pháp:** Tạo Jinja2 macro `editor_tab(prefix, labels)`

### 2.3. Column toggle map — định nghĩa 2 lần
- **Vị trí:** `project-manager.js:361-368` và `project-manager.js:447-454`
- **Giải pháp:** Module-level constant

### 2.4. loadProjectFile / loadPmProjectFile — logic giống hệt
- **Vị trí:** `editor-component.js:8-48` vs `editor-component.js:79-117`
- **Giải pháp:** `_loadFilePair(prefix, filename)` generic function

### 2.5. loadSpellcheckFile / loadPmSpellcheckFile — logic giống hệt
- **Vị trí:** `editor-component.js:51-77` vs `editor-component.js:120-145`
- **Giải pháp:** Tương tự #2.4

### 2.6. renderFileList3Col / renderPmFileList — structure giống hệt
- **Vị trí:** `project-manager.js:685-726` vs `project-manager.js:870-906`
- **Giải pháp:** `_renderFileItem(file, options)` helper

### 2.7. renderSpellcheckFileList3Col / renderPmSpellcheckFileList — trùng
- **Vị trí:** `project-manager.js:728-763` vs `project-manager.js:908-941`
- **Giải pháp:** Tương tự #2.6

### 2.8. 50 global wrapper functions
- **Vị trí:** `main.js:278-328`
- **Giải pháp:** Dùng `ModuleName.method()` trực tiếp trong HTML onclick

### 2.9. showPmInfoTab / showPmPromptTab — cùng pattern
- **Vị trí:** `project-manager.js:343-357` vs `project-manager.js:550-564`
- **Giải pháp:** `showPanelGroup(panelIds, activeId)` utility

### 2.10. toggleProjectFile / toggleTranslatedFile — cùng pattern
- **Vị trí:** `project-manager.js:468-472` vs `project-manager.js:474-478`
- **Giải pháp:** `_toggleFileSelection(set, filename, checked)`

### 2.11. Clipboard API không nhất quán
- **Vị trí:** `editor-component.js:345` (navigator.clipboard) vs `editor-component.js:364` (execCommand)
- **Giải pháp:** Dùng `navigator.clipboard.writeText()` cho cả hai

---

## 3. Dead Code

### 3.1. JS functions cho element không tồn tại

| Function | File | Bị xóa vì |
|----------|------|-----------|
| `runRetranslate()` | `main.js:330` | Reference `#result-text` (không có) |
| `runCorrection()` | `main.js:334` | Reference `#result-text` (không có) |
| `runBoth()` | `main.js:338` | Empty body |
| `copyDoneResult()` | `main.js:339` | Empty body |
| `downloadDoneResult()` | `main.js:340` | Empty body |
| `renderFileList3Col()` | `project-manager.js:685-726` | Target `#file-list-3col` (không có) |
| `renderSpellcheckFileList3Col()` | `project-manager.js:728-763` | Target `#spellcheck-file-list-3col` (không có) |

### 3.2. Dead DOMContentLoaded bindings
- `main.js:198-249` — bind vào ~10 button ID không tồn tại (remnants old workspace)

### 3.3. Dead CSS (~130 dòng)

| Selector | File | Lý do |
|----------|------|-------|
| `#project-tab-main:checked` (6 selectors) | `style.css:140-156` | Radio buttons không tồn tại |
| `#project-info-tab-summary:checked` (3 selectors) | `style.css:158-170` | Radio buttons không tồn tại |
| `#info-tab-style-guide:checked` (4 selectors) | `style.css:173-187` | Radio buttons không tồn tại |
| `#system-tab-retranslate/:checked` | `style.css:200-201` | Radio buttons không tồn tại |
| `.nt-editor-pane` | `style.css:439-443` | Không dùng |
| `.nt-ptab-content` | `style.css:39-41` | Old sub-tab system |
| `.tab-btn` | `style.css:35-36` | Old workspace tabs |
| `.sidebar-item` | `style.css:49-51` | Replaced by `.file-item-compact` |
| `.editor-container` | `style.css:54` | Replaced by `.workspace-layout-3col` |
| `.editor-pane` | `style.css:55` | Replaced by `.editor-pane-3col` |
| `.editor-textarea` / `.editor-textarea-fill` | `style.css:56-57` | Không dùng |
| `.file-list-box` | `style.css:60-66` | Replaced by `.file-list-sidebar` |
| `.sticky-top` | `style.css:69-73` | Không dùng |
| `.info-panel` / `.info-textarea` | `style.css:81-89` | Không dùng |
| `.col-checkbox` | `style.css:97-99` | Không dùng |
| `.project-card-progress-bar` | `style.css:670-674` | Không dùng |
| `.nt-btn-secondary` | `style.css:315-316` | Không dùng |
| `.nt-btn-lg` | `style.css:324` | Không dùng |
| `.op-20` | `style.css:116` | Không dùng |

### 3.4. Unused JS variables
- `main.js:7` — `window.allFiles` declared but never populated or read

---

## 4. Tối ưu

### 4.1. Inline styles → CSS classes
| Inline style | Vị trí | CSS class đề xuất |
|-------------|--------|-------------------|
| `height: calc(100vh - 80px)` | `tab_projects.html:5` | `.projects-list-view` |
| `display: none` | `tab_projects.html:54` | Dùng `.dn` (đã có) |
| `width:14px;height:14px` | `tab_projects.html` ×12 | `.icon-sm svg` |
| `height:120px;resize:none` | `tab_config.html:29` | `.api-keys-textarea` |
| `min-height:340px;resize:none` | `tab_prompts.html` ×5 | `.prompt-textarea` |
| `background:#ffe4e4;border:1px solid #f5c6c6` | `tab_projects.html:292` | `.btn-reset-custom` |

### 4.2. Modal z-index chuẩn hóa
| Modal | Hiện tại | Đề xuất |
|-------|----------|---------|
| `chunk-config-modal` | `9999` (inline) | `var(--z-modal)` |
| `translation-progress-modal` | `10000` (inline) | `var(--z-modal)` |
| `project-info-modal` | `9998` (inline) | `var(--z-modal)` |
| `showConfirm` overlay | `99999` (JS) | `var(--z-modal-top)` |

### 4.3. Button styling — chọn 1 hệ thống
- Hiện tại: Tachyons overrides + `.nt-btn` system (trùng lặp)
- Đề xuất: Chuẩn hóa theo `.nt-btn` system, xóa Tachyons button overrides

### 4.4. Consolidate modals vào 1 file
- Hiện tại: `modals.html` (3 modals) + `footer.html` (2 modals)
- Đề xuất: Tất cả modals vào `modals.html`

---

## 5. Thứ tự thực thi

### Phase 1: Fix 8 lỗi nghiêm trọng (ưu tiên cao)
1. Fix element IDs trong `main.js` (Ctrl+S, DOMContentLoaded bindings)
2. Fix element IDs trong `prompt-manager.js` (loadProjectPrompts, saveProjectPrompts, deleteGenre)
3. Fix CSS classes trong `ui-helpers.js` (switchProvider)
4. Xóa dead DOMContentLoaded bindings trong `main.js`

### Phase 2: Xóa dead code
1. Xóa 7 dead JS functions
2. Xóa ~130 dòng dead CSS
3. Xóa unused JS variables

### Phase 3: Consolidate duplicates
1. Extract inline SVGs → `Icons` object + render helper
2. Consolidate `loadProjectFile`/`loadPmProjectFile` → generic
3. Consolidate `renderFileList`/`renderPmFileList` → generic
4. Consolidate column toggle map → module constant
5. Replace 50 global wrappers → direct `Module.method()` calls

### Phase 4: Optimize
1. Inline styles → CSS classes
2. Modal z-index standardization
3. Button styling consolidation
4. Modal file consolidation

---

## 6. Ước lượng

| Phase | Thời gian | Giảm code |
|-------|-----------|-----------|
| Phase 1: Fix bugs | ~1h | 0 dòng |
| Phase 2: Dead code | ~30p | -330 dòng |
| Phase 3: Consolidate | ~2h | -300 dòng |
| Phase 4: Optimize | ~1h | -50 dòng |
| **Tổng** | **~4.5h** | **-680 dòng** (~30% codebase) |
