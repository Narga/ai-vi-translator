# Thiết kế Hệ thống Quản lý Dự án & Cải tiến Giao diện Biên dịch Tập trung (3 Cột)

Tài liệu này đề xuất phương án thiết kế giao diện quản lý dự án mới và tái cấu trúc vùng làm việc biên dịch/kiểm chính tả thành giao diện 3 cột tập trung, dựa trên các yêu cầu của người dùng.

---

## 1. Tóm tắt Yêu cầu & Phân tích Hiện trạng

### Yêu cầu mới:
1. **Nút Quản lý dự án** nằm trên thanh điều hướng chính (Main navigation bar), bấm vào mở ra tab quản lý dự án.
2. **Giao diện Quản lý dự án** chia làm 2 phần:
   - *Bên trái*: Form tạo dự án mới (Tên tác phẩm, Tác giả, Nút khởi tạo).
   - *Bên phải*: Danh sách dự án hiển thị dạng card (Tên tác phẩm - Tác giả, Thời gian, Trạng thái/Giai đoạn, Progress bar, và các nút thao tác: Sao lưu, Mở, Xóa). Có thêm nút "Nhập dự án" ở góc trên bên phải.
3. **Màn hình Biên tập/Kiểm chính tả 3 cột**:
   - Khi mở dự án, tự động chuyển sang chế độ tập trung (không hiển thị sidebar danh sách dự án toàn cục nữa).
   - Chia làm 3 cột dọc: Cột 1 (Danh sách tập tin), Cột 2 (Editor nguồn), Cột 3 (Editor dịch/soát).
4. **Thiết kế lại khối Danh sách tập tin (Cột 1)**:
   - Đổi tên cột "Tên tệp" thành "Tập tin". Chỉ hiển thị duy nhất cột này (gộp kích thước, trạng thái và hành động vào dưới tên tập tin).
   - Hiển thị kích thước và các nút chức năng nhỏ (Dịch, Đổi tên, Xóa) ngay dưới tên file.
   - Thêm dấu check xanh (`✔️`) nếu tập tin đã hoàn thành dịch.
   - Thay thế các nút chức năng ở đầu khối (Tải lên, Chia chunk, Dịch đã chọn, v.v.) bằng các biểu tượng icon có hiển thị tooltip mô tả khi di chuột qua.
   - Hiển thị dòng trạng thái "Đã chọn X tập tin" bên cạnh tiêu đề cột "Tập tin" khi có file được tick chọn.

---

## 2. Các phương án thiết kế giao diện & Luồng xử lý (Approaches)

### Phương án 1: SPA (Single Page Application) sử dụng Alpine.js & Tachyons (Khuyên dùng)
- **Cơ chế**: Tận dụng cơ chế chuyển đổi tab hiện tại của WebUI bằng cách ẩn/hiện các tab thông qua class `.nt-tab-content` (sử dụng thuộc tính `data-tab` và lưu trạng thái vào `localStorage`).
- **Ưu điểm**:
  - Tốc độ chuyển đổi tức thì, giữ nguyên trải nghiệm mượt mà không cần reload trang.
  - Phù hợp hoàn hảo với hệ thống Alpine.js đang chạy trên dự án.
  - Dễ dàng quản lý các trạng thái như `currentProject` toàn cục trong bộ nhớ client.
- **Nhược điểm**: Cần thiết kế mã CSS cẩn thận để tránh xung đột layout khi chuyển đổi giữa chế độ thường và chế độ 3 cột.

### Phương án 2: Đa trang (Multi-page) kết hợp Flask Routing
- **Cơ chế**: Tách trang Quản lý dự án thành một route riêng biệt (ví dụ `/projects`), khi chọn dự án sẽ redirect sang trang làm việc chính (`/workspace`).
- **Ưu điểm**: Phân tách mã HTML rõ ràng hơn ở phía backend.
- **Nhược điểm**: Reload trang mỗi khi đổi dự án, làm giảm trải nghiệm người dùng, mất đi tính liên tục của ứng dụng SPA hiện tại.

*👉 **Khuyến nghị**: Chọn **Phương án 1** để tối ưu hóa trải nghiệm người dùng và tận dụng 100% kiến trúc frontend hiện tại.*

---

## 3. Thiết kế kỹ thuật chi tiết (Detailed Design)

### A. Giao diện Quản lý dự án (Tab mới `#projects`)
- Thêm file partial mới `webui/templates/partials/tab_projects.html`.
- Định dạng CSS 2 cột sử dụng Flexbox của Tachyons:
  ```html
  <div class="flex flex-row gap-4 w-100 h-100 overflow-y-auto pa4">
      <!-- Cột trái: Tạo dự án mới (w-40) -->
      <div class="w-40 bg-white br3 border b--black-10 shadow-sm pa4">
          <h2 class="f3 fw6 text-main tc">Tạo dự án dịch mới</h2>
          <p class="f7 gray tc mb4">Bắt đầu bằng cách nhập thông tin cho dự án sách của bạn.</p>
          ...
      </div>
      <!-- Cột phải: Danh sách dự án (w-60) -->
      <div class="w-60 bg-white br3 border b--black-10 shadow-sm pa4">
          <div class="flex justify-between items-center mb3">
              <h2 class="f3 fw6 text-main">Quản lý dự án</h2>
              <button class="nt-btn nt-btn-secondary f7" onclick="importProject()">📥 Nhập dự án</button>
          </div>
          <div id="project-cards-container" class="flex flex-column gap-3">
              <!-- Danh sách project card được render động -->
          </div>
      </div>
  </div>
  ```

### B. Tái cấu trúc cấu trúc dữ liệu dự án (`project.json`)
Để lưu trữ thông tin "Tên tác phẩm" và "Tác giả" một cách có cấu trúc mà không phá vỡ tính tương thích ngược:
- Trong `project.json`, bổ sung 2 trường:
  ```json
  "book_title": "Bịp bợm bằng thống kê",
  "author": "Darrell Huff"
  ```
- Trường `name` chính thức của dự án sẽ được tự động ghép: `name = f"{book_title} - {author}"`.
- Các dự án cũ (chưa có `book_title` và `author`) sẽ tự động parse từ trường `name` cũ (tách bằng dấu `-`) để hiển thị khớp giao diện mới.

### C. Layout 3 cột trong Tab Biên tập & Kiểm chính tả
Thay vì hiển thị danh sách file dạng bảng rộng ở trên và 2 editor ở dưới, ta sẽ thiết kế cấu trúc 3 cột dọc chạy song song:
- **Cột 1 (w-25):** Danh sách tập tin. Được tối ưu hóa không gian dọc, có thanh cuộn độc lập.
- **Cột 2 & 3 (w-75 chia đôi):** 2 Editor (Nguồn và Bản dịch/Soát).
- **Mã CSS tinh chỉnh:**
  ```css
  .workspace-layout-3col {
      display: flex;
      flex-direction: row;
      gap: 1rem;
      height: 100%;
      align-items: stretch;
      overflow: hidden;
  }
  .file-list-sidebar {
      width: 280px;
      flex-shrink: 0;
      display: flex;
      flex-direction: column;
      border-right: 1px solid var(--border);
  }
  .editors-container-2col {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
  }
  ```

### D. Cải tiến danh sách tập tin (Cột 1)
- Header của cột:
  - Text "Tập tin" thay thế cho "Tên tệp".
  - Một vùng nhỏ hiển thị: `Đã chọn X tập tin` (chỉ hiển thị khi có file được tick).
  - Thanh công cụ chứa các icon với tooltip:
    - `Tải lên` -> Biểu tượng 📤
    - `Chia chunk` -> Biểu tượng ✂️
    - `Dịch đã chọn` / `Soát đã chọn` -> Biểu tượng 🚀 / 🔤
