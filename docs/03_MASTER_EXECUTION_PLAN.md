# 03. KẾ HOẠCH THỰC THI CHI TIẾT DỰ ÁN MỚI (MASTER EXECUTION PLAN)
> **Mục tiêu tối thượng**: **Ngay sau Phase 2, hệ thống PHẢI có giao diện WebUI hoàn chỉnh và sử dụng được ngay lập tức các tính năng cốt lõi (tạo dự án, nạp file, chọn prompt, xem song ngữ, dịch trực tiếp)**.  
> Các phase sau (Phase 3, 4, 5) sẽ tiếp tục bổ sung các tính năng nâng cao (Thư viện prompt tương tác, Công cụ EPUB, Context Handoff, v.v.).  
> **Địa chỉ lưu trữ**: `docs/03_MASTER_EXECUTION_PLAN.md`

---

## 1. TỔNG QUAN PHÂN KỲ TRIỂN KHAI (5-PHASE BLUEPRINT)

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│                            LỘ TRÌNH 5 GIAI ĐOẠN (5 PHASES)                                  │
├────────────────────────────────┬────────────────────────────────────────────────────────────┤
│ PHASE 1: NỀN TẢNG LÕI BACKEND  │ Chunker smartHardSplit, Key Pool Cooldown 429,             │
│                                │ Prompt Engine .txt, Single SQLite DB.                      │
├────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ PHASE 2: UI CƠ BẢN DÙNG ĐƯỢC   │ 🎯 CỘT MỐC SỐNG CÒN: Mở WebUI lên là dùng được ngay!       │
│ NGAY (LEAN FUNCTIONAL WEBUI)   │ Giao diện React SPA đa trang, Sidebar thu gọn, Tạo dự án, │
│                                │ Kéo thả file, Chọn prompt chính + bổ sung, Dual-Pane Editor│
│                                │ stream bản dịch và lưu file hoàn tất!                      │
├────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ PHASE 3: CÁC TRANG BỔ TRỢ      │ Trang Thư viện Prompt tương tác (sửa file .txt trên web),  │
│                                │ Trang Nhật ký Live Logs SSE, Trang Lưu trữ & Checkpoint,   │
│                                │ Trang Tài liệu hướng dẫn.                                  │
├────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ PHASE 4: TÍNH NĂNG CAO CẤP     │ Công cụ EPUB chuyển đổi text 2 chiều & đóng gói sách,      │
│ (KẾ THỪA SILABOOK)             │ Tự động tóm tắt chương nối tiếp (previous_chunk_handoff),  │
│                                │ Trích xuất thực thể nhân vật đính kèm vào chunk.           │
├────────────────────────────────┼────────────────────────────────────────────────────────────┤
│ PHASE 5: ĐÓNG GÓI & PHÁT HÀNH  │ Kiểm thử tải 100 chương bằng cụm key Gemini miễn phí,      │
│                                │ Đóng gói 1-Click Launcher cho Windows / macOS / Linux.     │
└────────────────────────────────┴────────────────────────────────────────────────────────────┘
```

---

## 2. CHI TIẾT PHASE 1: NỀN TẢNG LÕI BACKEND & CỤM KEY POOL

### Task 1.1: Khởi Tạo Dự Án & Quản Lý Gói Tối Giản
* **Tệp tạo**: `pyproject.toml`
* **Dependencies**:
  ```toml
  [project]
  name = "content-translator"
  version = "1.0.0"
  description = "Minimalist AI Novel & Text Translator"
  requires-python = ">=3.12"
  dependencies = [
      "fastapi>=0.110.0",
      "uvicorn>=0.28.0",
      "pydantic>=2.6.0",
      "httpx>=0.27.0",
      "google-genai>=1.0.0",
      "python-dotenv>=1.0.0",
  ]

  [project.optional-dependencies]
  dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]
  ```

### Task 1.2: Xây Dựng `core/chunker.py` (Kế thừa giải thuật `smartHardSplit` từ silaBook)
* **Logic**:
  * Đếm từ $O(N)$ bằng `count_words` không tạo mảng rác regex.
  * Tìm điểm cắt lý tưởng trong dải **20% - 80%** quanh mốc **50%**:
    * Ưu tiên 1: Dấu xuống dòng kép `\n\n` (ngắt đoạn văn tự nhiên, bảo toàn tuyệt đối khối Markdown/khoảng cách dòng).
    * Ưu tiên 2: Dấu xuống dòng đơn `\n`.
    * Ưu tiên 3: Dấu kết thúc câu kèm khoảng trắng (`. `, `! `, `? `, `。`, `！`, `？`).
    * Ưu tiên 4: Dấu cách thông thường.
    * Fallback: Cắt tại mốc 50%.
  * Đệ quy chia đôi văn bản cho đến khi toàn bộ các đoạn đều $\le \text{max\_chars}$ (mặc định: 15.000 ký tự).

### Task 1.3: Xây Dựng `core/prompt_engine.py` (Thư Viện File `.txt` & Prompt Stacking)
* **Logic**:
  * Thư mục `prompts/` chứa các file `.txt` thuần túy.
  * Tự động khởi tạo `prompts/default_translation.txt` nếu chưa có.
  * Hàm `assemble_prompt()`:
    * Nhận `source_text`, `main_prompt_file`, danh sách `complementary_prompt_files`.
    * Tự động dồn các prompt bổ sung vào phần chỉ thị phụ.
    * Thay thế các biến động: `{{source_text}}`, `{{glossary_terms}}`, `{{previous_summary}}`.

### Task 1.4: Xây Dựng `core/key_pool.py` (Cụm Key Tối Ưu Token Miễn Phí)
* **Logic**:
  * Nhận danh sách API keys (Google Gemini hoặc OpenAI-compatible).
  * Điều phối Round-Robin luân chuyển đều giữa các key.
  * **Tự động Cooldown khi gặp HTTP 429**: Đánh dấu tạm khóa key trong 60 giây (`cooldown_until = now + 60`), chuyển ngay sang key tiếp theo trong pool để luồng dịch không bị gián đoạn.
  * Hàm `get_status()` trả về tình trạng từng key (Ready, Cooldown còn lại bao nhiêu giây, Số lượt gọi thành công) để WebUI hiển thị.

### Task 1.5: Xây Dựng `core/ai_client.py` (Adapter Gọi AI Đa Provider)
* **Logic**:
  * Gọi Google Gemini API hoặc endpoint tương thích OpenAI (OpenRouter, Groq, DeepSeek, Ollama).
  * Tự động bắt lỗi HTTP 429 để kích hoạt `mark_rate_limited()` trên Key Pool và tự động thử lại với key mới.

### Task 1.6: Xây Dựng `core/storage.py` (1 File SQLite Duy Nhất Cho Toàn Bộ App)
* **Đường dẫn DB**: `workspace/app.db`
* **Schema tối giản**:
  * Bảng `projects (slug PRIMARY KEY, title, created_at)`
  * Bảng `file_checkpoints (project_slug, filename, chunk_index, source_text, translated_text, status, updated_at, PRIMARY KEY (project_slug, filename, chunk_index))`

---

## 3. CHI TIẾT PHASE 2: WEBUI CƠ BẢN DÙNG ĐƯỢC NGAY & DỊCH THỬ NGHIỆM END-TO-END

> 🎯 **ĐÂY LÀ MILESTONE SỐNG CÒN**: Ngay sau Phase 2, người dùng **mở trình duyệt lên là có thể sử dụng được ngay toàn bộ tính năng cốt lõi**: Tạo dự án, Nạp file nguồn, Chọn Prompt chính + Prompt bổ sung, Bấm dịch, Xem so sánh song ngữ và lưu bản dịch hoàn chỉnh!

### Task 2.1: Xây Dựng FastAPI REST API & SSE Streaming Endpoints (`server.py`)
Cung cấp các API tinh gọn để Frontend giao tiếp:
* `POST /api/projects`: Tạo dự án mới (tự tạo thư mục `sources/` và `translated/`).
* `GET /api/projects`: Danh sách các dự án hiện có.
* `GET /api/projects/{slug}/files`: Danh sách các file trong dự án kèm trạng thái.
* `POST /api/projects/{slug}/upload`: Upload hoặc kéo thả các file `.txt`, `.md`, `.html`.
* `GET /api/prompts`: Danh sách các file prompt `.txt` có sẵn.
* `GET /api/keys`: Danh sách và trạng thái sức khỏe của cụm API Key.
* `POST /api/keys`: Cập nhật danh sách API Key.
* `GET /api/projects/{slug}/file-content`: Lấy nội dung file nguồn và bản dịch để hiển thị lên Dual-Pane Editor.
* `POST /api/projects/{slug}/translate`: Bắt đầu tiến trình dịch cho các file được chọn, stream tiến độ thời gian thực về WebUI qua **Server-Sent Events (SSE)**.

### Task 2.2: Thiết Lập Frontend React SPA (Vite + TailwindCSS + Shadcn UI)
* Khởi tạo dự án Frontend tinh gọn trong thư mục `frontend/`.
* Cài đặt: `react`, `react-dom`, `react-router-dom`, `lucide-react`, `zustand`, `tailwindcss`.
* Cấu hình proxy `vite.config.ts` trỏ về FastAPI Backend port `8000`.

### Task 2.3: Xây Dựng Layout Điều Hướng Với Sidebar Thu Gọn (Collapsible Sidebar)
* **Tệp tạo**: `frontend/src/components/Sidebar.tsx`
* **2 Trạng thái**:
  * **Expanded (260px)**: Logo + Tên dự án + Nút thu gọn `[◀]` + Danh sách menu kèm icon và nhãn chữ.
  * **Collapsed (64px)**: Logo thu nhỏ + Nút mở rộng `[▶]` + Menu dạng icon-only với tooltip khi hover.
* **Lưu trạng thái**: Tự động ghi nhớ vào `localStorage.getItem('sidebar_collapsed')`.
* **Hiệu quả**: Tối đa hóa diện tích bề ngang cho màn hình biên dịch song ngữ Dual-Pane.

### Task 2.4: Xây Dựng 3 Trang WebUI Cốt Lõi Hoạt Động Được Ngay

#### 1. Trang Quản Lý Dự Án & Tập Tin (`frontend/src/pages/ProjectsPage.tsx`)
* Ô nhập tên và nút `[+ Tạo Dự Án Mới]`.
* Danh sách card các dự án (Tên, Số file, Nút `[Vào Không Gian Dịch]`).
* Khu vực Kéo thả Upload: Thả trực tiếp các file `.txt`, `.md`, `.html` vào dự án.
* Bảng danh sách file nguồn với cột trạng thái (`Chưa dịch`, `Đang dịch`, `Hoàn thành`).

#### 2. Trang Workspace Biên Dịch Song Ngữ (`frontend/src/pages/WorkspacePage.tsx`) — *TRỌNG TÂM CỐT LÕI*
* **Cột trái (30% bề ngang)**:
  * Bảng chọn file với checkbox (`Select All`, `Select Unfinished`).
  * **Bộ chọn Prompt**:
    * Dropdown chọn *Prompt Chính* từ danh sách file `.txt` (mặc định: `default_translation.txt`).
    * Danh sách checkbox chọn thêm *Prompt Bổ Sung* (ví dụ: tick chọn `style_co_trang.txt`, `qa_polish.txt`).
  * Dropdown chọn Model / Key Pool.
  * Bộ nút bấm điều khiển: `[▶ Bắt Đầu Dịch]`, `[⏸ Tạm Dừng]`.
  * Thanh tiến độ tổng thể (Chunk X/Y, %).
* **Cột phải (70% bề ngang) - Dual-Pane Editor**:
  * Màn hình chia đôi song song:
    * Khung trái: Văn bản gốc (nguyên vẹn khoảng cách dòng, thụt lề).
    * Khung phải: Văn bản dịch tiếng Việt đang stream trực tiếp từng câu.
  * Nút bật/tắt **Cuộn Đồng Bộ (Sync-Scroll)**.
  * Khung bản dịch hỗ trợ sửa trực tiếp văn bản (Inline Editing) và tự động lưu.
  * Nút `[Tải File Bản Dịch (.md / .txt)]` về máy tính.

#### 3. Trang Cấu Hình Cụm Key (`frontend/src/pages/SettingsPage.tsx`)
* Textarea nhập danh sách API key miễn phí (mỗi dòng 1 key).
* Bảng trạng thái trực quan: 🟢 `Ready`, 🟡 `Cooldown 60s (Rate Limit)`, 🔴 `Lỗi`.
* Nút `[Lưu Cấu Hình]`.

---

### 🚀 TIÊU CHÍ NGHIỆM THU HOÀN TẤT PHASE 2: SỬ DỤNG ĐƯỢC NGAY!
Khi kết thúc Phase 2, quy trình kiểm thử thực tế diễn ra như sau:
1. Chạy lệnh: `python server.py` (Khởi động FastAPI + Server static build Frontend).
2. Người dùng mở trình duyệt truy cập: `http://localhost:8000`.
3. Vào trang **Cấu Hình**: Dán 1 hoặc nhiều API key Gemini.
4. Vào trang **Dự Án**: Bấm tạo dự án mới `Truyen_Tien_Hiep`, kéo thả 1 file `chuong_01.md` vào.
5. Vào trang **Biên Dịch (Workspace)**:
   * Tick chọn file `chuong_01.md`.
   * Chọn prompt chính: `default_translation.txt`.
   * Bấm `[▶ Bắt Đầu Dịch]`.
