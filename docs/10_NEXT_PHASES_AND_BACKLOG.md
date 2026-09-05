# 10. VIỆC CHỜ LÀM — PHASE TIẾP THEO, KẾ HOẠCH THẢO LUẬN, CẦN REVIEW

> **Trạng thái Phase 2.5: XONG.** Chi tiết xem `docs/09_PHASE_2_5_COMPLETED.md`.
> Bước đóng: commit v2.6.0 (lệnh đã in ở release review trước, chưa chạy lúc viết file này).
> Sau commit, mọi mục dưới đây là backlog chuẩn duy nhất (thay thế `docs/08_*` ở những phần đã xong).

---

## 1. PHASE 3a — HOÀN THIỆN UI (làm trước — CHI TIẾT THỰC THI: `docs/11_*`)

- [ ] **Tách frontend (Task 0):** CSS → `web/css/app.css`, JS theo trang (`app/projects/workspace/findreplace/prompts/settings/init`), MIME map + test, `readSSE`/`toast` dùng chung, giữ `<script>` thường + globals (không ES modules ở 3a).
- [ ] **Quản lý prompt đủ dùng:** rename/delete prompt + backup 1 endpoint chung vào `assets/prompts/` của dự án (không hàm riêng từng dự án).
- [ ] **CSS foundation theo `del_PLAN_REDESIGN` §5:** Design Tokens (`:root`), `.card/.btn/.table-minimal/.label-tracked/.toast` vào `web/css/` mới (làm chung với mục 4).
- [ ] **Lưu trữ dự án (đã hứa "làm sau"):** nén `workspace/projects/{slug}` → `workspace/archive/{slug}.zip`, xóa thư mục gốc + rows db; nút trên card (confirm); endpoint `POST /api/projects/{slug}/archive`. Không tự bung (khôi phục = giải nén tay).
- [ ] **Hủy phiên dịch giữa chừng:** `POST /api/translate/cancel` + cờ kiểm tra giữa các chunk trong `_run_chunks`; UI nút ⏹ + trạng thái cuối rõ ràng; không ghi output dở (atomic đã có).
- [ ] **Tiến độ workspace trực quan:** thanh "chunk i/n · attempt · key j/m · file" từ event `progress` (hiện chỉ có text + bulk msg).
- [ ] **Lịch sử chạy:** `GET /api/history?limit=20` từ bảng `runs` + view gọn (file/provider/model/thời gian/trạng thái) + ước tính token/chi phí từ `model_info.pricing` (hiển thị, không cam kết chính xác).
- **Acceptance:** DoD `del_PLAN_REDESIGN` §6.2 (trừ Settings đã xong) + hủy/atomic/history có test.

## 2. PHASE 3b — CÔNG CỤ NỘI DUNG NHẸ

- [ ] **Glossary theo project có UI:** `GET/PUT /api/projects/{slug}/glossary` (text `gốc=nghĩa`, cap ~200 dòng + cảnh báo phình prompt); tab sửa trong Workspace + preview "chunk này trúng N thuật ngữ". Backend lọc đã có (`_glossary_for_chunk`).
- [ ] **Prompt profile:** `prompts/profiles/*.json` `{name, prompt, extra_prompts[]}` + dropdown Workspace nạp sẵn; ship 3 mẫu (Tiểu thuyết / Kỹ thuật / Giữ Markdown). Không engine động.
- [ ] **Diff + cảnh báo output bất thường (heuristic, không model chấm điểm):** rỗng / ngắn hơn nguồn 50% / trùng nguồn 80% / mất cấu trúc Markdown / nghi cắt dở → `done.warnings[]` + banner vàng theo chunk. Vendor `diff-match-patch` (1 file ~30KB) khi cần view 2 cột/inline — theo manifesto §9, không cần thảo luận lại.
- [ ] **Preview Markdown/HTML:** vendor `marked` + `DOMPurify`, pane toggle thứ 3 hoặc thay thế tạm; sanitize hiển thị (backend đã sanitize là chính).
- [ ] **Batch search/replace nâng cao:** hiện đã có thay-hết phạm vi; còn thiếu: preview danh sách chỗ match trước khi thay, undo 1 bước (backup `.bak` trước khi ghi).
- **Acceptance:** glossary/profile/diff/preview dùng được end-to-end; không state mới ngoài `profiles/*.json`.

## 3. PHASE 3c — BATCH NHẸ (đóng Phase 3) + PHASE 4/5