- Mỗi dòng tệp tin:
  ```html
  <div class="file-item-row flex items-start gap-2 pa2 bb b--black-05">
      <input type="checkbox" class="mt1">
      <div class="flex-auto">
          <div class="fw6 blue pointer truncate flex items-center">
              Han Men Gui Jiang.txt
              <span class="green ml1" title="Đã dịch xong">✔️</span>
          </div>
          <div class="flex items-center gap-2 f7 gray mt1">
              <span>297.9 KB</span>
              <span class="silver">|</span>
              <button class="link-btn" onclick="translateFile(...)">🚀 Dịch</button>
              <button class="link-btn" onclick="renameFile(...)">✏️ Đổi tên</button>
              <button class="link-btn red" onclick="deleteFile(...)">🗑️ Xóa</button>
          </div>
      </div>
  </div>
  ```

---

## 4. Đề xuất Ý kiến của AI & Đánh giá Tính năng

### 👍 Đề xuất bổ sung (Tăng hiệu quả):

| # | Tính năng | Quyết định | Ghi chú |
|---|-----------|------------|---------|
| 1 | **Auto-save trong Editor** | ✅ CHỈ editor Bản dịch (`result-text`) | Tự động lưu sau 10 giây không thao tác hoặc khi mất focus (blur). Editor nguồn là file gốc, không tự động ghi đè. |
| 2 | **Dirty State Indicator** | ✅ Giữ nguyên implementation hiện tại | Module `DirtyState` đã có trong `main.js:26-45`. Cần mở rộng để hiển thị `*` cạnh tên file trong danh sách 3 cột. |
| 3 | **Phím tắt Ctrl+S** | ✅ Implement | Lưu bản dịch khi đang focus trong editor. |
| 4 | **Phím tắt Ctrl+Enter** | ❌ LOẠI BỎ | Có thể conflict khi user đang gõ text. Không cần thiết. |
| 5 | **Drag-and-drop upload** | ✅ THÊM MỚI | Kéo thả file trực tiếp vào sidebar danh sách file để upload. Hiện đại hơn nút "Tải lên". |

### 👎 Đề xuất loại bỏ / Giản lược (Hiệu quả thấp):

| # | Tính năng | Quyết định | Lý do |
|---|-----------|------------|-------|
| 1 | **Nút "Chi tiết"** | ✅ LOẠI BỎ | Đã có tab Quản lý dự án tập trung. Nút này dư thừa. |
| 2 | **Bảng "Đã soát" riêng** | ✅ GỘP | Gộp vào 1 cột "Tập tin", phân biệt bằng nhãn trạng thái (✔️ Xong / ⏳ Chờ). Đồng bộ với tab Biên tập. |

---

## 5. Quyết định Thiết kế đã Xác nhận (Confirmed Design Decisions)

> [!NOTE]
> Các quyết định thiết kế đã được người dùng phê duyệt:

1. **Vị trí nút "Quản lý dự án"**:
   - Nút "Quản lý dự án" nằm **cạnh nút "Dự án" cũ** trên Main navigation bar.
   - Nút "Dự án" cũ và tính năng cũ vẫn được giữ nguyên hoạt động bình thường cho đến khi tính năng Quản lý dự án mới hoàn tất.
   - Quản lý dự án là thiết kế hoàn toàn mới, tối ưu hóa mã nguồn và công nghệ song song với bản cũ.

2. **Cách xác định "Giai đoạn dự án"**:
   - Chỉ có 2 trạng thái: **Đang thực hiện** và **Hoàn thành**.
   - Trạng thái được tính toán động: dự án được coi là "Hoàn thành" khi toàn bộ các tập tin bên trong đã được dịch xong, soát xong, hoặc đánh dấu là hoàn thành. Chỉ cần có 1 tập tin chưa ở trạng thái "Xong" thì dự án vẫn ở trạng thái "Đang thực hiện".

3. **Gộp trạng thái Kiểm chính tả**:
   - Thống nhất **gộp danh sách "Chưa soát" và "Đã soát"** trong tab Kiểm chính tả thành một cột "Tập tin" duy nhất, phân biệt trạng thái bằng các biểu tượng tương tự như tab Biên tập.

4. **Biểu tượng hành động đầu cột Tập tin**:
   - Sử dụng các icon kèm tooltip: Tải lên (`📤`), Chia chunk (`✂️`), Dịch đã chọn (`🚀`), Ghép tập tin (`🔗`), Soát lỗi đã chọn (`🔤`).

5. **Auto-save cho Editor Bản dịch**:
   - Chỉ auto-save editor `result-text` (Bản dịch).
   - Trigger: Sau 10 giây không thao tác HOẶC khi editor mất focus (blur).
   - Hiển thị indicator "Đang lưu..." khi auto-save chạy.
   - Không auto-save editor `source-text` (Nguồn) vì đây là file gốc.

6. **Phím tắt**:
   - `Ctrl + S`: Lưu bản dịch (khi focus trong editor).
   - Không có phím tắt cho "Dịch lại" để tránh conflict.

7. **Drag-and-drop Upload**:
   - Kéo thả file từ OS vào vùng sidebar danh sách file (Cột 1).
   - Hiển thị visual feedback (border highlight) khi đang kéo file vào.
   - Hỗ trợ multiple files cùng lúc.


---

## 6. Kế hoạch Kiểm thử & Xác thực (Verification Plan)

### Kiểm thử thủ công:
1. Truy cập WebUI, click vào nút "Quản lý dự án" mới trên thanh điều hướng, kiểm tra xem giao diện 2 cột có hiển thị đúng mockup không.
2. Thực hiện tạo một dự án mới từ form bên trái, kiểm tra xem dự án mới có xuất hiện ngay ở danh sách bên phải không.
3. Nhấp "Mở dự án" từ một card dự án, kiểm tra xem có tự chuyển trang sang Workspace ở chế độ tập trung (không có sidebar dự án cũ) không.
4. Mở tab Biên tập và Kiểm chính tả, kiểm tra bố cục 3 cột (Danh sách file bên trái, 2 editor bên phải) xem có bị vỡ layout trên các độ phân giải màn hình khác nhau hay không.
5. Kiểm tra chức năng các nút hành động con (Dịch, Đổi tên, Xóa) ngay dưới tên file trong cột 1 xem có hoạt động chính xác không.

---

## 7. Kế hoạch Triển khai Chi tiết (Detailed Implementation Plan)

> [!IMPORTANT]
> Phần này dành cho model thực thi. Tuân thủ nghiêm ngặt thứ tự các bước.

### Phase 1: Backend - Cập nhật API & Data Structure

#### Bước 1.1: Cập nhật `project.json` schema
**File:** `webui/routes/projects.py`

1. Sửa hàm `create_project()` (dòng 104-173):
   - Thêm parameter `book_title` và `author` từ request body
   - Tự động tạo `name = f"{book_title} - {author}"` nếu cả 2 đều có
   - Lưu `book_title` và `author` vào meta dict

```python
# Trong hàm create_project(), thay thế phần lấy name:
data = request.json
book_title = data.get("book_title", "").strip()
author = data.get("author", "").strip()
name = data.get("name", "").strip()

# Nếu có book_title, tự động tạo name
if book_title:
    author_display = author if author else "Vô danh"
    name = f"{book_title} - {author_display}"
elif not name:
    return jsonify({"error": "Tên tác phẩm hoặc tên dự án không được trống"}), 400

# Đảm bảo lưu book_title và author vào meta dict:
meta = {
    "name": name,
    "book_title": book_title if book_title else (name.split(" - ", 1)[0] if " - " in name else name),
    "author": author if author else (name.split(" - ", 1)[1] if " - " in name else ""),
    "slug": slug,
    "description": data.get("description", ""),
    "genre": data.get("genre", ""),
    "status": "active",
    "created_at": datetime.now().isoformat(),
    "updated_at": datetime.now().isoformat(),
}
```

