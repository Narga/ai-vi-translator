# HỆ THỐNG TÀI LIỆU DỰ ÁN MỚI: CONTENT TRANSLATOR (NEXT-GEN)
> **Thư mục tài liệu**: `docs/` trong dự án `content-translator`  
> **Tôn chỉ tối thượng**: **Minimalist — Single-User — Hiệu Quả — Nhanh — UI Siêu Nhẹ & Thực Dụng**  
> **Bản chất**: **"Đây là công cụ gửi nội dung cho AI và nhận bản dịch về, phục vụ duy nhất một người dùng."**

---

## 📚 BẢN ĐỒ TÀI LIỆU TOÀN DIỆN (DOCUMENTATION SITEMAP)

| Tập tin | Tên tài liệu | Nội dung chính |
| :--- | :--- | :--- |
| **[00]** | [`00_PROJECT_MANIFESTO.md`](00_PROJECT_MANIFESTO.md) | **Tôn Chỉ & Bản Tuyên Ngôn Dự Án**: 5 nguyên tắc bất biến, chu trình gửi–nhận nguyên bản, nguyên tắc vứt bỏ sự phức tạp (không checkpoint, không task manager, không queue) và Câu hỏi sát hạch (Litmus Test) cho mọi tính năng mới. |
| **[01]** | [`01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md`](01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md) | **Phân Tích silaBook & Chắt Lọc Giải Thuật**: Nghiên cứu sâu giải thuật đếm từ $O(N)$ `countWords` và thuật toán cắt thông minh `smartHardSplit` dải 20-80% ưu tiên `\n\n` để bảo toàn 100% định dạng. |
| **[02]** | [`02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md`](02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md) | **Đặc Tả Hệ Thống & Giao Diện Tối Giản**: Cấu trúc thư mục dự án (`sources/`, `translated/`, `assets/`), cấu hình mỏng và tách biệt `keys.json` (.gitignore), cơ chế xoay key đơn giản (gửi $\to$ 429 $\to$ đổi key 1 lần $\to$ dừng), quy trình chia chunk kèm metadata và ghép nối, UI 1 phiên dịch tại 1 thời điểm. |
| **[03]** | [`03_PHASE_1_DETAILED_ACTION_PLAN.md`](03_PHASE_1_DETAILED_ACTION_PLAN.md) | **Kế Hoạch Triển Khai Phase 1 Chi Tiết Tỉ Mỉ (Sinh Mã Được Ngay)**: Đặc tả chi tiết mã nguồn từng file `config.py`, `key_rotator.py`, `chunker.py`, `prompt_engine.py`, `ai_client.py`, `file_handler.py` và script `run.py`. **Sử dụng được ngay lập tức để dịch từ CLI mà không cần chờ đến Phase 2!** |
| **[04]** | [`04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md`](04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md) | **Kế Hoạch Phase 2 (WebUI Lean & Phản Hồi Nhanh)**: Giao diện React SPA đa trang với Sidebar thu gọn (260px $\to$ 64px), thao tác prompt dễ dàng, kiểm tra chunk rõ ràng, sao chép kết quả 1-click, lưu file nhanh chóng, nút gửi lại khi lỗi, Dual-Pane sync-scroll và inline edit. |
| **[05]** | [`05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md`](05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md) | **Chỉ Dẫn Công Cụ & Plugin Độc Lập**: Công cụ EPUB tối giản (đầu vào text/md/html, convert 2 chiều) và cơ chế trích xuất thuật ngữ sinh file `assets/glossary.txt` đính kèm vào chunk. |
| **[06]** | [`ROADMAP.md`](ROADMAP.md) | **Lộ Trình Phát Triển Tương Lai & So Sánh**: Phân tích so sánh về tính năng Checkpoint (tại sao dời lại và khi nào cần), định hướng khai thác SQLite cho tương lai (FTS5 search), tìm kiếm & thay thế hàng loạt, diff viewer. |

---

## 🎯 CÁC TIÊU CHÍ VÀNG ĐƯỢC CHỐT LẠI

1. **Phase 1 sử dụng được ngay**: Có script `run.py` dịch trực tiếp từng chương truyện với đầy đủ logic xoay key, cắt chunk và ghép nối.
2. **Phase 2 mở trình duyệt lên là dùng được ngay**: Giao diện cực nhẹ, không có bảng quản lý rườm rà, phục vụ 1 phiên dịch trực tiếp.
3. **Cơ chế xoay key đơn giản**: Gửi key hiện tại $\to$ nếu 429 và còn key thì thử key tiếp theo 1 lần $\to$ nếu hết key thì dừng báo lỗi cho user bấm gửi lại.
4. **Chia chunk có metadata để ghép nối**: Đánh số `file_index`, `chunk_index`, `total_chunks` giúp ghép nối lại văn bản hoàn chỉnh 100% chuẩn xác.
5. **Cấu hình & Bảo mật**: Cấu hình chung trong `config.json`, keys nhạy cảm trong `keys.json` đưa vào `.gitignore`.
