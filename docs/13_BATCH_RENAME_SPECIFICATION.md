# TÀI LIỆU CƠ CHẾ ĐỔI TÊN TẬP TIN & ĐỔI TÊN HÀNG LOẠT (BATCH RENAME)
> **Dự án**: Novel-Translator  
> **Tài liệu**: docs/BATCH_RENAME_SPECIFICATION.md  
> **Phiên bản**: v1.0 (05/09/2026)  
> **Phạm vi**: Cơ chế đổi tên đơn lẻ và đổi tên hàng loạt trong Workspace Quản lý Dự án.
> **Ghi chú áp dụng (content-translator, 3a+):** đặc tả gốc của Novel-Translator, dùng làm tài liệu tham khảo. Điểm khác khi triển khai ở đây (`docs/15_*`): **KHÔNG auto-sync** sang thư mục đối ứng (§3.3.5/§4.1 không áp dụng); va chạm → `_conflict` (đơn) / entry lỗi (batch); 2 tabs sources/results (không có tab Soát lỗi).

---

## 1. CÁC TẬP TIN THAM GIA VÀO CƠ CHẾ ĐỔI TÊN

Cơ chế đổi tên (đơn lẻ & hàng loạt) của dự án **Novel-Translator** được hiện thực trên 3 tầng (Template HTML, Client-side JS, Backend Flask API) qua các tập tin sau:

| Tầng | Đường dẫn tập tin | Trách nhiệm |
| :--- | :--- | :--- |
| **Giao diện HTML (Modal & Nút bấm)** | `webui/templates/partials/modals.html` *(dòng 150-176)* | Khai báo cấu trúc Modalbox Dialog `#batch-rename-modal`. |
| | `webui/templates/partials/tab_projects.html` *(dòng 138)* | Nút bấm icon đổi tên hàng loạt `#pm-btn-rename-batch` trên thanh công cụ Workspace. |
| **Logic Frontend (JS)** | `webui/static/js/project-manager.js` | <br>• `renameProjectFile(filename, section)` *(dòng 1294)*: Đổi tên đơn lẻ qua `prompt()`.<br>• `showBatchRenameModal()` *(dòng 1317)*: Khởi tạo dữ liệu, nhận diện pattern tự động và mở modal.<br>• `executeBatchRename()` *(dòng 1348)*: Thu thập input từ modal, gửi payload lên API và xử lý toast/reload. |
| **Xử lý Backend (Flask Route)** | `webui/routes/projects.py` | <br>• `POST /api/projects/<slug>/rename` *(dòng 1044)*: Đổi tên 1 file.<br>• `POST /api/projects/<slug>/rename-batch` *(dòng 1087)*: Đổi tên hàng loạt file theo pattern số thứ tự. |

---

## 2. BỐ TRÍ CỦA MODALBOX DIALOG (#batch-rename-modal)

### 2.1. Cấu trúc DOM & Bố cục Thị giác
Modalbox được đặt trong một overlay tối mờ toàn màn hình (`bg-black-70`, cố định `fixed absolute--fill`, `z-index: var(--z-modal)`). Khung hộp thoại trung tâm dùng nền trắng, bo góc 12px (`br3`), đổ bóng nổi (`shadow-5`), chiều rộng tối đa `mw6` (~32rem / 512px) kèm hiệu ứng nảy nhẹ `animate-pop`.

```text
+------------------------------------------------------------+
| Đổi tên hàng loạt                                          | (Tiêu đề f4 fw6, gạch chân phân cách)
+------------------------------------------------------------+
| Pattern đổi tên                                            |
| [ Chuong{N}                                              ] | (#batch-rename-pattern)
| Dùng {N} để đánh số thứ tự. VD: Chuong{N} -> Chuong01,...  | (Gợi ý nhỏ)
+------------------------------------------------------------+
| Bắt đầu từ                                                 |
| [ 1                                                      ] | (#batch-rename-start - type number)
+------------------------------------------------------------+
| Zero-pad (số chữ số)                                       |
| [ 2                                                      ] | (#batch-rename-zeropad - type number, min 0 max 10)
+------------------------------------------------------------+
| File đã chọn (X file)                                      | (#batch-rename-count)
| +--------------------------------------------------------+ |
| | Chuong_01.txt                                          | | (#batch-rename-preview - cuộn tối đa 150px)
| | Chuong_02.txt                                          | |
| +--------------------------------------------------------+ |
+------------------------------------------------------------+
|                                   [ Hủy bỏ ]   [ Đổi tên ] | (Footer: Nút Hủy và Nút Xác nhận)
+------------------------------------------------------------+
```