2. Sửa hàm `get_project()` (dòng 176-246):
   - Thêm logic parse backward compatibility cho project cũ

```python
# Sau khi load meta, thêm logic parse:
if "book_title" not in meta:
    # Parse từ name cũ: "Tên tác phẩm - Tác giả"
    parts = meta.get("name", "").split(" - ", 1)
    meta["book_title"] = parts[0] if parts else meta.get("name", "")
    meta["author"] = parts[1] if len(parts) > 1 else ""
```

3. Sửa hàm `list_projects()` (dòng 88-101):
   - Thêm logic tương tự backward compatibility

#### Bước 1.2: Thêm API Import/Export Project
**File:** `webui/routes/projects.py`

Thêm 2 endpoint mới sau hàm `delete_archive()` (sau dòng 422):

```python
@projects_bp.route("/api/projects/<slug>/export", methods=["GET"])
def export_project(slug):
    """Export dự án thành file zip để tải về."""
    pdir = _get_project_dir(slug)
    if not pdir.exists():
        return jsonify({"error": "Dự án không tồn tại"}), 404
    
    import tempfile
    import zipfile
    from io import BytesIO
    
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in pdir.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                arcname = file_path.relative_to(pdir.parent)
                zf.write(file_path, arcname)
    
    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f"{slug}.zip"
    )


@projects_bp.route("/api/projects/import", methods=["POST"])
def import_project():
    """Nhập dự án từ file zip."""
    if "file" not in request.files:
        return jsonify({"error": "Không tìm thấy file"}), 400
    
    f = request.files["file"]
    if not f.filename or not f.filename.endswith('.zip'):
        return jsonify({"error": "File phải là định dạng .zip"}), 400
    
    import zipfile
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        zip_path = Path(tmp_dir) / "import.zip"
        f.save(str(zip_path))
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(tmp_dir)
        
        # Tìm thư mục dự án trong zip
        extracted_dirs = [d for d in Path(tmp_dir).iterdir() if d.is_dir()]
        if not extracted_dirs:
            return jsonify({"error": "File zip không hợp lệ"}), 400
        
        project_dir = extracted_dirs[0]
        slug = project_dir.name
        
        # Kiểm tra trùng lặp
        dest_dir = _get_project_dir(slug)
        if dest_dir.exists():
            return jsonify({"error": f"Dự án '{slug}' đã tồn tại"}), 409
        
        # Copy vào workspace
        shutil.copytree(project_dir, dest_dir)
        
        meta = _load_project_meta(slug)
        if meta:
            return jsonify({"success": True, "slug": slug, "meta": meta})
        else:
            return jsonify({"error": "Không tìm thấy project.json trong file"}), 400
```

#### Bước 1.3: Thêm API lấy thống kê dự án cho card
**File:** `webui/routes/projects.py`

Sửa hàm `list_projects()` để trả về thêm thông tin cần thiết cho card display:

```python
@projects_bp.route("/api/projects")
def list_projects():
    """Liệt kê tất cả dự án với thông tin đầy đủ cho card display."""
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    projects = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = _load_project_meta(d.name)
        if not meta:
            continue
        stats = _project_stats(d.name)
        
        # Backward compatibility
        if "book_title" not in meta:
            parts = meta.get("name", "").split(" - ", 1)
            meta["book_title"] = parts[0] if parts else meta.get("name", "")
            meta["author"] = parts[1] if len(parts) > 1 else ""
        
        # Đọc danh sách tập tin nguồn thực tế để so sánh trạng thái
        src_dir = d / "sources"
        source_files = [f for f in src_dir.rglob("*") if f.is_file() and not f.name.startswith(".")] if src_dir.exists() else []
        file_status = meta.get("file_status", {})
        
        # Dự án được coi là Hoàn thành khi toàn bộ file nguồn đều có status là "Xong"
        all_done = len(source_files) > 0 and all(
            file_status.get(str(f.relative_to(src_dir)), "Chờ") == "Xong"
            for f in source_files
        )
        status = "Hoàn thành" if all_done else "Đang thực hiện"
        
        # Tính progress percentage
        total_files = len(source_files)
        translated_files = stats.get("translated_count", 0)
        progress = (translated_files / total_files * 100) if total_files > 0 else 0
        
        projects.append({
            **meta, 
            "slug": d.name, 
            **stats,
            "progress": round(progress, 1),
            "status": status
        })
    return jsonify(projects)
```

### Phase 2: Frontend - Tạo Tab Quản lý Dự án Mới

#### Bước 2.1: Tạo file partial mới
**File mới:** `webui/templates/partials/tab_projects.html`

Tạo file HTML với cấu trúc 2 cột (Form tạo dự án + Danh sách card):

```html
<!-- ==================== TAB: QUẢN LÝ DỰ ÁN ==================== -->
<section id="tab-projects" class="nt-tab-content dn">
    <div class="flex flex-row gap-4 w-100 h-100 overflow-y-auto pa4">
        <!-- Cột trái: Tạo dự án mới -->
        <div class="w-40 bg-white br3 border b--black-10 shadow-sm pa4">
            <h2 class="f3 fw6 dark-gray tc">Tạo dự án dịch mới</h2>
            <p class="f7 gray tc mb4">Bắt đầu bằng cách nhập thông tin cho dự án sách của bạn.</p>
            
            <div class="flex flex-column gap3">
                <div>
                    <label class="f7 fw6 gray db mb1">Tên tác phẩm *</label>
                    <input type="text" id="new-project-book-title" class="w-100 pa2 ba b--black-20 br2 f6 outline-0" placeholder="Nhập tên tác phẩm...">
                </div>
                <div>
                    <label class="f7 fw6 gray db mb1">Tác giả</label>
                    <input type="text" id="new-project-author" class="w-100 pa2 ba b--black-20 br2 f6 outline-0" placeholder="Nhập tên tác giả...">
                </div>
                <div>
                    <label class="f7 fw6 gray db mb1">Thể loại</label>
                    <select id="new-project-genre-new" class="w-100 pa2 ba b--black-20 br2 f6 outline-0">
                        <option value="">— Chọn thể loại —</option>
                    </select>
                </div>
                <div>
                    <label class="f7 fw6 gray db mb1">Mô tả</label>
                    <textarea id="new-project-desc-new" class="w-100 pa2 ba b--black-20 br2 f6 outline-0 no-resize" rows="3" placeholder="Mô tả ngắn về dự án..."></textarea>
                </div>
                <button class="pointer ph4 pv2 bn white bg-blue br2 fw6 shadow-1 hover-bg-dark-blue f6 mt2" onclick="ProjectManager.createNewProject()">
                    Khởi tạo dự án
                </button>
            </div>
        </div>
        
        <!-- Cột phải: Danh sách dự án -->
        <div class="w-60 bg-white br3 border b--black-10 shadow-sm pa4">
            <div class="flex justify-between items-center mb3">
                <h2 class="f3 fw6 dark-gray">Quản lý dự án</h2>
                <div class="flex gap-2">
                    <input type="file" id="import-project-file" class="dn" accept=".zip" onchange="ProjectManager.importProject()">
                    <button class="pointer ph3 pv1 f7 ba b--black-20 bg-white br2 shadow-sm hover-bg-near-white" onclick="document.getElementById('import-project-file').click()">
                        📥 Nhập dự án
                    </button>
                </div>
            </div>
            <div id="project-cards-container" class="flex flex-column gap3 overflow-y-auto" style="max-height: calc(100vh - 200px);">
                <!-- Cards được render động bởi JS -->
                <div class="pa4 tc silver i">Đang tải...</div>
            </div>
        </div>
    </div>
</section>
```

