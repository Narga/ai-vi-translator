# Thiết kế Hợp nhất Giao diện Biên tập & Kiểm chính tả

Tài liệu này chi tiết hóa thiết kế hợp nhất hai tính năng **Biên tập** (Editor) và **Kiểm chính tả** (Spell Check) trong giao diện dự án thành một mục duy nhất để tối ưu hóa không gian làm việc, tăng tính trực quan và giảm thiểu thao tác dư thừa.

---

## 1. Mục tiêu & Định hướng Thiết kế
- **Hợp nhất giao diện**: Loại bỏ thẻ phụ "Kiểm chính tả" ở thanh điều hướng cấp cao. Thay vào đó, tích hợp toàn bộ vào thẻ "Biên tập".
- **Chia sẻ danh sách tập tin nguồn**: Cả hoạt động Dịch thuật và Soát lỗi AI đều bắt đầu từ tập tin nguồn, do đó chúng sẽ cùng hiển thị trong tab **Nội dung nguồn** ở thanh bên.
- **Tối ưu hóa UI/UX**:
  - Giao diện nhẹ, không lạm dụng JavaScript nặng.
  - Sử dụng CSS thuần cho tooltips hiển thị mượt mà.
  - Hỗ trợ tốt cho điều khiển bằng chuột và cảm ứng trên thiết bị di động.
  - Biểu tượng soát lỗi trực quan, phản ánh đúng tính năng.
  - Việt hóa thuật ngữ "Xóa TM dự án" sang ngôn từ dễ hiểu hơn đối với người dùng phổ thông.

---

## 2. Chi tiết Thay đổi Giao diện (UI)

### 2.1. Thanh sub-tabs workspace của Dự án
Thay đổi danh sách thẻ điều hướng tại `tab_projects.html` từ 4 thẻ thành 3 thẻ:
1. **Biên tập** (Mặc định)
2. **Thông tin**
3. **Chỉ dẫn**

*Thẻ "Kiểm chính tả" bị loại bỏ hoàn toàn.*

### 2.2. Thanh bên (Sidebar) của mục Biên tập
Sử dụng chung thanh bên `#pm-file-sidebar` với 3 thẻ mini-tabs ở dưới cùng:
- **Nội dung nguồn** (Tập tin gốc cần dịch/soát lỗi)
- **Bản dịch** (Tập tin đã dịch xong)
- **Soát chính tả** (Tập tin đã soát lỗi xong)

#### Thanh công cụ trên cùng (Toolbar) trong Sidebar
Tích hợp tất cả các nút chức năng hoạt động trên tập tin. Tùy thuộc vào mini-tab đang hoạt động, các nút không liên quan sẽ được ẩn bằng lớp CSS `.dn` (display: none):
- **Tab "Nội dung nguồn"**: Hiển thị tất cả nút:
  - Chọn tất cả (Checkbox)
  - Tải lên (Upload)
  - Chia nhỏ (Chunk)
  - Dịch các mục đã chọn (`translateSelectedInProject`)
  - Soát lỗi các mục đã chọn (`spellcheckSelectedInProject`) **[MỚI]**
  - Ghép tập tin (`mergeTranslatedFiles`)
  - Xóa tập tin đã chọn (`deleteSelectedSidebarFiles`)
- **Tab "Bản dịch"**: Chỉ hiển thị:
  - Chọn tất cả (Checkbox)
  - Ghép tập tin (Merge)
  - Xóa tập tin đã chọn
- **Tab "Soát chính tả"**: Chỉ hiển thị:
  - Chọn tất cả (Checkbox)
  - Xóa tập tin đã chọn

#### Danh sách tập tin (File List Item)
Khi danh sách tập tin nguồn được chọn, mỗi dòng tập tin có các nút thao tác trực tiếp:
- **Dịch** (Translate)
- **Soát lỗi** (Spellcheck) **[MỚI]**
- **Đổi tên** (Rename)
- **Xóa** (Delete)

