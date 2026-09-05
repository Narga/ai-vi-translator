# Đánh Giá Editor: CodeMirror (MirrorCode?) vs Vanilla vs Lib Nhỏ

> **Ngày:** 05/09/2026 — **Giả định:** "MirrorCode" là bạn muốn nói **CodeMirror**
> (đã kiểm chứng: `MirrorCode` trên GitHub là benchmark AI của Epoch, npm `mirrorcode`
> chỉ là canvas-renderer cho CodeMirror — không có editor nào tên MirrorCode).

**Ngữ cảnh:** Workspace hiện tại là 2 `.pane` div + `textContent` + sync-scroll tay (~10 dòng JS).
Yêu cầu mới: số dòng, cuộn đồng thời, diff 2 cột/inline, tìm/thay thế (regex), preview Markdown/HTML.

## Kết luận trước

Không có lib nào "ăn cả 5 món". **Preview Markdown/HTML không thuộc về editor** —
CodeMirror cũng chỉ highlight source, render preview vẫn cần `marked` + `DOMPurify`
dù chọn editor gì. Nên tách quyết định làm hai:

1. **Preview:** lấy `marked` + `DOMPurify` (vendored, ~50KB), độc lập với editor. Xong.
2. **Editor (4 món còn lại):** CodeMirror 6 chỉ đáng giá khi cần **diff merge xịn +
   tìm/thay regex đã được kiểm thử + gõ tiếng Việt (IME) không lỗi**. Còn không,
   vanilla + gutter số dòng + `diff-match-patch` vendored là đủ và nhẹ hơn nhiều.

## Bảng đối chiếu từng yêu cầu

| Yêu cầu | Vanilla (hiện tại + thêm) | CodeMirror 6 | Lib nhỏ chuyên 1 việc |
|---|---|---|---|
| Số dòng | Gutter div tự render, đồng bộ scroll (~20 dòng, dễ) | `lineNumbers()` có sẵn | — (không cần lib) |
| Cuộn đồng thời 2 pane | Đã có (`onscroll` chép `scrollTop`) | 2 `EditorView` + listener scroll (tương đương) | — (không cần lib) |
| Diff 2 cột / inline cùng dòng | **Khó nhất**: phải có thuật toán diff (tự viết Myers = rủi ro cao) | `@codemirror/merge`: `MergeView` (2 cột) + `unifiedMergeView` (inline), gộp vùng không đổi, nút nhận/bỏ từng chunk, nhảy chunk trước/sau | **`diff-match-patch` của Google (~30KB, 1 file)**: engine diff đúng + nhẹ nhất; tự render 2 cột/đánh dấu dòng đổi (vài chục dòng DIY) |
| Tìm/thay thế + regex | Tự viết: `RegExp` + highlight overlay (~80 dòng). **Rủi ro thực**: Unicode Việt, `$` trong chuỗi thay thế, gõ IME (bộ gõ tách ký tự khi composition) | `@codemirror/search`: panel tìm/thay, **regexp có sẵn**, đã qua kiểm thử IME/Unicode | — (không có lib nhỏ nào làm tốt hơn CM) |
| Sửa trực tiếp bản dịch | `contenteditable` + `textContent`: đang chạy, nhưng IME tiếng Việt trong contenteditable vốn lỗi vặt (mất dấu, nhảy caret) | CM6 xử lý IME/composition đúng chuẩn, undo/redo tử tế | — |
| Preview Markdown/HTML | Cần thêm lib (xem dưới) | Cũng cần thêm lib — CM chỉ highlight source (`@codemirror/lang-markdown`, `lang-html`) | `marked` (~30KB) render MD + `DOMPurify` (~20KB) sanitize (backend đã sanitize, đây là lớp hiển thị) |

## Chi phí thật của CodeMirror 6 (theo tài liệu chính thức)

- **Dung lượng:** basicSetup + 1 language ≈ 400KB min (~135KB gzip); `minimalSetup` ≈ 250KB
  (75KB gzip); cộng thêm `merge` + `search` + `lang-markdown`/`lang-html`.
- **Phân phối mới là vấn đề lớn nhất:** CM6 là chùm module npm, trình duyệt không nạp
  trực tiếp được — phải **bundling (Rollup/esbuild) hoặc ESM CDN (esm.sh) + import map**.
  Cả hai đều phá quy ước "1 file, zero npm, `python main.py` là chạy offline" của repo:
  CDN thì mất mạng là mất editor; bundling thì máy dev phải có Node (runtime của user
  vẫn sạch, nhưng repo có thêm bước build + file bundle ~300–500KB cần version).
- Lối thoát duy nhất giữ lean: **build một lần, vendor 1 file `web/vendor/cm.bundle.js`,
  lazy-load chỉ ở Workspace** (đúng như `Y_KIEN_UI_STACK_VA_EDITOR.md` đã chốt).

## Lựa chọn thay thế đáng nói: CodeMirror 5 legacy

- CM5 vẫn ra bản vá (5.65.x tới 2026), phân phối dạng **file JS rời, thẻ `<script>` thuần —
  không cần bundler**: core (~170KB) + addon `merge` + `search` + `dialog` + `diff-match-patch`.
- Tổng ~250KB file rời, cache được, hợp với kiến trúc hiện tại hơn CM6.
- Đổi lại: legacy (không update tính năng), mobile/a11y kém CM6, API cũ.
- **Chỉ cân nhắc nếu team ghét bước build mà vẫn muốn merge-UI có sẵn.**

## Đề xuất (theo thứ tự Phase 3)

1. **Ngay (3a):** vanilla + gutter số dòng tự viết. Sync-scroll giữ nguyên. 0 byte thêm.
2. **Preview (3b):** vendor `marked` + `DOMPurify`, render vào pane thứ 3/toggle.
   Quyết định độc lập, làm trước hay sau editor đều được.
3. **Tìm/thay regex (3b):** thử panel vanilla trước (~80 dòng + test với chuỗi Việt,
   regex có flag `u`, thay thế `$&`). Nếu lòi bug IME/offset → đó là tín hiệu lên CM.
4. **Diff (3b):** vendor `diff-match-patch` (1 file, ~30KB) + render DIY:
   view 2 cột cho nguồn–dịch, view inline cho 2 lần dịch. Đủ cho heuristic Phase 3
   (chunk rỗng/ngắn/trùng nguồn/cắt dở đã có từ 2.5).
5. **Cửa CodeMirror 6** chỉ mở khi đồng thời: (a) bug IME trong ô sửa tay tái phát,
   (b) muốn workflow nhận/bỏ từng chunk diff kiểu merge. Khi đó build-once vendor bundle,
   lazy-load ở Workspace. Không mở chỉ vì "số dòng" hay "cuộn đồng thời" — hai món đó
   vanilla đã làm được.

**Một câu:** Preview thì lấy `marked`+`DOMPurify` (không liên quan editor);
diff thì `diff-match-patch` là điểm ngọt nhất giữa đúng và nhẹ;
CodeMirror 6 để dành cho ngày IME và merge-workflow bắt ta phải trả giá bundle.