#### Bước 2.2: Cập nhật header.html để thêm nút "Quản lý dự án"
**File:** `webui/templates/partials/header.html`

Thêm nút mới vào nav section (dòng 28-35):

```html
<!-- Navigation (Center) -->
<nav class="header-center flex justify-center">
    <a href="#workspace" class="nav-link active" data-tab="workspace">Dự án</a>
    <a href="#projects" class="nav-link" data-tab="projects">Quản lý dự án</a>  <!-- THÊM MỚI -->
    <a href="#config" class="nav-link" data-tab="config">Cấu hình</a>
    <a href="#prompts" class="nav-link" data-tab="prompts">Chỉ dẫn AI</a>
    <a href="#plugins" class="nav-link" data-tab="plugins">Công cụ</a>
    <a href="#logs" class="nav-link" data-tab="logs">Nhật ký</a>
    <a href="#archive" class="nav-link" data-tab="archive">Lưu trữ</a>
</nav>
```

#### Bước 2.3: Cập nhật index.html để include partial mới
**File:** `webui/templates/index.html`

Thêm dòng include sau tab_workspace:

```html
{% include 'partials/header.html' %}
{% include 'partials/tab_workspace.html' %}
{% include 'partials/tab_projects.html' %}  <!-- THÊM MỚI -->
{% include 'partials/tab_config.html' %}
{% include 'partials/tab_prompts.html' %}
{% include 'partials/tab_plugins.html' %}
{% include 'partials/tab_archive.html' %}
{% include 'partials/tab_logs.html' %}
{% include 'partials/modals.html' %}
{% include 'partials/footer.html' %}
```

### Phase 3: Frontend - Tái cấu trúc Layout 3 Cột

#### Bước 3.1: Thêm CSS mới
**File:** `webui/static/css/style.css`

Thêm vào cuối file:

```css
/* ============================================= */
/* PROJECT MANAGEMENT CARDS                      */
/* ============================================= */
.project-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
    transition: all 0.2s ease;
}

.project-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transform: translateY(-2px);
}

.project-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
}

.project-card-title {
    font-size: 1.1rem;
    font-weight: 600;
    color: #333;
    margin: 0;
}

.project-card-author {
    font-size: 0.85rem;
    color: #666;
    margin: 4px 0 0 0;
}

.project-card-meta {
    display: flex;
    gap: 16px;
    font-size: 0.8rem;
    color: #888;
    margin-bottom: 12px;
}

.project-card-progress {
    height: 8px;
    background: #e0e0e0;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 12px;
}

.project-card-progress-bar {
    height: 100%;
    background: linear-gradient(90deg, #4CAF50, #8BC34A);
    transition: width 0.3s ease;
}

.project-card-actions {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
}

/* ============================================= */
/* 3-COLUMN WORKSPACE LAYOUT                     */
/* ============================================= */
.workspace-layout-3col {
    display: flex;
    flex-direction: row;
    gap: 0;
    height: 100%;
    align-items: stretch;
    overflow: hidden;
}

.file-list-sidebar {
    width: 280px;
    flex-shrink: 0;
    display: flex;
    flex-direction: column;
    border-right: 1px solid #e0e0e0;
    background: white;
}

.file-list-sidebar-header {
    padding: 12px;
    border-bottom: 1px solid #e0e0e0;
    background: #f5f5f5;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.file-list-sidebar-content {
    flex: 1;
    overflow-y: auto;
    padding: 8px;
}

.editors-container-2col {
    flex: 1;
    display: flex;
    flex-direction: row;
    min-width: 0;
}

.editor-pane-3col {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
    border-right: 1px solid #e0e0e0;
}

.editor-pane-3col:last-child {
    border-right: none;
}

/* File item compact style */
.file-item-compact {
    padding: 10px 12px;
    border-bottom: 1px solid #f0f0f0;
    cursor: pointer;
    transition: background 0.15s ease;
}

.file-item-compact:hover {
    background: #f8f9fa;
}

.file-item-compact.active {
    background: #e3f2fd;
    border-left: 3px solid #2196F3;
}

.file-item-name {
    font-weight: 600;
    color: #1976D2;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    gap: 6px;
}

.file-item-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.75rem;
    color: #888;
    margin-top: 4px;
}

.file-item-actions {
    display: flex;
    gap: 4px;
}

.file-item-actions button {
    padding: 2px 6px;
    font-size: 0.7rem;
    border: 1px solid #ddd;
    background: white;
    border-radius: 4px;
    cursor: pointer;
}

.file-item-actions button:hover {
    background: #f0f0f0;
}

/* Icon toolbar */
.icon-toolbar {
    display: flex;
    gap: 8px;
    align-items: center;
}

.icon-toolbar button {
    width: 32px;
    height: 32px;
    border: 1px solid #ddd;
    background: white;
    border-radius: 6px;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1rem;
    transition: all 0.15s ease;
}

.icon-toolbar button:hover {
    background: #f0f0f0;
    border-color: #bbb;
}

/* Status badges */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 600;
}

.status-badge.done {
    background: #e8f5e9;
    color: #2e7d32;
}

.status-badge.pending {
    background: #fff3e0;
    color: #ef6c00;
}

/* Responsive adjustments */
@media (max-width: 1200px) {
    .file-list-sidebar {
        width: 240px;
    }
}

@media (max-width: 992px) {
    .workspace-layout-3col {
        flex-direction: column;
    }
    
    .file-list-sidebar {
        width: 100%;
        max-height: 300px;
        border-right: none;
        border-bottom: 1px solid #e0e0e0;
    }
    
    .editors-container-2col {
        flex-direction: column;
    }
}
```

#### Bước 3.2: Tái cấu trúc tab_workspace.html - Phần Biên tập
**File:** `webui/templates/partials/tab_workspace.html`

Thay thế toàn bộ phần `<!-- ===== TAB BIÊN TẬP ===== -->` (dòng 46-160) bằng cấu trúc 3 cột mới:

