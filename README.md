# Công cụ Dịch Thuật Tiểu Thuyết v3.0

Công cụ này sử dụng AI của Google (Gemini) để dịch thuật tiểu thuyết từ tiếng Trung hoặc tiếng Anh sang tiếng Việt. 

**Phiên bản hiện tại (v3.0)** sử dụng kiến trúc plugin hiện đại với khả năng mở rộng cao, đồng thời **vẫn bảo toàn đầy đủ các tính năng v2.7** (workflow legacy) để đảm bảo tương thích ngược và ổn định.

## 🎯 Hai Chế Độ Chạy

### 1. Plugin Architecture (v3.0) - Khuyến nghị
- Kiến trúc plugin hiện đại, dễ mở rộng
- ServiceBus và EventBus cho giao tiếp giữa các thành phần
- Chạy: `python main.py`

### 2. Legacy Workflow (v2.7) - Đã được kiểm chứng
- Workflow hoàn chỉnh với tất cả tính năng đã ổn định
- Context chaining, cache nâng cao, auto-retry, verification mode
- Sử dụng thông qua module `src/` hoặc `main_legacy.py`

## Tính năng nổi bật

-   **Xử lý đầu vào linh hoạt**:
    -   **Dịch file lẻ**: Kéo một file truyện (`.txt`, `.docx`...) vào thư mục `input` để chương trình tự động đọc và chia nhỏ.
    -   **Dịch nguyên thư mục**: Kéo một thư mục chứa các file chương (`001.txt`, `002.txt`...) vào `input`, chương trình sẽ coi đó là một cuốn truyện và dịch lần lượt.

-   **Thuật toán "Chia file Thông minh"**:
    -   **Nhận diện chương gốc**: Tự động nhận diện các tiêu đề chương/hồi trong văn bản gốc và bọc chúng trong định dạng `**...**` để AI hiểu và giữ lại.
    -   **Tối ưu hóa chunk**: Khi dịch một thư mục truyện, các file chương có dung lượng nhỏ hơn `CHUNK_SIZE` sẽ được coi là một chunk duy nhất để tiết kiệm tài nguyên và giữ ngữ cảnh tốt hơn. Chỉ các file lớn hơn mới bị chia nhỏ.

-   **Thuật toán "Sửa lỗi Lặp lại" (Iterative Correction)**:
    -   Đây là tính năng cốt lõi để đảm bảo chất lượng. Sau khi dịch một chunk, chương trình sẽ tự động quét lại bản dịch.
    -   Nếu phát hiện còn sót ký tự tiếng Trung, nó sẽ không chuyển sang chunk tiếp theo. Thay vào đó, nó sẽ gửi lại chính bản dịch lỗi đó cho AI và ra lệnh: "Hãy tìm và dịch nốt các ký tự còn sót này".
    -   Quá trình này tự động lặp lại cho đến khi chunk hoàn toàn "sạch" ký tự Trung, giúp diệt trừ gần như 100% lỗi sót.

-   **Quản lý API Key thông minh**:
    -   **Đa luồng**: Số luồng dịch được tự động điều chỉnh bằng đúng số lượng API key bạn cung cấp, tối ưu hóa tốc độ.
    -   **Tự động xử lý Quota**: Khi một API key hết quota, chương trình sẽ tự động phát hiện, tạm vô hiệu hóa key đó và chuyển sang key tiếp theo mà không làm gián đoạn quá trình.

-   **Độ tin cậy cao**:
    -   **Tính năng Resume**: Mọi tiến trình đều được lưu lại trong thư mục `progress`. Nếu chương trình bị dừng đột ngột (mất mạng, mất điện...), bạn chỉ cần chạy lại và chọn "tiếp tục" (y), nó sẽ dịch nốt phần còn dang dở.
    -   **Hệ thống Logging**: Mọi hoạt động, cảnh báo, lỗi đều được ghi lại trong một file log có định dạng `YYYY-MM-DD_HH-MM_translator.log` trong thư mục `progress`, giúp dễ dàng chẩn đoán sự cố.

-   **Cấu hình Toàn diện**:
    -   **`config.ini`**: Cho phép tùy chỉnh mọi thứ từ model AI, kích thước chunk, độ trễ giữa các request, cho đến số lần AI tự sửa lỗi.
    -   **`prompts.ini`**: Toàn bộ "bộ não" của AI nằm ở đây. Bạn có thể tùy chỉnh văn phong, quy tắc dịch thuật mà không cần đụng đến một dòng code nào.

