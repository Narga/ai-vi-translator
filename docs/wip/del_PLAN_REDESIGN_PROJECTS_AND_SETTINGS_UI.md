# KẾ HOẠCH THIẾT KẾ LẠI GIAO DIỆN (UI REDESIGN PLAN)
## TRANG QUẢN LÝ DỰ ÁN & TRANG CẤU HÌNH AI

> **Dự án**: Content Translator (Next-Gen)  
> **Tài liệu**: `docs/wip/PLAN_REDESIGN_PROJECTS_AND_SETTINGS_UI.md`  
> **Phiên bản**: v1.0 (04/09/2026)  
> **Định hướng**: Kế thừa thẩm mỹ chỉn chu của `Novel-Translator`, tích hợp vào cấu trúc hiển thị tinh gọn của `content-translator`. Ưu tiên: **Nhẹ, đơn giản, minimalist, không hiệu ứng màu mè**.

---

## 1. PHÂN TÍCH HIỆN TRẠNG MÃ NGUỒN & ĐỐI CHIẾU ĐẶC TẢ

### 1.1. Công nghệ UI Đang Dùng Trong `content-translator`
Sau khi kiểm tra toàn bộ mã nguồn của dự án mới, kiến trúc frontend hiện tại bao gồm:
* **Cấu trúc tệp**: Toàn bộ giao diện nằm gọn trong **duy nhất 1 file** `web/index.html` (~250 dòng gồm cả HTML, CSS và JavaScript).
* **HTML**: HTML5 ngữ nghĩa cơ bản (`<nav>`, `<main>`, `<section>`, `<table>`, `<details>`, `<textarea>`).
* **CSS**: Vanilla CSS nội tuyến trong thẻ `<style>` (~25 dòng). Không dùng bất kỳ framework CSS nào (không Tailwind, không Bootstrap, không Tachyons). Bố cục dựa trên Flexbox (`#side` cố định bên trái, `main` cuộn nội dung bên phải).
* **JavaScript**: Vanilla JS (ES6+) thuần nhúng trong `<script>`. Không dùng thư viện/framework (không React/Vue, không Alpine.js). Thao tác DOM trực tiếp qua helper `const $ = id => document.getElementById(id)`, nạp dữ liệu bằng `fetch()` và đọc luồng dịch thời gian thực qua Server-Sent Events (SSE) `ReadableStream`.
* **Backend phục vụ UI**: Python standard library `http.server` (`BaseHTTPRequestHandler`, `ThreadingHTTPServer`), SQLite (`workspace/app.db`) qua `sqlite3` stdlib, thư viện gọi AI `httpx`. Không sử dụng FastAPI/Flask.

### 1.2. Đối Chiếu Với Đặc Tả Trong Thư Mục `docs/`
Đối chiếu với `00_PROJECT_MANIFESTO.md`, `02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md`, `04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md`, `06_AI_MODELS_MANAGEMENT_SPEC.md` và `docs/wip/del_SETTINGS_REDESIGN_v2.5.md`:

| Tiêu chí | Đặc tả yêu cầu (`docs/`) | Hiện trạng trong mã nguồn | Đánh giá |
| :--- | :--- | :--- | :--- |
| **Triết lý tinh gọn (Lean/Minimalist)** | Không framework cồng kềnh, stdlib `http.server`, 1 người dùng local | Đúng 100%: Single-file `web/index.html`, zero dependency ngoài. | ✅ ĐẠT |
| **Cơ chế dịch thời gian thực** | Gửi tuần tự, SSE stream hiển thị từng chunk, không polling | Đã có endpoint `POST /api/translate` stream SSE, UI nối chunk `

`. | ✅ ĐẠT |
| **Quản lý AI & SSOT** | `config/providers.json` là SSOT, model live cache 5 phút, thinking 4 mức | Backend và JS đã hỗ trợ model metadata live, thinking budget, delay, timeout. | ✅ ĐẠT |
| **Trang Quản lý Dự án (`#v-projects`)** | Quản lý dự án, xem danh sách files nguồn/dịch, tải file lên (`/upload`) | **Chưa đạt**: UI chỉ có 1 ô nhập slug và 1 bảng hiển thị tên thô sơ. Chưa có nút/khung upload file, chưa xem được danh sách file con. | ⚠️ THÔ SƠ |
| **Trang Cấu hình (`#v-settings`)** | Bố cục 5 khối mạch lạc (Providers, Model, Thinking, Tuning, Save) | **Chưa đạt về thẩm mỹ**: Toàn bộ nhồi vào các thẻ `div.row` phẳng lì, thiếu cấu trúc thẻ Card, form thêm provider dùng `<details>` cụt lủn, bảng info model dính liền nhau. | ⚠️ THÔ SƠ |

