# LỘ TRÌNH PHÁT TRIỂN TƯƠNG LAI (FUTURE ROADMAP)
> **Tài liệu**: Lưu trữ các tính năng nâng cao được dời lại từ Phase 1 & Phase 2 nhằm giữ cho lõi gửi–nhận của dự án luôn tinh gọn, nhẹ và không phát sinh lỗi.  
> **Địa chỉ**: `docs/ROADMAP.md`
> **Phiên bản**: v3.1.0 (06/09/2026) — 3a+ released (fileops, batch rename, filter, default prompt, Gửi AI, abort thật); backlog chuẩn ở `docs/16_NEXT_PHASES.md`.

---

## 11. HOÀN THÀNH 3a+ — WORKSPACE REWORK (chi tiết: `docs/15_*`, CHANGELOG `[3a+]`)

- [x] `core/fileops.py`: `guard_name`/`unique_name` (`_conflict`)/`read_text_strict`/`write_bytes_no_overwrite` + ranh giới 5 vùng `main.py`
- [x] Upload theo tab (không gate ext, raw bytes) + rename đơn/batch (preview, `{N}` bắt buộc, lỗi cô lập, không auto-sync/ghi đè)
- [x] Find/replace `skipped`/`errors`, binary strict, sorted, all-or-nothing từng file
- [x] Toolbar SVG + tabs + filter + selection Set + `<dialog>` + status dot + khóa toolbar khi dịch
- [x] Prompt mặc định (prefs, ✓ đầu list, bất khả xóa/đổi) + backup vào dự án
- [x] Nút Gửi AI + dialog 2 chế độ; merge tách đúng về từng file + tự lưu; terminal log; abort thật giữa request
- [x] Project metadata + cards mới (progress bar, info dialog, archive icon)
- [x] Tests + docs (92 tests PASS lúc đóng)

---

---

## 10. HOÀN THÀNH 3a — HOÀN THIỆN UI (chi tiết: `docs/11_*`)

- [x] Tách frontend: `web/css/app.css` + `web/js/` theo trang, MIME map + test, `readSSE`/`toast` dùng chung
- [x] Cards/tokens đồng bộ 4 trang (grid, chips, table-minimal, tracked-labels)
- [x] Prompt: đổi tên, xóa, backup 1 endpoint chung vào `assets/prompts/`
- [x] Archive dự án (zip + xóa + dọn db)
- [x] Hủy phiên giữa chunk + thanh tiến độ (chunk/attempt/key/file/giây)
- [x] Lịch sử chạy (`runs.file_id` + `GET /api/history` + bảng Projects)
- [x] Find/replace phạm vi tất cả file + tabs Nguồn/Kết quả + layout fluid
- [x] Nút restart + version/health + nhớ tab (manifesto v2.5 §9)
- [x] Tests + docs + CHANGELOG 3.0.0

---

## 9. HOÀN THÀNH v2.6 — Stabilization & File Management

- [x] Atomic write toàn repo (`core/file_handler.atomic_write_text`) cho output/config/prompt
- [x] Error taxonomy chuẩn (`core/errors.py`, `docs/02` §5.1): 429 đổi key / network+5xx retry cùng key ≤2 attempt/chunk / 401/404+rỗng+malformed dừng ngay
- [x] SSE `progress` event (chunk/attempt/key) — UI quan sát tiến độ
- [x] Contract prefs duy nhất (`normalize_prefs`) cho `get_config()` + `PUT /api/settings`
- [x] 4 endpoint file mới: `GET .../file`, `DELETE .../files`, `POST .../rename`, `DELETE /api/projects/{slug}` (409 khi đang dịch)
- [x] Thư mục kết quả `translated/` → `results/` + tự migrate file cũ
- [x] Trang Dự Án chỉ còn cards (số file nguồn/kết quả, tiến độ, mở workspace, xóa)
- [x] Workspace 3 cột: file sources/results + dual editor, click-load cùng tên, lưu `results/`
- [x] Tìm/thay thế kiểu Sigil (regex, hoa/thường, cả từ, `$1`)
- [x] Tests mới (`core/errors.py`, `tests/test_translate_flow.py`, `tests/test_config.py`, `tests/test_file_handler.py` case crash atomic + migration)
- [x] Manifesto v2.4 (READ-FIRST + local-first security + contract runtime SSOT)
- [x] CHANGELOG v2.6.0

---

## 8. HOÀN THÀNH v2.5 — Trang Cấu Hình Redesign

