# 04. KẾ HOẠCH PHASE 2: GIAO DIỆN WEBUI LEAN & PHẢN HỒI NHANH
> **Mục tiêu**: Xây dựng giao diện WebUI siêu nhẹ, phản hồi tức thì, phục vụ MỘT PHIÊN DỊCH TẠI MỘT THỜI ĐIỂM.  
> **Cam kết**: Giúp người dùng thao tác prompt dễ hơn, kiểm tra chunk dễ hơn, sao chép / lưu file nhanh hơn và gửi lại tức thời khi cần.
> **Phiên bản**: v3.0.0 (05/09/2026) — đặc tả gốc Phase 2 + cập nhật hiện hành (§3 rewrite theo UI thật, §4 contract mở rộng).
> **Lưu ý đọc:** §1–§2 (nguyên tắc, kiến trúc) giữ nguyên giá trị. §3, §5 bước, §6 roadmap đã viết lại theo thực tế; chi tiết pha sau xem `docs/16_NEXT_PHASES.md`.
>
> **Stack chốt**: `main.py` stdlib (`http.server`, không FastAPI), frontend HTML/CSS/JS thuần (không build-chain React), tái dùng 100% `core/` Phase 1. 1 phiên in-flight, không queue/worker.

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
* ✅ **Kết quả dễ sao chép & lưu hơn**: Nút **[Sao chép]** (1-click copy) và **[Lưu file]** (ghi thẳng vào `results/`).
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

### 3.1. Trang 1: Cards Dự Án (`/projects`)

* **Tạo dự án:** dialog Tên sách + Tác giả + Mô tả → slug tự sinh (duy nhất) → card mới. Không form nhập slug.
* **Mỗi card:** click tên mở Workspace; tác giả/mô tả (ẩn khi trống); `done/sources tập tin`; thanh tiến độ + % (xanh khi ≥100%); icon sửa info / lưu trữ (zip) / xóa — hover hiện text.
* Nút 🔄 Làm mới + bảng Lịch sử chạy cuối trang.

### 3.2. Trang 2: Workspace Biên Dịch 3 Cột (`/workspace`) — *TRỌNG TÂM CỐT LÕI*

* **Cột Tập tin:** tabs Nguồn/Kết quả, kéo-thả upload đúng tab (không gate ext), lọc/sort keyword, checkbox + chọn-hết (chỉ visible), dot trạng thái cặp cùng tên, đổi tên (đơn/`_conflict`, hàng loạt pattern `{N}`), xóa; toolbar icon SVG + tooltip; khóa khi đang dịch.
* **Cột Nguồn / Kết quả:** dual editor, sync-scroll, wrap mặc định + nút toggle, dòng thông tin file (ký tự/từ/tokens), click file nạp 2 chiều cùng tên.
* **Gửi AI (1 nút):** dialog chọn Gộp-chia-chunk (marker `===== FILE`, tách đúng về từng file, tự lưu `results/`) hoặc Tuần tự; kèm provider/model/prompt/chars/chunks; tối ưu limit ngày/giờ. Thanh công cụ: Hủy (cắt cả request đang bay), Sao chép, Lưu, Gửi lại, Xóa & gửi lại.
* **Tìm/thay kiểu Sigil** trong `<dialog>` (regex PCRE, `$1` file này / `\1` tất cả file, binary skip) + terminal log đen dưới editor.

### 3.3. Trang 3: Quản Lý Thư Viện Prompt (`/prompts`)
* Liệt kê, mở, sửa, lưu, tạo mới, **đổi tên, xóa** prompt `.txt`.
* **Prompt mặc định** (`default_prompt` trong prefs): dropdown hiện ✓ đầu list + preselect ở Workspace; bất khả xóa/đổi tên (400); file mất → fallback + warn.
* Nút **⬇ Lưu vào dự án**: backup prompt vào `assets/prompts/` của project đã chọn (1 endpoint chung).