---

## 2. TRIẾT LÝ THIẾT KẾ MỚI: MINIMALIST & CHỈN CHU

### 2.1. Kế Thừa Gì Từ UI Dự Án Cũ (`Novel-Translator`)?
Dự án cũ `Novel-Translator` có giao diện rất thanh lịch nhờ:
1. **Cấu trúc Card trắng phân tầng**: Nền trang xám nhạt (`#f8fafc`), các khối nội dung được bọc trong Card nền trắng (`#ffffff`), viền mảnh (`1px solid #e2e8f0`), bo góc nhẹ (`8px`), bóng đổ phẳng (`box-shadow: 0 1px 3px rgba(0,0,0,0.04)`).
2. **Typography có tôn ti**: Tiêu đề trang rõ ràng kèm dòng phụ đề giải thích; nhãn trường nhập liệu kiểu tracked in hoa nhỏ gọn (`font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: #64748b`).
3. **Phân chia khối Providers rõ rệt**: Thẻ riêng cho Google Gemini và Thẻ riêng cho OpenAI-compatible, có viền xanh nổi bật khi active (`border-color: #2563eb`).
4. **Bảng danh sách tối giản (Minimal Table)**: Không kẻ ô dọc thô ráp, chỉ dùng đường phân cách ngang `1px solid #f1f5f9`, hiệu ứng hover nhẹ `#f8fafc`.
5. **Huy hiệu & Trạng thái (Badges & Chips)**: Tag nhỏ gọn cho trạng thái (`FREE`, `ACTIVE ★`, `Gemini`, `Đã dịch`).

### 2.2. Khắc Phục Gì Để Đảm Bảo "Nhẹ, Đơn Giản, Không Màu Mè"?
* **Không dùng thư viện nặng**: Loại bỏ hoàn toàn `tachyons.min.css` (74KB) và `alpine.js` (45KB) của dự án cũ. Toàn bộ CSS mới được viết bằng Vanilla CSS tinh gọn (~150 dòng, < 4KB).
* **Không hiệu ứng hào nhoáng**: Không gradient neon, không animation kéo dài, không backdrop-blur nặng nề. Chỉ giữ lại vi transition `0.15s ease-in-out` cho hover nút bấm và focus viền ô nhập liệu.
* **Tối ưu hiển thị**: Giữ nguyên bố cục Sidebar 4 mục của `content-translator`, tăng diện tích hiển thị nội dung chính, sắp xếp các trường khoa học theo luồng mắt nhìn từ trên xuống dưới.

---

## 3. THIẾT KẾ CHI TIẾT TRANG QUẢN LÝ DỰ ÁN (`#v-projects`)

### 3.1. Bố Cục Trang
Trang Dự Án sẽ được chia thành 2 khu vực rõ ràng:
1. **Header Trang & Thanh Thao Tác**:
   * Tiêu đề: `Dự án`
   * Phụ đề: `Quản lý thư mục tài liệu và các bản dịch.`
   * Nút bấm:
     * `+ Tạo dự án mới` (Primary Button màu xanh `#2563eb`, mở form tạo nhanh)
     * `🔄 Làm mới` (Secondary Button)