### 2.2. Chi tiết các trường dữ liệu trên Dialog
1. **Tiêu đề (`<h3>`)**: "Đổi tên hàng loạt" (có border-bottom xám mờ).
2. **Trường Pattern (`#batch-rename-pattern`)**:
   - Placeholder: `VD: Chuong{N} (tăng từ 1, zero-pad theo số digits)`.
   - Gợi ý (`<small>`): "Dùng {N} để đánh số thứ tự. VD: Chuong{N} -> Chuong01, Chuong02, ...".
3. **Trường Bắt đầu từ (`#batch-rename-start`)**:
   - Input `type="number"`, `value="1"`, `min="0"`.
4. **Trường Zero-pad (`#batch-rename-zeropad`)**:
   - Input `type="number"`, `value="2"`, `min="0"`, `max="10"` (quy định số lượng chữ số, vd: 2 chữ số thì 1 thành `01`).
5. **Danh sách file đã chọn & Xem trước (`#batch-rename-count`, `#batch-rename-preview`)**:
   - Hiển thị tổng số file đã tick chọn: `File đã chọn (N file)`.
   - Khung xem trước dạng danh sách cuộn dọc (`overflow-y-auto`, `max-height: 150px`, nền xám nhạt `bg-near-white`, viền mảnh `b--black-10`).
6. **Thanh nút bấm hành động (Action Footer)**:
   - Nút **Hủy bỏ** (`.nt-btn .nt-btn-outline`): Gọi `ModalManager.hide('batch-rename-modal')`.
   - Nút **Đổi tên** (`#btn-confirm-batch-rename` / `.nt-btn .nt-btn-success`): Gọi `ProjectManager.executeBatchRename()`.

---

## 3. GIẢI THUẬT VÀ LUỒNG HOẠT ĐỘNG (ALGORITHM & WORKFLOW)

### 3.1. Luồng kích hoạt và Tự động nhận diện mẫu (Auto-detect Pattern)
Khi người dùng chọn các file và bấm nút đổi tên hàng loạt (`ProjectManager.showBatchRenameModal()`):
1. **Kiểm tra điều kiện**:
   - Nếu chưa mở dự án -> Báo lỗi toast: *"Chưa chọn dự án!"*.
   - Lấy danh sách file đang được chọn từ tab hiện tại (`getSelectedFilesForCurrentTab()`).
   - Nếu số file chọn = 0 -> Báo lỗi toast: *"Chọn file cần đổi tên trước!"*.
2. **Cập nhật UI**:
   - Điền số lượng file vào `#batch-rename-count`.
   - Render danh sách tên file cũ vào `#batch-rename-preview`.
3. **Giải thuật Auto-detect Pattern từ file đầu tiên**:
   - Lấy file đầu tiên trong danh sách `first = files[0]`.
   - Chạy Regex tách 3 phần: `first.match(/^(.*?)(\d+)(.*)$/)`.
     - `prefix = match[1]`: Phần tiền tố trước cụm số.
     - `num = match[2]`: Cụm số đầu tiên gặp phải.
     - `suffix = match[3]`: Phần hậu tố sau cụm số (thường bao gồm cả đuôi mở rộng `.txt`, `.md`).
   - **Nếu match**:
     - Pattern tự sinh: `patternEl.value = prefix + '{N}' + suffix`.
     - Start value: `batch-rename-start.value = parseInt(num)`.
     - Zeropad value: `batch-rename-zeropad.value = num.length`.
   - **Nếu không match số nào**:
     - Mặc định gán: `patternEl.value = '{N}'`.
4. **Hiển thị Dialog**: Gọi `ModalManager.show('batch-rename-modal')`.

---

