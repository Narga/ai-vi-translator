# 16. CÁC PHA TIẾP THEO (REVIEW & QUYẾT ĐỊNH)

> **Trạng thái:** Phase 3a + 3a+ đã thực thi xong (92 tests PASS, chờ user test, chưa commit).
> File này là backlog chuẩn duy nhất cho mọi việc chưa làm. Việc đã xong xem `docs/09_*` (2.5),
> `docs/11_*` + `docs/15_*` (3a/3a+ hồ sơ đối chiếu).

---

## Phase 3b — Công cụ nội dung nhẹ (làm tiếp theo, vẫn zero-npm)

- [ ] **Glossary theo project có UI:** endpoint `GET/PUT /api/projects/{slug}/glossary` (text `gốc=nghĩa`, cap ~200 dòng + cảnh báo phình prompt); tab sửa trong Workspace + preview "chunk này trúng N thuật ngữ". Backend lọc đã có (`_glossary_for_chunk` trong `main.py`).
- [ ] **Prompt profile (preset, không engine động):** file JSON trong `prompts/profiles/` (`{name, prompt, extra_prompts[]}`); dropdown Workspace nạp sẵn prompt + extras vào control hiện có; ship 3 mẫu (Tiểu thuyết / Kỹ thuật / Giữ Markdown).
- [ ] **Diff + cảnh báo output bất thường (heuristic, không model chấm điểm):** sau `emit("done")`, server tính mỗi chunk — rỗng / ngắn hơn nguồn 50% / trùng nguồn 80% / mất cấu trúc Markdown (đếm `#`,`-`,`>`) / nghi cắt dở (kết thúc không dấu câu) → kèm `done.warnings[]`; UI banner vàng theo chunk, chỉ cảnh báo không tự sửa. Vendor `diff-match-patch` (1 file ~30KB, `web/vendor/`) khi cần view 2 cột/inline — theo manifesto §9, không cần thảo luận lại. Cửa CodeMirror 6 chỉ mở khi diff/search-replace cần editor thật (chưa có bằng chứng IME).
- [ ] **Preview Markdown/HTML:** vendor `marked` + `DOMPurify` vào `web/vendor/` (pin version, ghi license); pane toggle thứ 3 hoặc thay thế tạm trong Workspace; sanitize hiển thị (backend đã sanitize là chính).
- [ ] **Batch search/replace nâng cao:** đã có thay-hết phạm vi (`POST /api/find-replace` + `skipped`/`errors`); còn thiếu: preview danh sách chỗ match trước khi thay, undo 1 bước (backup `.bak` trước khi ghi).
- [ ] **Ước tính token/chi phí** từ `model_info.pricing` (hiển thị, không cam kết chính xác).
- **Acceptance:** glossary/profile/diff/preview dùng được end-to-end; không model chấm điểm; không state mới ngoài `profiles/*.json`.

## Phase 3c — Batch nhẹ (đóng Phase 3)

- [ ] Batch tuần tự N file đã có (`wsBulkTranslate`); thêm tùy chọn "bỏ qua file lỗi" (checkbox, mặc định TẮT) + progress tổng "file 2/5 · chunk 1/3" + integration test batch 3 file (1 file lỗi giữa chừng → dừng đúng khi TẮT, bỏ qua khi BẬT). Không song song (tránh 429 — manifesto failure policy).
- **Đóng Phase 3 khi:** acceptance 3a+3b+3c checked, `pytest` PASS, CHANGELOG release 3.x.

## Phase 4 — EPUB & ngữ cảnh (kế thừa silaBook)

- [ ] Công cụ EPUB độc lập (`tools/epub_tool.py` — hiện **chưa tồn tại**, đặc tả sẵn trong `docs/05_*` §1): đóng gói sách `.epub` từ `results/` (đầu vào txt/md/html, TOC chuẩn); chuyển đổi 2 chiều MD $\leftrightarrow$ TXT $\leftrightarrow$ HTML.
- [ ] Tóm tắt bối cảnh nối tiếp (`previous_chunk_handoff` qua `{{previous_summary}}`).
- [ ] Trích xuất thực thể/nhân vật → gợi ý `glossary.txt`.

## Phase 5 — Đóng gói & chịu tải

- [ ] Kiểm thử tải dịch 100 chương truyện.
- [ ] Script khởi động 1-click local (`docs/12_*` §1 đã có bản tay).
- [ ] Dọn docs, chốt release.

## Câu hỏi mở (cần user quyết)

1. Preview Markdown/HTML: pane thứ 3 cố định hay toggle thay editor phải? *(từ docs/10 §6 Q4 — còn mở)*
2. Archive: chỉ nén+xóa (hiện tại) hay cần thêm nút khôi phục trong UI? *(từ docs/10 §6 Q2 — còn mở)*
3. `web/vendor/`: commit kèm vào Git (đề xuất — offline tuyệt đối, đúng manifesto §9) hay `.gitignore` + script tải? *(từ docs/10 §6 Q1 — còn mở)*
4. *(Đã đóng)* Split `index.html`: đã tách xong ở 3a. *(Đã đóng)* Tên file gộp `*_gop`: đã bỏ — merge tự lưu từng file gốc.

## Mãi mãi KHÔNG làm (trừ khi manifesto đổi)

Multi-user/auth, queue phân tán, checkpoint/resume, DB workflow lớn, cloud sync, plugin marketplace/framework động, OCR nhúng lõi, đánh giá chất lượng bằng model thứ hai, tối ưu hàng nghìn file trước nhu cầu thực tế. (Nền: `docs/08_*` + manifesto litmus test.)