2. **Khu Vực Thẻ Dự Án (Project Cards Grid)**:
   * Hiển thị dạng lưới responsive (1 cột trên màn hình nhỏ, 2–3 cột trên màn hình rộng).
   * **Nội dung mỗi Thẻ Dự Án**:
     * Icon thư mục 📁 + **Tên dự án (Slug)** (font-weight: 600, màu `#1e293b`).
     * Số lượng tập tin: `X files` (kèm thông tin số file đã dịch nếu có).
     * Hàng nút thao tác nhanh:
       * `✍️ Vào dịch`: Chuyển ngay sang tab **Biên Dịch**, tự động chọn dự án này trên dropdown.
       * `📂 Quản lý files`: Mở rộng khu vực xem chi tiết files và tải tài liệu của dự án.
       * `🗑 Xóa`: Nút icon xóa (có xác nhận `confirm()` trước khi thực thi).

### 3.2. Bảng Chi Tiết Tập Tin & Tải Lên (Project Files & Upload Panel)
Khi người dùng bấm vào một dự án hoặc bấm `📂 Quản lý files`:
* **Khu vực Tải tệp lên (Upload Area)**:
  * Khung viền đứt nét tối giản (`border: 1.5px dashed #cbd5e1`), kéo thả file hoặc click để chọn `.txt`, `.md`, `.html`.
  * Khi chọn file $	o$ Gọi ngay `POST /api/projects/{slug}/upload`, cập nhật danh sách tức thì mà không reload trang.
* **Bảng danh sách tập tin (Minimalist Files Table)**:
  * Cột **Tên tập tin**: Kèm icon loại file.
  * Cột **Trạng thái**:
    * Badge xám: `Chưa dịch` (file chỉ mới nằm trong `sources/`).
    * Badge xanh lá dịu: `Đã dịch` (file đã có kết quả trong `translated/`).
  * Cột **Thao tác**:
    * Nút `Dịch`: Chuyển thẳng sang tab Biên dịch với đúng project + file đã nạp.
    * Nút `Xem`: Xem nhanh nội dung nguồn/dịch.

---

## 4. THIẾT KẾ CHI TIẾT TRANG CẤU HÌNH AI (`#v-settings`)

Trang Cấu hình được chuẩn hóa thành **4 khối Card trắng độc lập** (dựa trên đặc tả v2.5):

### 4.1. Khối 1: Nhà Cung Cấp AI (AI Providers)
* **Thanh chọn & Trạng thái**:
  * Dropdown chọn Provider đang cấu hình + Nút `★ Đặt làm active` + Nút `Xóa provider`.
  * Provider đang active được gắn nhãn `[★ Đang kích hoạt]` màu xanh dương.
* **Thẻ chi tiết Provider (Provider Details Card)**:
  * Nhãn loại: `Google Gemini` hoặc `OpenAI-Compatible`.
  * Nhãn: `API KEYS (MỖI DÒNG 1 KEY — XÓA DÒNG = XÓA KEY)`
  * Textarea Keys: Font monospace (`font-family: monospace; font-size: 13px`), chiều cao 100px, cuộn mượt mà.
  * Với OpenAI-compatible: Hiện thêm 2 ô nhập liệu song song: `Base URL` (mặc định OpenRouter hoặc tùy biến) và `Link tài liệu (Docs URL)`.
* **Khu vực Thêm Provider Mới (Inline Accordion Card)**:
  * Nút bấm mở rộng `＋ Thêm provider OpenAI-compatible mới`.
  * Form tinh gọn gồm: Tên (Groq, Step, DeepSeek...), Base URL, API Key $	o$ Nút `Thêm`.