### 3.4. Trang 4: Cấu Hình AI (`/settings`) — v2.5 (5 khối, xem `docs/wip/SETTINGS_REDESIGN_v2.5.md`)
* **A. Providers**: list + radio active ★, form `＋ Thêm provider` (tên/loại/base_url/key), nút xóa (chặn xóa active). Card: keys textarea full, `base_url` (chỉ openai), link docs.
* **B. Model**: select + `🔄` + ô lọc tên + Bao gồm/Loại trừ + badge 🆓 + `…tự nhập…`. Panel: Input/Output/Context/RPM/RPD (thiếu → `—` + link docs).
* **C. Thinking**: OFF/LOW/MEDIUM/HIGH, mặc định OFF, chỉ Gemini (ghi chú + tooltip).
* **D. Tốc độ & chờ**: Chunk Size (ký tự/chunk), API delay (giây), Response timeout (giây) — có label + đơn vị.
* Lọc model có mặt ở cả Settings lẫn Workspace.

---

## 4. API CONTRACT TỐI THIỂU (CHỐT v2.3 — ĐỦ LÀM XONG PHASE 2)

`main.py` stdlib `http.server`, port 8000, serve `web/` static (MIME: html/css/js/svg/json) + endpoint JSON dưới đây. Không auth (single-user local). Mọi lỗi trả `{"error": "<thông điệp tiếng Việt>"}` + HTTP status phù hợp. Dịch là **SSE** để UI hiện từng chunk ngay, không polling. Bảng gốc 18 endpoint Phase 2 + bổ sung 2.6/3a (contract hiện hành).

