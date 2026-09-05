# 10. VIỆC CHỜ LÀM — PHASE TIẾP THEO, KẾ HOẠCH THẢO LUẬN, CẦN REVIEW

> **Trạng thái Phase 2.5: XONG.** Chi tiết xem `docs/09_PHASE_2_5_COMPLETED.md`.
> **Trạng thái Phase 3a + 3a+: XONG** (92 tests PASS, chờ user test). Hồ sơ đối chiếu: `docs/11_*`, `docs/15_*`.
> **Backlog không-làm-tiêp theo: `docs/16_NEXT_PHASES.md`** (3b/3c/4/5 + câu hỏi mở). Mục 2–4 dưới đây giữ lại để khỏi mất dấu, nội dung chuẩn theo file 16.

---

## 1. PHASE 3a — HOÀN THIỆN UI (**XONG 05/09/2026**, chi tiết thực thi: `docs/11_*`, hồ sơ: CHANGELOG 3.0.0)

- [x] **Tách frontend (Task 0):** CSS → `web/css/app.css`, JS theo trang (`app/projects/workspace/findreplace/prompts/settings/init`), MIME map + test, `readSSE`/`toast` dùng chung, giữ `<script>` thường + globals (không ES modules ở 3a).
- [x] **Quản lý prompt đủ dùng:** rename/delete prompt + backup 1 endpoint chung vào `assets/prompts/` của dự án (không hàm riêng từng dự án).
- [x] **CSS foundation theo `del_PLAN_REDESIGN` §5:** Design Tokens (`:root`), `.card/.btn/.table-minimal/.label-tracked/.toast` vào `web/css/` mới (làm chung với mục 4).
- [x] **Lưu trữ dự án:** nén `workspace/projects/{slug}` → `workspace/archive/{slug}.zip`, xóa thư mục gốc + rows db; nút 📦 trên card (confirm); endpoint `POST /api/projects/{slug}/archive`. Không tự bung (khôi phục = giải nén tay).
- [x] **Hủy phiên dịch giữa chừng:** `POST /api/translate/cancel` + cờ kiểm tra giữa các chunk trong `_run_chunks`; UI nút ⏹ + trạng thái cuối rõ ràng; không ghi output dở (atomic đã có).
- [x] **Tiến độ workspace trực quan:** thanh "chunk i/n · attempt · key j/m · file · đã chờ Ns" từ event `progress` + timer.
- [x] **Lịch sử chạy:** `GET /api/history?limit=20` (JOIN runs+files, `runs.file_id`) + bảng cuối Projects (chưa có ước tính chi phí — dồn 3b nếu cần).
- **Acceptance:** DoD `del_PLAN_REDESIGN` §6.2 (trừ Settings đã xong) + hủy/atomic/history có test — ĐẠT (77 tests).

## 2. PHASE 3b — CÔNG CỤ NỘI DUNG NHẸ (→ chi tiết chuẩn: `docs/16_NEXT_PHASES.md`)

- Glossary theo project có UI; Prompt profile preset; Diff + cảnh báo heuristic;
  Preview Markdown/HTML (vendor); Batch search/replace nâng cao (preview match, undo `.bak`); ước tính token/chi phí.

## 3. PHASE 3c — BATCH NHẸ (đóng Phase 3) + PHASE 4/5 (→ chi tiết chuẩn: `docs/16_NEXT_PHASES.md`)

- Batch: tùy chọn "bỏ qua file lỗi", progress tổng, integration test. Phase 4: EPUB + handoff. Phase 5: tải + 1-click + chốt release.

## 4. KẾ HOẠCH CHIA NHỎ `index.html` (**XONG ở 3a** — giữ lại làm hồ sơ quyết định)

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

- `docs/08_PHASE_3_AND_BEYOND.md`: đã gắn cờ SUPERSEDED (xem đầu file) — không dùng làm plan nữa; nội dung chưa làm đã chuyển sang `docs/16_*`.
- `docs/del_07_*` + `docs/wip/del_*`: lịch sử, giữ nguyên, không review nội dung.
- P1/P2 còn lại (backoff/jitter, Retry-After, request ID, health check provider, truncate warning, dark mode, preset model, export metadata) — **mặc định TRÌ HOÃN**; muốn kéo mục nào vào 3b thì ghi vào `docs/16_*`.

## 6. CÂU HỎI MỞ (đã rút gọn — chi tiết + mới xem `docs/16_*`)

1. Preview Markdown/HTML: pane thứ 3 cố định hay toggle? *(còn mở)*
2. Archive: cần thêm nút khôi phục trong UI? *(còn mở)*
3. `web/vendor/`: commit kèm hay tải riêng? *(còn mở)*
4. ~~Split `index.html`~~ — xong ở 3a. ~~Tên file gộp `*_gop`~~ — đã bỏ, merge tự lưu từng file.