- [x] 5 khối UI (Providers / Model / Thinking / Tuning / Lưu riêng)
- [x] CRUD provider OpenAI-compatible (`POST /api/settings/providers`, `DELETE /api/settings/providers/{id}`)
- [x] Model metadata + `GET /api/settings/model-info` (input/output/context/quota/docs)
- [x] Thinking 4 mức (OFF/LOW/MEDIUM/HIGH) cho Gemini, OpenAI-compatible bỏ qua
- [x] Prefs: `max_chunk_chars`, `api_delay_seconds` (mặc định 2s), `timeout_seconds` có label + đơn vị
- [x] Lọc model Bao gồm/Loại trừ ở cả Settings lẫn Workspace
- [x] Tests + docs + CHANGELOG

---

## 1. PHÂN TÍCH SO SÁNH VỀ TÍNH NĂNG CHECKPOINT (LƯU TẠM TIẾN TRÌNH)

### 1.1. So Sánh Hai Cách Tiếp Cận

| Tiêu chí | **Phương Án Hiện Tại: Không Checkpoint (Minimalist Gửi–Nhận)** | **Phương Án Tương Lai: Có Checkpoint (Lưu Tạm Từng Chunk)** |
| :--- | :--- | :--- |
| **Bản chất** | Một phiên gửi–nhận trực tiếp. AI trả lời chunk nào thì giữ trong RAM, dịch xong toàn bộ chunk của file thì ghép lại và lưu thành file `.md`/`.txt`. | Ghi tạm từng chunk đã dịch vào database SQLite hoặc file JSON tạm. Nếu rớt mạng ở chunk 5, lần sau đọc lại chunk 1–4 và chỉ dịch tiếp từ chunk 5. |
| **Độ phức tạp code** | **Rất thấp (0 dòng code lưu trạng thái)**. Không lo lỗi khóa DB (Database Lock), không lo xung đột ghi file. | **Cao**. Phải thêm logic kiểm tra chunk nào đã dịch, xử lý file dở dang, xóa checkpoint khi xong, phục hồi khi crash. |
| **Giao diện WebUI** | Cực nhẹ, phản hồi tức thì, không có bảng điều khiển Resume / Recovery rườm rà. | Cần thêm UI hiển thị tiến trình phục hồi, nút "Dịch tiếp" hoặc "Dịch lại từ đầu". |
| **Khi gặp lỗi** | Dừng lại, báo lỗi rõ ràng. Người dùng xem lại mạng/key rồi bấm nút **[Gửi lại]** hoặc **[Xóa & gửi lại]**. | Tự động hoặc bán tự động nhảy cóc các chunk đã dịch. |
| **Mức độ phù hợp** | **Phù hợp tuyệt đối với mục tiêu gửi–nhận gọn nhẹ của dự án hiện tại**. | Chỉ cần thiết khi người dùng có nhu cầu dịch những file đơn lẻ khổng lồ (>100.000 từ / file). |

### 1.2. Kết luận
Trong Phase 1 và Phase 2, **loại bỏ hoàn toàn Checkpoint** giúp code giảm hơn 40% độ phức tạp, loại bỏ hoàn toàn các lỗi tiềm ẩn về lưu trạng thái. Tính năng này được bảo lưu tại tài liệu này và chỉ xem xét triển khai nếu người dùng thực sự có nhu cầu dịch các tệp khổng lồ trong tương lai.

---

## 2. KẾ HOẠCH SỬ DỤNG SQLITE CHO TƯƠNG LAI

File `workspace/app.db` **đã được tạo từ Phase 1** (v2.3) với 3 bảng `projects/files/runs` để index + log. Trong tương lai (Phase 3 trở đi), SQLite sẽ được tận dụng thêm cho:

1. **Đánh chỉ mục tìm kiếm toàn văn (SQLite FTS5 Full-Text Search)**:
   * Cho phép người dùng gõ từ khóa để tìm kiếm ngay lập tức xem nhân vật hoặc thuật ngữ xuất hiện ở những chương nào trong hàng trăm chương truyện.
2. **Quản lý danh mục dự án lớn**:
   * Khi người dùng tích lũy hàng chục đầu sách với hàng ngàn chương, SQLite giúp tải danh sách dự án tức thì mà không phải duyệt quét ổ đĩa mỗi lần mở app.
3. **Lưu trữ Checkpoint (Nếu kích hoạt lại)**:
   * Sẵn sàng bảng `checkpoints` để lưu tạm các chunk nếu tính năng Checkpoint được kích hoạt.

---

## 3. CÁC TÍNH NĂNG XỬ LÝ TẬP TIN NÂNG CAO (PHASE 3+ — xem docs/08_PHASE_3_AND_BEYOND.md)

> **Cập nhật:** Batch Search & Replace phạm vi file đã XONG ở 2.6/3a+ (`POST /api/find-replace` + `skipped`/`errors` + dialog). Còn lại Diff Viewer → Phase 3b (`docs/16_*`).

