# 02. ĐẶC TẢ HỆ THỐNG CỐT LÕI & GIAO DIỆN (MINIMALIST SPECIFICATION)
> **Mục tiêu**: Định nghĩa cấu trúc hệ thống gửi–nhận tối giản, cơ chế xoay key đơn giản, cấu trúc dự án tệp tin và giao diện phục vụ duy nhất một phiên dịch tại một thời điểm.

---

## 1. CẤU TRÚC THƯ MỤC DỰ ÁN (PROJECT DIRECTORY STRUCTURE)

Mọi dự án dịch được tổ chức hoàn toàn dưới dạng thư mục tệp tin trực quan, không phụ thuộc vào cơ sở dữ liệu phức tạp:

```text
workspace/projects/Truyen_Tien_Hiep/
├── sources/            # Chứa các file chương gốc (ch01.md, ch02.txt, chap03.html...)
├── translated/         # Chứa các file bản dịch tiếng Việt hoàn chỉnh sau khi ghép chunk
└── assets/             # Chứa tài nguyên riêng của dự án:
    ├── glossary.txt    # Bảng thuật ngữ / nhân vật riêng của truyện này
    └── custom_prompt.txt # (Tùy chọn) Các file prompt riêng của dự án để dễ sao lưu, làm lại
```

* **Lợi ích**: Toàn bộ dự án gói gọn trong 1 thư mục. Muốn sao lưu hay chuyển sang máy khác/VPS, chỉ cần copy thư mục `Truyen_Tien_Hiep` là xong 100%.

---

## 2. QUẢN LÝ CẤU HÌNH & BẢO VỆ DỮ LIỆU NHẠY CẢM

Hệ thống sử dụng **một lớp lưu cấu hình cực mỏng**, đọc/ghi file JSON cục bộ, tách biệt hoàn toàn giữa cấu hình chung và dữ liệu nhạy cảm:

```
config/
├── config.json         # Cấu hình chung (model, timeout, max_chars...) - Đưa vào Git
└── keys.json           # DỮ LIỆU NHẠY CẢM (API keys, provider secrets) - BẮT BUỘC TRONG .gitignore
```

### 2.1. File `config/config.json` (Cấu hình chung)
```json
{
  "default_provider": "gemini",
  "gemini_model": "gemini-2.5-flash",
  "openai_base_url": "https://openrouter.ai/api/v1",
  "openai_model": "qwen/qwen-2.5-72b-instruct",
  "max_chunk_chars": 12000,
  "timeout_seconds": 90
}
```

### 2.2. File `config/keys.json` (Dữ liệu nhạy cảm - `.gitignore`)
```json
{
  "gemini_keys": [
    "AIzaSyD-KEY_1",
    "AIzaSyD-KEY_2",
    "AIzaSyD-KEY_3"
  ],
  "openai_api_key": "sk-or-v1-..."
}
```

### 2.3. SQLite (Dự trữ cho tương lai, KHÔNG dùng làm Storage trạng thái)
* Một file SQLite rỗng `workspace/app.db` được khởi tạo sẵn sàng cho các tính năng tìm kiếm, đánh chỉ mục trong tương lai.
* **Quy tắc bất biến**: Trong Phase 1 và Phase 2, **tuyệt đối KHÔNG sử dụng SQLite để lưu trạng thái dịch hay checkpoint**.

---

## 3. CƠ CHẾ XOAY VÒNG API KEY TỐI GIẢN (MINIMAL KEY ROTATION)

Được thiết kế thành một module độc lập (`core/key_rotator.py`), áp dụng trước tiên cho Google Gemini nhưng có thể tái sử dụng ngay lập tức cho các Provider khác.

### 3.1. Logic Luân Chuyển Tối Giản
```
Gửi request bằng Key hiện tại
  │
  ├── Thành công ────────► Nhận kết quả bản dịch, hoàn tất chunk
  │
  └── Gặp lỗi HTTP 429 (Rate Limit)
        │
        ├── Còn key khác trong danh sách?
        │     ├── CÓ ──► Thử key kế tiếp một lần duy nhất
        │     └── KHÔNG (Tất cả key đều thất bại)
        │           │
        │           └── Báo lỗi rõ ràng: "Toàn bộ API Key đã hết lượt gọi tạm thời!"
        │               Dừng tiến trình và hiển thị nút [Gửi lại] cho người dùng
```

### 3.2. Nguyên Tắc Xử Lý Lỗi Tối Thiểu
* **Lỗi tạm thời của key (HTTP 429)**: Thử key kế tiếp trong danh sách một lần duy nhất.
* **Lỗi nội dung / prompt / model (HTTP 400, Invalid Argument)**: Dừng ngay lập tức, **tuyệt đối không retry vô hạn**.
* **Lỗi mạng (Connection Error) hoặc Timeout**: Báo lỗi mạng rõ ràng cho người dùng, dừng tiến trình và hiển thị nút **[Gửi lại]** để người dùng chủ động bấm khi mạng ổn định.
* **Không có cơ chế tự động cố gắng phục hồi toàn bộ quá trình**: Người dùng là người kiểm soát tối cao và quyết định khi nào gửi lại.

---

## 4. QUY TRÌNH CHIA CHUNK NHIỀU FILE & GHÉP NỐI CHÍNH XÁC