- [ ] Batch tuần tự N file đã có; thêm tùy chọn "bỏ qua file lỗi" (mặc định TẮT) + progress tổng "file 2/5 · chunk 1/3" + integration test batch 3 file (1 file lỗi giữa chừng → dừng đúng).
- [ ] **Phase 4 — EPUB & ngữ cảnh** (ROADMAP §4–§5): đóng gói EPUB từ `results/` (TOC chuẩn); `previous_chunk_handoff` (`{{previous_summary}}`); trích xuất thực thể → gợi ý glossary.
- [ ] **Phase 5 — Đóng gói & chịu tải:** test 100 chương; script khởi động 1-click; dọn docs, chốt release.
- [ ] Đóng Phase 3 khi: acceptance 3a+3b+3c checked, `pytest` PASS, CHANGELOG release 3.x.

## 4. KẾ HOẠCH CHIA NHỎ `index.html` (CHỜ THẢO LUẬN — làm đầu Phase 3)

**Vấn đề:** 1 file 482 dòng và tăng nhanh (256 → 482 trong 1 phase); CSS + JS 4 trang + find/replace + bulk trộn chung; lib sắp tới (`marked`, `DOMPurify`, `diff-match-patch`) không thể nhét inline sạch sẽ; sửa 1 trang dễ chạm nhầm trang khác.
**→ ĐÃ DUYỆT vào 3a Task 0 (`docs/11_*`):** tách tĩnh không build theo đúng cấu trúc dưới (plain `<script>`, giữ globals).

**Ràng buộc (manifesto §9):** không build, không npm ở máy user, offline, `python main.py` là chạy.

**Đề xuất — tách tĩnh, không build:**
```text
web/
  index.html        (markup 4 trang + <link>/<script>, không còn <style>/<script> lớn)
  css/app.css       (tokens + components, từ del_PLAN_REDESIGN §5)
  js/app.js         (helpers $, J, esc + sidebar + nhớ tab + version)
  js/projects.js    (cards)
  js/workspace.js   (3 cột, translate, bulk, merge, dropzone, tabs)
  js/findreplace.js (thanh Sigil + scope)
  js/prompts.js     (trang prompt)
  js/settings.js    (trang cấu hình)
  js/init.js        (thứ tự boot: listProjects/listFiles/loadMeta)
  vendor/           (marked, DOMPurify, diff-match-patch khi duyệt — file đơn, commit kèm)
```
- `<script src>` thường theo thứ tự phụ thuộc (giữ globals như hiện tại → refactor ít rủi ro nhất; không ES modules để khỏi vướng CORS/MIME).
- Backend: `_serve_static` bổ sung map MIME (`.css→text/css`, `.js→text/javascript`, +`.svg/.woff2` dự phòng) + test MIME; query `?v=` vẫn qua được (đã dùng `u.path`).
- Lazy-load: `vendor/*` chỉ `<script>` ở trang cần (Workspace), không nạp toàn cục.
- Bước làm: (1) rút CSS → app.css; (2) rút JS theo trang đúng thứ tự; (3) MIME map + tests; (4) checklist click-toàn-bộ-4-trang + `node --check` từng file; (5) ghi quy ước `vendor/` vào manifesto nếu cần.
- **Phương án loại:** bundler/esbuild (phạm §9), SSR/template (stdlib không có, không cần), giữ nguyên 1 file (chấp nhận được tới ~800 dòng, sau đó bắt buộc tách).
- **Điểm cần bạn chốt:** (a) tách ngay đầu Phase 3 (đề xuất) hay trì hoãn tới khi chạm 800 dòng; (b) có cho `vendor/` vào Git hay `.gitignore` + script tải (đề xuất: commit kèm để offline tuyệt đối).

## 5. BÁO CÁO & TÀI LIỆU CẦN REVIEW

- `docs/08_PHASE_3_AND_BEYOND.md`: đã lỗi thời một phần (workspace/file-mgmt/find-replace/merge xong sớm) — file này (mục 1–3) thay thế nó; **cần bạn xác nhận rồi `del_08`**.
- `docs/del_07_*` + `docs/wip/del_*`: lịch sử, giữ nguyên, không review nội dung.
- `docs/wip/bao_cao_pha_2.md` (nay là `del_*`): các mục P1/P2 còn lại (backoff/jitter, Retry-After, request ID, health check provider, truncate warning, dark mode, preset model, ước tính chi phí, export metadata) — **mặc định TRÌ HOÃN** theo §7 báo cáo; muốn kéo mục nào vào 3a/3b thì ghi vào đây.

## 6. CÂU HỎI MỞ (cần bạn quyết trước khi làm)

1. Split `index.html`: tách ngay đầu Phase 3 hay đợi ~800 dòng? `vendor/` commit kèm hay tải riêng?
2. Lưu trữ dự án: chỉ nén+xóa (đề xuất) hay cần cả nút khôi phục trong UI?
3. Tên file gộp mặc định `*_gop` hiện tại có ổn hay muốn quy tắc khác (vd. theo ngày)?
4. Preview Markdown/HTML: pane thứ 3 cố định hay chế độ toggle thay editor phải?
