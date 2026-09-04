# 04. KẾ HOẠCH PHASE 2: GIAO DIỆN WEBUI LEAN & PHẢN HỒI NHANH
> **Mục tiêu**: Xây dựng giao diện WebUI siêu nhẹ, phản hồi tức thì, phục vụ MỘT PHIÊN DỊCH TẠI MỘT THỜI ĐIỂM.  
> **Cam kết**: Giúp người dùng thao tác prompt dễ hơn, kiểm tra chunk dễ hơn, sao chép / lưu file nhanh hơn và gửi lại tức thời khi cần.
> **Phiên bản**: v2.3 (04/09/2026) — chốt stack + API contract tối thiểu.
>
> **Stack chốt**: `server.py` stdlib (`http.server`, không FastAPI), frontend HTML/CSS/JS thuần (không build-chain React), tái dùng 100% `core/` Phase 1. 1 phiên in-flight, không queue/worker.

---

## 1. NGUYÊN TẮC THIẾT KẾ GIAO DIỆN PHASE 2

Mọi thành phần trên giao diện WebUI phải vượt qua câu hỏi sát hạch:  
> *"Thành phần này có giúp người dùng gửi nội dung cho AI và nhận bản dịch về một cách đơn giản, nhanh và nhẹ nhất không?"*

### Những gì LOẠI BỎ KHỎI Phase 2:
* ❌ Không Auto-resume / Checkpoint.
* ❌ Không Task manager / Background worker / Queue / Job status.
* ❌ Không Tóm tắt tự động / Context memory tự động / Quality scoring.
* ❌ Không Multi-user / Auth / Database nhiều bảng.
* ❌ Không Dashboard task / History panel / Recovery panel.

### Những gì TẬP TRUNG XÂY DỰNG trong Phase 2:
* ✅ **Prompt dễ dùng hơn**: Chọn file `.txt`, xem nội dung, chỉnh sửa và lưu prompt trực tiếp trên web.
* ✅ **Chunk dễ kiểm tra hơn**: Hiển thị rõ danh sách các chunk (thường 2-3 chunk), số ký tự thực tế, số token ước lượng.
* ✅ **Kết quả dễ sao chép & lưu hơn**: Nút **[Sao chép]** (1-click copy) và **[Lưu file]** (ghi thẳng vào `translated/`).
* ✅ **Gửi lại dễ hơn**: Nút **[Xóa & Gửi lại]** và nút **[Gửi lại]** khi gặp lỗi mạng / 429.
* ✅ **Kế thừa các tính năng hữu ích từ UI cũ**: Màn hình song ngữ **Dual-Pane** cuộn đồng bộ (Sync-Scroll) và cho phép sửa trực tiếp văn bản dịch (Inline Edit).

---

## 2. KIẾN TRÚC GIAO DIỆN: ĐA TRANG ĐỘC LẬP & SIDEBAR THU GỌN

```text
Thanh Sidebar (Thu gọn được 260px -> 64px):
 ├── 📁 Dự Án (/projects)     : Quản lý thư mục dự án, nạp file nguồn
 ├── ✍️ Biên Dịch (/workspace) : Trọng tâm cốt lõi, gửi nhận trực tiếp 1 phiên
 ├── 📜 Prompt (/prompts)     : Quản lý, xem và sửa các file prompt .txt
 └── ⚙️ Cấu Hình (/settings)   : Nhập danh sách key Gemini, chỉnh model & timeout
```

---

## 3. CHI TIẾT CÁC MÀN HÌNH TRONG PHASE 2

### 3.1. Trang 1: Quản Lý Dự Án & Nạp File (`/projects`)
* **Thao tác nhanh**:
  * Nhập tên dự án $\to$ Bấm `[Tạo Dự Án]` $\to$ Tự động tạo cấu trúc `sources/`, `translated/`.
  * Kéo thả file `.txt`, `.md`, `.html` trực tiếp vào khung upload để nạp vào thư mục `sources/`.
  * Bảng danh sách file nguồn hiển thị: Tên file, Dung lượng, Trạng thái (Đã dịch / Chưa dịch).
  * Nút `[Chuyển Sang Biên Dịch]` để đưa các file được chọn vào màn hình Workspace.

### 3.2. Trang 2: Workspace Biên Dịch Song Ngữ (`/workspace`) — *TRỌNG TÂM CỐT LÕI*

Giao diện chia làm 2 khu vực trực quan:

#### A. Cột Điều Khiển Bên Trái (30% bề ngang):
1. **Danh sách file nguồn**:
   * Hiển thị các file đã chọn.
   * Hiển thị bảng phân đoạn các chunk của file hiện tại:
     * *Chunk 1: 16,200 ký tự (~4,050 tokens)*
     * *Chunk 2: 15,850 ký tự (~3,960 tokens)*
