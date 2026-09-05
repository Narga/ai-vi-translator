# TÀI LIỆU BỘ LỌC HIỂN THỊ TẬP TIN (FILE FILTER & SORT)
> **Dự án**: Novel-Translator  
> **Tài liệu**: docs/FILE_FILTER_SPECIFICATION.md  
> **Phiên bản**: v1.0 (05/09/2026)  
> **Phạm vi**: Cơ chế lọc theo từ khóa, sắp xếp danh mục và đồng bộ tương tác cho danh sách tập tin Workspace (Bản gốc, Bản dịch, Soát lỗi).
> **Ghi chú áp dụng (content-translator, 3a+):** đặc tả gốc của Novel-Translator, dùng làm tài liệu tham khảo. Triển khai ở đây: 2 tabs sources/results (không có tab Soát lỗi); selection bằng Set tên file, đổi tab reset; lifecycle còn lại giữ nguyên.

---

## 1. CÁC TẬP TIN THAM GIA VÀO CƠ CHẾ BỘ LỌC

Cơ chế lọc và sắp xếp tập tin trong danh sách Workspace của dự án **Novel-Translator** được triển khai hoàn toàn ở tầng Frontend (Client-side), xử lý trực tiếp trên dữ liệu danh sách file đã nạp trong bộ nhớ (`window.currentProject`), bao gồm các tập tin:

| Tầng | Đường dẫn tập tin | Trách nhiệm |
| :--- | :--- | :--- |
| **Giao diện HTML** | `webui/templates/partials/tab_projects.html` *(dòng 117-135)* | Nút bấm icon phễu lọc `#pm-btn-filter-files` và Dropdown Popup menu `#pm-file-filter-menu`. |
| **Định dạng CSS** | `webui/static/css/style.css` *(dòng 793-860)* | Định vị Dropdown Panel nổi, hiệu ứng hover, kiểu dáng Radio/Input nhỏ gọn. |
| **Logic Frontend (JS)** | `webui/static/js/project-manager.js` | <br>• Quản lý trạng thái `ProjectManager.fileFilters` *(dòng 128)*.<br>• Menu hiển thị: `toggleFileFilterMenu()`, `closeFileFilterMenu()`, `syncFileFilterMenuState()` *(dòng 1576-1601)*.<br>• Bộ lắng nghe sự kiện: `initFileFilterEvents()` (Click outside, phím Escape) *(dòng 1661-1678)*.<br>• Giải thuật lọc & sắp xếp: `applyFileFilters(files)` *(dòng 1634-1659)*.<br>• Đồng bộ render danh sách: `_reRenderActiveFileTab()` *(dòng 1618-1632)*.<br>• Tác động đến Chọn tất cả (Select All): `selectAllSidebarFiles()` *(dòng 1230-1275)*. |

---

## 2. BỐ TRÍ CỦA DROPDOWN MENU BỘ LỌC (`#pm-file-filter-menu`)

### 2.1. Cấu trúc DOM & Bố cục Thị giác
Nút bấm phễu lọc và panel menu được đặt trong một khối bao bọc tương đối (`.file-filter-menu-wrap`). Panel menu `.pm-file-filter-panel` được định vị tuyệt đối `position: absolute`, trượt xuống ngay bên dưới nút bấm (`top: 100%; left: 0; margin-top: 4px`).

Panel có nền trắng (`#fff`), viền mảnh (`1px solid #e2e8f0`), bo góc 8px (`border-radius: 8px`), đổ bóng nổi phân tầng (`box-shadow: 0 4px 12px rgba(0,0,0,0.12), 0 1px 3px rgba(0,0,0,0.08)`), chiều rộng cố định `230px` và chỉ số phân lớp `z-index: 1000`.

```text
  [📁] [⬆] [🔽] [▶] [🔍] [✏️] [🗑]   <-- Thanh công cụ sidebar header
            │
            ▼
┌─────────────────────────────────────────┐
│ SẮP XẾP THEO                            │ (.pm-file-filter-label)
│ (o) Tên file     ( ) Định dạng          │ (Radio pm-filter-sort-by: name | ext)
├─────────────────────────────────────────┤
│ THỨ TỰ                                  │
│ (o) Tăng dần     ( ) Giảm dần           │ (Radio pm-filter-sort-order: asc | desc)
├─────────────────────────────────────────┤
│ LỌC THEO TÊN                            │
│ [ Lọc theo tên file...                ] │ (#pm-filter-keyword-input)
└─────────────────────────────────────────┘
```