### 4.2. Khối 2: Lựa Chọn Mô Hình (Model Selection & Metadata)
* **Dòng điều khiển chính**:
  * Select chọn mô hình: Hiển thị model ID + Huy hiệu `[FREE]` với các model miễn phí.
  * Nút `🔄 Lấy danh sách mới`: Tải live từ API nhà cung cấp (cache 5 phút).
  * Mục `…tự nhập custom model…`: Khi chọn mục này, tự động lộ ô text để nhập mã model tùy ý.
* **Bộ lọc mô hình (Model Search Filter)**:
  * Ô tìm kiếm: Nhập từ khóa (vd: `deepseek`, `flash`, `free`).
  * Chế độ lọc: Dropdown `Bao gồm` hoặc `Loại trừ`.
* **Bảng thông số kỹ thuật mô hình (Model Info Strip)**:
  * Bố cục dạng thanh ngang gồm các chip nhỏ gọn:
    * `Input Limit`: Giới hạn token đầu vào (ví dụ: `1,000,000`).
    * `Output Limit`: Giới hạn token đầu ra (ví dụ: `8,192`).
    * `Context`: Tổng độ dài ngữ cảnh.
    * `Quota / Rate limits`: Hiện `usage/limit` (nếu có từ OpenRouter) hoặc link `quota ↗` chuyển đến Google AI Studio.
    * `ⓘ Thông tin chi tiết`: Link mở tài liệu chính thức của nhà cung cấp.

### 4.3. Khối 3: Mức Độ Suy Luận (Thinking Level)
* **Tùy chọn**: Dropdown 4 mức `OFF` (mặc định), `LOW`, `MEDIUM`, `HIGH`.
* **Ghi chú cảnh báo chuẩn**:
  * Hộp thông tin nền xám nhẹ viền mảnh:  
    `ⓘ Chỉ áp dụng cho Google Gemini. Đối với các provider OpenAI-compatible, trường này được bỏ qua hoàn toàn. Hãy chọn trực tiếp model non-reasoning nếu muốn tiết kiệm chi phí.`

### 4.4. Khối 4: Tốc Độ & Tham Số Yêu Cầu (Request Tuning)
* Bố cục lưới 3 cột ngang trên màn hình máy tính:
  1. **Chunk Size**: Số ký tự tối đa một đoạn cắt (mặc định: `16000 ký tự`).
  2. **API Delay**: Thời gian nghỉ an toàn giữa các request (mặc định: `2.0 giây`).
  3. **Response Timeout**: Thời gian chờ phản hồi tối đa của AI (mặc định: `90 giây`).
* Mỗi trường có nhãn tracked in hoa, đơn vị đo lường rõ ràng và icon `ⓘ` giải thích ngắn gọn.

### 4.5. Phân Định Nút Lưu & Thông Báo Phản Hồi (Feedback System)
* Tách biệt rõ ràng 2 nút hành động:
  * Nút `💾 Lưu Provider`: Lưu key, model mặc định, thinking, base_url cho provider đang chọn.
  * Nút `💾 Lưu Thiết Lập Chung`: Lưu Chunk Size, Delay, Timeout.
* Thông báo phản hồi: Banner trạng thái nhẹ (`.toast` hoặc `.alert`) xuất hiện tinh tế, tự mờ sau 3 giây (`✅ Đã lưu thành công` hoặc `❌ Lỗi: ...`), không làm xô lệch giao diện.

---

## 5. ĐẶC TẢ HỆ THỐNG CSS TINH GỌN (ZERO-DEPENDENCY)

Toàn bộ giao diện mới sử dụng hệ thống Design Token thuần bằng CSS Variables, nhúng trực tiếp trong `web/index.html`:

