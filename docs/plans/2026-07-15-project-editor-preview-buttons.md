# Kế hoạch triển khai nút Preview cho 2 editor trong mục Biên tập dự án

**Ngày:** 2026-07-15  
**Trạng thái:** Đã review và chốt — sẵn sàng triển khai  
**Phạm vi:** Frontend only. Không đụng backend.  
**Mục tiêu:** Thêm 2 nút `Preview` cho 2 editor trong `Biên tập dự án`, đặt bên trái nút `Wrap`, bấm vào tự nhận diện và render nội dung theo `Markdown` hoặc `HTML`.

---

## 0. Nguyên nhân lỗi hiện tại (Báo cáo & Phân tích)

Trong quá trình triển khai sơ khởi kế hoạch này, hệ thống gặp phải 2 lỗi nghiêm trọng ở Console và các nút không phản hồi:

### 0.1. Lỗi `Uncaught SyntaxError: redeclaration of const AutoSave`
* **Nguyên nhân gốc rễ**: File [footer.html](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/footer.html) đang load [project-manager.js](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/static/js/project-manager.js) hai lần:
  1. Dòng 15: `<script src="{{ url_for('static', filename='js/project-manager.js') }}?v={{ app_version }}"></script>` (load dạng non-module).
  2. Dòng 216: `<script src="{{ url_for('static', filename='js/project-manager.js') }}?v={{ app_version }}-f"></script>` (load trong nhóm ES Modules / Namespace Pattern).
* **Ảnh hưởng**: Trình duyệt báo lỗi cú pháp khi định nghĩa lại hằng số `AutoSave` (dòng 8 trong [project-manager.js](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/static/js/project-manager.js)), làm cho toàn bộ file `project-manager.js` bị dừng thực thi, vô hiệu hoá các chức năng của trình quản lý dự án.
* **Giải pháp**: Xoá dòng load trùng lặp ở dòng 15 trong [footer.html](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/footer.html).