6. **Kết quả đạt chuẩn**:
   * Khung bên phải hiển thị stream từng chunk bản dịch tiếng Việt mượt mà.
   * Định dạng Markdown (tiêu đề `#`, danh sách `-`, trích dẫn `>`, dòng trống) giữ nguyên 100%.
   * File bản dịch hoàn tất tự động xuất hiện tại thư mục `workspace/projects/Truyen_Tien_Hiep/translated/chuong_01.md`.
   * Người dùng có thể chỉnh sửa trực tiếp trên khung và bấm tải file về máy.
7. **Khẳng định**: Người dùng đã có thể sử dụng ứng dụng hoàn chỉnh cho công việc dịch hàng ngày!

---

## 4. CHI TIẾT PHASE 3: HOÀN THIỆN CÁC TRANG NGHIỆP VỤ BỔ TRỢ

Sau khi Phase 2 đã dùng được ngay, Phase 3 hoàn thiện nốt các trang còn lại trên giao diện:

### Task 3.1: Trang Thư Viện Prompt Tương Tác (`/prompts`)
* Giao diện quản lý toàn bộ các file `.txt` trong thư mục `prompts/`.
* Trình soạn thảo văn bản trực tiếp trên WebUI: Cho phép người dùng tạo file prompt mới, sửa nội dung prompt `.txt` mà không cần mở Notepad/VSCode.
* Bảng tra cứu các biến hệ thống sẵn có: `{{source_text}}`, `{{glossary_terms}}`, `{{previous_summary}}`.

