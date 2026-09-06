# 19. BÁO CÁO PHÂN TÍCH TÍNH NĂNG KẾ THỪA & ĐẶC TẢ THIẾT KẾ TRANG DỰ ÁN
> **Dự án**: Content Translator (Next-Gen)  
> **Tham chiếu so sánh**: Novel-Translator (v8.30.0)  
> **Tiêu chí cốt lõi**: Tôn chỉ Minimalist/Lean, Zero-npm, Zero-build, Đơn giản, Đẹp mắt, Nhẹ nhàng  
> **Ngày lập báo cáo**: 06/09/2026  
> **Tác giả**: Antigravity (Pair-programming Review)

---

## MỤC LỤC
1. [Bối Cảnh & Sự Khác Biệt Tôn Chỉ Giữa Hai Dự Án](#1-bối-cảnh--sự-khác-biệt-tôn-chỉ-giữa-hai-dự-án)
2. [Gợi Ý Tính Năng Cho Content-Translator: Kế Thừa & Loại Bỏ](#2-gợi-ý-tính-năng-cho-content-translator-kế-thừa--loại-bỏ)
   - 2.1. Các tính năng nên kế thừa từ Novel-Translator (Tái thiết kế theo chuẩn Lean)
   - 2.2. Các tính năng tuyệt đối KHÔNG kế thừa (Lý do vi phạm tôn chỉ)
3. [Đặc Tả Thiết Kế Trang "Dự Án" (Project Management Page Spec)](#3-đặc-tả-thiết-kế-trang-dự-án-project-management-page-spec)
   - 3.1. Cấu trúc tổng thể trang
   - 3.2. Thanh công cụ & Header trang
   - 3.3. Grid Cards & Chi tiết Thẻ Dự Án (Project Card)
   - 3.4. Thẻ Tạo Dự Án Nét Đứt (Dashed Create Card)
   - 3.5. Trạng thái rỗng & Lọc tìm kiếm
   - 3.6. Khu vực Lịch sử chạy (Run History)
4. [Chỉ Dẫn Phong Cách Thiết Kế: Đơn Giản, Đẹp Mắt, Nhẹ Nhàng](#4-chỉ-dẫn-phong-cách-thiết-kế-đơn-giản-đẹp-mắt-nhẹ-nhàng)
   - 4.1. Hệ thống Design Tokens (Semantic CSS Variables)
   - 4.2. Nghệ thuật thị giác & Cấp bậc Typography
   - 4.3. Hiệu ứng vi mô (Micro-interactions) không thư viện
   - 4.4. Quy chuẩn Icon SVG & Tooltip nội tại
5. [Mã Nguồn Mẫu (Prototypes: CSS, HTML & JS)](#5-mã-nguồn-mẫu-prototypes-css-html--js)
   - 5.1. CSS Component cho Card & Grid (`app.css`)
   - 5.2. Cấu trúc HTML View Dự Án (`index.html`)
   - 5.3. Logic Render Thẻ Dự Án (`projects.js`)
6. [Lộ Trình & Khuyến Nghị Triển Khai](#6-lộ-trình--khuyến-nghị-triển-khai)

---

## 1. BỐI CẢNH & SỰ KHÁC BIỆT TÔN CHỈ GIỮA HAI DỰ ÁN

Để đưa ra các gợi ý tính năng và đặc tả thiết kế chuẩn xác, trước hết cần nhìn nhận rõ nét lịch sử phát triển và sự khác biệt triết lý cốt lõi giữa hai dự án:

| Tiêu chí | **Novel-Translator** (v8.30.0 - Dự án tiền nhiệm) | **Content-Translator** (Next-Gen - Dự án hiện tại) |
| :--- | :--- | :--- |
| **Bản chất cốt lõi** | Một hệ thống quản trị và xử lý dịch thuật tiểu thuyết đa năng, đồ sộ, hướng giải pháp "tất cả trong một" (All-in-one). | **"Không phải hệ thống quản lý quá trình dịch, mà là CÔNG CỤ GỬI NỘI DUNG CHO AI VÀ NHẬN BẢN DỊCH VỀ, phục vụ duy nhất 1 người dùng."** |
| **Backend** | Hexagonal Architecture nhiều tầng (Application, Domain, Infrastructure, Facade), Flask server, SQLAlchemy/SQLite phức tạp. | Python Standard Library HTTP Server + `httpx`, zero framework, luồng xử lý thẳng, code tinh giản. |
| **Frontend** | Tachyons CSS + CSS tùy biến lớn, Alpine.js cho reactivity, tích hợp nhiều sub-tabs và workflow phức tạp. | **Vanilla HTML + CSS + JS thuần**, zero-npm, zero-build, offline 100%, tốc độ tải tức thì. |
| **Xử lý lỗi / Lưu trạng thái** | SQLite Checkpoint lưu trạng thái từng chunk, cơ chế Resume/Recovery phức tạp, Task Dashboard kiểm soát hàng loạt. | **Fail-fast & Không Checkpoint**: lỗi chunk dừng ngay, không lưu dở dang, chạy lại từ đầu file (chương 2-3 chunk chạy lại cực nhanh). |
| **Bảo mật** | Mask/ẩn API keys trên UI, cấu trúc bảo vệ nhiều tầng. | **Tư thế Local Single-User**: Full API key hiển thị trực tiếp để dễ quản lý, chống lộ là chống public git, không chống chính mình. |
| **Câu hỏi sát hạch (Litmus Test)** | *Tính năng này có giúp quy trình quản trị dịch thuật toàn diện hơn không?* | **"Tính năng này có giúp gửi chunk cho AI và nhận bản dịch về nhanh hơn, nhẹ hơn không? Nếu làm tăng trạng thái, thêm luồng ngầm: LOẠI BỎ NGAY."** |

---

## 2. GỢI Ý TÍNH NĂNG CHO CONTENT-TRANSLATOR: KẾ THỪA & LOẠI BỎ

Dựa trên việc đọc mã nguồn cả hai dự án và thẩm thấu `docs/00_PROJECT_MANIFESTO.md`, dưới đây là các đề xuất phân loại nghiêm ngặt:

### 2.1. Các tính năng NÊN KẾ THỪA từ Novel-Translator (Tái thiết kế theo phong cách Lean)

1. **Giao diện Quản lý Dự án dạng Grid Cards (Cards Layout)**:
   - *Giá trị từ Novel-Translator*: Novel-Translator sở hữu trang "Quản lý dự án" rất trực quan. Thay vì một danh sách khô khan, mỗi dự án được trình bày dạng thẻ (Card) gồm: Tên sách, tác giả, tóm tắt, chấm màu trạng thái (xám: chưa dịch, vàng cam: đang dịch dở, xanh teal: đã hoàn thành 100%), thanh tiến độ %, số file hoàn thành/tổng số file và cụm icon hành động. Cuối grid là một card nét đứt (+ Tạo dự án mới) đóng vai trò Call-To-Action tự nhiên.
   - *Ứng dụng cho Content-Translator*: Kế thừa trọn vẹn mô hình này nhưng **loại bỏ hoàn toàn Tachyons và Alpine.js**, chuyển thành CSS thuần và template string JS cực nhẹ.
2. **Xuất bản & Tải về kết quả 1-click (Export / Download Zip)**:
   - *Giá trị từ Novel-Translator*: Có nút Export ngay trên card để người dùng đóng gói nhanh kết quả dịch tải về máy.
   - *Ứng dụng cho Content-Translator*: Hiện tại `content-translator` mới chỉ có nút "Lưu trữ" (Archive - nén vào thư mục `archive/` trên đĩa cứng server). Nên bổ sung nút **Tải về kết quả (Download Zip)**: backend chỉ cần 1 endpoint `GET /api/projects/{slug}/export` dùng thư viện chuẩn `zipfile` của Python nén các file trong `results/` và stream trực tiếp về trình duyệt. Rất hữu ích và giữ đúng tiêu chí gửi-nhận!
3. **Tìm kiếm & Lọc nhanh danh sách dự án (Client-side Search / Filter)**:
   - *Giá trị*: Khi người dùng có từ 10 đến 30 bộ truyện/dự án, việc cuộn tìm kiếm bằng mắt rất tốn thời gian.
   - *Ứng dụng cho Content-Translator*: Bổ sung một ô tìm kiếm nhỏ gọn trên Header trang Dự án. Sử dụng JavaScript lọc client-side trên danh sách thẻ sẵn có (O(N), thời gian lọc < 5ms, không cần gọi API backend).
4. **Bộ nhớ dịch mỏng / Thuật ngữ gắn theo dự án (Lightweight Project Glossary)**:
   - *Giá trị từ Novel-Translator*: Quản lý danh sách thuật ngữ nhân vật, môn phái, xưng hô để nhúng vào prompt.
   - *Ứng dụng cho Content-Translator*: Đã được quy hoạch đường dẫn chuẩn tại `workspace/projects/{slug}/assets/glossary.txt` (Manifesto §2.C). Không làm hệ thống trích xuất AI hay cơ sở dữ liệu phức tạp; chỉ cần cho phép sửa nhanh file text glossary này tại trang dự án hoặc workspace, và tự động regex nạp thuật ngữ vào biến `{{glossary_terms}}` khi gửi AI.
5. **So sánh bản dịch gọn nhẹ (Diff Viewer)**:
   - *Giá trị từ Novel-Translator*: Cho phép so sánh 2 cột trực quan giữa bản gốc và bản dịch hoặc giữa các phiên bản dịch khác nhau.
   - *Ứng dụng cho Content-Translator*: Giữ đúng lộ trình Roadmap §3 & Manifesto §9: vendor thư viện đơn `diff-match-patch` (~30KB, zero-npm), hiển thị so sánh chênh lệch khi người dùng cần kiểm tra sự khác nhau giữa các lần tinh chỉnh prompt.

### 2.2. Các tính năng tuyệt đối KHÔNG KẾ THỪA (Vi phạm tôn chỉ dự án)

* ❌ **Hệ thống Checkpoint / Resume lưu tạm từng chunk**: Novel-Translator dùng SQLite checkpoints để ghi nhận từng chunk đã dịch và cơ chế phục hồi phức tạp. Content-Translator tuân thủ quy tắc Fail-Fast: khi lỗi thì dừng ngay, sửa lỗi và gửi lại từ chunk đầu (các file truyện ngắn 2-3 chunk chạy lại chỉ mất vài chục giây). Mang vác Checkpoint làm tăng 40% độ phức tạp code và sinh lỗi đồng bộ.
* ❌ **Task Dashboard & Background Worker đa luồng ngầm**: Novel-Translator có hệ thống điều phối tác vụ tập trung, Celery/Thread ngầm. Content-Translator ưu tiên xử lý trực tiếp, hiển thị tiến độ tức thời qua SSE (Server-Sent Events) trên màn hình làm việc của người dùng.
* ❌ **Che giấu API Key (Masking / Vault)**: Không che 4 ký tự cuối, không mã hóa lúc nghỉ vì app chạy local cho 1 người dùng.
* ❌ **Hệ sinh thái Plugin động & OCR tesseract nhúng**: Không nhúng thư viện xử lý ảnh, PDF, OCR nặng nề vào mã nguồn; tuân thủ nguyên tắc văn bản nguồn chỉ nhận `.txt`, `.md`, `.html`. Mọi xử lý OCR thực hiện bằng công cụ ngoài trước khi đưa vào.
* ❌ **Framework Frontend (Alpine.js, Tachyons, React/Vue)**: Giữ vững cam kết 100% Vanilla JS + CSS thuần, zero build-step.

---

## 3. ĐẶC TẢ THIẾT KẾ TRANG "DỰ ÁN" (PROJECT MANAGEMENT PAGE SPEC)

Thiết kế mới cho trang Dự án của `content-translator` tái hiện lại sự sang trọng, gọn gàng và tiện dụng của `Novel-Translator`, nhưng được xây dựng bằng **HTML5 semantic + CSS thuần túy**, tối ưu dung lượng và không phụ thuộc vào bất kỳ thư viện ngoài nào.

### 3.1. Cấu trúc tổng thể trang

Giao diện trang Dự án (`#v-projects`) được phân bố theo chiều dọc với 3 khu vực chính:
```text
┌────────────────────────────────────────────────────────────────────────┐
│ HEADER TRANG: Tiêu đề + Thống kê tổng quan + Toolbar Hành động         │
│ [📁 Dự án (N)]  [Tìm kiếm dự án...]    [+ Tạo dự án]  [🔄 Làm mới]    │
├────────────────────────────────────────────────────────────────────────┤
│ GRID CARDS DỰ ÁN (Responsive CSS Grid: minmax(310px, 1fr))            │
│ ┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────┐ │
│ │ ● Dự án A      [⋯]   │ │ ● Dự án B      [⋯]   │ │ ┌──────────────┐ │ │
│ │ Tác giả: Chu Thiên   │ │ Tác giả: Khuyết Danh │ │ │      +       │ │ │
│ │ Mô tả tóm tắt...     │ │ Mô tả tóm tắt...     │ │ │ Tạo dự án mới│ │ │
│ │ 📄 12/12  [ℹ][⬇][📦][🗑]│ │ 📄 4/10   [ℹ][⬇][📦][🗑]│ │ └──────────────┘ │ │
│ │ Tiến độ        100%  │ │ Tiến độ         40%  │ │ (Card nét đứt) │ │ │
│ │ [██████████████████] │ │ [██████░░░░░░░░░░░░] │ │                  │ │
│ └──────────────────────┘ └──────────────────────┘ └──────────────────┘ │
├────────────────────────────────────────────────────────────────────────┤
│ SECTION LỊCH SỬ CHẠY (Run History): Collapsible Details Panel          │
│ ▶ Nhật ký các phiên chạy gần đây (SQLite app.db)                       │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2. Thanh công cụ & Header trang

* **Tiêu đề & Mô tả**:
  - Tiêu đề chính `<h2>Dự án</h2>` kết hợp huy hiệu đếm tổng số dự án `(N)`.
  - Dòng mô tả ngắn gọn: *Quản lý không gian dịch thuật, tiến độ và tài liệu của bạn.*
* **Thanh công cụ (Action Bar)**:
  - **Ô tìm kiếm nhanh**: `<input id="pSearch" placeholder="Lọc theo tên sách, tác giả...">` với icon kính lúp SVG. Lọc danh sách thẻ ngay khi gõ phím (`oninput`).
  - **Nút "+ Tạo dự án mới"**: Primary button xanh dương (`--primary`), mở modal tạo dự án.
  - **Nút "Làm mới"**: Nút phụ icon xoay 🔄 tải lại danh sách từ `/api/projects`.

### 3.3. Grid Cards & Chi tiết Thẻ Dự Án (Project Card)

Grid sử dụng CSS Grid tự động co giãn:
```css
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  gap: 16px;
  align-items: stretch;
}
```

Mỗi **Thẻ Dự Án (`.pcard`)** được cấu trúc rõ ràng:
1. **Dòng Đầu Thẻ (Header Row)**:
   - **Chấm trạng thái (Status Dot - 8px)**:
     - 🟢 **Xanh lục (`--success`)**: Dự án đã dịch xong 100% (`done === sources && sources > 0`).
     - 🟠 **Vàng cam (`--warning`)**: Dự án đang dịch dở dang (`0 < done < sources`).
     - ⚪ **Xám trung tính (`--text-sub`)**: Dự án mới tạo hoặc chưa có file nào được dịch.
   - **Tên dự án (`.pcard-title`)**: Font chữ 15px, đậm (`font-weight: 600`), hover đổi màu xanh `--primary`. Nhấp vào tiêu đề hoặc thẻ sẽ chuyển thẳng sang tab **Biên dịch** với dự án đó được nạp sẵn.
2. **Dòng Tác Giả & Phân Loại (`.pcard-meta`)**:
   - Hiển thị tên tác giả chữ nghiêng mờ (`--text-muted`, 12.5px).
3. **Mô Tả Tóm Tắt (`.pcard-desc`)**:
   - Hiển thị tối đa 2 dòng văn bản với kỹ thuật thuần CSS `-webkit-line-clamp: 2`. Nếu không có mô tả, giữ khoảng đệm tối thiểu để các card luôn có chiều cao hài hòa.
4. **Hàng Thống Kê & Cụm Nút Hành Động (`.pcard-actions-row`)**:
   - **Bên trái**: Icon tập tin SVG kèm thống kê số lượng file: `${done}/${sources} tập tin`.
   - **Bên phải**: Cụm 4 nút icon tối giản (kích thước 28x28px, hover nền xám nhạt, màu icon theo vai trò):
     - ℹ️ **Sửa thông tin** (`openInfo`): Màu chàm Indigo (`#4f46e5`), sửa tiêu đề/tác giả/mô tả.
     - ⬇️ **Tải về kết quả ZIP** (`exportZip`): Màu xanh ngọc Teal (`#0d9488`), tải file `.zip` các bản dịch trong `results/`.
     - 📦 **Nén lưu trữ** (`archiveProject`): Màu vàng hổ phách Amber (`#b45309`), chuyển dự án vào `archive/`.
     - 🗑️ **Xóa dự án** (`delProject`): Màu đỏ Danger (`#dc2626`), xóa thư mục dự án sau khi xác nhận.
5. **Thanh Tiến Độ (`.pcard-progress`)**:
   - Nhãn "Tiến độ" kèm con số tỷ lệ phần trăm `${pct}%`.
   - Thanh tiến độ (Track) dày 6px, bo tròn hoàn toàn (`border-radius: 9999px`).
   - Phần trăm lấp đầy (Fill) đổi màu thông minh: Khi đạt 100% chuyển sang màu xanh lá hoàn thành (`--success`), khi đang làm mang màu xanh `--primary`.

### 3.4. Thẻ Tạo Dự Án Nét Đứt (Dashed Create Card)

* Đặt ở vị trí cuối cùng trong Grid cards (`.create-card-dashed`).
* Thiết kế:
  - Viền nét đứt mảnh (`border: 2px dashed #cbd5e1`).
  - Nền chuyển màu nhẹ (`background: #f8fafc`).
  - Ở giữa là vòng tròn icon `+` màu xanh dương nhạt.
  - Dòng chữ *"Tạo dự án mới"* (14px, đậm) và phụ đề *"Bắt đầu một bản dịch mới"* (12px).
  - Tương tác: Khi rê chuột vào (hover), viền chuyển màu xanh `--primary`, nền sáng hơn và toàn bộ card nhích nhẹ lên 2px (`transform: translateY(-2px)`). Click vào thẻ sẽ mở hộp thoại tạo dự án.

### 3.5. Trạng thái rỗng & Lọc tìm kiếm

* **Khi chưa có dự án**: Hiển thị khung thông báo thân thiện với icon thư mục lớn SVG và nút bấm trực tiếp để tạo dự án đầu tiên.
* **Khi tìm kiếm không có kết quả**: Hiển thị thông báo *"Không tìm thấy dự án phù hợp với từ khóa"* kèm nút xóa bộ lọc.

### 3.6. Khu vực Lịch sử chạy (Run History)

* Thay vì để bảng lịch sử chiếm diện tích bên dưới, đặt trong một thẻ đóng mở chuẩn HTML5:
  ```html
  <details class="history-accordion">
    <summary><b>Lịch sử các lượt chạy gần đây</b> (app.db)</summary>
    <div class="table-wrap">
      <table class="table-minimal">...</table>
    </div>
  </details>
  ```
  Giúp trang chủ luôn gọn gàng, người dùng chỉ mở ra khi cần kiểm tra log phiên dịch.

---

## 4. CHỈ DẪN PHONG CÁCH THIẾT KẾ: ĐƠN GIẢN, ĐẸP MẮT, NHẸ NHÀNG

Đây là bộ chỉ dẫn (Design Guidelines) tuân thủ nghiêm ngặt tôn chỉ **zero-dependency** của dự án: không kéo Tailwind, không dùng Bootstrap hay các thư viện hiệu ứng JavaScript nặng nề. Mọi vẻ đẹp thẩm mỹ đều được kiến tạo từ tỷ lệ bố cục, màu sắc cân bằng và hiệu ứng CSS gốc.

### 4.1. Hệ thống Design Tokens (Semantic CSS Variables)

Bổ sung và chuẩn hóa các biến CSS vào đầu tệp `web/css/app.css`:

```css
:root {
  /* Nền tảng (Surfaces & Backgrounds) */
  --bg-app: #f8fafc;          /* Nền trang (Slate 50) */
  --bg-card: #ffffff;         /* Nền thẻ / dialog trắng tinh khiết */
  --bg-subtle: #f1f5f9;       /* Nền thứ cấp cho hover / toolbars */
  
  /* Đường viền & Phân cách */
  --border: #e2e8f0;          /* Viền mặc định thanh thoát */
  --border-focus: #94a3b8;    /* Viền khi active hoặc hover card */
  --border-dashed: #cbd5e1;   /* Viền nét đứt cho thẻ tạo mới */

  /* Văn bản & Phân cấp (Text Hierarchy) */
  --text-main: #0f172a;       /* Chữ chính (Slate 900) - tương phản cao */
  --text-muted: #64748b;      /* Chữ phụ, mô tả (Slate 500) */
  --text-sub: #94a3b8;        /* Chữ nhãn nhỏ, placeholder (Slate 400) */

  /* Màu sắc ngữ nghĩa (Semantic Roles) */
  --primary: #2563eb;         /* Xanh dương chủ đạo */
  --primary-hover: #1d4ed8;   /* Trạng thái hover */
  --primary-light: #eff6ff;   /* Nền phụ tông xanh */
  
  --success: #16a34a;         /* Xanh lá hoàn thành / thành công */
  --success-bg: #f0fdf4;
  
  --warning: #d97706;         /* Vàng cam tiến trình / cảnh báo */
  --warning-bg: #fffbeb;
  
  --danger: #dc2626;          /* Đỏ nguy hiểm / nút xóa */
  --danger-bg: #fef2f2;
  
  --accent-indigo: #4f46e5;   /* Tông chàm cho nút thông tin */
  --accent-teal: #0d9488;     /* Tông xanh ngọc cho nút xuất file */

  /* Bo góc (Border Radius) */
  --radius-sm: 4px;
  --radius-md: 6px;           /* Dùng cho button, input */
  --radius-lg: 12px;          /* Dùng cho Card, Modal/Dialog */
  --radius-full: 9999px;      /* Dùng cho Progress bar, Badge, Dot */

  /* Đổ bóng tinh tế (Elevation / Shadows) */
  --shadow-xs: 0 1px 2px rgba(0, 0, 0, 0.04);
  --shadow-card: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03);
  --shadow-hover: 0 8px 20px -4px rgba(0, 0, 0, 0.08), 0 4px 8px -2px rgba(0, 0, 0, 0.03);
  --shadow-modal: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
}
```

### 4.2. Nghệ thuật thị giác & Cấp bậc Typography

1. **Sử dụng Font hệ thống cao cấp**:
   - Tránh nạp Google Fonts qua CDN để app hoạt động offline 100%.
   - Chuỗi font chuẩn: `font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;`. Font hệ thống của macOS và Windows hiện đại hiển thị tiếng Việt cực kỳ sắc nét và mượt mà.
2. **Quy tắc không gian (Whitespace & Rhythm)**:
   - Các card cách nhau cố định `16px`.
   - Padding bên trong card là `16px` đến `20px` tạo sự thông thoáng, tránh dồn cục dữ liệu.
   - Tên sách giới hạn kích thước vừa phải (15px), khoảng cách dòng `1.35`, không dùng chữ quá to gây thô kệch.

### 4.3. Hiệu ứng vi mô (Micro-interactions) không cần thư viện

Không sử dụng các thư viện như Framer Motion, Anime.js hay GSAP. Toàn bộ hiệu ứng được xử lý bằng chuyển động GPU thuần của trình duyệt:

1. **Card Hover Lift**:
   ```css
   .pcard {
     transition: transform 0.16s cubic-bezier(0.4, 0, 0.2, 1),
                 box-shadow 0.16s cubic-bezier(0.4, 0, 0.2, 1),
                 border-color 0.16s ease;
   }
   .pcard:hover {
     transform: translateY(-2px);
     box-shadow: var(--shadow-hover);
     border-color: var(--border-focus);
   }
   ```
   *Lợi ích*: Cảm giác thẻ nổi nhẹ lên trên bề mặt, mượt mà ở tần số quét 60/120fps, không gây giật lag RAM.
2. **Nút bấm phản hồi xúc giác (Tactile Button Feedback)**:
   ```css
   .btn:active, .icon-btn:active {
     transform: scale(0.97);
     transition: transform 0.05s ease;
   }
   ```
   *Lợi ích*: Khi bấm chuột, nút thu nhỏ nhẹ 3% tạo cảm giác có lực nhấn chân thực như ứng dụng desktop native.

### 4.4. Quy chuẩn Icon SVG & Tooltip nội tại

* **Zero Icon Font**: Không dùng FontAwesome hay Material Icons file woff/ttf.
* **Inline SVG đồng nhất**:
  - ViewBox cố định `0 0 24 24` hoặc `0 0 16 16`.
  - Độ dày nét vẽ (`stroke-width: 1.8` hoặc `2`).
  - Màu sắc nét vẽ dùng `stroke="currentColor"` để kế thừa trực tiếp từ màu chữ của nút.
* **Tooltip**: Sử dụng thuộc tính chuẩn `title="..."` của HTML5 hoặc thuộc tính `data-tooltip` thuần CSS. Không sử dụng thư viện tooltip JS (như Popper/Tippy).

---

## 5. MÃ NGUỒN MẪU (PROTOTYPES: CSS, HTML & JS)

Các đoạn mã dưới đây được thiết kế để có thể tích hợp liền mạch vào codebase hiện tại của `content-translator` mà không phá vỡ bất kỳ logic nghiệp vụ nào.

### 5.1. CSS Component cho Card & Grid (`web/css/app.css`)

```css
/* ==================== PROJECT MANAGEMENT GRID & CARDS ==================== */

/* Header & Search Bar */
.projects-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
}
.projects-header-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.projects-count-badge {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  background: var(--bg-subtle);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border);
}
.projects-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.search-input-wrap {
  position: relative;
  display: flex;
  align-items: center;
}
.search-input-wrap svg {
  position: absolute;
  left: 10px;
  color: var(--text-sub);
  pointer-events: none;
}
.search-input-wrap input {
  padding: 7px 12px 7px 32px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 13.5px;
  outline: none;
  background: #fff;
  color: var(--text-main);
  transition: border-color 0.15s, box-shadow 0.15s;
  width: 220px;
}
.search-input-wrap input:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}

/* Projects Grid Layout */
.projects-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
  gap: 16px;
  align-items: stretch;
  margin-bottom: 28px;
}

/* Project Card */
.pcard {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 18px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  box-shadow: var(--shadow-card);
  min-height: 190px;
  position: relative;
  cursor: pointer;
  transition: transform 0.16s cubic-bezier(0.4, 0, 0.2, 1),
              box-shadow 0.16s cubic-bezier(0.4, 0, 0.2, 1),
              border-color 0.16s ease;
}
.pcard:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
  border-color: var(--border-focus);
}

/* Card Header: Dot + Title */
.pcard-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 6px;
}
.pcard-status-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
  margin-top: 6px;
  background-color: var(--text-sub);
}
.pcard-status-dot.done { background-color: var(--success); }
.pcard-status-dot.in-progress { background-color: var(--warning); }
.pcard-status-dot.empty { background-color: var(--text-sub); }

.pcard-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.35;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.pcard:hover .pcard-title {
  color: var(--primary);
}

/* Meta & Description */
.pcard-author {
  font-size: 12.5px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-style: italic;
  min-height: 17px;
}
.pcard-desc {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.45;
  margin: 0 0 16px 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 38px;
}

/* Meta Row & Action Buttons */
.pcard-footer-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12.5px;
  color: var(--text-muted);
  margin-bottom: 8px;
}
.pcard-file-count {
  display: flex;
  align-items: center;
  gap: 5px;
}
.pcard-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.pcard-btn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  background: transparent;
  border-radius: var(--radius-sm);
  color: var(--text-muted);
  cursor: pointer;
  transition: background-color 0.12s, color 0.12s, transform 0.08s;
}
.pcard-btn-icon:hover {
  background-color: var(--bg-subtle);
}
.pcard-btn-icon.info:hover { color: var(--accent-indigo); }
.pcard-btn-icon.export:hover { color: var(--accent-teal); }
.pcard-btn-icon.archive:hover { color: var(--warning); }
.pcard-btn-icon.del:hover { color: var(--danger); }
.pcard-btn-icon:active { transform: scale(0.92); }

/* Progress Bar */
.pcard-progress-wrap {
  margin-top: 4px;
}
.pcard-progress-labels {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 11.5px;
  color: var(--text-muted);
  margin-bottom: 4px;
}
.pcard-progress-percent {
  font-weight: 600;
  color: var(--text-main);
}
.pcard-progress-percent.done { color: var(--success); }
.pcard-progress-track {
  width: 100%;
  height: 5px;
  background: #e2e8f0;
  border-radius: var(--radius-full);
  overflow: hidden;
}
.pcard-progress-fill {
  height: 100%;
  background: var(--primary);
  border-radius: var(--radius-full);
  width: 0%;
  transition: width 0.3s ease, background-color 0.3s ease;
}
.pcard-progress-fill.done { background: var(--success); }

/* Dashed "Create New Project" Card */
.create-card-dashed {
  border: 2px dashed var(--border-dashed);
  border-radius: var(--radius-lg);
  background-color: #fafbfc;
  min-height: 190px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  cursor: pointer;
  transition: background-color 0.16s ease, border-color 0.16s ease, transform 0.16s ease;
}
.create-card-dashed:hover {
  background-color: var(--primary-light);
  border-color: var(--primary);
  transform: translateY(-2px);
}
.create-card-icon-circle {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-full);
  background-color: #e0e7ff;
  color: var(--primary);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  transition: background-color 0.16s, color 0.16s;
}
.create-card-dashed:hover .create-card-icon-circle {
  background-color: var(--primary);
  color: #ffffff;
}
.create-card-title {
  margin: 0 0 4px 0;
  font-size: 14.5px;
  font-weight: 600;
  color: var(--text-main);
}
.create-card-sub {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}

/* Run History Collapsible */
.history-details {
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  padding: 12px 16px;
  margin-top: 24px;
}
.history-details summary {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  cursor: pointer;
  outline: none;
  user-select: none;
}
```

### 5.2. Cấu trúc HTML View Dự Án (`web/index.html`)

Thay thế khối `<section id="v-projects">` hiện tại bằng cấu trúc chuẩn sau:

```html
<section id="v-projects" class="view on">
  <!-- Header & Toolbar -->
  <div class="projects-header">
    <div>
      <h2 class="projects-header-title">
        Dự án <span id="pCountBadge" class="projects-count-badge">0 dự án</span>
      </h2>
      <p style="color:var(--text-muted); margin: 4px 0 0 0; font-size: 13.5px;">
        Quản lý không gian tài liệu và theo dõi tiến độ dịch thuật.
      </p>
    </div>
    <div class="projects-toolbar">
      <div class="search-input-wrap">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="7" cy="7" r="4"/><path d="M10 10l3.5 3.5"/>
        </svg>
        <input id="pSearch" type="text" placeholder="Tìm kiếm dự án…" oninput="filterProjects()">
      </div>
      <button class="btn pri" onclick="projDlg.showModal()">+ Tạo dự án mới</button>
      <button class="icon-btn" onclick="listProjects()" title="Làm mới danh sách">
        <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8">
          <path d="M13.5 8a5.5 5.5 0 11-1.6-3.9M13.5 2v4h-4"/>
        </svg>
      </button>
    </div>
  </div>

  <!-- Cards Grid Container -->
  <div id="pCards" class="projects-cards-grid">
    <!-- Render động bởi JS (bao gồm các thẻ dự án + thẻ dashed tạo mới) -->
  </div>

  <!-- Run History Accordion -->
  <details class="history-details">
    <summary>Nhật ký phiên dịch gần đây (SQLite app.db)</summary>
    <div style="margin-top: 12px; overflow-x: auto;">
      <table class="table-minimal">
        <thead>
          <tr>
            <th>Dự án</th>
            <th>File</th>
            <th>Provider / Model</th>
            <th>Trạng thái</th>
            <th>Thời gian</th>
          </tr>
        </thead>
        <tbody id="pHist"></tbody>
      </table>
    </div>
  </details>

  <!-- Dialogs: Tạo dự án & Thông tin -->
  <dialog id="projDlg">
    <h3>Tạo dự án mới</h3>
    <label class="label-tracked">Tên sách *</label>
    <input id="npTitle" class="input" placeholder="Ví dụ: Đấu Phá Thương Khung">
    <label class="label-tracked" style="margin-top:10px">Tác giả</label>
    <input id="npAuthor" class="input" placeholder="Tên tác giả (nếu có)">
    <label class="label-tracked" style="margin-top:10px">Mô tả tóm tắt</label>
    <textarea id="npDesc" rows="3" class="textarea" placeholder="Ghi chú về văn phong, bối cảnh..."></textarea>
    <div class="row spread" style="margin-top:16px">
      <button class="btn" onclick="projDlg.close()">Hủy bỏ</button>
      <button class="btn pri" onclick="mkProject()">Tạo dự án</button>
    </div>
  </dialog>

  <dialog id="infoDlg">
    <h3>Thông tin dự án</h3>
    <label class="label-tracked">Tên sách *</label>
    <input id="ipTitle" class="input">
    <label class="label-tracked" style="margin-top:10px">Tác giả</label>
    <input id="ipAuthor" class="input">
    <label class="label-tracked" style="margin-top:10px">Mô tả</label>
    <textarea id="ipDesc" rows="3" class="textarea"></textarea>
    <div class="row spread" style="margin-top:16px">
      <button class="btn" onclick="infoDlg.close()">Hủy bỏ</button>
      <button class="btn pri" onclick="saveInfo()">Lưu thay đổi</button>
    </div>
  </dialog>
</section>
```

### 5.3. Logic Render Thẻ Dự Án (`web/js/projects.js`)

Cập nhật lại tệp `projects.js` với khả năng lưu trữ bộ đệm danh sách (`_cachedProjects`), lọc trực tiếp và tạo thẻ nét đứt:

```javascript
let _cachedProjects = [];
let _infoSlug = null;

async function listProjects() {
  try {
    const d = await fetch('/api/projects').then(J);
    _cachedProjects = d.projects || [];
    renderProjectsList(_cachedProjects);
    
    // Cập nhật dropdown chọn dự án ở Workspace và Prompt
    const opts = _cachedProjects.map(p => `<option value="${esc(p.slug)}">${esc(p.title || p.slug)}</option>`).join('');
    if ($('wProj')) $('wProj').innerHTML = opts;
    if ($('prProj')) $('prProj').innerHTML = opts;
  } catch (e) {
    toast('Lỗi tải danh sách dự án: ' + e.message, true);
  }

  // Tải lịch sử chạy
  try {
    const h = await fetch('/api/history?limit=15').then(J);
    const tbody = $('pHist');
    if (tbody) {
      tbody.innerHTML = (h.runs && h.runs.length) 
        ? h.runs.map(r => `<tr>
            <td><b>${esc(r.project)}</b></td>
            <td>${esc(r.file)}</td>
            <td><code>${esc(r.provider)}/${esc(r.model)}</code></td>
            <td><span class="dot ${r.status === 'success' ? '' : 'off'}"></span>${esc(r.status)}${r.error ? ' — ' + esc(r.error.slice(0, 60)) : ''}</td>
            <td>${esc(r.started_at || '')}</td>
          </tr>`).join('')
        : '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">Chưa có lịch sử chạy nào.</td></tr>';
    }
  } catch (e) {}
}

function filterProjects() {
  const kw = ($('pSearch')?.value || '').trim().toLowerCase();
  if (!kw) {
    renderProjectsList(_cachedProjects);
    return;
  }
  const filtered = _cachedProjects.filter(p => {
    const title = (p.title || p.slug || '').toLowerCase();
    const author = (p.author || '').toLowerCase();
    const desc = (p.description || '').toLowerCase();
    return title.includes(kw) || author.includes(kw) || desc.includes(kw);
  });
  renderProjectsList(filtered, true);
}

function renderProjectsList(projects, isFiltered = false) {
  const container = $('pCards');
  const badge = $('pCountBadge');
  if (badge) badge.textContent = `${_cachedProjects.length} dự án`;
  if (!container) return;

  if (!projects.length) {
    if (isFiltered) {
      container.innerHTML = `<div style="grid-column: 1/-1; text-align:center; padding: 40px; color:var(--text-muted)">
        <p>Không tìm thấy dự án nào khớp với từ khóa tìm kiếm.</p>
        <button class="btn" onclick="$('pSearch').value=''; filterProjects()">Xóa bộ lọc</button>
      </div>`;
    } else {
      container.innerHTML = renderCreateDashedCard();
    }
    return;
  }

  const cardsHtml = projects.map(p => {
    const e = encodeURIComponent(p.slug);
    const n = p.sources || 0;
    const dn = p.done || 0;
    const pct = n ? Math.min(100, Math.round((dn / n) * 100)) : 0;
    const isDone = pct === 100 && n > 0;
    const inProg = pct > 0 && !isDone;
    const statusClass = isDone ? 'done' : (inProg ? 'in-progress' : 'empty');
    const title = esc(p.title || p.slug);

    return `
    <div class="pcard" onclick="handleCardClick(event, '${e}')">
      <div>
        <div class="pcard-header">
          <span class="pcard-status-dot ${statusClass}" title="${isDone ? 'Đã hoàn thành 100%' : (inProg ? 'Đang dịch' : 'Chưa dịch')}"></span>
          <h3 class="pcard-title" title="${title}">${title}</h3>
        </div>
        <div class="pcard-author">${p.author ? esc(p.author) : '&nbsp;'}</div>
        <div class="pcard-desc">${p.description ? esc(p.description) : 'Chưa có mô tả dự án.'}</div>
      </div>

      <div>
        <div class="pcard-footer-info">
          <span class="pcard-file-count">
            <svg viewBox="0 0 16 16" width="13" height="13" fill="none" stroke="currentColor" stroke-width="1.8">
              <path d="M3 2h6l4 4v8H3z"/><path d="M9 2v4h4"/>
            </svg>
            ${dn}/${n} tập tin
          </span>
          <div class="pcard-actions" onclick="event.stopPropagation()">
            <button class="pcard-btn-icon info" onclick="openInfo('${e}')" title="Sửa thông tin">
              <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8">
                <circle cx="8" cy="8" r="6"/><path d="M8 7v4M8 5v.5"/>
              </svg>
            </button>
            <button class="pcard-btn-icon export" onclick="exportProjectZip('${e}')" title="Tải về file ZIP kết quả">
              <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M8 2v9M4 7l4 4 4-4M2 13h12"/>
              </svg>
            </button>
            <button class="pcard-btn-icon archive" onclick="archiveProject('${e}')" title="Lưu trữ dự án (vào archive/)">
              <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M2 4h12v9H2z"/><path d="M2 4l2-2h8l2 2M6 8h4"/>
              </svg>
            </button>
            <button class="pcard-btn-icon del" onclick="delProject('${e}')" title="Xóa toàn bộ dự án">
              <svg viewBox="0 0 16 16" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8">
                <path d="M2 4h12M5 4V2h6v2M4 4l1 10h6l1-10"/>
              </svg>
            </button>
          </div>
        </div>

        <div class="pcard-progress-wrap">
          <div class="pcard-progress-labels">
            <span>Tiến độ</span>
            <span class="pcard-progress-percent ${isDone ? 'done' : ''}">${pct}%</span>
          </div>
          <div class="pcard-progress-track">
            <div class="pcard-progress-fill ${isDone ? 'done' : ''}" style="width: ${pct}%"></div>
          </div>
        </div>
      </div>
    </div>`;
  }).join('');

  // Ghép thêm Thẻ nét đứt vào cuối Grid
  container.innerHTML = cardsHtml + renderCreateDashedCard();
}

function renderCreateDashedCard() {
  return `
  <div class="create-card-dashed" onclick="projDlg.showModal()">
    <div class="create-card-icon-circle">
      <svg viewBox="0 0 16 16" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.2">
        <line x1="8" y1="3" x2="8" y2="13"/><line x1="3" y1="8" x2="13" y2="8"/>
      </svg>
    </div>
    <h4 class="create-card-title">Tạo dự án mới</h4>
    <p class="create-card-sub">Bắt đầu dịch một tài liệu mới</p>
  </div>`;
}

function handleCardClick(event, eslug) {
  // Chỉ mở workspace khi không bấm vào các nút thao tác
  if (event.target.closest('button') || event.target.closest('input')) return;
  goWS(eslug);
}

async function exportProjectZip(eslug) {
  const slug = decodeURIComponent(eslug);
  toast(`Đang chuẩn bị gói tải về cho ${slug}...`);
  // Gọi endpoint tải zip về trình duyệt
  window.location.href = `/api/projects/${encodeURIComponent(slug)}/export`;
}
```

---

## 6. LỘ TRÌNH & KHUYẾN NGHỊ TRIỂN KHAI

Để đưa thiết kế này vào hoạt động mượt mà, khuyến nghị thực hiện tuần tự qua 3 bước tinh gọn:

1. **Bước 1: Bổ sung CSS Tokens & Class vào `web/css/app.css`**
   - Đưa hệ thống biến màu và các class `.projects-*`, `.pcard*`, `.create-card-*` vào `app.css`.
   - Giữ nguyên các định dạng hiện tại để tránh ảnh hưởng đến các trang Workspace hay Settings.
2. **Bước 2: Cập nhật `web/index.html` và `web/js/projects.js`**
   - Thay đổi cấu trúc HTML trong `<section id="v-projects">`.
   - Cập nhật hàm `listProjects()`, `renderProjectsList()`, bổ sung hàm tìm kiếm `filterProjects()`.
3. **Bước 3: Bổ sung Endpoint Export ZIP ở Backend (`main.py`)**
   - Viết thêm handler cho `GET /api/projects/{slug}/export` sử dụng module có sẵn `zipfile` của Python để nén nhanh thư mục `results/` của dự án và trả về dưới dạng file đính kèm `attachment; filename="{slug}_results.zip"`.
   - Bổ sung test kiểm thử vào `tests/test_server.py`.

---
*Báo cáo được biên soạn độc lập bởi Antigravity dựa trên phân tích trực tiếp mã nguồn của hai dự án.*
