# 📊 BÁO CÁO TỔNG HỢP: PHÂN TÍCH MÃ NGUỒN & KẾ HOẠCH NÂNG CẤP HỆ THỐNG
## DỰ ÁN: NOVEL TRANSLATOR (v5.0.0 Alpha)

**Ngày lập:** 01/03/2026  
**Người thực hiện:** Đội ngũ Phát triển & Chuyên viên Phân tích AI  
**Trạng thái:** Hoàn tất khảo sát - Chờ phê duyệt triển khai  

---

## 1. TỔNG QUAN HỆ THỐNG HIỆN TẠI

### 1.1 Mục tiêu Dự án
Novel Translator là hệ thống dịch thuật chuyên biệt cho tiểu thuyết và tài liệu dài hơi, sử dụng sức mạnh của Google Gemini API. Mục tiêu là tạo ra bản dịch văn học trôi chảy, giữ đúng văn phong và ngữ cảnh, đồng thời tối ưu hóa chi phí API thông qua các cơ chế Cache và Rate Limiting thông minh.

### 1.2 Đánh giá Cấu trúc Thư mục
Kiến trúc hiện tại đi theo hướng phân tách Layer nhưng đang gặp vấn đề về sự phình to không đồng đều:
- `webui.py`: **Single File Monster (1500+ dòng)** - Chứa toàn bộ logic từ giao diện đến worker.
- `core/`: Hệ thống Service/Event Bus đang bị **Over-engineering** (quá phức tạp so với nhu cầu thực tế).
- `services/`: Quản lý API, Cache, và TM khá tốt nhưng chưa nhất quán về dữ liệu.
- `plugins/`: Tách biệt được các tính năng phụ trợ (OCR, Epub) nhưng logic dịch thuật cốt lõi (Translation Plugin) còn nhiều lỗ hổng thuật toán.

---

## 2. PHÂN TÍCH CÁC VẤN ĐỀ CỐT LÕI

### 2.1 Vấn đề về Kiến trúc & Mã nguồn (Structural Issues)
1. **Sự cồng kềnh của WebUI**: Việc dồn nén mọi thứ vào một file `webui.py` khiến việc bảo trì cực kỳ khó khăn. Global state không an toàn (thread-safety) gây rủi ro leak dữ liệu giữa các phiên dịch thuật.
2. **Kiến trúc "Bus" dư thừa**: Core sử dụng `EventBus` và `ServiceBus` cho một quy trình vốn dĩ là Pipeline tuần tự. Điều này làm chậm hệ thống và gây khó khăn khi debug luồng dữ liệu.
3. **Trùng lặp Logic Cache & TM**: Logic tạo Cache Key và lưu trữ Translation Memory (TM) bị phân mảnh giữa Global và Project-specific, không có cơ chế đồng bộ hóa.
4. **Error Handling & Validation**: Thiếu kiểm tra đầu vào (Input Validation), dẫn đến các lỗi tiềm ẩn về Security và Crash hệ thống khi nhận dữ liệu không mong muốn.

### 2.2 Vấn đề về Thuật toán Dịch thuật (Algorithmic Issues)
1. **Lỗ hổng Chunker (Cắt văn bản)**: Thuật toán tìm điểm cắt dựa trên index ngược rủi ro cao. Nếu không tìm thấy dấu câu trong "window", hệ thống cắt cứng, dẫn đến mất chữ hoặc cắt đôi từ ở ranh giới Chunk.
2. **Cơ chế Retry & Cooldown mù quáng**: Hệ thống retry đến 8 lần cho các lỗi Quota, có thể treo tiến trình đến 10-15 phút mà không có phản hồi cho người dùng.
3. **Logical Fallback yếu**: Khi gặp lỗi "Cắt vắn" (Length Ratio) hoặc lỗi API liên tục, hệ thống trả về thông báo lỗi cứng thay vì giữ nguyên text gốc để biên dịch viên xử lý, làm gãy mạch toàn bộ văn bản đầu ra.
4. **Correction Mode dư thừa**: Việc dùng Regex phát hiện ký tự Trung `[\u4e00-\u9fff]` trên toàn bộ kết quả dịch để ép sửa lỗi gây lãng phí tài nguyên và thường xuyên sai lệch với các danh từ riêng/ngoại truyện cố ý để gốc.