```html
<!-- ===== TAB BIÊN TẬP (3 CỘT) ===== -->
<div x-show="activeTab === 'editor'" x-cloak class="flex-auto flex flex-column overflow-hidden">
    
    <div class="workspace-layout-3col">
        <!-- CỘT 1: DANH SÁCH TẬP TIN -->
        <div class="file-list-sidebar">
            <div class="file-list-sidebar-header">
                <div class="flex items-center gap-2">
                    <span class="f7 fw6 dark-gray uppercase tracked">Tập tin</span>
                    <span id="selected-files-count" class="f7 blue dn"></span>
                </div>
                <div class="icon-toolbar">
                    <input type="file" id="upload-source-file" class="dn" multiple onchange="uploadProjectFile()">
                    <button onclick="document.getElementById('upload-source-file').click()" title="Tải lên">📤</button>
                    <button onclick="showChunkConfig()" title="Chia chunk">✂️</button>
                    <button onclick="translateSelectedInProject()" title="Dịch đã chọn">🚀</button>
                    <button onclick="mergeTranslatedFiles()" title="Ghép tập tin">🔗</button>
                </div>
            </div>
            <div class="file-list-sidebar-content">
                <div id="file-list-3col">
                    <!-- Render động bởi JS -->
                </div>
            </div>
        </div>
        
        <!-- CỘT 2 & 3: EDITORS -->
        <div class="editors-container-2col">
            <!-- Editor Nguồn -->
            <div class="editor-pane-3col">
                <div class="pa2 bb b--black-10 flex items-center bg-near-white gap-2">
                    <span class="f7 fw6 gray uppercase tracked">Nguồn</span>
                    <div class="ml-auto flex gap-1">
                        <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="toggleWordWrap('source-text')" title="Toggle word wrap">Wrap</button>
                        <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="findInText('source-text')" title="Tìm trong văn bản">Tìm</button>
                    </div>
                </div>
                <textarea id="source-text" class="flex-auto bn pa3 f6 lh-copy outline-0 no-resize" placeholder="Chọn một file từ danh sách bên trái để nạp nội dung nguồn..." oninput="updateTokenEstimate();DirtyState.mark('source-text')"></textarea>
            </div>
            
            <!-- Editor Bản dịch -->
            <div class="editor-pane-3col">
                <div class="pa2 bb b--black-10 flex items-center bg-near-white gap-2">
                    <span class="f7 fw6 gray uppercase tracked">Bản dịch</span>
                    <div class="ml-auto flex gap-1">
                        <button class="pointer ph2 pv1 f7 ba b--silver bg-white br1 gray hover-bg-near-white fw6" onclick="showDiffView('source-text','result-text')" title="So sánh">So sánh</button>
                        <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="toggleWordWrap('result-text')" title="Toggle word wrap">Wrap</button>
                        <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="findInText('result-text')" title="Tìm trong văn bản">Tìm</button>
                        <button id="btn-save-translation" class="pointer ph2 pv1 f7 bn white bg-green br2 shadow-1 hover-bg-dark-green fw6" onclick="saveChunkTranslation()">Lưu</button>
                    </div>
                </div>
                <textarea id="result-text" class="flex-auto bn pa3 f6 lh-copy outline-0 no-resize" placeholder="Bản dịch sẽ hiển thị tại đây..." oninput="DirtyState.mark('result-text')"></textarea>
            </div>
        </div>
    </div>
    
    <!-- Token & Quick Actions (Bottom bar) -->
    <div class="flex justify-between items-center pa2 ba b--black-10 bg-near-white flex-wrap gap-2 flex-shrink-0">
        <div id="token-estimate-mini" class="dn f7 gray">
            Bản gốc: <strong id="token-char-count">0</strong> ký tự | <strong id="token-word-count">0</strong> từ | <strong id="token-estimate" class="blue">0</strong> tokens
            <span id="token-model-fit" class="ml2"></span>
        </div>
        <div class="ml-auto flex gap-2">
            <button id="btn-copy-result" class="pointer ph3 pv2 ba b--silver bg-white br2 gray hover-bg-near-white f7 fw6" onclick="copyResult()">Sao chép</button>
            <button id="download-btn" class="pointer ph3 pv2 ba b--silver bg-white br2 gray hover-bg-near-white f7 fw6" onclick="downloadResult()">Tải về</button>
            <button id="translate-btn" class="pointer ph4 pv2 bn white bg-blue br2 fw6 shadow-1 hover-bg-dark-blue f7" onclick="startTranslation()">Dịch lại</button>
        </div>
    </div>
</div>
```

#### Bước 3.3: Tái cấu trúc tab_workspace.html - Phần Kiểm chính tả
**File:** `webui/templates/partials/tab_workspace.html`

Thay thế toàn bộ phần `<!-- ===== TAB KIỂM CHÍNH TẢ ===== -->` (dòng 162-273) bằng cấu trúc gộp:

```html
<!-- ===== TAB KIỂM CHÍNH TẢ (GỘP) ===== -->
<div x-show="activeTab === 'spellcheck'" x-cloak class="flex-auto flex flex-column overflow-hidden">
    
    <div class="workspace-layout-3col">
        <!-- CỘT 1: DANH SÁCH TẬP TIN (GỘP) -->
        <div class="file-list-sidebar">
            <div class="file-list-sidebar-header">
                <div class="flex items-center gap-2">
                    <span class="f7 fw6 dark-gray uppercase tracked">Tập tin</span>
                    <span id="selected-spellcheck-count" class="f7 blue dn"></span>
                </div>
                <div class="icon-toolbar">
                    <button onclick="spellcheckSelectedInProject()" title="Soát lỗi đã chọn">🔤</button>
                </div>
            </div>
            <div class="file-list-sidebar-content">
                <div id="spellcheck-file-list-3col">
                    <!-- Render động bởi JS -->
                </div>
            </div>
        </div>
        
        <!-- CỘT 2 & 3: EDITORS -->
        <div class="editors-container-2col">
            <!-- Editor Bản dịch (trước soát) -->
            <div class="editor-pane-3col">
                <div class="pa2 bb b--black-10 flex items-center bg-near-white gap-2">
                    <span class="f7 fw6 gray uppercase tracked">Bản dịch</span>
                    <div class="ml-auto flex gap-1">
                        <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="toggleWordWrap('spell-source-text')" title="Toggle word wrap">Wrap</button>
                        <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="findInText('spell-source-text')" title="Tìm">Tìm</button>
                    </div>
                </div>
                <textarea id="spell-source-text" class="flex-auto bn pa3 f6 lh-copy outline-0 no-resize" placeholder="Chọn file để soát lỗi..." oninput="DirtyState.mark('spell-source-text')"></textarea>
            </div>
            
            <!-- Editor Đã soát -->
            <div class="editor-pane-3col">
                <div class="pa2 bb b--black-10 flex items-center bg-near-white gap-2">
                    <span class="f7 fw6 gray uppercase tracked">Bản đã soát</span>
                    <div class="ml-auto flex gap-1">
                        <button class="pointer ph2 pv1 f7 ba b--silver bg-white br1 gray hover-bg-near-white fw6" onclick="showDiffView('spell-source-text','spell-result-text')" title="So sánh">So sánh</button>
                        <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="toggleWordWrap('spell-result-text')" title="Toggle word wrap">Wrap</button>
                        <button class="ph2 pv1 f8 ba b--silver bg-white br1 pointer hover-bg-near-white" onclick="findInText('spell-result-text')" title="Tìm">Tìm</button>
                        <button id="btn-save-spellcheck" class="pointer ph2 pv1 f7 bn white bg-green br2 shadow-1 hover-bg-dark-green fw6" onclick="saveSpellcheckResult()">Lưu</button>
                    </div>
                </div>
                <textarea id="spell-result-text" class="flex-auto bn pa3 f6 lh-copy outline-0 no-resize" placeholder="Kết quả soát lỗi sẽ hiển thị tại đây..." oninput="DirtyState.mark('spell-result-text')"></textarea>
            </div>
        </div>
    </div>
    
    <!-- Actions Bottom bar -->
    <div class="flex justify-between items-center pa2 ba b--black-10 bg-near-white flex-wrap gap-2 flex-shrink-0">
        <div class="ml-auto flex gap-2">
            <button id="btn-copy-spellcheck" class="pointer ph3 pv2 ba b--silver bg-white br2 gray hover-bg-near-white f7 fw6" onclick="copySpellcheckResult()">Sao chép</button>
            <button id="download-spellcheck-btn" class="pointer ph3 pv2 ba b--silver bg-white br2 gray hover-bg-near-white f7 fw6" onclick="downloadSpellCheckResult()">Tải về</button>
            <button id="spellcheck-btn" class="pointer ph4 pv2 bn white bg-blue br2 fw6 shadow-1 hover-bg-dark-blue f7" onclick="runSpellcheck()">Soát lại</button>
        </div>
    </div>
</div>
```

#### Bước 3.4: Loại bỏ nút "Chi tiết" trong Project Header
**File:** `webui/templates/partials/tab_workspace.html`

Sửa phần Project Header Block (dòng 24-32):

