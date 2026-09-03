# HỆ THỐNG TÀI LIỆU DỰ ÁN MỚI: NOVEL & TEXT TRANSLATOR (NEXT-GEN)
> **Thư mục tài liệu**: `docs/new_project_plan/`  
> **Tôn chỉ dự án**: **Minimalist — Single-User — Hiệu Quả — Nhanh — UI Siêu Nhẹ & Thực Dụng**  
> **Mục tiêu cốt lõi**: Dùng AI chuyển ngữ nội dung được cấp sang tiếng Việt, người dùng tự chủ động kiểm soát nội dung, không public (chạy Local hoặc Private VPS tự bảo vệ), loại bỏ mọi sự hào nhoáng và các cơ chế bảo mật thừa thãi.

---

## 📚 BẢN ĐỒ TÀI LIỆU (DOCUMENTATION INDEX)

Bộ tài liệu này cung cấp bức tranh toàn cảnh, kiến trúc hệ thống, phân tích giải thuật, đặc tả giao diện và kế hoạch triển khai chi tiết từng bước cho dự án mới:

| Tập tin | Tên tài liệu | Nội dung chính |
| :--- | :--- | :--- |
| **[00]** | [`00_PROJECT_MANIFESTO.md`](00_PROJECT_MANIFESTO.md) | **Tôn Chỉ & Bản Tuyên Ngôn Dự Án**: 5 nguyên tắc bất biến: Đơn người dùng (Single-User), Tự do & chủ động nội dung, Riêng tư & tự bảo vệ ở tầng hạ tầng, Tốc độ & hiệu quả là số 1, UI siêu nhẹ & thực dụng (Lean UI), KHÔNG hào nhoáng bóng bẩy. |
| **[01]** | [`01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md`](01_SILABOOK_ANALYSIS_AND_ENHANCEMENTS.md) | **Phân Tích silaBook & Đề Xuất Kế Thừa, Tối Ưu**: Phân tích các giải thuật `countWords` $O(N)$, thuật toán chia cắt thông minh `smartHardSplit`, kỹ thuật `filterGlossary` động, cơ chế bối cảnh nối tiếp `previous_chunk_handoff` và các bài học quý giá đưa vào dự án mới. |
| **[02]** | [`02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md`](02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md) | **Đặc Tả Hệ Thống & Giao Diện Đa Trang (Dedicated Pages)**: Quy định giao diện 8 trang riêng biệt (không dồn 1 trang), thiết kế **Sidebar có thể thu gọn (Collapsible)** để mở rộng không gian, cơ chế Thư viện Prompt `.txt` hỗ trợ chọn thêm prompt bổ sung, hạ tầng xoay vòng Key Pool tối ưu token miễn phí. |
| **[03]** | [`03_PHASE_1_DETAILED_ACTION_PLAN.md`](03_PHASE_1_DETAILED_ACTION_PLAN.md) | **Kế Hoạch Thực Hiện Phase 1 Chi Tiết Tỉ Mỉ**: Bẻ nhỏ thành từng bước hành động 2-5 phút, đặc tả chi tiết code `KeyPoolManager`, `FormatPreservingChunker`, `PromptEngine`, API client với cơ chế tự động cooldown 60s khi gặp lỗi 429. |
| **[04]** | [`04_PHASE_2_AND_ROADMAP.md`](04_PHASE_2_AND_ROADMAP.md) | **Kế Hoạch Phase 2 (Hoàn Tất Có Thể Dịch Thử Nghiệm Ngay)**: Đặc tả cấu trúc lưu trữ dự án, Runner nạp file và dịch thử nghiệm một nguồn nội dung bất kỳ; cùng lộ trình mở rộng Phase 3 (UI React), Phase 4 (Nâng cao) và Phase 5 (Đóng gói). |
| **[05]** | [`05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md`](05_STANDALONE_PLUGINS_AND_TOOLS_GUIDE.md) | **Chỉ Dẫn Chi Tiết Các Công Cụ & Plugin Độc Lập**: Hướng dẫn xây dựng Công cụ EPUB tối giản (đầu vào text/md/html, convert 2 chiều) và Công cụ trích xuất thực thể/nhân vật (sinh file `glossary.txt` tại thư mục dự án và đính kèm vào prompt gửi chunk). |

---

## 🎯 CÁC TIÊU CHÍ VÀNG CỦA DỰ ÁN MỚI
1. **Single-User & Zero Auth**: Ứng dụng chỉ phục vụ 1 người dùng duy nhất, không đăng nhập, không phân quyền, không session phức tạp.
2. **Minimalist & Pure Text Focus**: Chỉ tập trung dịch văn bản (TXT, Markdown, HTML), không ôm đồm OCR hay các parser nặng nề.
3. **Bảo toàn 100% định dạng gốc**: Không làm mất khoảng cách dòng, thụt lề, cú pháp Markdown.
4. **Thư viện Prompt `.txt` linh hoạt**: Gửi chunk kèm prompt chính, cho phép tick chọn thêm các prompt bổ sung.
5. **Tối ưu hóa triệt để token miễn phí**: Cụm Key Pool Google Gemini và OpenAI-compatible tự động chuyển key khi gặp 429.
6. **UI Siêu Nhẹ & Thực Dụng (Lean UI)**: Đa trang riêng biệt, Sidebar thu gọn được, loại bỏ hiệu ứng bóng bẩy, tập trung vào tốc độ và hiển thị văn bản.
7. **Milestone thực tế rõ ràng**: Kết thúc **Phase 2**, hệ thống đã có thể nạp một file tiểu thuyết/văn bản bất kỳ và thực hiện dịch thử nghiệm hoàn tất!