Hệ thống cho phép người dùng chọn cùng lúc nhiều file nguồn trong `sources/` (ví dụ: `ch01.md`, `ch02.txt`).

### 4.1. Cắt Chunk Kèm Metadata Đánh Số
Trước khi gửi đi, mỗi đoạn văn bản được gán thông tin nhận diện:
```python
{
    "file_index": 0,
    "filename": "ch01.md",
    "chunk_index": 1,          # Đánh số 0, 1, 2...
    "total_chunks": 4,         # Tổng số chunk của file này
    "char_count": 11450,       # Số ký tự thực tế
    "estimated_tokens": 2860,  # Token ước lượng (char_count // 4)
    "source_text": "..."
}
```

### 4.2. Ghép Nối Hoàn Chỉnh Khi Nhận Về
* Sau khi AI dịch xong lần lượt các chunk của một file, hệ thống sắp xếp các chunk theo đúng `chunk_index` (từ $0$ đến $N-1$).
* Nối lại bằng 2 dấu xuống dòng `\n\n` để giữ nguyên khoảng cách đoạn văn.
* Ghi trực tiếp ra file kết quả: `workspace/projects/{slug}/translated/{filename}`.

---

## 5. THƯ VIỆN PROMPT NHẸ (LIGHTWEIGHT PROMPT LIBRARY)

Cho phép người dùng toàn quyền kiểm soát chỉ thị AI:
1. **Nguồn Prompt đa dạng**:
   * Chọn prompt từ thư mục dùng chung của ứng dụng (`prompts/*.txt`).
   * Hoặc chọn prompt riêng của chính dự án (`workspace/projects/{slug}/assets/*.txt`). Giúp dự án mang theo toàn bộ chỉ thị khi copy/backup.
2. **Thao tác nhanh**: Xem nội dung, sửa trực tiếp, lưu prompt mới ngay trên giao diện.
3. **Prompt Stacking**: Chọn 1 Prompt Chính (ép chuẩn dịch thuật & bảo toàn Markdown) + Tick chọn thêm các Prompt Bổ Sung (xưng hô cổ trang, trau chuốt câu từ).

---

## 6. THIẾT KẾ GIAO DIỆN: 1 PHIÊN DỊCH TẠI 1 THỜI ĐIỂM (SINGLE-SESSION UI)

Giao diện tập trung 100% vào sự rõ ràng, phản hồi nhanh và loại bỏ hoàn toàn các bảng biểu quản lý rườm rà.

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ [LOGO] CONTENT TRANSLATOR                                    [Gemini: 3 Keys Ready]  [⚙️]   │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ 📁 Dự Án: [Truyen_Tien_Hiep ▼]   📜 Prompt: [default.txt ▼]   [+ Prompt bổ sung]            │
├──────────────────────────────────┬──────────────────────────────────────────────────────────┤
│ DANH SÁCH FILE NGUỒN             │ MÀN HÌNH SO SÁNH SONG NGỮ (DUAL-PANE EDITOR)            │
│ [X] ch01.md (12.4k ký tự)        ├────────────────────────────┬─────────────────────────────┤
│ [ ] ch02.md (15.1k ký tự)        │ VĂN BẢN GỐC (ch01.md)      │ BẢN DỊCH TIẾNG VIỆT         │
│                                  │                            │                             │
│ ℹ️ THÔNG TIN CHUNK ĐANG XỬ LÝ:   │ # Chương 1: Khởi đầu       │ # Chương 1: Khởi đầu        │
│ • Chunk: 1/3 (ch01.md)           │ Đêm đã về khuya...         │ Đêm đã về khuya...          │
│ • Số ký tự: 11,450 ký tự         │                            │                             │
│ • Token ước lượng: ~2,860 tokens │                            │                             │
├──────────────────────────────────┴────────────────────────────┴─────────────────────────────┤
│ BỘ NÚT ĐIỀU KHIỂN THAO TÁC TRỰC TIẾP:                                                       │
│ [▶ Bắt Đầu Dịch]   [📋 Sao Chép Kết Quả]   [💾 Lưu Vào File]   [❌ Xóa & Gửi Lại]   [🔄 Gửi Lại]│
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Các Tính Năng & Nút Thao Tác Trực Tiếp Trên UI:
1. **Đếm ký tự & Ước lượng Token**: Hiển thị rõ ràng số ký tự và số token ước tính của từng chunk và toàn bộ file.
2. **So sánh Song ngữ (Dual-Pane Sync-Scroll)**: Khung trái văn bản gốc, khung phải văn bản dịch tiếng Việt hiển thị streaming trực tiếp.
3. **Nút [Sao chép kết quả] (Copy)**: Copy nhanh toàn bộ bản dịch vào Clipboard.
4. **Nút [Lưu vào file] (Save)**: Lưu ngay bản dịch vào thư mục `translated/`.
5. **Nút [Xóa & Gửi lại] (Clear & Resend)**: Xóa trắng kết quả hiện tại và kích hoạt lại luồng gửi.
6. **Nút [Gửi lại] (Retry)**: Khi gặp lỗi mạng hoặc lỗi 429 hết key, nút này sáng lên để người dùng bấm thử lại khi đã sẵn sàng.
7. **Các nút xử lý nâng cao** (so sánh diff chi tiết, tìm kiếm & thay thế...): Được xếp lịch làm sau ở Phase 3 trở đi.