```html
<!-- Project Header Block (KHÔNG CÓ NÚT CHI TIẾT) -->
<div id="project-header-block" class="ba b--black-10 br2 bg-white pa3 mb3 flex justify-between items-start shadow-1">
    <div class="flex-auto pr3" style="min-width: 0;">
        <h2 id="project-title" class="f4 ma0 dark-gray fw6">Tên dự án</h2>
        <p id="project-desc" class="f7 gray ma0 mt1" style="word-break: break-word; white-space: pre-wrap;">Mô tả dự án...</p>
    </div>
    <!-- ĐÃ LOẠI BỎ NÚT "CHI TIẾT" -->
</div>
```

### Phase 4: Frontend - JavaScript Functions

#### Bước 4.1: Thêm hàm mới vào project-manager.js
**File:** `webui/static/js/project-manager.js`

Thêm các hàm mới vào object `ProjectManager` (trước dòng `window.ProjectManager = ProjectManager;`):

```javascript
// ===== PROJECT MANAGEMENT FUNCTIONS =====

createNewProject() {
    const bookTitle = document.getElementById('new-project-book-title').value.trim();
    const author = document.getElementById('new-project-author').value.trim();
    const genre = document.getElementById('new-project-genre-new').value;
    const description = document.getElementById('new-project-desc-new').value.trim();
    
    if (!bookTitle) {
        UiHelpers.showToast('Tên tác phẩm không được trống!', 'error');
        return;
    }
    
    fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ book_title: bookTitle, author, genre, description })
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            UiHelpers.showToast(`Đã tạo dự án "${bookTitle}"`, 'success');
            // Clear form
            document.getElementById('new-project-book-title').value = '';
            document.getElementById('new-project-author').value = '';
            document.getElementById('new-project-desc-new').value = '';
            // Reload project cards
            ProjectManager.loadProjectCards();
        } else {
            UiHelpers.showToast(data.error || 'Lỗi tạo dự án', 'error');
        }
    })
    .catch(e => UiHelpers.showToast(e.message, 'error'));
},

loadProjectCards() {
    fetch('/api/projects')
    .then(r => r.json())
    .then(projects => {
        const container = document.getElementById('project-cards-container');
        if (!container) return;
        
        if (!projects.length) {
            container.innerHTML = '<div class="pa4 tc silver i">Chưa có dự án nào. Hãy tạo dự án mới!</div>';
            return;
        }
        
        container.innerHTML = projects.map(p => {
            const progressWidth = p.progress || 0;
            const statusClass = p.status === 'Hoàn thành' ? 'done' : 'pending';
            const statusText = p.status || 'Đang thực hiện';
            
            return `
            <div class="project-card">
                <div class="project-card-header">
                    <div>
                        <h3 class="project-card-title">${escapeHtml(p.book_title || p.name)}</h3>
                        ${p.author ? `<p class="project-card-author">${escapeHtml(p.author)}</p>` : ''}
                    </div>
                    <span class="status-badge ${statusClass}">${statusText}</span>
                </div>
                <div class="project-card-meta">
                    <span>📁 ${p.source_count || 0} files</span>
                    <span>✅ ${p.translated_count || 0} dịch</span>
                    <span>📅 ${p.created_at ? new Date(p.created_at).toLocaleDateString('vi-VN') : '—'}</span>
                </div>
                <div class="project-card-progress">
                    <div class="project-card-progress-bar" style="width: ${progressWidth}%"></div>
                </div>
                <div class="project-card-actions">
                    <button class="ph3 pv1 f7 ba b--silver bg-white br2 hover-bg-near-white" onclick="ProjectManager.exportProject('${p.slug}')" title="Sao lưu">💾</button>
                    <button class="ph3 pv1 f7 bn white bg-blue br2 hover-bg-dark-blue fw6" onclick="ProjectManager.openProject('${p.slug}')" title="Mở dự án">Mở</button>
                    <button class="ph3 pv1 f7 ba b--red red bg-white br2 hover-bg-washed-red" onclick="ProjectManager.deleteProjectCard('${p.slug}')" title="Xóa">🗑️</button>
                </div>
            </div>`;
        }).join('');
    })
    .catch(err => {
        console.error('Error loading project cards:', err);
        const container = document.getElementById('project-cards-container');
        if (container) container.innerHTML = '<div class="pa4 tc red">Lỗi tải danh sách dự án</div>';
    });
},

openProject(slug) {
    // Chuyển sang tab workspace và load project
    const workspaceLink = document.querySelector('[data-tab="workspace"]');
    if (workspaceLink) workspaceLink.click();
    
    setTimeout(() => {
        ProjectManager.selectProject(slug);
    }, 100);
},

exportProject(slug) {
    UiHelpers.showToast('Đang tạo file sao lưu...', 'info');
    window.location.href = `/api/projects/${slug}/export`;
},

importProject() {
    const fileInput = document.getElementById('import-project-file');
    const file = fileInput.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    UiHelpers.showToast('Đang nhập dự án...', 'info');
    
    fetch('/api/projects/import', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            UiHelpers.showToast(`Đã nhập dự án "${data.slug}"`, 'success');
            ProjectManager.loadProjectCards();
        } else {
            UiHelpers.showToast(data.error || 'Lỗi nhập dự án', 'error');
        }
        fileInput.value = '';
    })
    .catch(e => {
        UiHelpers.showToast(e.message, 'error');
        fileInput.value = '';
    });
},

async deleteProjectCard(slug) {
    if (!await showConfirm('Xóa VĨNH VIỄN dự án "' + slug + '"?', { danger: true })) return;
    
    fetch('/api/projects/' + slug, { method: 'DELETE' })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            UiHelpers.showToast('Đã xóa dự án', 'success');
            
            // Nếu dự án bị xóa đang là dự án active, dọn dẹp state
            if (window.currentProject && window.currentProject.slug === slug) {
                window.currentProject = null;
                localStorage.removeItem('nt_active_project_slug');
                const activeContent = document.getElementById('project-active-content');
                if (activeContent) activeContent.classList.add('dn');
            }
            
            ProjectManager.loadProjectCards();
        } else {
            UiHelpers.showToast(data.error || 'Lỗi xóa dự án', 'error');
        }
    });
},

// ===== 3-COLUMN FILE LIST RENDERING =====

renderFileList3Col(sources) {
    const el = document.getElementById('file-list-3col');
    if (!el) return;
    
    if (!sources || !sources.length) {
        el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file nguồn</div>';
        return;
    }
    
    el.innerHTML = sources.map(f => {
        const esc = escapeHtml(f.name);
        const isActive = window.currentProjectFile === f.name;
        const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
        const doneIcon = f.has_translation ? '<span class="green" title="Đã dịch xong">✔️</span>' : '';
        
        return `
        <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadProjectFile('${esc}','sources')">
            <div class="flex items-start gap-2">
                <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="mt1">
                <div class="flex-auto">
                    <div class="file-item-name">
                        ${esc}
                        ${doneIcon}
                    </div>
                    <div class="file-item-meta">
                        <span>${f.size_display || ''}</span>
                        <div class="file-item-actions">
                            <button onclick="event.stopPropagation();TranslationWorker.translateFileInProject('${esc}')" title="Dịch">🚀</button>
                            <button onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','sources')" title="Đổi tên">✏️</button>
                            <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','sources')" title="Xóa" class="red">🗑️</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
    }).join('');
    
    ProjectManager.updateSelectAllButton();
},

