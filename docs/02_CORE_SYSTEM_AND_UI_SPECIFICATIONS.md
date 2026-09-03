# 02. ĐẶC TẢ HỆ THỐNG CỐT LÕI & THIẾT KẾ GIAO DIỆN ĐA TRANG
> **Tài liệu**: Đặc tả kiến trúc kỹ thuật, luồng dữ liệu, hệ thống trang riêng biệt và thiết kế thanh điều hướng thu gọn (Collapsible Sidebar).  
> **Định hướng**: Minimalist, tập trung vào quản lý tập tin nguồn và bản dịch, không dồn tất cả vào một trang thao tác.

---

## 1. KIẾN TRÚC HỆ THỐNG KỸ THUẬT (TECHNICAL ARCHITECTURE)

```
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                                 FRONTEND: REACT SPA (VITE)                                │
│  • React 19 + TypeScript + TailwindCSS + Shadcn UI + Lucide Icons                         │
│  • Navigation: React Router (8 Dedicated Pages) + Collapsible Sidebar                     │
│  • State: Zustand Store (Workspace, Projects, Key Pools, Prompts)                         │
└─────────────────────────────────────────────▲─────────────────────────────────────────────┘
                                              │ HTTP REST & Server-Sent Events (SSE)
┌─────────────────────────────────────────────▼─────────────────────────────────────────────┐
│                                 BACKEND: FASTAPI (PYTHON 3.12+)                           │
├───────────────────┬───────────────────┬───────────────────┬───────────────────────────────┤
│ 1. API ROUTERS    │ 2. CORE TRANSLATE │ 3. KEY POOL ENGINE│ 4. TOOLS & STORAGE            │
├───────────────────┼───────────────────┼───────────────────┼───────────────────────────────┤
│ • /api/projects   │ • Format Chunker  │ • Gemini Key Pool │ • EPUB Text Converter         │
│ • /api/workspace  │ • Prompt Engine   │ • OpenAI Adapter  │ • Single SQLite DB (State/CP) │
│ • /api/prompts    │ • Dynamic Filter  │ • Cooldown 429    │ • File System Project Storage │
│ • /api/providers  │ • Stream Emitter  │ • Round-Robin     │ • Glossary Extractor          │
└───────────────────┴───────────────────┴───────────────────┴───────────────────────────────┘
```

---

## 2. ĐẶC TẢ TÍNH NĂNG CỐT LÕI & CƠ CHẾ GỬI PROMPT

### 2.1. Bản chất Hoạt động Cốt lõi
* Hệ thống hoạt động dựa trên cơ chế: **Chia nhỏ tệp nguồn thành các Chunk $\to$ Gửi kèm Prompt lên AI $\to$ Nhận về bản dịch $\to$ Ghép lại giữ nguyên định dạng ban đầu**.
* **Thư viện Prompt dạng file `.txt`**:
  * Mỗi mẫu prompt là một tệp `.txt` độc lập lưu trong thư mục `prompts/`.
  * Có thể mở và chỉnh sửa trực tiếp bằng bất kỳ công cụ nào (Notepad, VSCode) hoặc sửa qua WebUI.
  * Cấu trúc biến động hỗ trợ:
    * `{{source_text}}`: Nội dung của chunk hiện tại (bắt buộc).
    * `{{glossary_terms}}`: Danh sách từ khóa/nhân vật xuất hiện trong chunk.
    * `{{previous_summary}}`: Tóm tắt bối cảnh từ chương trước (học tập từ silaBook).
    * `{{additional_instructions}}`: Khu vực ghép các prompt bổ sung.

### 2.2. Cơ chế Ghép Prompt Đa Tầng (Prompt Stacking)
* **Mặc định**: Hệ thống chạy: `Chunk + Prompt Chính (default_translation.txt)`.
* **Linh hoạt chọn thêm Prompt Bổ Sung**:
  * Người dùng có thể chọn kèm 1 hoặc nhiều prompt bổ sung từ danh sách file `.txt` để điều chỉnh kết quả theo ý muốn.
  * *Ví dụ*:
    * File chọn: `Hoi_01.md`, `Hoi_02.md`
    * Prompt chính: `default_translation.txt` (Dịch chuẩn, ép giữ nguyên cấu trúc Markdown/thụt dòng).
    * Prompt bổ sung 1: `style_co_trang.txt` (Dặn dò dùng từ Hán-Việt, xưng hô phụ mẫu, đạo hữu).
    * Prompt bổ sung 2: `vietnamese_literary_polish.txt` (Dặn dò trau chuốt câu từ uyển chuyển).
  * Backend tự động hợp nhất các prompt bổ sung vào phần chỉ thị phụ trước khi gửi cho AI.

