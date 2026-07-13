# Kế hoạch chi tiết: Cải tiến plugin Công cụ chuyển đổi (`plugins/epub_converter`) theo hướng hoàn toàn mới

**Ngày:** 2026-07-13  
**Phạm vi:** Triển khai plugin Công cụ chuyển đổi - thay thế eBook Kit cũ  
**Mục tiêu:** Thay eBook Kit hiện tại từ form nhập path thủ công thành workspace thao tác kiểu biên tập, dùng panel danh sách tập tin của dự án để chọn file và chạy 2 tác vụ độc lập:
- **Chuyển HTML → Markdown**
- **Chuyển Markdown → HTML**

---

## 1. Tóm tắt hiện trạng

Từ mã hiện tại:
- Workspace `eBook Kit` đã có tab riêng nhưng chỉ là form tĩnh, không dùng file panel của dự án:
  - `webui/templates/partials/workspace_ebook_kit.html`
  - `webui/static/js/ui-helpers.js`
  - `webui/routes/plugins.py`
- Danh sách tập tin kiểu biên tập, upload, drag-drop, chọn nhiều file, đổi tên, xóa, chuyển Markdown đã có sẵn trong:
  - `webui/templates/partials/tab_projects.html`
  - `webui/static/js/project-manager.js`
  - `webui/routes/projects.py`
- Plugin `plugins/epub_converter` hiện là wrapper mỏng cho 2 script cũ:
  - `plugins/epub_converter/epub_to_text/epub2text.py`
  - `plugins/epub_converter/text_to_epub/*`
- Dự án hiện **chưa tạo thư mục `input/` mặc định** khi khởi tạo project. `webui/routes/projects.py` mới tạo:
  - `sources/`
  - `translated/`
  - `prompt/`
  - `assets/`
  - `output/`

---

## 2. Định hướng triển khai được đề xuất

### 2.1. Giữ cái gì, thay cái gì

**Giữ:**
- `plugin_id = "epub_converter"` để không phải sửa lan sang config/plugin manager.
- Workspace tab `ebook-kit`.
- Hệ thống project/workspace hiện có.
- File list sidebar, multi-select, upload, drag-drop, row actions đã có.

**Thay gần như toàn bộ:**
- UI của `workspace_ebook_kit.html` → đổi thành workspace "Công cụ chuyển đổi".
- API plugin trong `webui/routes/plugins.py`.
- Logic điều phối của `plugins/epub_converter/plugin.py`.
- Cấu trúc nội bộ plugin để phục vụ workflow theo dự án thay vì convert theo path tay.

### 2.2. Phương án tổng quát

Tôi đề xuất **không làm một plugin độc lập với file browser riêng**, mà:
- tái dùng **sidebar danh sách tập tin hiện có** của workspace dự án;
- khi người dùng chuyển sang tab `eBook Kit`, panel trái vẫn là file list chuẩn của dự án;
- phần bên phải đổi thành giao diện "Công cụ chuyển đổi" với 2 nút tác vụ;
- lựa chọn file luôn dựa trên checkbox của panel trái;
- đổi cột/tab file là reset lựa chọn, đúng yêu cầu của anh.

Lý do:
- ít rủi ro hơn vì tận dụng đúng flow người dùng đã quen ở khu vực Biên tập;
- không phải dựng thêm một hệ quản lý file thứ hai;
- giảm khối lượng JS/CSS/route phải viết mới.

---

## 3. UX mục tiêu

### 3.1. Bố cục

Khi mở dự án và chuyển sang tab `eBook Kit`:
- layout giống kiểu biên tập:
  - **cột trái:** file list của toàn bộ dự án;
  - **cột phải:** vùng thao tác Công cụ chuyển đổi.
- UI chỉ có 2 nút tác vụ chính:
  - **Chuyển Markdown thành HTML**
  - **Chuyển HTML thành Markdown**

### 3.2. File list bên trái

Để đáp ứng câu "có thể thao tác với tất cả các tập tin của dự án thông qua panel danh sách tập tin", tôi đề xuất mở rộng mini-tab của file list thành:
- `input`
- `sources`
- `translated`
- `output`
- `assets`
- `spelling`

