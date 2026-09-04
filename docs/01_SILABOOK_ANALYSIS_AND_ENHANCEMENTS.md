# 01. PHÂN TÍCH GIẢI THUẬT SILABOOK & ĐỀ XUẤT TỐI ƯU VÀO DỰ ÁN MỚI
> **⚠️ TÀI LIỆU THAM KHẢO — NON-NORMATIVE (v2.3, 04/09/2026).**
> Chuẩn thực thi là `00_PROJECT_MANIFESTO.md` v2.3. Bảng "Định hướng Dự Án Mới" dưới đây (FastAPI/8 trang/adaptive-cooldown) đã bị thay thế: Phase 1 dùng CLI + `httpx` + 2 providers explicit, Phase 2 dùng `server.py` stdlib + 4 trang. Chỉ giữ lại giá trị của doc này là 4 giải thuật (SmartHardSplit, handoff, lọc thuật ngữ, sidebar thu gọn).
>
> **Tham chiếu**: Thư mục `docs/silaBooks/` (9 chuyên đề kỹ thuật)  
> **Mục tiêu**: Phân tích sâu sắc cấu trúc, giải thuật của silaBook, so sánh với Novel-Translator hiện tại, chắt lọc các giải thuật xuất sắc và đề xuất phương án tối ưu hóa cho hệ thống mới.

---

## 1. TỔNG QUAN VỀ SILABOOK & NHỮNG ĐIỂM SÁNG KỸ THUẬT