```css
:root {
  /* Bảng màu tối giản - Lấy cảm hứng từ Novel-Translator */
  --bg-app: #f8fafc;
  --bg-card: #ffffff;
  --bg-subtle: #f1f5f9;
  --border: #e2e8f0;
  --border-focus: #94a3b8;
  
  --text-main: #0f172a;
  --text-muted: #64748b;
  --text-sub: #94a3b8;
  
  --primary: #2563eb;
  --primary-hover: #1d4ed8;
  --primary-light: #eff6ff;
  
  --success: #16a34a;
  --success-bg: #f0fdf4;
  --danger: #dc2626;
  --danger-bg: #fef2f2;
  
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
}

/* Base Card Container */
.card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 1.25rem;
  margin-bottom: 1.25rem;
  box-shadow: var(--shadow-sm);
}

/* Minimal Table */
.table-minimal {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.table-minimal th {
  text-align: left;
  padding: 8px 12px;
  color: var(--text-muted);
  font-weight: 600;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border-bottom: 1px solid var(--border);
}
.table-minimal td {
  padding: 10px 12px;
  border-bottom: 1px solid #f8fafc;
  color: var(--text-main);
}
.table-minimal tr:hover td {
  background-color: var(--bg-subtle);
}

/* Form Controls */
.label-tracked {
  display: block;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 6px;
}
.input, .select, .textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  font-size: 14px;
  background: #ffffff;
  color: var(--text-main);
  outline: none;
  transition: border-color 0.15s ease;
}
.input:focus, .select:focus, .textarea:focus {
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1);
}

/* Buttons */
.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: #ffffff;
  color: var(--text-main);
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.btn:hover {
  background: var(--bg-subtle);
}
.btn-pri {
  background: var(--primary);
  color: #ffffff;
  border-color: var(--primary);
}
.btn-pri:hover {
  background: var(--primary-hover);
}
.btn-danger {
  color: var(--danger);
  border-color: #fecaca;
  background: #ffffff;
}
.btn-danger:hover {
  background: var(--danger-bg);
}
```

---

## 6. LỘ TRÌNH THỰC HIỆN & TIÊU CHÍ NGHIỆM THU

### 6.1. Các Bước Thực Hiện
1. **Bước 1: Cập nhật CSS Foundation**: Bổ sung Design Tokens và các lớp tiện ích tối giản vào thẻ `<style>` trong `web/index.html`.
2. **Bước 2: Nâng cấp Trang Quản lý Dự án (`#v-projects`)**:
   * Xây dựng layout Header + Project Cards Grid.
   * Xây dựng File Management Drawer kèm chức năng kéo thả / nút chọn file để gọi `POST /api/projects/{slug}/upload`.
   * Gắn sự kiện `✍️ Vào dịch` tự động đồng bộ sang tab Workspace.
   * Thêm endpoint `DELETE /api/projects/{slug}` trong `main.py` để hỗ trợ xóa dự án an toàn.
3. **Bước 3: Nâng cấp Trang Cấu hình AI (`#v-settings`)**:
   * Chia 5 khối Card trắng sạch sẽ.
   * Chuẩn hóa form Thêm Provider và hiển thị Provider active.
   * Căn chỉnh thanh thông số Model Info Strip dạng Chip.
   * Bố cục 3 cột cho Request Tuning.
4. **Bước 4: Kiểm thử hiển thị & Tương thích**:
   * Kiểm tra độ mượt trên trình duyệt: tải trang < 20ms, phản hồi tức thì.
   * Kiểm tra luồng dữ liệu: Tạo dự án $	o$ Upload file $	o$ Chuyển tab dịch $	o$ Sửa key/provider $	o$ Lưu thành công.

### 6.2. Tiêu Chí Nghiệm Thu (Definition of Done)
* [ ] Trang Dự Án hiển thị dạng Cards sạch sẽ, có nút tải file trực tiếp, có danh sách file nguồn/dịch.
* [ ] Trang Cấu Hình chia thành 4 khối Card trắng viền xám nhạt, trường nhập có nhãn tracked hoa, nút lưu phân tách rõ ràng.
* [ ] Hoàn toàn **không cài thêm bất kỳ thư viện npm hay package ngoài nào**.
* [ ] Trọng lượng file `web/index.html` < 35KB, tải nhanh tức thì.
* [ ] Không có bất kỳ hiệu ứng màu mè hay chuyển động giật lag.