### 0.2. Lỗi `Uncaught SyntaxError: invalid escape sequence`
* **Nguyên nhân gốc rễ**: Các thuộc tính `onclick` của các nút trên toolbar trong [tab_projects.html](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/tab_projects.html) sử dụng ký tự escape `\` cho dấu nháy đơn không hợp lệ bên trong chuỗi thuộc tính HTML:
  * Ví dụ: `onclick="EditorComponent.openPreview(\'pm-result-text\', { label: \'Bản dịch\' })"`
  * Trình duyệt không parse dấu `\` làm ký tự escape cho nháy đơn bên trong dấu nháy kép của attribute HTML. Nó chuyển trực tiếp chuỗi này sang JavaScript engine thành `EditorComponent.openPreview('pm-result-text', { label: '\Bản dịch' })`.
  * Vì `\B` là một escape sequence không hợp lệ trong JS, trình duyệt ném ra lỗi `Uncaught SyntaxError: invalid escape sequence`.
* **Giải pháp**: Loại bỏ toàn bộ ký tự escape `\` trong thuộc tính `onclick` của [tab_projects.html](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/tab_projects.html). Sử dụng cặp nháy kép `"..."` bao bọc bên ngoài và nháy đơn `'...'` bên trong một cách bình thường:
  * Ví dụ: `onclick="EditorComponent.openPreview('pm-result-text', { label: 'Bản dịch' })"`

### 0.3. Chuyển đổi nút "So sánh" và "Preview" thành Biểu tượng (Icon)
* **Yêu cầu**: Thay thế các nút dạng text `So sánh` và `Preview` bằng các nút chỉ có biểu tượng SVG đơn giản, đồng bộ phong cách với các nút `Wrap` và `Tìm kiếm` có sẵn.
* **Thiết kế**:
  * **Preview**: Biểu tượng hình con mắt (`eye` của Lucide/Feather).
  * **So sánh**: Biểu tượng `git-diff` của Lucide/Feather.
  * Cả hai nút sẽ sử dụng class `ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white` (bằng kích thước và kiểu dáng với nút Wrap và Tìm kiếm).
  * Nút `Preview` cũng sẽ được bổ sung vào toolbar của editor **Nguồn**.

### 0.4. Các lỗi và yêu cầu bổ sung mới phát sinh (Rà soát Phase 2)
* **Lỗi 1: Phần xem trước Preview vượt quá vùng hiển thị màn hình (Overflow viewport)**:
  * **Nguyên nhân**: Trong tệp `editor-component.js`, hàm `openPreview` đang sử dụng `wide: true` (lớp `mw9` - 96rem/1536px), quá rộng so với kích thước `mw8` (64rem/1024px) của Diff. Ngoài ra, thẻ `iframe` hiển thị preview HTML có chiều cao cố định là `height: 75vh` mà không tính đến chiều cao của Header và Margin của modal, khiến tổng chiều cao modal vượt quá 100% viewport trên nhiều kích thước màn hình.
  * **Giải pháp**: 
    - Đồng bộ kích thước Preview và Diff bằng cách thiết lập `wide: false` (lớp `mw8`) trong `openPreview`.
    - Giới hạn chiều cao tối đa của iframe xuống `height: 70vh` (hoặc `68vh`) để vừa khít bên trong modal và viewport, không gây vỡ/tràn màn hình.
* **Lỗi 2: Các nút khác (Wrap, Tìm kiếm) báo lỗi `SyntaxError: invalid escape sequence`**:
  * **Nguyên nhân**: Khi thêm nút Preview mới, các nút xung quanh như Wrap và Tìm kiếm trong `tab_projects.html` đã bị thêm các ký tự escape `\` trái phép vào thuộc tính `onclick` (ví dụ: `onclick="EditorComponent.toggleWordWrap(\'pm-result-text\')"`). Điều này làm hỏng tính hợp lệ của lệnh JavaScript.
  * **Giải pháp**: Dọn dẹp sạch sẽ toàn bộ dấu `\` trong thuộc tính `onclick` của các nút trên toolbar.
* **Lỗi 3: Hàm `showDiffView` bị lặp logic gán sự kiện**:
  * **Nguyên nhân**: Ở cuối hàm `showDiffView`, do sáp nhập code không cẩn thận, đoạn mã append overlay vào body và gán sự kiện click/Escape đã được gọi lại một lần nữa dù `_createOverlay` đã tự động xử lý.
  * **Giải pháp**: Xóa bỏ đoạn mã dư thừa ở cuối hàm `showDiffView` (dòng 315-325).
* **Yêu cầu mới: Đổi nút "Lưu" thành biểu tượng dạng Icon**:
  * **Giải pháp**: Thay thế các nút Lưu chữ văn bản màu xanh (`bg-green`) bằng nút icon nhỏ tương tự các icon khác, sử dụng biểu tượng đĩa mềm (Feather/Lucide `save`). Áp dụng đồng bộ cho cả 3 nút Lưu trong `tab_projects.html` (editor Nguồn, editor Bản dịch, editor Soát lỗi).

---

## 1. Mục tiêu nghiệp vụ

Người dùng làm việc trong `Biên tập dự án` cần xem nhanh nội dung editor dưới dạng render thực tế thay vì nhìn raw text.

Yêu cầu:

- 1 nút `Preview` cho editor `Nguồn` (`pm-source-text`).
- 1 nút `Preview` cho editor `Bản dịch` (`pm-result-text`).
- Vị trí: ngay bên trái nút `Wrap` của mỗi editor.
- Hệ thống tự nhận diện định dạng (`Markdown` / `HTML`) — người dùng không chọn tay.
- Preview hiển thị render thực tế, không phải raw text.

---

## 2. Hiện trạng đã xác nhận trong mã nguồn

### 2.1. Vị trí 2 editor

File: `webui/templates/partials/tab_projects.html`

Toolbar editor `Nguồn` (line ~159), thứ tự nút hiện tại:

```
Wrap | Tìm kiếm | Lưu
```

Toolbar editor `Bản dịch` (line ~170), thứ tự nút hiện tại:

```
So sánh | Wrap | Tìm kiếm | Lưu
```

Thứ tự sau khi thêm nút:

```
Nguồn:    Preview | Wrap | Tìm kiếm | Lưu
Bản dịch: So sánh | Preview | Wrap | Tìm kiếm | Lưu
```

### 2.2. Markdown renderer sẵn có

- `webui/static/js/marked.min.js` — parser Markdown, đã load global
- CSS class `.doc-markdown` trong `webui/static/css/style.css` — style render Markdown
- Pattern tái dụng từ `webui/static/js/doc-manager.js` line 161:

```js
contentEl.innerHTML = `<div class="doc-markdown">${marked.parse(data.content)}</div>`;
```

### 2.3. Pattern overlay đã có: `showDiffView`

`EditorComponent.showDiffView(...)` trong `webui/static/js/editor-component.js` (line 245–318) dùng dynamic overlay:

- Tạo `div` bằng `document.createElement('div')`
- Append vào `document.body`
- Click backdrop → `overlay.remove()`
- **Không có** Escape key handler (cần bổ sung)
- Content được build dạng HTML string inline

`openPreview` sẽ dùng **cùng pattern dynamic overlay**, không dùng `ModalManager` hay `modals.html`.

Lý do chọn dynamic overlay thay `ModalManager`:
- Overlay content hoàn toàn runtime (không có static HTML template nào hợp lý)
- Giống use case của `showDiffView` (view-only, ephemeral, xóa khi đóng)
- Không cần thêm entry vào `modals.html`
- Cho phép tách `_createOverlay` helper dùng chung cho cả `showDiffView` và `openPreview`

### 2.4. `window.currentProjectFile` đã tồn tại

Đã xác nhận trong `editor-component.js` lines 39, 53, 79:

```js
window.currentProjectFile = { name: filename, section };
```

`.name` chứa tên file hiện tại (ví dụ `chapter_01.md`). Dùng trực tiếp trong logic detect format, không cần truyền qua `options`.

---

## 3. Phạm vi thay đổi

### Files sẽ chỉnh sửa

| File | Thay đổi |
|---|---|
| `webui/templates/partials/tab_projects.html` | Cập nhật toolbar của hai editor: thêm nút Preview cho editor Nguồn, đổi nút So sánh & Preview thành biểu tượng SVG, loại bỏ ký tự escape `\` lỗi |
| `webui/templates/partials/footer.html` | Xoá dòng load trùng lặp `project-manager.js` ở dòng 15 |
| `webui/static/js/editor-component.js` | Thêm `_createOverlay`, thêm `openPreview`, refactor `showDiffView` dùng `_createOverlay` |
| `webui/static/css/style.css` | Thêm style cho iframe preview nếu cần |

### Files KHÔNG chỉnh sửa

- `webui/templates/partials/modals.html` — không cần thêm modal mới
- `webui/static/js/ui-helpers.js` — không cần
- `webui/static/js/doc-manager.js` — chỉ tham khảo pattern, không sửa
- Bất kỳ file backend nào

---

## 4. Thiết kế kỹ thuật chi tiết

### 4.1. Cấu trúc nút mới trong `tab_projects.html`

Các nút So sánh, Preview và Lưu được thay đổi thành dạng icon SVG với class `ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white`, đồng bộ với các icon khác.

#### 4.1.1. Icon SVG mẫu
* **Icon Xem trước (Preview/Eye)**:
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
```
* **Icon So sánh (Compare/GitDiff)**:
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><path d="M11 18H8a2 2 0 0 1-2-2V9"/></svg>
```
* **Icon Lưu (Save/FloppyDisk)**:
```html
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg>
```

#### 4.1.2. Toolbar editor Nguồn (`pm-source-editor`)
Vị trí: [tab_projects.html:158-162](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/tab_projects.html#L158-L162)
Nội dung cập nhật (thêm nút Preview, đổi nút Lưu thành icon):
```html
<div class="ml-auto flex gap-1 editor-icon-toolbar">
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.openPreview('pm-source-text', { label: 'Nguồn' })" title="Xem trước"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.toggleWordWrap('pm-source-text')" title="Wrap"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M3 6h18"/><path d="M3 12h15a3 3 0 1 1 0 6h-4"/><path d="M3 18l4-4"/><path d="M3 14l4 4"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.openSearchReplaceModal('pm-source-text')" title="Tìm kiếm"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.saveSourceFile()" title="Lưu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg></button>
</div>
```

#### 4.1.3. Toolbar editor Bản dịch (`pm-result-editor`)
Vị trí: [tab_projects.html:169-175](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/tab_projects.html#L169-L175)
Nội dung cập nhật (đổi So sánh, thêm Preview, đổi Lưu thành icon, dọn sạch ký tự escape `\`):
```html
<div class="ml-auto flex gap-1 editor-icon-toolbar">
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.showDiffView('pm-source-text', 'pm-result-text')" title="So sánh"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><path d="M11 18H8a2 2 0 0 1-2-2V9"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.openPreview('pm-result-text', { label: 'Bản dịch' })" title="Xem trước"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.toggleWordWrap('pm-result-text')" title="Wrap"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M3 6h18"/><path d="M3 12h15a3 3 0 1 1 0 6h-4"/><path d="M3 18l4-4"/><path d="M3 14l4 4"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.openSearchReplaceModal('pm-result-text')" title="Tìm kiếm"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.saveChunkTranslation()" title="Lưu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg></button>
</div>
```

#### 4.1.4. Toolbar editor Bản đã soát (`pm-spell-result-editor`)
Vị trí: [tab_projects.html:199-204](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/tab_projects.html#L199-L204)
Nội dung cập nhật (đổi So sánh và Lưu thành icon):
```html
<div class="ml-auto flex gap-1 editor-icon-toolbar">
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.showDiffView('pm-spell-source-text','pm-spell-result-text')" data-tooltip="So sánh" aria-label="So sánh"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M13 6h3a2 2 0 0 1 2 2v7"/><path d="M11 18H8a2 2 0 0 1-2-2V9"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.toggleWordWrap('pm-spell-result-text')" data-tooltip="Wrap" aria-label="Wrap"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M3 6h18"/><path d="M3 12h15a3 3 0 1 1 0 6h-4"/><path d="M3 18l4-4"/><path d="M3 14l4 4"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.openSearchReplaceModal('pm-spell-result-text')" data-tooltip="Tìm kiếm" aria-label="Tìm kiếm"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></button>
    <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="EditorComponent.saveSpellcheckResult()" title="Lưu"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:14px;height:14px"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/><polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/></svg></button>
