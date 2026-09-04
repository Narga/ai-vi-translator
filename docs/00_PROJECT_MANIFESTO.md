# 00. TÔN CHỈ & BẢN TUYÊN NGÔN CỐT LÕI DỰ ÁN
> **Dự án**: Content Translator (Next-Gen)  
> **Phiên bản tài liệu**: v2.3 (Chốt: app.db từ Phase 1 + đa provider explicit + bỏ OCR)  
> **Cập nhật ngày**: 04/09/2026

---

## 1. BẢN CHẤT CỐT LÕI (CORE ESSENCE)

> **"Đây KHÔNG PHẢI là một hệ thống quản lý quá trình dịch tiểu thuyết.**  
> **Đây là một CÔNG CỤ GỬI NỘI DUNG CHO AI VÀ NHẬN BẢN DỊCH VỀ, phục vụ duy nhất MỘT NGƯỜI DÙNG."**

Mọi kiến trúc của dự án chỉ xoay quanh chu trình gửi–nhận nguyên bản:

```text
GIAO DIỆN (UI) / CLI
 ├── Chọn / Nhập văn bản nguồn
 ├── Cắt chunk tự nhiên theo ngưỡng cấu hình (thông thường ~2-3 chunk với file phổ biến)
 ├── Dựng prompt đơn giản
 ├── Gửi request tuần tự
 ├── Nhận response
 ├── Ghép kết quả (nối bằng \n\n)
 └── Hiển thị kết quả / Ghi ra file (Gửi lại thủ công khi lỗi)

AI CLIENT
  ├── Gemini REST + OpenAI-compatible REST (cùng dùng httpx thuần, zero SDK)
  ├── Provider/Model chọn explicit: làm gì chọn model đó, KHÔNG fallback ngầm
  ├── Xử lý Timeout & Bắt lỗi HTTP / Lỗi mạng
  └── Xoay key đơn giản: Mỗi key thử tối đa 1 lần/chunk; 429 thì chuyển key kế tiếp; hết key thì dừng

FILE & CẤU HÌNH (LOCAL)
  ├── Đường dẫn tính tương đối theo thư mục chứa dự án (PROJECT_ROOT)
  ├── config.json mỏng (kèm danh sách models) & keys.json nhạy cảm (nằm trong .gitignore)
  ├── workspace/app.db (SQLite stdlib): index dự án/file + log runs, KHÔNG checkpoint nội dung
  └── Toàn bộ thư mục workspace/ KHÔNG track với Git (bảo đảm riêng tư tuyệt đối)
```

---

## 2. PHÂN ĐỊNH RANH GIỚI: LÕI BẮT BUỘC VS. TIỆN ÍCH MỞ RỘNG

### A. Thành Phần Lõi Bắt Buộc (Phải có để Phase 1 chạy được)
* **`chunker`**: Chia văn bản thành các chunk tự nhiên ($\le \text{max\_chars}$), ưu tiên ranh giới đoạn/câu, xử lý file rỗng, không làm mất nội dung có ý nghĩa.
* **`prompt_engine`**: Thay thế biến `{{source_text}}` (+ `{{glossary_terms}}` khi có) vào template prompt `.txt` mà không làm hỏng Unicode tiếng Việt.
* **`ai_client`**: Gọi AI qua HTTP REST (Gemini + OpenAI-compatible, chung interface `AIClient`), bắt lỗi mạng, timeout, response rỗng và xoay key khi 429. Provider/model luôn chọn explicit qua `--provider/--model`, không fallback ngầm model khác.
* **`run.py` (CLI)**: Đọc file đầu vào, chạy luồng gửi-nhận, in tiến độ và ghi file đầu ra.