### 3.2. Luồng gửi yêu cầu từ Client (`ProjectManager.executeBatchRename()`)
1. Lấy giá trị: `pattern`, `start`, `zeropad`, danh sách `oldNames`.
2. Kiểm tra `pattern`: Nếu rỗng -> Báo toast: *"Nhập pattern đổi tên!"*.
3. Xác định phân vùng (`section`): Dựa trên tab đang mở (`sources`, `translated`, hoặc `spelling`).
4. Khóa nút bấm: `btn.disabled = true; btn.textContent = 'Đang đổi tên...'`.
5. Gửi POST HTTP tới endpoint:  
   `POST /api/projects/{slug}/rename-batch`  
   **Payload JSON**:
   ```json
   {
     "section": "sources",
     "pattern": "Chuong_{N}.txt",
     "start": 1,
     "zeropad": 2,
     "old_names": ["raw_1.txt", "raw_2.txt"]
   }
   ```
6. Xử lý phản hồi từ server:
   - Nếu thành công: Hiển thị toast thông báo số file đổi tên thành công (`Đã đổi tên X/Y file`).
   - Ẩn modal: `ModalManager.hide('batch-rename-modal')`.
   - Xóa selection và nạp lại danh sách file dự án: `ProjectManager.openProject(slug)`.
   - Phục hồi trạng thái nút bấm trong khối `finally`.

---

### 3.3. Giải thuật xử lý Backend (`rename_batch` trong `projects.py`)
Mã nguồn duyệt tuần tự qua từng file trong danh sách `old_names` với các bước kiểm tra an toàn nghiêm ngặt:

1. **Sinh tên mới**:
   - Với mỗi file ở vị trí `idx`:
     `num = start + idx`
     `num_str = str(num).zfill(zeropad) if zeropad > 0 else str(num)`
     `new_name = pattern.replace("{N}", num_str)`
   - **Bảo toàn phần mở rộng**: Nếu `new_name` không có dấu `.` nhưng `old_name` có đuôi:
     `new_name = f"{new_name}.{old_name.rsplit('.', 1)[-1]}"`
2. **Kiểm tra an toàn đường dẫn**:
   - `old_path = (pdir / section / old_name).resolve()`
   - `new_path = (pdir / section / new_name).resolve()`
   - Kiểm tra `str(path).startswith(str((pdir / section).resolve()))` để chống Path Traversal.
3. **Kiểm tra trạng thái tệp**:
   - Nếu `not old_path.exists()` -> Lỗi: *"File không tồn tại"*.
   - Nếu `new_path.exists()` -> Lỗi: *"Tên file đã tồn tại"* (tránh ghi đè file hiện có).
4. **Đổi tên vật lý**:
   - `old_path.rename(new_path)`
5. **Đồng bộ tự động (Auto-sync) sang `translated`**:
   - Nếu `section == "sources"`: Kiểm tra `old_trans = pdir / "translated" / old_name`. Nếu tồn tại và `new_trans` chưa tồn tại -> tự động gọi `old_trans.rename(new_trans)` để đảm bảo tính nhất quán giữa file nguồn và bản dịch.
6. **Tổng kết**: Trả về danh sách kết quả chi tiết từng file và số lượng thành công `renamed`.

---

## 4. CÁC ĐIỂM ĐẶC BIỆT CỦA CƠ CHẾ ĐỔI TÊN TRONG NOVEL-TRANSLATOR

1. **Đồng bộ tự động giữa Nguồn và Đích (`sources` -> `translated`)**:
   - Khi đổi tên file nguồn trong thư mục `sources/`, hệ thống tự động kiểm tra xem trong `translated/` có file cùng tên hay không. Nếu có, file trong `translated/` cũng được đổi tên tương ứng theo tên mới. Điều này bảo đảm không bị lệch cặp file gốc - bản dịch.
2. **Cơ chế giữ đuôi file thông minh**:
   - Nếu người dùng chỉ nhập pattern là `Chuong_{N}` mà quên gõ đuôi `.txt` hay `.md`, hệ thống backend sẽ tự động lấy đuôi mở rộng từ `old_name` gắn vào sau `new_name`.
3. **An toàn đường dẫn (Path Traversal Guard)**:
   - Cả đường dẫn cũ và mới đều được kiểm tra `resolve()` và đối chiếu tiền tố `str(pdir / section)` để ngăn chặn việc người dùng dùng `../` đổi tên tệp ra ngoài phạm vi thư mục dự án.
4. **Không đè file đã tồn tại (Conflict Guard)**:
   - Nếu `new_path.exists()`, lượt đổi tên của file đó sẽ bị hủy và báo lỗi riêng lẻ trong mảng `results`, không làm hỏng tiến trình của các file còn lại trong danh sách hàng loạt.
