# 📖 Hướng Dẫn Sử Dụng Content Translator

Chào mừng bạn đến với hệ thống dịch thuật tiểu thuyết chuyên nghiệp sử dụng sức mạnh của Gemini AI.

## 1. Cài Đặt Ban Đầu

### Yêu cầu hệ thống
- Python 3.10+
- Bộ công cụ `uv` (khuyến nghị) hoặc `pip`
- API Keys từ Google AI Studio (Gemini)

### Các bước cài đặt
1. Giải nén/Clone mã nguồn.
2. Cài đặt các thư viện cần thiết:
   ```bash
   uv sync
   # Hoặc dùng pip:
   pip install -r requirements.txt
   ```
3. Cấu hình API: Chạy ứng dụng lần đầu → tự động migration sang `config/providers.json`. Hoặc cấu hình qua tab **Cấu hình** trên WebUI.
   ```bash
   # Cấu hình thủ công: tạo config/providers.json (xem mẫu trong code)
   # Hoặc cấu hình qua giao diện WebUI
   ```


### ☁️ Hỗ trợ Cloudflare AI Gateway & Workers AI
Khi bạn sử dụng **Cloudflare AI Gateway** (Base URL: `https://gateway.ai.cloudflare.com/v1/.../compat`), hệ thống sẽ tự động nhận diện và kích hoạt bộ lọc chuyên dụng:
- Chỉ hiển thị danh sách các model của **Cloudflare Workers AI** (các model có định dạng `@cf/author/model`).
- Có ô tìm kiếm từ khóa và bộ lọc "Model miễn phí (free)".
- Tính năng này giúp bạn dễ dàng chọn đúng model và tránh chọn nhầm các model ngoại lai từ OpenRouter hay OpenAI.

---

## 2. Các Chế Độ Sử Dụng

### 🖥️ Chế độ Giao diện Web (WebUI)
Đây là cách dễ nhất để sử dụng cho người dùng cuối.
```bash
python main.py
# Hoặc chỉ định port:
python main.py --port 7860
```
Sau đó truy cập địa chỉ `http://localhost:7860` trên trình duyệt. Tại đây bạn có thể:
- Quản lý các dự án dịch thuật (Project-based Workspace).
- Xem tiến độ dịch thời gian thực (SSE Streaming).
- Quản lý Thư viện Prompt và Chỉ dẫn tùy chỉnh cho từng dự án.
- Sử dụng Translation Memory tự động ghi nhớ bản dịch.
- Chạy EPUB Converter và OCR trực tiếp từ giao diện.

### ⌨️ Chế độ Dòng lệnh (CLI)
Dành cho người dùng nâng cao hoặc muốn tự động hóa (Automation).
```bash
python cli.py translate -i input/novel.txt -o output/
```
Các tham số quan trọng:
- `-i`: Đường dẫn file hoặc thư mục đầu vào.
- `-o`: Thư mục chứa kết quả dịch.
- `--model`: Chọn model Gemini (mặc định: gemini-3-flash-preview).
- `--chunk-size`: Kích thước mỗi đoạn dịch (mặc định: 22000 ký tự).

---

## 3. Quản Lý Dự Án (Project Workspace)

Mỗi dự án dịch thuật được tổ chức riêng biệt trong `workspace/projects/<slug>/` với cấu trúc:
```
my-novel/
├── sources/           # File nguồn cần dịch (.txt)
├── translated/        # File đã dịch xong
├── prompt/            # Prompt riêng cho dự án (nếu có)
├── assets/            # Glossary, Style guide, Relationship, Summary
│   └── translation_memory/  # TM riêng dự án
└── project.json       # Metadata dự án
```

---

## 4. Các Tính Năng Nâng Cao

### 📚 Từ điển Thuật ngữ (Glossary)
Để đảm bảo tên nhân vật và chiêu thức nhất quán:
- Đặt file `glossary.txt` vào thư mục `assets/` của dự án.
- Hệ thống sẽ tự động nhúng các thuật ngữ liên quan vào prompt khi dịch.