Khuyến nghị:
- trong `eBook Kit`, mặc định active mini-tab là `input`;
- trong `Biên tập`, giữ behavior hiện tại (`sources`, `translated`, `spelling`) để tránh làm vỡ UX cũ.

### 3.3. Quy tắc chọn file

- Chọn file theo checkbox ở panel trái.
- Selection chỉ có hiệu lực trong mini-tab hiện hành.
- Khi đổi mini-tab file list:
  - reset lựa chọn;
  - không nhớ các file đã chọn ở tab trước.
- Không kiểm tra "đúng định dạng hay không" theo kiểu chặn trước; plugin chỉ lọc những file nào hợp với tác vụ đang chạy.

---

## 4. Cấu trúc thư mục dự án đề xuất sau khi nâng cấp

Mỗi dự án nên có thêm:

```text
workspace/projects/<project-slug>/
├── input/
├── sources/
├── translated/
├── output/
├── assets/
└── prompt/
```

### Quy tắc tạo `input/`

- Khi tạo project mới: tạo luôn `input/`.
- Với project cũ chưa có `input/`: mọi API Công cụ chuyển đổi phải `mkdir(parents=True, exist_ok=True)` trước khi thao tác.

---

## 5. Thiết kế tác vụ 1: Chuyển HTML → Markdown

### 5.1. Mục tiêu

Tác vụ này dùng để chuyển các file HTML/XHTML được chọn thành Markdown, kết quả ghi cùng thư mục với file gốc.

### 5.2. Input người dùng

- File được chọn ở panel trái (checkbox);
- Hỗ trợ `.html`, `.htm`, `.xhtml`;
- Chỉ chạy trên mini-tab đang mở (`sources`, `translated`, `spelling`).

### 5.3. Luồng xử lý backend

Với mỗi file HTML/XHTML được chọn:
1. Gọi `core.source_normalizer.normalize_html_file()` để chuyển sang Markdown.
2. File kết quả ghi cùng thư mục, đổi đuôi sang `.md` (nếu trùng suffix thì thêm `.converted.md`).
3. Trả về relative path để log hiển thị.

### 5.4. Những gì không nên làm

- Không parse nội dung HTML sâu thêm nếu chỉ cần chuyển Markdown.
- Không ép validate cấu trúc HTML.

---

## 6. Thiết kế tác vụ 2: Chuyển Markdown → HTML

### 6.1. Mục tiêu

Từ các file Markdown được chọn trong panel trái, tạo ra file HTML/XHTML cùng thư mục.

### 6.2. Quy tắc chọn file

- Người dùng chọn file từ mini-tab đang mở.
- Tác vụ chạy trên: `input`, `sources`, `translated`.
- File HTML sinh ra nằm **cùng thư mục với file gốc**.
- Không nhớ selection giữa các mini-tab.

### 6.3. Khuyến nghị kỹ thuật

- Tái dùng logic `convert_markdown_to_html_body()` trong `plugins/epub_converter/text_to_epub/parser.py`;
- Bọc phần body vào khung XHTML/HTML tối thiểu thống nhất, thay vì chỉ dump fragment.

---

## 7. API backend đề xuất

Thay vì dồn tất cả vào 1 endpoint `direction`, nên tách rõ 2 API cho Công cụ chuyển đổi:

1. `POST /api/projects/<slug>/plugins/epub-converter` (task=`html_to_markdown`)
   - Chuyển `.html`/`.xhtml` đã chọn thành Markdown cùng thư mục

2. `POST /api/projects/<slug>/plugins/epub-converter` (task=`markdown_to_html`)
   - Chuyển `.md` đã chọn thành HTML/XHTML cùng thư mục

3. `GET /api/plugins/progress/<plugin_id>`
   - Tái dùng nguyên endpoint progress hiện tại

---

## 8. Tổ chức mã nguồn được đề xuất

### 8.1. Frontend

