# 08. PHASE 3 HOÀN THIỆN UI + CÔNG CỤ NỘI DUNG & CÁC PHA TIẾP THEO

> **For agentic workers:** REQUIRED: làm theo thứ tự 3a → 3b → 3c. Mỗi Task xong chạy test + commit. Đọc `docs/00_PROJECT_MANIFESTO.md` (v2.4) trước khi sửa bất cứ gì.

**Goal:** Đưa UI từ "hơn CLI một chút" lên mức dùng hàng ngày thoải mái (đẹp tối giản + quan sát được phiên dịch + hủy được), rồi thêm công cụ nội dung nhẹ (glossary, prompt profile, diff, batch) — vẫn zero-npm, vẫn stdlib backend.

**Architecture:** 3a = áp `PLAN_REDESIGN` + tiến độ/hủy phiên; 3b = công cụ nội dung trên nền đã ổn định; 3c = batch nhẹ. Cửa CodeMirror 6 (theo `docs/wip/Y_KIEN_UI_STACK_VA_EDITOR.md`) chỉ mở ở 3b khi diff/search-replace cần editor thật.

**Tech Stack:** giữ nguyên (stdlib `http.server`, vanilla single-file UI, `httpx`). Không React/Tailwind — xem lại chỉ khi xuất hiện multi-user/auth/queue nền (manifesto v2.4).

**Điều kiện vào Phase 3:** exit criteria `docs/07_*` (2.5a + 2.5b) đã checked hết.

> **Cập nhật 05/09/2026 (v2.6.0):** quản lý file đã chuyển từ Projects sang Workspace
> 3 cột (click-load cùng tên, lưu `results/`), tìm/thay regex kiểu Sigil đã làm,
> `translated/` đã đổi thành `results/`. Phase 3a dưới đây bỏ phần trùng, giữ:
> CSS foundation + progress/hủy phiên + glossary/profile/diff/batch.

---

## Chunk 1 — Phase 3a: Hoàn thiện UI (theo PLAN_REDESIGN, Settings đã xong thì bỏ qua)

Trang Settings đã redesign ở v2.5.0 → 3a chỉ còn 3 trang + khung chung.

### Task 1: CSS foundation + khung chung

**Files:** Modify `web/index.html` (`<style>` + sidebar).

- [ ] **Step 1:** Nhét Design Tokens (`:root` variables) + class `.card/.btn/.btn-pri/.btn-danger/.table-minimal/.label-tracked/.input/.toast` y đặc tả `PLAN_REDESIGN` §5 vào `<style>`. Không npm, không CDN CSS.
- [ ] **Step 2:** Sidebar: giữ 4 mục + thu gọn, thêm toast container chung (`.toast` tự mờ 3s) thay `wMsg` text thô.
- [ ] **Step 3:** Kiểm tra `web/index.html` vẫn 1 file, tải < 20ms local. Commit.

### Task 2: Trang Projects + Prompts lên Card chuẩn

- [ ] **Step 1:** Projects: bọc drop zone + bảng file (đã có từ 2.5b) vào `.card`, header trang + phụ đề, badge `Chưa dịch`/`Đã dịch` theo `PLAN_REDESIGN` §3.
- [ ] **Step 2:** Prompts: bọc list + editor vào `.card`, thêm nút `+ Tạo`/`Xóa prompt` (endpoint PUT đã có; xóa = thêm `DELETE /api/prompts/{name}`, chặn xóa prompt mặc định đang dùng).
- [ ] **Step 3:** Checklist thủ công 4 trang caballo. Commit.

### Task 3: Workspace quan sát được + hủy phiên

Backend 2.5a đã `emit("progress", {i, n, attempt})` → 3a chỉ việc hiện + thêm cancel:

- [ ] **Step 1 (backend):** `POST /api/translate/cancel` đặt `threading.Event`; `run_all()` kiểm tra event giữa các chunk → dừng, `emit("error", {"error": "Đã hủy bởi người dùng", "cancelled": true})`, NHẢ `_translate_lock`, không ghi output dở (atomic write 2.5a đã đảm bảo). Test trong `tests/test_server.py`.
- [ ] **Step 2 (UI):** Thanh tiến độ "chunk i/n · attempt k · đã chờ Ns · key j/m" + nút `⏹ Hủy` (confirm) + trạng thái cuối rõ ràng (xong/hủy/lỗi). Không ghi output khi hủy.
- [ ] **Step 3:** Test reload trang giữa phiên: server tiếp tục chạy (SSE cũ đứt, không crash), phiên mới bị 409 đúng. Commit.