### 🧠 Bộ nhớ Dịch thuật (Translation Memory)
Hệ thống tự động ghi nhớ các câu đã dịch. Nếu gặp lại câu tương tự ≥85%, hệ thống sẽ gợi ý hoặc tự động áp dụng để tiết kiệm API và đảm bảo tính nhất quán.

### 📚 Thư viện Prompt (Prompt Library)
Tạo và quản lý các bộ prompt mẫu. Mỗi bộ prompt lưu tại `workspace/prompts/<slug>/`. Bộ `default` là mặc định hệ thống, không thể xóa.

### ⚙️ Cấu hình Tối ưu (config/app.ini)
Bạn có thể tinh chỉnh các thông số kỹ thuật:
- `REQUEST_DELAY`: Thời gian nghỉ giữa các lần gọi API (tránh bị block).
- `MAX_REFINEMENT_ATTEMPTS`: Số lần AI tự sửa lỗi nếu phát hiện còn ký tự Trung.
- `CONTEXT_CHAR_COUNT`: Số ký tự đoạn trước được gửi kèm đoạn sau để AI nắm bắt ngữ cảnh.

---

## 5. Các Công Cụ Hỗ Trợ (Utilities)

### 📄 EPUB Converter
Hệ thống tích hợp sẵn bộ chuyển đổi dành cho sách điện tử:
- **EPUB → Text**: Tách nội dung từ file sách để bắt đầu dịch.
- **Text → EPUB**: Đóng gói lại thành file sách hoàn chỉnh sau khi dịch xong, bảo toàn Metadata và cấu trúc chương hồi.

#### Quy ước khi biên tập EPUB sau đóng gói (v8.19.0+)

EPUB xuất ra là bản **tối thiểu, đúng cấu trúc OEBPS** để mở và biên tập tiếp bằng Sigil/Calibre:

```text
file.epub
├── mimetype
├── META-INF/container.xml
└── OEBPS/
    ├── content.opf        # metadata tối thiểu: tên sách, tác giả, mô tả
    ├── Text/              # các chương (.xhtml), giữ nguyên cấu trúc thư mục con
    ├── Images/            # rỗng — tự đưa ảnh vào khi biên tập
    ├── Styles/            # rỗng — tự đưa stylesheet vào (quy ước styles.css)
    └── Fonts/             # rỗng — tự đưa font vào
```

**Lưu ý quan trọng:**

- **Ảnh**: công cụ chỉ *bảo toàn đường dẫn và vị trí* ảnh (`![chú thích](images/01.jpg)` trong Markdown ↔ `<img src="images/01.jpg"/>` trong chương). Ảnh **không được đóng gói** sẵn — khi biên tập, copy ảnh vào đúng đường dẫn tương đối mà `src` đang trỏ tới (Sigil/Calibre sẽ tự nhận và đưa vào manifest).
- **Link giữa các chương**: giữ nguyên đường dẫn tương đối, chỉ đổi đuôi thành `.xhtml`. Kiểm tra lại khi biên tập nếu cần.
- **Chú thích cuối trang (footnote)**: viết trong Markdown bằng cú pháp chuẩn `[^1]` và `[^1]: nội dung chú thích`. Converter render thành danh sách chú thích cuối chương có link hai chiều. Khi biên tập, kiểm tra lại nếu muốn tách thành footnote chuẩn EPUB (`epub:type`).
- **Không hỗ trợ** `~~gạch ngang~~` — dùng thẻ HTML `<del>` trực tiếp nếu cần.
- **Gạch chân** `<u>...</u>` được giữ nguyên dạng HTML inline — hỗ trợ phụ thuộc reader, kiểm tra lúc biên tập.
- **Stylesheet**: mỗi chương đã có sẵn link `../Styles/styles.css`; chỉ cần đặt file vào `Styles/styles.css` khi biên tập là tất cả chương nhận style.
- **Nav/titlepage/cover**: không được tạo sẵn — Sigil/Calibre tự sinh khi import.
- **Nếu batch báo "partial"**: một số file lỗi — xem log để biết file nào, sửa và chạy lại chỉ những file đó.