Sửa/chạm chủ yếu:
- `webui/templates/partials/workspace_ebook_kit.html` (đổi tên/tái cấu trúc)
- `webui/templates/partials/tab_projects.html`
- `webui/static/js/project-manager.js`
- `webui/static/js/converter-tool-plugin.js` (file mới)

### 8.2. Backend WebUI

Sửa/chạm:
- `webui/routes/plugins.py` (orchestration chính)
- `webui/routes/projects.py` (chỉ thêm `input/` vào lifecycle project)

### 8.3. Plugin nội bộ

Hiện tại `plugins/epub_converter/plugin.py` quá mỏng. Tách tối thiểu:

```text
plugins/epub_converter/
├── plugin.py
├── services/
│   ├── text_converter.py
│   └── project_paths.py
├── epub_to_text/
└── text_to_epub/
```

Mức "tối giản nhưng đủ sạch":
- `plugin.py` chỉ điều phối;
- logic nghiệp vụ thật nằm trong `services/`.

---

## 9. Tận dụng mã hiện có

Nên tái dùng:
- `ProjectManager`:
  - upload
  - drag-drop
  - multi-select
  - render file list
  - reset selection khi chuyển mini-tab
- `core/source_normalizer.py`
  - cho luồng HTML/XHTML → Markdown
- `plugins/epub_converter/text_to_epub/parser.py`
  - Markdown → HTML body
  - TXT → parse chapter
  - build XHTML

---

## 10. Kế hoạch triển khai theo pha (ĐÃ CẬP NHẬT THEO THỰC TẾ)

### Pha 1. Dọn nền dự án ✅ HOÀN TẤT
- ✅ Tạo `input/` cho project mới (cần làm ở `projects.py`)
- ✅ Auto-create `input/` cho project cũ khi chạy plugin
- ✅ Mở rộng file list để xem được các khu vực file cần cho Công cụ chuyển đổi

### Pha 2. Rebuild UI Công cụ chuyển đổi ✅ HOÀN TẤT
- ✅ Thay form path cũ bằng workspace 2 nút tác vụ
- ✅ Gắn selection từ file panel trái
- ✅ Thêm log/progress panel riêng cho Công cụ chuyển đổi
- ✅ Tách JS riêng `converter-tool-plugin.js`

### Pha 3. Chuyển HTML → Markdown ✅ HOÀN TẤT
- ✅ API chuyển `.html`/`.xhtml` đã chọn thành Markdown cùng thư mục
- ✅ Refresh file list sau khi tạo file

### Pha 4. Chuyển Markdown → HTML ✅ HOÀN TẤT
- ✅ Chuyển `.md` được chọn thành file HTML/XHTML cùng thư mục
- ✅ Refresh file list sau khi tạo file

### Pha 5. Dọn dẹp & Cải tiến (PHASE HIỆN TẠI)
- [ ] **Thêm script include cho `converter-tool-plugin.js`** (footer.html) ✅ DONE
- [ ] **Xóa route cũ `/api/projects/<slug>/convert-markdown`** (projects.py) ✅ DONE
- [ ] **Chốt lại contract trả về của `Plugin.convert()`** (plugin.py) ✅ DONE
- [ ] **Rà nhánh `task` trong `run_epub_converter()`** (plugins.py) ✅ DONE - đã review
- [ ] **Cập nhật plan file cho đúng scope mới** ✅ DONE
- [ ] **Chạy kiểm tra cú pháp tối thiểu cho Python và tải thử UI plugin** ✅ DONE

### Pha 6. Dọn phần JS chết (optional - sau phase 5)
- `ui-helpers.js` vẫn còn `runEpubToText()` và `runTextToEpub()` cũ (không còn được gọi)
- Nếu muốn sạch thì xóa, nhưng không bắt buộc cho phase này

---

## 11. Rủi ro và cách giảm rủi ro

1. **Đụng tên file khi move từ archive sang `sources/`**
   - Giải pháp: giữ relative path dưới `archive_stem`

2. **JS hiện tại của project manager gắn chặt vào 3 mini-tab cũ**
   - Giải pháp: không phá behavior cũ ở tab Biên tập; chỉ mở rộng behavior khi active workspace tab là `ebook-kit`