| # | Method + Path | Request | Response / SSE | Ghi chú |
|---|---|---|---|---|
| 1 | `GET /api/health` | — | `{"ok": true}` | Kiểm tra server sống |
| 2 | `GET /api/projects` | — | `{"projects": [{slug, title, author, description, sources, results, done}]}` | Metadata + đếm cho cards |
| 3 | `POST /api/projects` | `{"title","author","description"}` (slug tự sinh, duy nhất) | `{"slug": "..."}` | Tạo `sources/`, `results/`, `assets/` + row db |
| 4 | `GET /api/projects/{slug}/files` | — | `{"sources": ["ch01.md"], "results": ["ch01.md"]}` | So sánh 2 thư mục |
| 5 | `POST /api/projects/{slug}/upload` | multipart `file` hoặc raw bytes + `?filename=&side=` | `{"filename": "<tên thực tế>", "chars": 32100}` | Không gate ext; va chạm → `_conflict`; raw bytes giữ nguyên bit |
| 6 | `GET /api/chunks?project=S&file=F` | — (`&full=1` kèm full text mỗi chunk cho dual-pane) | `{"chunks": [{"i": 1, "chars": 16200, "tokens_est": 4050, "preview": "..."}]}` | Dùng chung `split_text`; tokens_est = `chars/4` |
| 7 | `POST /api/translate` (SSE) | `{"project": "S", "file": "F", "provider": "gemini", "model": "gemini-2.5-flash", "prompt": "default_translation.txt", "extra_prompts": []}` | SSE: `event: chunk\ndata: {"i":1,"n":2,"text":"..."}` … cuối `event: done\ndata: {"chars": 30000}` hoặc `event: error\ndata: {"error": "..."}` | Tuần tự từng chunk, lỗi dừng ngay, không lưu dở dang |
| 8 | `POST /api/save` | `{"project": "S", "file": "F", "content": "..."}` | `{"path": "results/ch01.md"}` | Ghi đè `results/`, cập nhật app.db |
| 9 | `GET /api/prompts` | — | `{"prompts": ["default_translation.txt"]}` | Liệt kê `prompts/*.txt` |
| 10 | `GET /api/prompts/{name}` | — | `{"name": "...", "content": "..."}` | Sanitize như filename |
| 11 | `PUT /api/prompts/{name}` | `{"content": "..."}` | `{"ok": true}` | Lưu prompt |
| 12 | `GET /api/settings` / `PUT /api/settings` | GET — / PUT `{...prefs}` | prefs app + `thinking_levels` + `default_prompt` | PUT sai → giữ cũ; default file mất → fallback + warn |
| 34 | `POST /api/projects/{slug}/rename-batch` | `{"side","pattern","start","zeropad","old_names"}` | `{"results":[{old,new,ok,error}],"renamed":n}` | Bắt buộc `{N}`; lỗi từng file cô lập; không auto-sync/ghi đè |
| 35 | `GET/PUT /api/projects/{slug}/info` | `{"title","author","description"}` | meta project | GET trả rỗng nếu chưa có |
| 36 | `POST /api/find-replace` (mở rộng) | `{...}` | `{"files":{},"skipped":[],"errors":{},"total"}` | Binary skip (`errors="strict"`); lỗi ghi từng file cô lập |
| 37 | `POST /api/translate/merge` (mở rộng) | `{...}` | `done {chars,chunks,files:[{file,chars}]}` | Tách đúng về từng file + **tự lưu `results/`** |
| 38 | Hủy phiên | `POST /api/translate/cancel` | error event `cancelled:true` | **Cắt cả request đang bay** (`task.cancel`), nháp giữ trên UI |
| 13 | `GET /api/settings/providers` | — | providers **đầy đủ key** (single-user) + `active_id` |
| 14 | `GET /api/settings/models?provider_id=` | — | `{"models": [{id, name, context_length?, pricing?, is_free?}], "selected_model", "source", "docs_url"}` | Live từ API NCC, cache 5 phút |
| 15 | `POST /api/settings/save` | `{"provider_id": "...", "api_keys"/"api_key", "base_url", "selected_model", "thinking", "docs_url", "set_active": true}` | `{"ok": true}` | Lưu nguyên danh sách key (single-user) + namespace validation |
| 16 | `GET /api/settings/model-info?provider_id=&model=` | — | `{input_limit, output_limit, context_length, pricing, is_free, rate_limits{usage,limit}, quota_url, docs_url}` | Fail-soft; Gemini không quota API → link AI Studio |
| 17 | `POST /api/settings/providers` | `{"name", "type": "openai"/"gemini", "base_url", "api_key"}` | record mới `{id, docs_url}` | Thêm provider OpenAI-compatible |
| 18 | `DELETE /api/settings/providers/{id}` | — | `{"ok": true}` | Chặn xóa active / provider cuối |
| 19 | `GET /api/projects/{slug}/files` | — | `{"sources": [...], "results": [...]}` | v2.6: key `results` (đổi từ `translated/`) |
| 20 | `GET /api/projects/{slug}/file?filename=&side=` | side `sources`\|`results` | `{"content": "..."}` | Xem nội dung 1 file |
| 21 | `DELETE /api/projects/{slug}/files?filename=` | — | `{"ok": true}` | Xóa cả 2 bên cùng tên; 409 khi đang dịch file đó |
| 22 | `POST /api/projects/{slug}/rename` | `{"old","new"}` | `{"filename","renames":[...]}` | Đổi cả 2 bên cùng tên; va chạm → `_conflict` từng bên, trả mapping |
| 23 | `DELETE /api/projects/{slug}` | — | `{"ok": true}` | 409 khi có phiên dịch trong project |
| 24 | `POST /api/projects/{slug}/archive` | — | `{"path": "archive/{slug}.zip"}` | 3a: nén + xóa gốc + dọn db; 409 khi đang dịch |
| 25 | `POST /api/projects/{slug}/prompt-backup` | `{"name"}` | `{"path": "assets/prompts/x.txt"}` | 3a: 1 endpoint chung mọi dự án |
| 26 | `POST /api/translate/merge` (SSE) | `{"project","files[]",...}` | chunk `{i,n,text,file,files}` … `done {chars,chunks,files}` | 2.6: gộp file với marker `===== FILE`, chia chunk chung |
| 27 | `POST /api/translate/cancel` | — | `{"ok":true,"cancelled":bool}` | 3a: dừng giữa chunk, không ghi output dở |
| 28 | `POST /api/find-replace` | `{"project","side","pattern","repl","regex","case","word"}` | `{"files":{name:n},"total"}` + `skipped`/`errors` | 2.6: Python re (`\1`), atomic từng file; binary skip |
| 29 | `POST /api/restart` | — | `{"ok":true,"restarting":true}` | 2.6: execv argv tuyệt đối, đúng mọi launcher |
| 30 | `GET /api/health` | — | `{"ok":true,"version","started_at"}` | 2.6: phát hiện server cũ |
| 31 | `GET /api/history?limit=` | — | `{"runs":[{project,file,provider,model,status,...}]}` | 3a: JOIN runs+files |
| 32 | `POST /api/prompts/rename` | `{"old","new"}` | `{"filename"}` | 3a: chỉ `*.txt`, chặn trùng/traversal |
| 33 | `DELETE /api/prompts/{name}` | — | `{"ok": true}` | 3a: default xóa được (tự tạo lại khi restart) |

