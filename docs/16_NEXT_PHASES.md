# 16. CÁC PHA TIẾP THEO (REVIEW & QUYẾT ĐỊNH)

> **Trạng thái:** Phase 3a + 3a+ + 3b-stabilization xong (136 tests PASS).
> **Phase 4 đã thực thi xong (155 tests PASS + node 5/5 + smoke live, chờ user test tay browser + duyệt diff).**
> **Đánh lại số (theo yêu cầu user):** 3b-F + 3c cũ gộp thành **Phase 4**;
> Phase 4/5 cũ thành **Phase 5/6** (nay Phase 5 = polish UI theo đề xuất mới).
> File này là backlog chuẩn duy nhất cho mọi việc chưa làm. Việc đã xong xem `docs/09_*` (2.5),
> `docs/11_*` + `docs/15_*` (3a/3a+ hồ sơ đối chiếu), `docs/17_*` (3b stabilization).
>
> **Quy tắc version (user chốt): Phase chỉ là thứ tự thực hiện, KHÔNG phải phiên bản.**
> Chỉ đổi version khi user yêu cầu hoặc khi có thay đổi lớn được đề xuất + duyệt.

---

## Phase 4 — Preview + Doc Viewer + đóng batch (làm tiếp theo, vẫn zero-npm)

> **Chi tiết thực thi: `docs/18_PHASE_4_PLAN.md`.**
> Spec đầu vào: `docs/EDITOR_PREVIEW_AND_DOC_VIEWER_SPEC.md`.
> Quyết định user đã chốt: Preview = modal `<dialog>` on-demand; Viewer = tab thứ 5;
> vendor commit kèm vào git.

- [x] **Vendor:** `marked` 18.0.11 + `DOMPurify` 3.4.15 vào `web/vendor/` (checksum + nguồn chính thức, `.gitignore` exception đã verify); lazy-load thật qua `loadScriptOnce`.
- [x] **Preview Markdown/HTML:** nút 👁 2 editor + `openPreview` (ext → heuristic), md render `marked+DOMPurify` trong `.doc-markdown`, html render `iframe sandbox=""` + `referrerpolicy`, modal `<dialog>` có a11y.
- [x] **Doc Viewer:** `GET /api/docs` + `GET /api/docs/content` (whitelist `.md/.txt/.html`, chặn traversal/symlink/size — test khóa); tab 📚 Tài liệu (search offline, group theo `dir`, viewer chỉ đọc source); tên dài cuộn ngang cả khối.
- [x] **Diff nguồn ↔ kết quả:** vendor `diff-match-patch` (line-mode, timeout 2s), render 2 cột + liền mạch trong `<dialog>` (`web/js/diff.js`).
- [x] **Toolbar regroup + save 2 chiều:** preview/save per-editor (header phải), lọc/đổi tên/xóa vào tiêu đề Tập tin; header Kết quả Wrap/Preview/Find/Diff/Copy/Save; actions phải (Gửi/Hủy/Dịch lại/Xóa trắng); `/api/save` thêm `side` (sources→status `new`, results→`done`).
- [x] **Workspace UX:** `+prompts` dropdown checkbox + info luôn hiện; info bar góc phải; filter panel restyle + neo dưới nút; 3 cột cao bằng nhau; select-all indeterminate.
- ~~Prompt profile (preset)~~ — **ĐÃ GỠ theo yêu cầu user** (dropdown + `GET /api/profiles` + 3 file JSON; 2 prompt `qa_*.txt` giữ lại vì là prompt độc lập).
- [x] **Diff + cảnh báo output bất thường (heuristic):** `core/quality.py` + banner vàng UI + diff 2 cột/liền mạch (`web/js/diff.js`, xem dòng trên).
- [x] **Batch dịch:** skip-error checkbox + logic (mặc định TẮT) + progress tổng — ĐÃ CÓ trong code; coverage 3 lớp đã bổ sung (Task E).
- [x] **Đóng Phase 4:** acceptance `docs/18_*` §10 đạt (trừ checklist browser tay), `pytest` 155 PASS + node 5/5, CHANGELOG `[Unreleased]` cập nhật (không bump version).