### 2.3. Khu vực Editors (Bộ biên tập)
Khu vực hiển thị nội dung editor sẽ tự động thay đổi dựa theo mini-tab đang được chọn ở Sidebar:
- **Khi chọn "Nội dung nguồn" hoặc "Bản dịch"**:
  - Hiển thị cột Nguồn (`#pm-source-editor`) và cột Bản dịch (`#pm-result-editor`).
  - Hiển thị thanh trạng thái dịch thuật ở dưới cùng (đếm từ, đếm ký tự, ước lượng token, nút Tải về/Sao chép/Dịch lại).
  - Ẩn toàn bộ phần soát lỗi.
- **Khi chọn "Soát chính tả"**:
  - Hiển thị cột Bản dịch (`#pm-spell-source-editor`) và Bản đã soát (`#pm-spell-result-editor`).
  - Hiển thị Nhật ký soát lỗi (`.spell-log-panel`).
  - Hiển thị thanh trạng thái soát lỗi ở dưới cùng (đếm từ, đếm ký tự, nút Tải về/Sao chép/Soát lại).
  - Ẩn toàn bộ phần biên tập dịch thuật.

---

## 3. Thay đổi Biểu tượng & Thuật ngữ

### 3.1. Biểu tượng Soát chính tả mới
Thay thế biểu tượng chữ `T` kèm dấu tích (dễ gây hiểu nhầm sang định dạng văn bản) bằng biểu tượng chữ `A` kèm dấu tích (biểu trưng chuẩn của Spellcheck/Proofread):
```xml
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="m6 16 6-12 6 12"/>
  <path d="M8 12h8"/>
  <path d="m16 20 2 2 4-4"/>
</svg>
```

### 3.2. Thay đổi tên nút "Xóa TM dự án"
- **Tên mới**: **"Đặt lại bộ nhớ dịch"** (Reset translation memory)
- **Lý do chọn**:
  - "TM" là thuật ngữ kỹ thuật (Translation Memory) ít người dùng phổ thông biết đến.
  - "Bộ nhớ dịch" phản ánh chính xác tính năng lưu trữ dữ liệu dịch để tái sử dụng.
  - "Đặt lại" mô tả rõ hành động làm sạch/reset bộ nhớ của riêng dự án này mà không làm ảnh hưởng đến tệp tin của dự án.
- **Cập nhật nội dung thông báo xác nhận (Confirm popup)**:
  - Từ: `"Xóa Translation Memory của dự án..."`
  - Thành: `"Bạn có chắc chắn muốn đặt lại bộ nhớ dịch của dự án này không? Hành động này sẽ xóa sạch toàn bộ dữ liệu bộ nhớ dịch riêng của dự án này và không thể khôi phục."`

---

## 4. Giải pháp Hiển thị Hover Giải thích (Tooltips) bằng CSS Thuần
Thêm các định nghĩa CSS hiệu năng cao, nhẹ và mượt mà vào `style.css`:
```css
/* Custom CSS Tooltip */
[data-tooltip] {
    position: relative;
}
[data-tooltip]::after {
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
[data-tooltip]:hover::after {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) scale(1);
}
```
*Tất cả các nút chức năng sẽ được bổ sung thuộc tính `data-tooltip` thay vì `title` mặc định để đồng bộ hóa thẩm mỹ.*

---

## 5. Kế hoạch xác minh (Verification Plan)
- **Tập tin nguồn**: Tải lên tập tin mới, kiểm tra các thao tác Dịch lẻ, Soát lỗi lẻ, Dịch đã chọn, Soát lỗi đã chọn.
- **Tab chuyển đổi**: Đảm bảo khi bấm "Soát chính tả" ở mini-tab thanh bên, các editor tương ứng được hiện lên và Nhật ký soát lỗi hiển thị đúng.
- **Tính năng Đặt lại bộ nhớ dịch**: Bấm nút và kiểm tra xem thông báo hiển thị đúng tên mới, gửi đúng API xóa TM và không lỗi.
