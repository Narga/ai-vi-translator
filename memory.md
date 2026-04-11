# 🧠 Project Memory: Content Translator (ai-vi-translator)

Tập tin này là "bộ nhớ dài hạn" (Long-term Memory) duy nhất và đầy đủ nhất của dự án Content Translator. Nó tổng hợp mọi quyết định kỹ thuật, bước ngoặt kiến trúc và logic nghiệp vụ từ tất cả các phiên làm việc trước đó.

> [!IMPORTANT]
> Đây là nguồn tri thức duy nhất để AI duy trì tính nhất quán cho dự án giữa các phiên làm việc.

---

## 1. 🎯 Tổng Quan & Triết Lý Dự Án
- **Tên dự án:** Content Translator (v6.1.0).
- **Mục tiêu:** Hệ sinh thái dịch thuật nội dung (tiểu thuyết, tài liệu dài) chuyên nghiệp tối ưu cho Gemini AI và OpenAI-compatible APIs.
- **Triết lý cốt lõi:** 
    - **Context-aware**: Dịch văn học trôi chảy, giữ đúng ngữ cảnh.
    - **Efficiency**: Tối ưu chi phí API qua Smart Cache & Translation Memory (TM).
    - **Reliability**: Đảm bảo tính toàn vẹn dữ liệu qua SQLite Checkpoints (ACID).
    - **UX/UI**: Trải nghiệm UI cấp độ Premium với Dashboard tối giản (Tachyons Card-based).

---

## 2. 🏛️ Kiến Trúc Hệ Thống (v6.1.0)

### A. Phân Tầng Chức Năng
1.  **WebUI (`webui/`)**: Module hóa bằng Flask Blueprints.
    - `settings`: Cấu hình Provider, Models, API Keys.
    - `projects`: Quản lý workspace, sources, translated files, metadata.
    - `translation`: SSE streaming worker cho tiến trình dịch.
2.  **Core Executor (`core/executor.py`)**: Điều phối luồng dịch thuật (Functional Pipeline), thay thế hệ thống Plugin v3.x cũ.
3.  **Services (`services/`)**:
    - `ai_provider.py`: Adapter pattern hỗ trợ đa nhà cung cấp (Gemini/OpenAI).
    - `checkpoint_service.py`: Quản lý trạng thái dịch bằng SQLite (WAL mode).
    - `translation_memory.py`: Fuzzy matching (Jaccard Similarity) để tái sử dụng bản dịch.
    - `glossary_service.py`: Dynamic injection thuật ngữ theo ngữ cảnh.

### B. Workspace Model (Project-Based)
Dự án đã chuyển đổi hoàn toàn sang mô hình "Project-based":
- Mọi file dịch đều thuộc về một project.
- `default-project`: Dùng cho các tác vụ dịch đơn lẻ hoặc CLI fallback.
- Đường dẫn: `workspace/projects/<slug>/` (chứa `sources/`, `translated/`, `metadata.json`).

---

## 3. 📅 Lịch Sử Phát Triển & Các Giai Đoạn Quan Trọng

### Giai đoạn 1-4: Từ Monolithic đến Plugin (v1.x -> v4.x)
- Phát triển core dịch thuật, tích hợp Rate Limiting.
- Redesign UI với PicoCSS, tách CSS/JS ra file riêng.
- Tích hợp Translation Memory và Cache Busting.

### Giai đoạn 5: Tái Cấu Trúc v5.0.0 Alpha (01/03/2026)
- Module hóa WebUI thành package với Blueprints.
- Chuyển sang **Functional Pipeline** đơn giản, loại bỏ EventBus dư thừa.
- Hợp nhất các phiên bản lẻ về v5.0.0.

### Giai đoạn 6: Hoàn Thiện Thuật Toán (Hiện tại)
- **Sentence Aggregation Chunker**: Đảm bảo 100% không cắt ngang câu.
- **Dynamic Glossary Injection**: Chỉ nhúng thuật ngữ nếu xuất hiện trong chunk.
- **Side-by-Side Editor**: Giao diện biên tập song ngữ thời gian thực.

### Giai đoạn 7: v6.0.0 Beta 1 (Project Sources & AI Config)
- **Batch Translation**: Dịch nhiều file cùng lúc.
- **Select All Toggle**: Quản lý file hàng loạt dễ dàng.
- **File Renaming**: Đồng bộ đổi tên file nguồn và file dịch.
- **Workspace Optimization**: Hợp nhất mọi luồng vào mô hình Project.

---

## 4. 📝 Quy Tắc Làm Việc & Coding Convention

1.  **Naming**: Call project "Content Translator". Python: `snake_case`. JS: `camelCase`. CSS: Tachyons + Custom variables.
2.  **Arch**: Tuân thủ cấu trúc Blueprint trong `webui/` và Functional Pipeline trong `core/`.
3.  **Frontend**: Không viết inline CSS/JS. Sử dụng Tachyons utilities cho styling. Sử dụng `{{ app_version }}` cho cache busting.
4.  **Logging**: Sử dụng module `logging`, không dùng `print()`.
5.  **Archiving**: Tuân thủ quy tắc lưu trữ vào `workspace/archive` và xóa khỏi workspace khi archive.

---

## 5. 🗺️ Lộ Trình Phát Triển (Roadmap)
- [ ] Hoàn thiện hệ thống Managed Context (/checkpoint & /resume).
- [ ] Tích hợp sâu hơn các model Thinking (Gemini 2.0 Thinking/OpenAI o1).
- [ ] Cải thiện độ chính xác của Translation Memory (Semantic search / Vector DB).

---

## 6. 🔄 Session Marker (Handover)
- **Phiên bản hiện tại**: v6.1.0
- **Trạng thái**: ACTIVE
- **Hoạt động gần nhất**: 
    - Hoàn thiện hệ thống Project Archiving (Zip/Restore).
    - Tối ưu hóa Dashboard UI sang Tachyons (Performance focus).
    - Reorganize documentation: CHANGELOG, ROADMAP, REPORTS, README, DEVELOPMENT ra thư mục gốc.
- **Handover Note**:
    - Dự án đã đạt độ ổn định cao về cấu trúc. Sẵn sàng cho Giai đoạn 6.2 (Bảo toàn định dạng EPUB/Markdown).
    - Cần rà soát `REPORTS.md` khi có các đợt audit hệ thống định kỳ.

---
*Cập nhật lần cuối: 11/04/2026*