3. **`epub_creator.py` đang theo layout cũ (`Text`, `Styles`, `Images`, `toc.xhtml`)**
   - Giải pháp: refactor tập trung file này trước, không vá rải rác

4. **Markdown library có thể không luôn sẵn**
   - Giải pháp: reuse cơ chế phát hiện `HAS_MARKDOWN` đang có và báo lỗi rõ ràng trên UI

5. **Người dùng chọn lẫn nhiều định dạng**
   - Giải pháp: plugin chỉ lọc những file hợp với tác vụ đang chạy

---

## 12. Gợi ý của tôi

Tôi đề xuất chốt theo hướng sau:

1. **Giữ `plugin_id = epub_converter`, đổi UX thành Công cụ chuyển đổi**
   - Tránh sửa lan rộng plugin registry

2. **Dùng sidebar file list hiện có thay vì dựng file explorer mới**
   - Nhanh hơn, ít lỗi hơn

3. **Tạo `input/` như vùng staging chuẩn của project**
   - Đúng yêu cầu mới và sạch luồng

4. **Artifact cuối nên để ở `output/`, không để lẫn trong `input/`**
   - Dễ quản lý hơn

5. **Chỉ hỗ trợ normalize HTML/XHTML ở mức tối thiểu**
   - Không cố bảo tồn toàn bộ CSS/media của file gốc

---

## 13. Các điểm cần chú ý khi triển khai tiếp

1. **`converter-tool-plugin.js:133`** đang gọi `ProjectManager.openProject(slug)` rồi set tab lại `ebook-kit`.
   - Cách này hợp lý để refresh sidebar, nhưng sẽ tạo toast "Đã mở".
   - Nếu muốn UX yên hơn, có thể thay bằng refresh cục bộ, nhưng không bắt buộc.

2. **`text_converter.py:89`** đang dùng `normalize_html_file()` rồi copy kết quả sang path đích nếu khác suffix.
   - Logic này đúng ý "không kiểm tra đầu vào", nhưng cần test case:
     - File có suffix `.txt` nhưng nội dung là HTML
     - File có suffix `.md` rồi bấm HTML → Markdown
     - File có suffix `.html` rồi bấm Markdown → HTML
   - Hiện rule overwrite tránh bằng `.converted.<ext>` nếu suffix đã trùng target ở `text_converter.py:19`.

3. **`workspace_ebook_kit.html:22`** dùng class `bg-dark-green`.
   - Đã xác nhận class này tồn tại trong Tachyons (`tachyons.min.css`).

4. **`project-manager.js:1297`** hiện row action convert đã bị xóa chỉ ở `sources`.
   - `translated` và `spelling` vốn không có row convert riêng, nên không cần tìm thêm chỗ khác.

---

## 14. Những file không nên đụng thêm nếu chỉ muốn hoàn tất phase này

- `README.md`: không cần sửa để tính năng chạy được
- `translation-worker.js`, `editor-component.js`: không liên quan trực tiếp
- `core/source_normalizer.py`: hiện đã tái dùng được, chưa cần chỉnh

---

## 15. Checklist hoàn tất ngắn gọn

- [x] Thêm script include cho `converter-tool-plugin.js`
- [x] Xóa route `/api/projects/<slug>/convert-markdown`
- [x] Chốt lại contract trả về của `Plugin.convert()`
- [x] Rà nhánh `task` trong `run_epub_converter()`
- [x] Cập nhật plan file cho đúng scope mới
- [x] Chạy kiểm tra cú pháp tối thiểu cho Python và tải thử UI plugin
- [x] Thêm wrapper editor panels (fix lỗi trùng giao diện)
- [x] `isSameProject` guard trong `openProject` (fix auto-switch tab)
- [x] `refreshProjectFiles()` — refresh sidebar nhẹ không đổi wsTab
- [x] `_safe_project_file()` — chống path traversal cho plugin converter
- [x] Sửa `relative_to` path: resolve cả 2 vế trước khi tính

## 17. Phiên bản

- Plugin version: `4.0.0` (trong `plugin.py`)
- Project version: `8.6.0` (tag trên git)