### Task 3.2: Trang Nhật Ký & Giám Sát Tiến Trình (`/logs`)
* Cửa sổ Terminal hiển thị dòng sự kiện SSE thời gian thực.
* Bộ lọc log: `Tất cả`, `Lỗi (ERROR)`, `Xoay vòng Key (KEY_ROTATION)`.
* Đồng hồ đo tốc độ xử lý: `Tokens / giây` và thống kê số lần tự động đổi key khi gặp 429.

### Task 3.3: Trang Quản Lý Lưu Trữ & Checkpoint (`/storage`)
* Bảng thống kê các phiên dịch dở lưu trong SQLite.
* Nút `[Khôi phục phiên]` cho các tác vụ bị gián đoạn do tắt máy đột ngột.
* Nút `[Xuất file ZIP toàn bộ dự án]` để tải bản dịch sạch về máy tính.
* Nút `[Xóa Cache / Dọn dẹp Checkpoint cũ]`.

### Task 3.4: Trang Tài Liệu & Hướng Dẫn Tích Hợp (`/docs`)
* Bài hướng dẫn chi tiết cách lấy 5 - 10 Google Gemini API Key miễn phí qua Google AI Studio.
* Hướng dẫn kết nối OpenRouter, Groq Cloud và Local Ollama.
* Cẩm nang viết prompt dịch văn học chất lượng cao.