### 🖼️ OCR Engine (Plugin)
Chuyên dùng cho các tài liệu dạng ảnh hoặc PDF quét. OCR Engine có kiến trúc mô-đun lớp (Layered Architecture):
- **Cấu trúc**: Logic được tách bạch thành các module `config`, `image`, `pdf`, `tables`, `formats`, và `ai_processor` trong `plugins/ocr/modules/`.
- **AI Post-Processing**: Tự động làm sạch văn bản (AI Cleanup) và sửa lỗi chính tả (AI Spellcheck) sau khi quét.
- **Tính tương thích**: File `ocr_engine.py` đóng vai trò Facade, đảm bảo các script cũ vẫn hoạt động.

## 5a. Quản lý Plugin (v7.8.0+)

### 🔌 Plugin Management
- **Quản lý Plugin**: Tab **Cấu hình** → cuối trang → khối **Quản lý Plugin**
- **Bật/Tắt**: Tool plugins (eBook Kit, OCR Toolbox) bật/tắt bằng toggle switch
- **Core plugins** (Translation, Spellcheck) mặc định bật, không thể tắt

### 📚 eBook Kit (Workspace Tab)
Khi plugin eBook Kit được bật, workspace hiển thị tab **eBook Kit**:
- **EPUB → Text**: Trích xuất nội dung từ EPUB, hỗ trợ Single/Multi/Both mode
- **Text → EPUB**: Đóng gói lại thành EPUB, giữ cấu trúc chương hồi

### 🖼️ OCR Toolbox (Workspace Tab)
Khi plugin OCR Toolbox được bật, workspace hiển thị tab **OCR Toolbox**:
- Nhận dạng ký tự từ PDF/Ảnh bằng Tesseract + AI Cleanup + Spellcheck
- Hỗ trợ chọn trang PDF, bỏ qua Cleanup/Spellcheck riêng lẻ

---

### 🛠️ Công cụ Biên tập & Soát lỗi (v7.7.0+)
Giao diện Biên tập hợp nhất (Editor + Spellcheck) với sidebar 3 mini-tab:
- **Nội dung nguồn**: File gốc cần dịch hoặc soát lỗi. Row actions: Dịch, Chuyển Markdown (HTML/XHTML), Soát lỗi AI, Đổi tên, Xóa.
- **📝 Tiền xử lý HTML/XHTML → Markdown**: Chuyển đổi file `.html`, `.htm`, `.xhtml` → Markdown sạch bằng nút "Chuyển Markdown".
- **Bản dịch**: File đã dịch xong. Click để xem song song nguồn + bản dịch.
- **Soát chính tả**: File đã AI soát lỗi xong.
- **↩️ Wrap**: Ngắt dòng tự động, không cần cuộn ngang.
- **📊 Diff (So sánh)**: Xem khác biệt giữa nguồn và đích trong modal.
- **🧩 Ghép tập tin (Smart Merge)**: Gộp file đã dịch thành một, dùng Natural Sort.

#### 🔍 Tìm kiếm & Thay thế Regex & Quy trình Chạy thử (v8.20.0+)

Mở modal Tìm kiếm & Thay thế bằng nút icon 🔍 trên thanh công cụ của Editor.

##### 1. Quy chuẩn ECMAScript/Python Portable Regex v1
Hệ thống sử dụng profile Regex di động đồng bộ giữa JavaScript (Editor) và Python (Backend):
- **Cú pháp được hỗ trợ**: Nhóm `(...)`, `(?:...)`, lựa chọn `a|b`, lặp `*`, `+`, `?`, `{m,n}`, character class `[abc]`, `[^abc]`, neo `^`, `$`, `.`, `\n`, `\t`.
- **Cờ (Flags)**: Hỗ trợ `i` (bỏ qua hoa/thường) và `m` (multiline). Ký tự xuống dòng Windows CRLF (`\r\n`) được tự động chuẩn hóa về LF (`\n`).
- **Thay thế tham chiếu (Back-reference)**: Khi thay thế pattern có nhóm capture, nhập `$1`, `$2` trực tiếp trong ô "Từ thay thế". Backend Python sẽ tự động chuyển đổi sang `\g<1>`, `\g<2>`.
- **Lưu ý CJK/Tiếng Việt**: Tránh dùng `\w`, `\d`, `\b` cho logic phụ thuộc tiếng Việt hoặc CJK; nên dùng character class cụ thể (ví dụ: `[0-9]`, `[a-zA-ZÀ-ỹ]`).