1. **Bộ công cụ Tìm kiếm & Thay thế Hàng loạt (Batch Search & Replace)** — ✅ DONE:
   * Cho phép người dùng tìm một từ bị dịch sai (ví dụ: tên riêng dịch gượng gạo) và thay thế đồng loạt trên toàn bộ các file bản dịch trong thư mục `results/`.
   * Hỗ trợ tìm kiếm theo chuỗi văn bản thường hoặc biểu thức chính quy (Regex).
2. **Công cụ So Sánh Chênh Lệch Nâng Cao (Diff Viewer)**:
   * So sánh chi tiết từng câu giữa bản gốc và bản dịch, hoặc giữa 2 lần dịch khác nhau (khi đổi prompt).
   * Đề xuất: vendor `diff-match-patch` (1 file ~30KB) + render DIY 2 cột/inline; CodeMirror 6 (`@codemirror/merge`) nếu cần workflow nhận/bỏ chunk; cửa CM6 chỉ khi IME tiếng Việt tái phát.
- [ ] Batch Search & Replace (Phase 3b)
- [ ] Diff Viewer (Phase 3b)

---

## 4. CÔNG CỤ EPUB & CHUYỂN ĐỔI ĐỊNH DẠNG 2 CHIỀU (PHASE 4)

1. **Đóng gói sách EPUB tối giản**:
   * Chỉ nhận đầu vào là các file text (`.txt`, `.md`, `.html`), tự động ghép thành sách `.epub` tiêu chuẩn có mục lục TOC.
2. **Chuyển đổi định dạng văn bản 2 chiều**:
   * `Markdown (.md)` $\longleftrightarrow$ `Text thuần (.txt)`.
   * `HTML (.html)` $\longleftrightarrow$ `Markdown (.md)`.
   * Áp dụng cho cả thư mục `sources/` và thư mục `results/`.

---

## 5. CƠ CHẾ NGỮ CẢNH TỰ ĐỘNG & TRÍCH XUẤT THUẬT NGỮ (PHASE 4)

1. **Tự động tóm tắt chương trước (`previous_chunk_handoff` - Kế thừa từ silaBook)**:
   * Sau khi dịch xong một chương, AI tự sinh tóm tắt 3 câu và tự động truyền vào biến `{{previous_summary}}` của chương kế tiếp để giữ giọng điệu liền mạch.
2. **Công cụ Trích xuất Thực thể & Nhân vật tự động**:
   * Quét các chương truyện nguồn và tự động trích xuất danh sách nhân vật, môn phái, địa danh vào file `workspace/projects/{slug}/assets/glossary.txt` (đường dẫn chuẩn duy nhất, chốt v2.3).

---

## 6. OCR — TẠM HOÃN SANG TƯƠNG LAI XA (KHÔNG LÀM PHASE 1–4)

* Giữ chỗ: nếu sau này thực sự cần, triển khai dưới dạng microservice/tool độc lập `tools/ocr_tool.py` gọi qua API, KHÔNG nhúng Tesseract/Poppler vào lõi hay WebUI.
* Tạm thời dùng công cụ ngoài (Preview, Google Lens/Docs, NAPS2, Calibre) rồi nạp txt/md/html vào `sources/`.

---

## 7. QUYẾT ĐỊNH ĐÃ CHỐT v2.5 (KHỎI TRANH LUẬT LẠI)

* OCR: tạm hoãn vào §6 trên, dùng tool ngoài.
* OpenAI-compatible: đã đưa vào Phase 1, chọn explicit `--provider/--model`, không fallback.
* Plugin: quy ước file (prompts/tools/providers), không framework động.
* Single-user: FULL key hiển thị, sửa/xóa trực tiếp trong UI; model select nhìn thấy được + custom; thinking chỉ Gemini; lọc model client-side ở cả Settings và Workspace.
* `main.py` là điểm vào chính; `run.py` CLI giữ nguyên là entry point được hỗ trợ (quyết định cuối §10.2 `docs/17_*` — đã bác đề xuất loại bỏ).
* `config/providers.json` là SSOT provider; `config/config.json` chỉ chứa prefs app (`max_chunk_chars`, `api_delay_seconds`, `timeout_seconds`, `default_prompt`).
* `api_delay_seconds` mặc định 2.0s giữa các chunk chống 429; `timeout_seconds` mặc định 90s.

---

## 8. ĐỀ XUẤT KỸ THUẬT TẠM GÁC (tham khảo sau, không làm ở 3b)

* **`TranslationError` có cấu trúc** (`category: retry_same_key | rotate_key | stop` + provider/model/status/chunk/message): taxonomy đã tập trung ở `classify()`, SSE đã mang attempt/key — chưa có nhu cầu tiêu thụ nên không tạo class. Quay lại khi UI cần dữ liệu lỗi có cấu trúc. (Nguồn: review ngoài 05/09, phản biện tại `docs/17_*` §2.3.)