**silaBook** là ứng dụng dịch sách hoạt động 100% Client-side trên nền Angular 21, lưu trữ trên IndexedDB và kết nối trực tiếp với Google Gemini API. Mặc dù có những hạn chế về mặt dịch hàng loạt và quản lý key so với backend Python, silaBook sở hữu nhiều giải thuật toán học và logic xử lý ngôn ngữ cực kỳ thông minh:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   CÁC ĐIỂM SÁNG KỸ THUẬT CỦA SILABOOK                            │
├──────────────────────────────────┬───────────────────────────────────────────────┤
│ 1. Giải thuật đếm từ O(N)        │ Duyệt mã ký tự, không phân mảnh RAM.          │
│ 2. Thuật toán smartHardSplit     │ Cắt thông minh theo dải 20% - 80% quanh mốc   │
│                                  │ trung tâm 50% theo thứ tự ưu tiên dấu ngắt.   │
│ 3. Lọc thuật ngữ động            │ Dùng model nhẹ (Flash Lite) trích xuất từ vựng│
│    (filterGlossary)              │ thực tế trước khi dịch, tránh loãng prompt.   │
│ 4. Bối cảnh nối tiếp             │ Tóm tắt chương trước nhúng vào chương sau     │
│    (previous_chunk_handoff)      │ trong thẻ XML riêng, giữ mạch truyện liền lạc. │
│ 5. Chuẩn hóa đại từ xưng hô      │ Bảng ánh xạ quan hệ nhân vật giúp lời thoại   │
│    (Pronoun Management)          │ tiếng Việt chuẩn vai vế, tự nhiên.           │
│ 6. Translation Versioning        │ Lưu 3 snapshot gần nhất kèm cấu hình dịch.    │
└──────────────────────────────────┴───────────────────────────────────────────────┘
```

---

## 2. PHÂN TÍCH CHI TIẾT CÁC GIẢI THUẬT CỐT LÕI CỦA SILABOOK

### 2.1. Giải Thuật Đếm Từ Chuẩn Hóa Hiệu Năng Cao (`countWords`)
* **File tham chiếu**: `docs/silaBooks/04-giai-thuat-chia-chuong-splitter.md`
* **Nguyên lý**: 
  * Cách thông thường `text.split(/\s+/)` tạo ra hàng trăm ngàn mảng con trong RAM, gây nghẽn Garbage Collection khi xử lý sách hàng triệu từ.
  * silaBook duyệt chuỗi tuần tự từng ký tự với bộ nhớ $O(1)$:
    ```typescript
    // Kiểm tra ký tự khoảng trắng ASCII và Unicode (NBSP, Em Space, Ideographic Space)
    const isWhitespace = c <= 32 || c === 160 || (c >= 8192 && c <= 8202) || c === 12288;
    ```
* **Ứng dụng cho dự án mới**: Cài đặt phiên bản Python $O(1)$ cực nhanh để kiểm soát chính xác dung lượng chunk mà không tốn tài nguyên.

### 2.2. Thuật Toán Cắt Thông Minh Đệ Quy (`smartHardSplit`)
* **Vấn đề**: Khi một chương hoặc đoạn văn vượt quá giới hạn ký tự tối đa của một chunk, nếu cắt cứng sẽ làm đứt đôi câu văn hoặc ngắt giữa chừng một đoạn văn.
* **Giải thuật của silaBook**:
  1. Giới hạn dải tìm kiếm từ **20% đến 80%** chiều dài văn bản (`minPos = len * 0.2`, `maxPos = len * 0.8`).
  2. Đặt mục tiêu lý tưởng là vị trí chính giữa **50%** (`targetPos = len * 0.5`) để chia đôi đều văn bản, không bị lệch (tránh tình trạng một bên 95%, một bên 5%).
  3. Quét tìm điểm cắt theo thứ tự ưu tiên nghiêm ngặt:
     * **Ưu tiên 1**: Dấu xuống dòng kép `\n\n` (ngắt giữa 2 đoạn văn — tối ưu nhất cho văn bản/Markdown).
     * **Ưu tiên 2**: Dấu xuống dòng đơn `\n`.
     * **Ưu tiên 3**: Dấu kết thúc câu kèm khoảng trắng (`. `, `! `, `? `, `。`, `！`, `？`).
     * **Ưu tiên 4**: Khoảng trắng thông thường ` `.
     * **Fallback**: Cắt tại đúng vị trí 50% nếu không tìm thấy ký tự ngắt nào.
  4. Sau khi cắt, đệ quy áp dụng `smartHardSplit` cho cả 2 nửa nếu chúng vẫn lớn hơn `maxWords`.
* **Đánh giá**: Đây là thuật toán phân đoạn xuất sắc nhất, giải quyết triệt để lỗi "cắt đứt câu" mà vẫn giữ nguyên cấu trúc định dạng dòng.

### 2.3. Kỹ Thuật Lọc Thuật Ngữ Động (`filterGlossary`)
* **File tham chiếu**: `docs/silaBooks/06-logic-dich-thuat-va-prompt-engineering.md`
* **Vấn đề**: Bảng thuật ngữ của một cuốn tiểu thuyết có thể có 500 - 1.000 từ. Nếu nhồi toàn bộ vào prompt của mỗi chunk:
  * Lãng phí hàng ngàn token vô ích cho mỗi lượt gọi.
  * Làm mô hình AI bị phân tâm (Over-fitting / Attention Distraction) bởi các từ vựng không hề xuất hiện trong đoạn đó.
* **Giải thuật**:
  * Nếu bảng thuật ngữ $>100$ từ: Gọi một lượt API siêu nhanh (dùng model rẻ/nhẹ như Gemini Flash Lite) trích xuất chỉ những từ có mặt trong đoạn text hiện tại qua JSON Schema.
  * Chỉ đưa danh sách rút gọn này vào prompt dịch chính.
* **Ứng dụng cho dự án mới**: Tích hợp cơ chế lọc thuật ngữ nhanh trước khi gửi chunk, giúp tiết kiệm token và tăng độ chuẩn xác của AI.

### 2.4. Kỹ Thuật Bối Cảnh Nối Tiếp (`previous_chunk_handoff`)
* **Vấn đề**: Các chương dịch độc lập thường bị đứt gãy mạch truyện, nhân vật bị đổi giọng hoặc AI không hiểu sự kiện trước đó dẫn đến phản ứng kỳ lạ.
* **Giải pháp**:
  * Sau khi dịch xong chương $N$, AI tự động tóm tắt chương đó thành 1 đoạn ngắn ($\le 10\%$ độ dài).
  * Khi dịch chương $N+1$, đoạn tóm tắt này được nạp vào thẻ:
    ```xml
    <previous_chunk_handoff>
    **Tóm tắt bối cảnh từ phần trước:**
    [Nội dung tóm tắt]
    *LƯU Ý: Đây là thông tin bối cảnh... TUYỆT ĐỐI KHÔNG lặp lại tóm tắt này vào bản dịch.*
    </previous_chunk_handoff>
    ```
* **Ứng dụng cho dự án mới**: Kế thừa trực tiếp cơ chế này vào biến `{{previous_summary}}` trong prompt template của dự án mới.

---

## 3. MA TRẬN SO SÁNH: SILABOOK VS. NOVEL-TRANSLATOR HIỆN TẠI

| Tiêu chí kỹ thuật | **silaBook** | **Novel-Translator (Hiện tại)** | **Định hướng Dự Án Mới (Tối ưu nhất)** |
| :--- | :--- | :--- | :--- |
| **Môi trường chạy** | 100% Client-side (Angular) | Fullstack (Python Flask + JS) | **Python 3.12 (FastAPI) + React SPA** |
| **Quản lý API Key** | Nhập 1 key duy nhất, lưu mã hóa AES-GCM trong IndexedDB | Quản lý đa key, rotation, adaptive cooldown khi gặp 429 | **Kế thừa Novel-Translator**: Multi-Key Pool, xoay vòng tự động, tối ưu token miễn phí |
| **Hỗ trợ Providers** | Chỉ hỗ trợ Google Gemini | Hỗ trợ Gemini + OpenAI + Local Ollama | **Kế thừa Novel-Translator**: Gemini + OpenAI-compatible + Ollama |
| **Giải thuật Chunking** | `smartHardSplit` (Dải 20-80%, ưu tiên `\n\n`) | Heuristic chấm điểm Delimiters, dồn câu | **Hợp nhất**: Dùng `smartHardSplit` của silaBook vì bảo toàn cấu trúc dòng tuyệt đối |
| **Bảo toàn định dạng** | Giữ tương đối tốt cấu trúc Markdown | Regex can thiệp thô bạo (xóa MD, đổi nháy kép) | **Bảo toàn 100% định dạng** qua System Prompt Guard & Chunker trung lập |
| **Quản lý Ngữ cảnh** | `previous_chunk_handoff` tự động tóm tắt chương trước | Rolling memory đơn giản | **Kế thừa silaBook**: Tự động sinh tóm tắt bối cảnh nối tiếp |
| **Thuật ngữ & Xưng hô** | `filterGlossary` động + Quản lý Đại từ xưng hô | Đọc file text glossary tĩnh | **Hợp nhất**: Glossary dạng `.txt` đơn giản, tự động lọc thuật ngữ có trong chunk |
| **Tổ chức Giao diện** | Single flow wizard (từng bước) | Dashboard nhiều tab cồng kềnh (>90KB JS) | **8 Trang Riêng Biệt (Dedicated Pages)**, Sidebar thu gọn được |
| **Xử lý File & EPUB** | Tự unpack epub/pdf client-side | EPUB converter DOM/XML phức tạp | **Công cụ EPUB độc lập**: Chỉ nhận text/md/html, convert 2 chiều |

---

## 4. CÁC ĐỀ XUẤT BỔ SUNG & TỐI ƯU VÀO DỰ ÁN MỚI

Từ việc nghiên cứu silaBook, chúng tôi đề xuất 4 cải tiến then chốt cho hệ thống mới:

### Đề xuất 1: Triển khai thuật toán `SmartHardSplit` chuẩn xác
Thay thế toàn bộ logic cắt text cũ bằng thuật toán tìm điểm ngắt ưu tiên (`\n\n` $\to$ `\n` $\to$ kết thúc câu) trong dải 20% - 80% quanh mốc 50%. Điều này đảm bảo:
* Không bao giờ cắt đứt đôi câu văn hoặc đứt dòng thơ, câu thoại.
* Giữ nguyên 100% các khối Markdown (heading, list, code block).

### Đề xuất 2: Tích hợp cơ chế Context Handoff (`previous_chunk_handoff`)
* Khi người dùng dịch một chuỗi các chương liên tiếp:
  * Sau khi hoàn tất chương 1, sinh một đoạn tóm tắt 3-5 câu về cốt truyện và tâm lý nhân vật.
  * Tự động truyền đoạn tóm tắt này vào prompt của chương 2 để giữ mạch cảm xúc và phong cách xưng hô liền lạc xuyên suốt toàn bộ cuốn sách.

### Đề xuất 3: Cơ chế lọc thuật ngữ nhanh theo Chunk
* Thay vì nhồi nhét toàn bộ file `glossary.txt` vào prompt làm tốn token:
  * Trước khi gửi chunk, hệ thống quét nhanh bằng Hash-set trong Python ($O(N)$) để chỉ lấy ra các cặp từ khóa thực sự xuất hiện trong chunk hiện tại.
  * Đính kèm danh sách rút gọn này vào biến `{{glossary_terms}}`.

### Đề xuất 4: Giao diện với Sidebar có thể thu gọn (Collapsible Sidebar)
* Học tập từ trải nghiệm đọc sách và biên dịch song ngữ:
  * Màn hình Dual-Pane cần tối đa diện tích bề ngang để hiển thị đầy đủ văn bản gốc và văn bản dịch mà không bị quấn dòng (wrap) quá nhiều.
  * Thanh Sidebar điều hướng 8 trang có thể **thu nhỏ thành dạng icon-only (từ 260px xuống 64px)** hoặc ẩn hoàn toàn chỉ bằng một click chuột, giải phóng toàn bộ không gian cho màn hình dịch thuật.