Ví dụ SSE khi bấm **Gửi AI** (chế độ đơn file):
```text
POST /api/translate {"project":"Kiem_Hiep","file":"chuong_01.md","provider":"gemini","model":"gemini-2.5-flash","prompt":"default_translation.txt"}
→ event: chunk {"i":1,"n":2,"text":"...bản dịch chunk 1..."}
→ event: chunk {"i":2,"n":2,"text":"...bản dịch chunk 2..."}
→ event: done {"chars": 30500}
→ (lỗi) event: error {"error": "❌ TẤT CẢ API KEY ĐỀU BỊ 429, bấm Gửi Lại sau ít phút."}
```

`main.py` (~khung, tái dùng `core/`):
```python
# main.py — http.server stdlib, không FastAPI
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

Sau khi hoàn thành Phase 2 (+ các pha 2.5–3a+), người dùng:
1. Chạy `python main.py` $\to$ Mở trình duyệt `http://localhost:8000` (version chân sidebar khớp CHANGELOG; lệch → restart server).
2. Tạo dự án qua dialog (Tên sách/Tác giả/Mô tả), thấy card + tiến độ.
3. Vào Workspace: chọn file, thấy thông tin ký tự/từ/tokens, chọn provider/model/prompt explicit.
4. Bấm **Gửi AI** → chọn Gộp-chia-chunk hoặc Tuần tự → thấy tiếng Việt về từng chunk + log terminal.
5. Nếu gặp lỗi 429 hay lỗi mạng $\to$ UI báo đỏ + nút Gửi lại (không fallback model); Hủy cắt cả request đang bay, nháp giữ trên editor.
6. Merge xong → từng file tự nằm trong `results/`; lưu tay → atomic write, app.db cập nhật.

---

## 6. LỘ TRÌNH TRIỂN KHAI CÁC PHASE TIẾP THEO (hợp nhất 05/09/2026 → xem `docs/16_NEXT_PHASES.md`)

Nhằm giữ cho Phase 1 và Phase 2 tập trung tuyệt đối vào việc chạy ổn định, các tính năng mở rộng được phân kỳ thực hiện lần lượt (trạng thái cập nhật trong `docs/ROADMAP.md`):

* **PHASE 3: TIỆN ÍCH FILE & GLOSSARY** — phần lớn đã xong ở 2.6/3a/3a+ (upload, rename, find/replace, merge, history, archive); còn lại: glossary UI, prompt profile, diff heuristic, preview, batch nâng cao → `docs/16_*`.
* **PHASE 4: CÔNG CỤ EPUB & NÂNG CAO (KẾ THỪA SILABOOK)** — như cũ (EPUB 2 chiều, handoff tóm tắt).

* **PHASE 5: ĐÓNG GÓI & PHÁT HÀNH**:
  1. Công cụ EPUB: Chuyển đổi định dạng 2 chiều giữa MD $\leftrightarrow$ TXT $\leftrightarrow$ HTML và đóng gói sách `.epub` chuẩn.
  2. Tự động sinh tóm tắt bối cảnh nối tiếp giữa các chương (`previous_chunk_handoff`).

* **PHASE 5: ĐÓNG GÓI & PHÁT HÀNH**:
  1. Kiểm thử tải dịch khối lượng lớn với 100 chương truyện.
  2. Đóng gói script khởi động 1-click cho người dùng cá nhân (Local / Private VPS).