##### 2. Quy trình Chạy thử (Dry-Run Preview) an toàn cho "Tất cả tập tin"
Thay thế trên toàn bộ tập tin dự án là thao tác không thể hoàn tác. Để bảo vệ dữ liệu dự án:
1. **Chọn phạm vi**: Chuyển ô "Áp dụng" sang **Tất cả tập tin**. Nút **Chạy thử** màu xanh sẽ xuất hiện.
2. **Bấm Chạy thử**: Hệ thống tự động lưu file hiện tại (nếu đang bị chỉnh sửa), sau đó quét đếm số lượt xuất hiện và số tập tin bị ảnh hưởng mà **không thực hiện ghi file**.
3. **Thay tất cả**: Sau khi preview hiển thị số kết quả dự kiến, bấm **Thay tất cả** để tiến hành thay thế thực sự.
4. **Cơ chế bảo vệ (Guard)**: Nếu bạn thay đổi từ khóa, chế độ tìm kiếm, phạm vi hoặc chỉnh sửa file trong editor, kết quả preview sẽ bị hủy và hệ thống yêu cầu bạn bấm **Chạy thử** lại trước khi cho phép áp dụng.

---

## 6. Quản Lý Chỉ Dẫn (Prompt Management)

### Hai khu vực quản lý prompt riêng biệt

#### A. Thư viện Chỉ dẫn AI (cấp hệ thống)
- Tab **Chỉ dẫn AI** → bên trái danh sách bộ prompt, bên phải editor.
- Bộ `default` là mặc định hệ thống, có thể sửa nội dung nhưng **không thể xóa**.
- **Tạo bộ mới**: Nút "+ Thêm bộ" → modal nhập Tên + Mô tả → tự động tạo thư mục `workspace/prompts/<slug>/` với 5 file prompt rỗng.
- **Editor**: Click bộ prompt → load nội dung vào 5 tab (Dịch thuật, Tóm tắt, Quan hệ, Thuật ngữ, Chính tả). Chỉnh sửa và bấm **Lưu**.
- **Thông tin bộ prompt**: Nút "Thông tin" → modal sửa Tên + Mô tả.
- **Xóa bộ prompt**: Nút "Xóa bộ" → confirm → xóa thư mục (ẩn với bộ `default`).
- Vị trí lưu: `workspace/prompts/<slug>/` (mỗi slug là một thư mục chứa `meta.json` + 5 file `.txt`).

#### B. Chỉ dẫn của Dự án (Project Override)
- Trong workspace dự án, tab **Chỉ dẫn**.
- 5 tab prompt (Dịch thuật, Tóm tắt, Quan hệ, Thuật ngữ, Chính tả) — giao diện tab-style.
- **📥 Nhập từ Thư viện**: Chọn bộ prompt nguồn từ dropdown + tab đang mở → bấm "Nhập Prompt" → nội dung được copy vào textarea (chưa lưu, có dirty flag).
- **💾 Lưu**: Lưu nội dung prompt hiện tại vào `workspace/projects/<slug>/prompt/`. Hệ thống ưu tiên prompt dự án trước; nếu file prompt rỗng → dùng prompt mặc định từ bộ `default`.
- **Cơ chế fallback**: Không cần nút "Reset" hay "Xóa riêng". Chỉ cần lưu textarea trống → file prompt rỗng → hệ thống tự dùng mặc định.

---

## 7. Giải Quyết Sự Cố (Troubleshooting)