</div>
```
```

### 4.2. `_createOverlay` — private helper dùng chung

Thêm method `_createOverlay` vào `EditorComponent` trong `editor-component.js`. Method này là **nền tảng chung** cho cả `showDiffView` và `openPreview`.

Signature:

```js
_createOverlay({ title, subtitle, bodyHtml, wide })
```

- `title` (string): tiêu đề chính hiển thị ở header
- `subtitle` (string, optional): dòng nhỏ bên dưới title
- `bodyHtml` (string): HTML string cho phần body
- `wide` (boolean, default false): nếu `true` dùng `mw9` thay vì `mw8`

Logic:

```js
_createOverlay({ title, subtitle, bodyHtml, wide }) {
    var overlay = document.createElement('div');
    overlay.className = 'fixed absolute--fill bg-black-70 items-center justify-center z-max';
    overlay.style.cssText = 'display:flex; z-index:99999;';
    var widthClass = wide ? 'mw9' : 'mw8';
    var subtitleHtml = subtitle
        ? '<div class="f7 silver mt1">' + subtitle + '</div>'
        : '';
    overlay.innerHTML =
        '<div class="bg-white br3 shadow-5 w-100 ' + widthClass + ' overflow-hidden animate-pop" style="max-height:85vh;">' +
            '<div class="pa3 bb b--black-10 bg-near-white flex justify-between items-center">' +
                '<div>' +
                    '<h3 class="f5 ma0 fw6 dark-gray">' + title + '</h3>' +
                    subtitleHtml +
                '</div>' +
                '<button class="modal-close-btn" onclick="this.closest(\'.fixed\').remove()">&times;</button>' +
            '</div>' +
            '<div class="overflow-y-auto" style="max-height:75vh;">' + bodyHtml + '</div>' +
        '</div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e) {
        if (e.target === overlay) overlay.remove();
    });
    document.addEventListener('keydown', function onEsc(e) {
        if (e.key === 'Escape') {
            overlay.remove();
            document.removeEventListener('keydown', onEsc);
        }
    });
    return overlay;
},
```