---

## 3. KẾ HOẠCH HÀNH ĐỘNG NÂNG CẤP (v5.0.0)

### Phase 1: Tái Cấu Trúc Toàn Diện (Refactor & Stabilize)
*   **Module hóa WebUI**: Tách `webui.py` thành thư mục `webui/` với các Blueprints: `routes/translation.py`, `routes/projects.py`, `routes/prompts.py`.
*   **Đơn giản hóa Core**: Loại bỏ EventBus, chuyển sang kiến trúc **Functional Pipeline**. Chỉ giữ lại Service Manager cho các dịch vụ dùng chung (API, Logger, Config).
*   **Thống nhất SDK**: Xóa bỏ hoàn toàn hỗ trợ cho `google-generativeai` cũ, tập trung tối ưu 100% cho `google-genai` SDK mới nhất.
*   **Thêm Checkpoint SQLite**: Thay thế JSON checkpoint bằng SQLite để quản lý trạng thái từng Chunk trong dự án, đảm bảo khả năng khôi phục (Resume) tin cậy 100%.

### Phase 2: Nâng Cấp Thuật Toán & Xử Lý Dữ Liệu
*   **Smart Sentence Chunker**: Áp dụng thuật toán **Sentence Aggregation**. Không cắt theo index, chỉ cắt sau khi đã hoàn thành một câu trọn vẹn. Nếu vượt limit, chủ động chuyển cả câu sang Chunk sau.
*   **Dynamic Glossary Injection**: Hệ thống tự động quét và nhúng các thuật ngữ (Glossary) vào Prompt chỉ khi chúng xuất hiện trong Chunk hiện tại, giúp tiết kiệm Token và tăng độ chính xác của LLM.
*   **Robust Fallback**: Nếu Chunk dịch thất bại sau 3 lần thử, hệ thống sẽ đánh dấu `<!-- FAILED_CHUNK -->`, lưu text gốc và tiếp tục dịch đoạn sau thay vì dừng lại.

### Phase 3: Tính Năng Mới & Trải Nghiệm Người Dùng (UX)
*   **Giao diện Side-by-Side Review**: WebUI mới sẽ cho phép xem bản gốc và bản dịch song song để biên tập viên chỉnh sửa thủ công ngay trước khi xuất file.
*   **Nút Dừng Khẩn Cấp (Emergency Stop)**: Tích hợp nút điều khiển trên giao diện để ngắt ngay tiến trình gọi API khi phát hiện sai lầm hàng loạt.
*   **Tích hợp Prompt Sets (Genre-based)**: Tự động đề xuất Prompt phù hợp theo thể loại truyện (Ngôn tình, Tiên hiệp, Trinh thám...).

---

## 4. KẾT LUẬN & KIẾN NGHỊ

Hệ thống Novel Translator đang sở hữu một bộ khung (Framework) xử lý API rất mạnh mẽ nhưng cần được **tối giản hóa kiến trúc** và **nâng cấp thuật toán cắt câu**. 

**Kiến nghị:**
1. Phê duyệt việc tái cấu trúc `webui.py` ngay lập tức để tránh nợ kỹ thuật (Technical Debt).
2. Triển khai SQLite thay cho file JSON để quản lý dự án dài hơi.
3. Ưu tiên nâng cấp thuật toán `Sentence Chunker` vì đây là yếu tố tiên quyết quyết định chất lượng ngữ cảnh bản dịch.

---
*Báo cáo được tổng hợp và trình lên bởi Hệ thống Phân tích AI - Ngày 01/03/2026.*
