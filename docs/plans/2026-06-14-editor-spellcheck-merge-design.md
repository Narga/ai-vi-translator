# Thiết kế Hợp nhất Giao diện Biên tập & Kiểm chính tả

Tài liệu này chi tiết hóa thiết kế hợp nhất hai tính năng **Biên tập** (Editor) và **Kiểm chính tả** (Spell Check) trong giao diện dự án thành một mục duy nhất để tối ưu hóa không gian làm việc, tăng tính trực quan và giảm thao tác dư thừa.

---

## 1. Mục tiêu & Định hướng Thiết kế

- **Hợp nhất giao diện**: Loại bỏ thẻ phụ "Kiểm chính tả" ở thanh điều hướng cấp cao. Toàn bộ trải nghiệm kiểm chính tả nằm trong thẻ **Biên tập**.
- **Chia sẻ danh sách tập tin nguồn**: Dịch thuật và Soát lỗi AI đều bắt đầu từ tập tin nguồn, nên thao tác bắt đầu spellcheck nằm trong tab **Nội dung nguồn**.
- **Tách rõ kết quả đã soát**: Tab **Soát chính tả** chỉ hiển thị các tập tin đã được soát lỗi xong.
- **An toàn thao tác hàng loạt**: Khi người dùng chuyển giữa các mini-tab trong sidebar, hệ thống xóa selection hiện tại để tránh dịch, xóa, ghép hoặc soát nhầm nhóm file.
- **Tối ưu hóa UI/UX**:
  - Giao diện nhẹ, không lạm dụng JavaScript nặng.
  - Tooltip CSS chỉ dùng cho các nút icon toolbar trong khu vực Editor.
  - Biểu tượng soát lỗi trực quan, phản ánh đúng tính năng.
  - Việt hóa thuật ngữ "Xóa TM dự án" sang ngôn từ dễ hiểu hơn đối với người dùng phổ thông.

---

## 2. Chi tiết Thay đổi Giao diện

### 2.1. Thanh sub-tabs workspace của Dự án

Thay đổi danh sách thẻ điều hướng tại `tab_projects.html` từ 4 thẻ thành 3 thẻ:

1. **Biên tập** (Mặc định)
2. **Thông tin**
3. **Chỉ dẫn**

Thẻ **Kiểm chính tả** bị loại bỏ hoàn toàn ở cấp workspace.

### 2.2. Thanh bên của mục Biên tập

Sử dụng chung thanh bên `#pm-file-sidebar` với 3 mini-tabs ở dưới cùng:

- **Nội dung nguồn**: tập tin gốc cần dịch hoặc cần soát lỗi.
- **Bản dịch**: tập tin đã dịch xong.
- **Soát chính tả**: tập tin đã soát lỗi xong.

Không còn thanh bên riêng `#pm-spell-file-sidebar`.

### 2.3. Quy tắc dữ liệu của từng mini-tab

- **Nội dung nguồn**
  - Render từ `window.currentProject.sources`.
  - Mỗi dòng có các thao tác: Dịch, Soát lỗi, Đổi tên, Xóa.
  - Bulk action được phép: upload, chunk, dịch đã chọn, soát lỗi đã chọn, ghép, xóa.

- **Bản dịch**
  - Render từ `window.currentProject.translated`.
  - Bulk action được phép: ghép, xóa.

- **Soát chính tả**
  - Render từ endpoint `/api/projects/{slug}/files/spelling`.
  - Endpoint trả về danh sách các tập tin **đã được AI soát lỗi xong** và lưu trong thư mục output được chỉ định của dự án (không phải thư mục sources).
  - Không hiển thị file `_info.txt`.
  - Chỉ hiển thị output đã soát, không hiển thị file nguồn chưa soát.
  - Bulk action được phép: xóa.

### 2.4. Quy tắc selection

Khi chuyển giữa bất kỳ mini-tab nào, toàn bộ selection hiện tại phải được clear:

- Clear `window.selectedFiles`.
- Clear `window.selectedTranslatedFiles`.
- Reset checkbox chọn tất cả.
- Ẩn hoặc cập nhật text báo số file đang chọn.

Lý do: tránh người dùng chọn ở tab này rồi vô tình xóa hoặc thao tác hàng loạt ở tab khác.

### 2.5. Thanh công cụ trên cùng trong Sidebar

Tùy thuộc vào mini-tab đang hoạt động, các nút không liên quan được ẩn bằng lớp CSS `.dn` hoặc style tương đương:

- **Tab "Nội dung nguồn"**:
  - Chọn tất cả
  - Tải lên
  - Chia nhỏ
  - Dịch các mục đã chọn (`translateSelectedInProject`)
  - Soát lỗi các mục đã chọn (`spellcheckSelectedInProject`)
  - Ghép tập tin (`mergeTranslatedFiles`)
  - Xóa tập tin đã chọn (`deleteSelectedSidebarFiles`)

- **Tab "Bản dịch"**:
  - Chọn tất cả
  - Ghép tập tin
  - Xóa tập tin đã chọn