- **Lỗi 429 (Rate Limit):** Hệ thống tự động chờ hoặc chuyển API Key nhờ `AdaptiveRateLimiter`.
- **Bản dịch bị cắt dòng:** Kiểm tra `chunk_size` hoặc dùng model mạnh hơn.
- **Lỗi Encoding:** File đầu vào phải UTF-8.
- **Port bị chiếm:** Dùng `python main.py --port 8080`.

### A. Tác vụ Dịch File Nhiều Chunk Bị Treo hoặc Kẹt Giữa Chừng (Stalled/Hang Chunk)

#### 1. Nguyên nhân & Bản chất hiện tượng
- **Thời gian xử lý chunk lớn**: Khi dịch file văn bản dài được chia thành các chunk lớn (15.000 – 20.000 ký tự/chunk), các mô hình AI có cơ chế suy luận chuyên sâu (*Thinking / Reasoning* như Gemini 2.5/3.0, Step-3.7-flash, DeepSeek R1, v.v.) thường mất từ **5 đến 10 phút** cho mỗi chunk.
- **Nguyên tắc Ghép File (Verification Gate)**: Để bảo đảm bản dịch hoàn chỉnh và không bị thiếu sót nội dung, hệ thống **bắt buộc phải nhận đủ 100% tất cả các chunk** mới tiến hành ghép file (assemble) và ghi ra thư mục `translated/`. Nếu một file có 3 chunk và mới hoàn thành 2/3 chunk thì hệ thống sẽ **chưa ghép file**.
- **Kẹt mạng hoặc nghẽn Socket từ nhà cung cấp API**: Trong một số trường hợp, máy chủ AI của nhà cung cấp (Stepfun, OpenAI proxy, v.v.) bị quá tải hoặc treo kết nối HTTP giữa chừng (đã nhận request nhưng không phản hồi cũng không ngắt kết nối), khiến tiến trình dịch bị đứng chờ.

#### 2. Dữ liệu luôn an toàn 100% (Zero Data Loss)
Mọi chunk sau khi nhận về thành công đều được ghi tức thì vào cơ sở dữ liệu SQLite Checkpoint (`workspace/checkpoints/*.db`). **Dữ liệu các chunk đã dịch trước đó không bao giờ bị mất.**

#### 3. Các bước xử lý nhanh trên giao diện WebUI

```
[Tác vụ đang kẹt/treo]
       │
       ├─► Bấm nút "Dừng" (Stop)
       │         │
       │         ├─► Lựa chọn 1: Bấm "Tiếp tục" (Resume)
       │         │   └── Tự động bỏ qua các chunk đã hoàn thành, chỉ dịch lại duy nhất chunk bị kẹt.
       │         │
       │         └─► Lựa chọn 2: Bấm "Chỉ xuất phần đã dịch" (Export Partial)
       │             └── Xuất ngay file chứa các chunk đã dịch xong thành công ra đĩa.
```

* **Cách 1: Khôi phục và dịch tiếp (Khuyên dùng)**:
  1. Trên modal tiến trình hoặc danh sách tác vụ, bấm nút **"Dừng"** (Stop).
  2. Bấm nút **"Tiếp tục"** (Resume).
  3. Hệ thống đọc checkpoint trên đĩa, tự động nhận diện các chunk đã `done` và chỉ gửi yêu cầu dịch đối với các chunk còn `pending`.
* **Cách 2: Xuất ngay kết quả phần đã dịch (Partial Export)**:
  - Nếu không muốn tiếp tục chờ AI dịch nốt các chunk còn lại, bấm nút **"Chỉ xuất phần đã dịch"** hoặc **"Chia tách phần đã dịch"**. Hệ thống sẽ tự động ghép các chunk đã dịch xong thành file `*_partial.txt` lưu vào thư mục `translated/`.