**Sizing nhất quán với `showDiffView` hiện tại:**
- Outer container: `max-height: 85vh`
- Body scroll area: `max-height: 75vh`

### 4.3. Refactor `showDiffView` dùng `_createOverlay`

Sau khi build xong `unifiedHtml` và `sideHtml`, thay toàn bộ phần tạo `overlay` (từ `var overlay = document.createElement(...)` đến `overlay.addEventListener(...)`) bằng:

```js
var overlay = this._createOverlay({
    title: '📊 So sánh thay đổi (' + changes + ' dòng khác)',
    bodyHtml:
        '<div id="diff-view-unified" class="pa3" style="background:#fafafa;">' + unifiedHtml + '</div>' +
        '<div id="diff-view-side" class="pa3" style="background:#fafafa;display:none;">' + sideHtml + '</div>'
});
```

Sau đó chèn thêm 2 nút chế độ vào header. Cách đơn giản nhất: sau khi `_createOverlay` trả về `overlay`, tìm header và append nút:

```js
var headerDiv = overlay.querySelector('.flex.justify-between');
var btnGroup = document.createElement('div');
btnGroup.className = 'flex gap-2';
btnGroup.innerHTML =
    '<button id="btn-diff-unified" class="ph2 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="EditorComponent.switchDiffView(\'unified\')">Dọc</button>' +
    '<button id="btn-diff-side" class="ph2 pv1 f7 ba b--silver bg-white br2 pointer hover-bg-near-white" onclick="EditorComponent.switchDiffView(\'side\')">Ngang</button>';
headerDiv.querySelector('button.modal-close-btn').before(btnGroup);
```