### B. Thành Phần Tiện Ích Mỏng (Hỗ trợ cấu hình và an toàn cơ bản)
* **`config`**: Đọc cấu hình JSON mỏng, kiểm tra tính hợp lệ tối thiểu (`max_chunk_chars > 0`, `timeout_seconds > 0`), chứa danh sách `providers.{gemini,openai_compat}.models` để chọn, tách biệt `keys.json` (`gemini_keys`, `openai_compat_keys`).
* **`key_rotator`**: Bộ xoay key tối giản (1 key gặp 429 dừng ngay, nhiều key chuyển lần lượt, không thử lại key trong cùng 1 chunk). Tái dùng y hệt cho cả Gemini và OpenAI-compatible.
* **`file_handler`**: Lớp đọc/ghi file có kiểm tra an toàn đường dẫn (`relative_to()`, chống path traversal `..`, `/`, `\`).
* **`app_db`**: SQLite stdlib (`workspace/app.db`, đã gitignore theo `workspace/`). Chỉ 3 bảng `projects/files/runs` để index + log, KHÔNG lưu checkpoint chunk. Tạo từ Phase 1 để dùng ngay.

### C. Tiện Ích Mở Rộng (Chuyển sang các Phase tiếp theo)
* Quản lý `assets/` riêng của từng dự án & `assets/glossary.txt` $\to$ Chuyển sang **Phase 3** (đường dẫn chuẩn duy nhất: `workspace/projects/{slug}/assets/glossary.txt`).
* Tìm kiếm & thay thế hàng loạt, so sánh Diff chi tiết $\to$ Chuyển sang **Phase 3**.
* Công cụ đóng gói EPUB & chuyển đổi 2 chiều $\to$ Chuyển sang **Phase 4**.
* Checkpoint lưu tạm từng chunk $\to$ Chuyển sang **ROADMAP** (chỉ làm khi thực sự có nhu cầu).
* OCR $\to$ **TẠM HOÃN sang ROADMAP §6** (dùng công cụ ngoài; input của tool chỉ nhận text/md/html).

---

## 3. NGUYÊN TẮC THẤT BẠI & KHÔNG CHECKPOINT (FAILURE POLICY)

1. **Mỗi chunk là một phiên gửi độc lập**:
   * Khi gửi một chunk: thử key hiện tại $\to$ gặp 429 thì chuyển lần lượt sang key kế tiếp trong danh sách (mỗi key thử tối đa 1 lần).
   * Nếu tất cả key đều bị 429 hoặc gặp lỗi mạng/timeout: **Dừng toàn bộ chương trình ngay lập tức**, in thông báo lỗi rõ ràng.
2. **Quy tắc chạy lại (Không Resume)**:
   * **Khi một chunk bị lỗi, chương trình dừng và KHÔNG lưu trạng thái dở dang.**
   * Người dùng kiểm tra lại mạng/key và chạy lại lệnh thủ công. Lần chạy lại sẽ **bắt đầu lại toàn bộ file từ chunk đầu tiên**.
   * *Lý do*: Thông thường mỗi chương truyện kích thước phổ biến chỉ có 2-3 chunk. Việc chạy lại từ đầu là cực kỳ nhanh chóng, không đáng để phải mang vác thêm hệ thống lưu trạng thái hay checkpoint phức tạp.

---

## 4. CAM KẾT ĐỊNH DẠNG THỰC TẾ & KỲ VỌNG AI (REALISTIC CRITERIA)

* ✅ **Bảo toàn nội dung có ý nghĩa**: Không bỏ sót bất kỳ câu, đoạn văn bản nguồn nào ở tầng phân chia chunk.
* ✅ **Tôn trọng ranh giới tự nhiên**: Ưu tiên cắt tại dấu xuống dòng kép `\n\n`, xuống dòng đơn `\n`, hoặc dấu chấm câu kết thúc `. `, không cắt đứt đôi câu văn.
* ✅ **Quy ước khoảng trắng (Whitespace)**: Whitespace quanh ranh giới chunk được chuẩn hóa theo quy ước ghép bằng **một dòng trống (`\n\n`)**; không cam kết bảo toàn tuyệt đối 100% từng byte khoảng trắng gốc.
* ✅ **Kỳ vọng đối với AI**: AI có thể bỏ sót từ, thêm giải thích hoặc bị chặn an toàn. Tiêu chuẩn nghiệm thu kỹ thuật của phần mềm là: **Gửi đầy đủ các chunk, nhận response hợp lệ từ AI, không bỏ qua chunk nào và ghép nối chính xác theo quy ước**. Người dùng luôn là người kiểm tra kết quả cuối cùng trước khi sử dụng.
* ✅ **Ước lượng số chunk**: "Khoảng 2–3 chunk/file" là ước lượng dựa trên kích thước chương truyện thông thường (15k-45k ký tự) với cấu hình `max_chunk_chars=16000`. File dài hơn sẽ tạo nhiều chunk hơn tùy theo độ dài thực tế.

---

## 5. CÂU HỎI SÁT HẠCH (LITMUS TEST)

> **"Tính năng này có giúp việc gửi chunk cho AI và nhận bản dịch về nhanh hơn, nhẹ hơn không?"**  
> Nếu làm tăng trạng thái, thêm luồng ngầm, hoặc không phục vụ trực tiếp chu trình gửi-nhận: **LOẠI BỎ NGAY LẬP TỨC**.

---

## 6. NGUYÊN TẮC PROVIDER/MODEL & MỞ RỘNG (CHỐT v2.3)

1. **Explicit, không fallback ngầm**: Mọi lượt gọi chỉ rõ `provider id + model` (CLI `--provider/--model`, WebUI dropdown từ danh sách live). Lỗi thì dừng, không tự đổi model khác. Model không hardcode — lấy động từ API nhà cung cấp (`providers.json` SSOT, docs/06).
2. **Key theo provider**: `gemini_keys` và `openai_compat_keys` độc lập, cùng dùng `KeyRotator`.
3. **app.db từ Phase 1**: Chỉ index + log (`projects/files/runs`). Không bảng `chunks/checkpoints` cho tới khi ROADMAP kích hoạt.
4. **Mở rộng bằng quy ước, không framework plugin**: Prompt mới = thêm file `prompts/*.txt`; tool mới = thêm file `tools/*.py` chạy độc lập; provider mới = thêm file `core/*_client.py` theo interface `AIClient`. Không hệ thống nạp plugin động, không sandbox trong Phase 1/2.