2. **Bộ chọn Prompt linh hoạt**:
   * Dropdown chọn *Prompt Chính* (`default_translation.txt`).
   * Danh sách checkbox chọn thêm *Prompt Bổ Sung* (ví dụ: `+ style_co_trang.txt`, `+ qa_polish.txt`).
3. **Bộ nút điều khiển phiên gửi–nhận**:
   * `[▶ Bắt Đầu Dịch]`: Gửi tuần tự các chunk của file lên AI.
   * `[📋 Sao Chép Bản Dịch]`: Copy toàn bộ nội dung bản dịch vào clipboard.
   * `[💾 Lưu Vào File]`: Lưu nội dung vào `workspace/projects/{slug}/translated/{filename}`.
   * `[❌ Xóa & Gửi Lại]`: Xóa kết quả hiện tại và gửi lại từ đầu.
   * `[🔄 Gửi Lại (Retry)]`: Nút này sáng lên khi gặp lỗi mạng hoặc lỗi 429 để người dùng chủ động bấm gửi lại.

#### B. Màn hình Dual-Pane Bên Phải (70% bề ngang):
* **Bên trái**: Văn bản gốc (nguyên vẹn cấu trúc dòng, tiêu đề Markdown `#`, trích dẫn `>`).
* **Bên phải**: Văn bản dịch tiếng Việt đang nhận về từ AI.
* **Tính năng kế thừa từ UI cũ**:
  * **Cuộn đồng bộ (Sync-Scroll)**: Cuộn văn bản gốc thì văn bản dịch cuộn theo tương ứng.
  * **Chỉnh sửa trực tiếp (Inline Edit)**: Người dùng có thể click vào khung dịch sửa từ ngữ ngay lập tức trước khi bấm lưu file.

### 3.3. Trang 3: Quản Lý Thư Viện Prompt (`/prompts`)
* Liệt kê danh sách các file prompt `.txt` từ thư mục `prompts/`.
* Cho phép mở ra xem nội dung, chỉnh sửa câu chữ và bấm **[Lưu Prompt]**.
* Cung cấp nút **[+ Tạo Prompt Mới]** (lưu thành file `.txt` mới).

### 3.4. Trang 4: Cấu Hình Tối Giản (`/settings`)
* 2 textarea nhập API Key theo provider (mỗi dòng 1 key, lưu vào `config/keys.json`): Gemini + OpenAI-compatible.
* 2 dropdown `default_provider` / `default_model` (options lấy từ `config.json`), ô `base_url` cho OpenAI-compatible, ô `max_chunk_chars` (mặc định 16.000).

---

## 4. API CONTRACT TỐI THIỂU (CHỐT v2.3 — ĐỦ LÀM XONG PHASE 2)

`server.py` stdlib `http.server`, port 8000, serve `web/` static + 12 endpoint JSON dưới đây. Không auth (single-user local). Mọi lỗi trả `{"error": "<thông điệp tiếng Việt>"}` + HTTP status phù hợp. Dịch là **SSE** để UI hiện từng chunk ngay, không polling.

| # | Method + Path | Request | Response / SSE | Ghi chú |
|---|---|---|---|---|
| 1 | `GET /api/health` | — | `{"ok": true}` | Kiểm tra server sống |
| 2 | `GET /api/projects` | — | `{"projects": [{"slug": "Kiem_Hiep", "files": 12}]}` | Đọc từ app.db |
| 3 | `POST /api/projects` | `{"slug": "Kiem_Hiep"}` | `{"slug": "Kiem_Hiep"}` | Tạo `sources/`, `translated/`, `assets/` |
| 4 | `GET /api/projects/{slug}/files` | — | `{"sources": ["ch01.md"], "translated": ["ch01.md"]}` | So sánh 2 thư mục |
| 5 | `POST /api/projects/{slug}/upload` | multipart `file` (.txt/.md/.html) | `{"filename": "ch01.md", "chars": 32100}` | Lưu vào `sources/` |
| 6 | `GET /api/chunks?project=S&file=F` | — | `{"chunks": [{"i": 1, "chars": 16200, "tokens_est": 4050, "preview": "..."}]}` | Dùng chung `split_text`; tokens_est = `chars/4` |
| 7 | `POST /api/translate` (SSE) | `{"project": "S", "file": "F", "provider": "gemini", "model": "gemini-2.5-flash", "prompt": "default_translation.txt", "extra_prompts": []}` | SSE: `event: chunk\ndata: {"i":1,"n":2,"text":"..."}` … cuối `event: done\ndata: {"chars": 30000}` hoặc `event: error\ndata: {"error": "..."}` | Tuần tự từng chunk, lỗi dừng ngay, không lưu dở dang |
| 8 | `POST /api/save` | `{"project": "S", "file": "F", "content": "..."}` | `{"path": "translated/ch01.md"}` | Ghi đè `translated/`, cập nhật app.db |
| 9 | `GET /api/prompts` | — | `{"prompts": ["default_translation.txt"]}` | Liệt kê `prompts/*.txt` |
| 10 | `GET /api/prompts/{name}` | — | `{"name": "...", "content": "..."}` | Sanitize như filename |
| 11 | `PUT /api/prompts/{name}` | `{"content": "..."}` | `{"ok": true}` | Lưu prompt |
| 12 | `GET /api/settings` / `PUT /api/settings` | GET — / PUT `{"default_provider": "...", "default_model": "...", "max_chunk_chars": 16000, "gemini_keys": [...], "openai_compat_keys": [...]}` | GET trả config+models / PUT validate tối thiểu rồi lưu | Keys không bao giờ log |