---

## 5. CHI TIẾT PHASE 4: TÍNH NĂNG CAO CẤP & CÔNG CỤ EPUB

### Task 4.1: Trang Công Cụ EPUB Tối Giản (`/tools/epub`)
* **Nguyên tắc**: Chỉ nhận đầu vào là các file text (`.txt`, `.md`, `.html`), xử lý thuần túy là text.
* **Tính năng 1**: Chọn các file text/md/html trong dự án $\to$ Đóng gói thành file `.epub` hoàn chỉnh (tự động tạo trang bìa và mục lục TOC).
* **Tính năng 2**: Chuyển đổi định dạng văn bản 2 chiều (`MD sang TXT`, `HTML sang MD`, `TXT sang MD`) áp dụng cho cả thư mục `sources/` và `translated/`.

### Task 4.2: Tự Động Tóm Tắt & Ngữ Cảnh Nối Tiếp (`previous_chunk_handoff` - Kế Thừa silaBook)
* Sau khi dịch xong chương $N$, AI tự động tóm tắt 3-5 câu về cốt truyện và tâm lý nhân vật.
* Khi dịch chương $N+1$, đoạn tóm tắt này tự động được nạp vào thẻ `<previous_chunk_handoff>` trong prompt để giữ mạch truyện liền mạch qua các chương.