## 18. Phân tích lỗi mới phát sinh và Phương án xử lý dứt điểm

### Lỗi 1: `No module named 'services.text_converter'`
- **Nguyên nhân cốt lõi**: 
  Trong `plugins/epub_converter/plugin.py` có import `from services.text_converter import ...`. 
  Mặc dù plugin đã thêm `plugins/epub_converter` vào `sys.path` nhưng ở thư mục gốc của dự án đã tồn tại gói `services/` (có file `__init__.py` và các module chính tả, API service). Do đó, trình thông dịch Python ưu tiên tìm kiếm gói `services` ở thư mục gốc trước và báo lỗi không tìm thấy `text_converter` bên trong gói đó.
- **Phương án xử lý**: 
  Sửa import thành dạng tương đối (relative import) hoặc chỉ định chính xác từ không gian tên plugin:
  ```python
  from .services.text_converter import convert_html_file, convert_markdown_file
  ```
  Điều này sẽ hướng Python tìm kiếm chính xác gói `services` cục bộ bên trong thư mục plugin `plugins/epub_converter`.

### Lỗi 2: Trùng lắp giao diện biên tập khi mới tải trang (4 panels, 2 bottom info bars)
- **Nguyên nhân cốt lõi**:
  1. Các thẻ giao diện `pm-translation-workspace`, `pm-spellcheck-workspace`, và các thanh thông tin bottom bar tương ứng đều sử dụng directive của Alpine.js: `x-show="$store.workspace.wsTab === 'editor'"`.
  2. Khi người dùng mở dự án và tab hoạt động mặc định là `editor`, Alpine.js tự động kích hoạt hiển thị tất cả các thẻ có thuộc tính trên (đè đè lên thuộc tính ẩn mặc định `style="display: none;"` của phần soát lỗi).
  3. Trong khi đó, việc chuyển đổi qua lại giữa panel dịch thuật và soát lỗi được thiết kế bằng JavaScript thuần qua hàm `switchPmFileTab(tab)`, nhưng hàm này **không được gọi** khi vừa khởi chạy dự án trong `openProject(slug)`.
- **Phương án xử lý**:
  1. **Nhóm các phần tử xung đột**: Loại bỏ `x-show="$store.workspace.wsTab === 'editor'"` ra khỏi từng thành phần con độc lập (`pm-translation-workspace`, `pm-spellcheck-workspace` và các bottom bar).
  2. **Tạo Wrapper**:
     - Bọc hai workspace editor (`pm-translation-workspace` và `pm-spellcheck-workspace`) vào một thẻ `div` Wrapper chung kiểm soát bởi Alpine:
       ```html
       <!-- WRAPPER CHO CÁC WORKSPACE BIÊN TẬP -->
       <div x-show="$store.workspace.wsTab === 'editor'" class="flex-auto flex flex-column overflow-hidden">
           <!-- pm-translation-workspace và pm-spellcheck-workspace bên trong -->
       </div>
       ```
     - Bọc hai bottom bar vào một thẻ `div` Wrapper chung tương tự:
       ```html
       <!-- WRAPPER CHO CÁC BOTTOM BAR BIÊN TẬP -->
       <div x-show="$store.workspace.wsTab === 'editor'" class="flex-shrink-0 flex flex-column">
           <!-- pm-translation-bottom-bar và pm-spellcheck-bottom-bar bên trong -->
       </div>
       ```
  3. **Đồng bộ hóa trong ProjectManager**: Sửa phương thức `openProject` trong `webui/static/js/project-manager.js` để gọi `switchPmFileTab` đồng bộ hóa giao diện dựa trên tab sidebar đang active, tránh việc chỉ render danh sách file mà bỏ qua render trạng thái các ô biên tập:
     ```javascript
     // Thay thế phần logic render danh sách tập tin theo tab ở cuối openProject
     const sourcesBtn = document.getElementById('pm-tab-sources');
     const translatedBtn = document.getElementById('pm-tab-translated');
     const spellingBtn = document.getElementById('pm-tab-spelling');

     if (translatedBtn && translatedBtn.classList.contains('active')) {
         ProjectManager.switchPmFileTab('translated');
     } else if (spellingBtn && spellingBtn.classList.contains('active')) {
         ProjectManager.switchPmFileTab('spelling');
     } else {
         ProjectManager.switchPmFileTab('sources');
     }
     ```