### 2.3. Quản lý Cụm Key Pool & Tối Ưu Token Miễn Phí
* **Google Gemini Pool**:
  * Cho phép dán hàng loạt API key miễn phí (mỗi dòng 1 key).
  * Cân bằng tải vòng tròn (Round-Robin).
  * **Tự động Cooldown khi gặp HTTP 429**: Tạm khóa key bị 429 trong 60 giây (`cooldown_until = time.time() + 60`), chuyển ngay sang key tiếp theo trong pool để luồng dịch không bao giờ bị dừng.
* **OpenAI-Compatible Providers**:
  * Cấu hình linh hoạt: `Base URL`, `API Key`, `Model Name`.
  * Tương thích với các nguồn token miễn phí hoặc cực rẻ: **OpenRouter (Free models: Qwen 2.5, Llama 3)**, **Groq Cloud (Free tier tốc độ cao)**, **DeepSeek API**, **Local Ollama**.

### 2.4. Mô Hình Đơn Người Dùng & Không Cần Lớp Bảo Mật Ứng Dụng (Zero Auth)
* Ứng dụng phục vụ **duy nhất một người dùng** (Local hoặc Private VPS).
* **Không xây dựng**: Hệ thống User, Login, Register, JWT token, mã hóa Web Crypto API rườm rà hay phân quyền RBAC.
* Mở ứng dụng là vào thẳng làm việc ngay lập tức, người dùng tự bảo vệ hệ thống của mình ở tầng mạng (Firewall, SSH Tunnel, VPN).

---

## 3. TRIẾT LÝ GIAO DIỆN: THỰC DỤNG, SIÊU NHẸ (UTILITARIAN LEAN UI)

* **Tôn chỉ thiết kế**: **Nhanh — Nhẹ — Rõ ràng — Tập trung vào con chữ**, **KHÔNG hào nhoáng bóng bẩy**:
  * ❌ **Không dùng**: Glassmorphism (làm mờ kính), gradient màu mè, animation chuyển cảnh phức tạp gây giật lag.
  * ✅ **Tập trung vào**: Tốc độ tải trang tức thì (< 0.2s), độ tương phản cao, phông chữ tối ưu cho việc đọc text dài, phản hồi mượt mà không có độ trễ.
  * ✅ **Tối đa hóa diện tích đọc**: Mọi thành phần thừa thãi đều bị lược bỏ để nhường chỗ cho văn bản.

### Thanh Điều Hướng Sidebar Thu Gọn (Collapsible Sidebar)
Để giải quyết bài toán không gian hiển thị cho việc dịch văn bản song ngữ, thanh điều hướng Sidebar hỗ trợ **2 trạng thái**:

```
TRẠNG THÁI MỞ RỘNG (EXPANDED - 260px):           TRẠNG THÁI THU GỌN (COLLAPSED - 64px):
┌───────────────────────────┐                    ┌──────────┐
│ [LOGO] NOVEL TRANSLATOR   │ [◀ Thu gọn]        │ [LOGO]   │ [▶ Mở]
├───────────────────────────┤                    ├──────────┤
│ 📁  Quản Lý Dự Án         │                    │ 📁       │ (Tooltip: Dự Án)
│ ✍️   Biên Dịch & Nội Dung   │                    │ ✍️        │ (Tooltip: Biên Dịch)
│ 📜  Thư Viện Prompt       │                    │ 📜       │ (Tooltip: Prompt)
│ 📖  Công Cụ EPUB          │                    │ 📖       │ (Tooltip: EPUB)
│ ⚙️   Cấu Hình AI & Keys    │                    │ ⚙️        │ (Tooltip: Cấu Hình)
│ ⚡  Nhật Ký & Giám Sát    │                    │ ⚡       │ (Tooltip: Nhật Ký)
│ 💾  Lưu Trữ & Checkpoint  │                    │ 💾       │ (Tooltip: Lưu Trữ)
│ 📚  Tài Liệu & Chỉ Dẫn    │                    │ 📚       │ (Tooltip: Tài Liệu)
└───────────────────────────┘                    └──────────┘
```