### Task 4.3: Công Cụ Trích Xuất Nhân Vật & Thuật Ngữ (Entity Extractor)
* Gửi nội dung file nguồn cho AI $\to$ Tự động sinh file `glossary.txt` tại thư mục dự án.
* Tích hợp tự động: Khi dịch chunk, hệ thống tự động đọc file `glossary.txt` này và **đính kèm vào prompt gửi cùng chunk** để AI dịch chuẩn xác 100% tên riêng.

---

## 6. CHI TIẾT PHASE 5: ĐÓNG GÓI & PHÁT HÀNH ONE-CLICK

### Task 5.1: Kiểm Thử Tải Quy Mô Lớn
* Thử nghiệm dịch 1 bộ tiểu thuyết 100 chương (khoảng 300.000 từ) bằng 5 Gemini Free API Key.
* Kiểm chứng tính ổn định của cơ chế tự động xoay key, tự động cooldown khi gặp 429 và kiểm tra tính toàn vẹn của cấu trúc định dạng Markdown đầu ra.

### Task 5.2: Đóng Gói 1-Click Launcher (Windows / macOS / Linux)
* Viết script khởi động tự động:
  * `start_windows.bat`: Tự động kích hoạt venv, khởi động FastAPI server và tự mở trình duyệt.
  * `start_mac_linux.sh`: Script 1-click cho macOS và Linux.
* Hướng dẫn chạy trên Private VPS qua `systemd` hoặc `docker-compose` tối giản.
