# 🧠 Giới Thiệu Phiên Cố Định: Content Translator (ai-vi-translator)

Tập tin này là "bộ nhớ dài hạn" (Long-term Memory) duy nhất và đầy đủ nhất của dự án Content Translator. Nó tổng hợp mọi quyết định kỹ thuật, bước ngoặt kiến trúc và logic nghiệp vụ từ tất cả các phiên làm việc trước đó. 

> [!IMPORTANT]
> Toàn bộ các phiên chat cũ đã được xóa. Đây là nguồn tri thức duy nhất để AI tiếp tục duy trì tính nhất quán cho dự án.

---

## 1. 🎯 Tổng Quan & Triết Lý Dự Án
- **Tên dự án:** Content Translator (Tên cũ: Novel Translator).
- **Mục tiêu:** Hệ sinh thái dịch thuật nội dung (tiểu thuyết, tài liệu dài) chuyên nghiệp tối ưu cho Gemini AI.
- **Triết lý cốt lõi:** 
    - Dịch văn học trôi chảy, giữ đúng ngữ cảnh (Context-aware).
    - Tối ưu chi phí API (Smart Cache & Translation Memory).
    - Độ tin cậy tuyệt đối (ACID Checkpoints).
    - Trải nghiệm người dùng cao cấp (Side-by-Side Review).

---

## 2. 🏛️ Kiến Trúc Hệ Thống (v5.0.0 Alpha)

### A. Phân Tầng Chức Năng (Architectural Layers)
1.  **Lớp Chiến lược (`ExecutionManager`)**: Điều phối toàn bộ tiến trình, quản lý số lượng worker và giám sát tiến độ.
2.  **Lớp Điều phối (`ApiManager`)**: Quản lý vòng đời API Key, xoay vòng key thông minh và xử lý lỗi Rate Limit.
3.  **Lớp Thực thi (`Worker`)**: Các tác vụ asyncio thực hiện dịch chunk, chuẩn hóa kết quả và lưu checkpoint.

### B. Cơ Chế Điều Phối API (Api Handling)
- **Worker-Key Affinity**: Mỗi worker ưu tiên dùng 1 key để tận dụng server-side cache của Gemini.
- **Reserve Pool**: Hệ thống failover sang key dự phòng trong `< 1ms` nếu key chính bị cạn quota.
- **Adaptive Scaling**: Tự động điều chỉnh số lượng worker dựa trên `success_rate`. Chế độ **Slow-Start** khi gặp lỗi 429 hàng loạt.

### C. Quản Lý Dữ Liệu
- **SQLite Checkpoint**: Thay thế JSON bằng SQLite (WAL mode). Đảm bảo tính toàn vẹn dữ liệu (ACID) và hỗ trợ resume tiến trình 100%.
- **Translation Memory (TM)**: Sử dụng thuật toán Jaccard Similarity (N-gram) với ngưỡng tương đồng ≥85%.

---

## 3. 📅 Lịch Sử Phát Triển & Các Giai Đoạn Quan Trọng

### Giai đoạn 1-2: Monolithic & Legacy (v1.x -> v2.x)
- Phát triển các script dịch thuật đơn lẻ. Chuyển đổi sang SDK `google-genai` mới.
- Tích hợp `tqdm` và cơ chế Rate Limiting cơ bản (v2.x).

### Giai đoạn 3: Kiến Trúc Plugin (v3.0.x)
- **Quyết định:** Tách biệt core và feature thông qua `ServiceBus` và `EventBus`.
- **Hệ quả:** Mở rộng được OCR và EPUB Converter nhưng kiến trúc Bus bị đánh giá là over-engineering cho luồng pipeline tuần tự.

### Giai đoạn 4: WebUI & UI Redesign (v4.0.x - v4.1.0)
- **UI:** Redesign với PicoCSS, phân tách tab Pending/Done.
- **Feature:** Tích hợp TM (Translation Memory), Cache Busting (`?v=APP_VERSION`), và SSE Streaming cho tiến độ thời gian thực.
- **Refactor:** JavaScript được tách từ nội tuyến (inline) sang file external (`static/js/main.js`).

### Giai đoạn 5: Tái Cấu Trúc v5.0.0 Alpha (Báo cáo 01/03/2026)
- **Vấn đề:** `webui.py` phình to (>1500 dòng), EventBus gây khó debug.
- **Giải pháp:**
    - Module hóa WebUI thành package với các Blueprint (Flask).
    - Chuyển sang **Functional Pipeline** đơn giản, loại bỏ Bus dư thừa.
    - Hợp nhất các phiên bản lẻ từ v10.x về v5.0.0 để chuẩn hóa Roadmap 2026.

### Giai đoạn 6: Hoàn Thiện Thuật Toán (Hiện tại)
- **Sentence Aggregation Chunker:** Thay thế thuật toán cắt theo index bằng cắt theo câu trọn vẹn (Regex multi-language). Tuyệt đối không cắt ngang câu.
- **Dynamic Glossary Injection:** Chỉ nhúng thuật ngữ vào prompt nếu từ đó thực sự xuất hiện trong chunk hiện tại (tiết kiệm Token).
- **Side-by-Side Editor:** Giao diện biên tập song ngữ thời gian thực.
- **Theme Fixes:** Tối ưu textarea height, layout header và hệ thống Toast Notifications.

### Giai đoạn 7: v6.0.0 Alpha (Multi-Provider & Workflow)
- **Multi-Provider AI:** Tích hợp OpenAI SDK (`openai>=1.0.0`) hỗ trợ OpenAI/OpenRouter song song Gemini qua `services/ai_provider.py` (Adapter Pattern).
- **Template Architecture:** Tách `index.html` thành 6 Jinja2 partials chuyên biệt (`templates/partials/`).
- **Project Workflow Tabs:** 5 tabs chức năng (Info, Files, Translation, Guidelines, Prompts).
- **Guidelines & AI Summarize:** Hỗ trợ `GET/PUT /guidelines` (5 fields) và tự động tóm tắt nội dung bằng AI (`POST /summarize`).
- **Prompt Library:** Nạp bộ prompt từ thư viện genre (Mặc định + Thể loại) vào project prompt.
- **Bug Fixes:**
    - Sidebar toggle expand cột chính (`w-100-l`).
    - SSE handler ưu tiên hiển thị `translated_text` trong textarea.
    - `startTranslation()` tự động định tuyến API project.
    - Model selector cho AI Summarize.
- **Tài liệu tham khảo:** `docs/v6-development-plan.md` và `docs/CHANGELOG.md`.

---

## 4. 📝 Quy Tắc Làm Việc & Coding Convention

1.  **Naming:** Luôn gọi dự án là "Content Translator". Code tuân thủ `snake_case` cho hàm/biến, `PascalCase` cho lớp. 
2.  **Arch:** Tuân thủ cấu trúc Blueprint trong `webui/` và Functional Pipeline trong `core/`.
3.  **Frontend:** Không viết inline CSS/JS. Sử dụng Tachyon CSS Framework (tachyons.io) và các biến `{{ app_version }}` cho cache busting.
4.  **Logging:** Tuyệt đối không dùng `print()`. Sử dụng module `logging` với các level phù hợp.
5.  **Data:** Luôn dùng `checkpoint_service.py` (SQLite) cho mọi tương tác trạng thái dự án.
6.  **Safety:** Ưu tiên trả về text gốc kèm đánh dấu `<!-- FAILED_CHUNK -->` thay vì crash khi gặp lỗi API không thể phục hồi.


---
*Cập nhật lần cuối: 17/03/2026*
