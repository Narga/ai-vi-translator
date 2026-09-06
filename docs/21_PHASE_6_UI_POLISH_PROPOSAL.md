# 21. PHASE 6 — ĐỀ XUẤT POLISH UI (chờ duyệt, làm sau Phase 5)

> **Mục tiêu:** UI dễ nhìn theo chuẩn design (tham chiếu Material Design) mà không
> phá kiến trúc: vanilla trước, offline, `python main.py` là chạy.
> **Quy tắc lib (manifesto §9-điểm 2b, quyết định user):** framework CSS/JS vẫn cấm;
> minimal lib chỉ dùng khi có đề xuất được duyệt — đánh giá từng ứng viên ở §4.

---

## 1. PHẠM VI ĐỀ XUẤT

- [ ] **Design tokens mở rộng** trong `web/css/app.css` (tên mới, class cũ giữ nguyên
      để không vỡ UI giữa chừng): color roles (`--primary/--on-primary/--surface/`
      `--on-surface/--surface-variant/--error/...`), elevation 0–3 (box-shadow),
      type scale (display/headline/title/body/label theo tỉ lệ Material),
      shape (`--radius-s/m/l`), state-layer opacity (hover 8%, focus 12%, pressed 12%),
      motion (150–200ms, `ease-out`).
- [ ] **Áp theo thứ tự** (mỗi bước xong mới sang bước sau, checklist tay 4 trang):
      sidebar/nav → buttons (filled/tonal/outline/text trên cùng họ `.btn` hiện có)
      → cards → tables → dialogs (`prevDlg`/`sendDlg`/`findDlg` hưởng a11y từ Phase 4)
      → toast/snackbar + progress → empty states (list rỗng, chưa chọn file/doc).
- [ ] **A11y cơ bản:** `:focus-visible` toàn app, contrast text ≥ 4.5:1,
      mọi icon-btn đã có `title` + bổ sung `aria-label` nơi thiếu.
- [ ] **Tùy chọn (chờ user chốt):** dark mode qua `prefers-color-scheme` — rẻ khi đã
      có color roles, nhưng bệnh là test gấp đôi. Đề xuất: làm sau, tách commit riêng.
- [ ] `tests/test_frontend_hygiene.py` mở rộng: assert token tồn tại, không màu hardcode
      mới ngoài token, dialog có `aria-labelledby`.

**Không làm:** đổi layout 3 cột workspace; icon lib ngoài (giữ SVG tay);
đổi họ class hiện có (`.btn/.card/.table-minimal/.input`).

## 2. VÌ SAO KHÔNG PHẢI LIB NGAY

Hiện app chỉ có ~6KB CSS tay hoạt động tốt, 4 trang đồng bộ. Kéo lib vào lúc này
đồng nghĩa restyle toàn bộ + học API mới + rủi ro vỡ hygiene tests — chi phí lớn hơn
lợi ích khi nhu cầu chỉ là "dễ nhìn hơn". Tokens tay đạt 80% hiệu ứng Material
(elevation, type scale, state layer) với ~100 dòng CSS thêm.

## 3. KHI NÀO LIB ĐÁNG CÂN NHẮC (ngưỡng kích hoạt, không phải bây giờ)

- Form/dialog phình thêm (validation, nested dialog): xét lib classless CSS.
- State tương tác phía client phình (tab + filter + selection đồng bộ phức tạp):
  xét lib reactivity nhỏ.
- Ngưỡng chung: cùng 1 chỗ phải sửa lần thứ 3 vì vanilla rối (rule-of-three) →
  mới viết đề xuất lib cho đúng chỗ đó, không áp toàn app.

## 4. ĐÁNH GIÁ ỨNG VIÊN MINIMAL LIB (đề xuất luôn theo yêu cầu user)

| Lib | Việc nó làm tốt | Vấn đề với repo này | Kết luận |
|---|---|---|---|
| **Pico CSS** (~10KB, classless) | Dialog/form/table đẹp ngay không cần class | Đè toàn bộ look hiện tại (phải restyle 4 trang + viết lại `.btn/.card` hoặc sống chung 2 hệ class); chỉ có CSS, không giải quyết state JS | **Không duyệt cho Phase 5.** Đẹp hơn không đủ bù chi phí restyle. Chỉ xem lại nếu làm lại UI từ đầu. |
| **AlpineJS** (~15KB, `x-data`) | State khai báo (tab/filter/dialog) gọn hơn globals + `onclick` | Kiến trúc hiện tại (plain `<script>` + globals + hygiene test quét ID) đang chạy ổn, Alpine chèn vào giữa gây 2 phong cách state song song; lợi ích chỉ thấy khi thêm nhiều tương tác mới | **Hoãn.** Ngưỡng kích hoạt ở §3 (sửa state lần 3) chưa tới. Viết đề xuất riêng khi tới. |
| **Giữ vanilla + tokens tay** | 0 dependency, 0 rischio hồi quy kiến trúc, test hiện tại giữ nguyên | Tốn ~100 dòng CSS tay + kỷ luật dùng token | **Đề xuất cho Phase 5.** Đúng hạng "việc nhỏ, làm tay rẻ hơn kéo lib". |

> Nếu user vẫn muốn thử 1 lib: phạm vi thí điểm tối đa là **1 trang** (vd. tab Tài liệu
> mới — ít ràng buộc lịch sử nhất), đo trước/sau (dòng code, số bug tay), không đạt
> thì revert. Không thí điểm trên Workspace (luồng tiền của app).

## 5. ACCEPTANCE ĐỀ XUẤT

- [ ] 4 trang + tab Tài liệu đồng bộ tokens, không màu hardcode mới.
- [ ] Keyboard đi hết luồng chính (tab → mở dialog → Esc đóng, focus trả về đúng chỗ).
- [ ] `pytest` xanh; before/after screenshot tay mỗi bước (lưu ngoài repo, không commit).