## Phase 5 — Plugin công cụ: chuyển đổi định dạng + EPUB cơ bản (làm tiếp theo)

> **Chi tiết thực thi: `docs/20_PHASE_5_TOOLS_CONVERT_EPUB_PLAN.md`.**
> Spec gốc: `docs/05_*` §1 + quy ước plugin (thêm file là chạy, không framework).

- [ ] **`core/convert.py`:** 6 hàm thuần 2 chiều txt/md/html (strip tags bằng `html.parser`, escape bằng `saxutils`) + unit round-trip.
- [ ] **`tools/epub_tool.py`:** CLI độc lập, EPUB 2.0 (mimetype STORED đầu tiên, OPF+NCX, cover chữ, TOC theo heading/tên file) → `assets/*.epub`.
- [ ] **Backend mỏng:** `POST .../convert` (va chạm `_conflict`, binary skip) + `POST .../epub` (meta mặc định từ project info) + `GET .../epub?file=` (tải về, chặn traversal).
- [ ] **UI:** 1 dialog "Công cụ" (convert file đã chọn + build/tải EPUB), nút trong `#wActions`.
- [ ] **Đóng Phase 5 khi:** `.epub` mở được trong Calibre, convert 6 chiều đúng, `pytest` + node xanh, CHANGELOG `[Unreleased]` (không bump version).

## Phase 6 — Polish UI (ĐỀ XUẤT — chi tiết tách riêng: `docs/21_PHASE_6_UI_POLISH_PROPOSAL.md`)

> Ràng buộc (manifesto §9, đã nới theo quyết định user): vanilla trước;
> framework CSS/JS vẫn cấm; **minimal lib (Pico/Alpine-class) cho phép nếu có đề xuất
> được duyệt** — đánh giá từng lib trong file 19. Chờ duyệt phạm vi + dark mode.

- [ ] Design tokens mở rộng (color roles, elevation, type scale, shape, state layer, motion) + áp theo thứ tự sidebar → buttons → cards → tables → dialogs → toast/progress → empty states. Class cũ giữ nguyên.
- [ ] Focus-visible + contrast tối thiểu. Dark mode tùy chọn.

## Backlog — chỉ làm khi cần (user chốt hoãn, không mang số pha)

- Token/chi phí ước tính trong dialog Gửi AI (hiển thị, không cam kết).
- Find-replace: preview số match mỗi file (dry-run) + undo `.bak` trước ghi.
- Tải 100 chương + script 1-click local (khi cần mới làm).
- **Hiệu quả thấp, hoãn dài hạn (chi tiết ở ROADMAP § deferred):**
  tóm tắt nối tiếp (`handoff`), trích xuất thực thể/nhân vật, glossary UI.

## Cuối cùng — dọn docs + chốt release (làm sau mọi phase)

- Dọn docs (xóa/merge file `del_*`/lịch sử đã hết giá trị tham chiếu), CHANGELOG release,
  bump version **chỉ khi user yêu cầu hoặc có thay đổi lớn được duyệt**.

## Câu hỏi mở (cần user quyết)

1. ~~Preview: pane thứ 3 hay toggle?~~ → **ĐÃ CHỐT: modal `<dialog>` on-demand.**
2. Archive: chỉ nén+xóa (hiện tại) hay cần thêm nút khôi phục trong UI? *(còn mở)*
3. ~~`web/vendor/`: commit kèm hay tải riêng?~~ → **ĐÃ CHỐT: commit kèm.**
4. *(Đã đóng)* Split `index.html`, tên file gộp `*_gop`, CLI `--handoff` (handoff đã hoãn).
5. Phase 5 polish UI: duyệt phạm vi đề xuất trên? Dark mode có làm luôn không? *(mới)*

## Mãi mãi KHÔNG làm (trừ khi manifesto đổi)

Multi-user/auth, queue phân tán, checkpoint/resume, DB workflow lớn, cloud sync, plugin marketplace/framework động, OCR nhúng lõi, đánh giá chất lượng bằng model thứ hai, tối ưu hàng nghìn file trước nhu cầu thực tế. (Nền: `docs/08_*` + manifesto litmus test.)