**Acceptance 3a:** 4 trang đồng bộ thẩm mỹ Card tối giản; mọi phiên dịch đều quan sát + hủy được; DoD `PLAN_REDESIGN` §6.2 checked (trừ mục Settings đã xong).

---

## Chunk 2 — Phase 3b: Công cụ nội dung nhẹ

### Task 4: Glossary theo project (có UI)

Backend lọc glossary đã có (`main.py:_glossary_for_chunk` + `assets/glossary.txt`). Thiếu UI sửa.

- [ ] **Step 1:** Endpoint `GET/PUT /api/projects/{slug}/glossary` (text thuần, 1 dòng `gốc=nghĩa`, tối đa ~200 dòng → cắt + cảnh báo khi vượt để khỏi phình prompt).
- [ ] **Step 2:** Tab nhỏ trong Projects: textarea sửa + lưu + đếm dòng + preview "chunk này trúng N thuật ngữ" (gọi `/api/chunks?full=1` client-side match). Test + commit.

### Task 5: Prompt profile (preset, không engine động)

Profile = 1 file JSON nhỏ trong `prompts/profiles/`: `{name, prompt, extra_prompts[]}`. Không hệ thống prompt động.

- [ ] **Step 1:** Endpoint `GET/PUT /api/profiles` + UI Workspace: dropdown profile (VD: Tiểu thuyết / Kỹ thuật / Giữ Markdown / Hiệu đính) → nạp sẵn prompt + extras vào control hiện có. Ship kèm 3 profile mẫu. Test + commit.

### Task 6: Diff + cảnh báo output bất thường (heuristic, không model chấm điểm)

- [ ] **Step 1:** Sau `emit("done")`, server tính heuristic mỗi chunk: rỗng / ngắn hơn nguồn quá 50% / trùng nguồn > 80% / mất cấu trúc Markdown (đếm `#`,`-`,`>`) / nghi cắt dở (kết thúc không dấu câu) → kèm trong payload `done.warnings[]`.
- [ ] **Step 2:** UI hiện warnings dạng banner vàng theo chunk, chỉ cảnh báo không tự sửa. Unit test cho từng heuristic. Commit.
- [ ] **Step 3 (cửa CodeMirror):** CHỈ khi diff cần xem cạnh nhau + search-replace hàng loạt (ROADMAP §3) thì nhét CodeMirror 6 lazy-load vào Workspace theo `Y_KIEN_UI_STACK_VA_EDITOR.md`; nếu textarea hiện tại đủ → bỏ qua, khỏi thêm lib.

### Task 7: Lịch sử + ước tính (P2 rẻ, làm luôn cho UI đỡ "sơ sài")

- [ ] Dùng bảng `runs` sẵn có: endpoint `GET /api/history?limit=20` + view lịch sử gọn (file/provider/model/thời gian/trạng thái) + ước tính token/chi phí từ `model_info.pricing` (hiển thị, không cam kết chính xác). Commit.

**Acceptance 3b:** Glossary/profile/diff/history dùng được end-to-end; không model chấm điểm, không state mới ngoài `profiles/*.json`.

---

## Chunk 3 — Phase 3c: Batch nhẹ (đóng Phase 3)

- [ ] **Step 1:** Mở rộng bulk 2.5b: hàng đợi tuần tự N file (file1 xong → file2), lỗi dừng cả loạt + báo file nào hỏng; tùy chọn "bỏ qua file lỗi" (checkbox, mặc định TẮT). Không song song (tránh 429 — manifesto failure policy).
- [ ] **Step 2:** Progress tổng "file 2/5 · chunk 1/3". Integration test batch 3 file (giữa chừng 1 file lỗi → dừng đúng). Commit.

**Đóng Phase 3 khi:** acceptance 3a+3b+3c checked, `pytest -q` PASS, CHANGELOG release 3.x.

---

## Các pha tiếp theo (đề xuất, chưa chi tiết hóa)

- **Phase 4 — EPUB & ngữ cảnh:** đóng gói EPUB từ `results/` (đầu vào txt/md/html, TOC chuẩn); `previous_chunk_handoff` (tóm tắt 3 câu truyền sang chunk/chương kế qua `{{previous_summary}}`); trích xuất thực thể → gợi ý glossary. Nền: ROADMAP §4–§5.
- **Phase 5 — Đóng gói & chịu tải:** test tải 100 chương; script khởi động 1-click (local); dọn docs, chốt release.
- **Mãi mãi KHÔNG làm** (trừ khi manifesto đổi): multi-user/auth, queue phân tán, checkpoint/resume, DB workflow lớn, cloud sync, plugin marketplace, OCR nhúng lõi, đánh giá chất lượng bằng model thứ hai. Nền: `bao_cao_pha_2.md` §7 + manifesto litmus test.