> **Lưu ý:** Nếu refactor `showDiffView` gây phức tạp hơn mong đợi, có thể bỏ qua phần refactor và giữ nguyên `showDiffView` hiện tại. `_createOverlay` vẫn được thêm vào và dùng bởi `openPreview`. Refactor `showDiffView` là secondary, không bắt buộc.

### 4.4. `openPreview` — public method mới

Thêm method `openPreview` vào `EditorComponent`:

```js
openPreview(textareaId, options) {
    var content = document.getElementById(textareaId).value;
    if (!content.trim()) {
        UiHelpers.showToast('Editor không có nội dung để preview', 'warning');
        return;
    }
    var label = options.label || 'Preview';
    var filename = window.currentProjectFile ? window.currentProjectFile.name : '';
    // Detect format
    var format = 'markdown';
    if (filename) {
        var ext = filename.split('.').pop().toLowerCase();
        if (ext === 'md' || ext === 'markdown') format = 'markdown';
        else if (ext === 'html' || ext === 'htm' || ext === 'xhtml') format = 'html';
    } else {
        // Fallback: heuristic theo nội dung
        if (/<!DOCTYPE html>|<html[\s>]|<body[\s>]/.test(content) ||
            (content.match(/<(div|p|h[1-6]|section|article|table|ul|ol)[>\s]/gi) || []).length >= 3) {
            format = 'html';
        }
    }
    // Build subtitle
    var subtitle = (filename ? filename + ' • ' : '') + (format === 'html' ? 'HTML' : 'Markdown');
    if (format === 'markdown') {
        bodyHtml = '<div class="doc-markdown pa3">' + marked.parse(content) + '</div>';
    } else {
        bodyHtml = '<iframe sandbox="" srcdoc="" style="width:100%;height:70vh;border:none;display:block;"></iframe>';
    }
    this._createOverlay({
        title: 'Preview — ' + label,
        subtitle: subtitle,
        bodyHtml: bodyHtml,
        wide: false
    });
    // Gán srcdoc sau khi overlay đã vào DOM (tránh timing issue)
    if (format === 'html') {
        var iframe = document.querySelector('.fixed iframe[sandbox]');
        if (iframe) iframe.srcdoc = content;
    }
},

```