### 2.2. Chi tiết các khối điều khiển trong Menu
1. **Khối 1: Sắp xếp theo (Sort By)**:
   - Nhãn: `SẮP XẾP THEO` (in hoa, màu xám `#64748b`, 11px font-weight 700).
   - Radio button `pm-filter-sort-by`:
     - `name`: Theo tên file (mặc định).
     - `ext`: Theo định dạng phần mở rộng tệp (`.txt`, `.md`, `.html`...).
2. **Khối 2: Thứ tự (Sort Order)**:
   - Nhãn: `THỨ TỰ`.
   - Radio button `pm-filter-sort-order`:
     - `asc`: Tăng dần A -> Z (mặc định).
     - `desc`: Giảm dần Z -> A.
3. **Khối 3: Lọc theo tên (Filter Keyword)**:
   - Nhãn: `LỌC THEO TÊN`.
   - Ô text `#pm-filter-keyword-input` (`.pm-file-filter-input`): Nhập chuỗi ký tự bất kỳ để lọc ngay lập tức theo sự kiện `oninput`.

---

## 3. CƠ CHẾ LƯU TRỮ TRẠNG THÁI (STATE MANAGEMENT)

Trạng thái bộ lọc được quản lý tập trung bên trong đối tượng `ProjectManager.fileFilters`:

```javascript
fileFilters: {
    isOpen: false,       // Menu đang mở hay đóng
    sortBy: 'name',      // Tiêu chí sắp xếp: 'name' | 'ext'
    sortOrder: 'asc',    // Chiều sắp xếp: 'asc' | 'desc'
    keyword: ''          // Chuỗi từ khóa lọc
}
```

### Quy tắc vòng đời trạng thái (Lifecycle):
- **Khi mở dự án mới (`openProject`)**: Gọi `_resetFileFilters()` để đưa trạng thái về mặc định (`sortBy: 'name'`, `sortOrder: 'asc'`, `keyword: ''`, `isOpen: false`), tránh lưu vết lọc của dự án trước.
- **Khi chuyển tab file nội bộ (Bản gốc <-> Bản dịch <-> Soát lỗi)**:
  - Tự động đóng menu nếu đang mở (`closeFileFilterMenu()`).
  - **GIỮ NGUYÊN** giá trị `sortBy`, `sortOrder`, `keyword` để người dùng không phải nhập lại từ khóa lọc khi chuyển qua lại giữa file nguồn và file đã dịch.

---

## 4. GIẢI THUẬT LỌC VÀ SẮP XẾP (`applyFileFilters`)

Hàm cốt lõi xử lý lọc và sắp xếp là `ProjectManager.applyFileFilters(files)`. Giải thuật gồm 2 bước tuần tự:

```javascript
applyFileFilters(files) {
    if (!files || !files.length) return [];
    const { sortBy, sortOrder, keyword } = this.fileFilters;
    let result = [...files]; // Tạo bản sao nông, không đột biến mảng gốc

    // BƯỚC 1: LỌC THEO TỪ KHÓA (Case-insensitive)
    if (keyword) {
        const kw = keyword.toLowerCase();
        result = result.filter(f => f.name.toLowerCase().includes(kw));
    }

    // BƯỚC 2: SẮP XẾP TẬP TIN
    result.sort((a, b) => {
        let cmp = 0;
        if (sortBy === 'ext') {
            // Tách phần mở rộng tệp
            const extA = (a.name.split('.').pop() || '').toLowerCase();
            const extB = (b.name.split('.').pop() || '').toLowerCase();
            
            // So sánh theo extension với locale 'vi'
            cmp = extA.localeCompare(extB, 'vi');
            
            // Nếu trùng extension, sắp xếp phụ theo tên file
            if (cmp === 0) cmp = a.name.localeCompare(b.name, 'vi');
        } else {
            // Sắp xếp mặc định theo tên file với locale 'vi'
            cmp = a.name.localeCompare(b.name, 'vi');
        }
        
        // Đảo chiều nếu sortOrder là 'desc'
        return sortOrder === 'desc' ? -cmp : cmp;
    });

    return result;
}
```