-   **Đầu ra có cấu trúc**:
    -   Kết quả được lưu vào thư mục `output/[tên truyện]`.
    -   Tự động tạo các file `.txt` riêng cho từng chương và một file `_full.txt` tổng hợp toàn bộ truyện.

## Hướng dẫn cài đặt và sử dụng

### 1. Yêu cầu

-   Python 3.8 trở lên.

### 2. Cài đặt

Mở terminal (hoặc Command Prompt) trong thư mục dự án và chạy lệnh:
```bash
pip install -r requirements.txt
```

### 3. Cấu hình

a. **File `config/API.txt`**:
   - Sao chép `config/API.txt.example` thành `config/API.txt`
   - Mở file `config/API.txt` và thêm các API key của bạn (mỗi key một dòng)
   - Lấy API key từ: https://aistudio.google.com/app/apikey

b. **File `config.ini`**:
   - File cấu hình chính đã được thiết lập sẵn với các giá trị tối ưu
   - Bạn có thể tinh chỉnh các thông số nếu cần (model, chunk size, temperature, etc.)

### 4. Sử dụng

a. **Chuẩn bị file nguồn**:
   - **Cách 1 (File lẻ):** Đặt một file truyện (ví dụ: `truyen_goc.txt`) vào thư mục `input`.
   - **Cách 2 (Thư mục truyện):** Đặt một thư mục (ví dụ: `[Tên Truyện]`) chứa các file chương (`001.txt`, `002.txt`...) vào thư mục `input`.

b. **Chạy chương trình**:
   Mở terminal và chạy lệnh:
   ```bash
   python main.py
   ```

c. **Theo dõi và nhận kết quả**:
   - Theo dõi tiến trình dịch trên màn hình.
   - Kết quả sẽ nằm trong thư mục `output/[tên truyện]`.

---

## 🚀 Tính năng Legacy (v2.7) đã được tích hợp

Tất cả các tính năng nâng cao từ v2.7 đã được tích hợp hoàn toàn vào v3.0:

### Core Features
- ✅ **Context Chaining**: Nối ngữ cảnh giữa các chunk để dịch liền mạch
- ✅ **Smart Chunking**: Thuật toán cắt văn bản thông minh theo chương và ngữ cảnh
- ✅ **Auto-retry**: Tự động phát hiện và dịch lại chunks có lỗi
- ✅ **Verification Mode**: Kiểm tra bản dịch cũ, chỉ dịch lại chunks có vấn đề
- ✅ **Text Normalization**: Chuẩn hóa dấu câu, quotes, brackets sau khi dịch

### Advanced Cache System
- ✅ **Signature-based Cache Keys**: Cache key bao gồm model, temperature, prompt hash, context
- ✅ **GeminiProjectFileManager**: Upload nguồn dự án một lần, tái sử dụng qua file_uri
- ✅ **Smart Cache Invalidation**: Tự động xóa cache khi thay đổi cấu hình

### Translation Guides
- ✅ **Style Profiles**: Định nghĩa văn phong, thể loại, tone (`prompts/instructions/style_profile.json`)
- ✅ **Glossary**: Bảng thuật ngữ chuẩn (`prompts/instructions/glossary.csv`)
- ✅ **Character Relations**: Ma trận xưng hô nhân vật (`prompts/instructions/character_relations.csv`)

### Monitoring & Statistics
- ✅ **Health Monitoring**: Theo dõi tiến độ, phát hiện treo
- ✅ **Detailed Statistics**: Thống kê từ, ký tự, token, API quota
- ✅ **Emergency Stop**: Cơ chế dừng khẩn cấp an toàn

### Utilities
- ✅ **Content Analysis Tool**: Phân tích nội dung để trích xuất style, glossary, character relations (`utils/content-analysis/`)
- ✅ **EPUB Converter**: Chuyển đổi EPUB ↔ Text/Markdown (đã tích hợp trong plugin)

### Chinese Detection
- ✅ **Extended Unicode**: Phát hiện CJK Ideographs, Symbols, Punctuation, Fullwidth forms
- ✅ **File/Chunk Scanning**: Quét file và chunk tìm ký tự tiếng Trung

---

## 📚 Tài liệu thêm

- [CHANGELOG.md](CHANGELOG.md): Lịch sử thay đổi đầy đủ từ v1.0 → v3.0
- [docs/README.md](docs/README.md): Tài liệu chi tiết về kiến trúc plugin v3.0
- [docs/TODO.md](docs/TODO.md): Kế hoạch phát triển

## 📄 License

MIT License - Xem file LICENSE để biết chi tiết.