#### 4. Cơ chế phòng hộ tự động của hệ thống
- **Live Timer (`⏱️ MM:SS`)**: Modal tiến trình hiển thị đồng hồ đếm thời gian thực theo từng giây để người dùng theo dõi AI đã xử lý chunk hiện tại được bao lâu.
- **Hard Socket Timeout (600s / 10 phút)**: Hệ thống tự động ngắt kết nối với mã lỗi `408 Timeout` nếu socket máy chủ AI bị treo quá 10 phút, kích hoạt cơ chế chuyển key hoặc retry tự động thay vì chờ vô hạn.

---

### B. Lỗi Phân mảnh Module OCR (v6.9.0+)
- Lỗi `ImportError` liên quan `plugins.ocr.modules`: chạy từ thư mục gốc dự án.
- Module báo thiếu thư viện: hệ thống tự động cài qua `lazy_import_and_install`. Nếu thất bại, chạy `pip install <package>`.

---

## 8. Cấu hình Tài nguyên (Assets) & Hướng dẫn Sử dụng Biến (Placeholders)

### A. Cơ chế quản lý tài nguyên của Dự án
Mỗi dự án lưu trữ các tệp cấu hình bổ trợ riêng trong thư mục `workspace/projects/<project_slug>/assets/`. 

Nếu tạo thủ công hoặc muốn chỉnh sửa trực tiếp qua tệp tin, bạn phải đặt đúng tên tệp dưới đây (định dạng tệp là văn bản thường UTF-8):

| Tài nguyên | Tên tệp tin chính xác | Định dạng dữ liệu bên trong |
| :--- | :--- | :--- |
| **Bản tóm tắt** | `summary.txt` | Văn bản tóm tắt nội dung/bối cảnh chung. |
| **Chỉ dẫn phong cách** | `style_guide.txt` | Các quy tắc dịch thuật, giọng điệu, xưng hô. |
| **Bảng thuật ngữ** | `glossary.txt` | Dòng phân tách bằng dấu gạch đứng:<br>`từ_gốc \| từ_dịch \| ghi_chú` |
| **Nhân vật & Quan hệ** | `relationship.txt` | Dòng phân tách bằng dấu gạch đứng:<br>`tên_gốc \| tên_dịch \| vai_trò \| quan_hệ` |
| **Ghi chú thêm** | `additional_notes.txt` | Các thông tin ghi chú tự do khác. |

### B. Tính năng dùng AI tự động tạo Tài nguyên (AI Summarize)
Hệ thống tích hợp sẵn tính năng tự động trích xuất và phân tích tài nguyên bằng AI:
- **Cơ chế hoạt động**: Sử dụng mô hình AI được cấu hình (Gemini hoặc OpenAI) để đọc các tệp nguồn (`.txt` hoặc `.md` trong thư mục `sources/` của dự án). File nhỏ chạy một request; file lớn được chia phân tích nhiều phần rồi tổng hợp. Kết quả được ghi an toàn vào các tệp tương ứng (`summary.txt`, `style_guide.txt`, `glossary.txt`, `relationship.txt`).
- **Cách sử dụng trên UI**: Trong Workspace dự án, chuyển sang tab **Thông tin**, chọn tệp nguồn, chọn Mô hình, sau đó chọn loại tài nguyên và bấm **✨ AI Generate**. Hệ thống tạo task chạy nền và hiển thị tiến độ realtime (phase, phần hiện tại, log). Kết quả tự động tải vào khung sau khi hoàn tất.

### C. Bảng cơ chế hoạt động của các biến (Placeholders) trong Prompt dịch
Khi biên soạn prompt hệ thống hoặc prompt dự án, bạn có thể sử dụng các biến sau để chèn dữ liệu động. 

> [!WARNING]
> Không viết các chuỗi `{glossary}` hoặc `{relationships}` vào prompt vì backend không hỗ trợ thay thế các từ khóa này trực tiếp (chúng sẽ bị gửi đi dưới dạng chữ tĩnh).