renderSpellcheckFileList3Col(sources) {
    const el = document.getElementById('spellcheck-file-list-3col');
    if (!el) return;
    
    if (!sources || !sources.length) {
        el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file</div>';
        return;
    }
    
    el.innerHTML = sources.map(f => {
        const esc = escapeHtml(f.name);
        const isActive = window.currentProjectFile === f.name;
        const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
        const status = (window.currentProject.file_status && window.currentProject.file_status[f.name]) || "Chờ";
        const statusIcon = status === "Xong" 
            ? '<span class="status-badge done">✔️ Xong</span>'
            : '<span class="status-badge pending">⏳ Chờ</span>';
        
        return `
        <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadSpellcheckFile('${esc}')">
            <div class="flex items-start gap-2">
                <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="mt1">
                <div class="flex-auto">
                    <div class="file-item-name">${esc}</div>
                    <div class="file-item-meta">
                        <span>${f.size_display || ''}</span>
                        ${statusIcon}
                        <div class="file-item-actions">
                            <button onclick="event.stopPropagation();TranslationWorker.spellcheckFileInProject('${esc}')" title="Soát lỗi AI">🔤</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
    }).join('');
}
```

#### Bước 4.2: Cập nhật hàm selectProject để render 3 cột
**File:** `webui/static/js/project-manager.js`

Trong hàm `selectProject()`, sau dòng `ProjectManager.renderProjectTranslated(data.translated || []);` (dòng 73), thêm:

```javascript
// Render 3-column file lists
ProjectManager.renderFileList3Col(data.sources || []);
ProjectManager.renderSpellcheckFileList3Col(data.sources || []);
```

#### Bước 4.3: Cập nhật main.js để load project cards
**File:** `webui/static/js/main.js`

Trong hàm `initTabs()`, thêm logic load project cards khi switch tab:

```javascript
// Trong hàm initTabs(), trong phần xử lý click:
if (targetId === 'projects') {
    ProjectManager.loadProjectCards();
}
```

Trong phần `DOMContentLoaded`, thêm dòng sau `ProjectManager.loadProjects();`:

```javascript
// Load project cards if projects tab is active
if (document.getElementById('project-cards-container')) {
    ProjectManager.loadProjectCards();
}
```

#### Bước 4.4: Thêm hàm legacy cho onclick handlers
**File:** `webui/static/js/main.js`

Thêm vào phần Legacy functions:

```javascript
function createNewProject() { ProjectManager.createNewProject(); }
function loadProjectCards() { ProjectManager.loadProjectCards(); }
function openProject(slug) { ProjectManager.openProject(slug); }
function exportProject(slug) { ProjectManager.exportProject(slug); }
function importProject() { ProjectManager.importProject(); }
```

### Phase 5: Backend - Cập nhật hàm render cho tab spellcheck

#### Bước 5.1: Cập nhật API spellcheck files
**File:** `webui/routes/projects.py`

Thêm endpoint mới để lấy trạng thái spellcheck:

```python
@projects_bp.route("/api/projects/<slug>/files/spelling")
def get_project_spelling_files(slug):
    """Lấy danh sách file đã soát lỗi."""
    pdir = _get_project_dir(slug)
    spelling_dir = pdir / "spelling"
    
    if not spelling_dir.exists():
        return jsonify([])
    
    files = []
    for f in sorted(spelling_dir.rglob("*")):
        if f.is_file() and not f.name.startswith('.'):
            rel = str(f.relative_to(spelling_dir))
            size = f.stat().st_size
            files.append({
                "name": rel,
                "path": str(f),
                "size": size,
                "size_display": f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB",
            })
    
    return jsonify(files)
```

### Phase 6: Tính năng Bổ sung - Auto-save, Phím tắt, Drag-and-drop

#### Bước 6.1: Auto-save cho Editor Bản dịch (CHỈ result-text)
**File:** `webui/static/js/project-manager.js`

Thêm object `AutoSave` vào đầu file (sau dòng khai báo `ProjectManager`):

```javascript
// ============================================================
// Auto-save Module (CHỈ cho editor Bản dịch - result-text)
// ============================================================
const AutoSave = {
    _timer: null,
    _delay: 10000, // 10 giây
    _isSaving: false,

    init() {
        const editor = document.getElementById('result-text');
        if (!editor) return;

        // Trigger khi user gõ
        editor.addEventListener('input', () => {
            this.schedule();
        });

        // Trigger khi mất focus
        editor.addEventListener('blur', () => {
            this.save();
        });
    },

    schedule() {
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this.save(), this._delay);
    },

    async save() {
        if (this._isSaving) return;
        if (!window.currentProject || !window.currentProjectFile) return;
        if (!DirtyState.isDirty('result-text')) return;

        const editor = document.getElementById('result-text');
        if (!editor) return;

        this._isSaving = true;
        this.showIndicator('Đang lưu...');

        try {
            const slug = window.currentProject.slug;
            const filename = window.currentProjectFile.name;
            const content = editor.value;

            const response = await fetch(`/api/projects/${slug}/file/translated/${filename}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });

            const data = await response.json();
            if (data.success) {
                DirtyState.clean('result-text');
                this.showIndicator('Đã lưu tự động');
                setTimeout(() => this.hideIndicator(), 2000);
            } else {
                this.showIndicator('Lỗi lưu');
            }
        } catch (err) {
            console.error('Auto-save error:', err);
            this.showIndicator('Lỗi lưu');
        } finally {
            this._isSaving = false;
        }
    },

    showIndicator(text) {
        let el = document.getElementById('auto-save-indicator');
        if (!el) {
            el = document.createElement('span');
            el.id = 'auto-save-indicator';
            el.className = 'f7 gray ml2';
            const header = document.querySelector('#result-text')?.closest('.editor-pane-3col')?.querySelector('.pa2');
            if (header) header.appendChild(el);
        }
        el.textContent = text;
        el.style.display = 'inline';
        if (text.includes('Đã lưu')) {
            el.className = 'f7 green ml2 fw6';
        } else if (text.includes('Lỗi')) {
            el.className = 'f7 red ml2 fw6';
        } else {
            el.className = 'f7 gray ml2';
        }
    },

    hideIndicator() {
        const el = document.getElementById('auto-save-indicator');
        if (el) el.style.display = 'none';
    },

    cancel() {
        clearTimeout(this._timer);
    }
};

window.AutoSave = AutoSave;
```

**File:** `webui/static/js/main.js`

Trong phần `DOMContentLoaded`, sau `ProjectManager.initProjectDialog();`:

```javascript
// Khởi tạo Auto-save
AutoSave.init();
```

#### Bước 6.2: Phím tắt Ctrl+S
**File:** `webui/static/js/main.js`

Thêm vào phần `Keyboard Navigation` (sau dòng 157):

```javascript
// Ctrl+S để lưu bản dịch
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        
        // Kiểm tra editor nào đang focus hoặc có thay đổi
        const resultText = document.getElementById('result-text');
        const spellResultText = document.getElementById('spell-result-text');
        
        if (document.activeElement === resultText || DirtyState.isDirty('result-text')) {
            EditorComponent.saveChunkTranslation();
        } else if (document.activeElement === spellResultText || DirtyState.isDirty('spell-result-text')) {
            EditorComponent.saveSpellcheckResult();
        }
    }
});
```

#### Bước 6.3: Drag-and-drop Upload
**File:** `webui/static/css/style.css`

Thêm vào cuối file:

```css
/* ============================================= */
/* DRAG AND DROP UPLOAD                          */
/* ============================================= */
.file-list-sidebar.drag-over {
    background: #e3f2fd;
    border: 2px dashed #2196F3;
}

.file-list-sidebar.drag-over::after {
    content: 'Thả file vào đây để tải lên';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(33, 150, 243, 0.9);
    color: white;
    padding: 12px 24px;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 600;
    pointer-events: none;
    z-index: 100;
}