**Giải thích các quyết định:**

- `options` chỉ nhận `label`. Không nhận `filename` vì đọc thẳng từ `window.currentProjectFile`.
- Format detection: tầng 1 theo extension (ổn định), tầng 2 heuristic nội dung (fallback).
- Markdown: dùng `marked.parse()` + class `.doc-markdown` — tái dụng hoàn toàn style hiện có.
- HTML: dùng `iframe sandbox="" srcdoc="..."` — cô lập hoàn toàn, chặn script.
- `iframe` không dùng `max-height` mà dùng `height: 70vh` fixed — iframe cần explicit height.
- `srcdoc` gán sau khi DOM đã mount để tránh timing issue với một số browser.

### 4.5. Quy tắc nhận diện định dạng (chốt)

**Tầng 1 — extension file (ưu tiên):**

| Extension | Format |
|---|---|
| `.md`, `.markdown` | `markdown` |
| `.html`, `.htm`, `.xhtml` | `html` |
| Khác hoặc không có | → sang Tầng 2 |

**Tầng 2 — heuristic nội dung (fallback):**

Nhận là `html` nếu thoả một trong hai:
- Có `<!DOCTYPE html>`, `<html`, hoặc `<body` (case-insensitive)
- Có từ 3 block tag HTML trở lên: `<div`, `<p`, `<h1`–`<h6`, `<section`, `<article`, `<table`, `<ul`, `<ol`

Còn lại: mặc định `markdown`.

---

## 5. Sizing và style

### 5.1. Overlay sizing (nhất quán toàn bộ)

| Thành phần | Value |
|---|---|
| Outer container `max-height` | `85vh` |
| Body scroll area `max-height` | `75vh` |
| iframe preview `height` | `70vh` (explicit, để trống khoảng cách cho header modal) |
| Preview overlay width | `mw8` (bằng diff `mw8`) |
| Diff overlay width | `mw8` (giữ nguyên) |

### 5.2. CSS mới trong `style.css`

Chỉ thêm nếu cần override, không thêm thừa:

```css
/* Preview overlay: đảm bảo iframe fill body */
.preview-iframe-body {
    padding: 0;
    overflow: hidden;
}
```

Nếu không có vấn đề về padding/overflow với iframe, có thể bỏ luôn — không bắt buộc.

---

## 6. Luồng tương tác

1. Người dùng mở file trong `Biên tập dự án`
2. Bấm `Preview` trên toolbar editor muốn xem
3. `openPreview(textareaId, { label })` được gọi
4. Nếu editor rỗng → toast cảnh báo, dừng
5. Đọc `window.currentProjectFile.name` lấy filename
6. Detect format (extension → heuristic)
7. Build bodyHtml tương ứng
8. Gọi `_createOverlay({ title, subtitle, bodyHtml, wide: true })`
9. Overlay mount vào DOM với Escape + backdrop-click để đóng
10. Nếu HTML: gán `iframe.srcdoc = content` sau khi mount

---

## 7. Tiêu chí nghiệm thu

- [ ] Có đúng 2 nút `Preview`, mỗi editor 1 nút.
- [ ] Cả hai nút nằm bên trái nút `Wrap`.
- [ ] Bấm preview khi editor chứa Markdown → render Markdown với style `.doc-markdown`.
- [ ] Bấm preview khi editor chứa HTML → render thực tế trong iframe.
- [ ] Format tự nhận diện, người dùng không chọn tay.
- [ ] Editor rỗng → toast, không mở overlay.
- [ ] Overlay đóng được bằng: nút ×, click backdrop, phím Escape.
- [ ] Nội dung HTML preview không làm vỡ layout trang chính.
- [ ] Không ảnh hưởng `Wrap`, `Tìm kiếm`, `Lưu`, `So sánh`.