| Biến (Placeholder) | Trạng thái hỗ trợ | Cơ chế hoạt động của hệ thống | Cách sử dụng |
| :--- | :--- | :--- | :--- |
| **`{source_text}`** | Không cần viết | Hệ thống luôn tự động ghép văn bản gốc của chương/chunk hiện tại vào cuối prompt gửi đi (`prompt + "\n\n" + text_to_process`). | Không viết biến này vào prompt của bạn. |
| **`{translation_guidelines}`** | Có hoạt động | Thay thế bằng nội dung tệp `style_guide.txt`. Nếu prompt không chứa biến này, hệ thống sẽ tự động ghép nội dung phong cách vào cuối prompt. | Viết `{translation_guidelines}` ở vị trí bạn muốn hiển thị quy tắc dịch. |
| **`{previous_chunk_context}`** | Có hoạt động | Thay thế bằng bản dịch và ngữ cảnh tóm tắt của chương/chunk đã dịch trước đó để đảm bảo tính liên kết. | Viết `{previous_chunk_context}` ở phần đầu hoặc phần ngữ cảnh của prompt. |
| **`{project_summary}`** | Có hoạt động | Thay thế bằng nội dung tệp tóm tắt tổng thể `summary.txt`. | Viết `{project_summary}` để cung cấp bối cảnh toàn tác phẩm cho mô hình. |
| **`{project_context}`** | Có hoạt động | Thay thế bằng tổ hợp gộp chung của cả tóm tắt (`summary.txt`) và chỉ dẫn phong cách (`style_guide.txt`). | Viết `{project_context}` nếu muốn chèn gộp nhanh tất cả bối cảnh. |
| **Bảng Thuật ngữ & Nhân vật** | Tự động ghép | Hệ thống tự động quét văn bản gốc hiện tại, tìm các thuật ngữ xuất hiện trong `glossary.txt` và `relationship.txt`, đóng gói chúng thành bảng và tự động ghép vào cuối prompt gửi đi. | Không cần viết bất kỳ biến nào, hệ thống tự động xử lý. |

```python
# Ví dụ về thứ tự prompt được gửi tới LLM thực tế:
# 1. [Nội dung Prompt Dịch thuật của bạn] (Sau khi đã replace các biến hoạt động)
# 2. [Bảng thuật ngữ quét được động từ glossary.txt / relationship.txt] (Nếu có)
# 3. [Văn bản gốc cần dịch]
```

---

## 9. Quản Lý Tác Vụ Dịch Thuật & Bảng Giải Thích Trạng Thái (Task Lifecycle & Status Reference)

Hệ thống cung cấp cơ chế lưu vết và khôi phục tiến trình dịch thuật tự động qua `TaskStore` (SQLite) và Checkpoint Engine (`.db` files).

### A. Bảng Chi Tiết Trạng Thái Tác Vụ (Task Status Reference)