### Đặc tính nổi bật của giải thuật:
1. **Hỗ trợ tiếng Việt đầy đủ (`localeCompare(..., 'vi')`)**: Giúp tên file có dấu tiếng Việt (ví dụ: *Chương 1, Chương 10, Đắc Nhân Tâm*) được sắp xếp đúng chuẩn ngữ pháp thay vì chỉ so mã ASCII đơn thuần.
2. **Sắp xếp 2 cấp khi chọn định dạng (`ext`)**: Đầu tiên so sánh đuôi file; nếu hai file cùng đuôi (ví dụ đều là `.txt`) thì tự động fallback sắp xếp theo tên file để đảm bảo thứ tự luôn ổn định.
3. **Không ảnh hưởng dữ liệu gốc**: Luôn tạo mảng sao chép `let result = [...files]`, giữ nguyên danh sách `window.currentProject.sources` và `translated` trong bộ nhớ RAM.

---

## 5. TƯƠNG TÁC NGƯỜI DÙNG & ĐỒNG BỘ GIAO DIỆN (UI INTEGRATION)

### 5.1. Cơ chế đóng mở & Click-outside
Được đăng ký thông qua `initFileFilterEvents()`:
- **Click ra ngoài (Click Outside)**: Bắt sự kiện trên toàn `document`. Nếu click vào phần tử không thuộc `.file-filter-menu-wrap` $\to$ Tự động đóng menu.
- **Phím Escape**: Nhấn phím `Escape` khi menu đang mở $\to$ Đóng menu ngay lập tức.
- **Ngăn chặn nổi bọt (`event.stopPropagation()`)**: Khi click bên trong panel menu, sự kiện click không lan truyền ra ngoài, tránh làm đóng panel khi người dùng đang bấm radio hoặc gõ chữ.

### 5.2. Luồng phản hồi trực tiếp (Real-time Re-render)
Mỗi khi người dùng gõ phím vào ô tìm kiếm hoặc đổi radio chọn sắp xếp:
1. Gọi tương ứng `setFileFilterKeyword()`, `setFileFilterSortBy()`, hoặc `setFileFilterSortOrder()`.
2. Hàm điều phối `_reRenderActiveFileTab()` kiểm tra xem tab con nào đang `active`:
   - Nếu đang ở tab Nguồn (`pm-tab-sources`): Gọi `renderPmFileList()` và cập nhật nút chọn tất cả `updateSelectAllButton()`.
   - Nếu đang ở tab Dịch (`pm-tab-translated`): Gọi `renderPmTranslatedList()` và `updateSelectAllTranslatedButton()`.
   - Nếu đang ở tab Soát lỗi (`pm-tab-spelling`): Gọi `renderPmSpellcheckedList()`.
3. Giao diện danh sách file lập tức cập nhật chỉ hiển thị các file thỏa mãn điều kiện lọc.

### 5.3. Tác động của Bộ lọc tới thao tác Hàng loạt (Bulk Actions)
Khi người dùng tick chọn checkbox **Chọn tất cả** trên Sidebar (`#chk-select-all-sidebar`):
- Hệ thống chỉ tick chọn **các file đang hiển thị sau khi lọc** (`applyFileFilters(...)`):
  ```javascript
  // Trích đoạn từ selectAllSidebarFiles()
  const filtered = ProjectManager.applyFileFilters(allSources);
  if (checked) {
      filtered.forEach(f => window.selectedFiles.add(f.name));
  } else {
      filtered.forEach(f => window.selectedFiles.delete(f.name));
  }
  ```
- **Ý nghĩa UX**: Người dùng có thể kết hợp: Lọc các chương từ `1` đến `10` -> Bấm "Chọn tất cả" -> Bấm "Dịch đã chọn" hoặc "Đổi tên hàng loạt" mà không lo bị tác động nhầm vào các file khác đang bị ẩn.