* **Cơ chế hoạt động**:
  * Nút bấm thu gọn đặt ở đầu hoặc cuối thanh Sidebar.
  * Khi bấm thu gọn: Chiều rộng Sidebar thu hẹp từ **260px xuống 64px**, chỉ hiển thị icon với tooltip nổi khi di chuột qua.
  * Toàn bộ không gian được giải phóng (hơn 190px) được cộng trực tiếp vào màn hình làm việc trung tâm (**Dual-Pane Editor**), giúp hiển thị được nhiều từ trên 1 dòng hơn, hạn chế tối đa tình trạng quấn dòng (line-wrap).
  * Trạng thái thu gọn được lưu tự động vào `localStorage` để duy trì qua các phiên làm việc.

---

## 4. ĐẶC TẢ CHI TIẾT 8 TRANG GIAO DIỆN RIÊNG BIỆT (DEDICATED PAGES)

### Trang 1: Quản Lý Dự Án & Tập Tin (`/projects`)
* **Mục đích**: Điểm bắt đầu quản lý các đầu sách / tài liệu.
* **Các thành phần UI**:
  * Nút bấm: `[+ Tạo Dự Án Mới]`, `[Nhập Dự Án]`.
  * Danh sách Card dự án: Tên dự án, ảnh bìa (nếu có), số chương, % hoàn thành, nút `[Mở Dự Án]`.
  * Khung kéo thả Upload: Cho phép nạp hàng loạt file `.txt`, `.md`, `.html` vào dự án.
  * Bảng danh sách file trong dự án: Tên file, dung lượng, trạng thái (`Chưa dịch`, `Đang dịch`, `Hoàn thành`).

### Trang 2: Xử Lý Nội Dung & Biên Dịch Song Ngữ (`/workspace`) — *TRỌNG TÂM CỐT LÕI*
* **Mục đích**: Nơi người dùng thực hiện toàn bộ thao tác dịch và duyệt văn bản.
* **Bố cục 2 cột chính**:
  * **Cột trái (Điều phối File & Prompt - 30% bề ngang)**:
    * Bảng chọn file với checkbox (Chọn tất cả, Chọn file chưa dịch).
    * **Bộ chọn Prompt**:
      * Dropdown chọn *Prompt Chính* từ thư viện `.txt`.
      * Danh sách checkbox chọn *Prompt Bổ Sung* (ví dụ: `+ Tiên Hiệp`, `+ Trau Chuốt`).
      * Checkbox `[Đính kèm Glossary dự án]`.
    * Dropdown chọn Cụm Key / Model (Gemini Pool, OpenAI Pool, Ollama).
    * Nút hành động: `[▶ Bắt Đầu Chạy]`, `[⏸ Tạm Dừng]`, `[🔄 Chạy Lại File Lỗi]`.
    * Thanh tiến độ tổng thể và thời gian ước tính.
  * **Cột phải (Dual-Pane Translation Editor - 70% bề ngang)**:
    * Chia đôi màn hình song song:
      * Bên trái: Văn bản gốc (nguyên vẹn khoảng cách dòng và cấu trúc thụt lề).
      * Bên phải: Văn bản dịch tiếng Việt (stream token theo thời gian thực).
    * Thanh công cụ editor: Nút bật/tắt **Cuộn Đồng Bộ (Sync-Scroll)**, Nút **Lưu Thủ Công**, Nút **Xuất File Nhanh**.
    * Khung bản dịch cho phép sửa trực tiếp văn bản (Inline Editing).