| Trạng thái (Status) | Tên hiển thị WebUI | Nguyên nhân & Bối cảnh phát sinh | Dữ liệu Checkpoint | Khả năng Tiếp tục (Resume) & Thao tác |
| :--- | :--- | :--- | :--- | :--- |
| **`running`** / **`started`** | 🟢 **Đang chạy** | Tác vụ đang được worker xử lý thực tế, gửi request tới LLM Provider và phát heartbeat định kỳ về SQLite. | Đang được cập nhật liên tục theo từng chunk hoàn thành. | ❌ Không thể bỏ/xóa nếu chưa bấm **Dừng**. Bấm *"🔍 Chi tiết"* để xem tiến độ streaming trực tiếp. |
| **`resumable`** | 🔵 **Có thể Resume** | Tác vụ bị gián đoạn nhưng checkpoint hợp lệ (`.db`) còn nguyên vẹn trên đĩa, có các chunk chưa dịch xong. | Còn đầy đủ dữ liệu chunk đã dịch. | ✅ **Sẵn sàng tiếp tục** — Bấm *"▶ Tiếp tục"* (đơn lẻ hoặc theo dự án) để nạp checkpoint và dịch tiếp. |
| **`interrupted`** | 🔵 **Bị gián đoạn** | Worker bị ngắt ngoài ý muốn (mất điện, đóng tab, reload trình duyệt, hoặc heartbeat quá hạn >30s). | Checkpoint nguyên vẹn 100%. | ✅ **Sẵn sàng tiếp tục** — Hệ thống tự động phân loại đây là tác vụ an toàn để tiếp tục. |
| **`paused`** | 🟠 **Đã tạm dừng** | Người dùng chủ động bấm nút *"Dừng"* trên modal tiến trình. Worker thread đã kết thúc an toàn. | Checkpoint nguyên vẹn, giữ đúng chunk đã dịch cuối cùng. | ✅ **Sẵn sàng tiếp tục** bất cứ lúc nào. |
| **`failed`** | 🔴 **Thất bại / Lỗi** | Gặp sự cố nghiệp vụ hoặc lỗi API (Sai key, hết quota, HTTP 429/500/503, proxy lỗi, hoặc chunk độc hại `poison_job`). | Checkpoint lưu giữ các chunk dịch thành công trước thời điểm lỗi. | ⚠️ **Cần kiểm tra lỗi** — Xem `last_error` trong chi tiết. Có thể đổi API Key/Model rồi bấm *"Tiếp tục"* hoặc *"✕ Bỏ"*. |
| **`cancelled`** | ⚪ **Đã hủy** | Người dùng bấm hủy tác vụ qua endpoint cancel hoặc dừng hẳn. | Checkpoint giữ ở trạng thái đóng. | 🗑️ Có thể bấm *"✕ Bỏ"* để dọn sạch. |
| **`closed_partial`** | 🟣 **Đã chia tách** | Người dùng đã bấm *"✂ Chia tách"* để xuất phần chunk đã dịch ra file riêng (`*_partial.txt`). | Checkpoint đã đóng và xuất file. | 🏁 Tác vụ đã hoàn tất một phần, có thể bỏ để giải phóng. |
| **`completed`** | 🟢 **Hoàn thành** | Toàn bộ các chunk của file đã được dịch xong và ghi vào thư mục `translated/`. | Checkpoint đã hoàn thành hoặc tự động dọn dẹp. | 🏁 Không cần thao tác, tự động biến mất khỏi danh sách chờ. |
| **`archived`** | ⚪ **Đã lưu trữ / Bỏ** | Người dùng đã bấm *"✕ Bỏ"* (hoặc Bỏ tất cả của dự án). Checkpoint đổi đuôi `.archived` và `lease_token = NULL`. | File checkpoint đổi đuôi `.db.archived`. | 🗑️ Không còn hiển thị trên Header Pill hoặc danh sách chờ. |

---

### B. Hướng Dẫn Thao Tác Quản Lý Tiến Trình

1. **Header Pill ("Có thể resume: N")**:
   - Khi có **1 tác vụ dở**: Bấm vào pill sẽ mở thẳng Modal Tiến trình với đầy đủ tên file và tên dự án.
   - Khi có **nhiều tác vụ dở ($N > 1$)**: Bấm vào pill sẽ mở **Task Manager Modal** gom nhóm các file theo từng Dự án.
2. **Thao tác Hàng loạt theo từng Dự án (Project-Scoped Actions)**:
   - **`▶ Tiếp tục (N)`**: Tự động khôi phục toàn bộ $N$ tác vụ dở của **riêng dự án đó**.
   - **`✕ Bỏ (N)`**: Tự động hủy và lưu trữ $N$ tác vụ dở của **riêng dự án đó** mà không ảnh hưởng đến các dự án khác.
3. **Trung tâm Quản trị Tác vụ (Task Dashboard)**:
   - Bấm nút **`⚡ Dashboard`** trên góc phải Task Manager để mở giao diện toàn màn hình.
   - Hỗ trợ các Tab bộ lọc (*Tất cả, Đang chạy, Chờ Resume, Lỗi*), tìm kiếm file/dự án, chọn nhiều checkbox và nút *"🧹 Dọn checkpoint mồ côi"*.

---

*Phiên bản tài liệu: 2.7 — Ngày cập nhật: 23/08/2026*