---

## 8. Kịch bản kiểm thử tay

### 8.1. Markdown cơ bản

- Mở file `.md` có heading, list, code block
- Bấm Preview ở editor `Nguồn` và `Bản dịch`
- Kỳ vọng: render đúng, style giống tab `Tài liệu`

### 8.2. HTML cơ bản

- Mở file `.html` có `h1`, `p`, `strong`, `table`
- Bấm Preview
- Kỳ vọng: render thật trong iframe, không hiện raw tag

### 8.3. Fallback heuristic

- File không có extension rõ hoặc nội dung paste tạm
- Nội dung có nhiều HTML block tag → nhận là HTML
- Nội dung Markdown / plain text → nhận là Markdown

### 8.4. Empty state

- Editor rỗng → bấm Preview
- Kỳ vọng: toast `Editor không có nội dung để preview`, không mở overlay

### 8.5. HTML có `<style>` nội tuyến

- HTML có `<style>` trong nội dung
- Kỳ vọng: style chỉ áp dụng trong iframe, không ảnh hưởng trang chính

### 8.6. Đóng overlay

- Bấm nút ×
- Bấm backdrop (vùng tối ngoài modal)
- Nhấn phím Escape
- Kỳ vọng: cả 3 cách đều đóng được

---

## 9. Các quyết định đã chốt

| Quyết định | Chốt |
|---|---|
| HTML preview dùng `innerHTML` hay `iframe`? | `iframe sandbox="" srcdoc` |
| Modal cố định (`modals.html`) hay dynamic overlay? | Dynamic overlay — giống `showDiffView` |
| Auto-detect ưu tiên extension hay nội dung? | Extension trước, heuristic nội dung là fallback |
| `filename` truyền qua `options` hay đọc global? | Đọc thẳng từ `window.currentProjectFile.name` |
| 4 helper riêng hay inline trong `openPreview`? | Inline trong `openPreview` |
| Escape key? | Implement trong `_createOverlay` — áp dụng tự động cho cả Diff và Preview |
| iframe height? | `height: 70vh` explicit — chừa khoảng trống cho header tránh overflow viewport |
| Preview overlay width? | `mw8` — bằng với kích thước của Diff overlay |

---

## 10. Ngoài phạm vi

Các mục sau **không** nằm trong lần triển khai này:

- Preview cho khu vực `Spellcheck`
- Nút chuyển tay giữa `Markdown` và `HTML`
- Live preview theo thời gian thực khi gõ
- Lưu trạng thái modal preview giữa các lần mở
- Sanitizer HTML phức tạp ngoài cơ chế `sandbox` cơ bản

---

## 11. Các bước triển khai theo thứ tự

1. **`footer.html`**: Xác nhận đã xoá dòng load trùng lặp `project-manager.js` ở dòng 15.
2. **`editor-component.js`**:
   - Cập nhật hàm `openPreview` để dùng `wide: false` khi gọi `_createOverlay` và đặt `height: 70vh` cho iframe.
   - Xóa bỏ đoạn code thừa (append và addEventListener) ở cuối hàm `showDiffView` từ dòng 315 đến 325.
3. **`tab_projects.html`**:
   - Cập nhật toolbar editor Nguồn (thêm nút Preview biểu tượng, thay nút Lưu thành biểu tượng đĩa mềm SVG, dọn sạch ký tự escape `\`).
   - Cập nhật toolbar editor Bản dịch (thay nút So sánh và Preview thành biểu tượng, thay nút Lưu thành biểu tượng đĩa mềm SVG, dọn sạch ký tự escape `\` ở toàn bộ các thuộc tính `onclick`).
   - Cập nhật toolbar editor Bản đã soát (thay nút So sánh thành biểu tượng, thay nút Lưu thành biểu tượng đĩa mềm SVG).
4. Kiểm thử tay theo mục 8 (cả editor Nguồn, Bản dịch, Bản đã soát).