- **Tab "Soát chính tả"**:
  - Chọn tất cả
  - Xóa tập tin đã chọn

Tooltip CSS chỉ áp dụng cho các nút icon toolbar này. Không thay toàn bộ `title` của các nút văn bản hoặc row action.

### 2.6. Khu vực Editors

Khu vực hiển thị nội dung editor thay đổi theo mini-tab đang chọn:

- **Khi chọn "Nội dung nguồn"**:
  - Hiển thị `#pm-translation-workspace`.
  - Hiển thị cột Nguồn (`#pm-source-editor`) và cột Bản dịch (`#pm-result-editor`) — bố cục 2 cột.
  - Hiển thị thanh trạng thái dịch thuật ở dưới cùng.
  - Ẩn `#pm-spellcheck-workspace`.

- **Khi chọn "Bản dịch"**:
  - Hiển thị `#pm-translation-workspace` — **vẫn là bố cục 2 cột song song** (cột Nguồn + cột Bản dịch).
  - Người dùng click vào file dịch trong sidebar sẽ thấy đồng thời cả nội dung nguồn (cột trái) và bản dịch (cột phải).
  - Hành vi load file giống với tab "Nội dung nguồn", không cần workspace riêng.
  - Hiển thị thanh trạng thái dịch thuật ở dưới cùng.
  - Ẩn `#pm-spellcheck-workspace`.

- **Khi chọn "Soát chính tả"**:
  - Hiển thị `#pm-spellcheck-workspace`.
  - Hiển thị cột Bản dịch (`#pm-spell-source-editor`) và Bản đã soát (`#pm-spell-result-editor`).
  - Hiển thị Nhật ký soát lỗi (`.spell-log-panel`).
  - Hiển thị thanh trạng thái soát lỗi ở dưới cùng.
  - Ẩn `#pm-translation-workspace`.

---

## 3. Thay đổi Biểu tượng & Thuật ngữ

### 3.1. Biểu tượng Soát chính tả mới

Thay biểu tượng chữ `T` kèm dấu tích bằng biểu tượng chữ `A` kèm dấu tích:

```xml
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="m6 16 6-12 6 12"/>
  <path d="M8 12h8"/>
  <path d="m16 20 2 2 4-4"/>
</svg>
```

### 3.2. Thay đổi tên nút "Xóa TM dự án"

- **Tên mới**: **"Đặt lại bộ nhớ dịch"**
- **Tooltip/title**: `"Đặt lại bộ nhớ dịch riêng của dự án này"`
- **Confirm popup**:

```text
Bạn có chắc chắn muốn đặt lại bộ nhớ dịch của dự án "{name}" không?
Hành động này sẽ xóa sạch toàn bộ dữ liệu bộ nhớ dịch riêng của dự án này và không thể khôi phục.
```

Backend API hiện có không đổi.

---

## 4. Tooltip CSS

Tooltip CSS dùng cho icon toolbar trong khu vực Editor, không dùng thay thế toàn bộ `title` trên trang.

Selector đề xuất:

```css
.icon-toolbar [data-tooltip],
.editor-icon-toolbar [data-tooltip] {
    position: relative;
}
.icon-toolbar [data-tooltip]::after,
.editor-icon-toolbar [data-tooltip]::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%) scale(0.9);
    background: rgba(15, 23, 42, 0.95);
    color: #ffffff;
    font-size: 0.75rem;
    padding: 6px 10px;
    border-radius: 6px;
    white-space: nowrap;
    opacity: 0;
    visibility: hidden;
    transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 1000;
    pointer-events: none;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
    backdrop-filter: blur(4px);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
.icon-toolbar [data-tooltip]:hover::after,
.editor-icon-toolbar [data-tooltip]:hover::after {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) scale(1);
}
```

Manual verification must check tooltip clipping inside the sidebar header because several parent containers use constrained overflow.

---

## 5. Kế hoạch Xác Minh

- **Tập tin nguồn**: tải lên file mới, kiểm tra Dịch lẻ, Soát lỗi lẻ, Dịch đã chọn, Soát lỗi đã chọn.
- **Bản dịch**: kiểm tra danh sách file dịch, chọn tất cả, ghép tập tin, xóa đã chọn.
- **Soát chính tả**: kiểm tra chỉ thấy file đã soát, không thấy file nguồn chưa soát, không thấy `_info.txt`.
- **Chuyển tab**: selection phải clear khi chuyển `Nội dung nguồn` sang `Bản dịch`, `Bản dịch` sang `Soát chính tả`, và `Soát chính tả` về `Nội dung nguồn`.
- **Toolbar**: nút hiện/ẩn đúng theo từng mini-tab.
- **Tooltip**: chỉ icon toolbar có tooltip CSS mới; row action hoặc nút văn bản có thể giữ `title`.
- **Đặt lại bộ nhớ dịch**: text nút và confirm popup dùng thuật ngữ mới, API backend không đổi.
- **Regression**: chạy `uv run pytest` và kiểm tra app khởi động bằng `uv run python webui.py`.