.file-list-sidebar {
    position: relative;
}
```

**File:** `webui/static/js/project-manager.js`

Thêm hàm `initDragDrop()` vào object `ProjectManager`:

```javascript
initDragDrop() {
    const sidebar = document.querySelector('.file-list-sidebar');
    if (!sidebar) return;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        sidebar.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
        });
    });

    sidebar.addEventListener('dragenter', () => {
        sidebar.classList.add('drag-over');
    });

    sidebar.addEventListener('dragleave', (e) => {
        // Chỉ remove class khi thực sự rời khỏi sidebar
        if (!sidebar.contains(e.relatedTarget)) {
            sidebar.classList.remove('drag-over');
        }
    });

    sidebar.addEventListener('drop', (e) => {
        sidebar.classList.remove('drag-over');
        
        if (!window.currentProject) {
            UiHelpers.showToast('Vui lòng chọn dự án trước!', 'warning');
            return;
        }

        const files = e.dataTransfer.files;
        if (!files.length) return;

        // Upload từng file
        Array.from(files).forEach(file => {
            ProjectManager.uploadSingleFile(file);
        });
    });
},

async uploadSingleFile(file) {
    if (!window.currentProject) return;

    const formData = new FormData();
    formData.append('file', file);

    UiHelpers.showToast(`📤 Đang tải lên: ${file.name}...`, 'info');

    try {
        const response = await fetch(`/api/projects/${window.currentProject.slug}/upload`, {
            method: 'POST',
            body: formData
        });
        const data = await response.json();

        if (data.success) {
            UiHelpers.showToast(`Đã tải lên: ${data.filename} (${data.size_display})`, 'success');
            // Reload project để cập nhật danh sách
            ProjectManager.selectProject(window.currentProject.slug);
        } else {
            UiHelpers.showToast(data.error || 'Lỗi upload', 'error');
        }
    } catch (err) {
        UiHelpers.showToast('Lỗi upload: ' + err.message, 'error');
    }
}
```

**File:** `webui/static/js/main.js`

Trong phần `DOMContentLoaded`, sau `ProjectManager.initProjectDialog();`:

```javascript
// Khởi tạo Drag-and-drop
ProjectManager.initDragDrop();
```

#### Bước 6.4: Hiển thị Dirty State trong danh sách file
**File:** `webui/static/js/project-manager.js`

Sửa hàm `renderFileList3Col()` để hiển thị dấu `*` cạnh file đang edit:

```javascript
renderFileList3Col(sources) {
    const el = document.getElementById('file-list-3col');
    if (!el) return;
    
    if (!sources || !sources.length) {
        el.innerHTML = '<div class="pa3 tc silver i f7">Chưa có file nguồn</div>';
        return;
    }
    
    el.innerHTML = sources.map(f => {
        const esc = escapeHtml(f.name);
        const isActive = window.currentProjectFile === f.name;
        const checked = window.selectedFiles.has(f.name) ? 'checked' : '';
        const doneIcon = f.has_translation ? '<span class="green" title="Đã dịch xong">✔️</span>' : '';
        
        // Hiển thị dấu * nếu file đang có thay đổi chưa lưu
        const isDirty = isActive && DirtyState.isDirty('result-text');
        const dirtyIndicator = isDirty ? '<span class="red fw6 ml1" title="Có thay đổi chưa lưu">*</span>' : '';
        
        return `
        <div class="file-item-compact ${isActive ? 'active' : ''}" onclick="EditorComponent.loadProjectFile('${esc}','sources')">
            <div class="flex items-start gap-2">
                <input type="checkbox" ${checked} onclick="event.stopPropagation();ProjectManager.toggleProjectFile('${esc}',this.checked)" class="mt1">
                <div class="flex-auto">
                    <div class="file-item-name">
                        ${esc}${dirtyIndicator}
                        ${doneIcon}
                    </div>
                    <div class="file-item-meta">
                        <span>${f.size_display || ''}</span>
                        <div class="file-item-actions">
                            <button onclick="event.stopPropagation();TranslationWorker.translateFileInProject('${esc}')" title="Dịch">🚀</button>
                            <button onclick="event.stopPropagation();ProjectManager.renameProjectFile('${esc}','sources')" title="Đổi tên">✏️</button>
                            <button onclick="event.stopPropagation();ProjectManager.deleteProjectFile('${esc}','sources')" title="Xóa" class="red">🗑️</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>`;
    }).join('');
    
    ProjectManager.updateSelectAllButton();
}
```

### Phase 7: Kiểm thử & Xác nhận

#### Bước 7.1: Kiểm thử Backend
1. Chạy server: `python webui.py`
2. Test API tạo dự án mới với `book_title` và `author`
3. Test API list projects xem có trả về backward compatibility không
4. Test API export/import project

#### Bước 7.2: Kiểm thử Frontend
1. Mở trình duyệt, click tab "Quản lý dự án"
2. Tạo dự án mới từ form
3. Click "Mở" từ card, kiểm tra chuyển sang workspace 3 cột
4. Kiểm tra tab Biên tập: 3 cột layout, file list compact
5. Kiểm tra tab Kiểm chính tả: gộp 1 cột file
6. Kiểm tra nút "Chi tiết" đã biến mất

#### Bước 7.3: Kiểm thử Auto-save
1. Mở file bản dịch, chỉnh sửa nội dung
2. Chờ 10 giây, kiểm tra indicator "Đang lưu..." / "Đã lưu tự động"
3. Click ra ngoài editor (blur), kiểm tra auto-save trigger
4. Kiểm tra dấu `*` cạnh tên file khi có thay đổi chưa lưu

#### Bước 7.4: Kiểm thử Phím tắt
1. Focus trong editor bản dịch, nhấn `Ctrl+S`
2. Kiểm tra file được lưu thành công

#### Bước 7.5: Kiểm thử Drag-and-drop
1. Kéo file từ Finder/Explorer vào sidebar danh sách file
2. Kiểm tra visual feedback (border highlight)
3. Kiểm tra file được upload thành công
4. Kéo nhiều file cùng lúc

#### Bước 7.6: Kiểm thử Responsive
1. Thu nhỏ cửa sổ browser
2. Kiểm tra layout có responsive không
3. Kiểm tra trên mobile view

---

## 8. Quy ước Code & Lưu ý

### Quy ước:
- Sử dụng Tachyons CSS classes cho styling
- Sử dụng Alpine.js cho state management
- Giữ nguyên naming convention hiện tại (camelCase cho JS, snake_case cho Python)
- Không thêm comments除非 được yêu cầu (trừ comments trong code blocks mẫu)

### Lưu ý quan trọng:
1. **Backward Compatibility**: Luôn kiểm tra và parse project cũ không có `book_title`/`author`
2. **Error Handling**: Thêm try-catch cho tất cả API calls
3. **Performance**: Sử dụng debounce cho auto-save (nếu implement)
4. **Security**: Validate tất cả user input, prevent path traversal

### Files cần chỉnh sửa:

| # | File | Loại | Mô tả |
|---|------|------|-------|
| 1 | `webui/routes/projects.py` | Sửa | Backend APIs (CRUD, import/export, backward compatibility) |
| 2 | `webui/templates/partials/header.html` | Sửa | Thêm nút "Quản lý dự án" vào navigation |
| 3 | `webui/templates/partials/tab_projects.html` | **TẠO MỚI** | Tab Quản lý dự án (2 cột: form + card list) |
| 4 | `webui/templates/partials/tab_workspace.html` | Sửa | Layout 3 cột, loại bỏ nút "Chi tiết", gộp spellcheck |
| 5 | `webui/templates/index.html` | Sửa | Include `tab_projects.html` |
| 6 | `webui/static/css/style.css` | Sửa | CSS cho project cards, 3-column layout, drag-and-drop |
| 7 | `webui/static/js/project-manager.js` | S sửa | New functions: createProject, loadCards, openProject, export, import, dragDrop, render3Col |
| 8 | `webui/static/js/main.js` | Sửa | Auto-save init, Ctrl+S shortcut, dragDrop init, legacy functions |