Ví dụ SSE khi bấm `[Bắt Đầu Dịch]`:
```text
POST /api/translate {"project":"Kiem_Hiep","file":"chuong_01.md","provider":"gemini","model":"gemini-2.5-flash","prompt":"default_translation.txt"}
→ event: chunk {"i":1,"n":2,"text":"...bản dịch chunk 1..."}
→ event: chunk {"i":2,"n":2,"text":"...bản dịch chunk 2..."}
→ event: done {"chars": 30500}
→ (lỗi) event: error {"error": "❌ TẤT CẢ API KEY ĐỀU BỊ 429, bấm Gửi Lại sau ít phút."}
```

`server.py` mẫu (~khung, tái dùng `core/`):
```python
# server.py — http.server stdlib, không FastAPI
from http.server import BaseHTTPRequestHandler, HTTPServer
import json, urllib.parse
from core.chunker import split_text
from core.prompt_engine import PromptEngine
# ... route GET /api/* đọc app.db / workspace, POST /api/translate chạy asyncio từng chunk và flush SSE
if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
```

---

## 5. TIÊU CHÍ NGHIỆM THU PHASE 2 (HOÀN TOÀN DÙNG ĐƯỢC CHO CÔNG VIỆC THỰC TẾ)

Sau khi hoàn thành Phase 2, người dùng:
1. Chạy `python server.py` $\to$ Mở trình duyệt `http://localhost:8000`.
2. Tạo dự án `Kiem_Hiep`, kéo file `chuong_01.md` vào.
3. Vào Workspace: Thấy rõ file được chia thành 2 chunk, số ký tự và token ước lượng rõ ràng, chọn provider/model explicit.
4. Bấm `[▶ Bắt Đầu Dịch]` $\to$ Thấy văn bản tiếng Việt hiển thị song song ngay bên cạnh (SSE từng chunk).
5. Nếu gặp lỗi 429 hay lỗi mạng $\to$ UI hiển thị thông báo đỏ rõ ràng và hiện nút `[Gửi Lại]` (không tự fallback model).
6. Dịch xong $\to$ Bấm `[Lưu Vào File]` $\to$ File xuất hiện ngay trong `translated/chuong_01.md`, app.db cập nhật.

---

## 6. LỘ TRÌNH TRIỂN KHAI CÁC PHASE TIẾP THEO (PHASE 3, 4, 5)

Nhằm giữ cho Phase 1 và Phase 2 tập trung tuyệt đối vào việc chạy ổn định, các tính năng mở rộng được phân kỳ thực hiện lần lượt:

* **PHASE 3: TIỆN ÍCH FILE & GLASSARY (OpenAI đã xong từ Phase 1)**:
  1. ~~Hỗ trợ thêm Provider OpenAI~~ → ĐÃ LÀM ở Phase 1 v2.3.
  2. Bổ sung thư mục `assets/` riêng của từng dự án (`workspace/projects/{slug}/assets/glossary.txt` + prompt riêng).
  3. Công cụ Tìm kiếm & Thay thế hàng loạt (Batch Search & Replace) trong thư mục `translated/`.
  4. Trình so sánh Diff chi tiết giữa bản dịch cũ và mới.

* **PHASE 4: CÔNG CỤ EPUB & NÂNG CAO (KẾ THỪA SILABOOK)**:
  1. Công cụ EPUB: Chuyển đổi định dạng 2 chiều giữa MD $\leftrightarrow$ TXT $\leftrightarrow$ HTML và đóng gói sách `.epub` chuẩn.
  2. Tự động sinh tóm tắt bối cảnh nối tiếp giữa các chương (`previous_chunk_handoff`).

* **PHASE 5: ĐÓNG GÓI & PHÁT HÀNH**:
  1. Kiểm thử tải dịch khối lượng lớn với 100 chương truyện.
  2. Đóng gói script khởi động 1-click cho người dùng cá nhân (Local / Private VPS).