### Trang 3: Thư Viện Prompt (`/prompts`)
* **Mục đích**: Quản lý kho prompt `.txt` phong phú và linh hoạt.
* **Các thành phần UI**:
  * Danh sách các file prompt `.txt` có trong thư mục `prompts/`.
  * Bộ lọc phân loại: `Dịch thuật`, `Phong cách văn học`, `Soát lỗi/Trau chuốt`, `Tóm tắt`.
  * Trình soạn thảo văn bản tích hợp (Textarea / CodeMirror nhẹ) để chỉnh sửa nội dung file prompt.
  * Bảng tra cứu các biến hệ thống sẵn có: `{{source_text}}`, `{{glossary_terms}}`, `{{previous_summary}}`.
  * Nút bấm: `[+ Tạo Prompt Mới]`, `[Nhân Bản]`, `[Lưu File .txt]`.

### Trang 4: Công Cụ EPUB & Chuyển Đổi Định Dạng Văn Bản (`/tools/epub`)
* **Mục đích**: Trang chuyên biệt dành cho công cụ EPUB tối giản.
* **Các thành phần UI**:
  * Bộ lọc chọn file từ thư mục `sources/` (nguồn) hoặc `translated/` (bản dịch).
  * **Phân vùng 1: Đóng Gói EPUB**:
    * Chọn các file text/md/html muốn gom thành sách.
    * Nhập metadata: Tên sách, Tác giả, Chọn ảnh bìa (Cover Image).
    * Nút bấm: `[Đóng gói thành file EPUB]`.
  * **Phân vùng 2: Chuyển Đổi Định Dạng Văn Bản (Bidirectional Converter)**:
    * Chọn các file cần chuyển đổi.
    * Chọn chiều chuyển đổi: `MD sang TXT`, `HTML sang MD`, `TXT sang MD`.
    * Nút bấm: `[Thực hiện chuyển đổi]` (Lưu trực tiếp vào thư mục tương ứng).

### Trang 5: Cấu Hình AI & Quản Lý Cụm Key Tối Ưu Token Miễn Phí (`/settings`)
* **Mục đích**: Cấu hình các kết nối AI và tối ưu hóa chi phí.
* **Các thành phần UI**:
  * **Google Gemini Pool**:
    * Textarea nhập danh sách API key miễn phí (mỗi dòng 1 key).
    * Bảng trạng thái trực quan: Trạng thái từng key (🟢 `Ready`, 🟡 `Cooldown 60s`, 🔴 `Error`), số lượt gọi thành công, thời gian mở lại.
  * **OpenAI-Compatible Endpoints**:
    * Cấu hình Base URL, API Key, Model cho OpenRouter, Groq, DeepSeek, Local Ollama.
  * **Cấu hình Chunker**:
    * Độ dài tối đa mỗi chunk (mặc định: 18.000 ký tự cho Gemini, 6.000 ký tự cho GPT).

### Trang 6: Nhật Ký & Giám Sát Tiến Trình (`/logs`)
* **Mục đích**: Đọc log hệ thống trực tiếp.
* **Các thành phần UI**:
  * Cửa sổ dòng lệnh Terminal giả lập stream log thời gian thực qua SSE.
  * Bộ lọc log: `Tất cả`, `Lỗi (ERROR)`, `Xoay Key (KEY_ROTATION)`, `AI Output`.
  * Widget đo lường: Tốc độ xử lý (Tokens/s), số request/phút (RPM).

### Trang 7: Quản Lý Lưu Trữ & Checkpoint (`/storage`)
* **Mục đích**: Quản trị dữ liệu, sao lưu và dọn dẹp.
* **Các thành phần UI**:
  * Danh sách các phiên checkpoint đang lưu trong SQLite.
  * Nút `[Khôi phục phiên]` cho các tác vụ bị ngắt quãng do mất điện/mất mạng.
  * Nút `[Xuất file ZIP toàn bộ dự án]` để tải bản dịch sạch về máy tính.
  * Nút `[Xóa Cache / Dọn dẹp Checkpoint cũ]`.

### Trang 8: Tài Liệu Dự Án & Hướng Dẫn Sử Dụng (`/docs`)
* **Mục đích**: Cung cấp cẩm nang sử dụng tích hợp sẵn trong ứng dụng.
* **Các thành phần UI**:
  * Bài hướng dẫn chi tiết cách tạo hàng loạt API key Gemini miễn phí qua Google AI Studio.
  * Hướng dẫn kết nối OpenRouter, Groq và Ollama.
  * Hướng dẫn viết prompt và tạo các prompt bổ sung hiệu quả.