### Lỗi 3: Lỗi đường dẫn khi chuyển HTML thành Markdown (`not in the subpath of`)
- **Nguyên nhân cốt lõi**:
  Mặc dù `project_dir` đã được khai báo dùng `.resolve()` ở dòng 75, trong một số luồng gọi hoặc do cấu hình chưa reload, một trong hai đối tượng Path (`output_path` hoặc `project_dir`) vẫn có thể tồn tại dưới dạng tương đối/tuyệt đối không đồng nhất trước khi gọi hàm `.relative_to()`.
- **Phương án xử lý**:
  Đảm bảo cả hai đối tượng Path đều là tuyệt đối ngay tại điểm so sánh ở dòng 125 của file `plugins.py`:
  ```python
  rel_output = output_path.resolve().relative_to(project_dir.resolve())
  ```

### Lỗi 4: Tự động chuyển về tab Biên tập (auto-switch) sau khi thao tác trên panel file (Upload, Delete, Rename, v.v.)
- **Nguyên nhân cốt lõi**:
  Khi người dùng thực hiện các thao tác quản lý file (như tải file lên, đổi tên, xóa file, v.v.), JavaScript gọi `ProjectManager.openProject(slug)` để đồng bộ lại danh sách file từ backend.
  Tuy nhiên, trong `openProject(slug)`, dòng 301-303 luôn ép `Alpine.store('workspace').wsTab = 'editor'` mà không kiểm tra xem dự án đó có đang được mở sẵn hay không. Việc này cũng đồng thời xóa trắng nội dung editor hiện hành và đặt lại bộ lọc sidebar.
- **Phương án xử lý**:
  Làm cho `openProject(slug)` thông minh hơn bằng cách phát hiện xem dự án được yêu cầu mở có trùng với dự án hiện hành hay không:
  ```javascript
  const isSameProject = window.currentProject && window.currentProject.slug === slug;
  ```
  Nếu `isSameProject === true`, ta **bỏ qua** việc thiết lập lại tab `wsTab`, bỏ qua việc làm sạch editor, giữ nguyên bộ lọc sidebar và không hiện toast thông báo.

## 19. Kế hoạch triển khai sửa lỗi (TẤT CẢ ĐÃ HOÀN TẤT)

### [MODIFY] [plugin.py](file:///Users/narga/Briefcase/Projects/Novel-Translator/plugins/epub_converter/plugin.py)
- Đổi import `services.text_converter` thành `.services.text_converter`. (ĐÃ THỰC HIỆN)

### [MODIFY] [tab_projects.html](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/tab_projects.html)
- Bọc các panel biên tập và bottom bar vào thẻ Wrapper có `x-show="$store.workspace.wsTab === 'editor'"`. (ĐÃ THỰC HIỆN)
- Xóa thuộc tính `x-show` thừa trên các thẻ con. (ĐÃ THỰC HIỆN)

### [MODIFY] [project-manager.js](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/static/js/project-manager.js)
- ✅ Sửa đổi hàm `openProject(slug)`: kiểm tra `isSameProject` để tránh tự động đổi tab, tránh xóa editor và tránh reset file filter khi chỉ tải lại dự án cũ. (ĐÃ THỰC HIỆN)
- ✅ Thêm `refreshProjectFiles()` để refresh sidebar nhẹ không đổi wsTab.
- ✅ Giữ nguyên logic đồng bộ hóa giao diện ở cuối hàm `openProject(slug)` khi mở dự án mới. (ĐÃ THỰC HIỆN)

### [MODIFY] [plugins.py](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/routes/plugins.py)
- ✅ Cập nhật dòng tính toán `relative_to` tại dòng 125 của hàm `run_epub_converter`:
  ```python
  rel_output = output_path.resolve().relative_to(project_dir.resolve())
  ```
  (ĐÃ THỰC HIỆN)