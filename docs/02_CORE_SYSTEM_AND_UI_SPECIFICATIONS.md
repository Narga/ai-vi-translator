# 02. ĐẶC TẢ HỆ THỐNG CỐT LÕI & GIAO DIỆN (ĐÃ TINH GIẢN)
> **Mục tiêu**: Định nghĩa chuẩn xác cấu trúc hệ thống gửi–nhận, cơ chế xoay key đơn giản, các kiểm tra an toàn đường dẫn và giao diện phục vụ duy nhất một phiên dịch tại một thời điểm.

---

## 1. CẤU TRÚC DỰ ÁN & CHÍNH SÁCH BẢO VỆ DỮ LIỆU CÁ NHÂN

### 1.1. Cấu Trúc Thư Mục Dự Án
```text
workspace/projects/Truyen_Tien_Hiep/
├── sources/            # Chứa các file chương gốc (ch01.md, ch02.txt...)
├── translated/         # Chứa các file bản dịch tiếng Việt hoàn chỉnh
└── assets/             # (Mở rộng ở Phase 3) glossary.txt, prompt riêng của dự án
```

### 1.2. Chính Sách Gitignore (Bảo Đảm Riêng Tư Tuyệt Đối)
Toàn bộ thư mục `workspace/` và các file bí mật **BẮT BUỘC KHÔNG TRACK VỚI GIT**:
```text
# .gitignore
__pycache__/
.venv/
workspace/             # Toàn bộ nội dung sách, file nguồn, bản dịch được giữ riêng tư
config/keys.json       # Chứa API key nhạy cảm
```

### 1.3. An Toàn Đường Dẫn (Chống Path Traversal Cơ Bản)
* Trong lớp `file_handler`, mọi thao tác mở và ghi file đều phải kiểm tra:
  * Không chứa ký tự đi lùi thư mục `..`.
  * Không chứa đường dẫn tuyệt đối bắt đầu bằng `/` hoặc `C:\`.
  * Đường dẫn phân giải thực tế (`resolve()`) bắt buộc phải nằm bên trong thư mục `workspace/`.
* *Mục đích*: Đây là **tính đúng đắn cơ bản** để tránh đọc/ghi nhầm file hệ thống ngoài ý muốn, không phải cơ chế bảo mật rườm rà.

---

## 2. QUẢN LÝ CẤU HÌNH CỰC MỎNG

Hệ thống dùng chuẩn JSON thuần của thư viện chuẩn Python (zero dependency, không cần Pydantic):

* **`config/config.json`** (Cấu hình chung - Track Git):
  ```json
  {
    "provider": "gemini",
    "gemini_model": "gemini-2.5-flash",
    "max_chunk_chars": 16000,
    "timeout_seconds": 90
  }
  ```
* **`config/keys.json`** (Dữ liệu nhạy cảm - Bị ignore bởi Git):
  ```json
  {
    "gemini_keys": [
      "AIzaSyD-KEY_1",
      "AIzaSyD-KEY_2"
    ]
  }
  ```

---

## 3. CƠ CHẾ XOAY VÒNG API KEY TỐI GIẢN (CHUYÊN BIỆT CHO GEMINI TRONG PHASE 1)

### 3.1. Logic Luân Chuyển Khẳng Định
* **Mỗi chunk là một phiên gửi độc lập**.
* Khi gửi request cho một chunk:
  1. Gửi bằng key hiện tại.
  2. Nếu gặp lỗi **HTTP 429 (Rate Limit)**: Chuyển sang key kế tiếp trong danh sách.
  3. **Mỗi key chỉ được thử tối đa một lần trong một lần gửi chunk**.
  4. Nếu tất cả các key đều gặp lỗi 429: **Dừng toàn bộ chương trình**, in thông báo lỗi rõ ràng:  
     `"❌ TẤT CẢ API KEY ĐỀU BỊ RATE LIMIT (429)! Vui lòng bấm 'Gửi lại' sau ít phút."`
* Nếu chunk trước thành công ở key thứ $K$, chunk sau tiếp tục bắt đầu từ key thứ $K$ để tận dụng quota khả dụng.

### 3.2. Phân Loại Xử Lý Lỗi Tối Thiểu
* **Lỗi tạm thời của key (HTTP 429)**: Thử key kế tiếp trong danh sách lần lượt.
* **Lỗi nội dung / prompt / model (HTTP 400)**: Dừng ngay lập tức, **tuyệt đối không retry vô hạn**.
* **Lỗi mạng (ConnectError) hoặc Timeout**: Báo lỗi mạng rõ ràng cho người dùng, dừng tiến trình và hiển thị nút **[Gửi lại]**.
* **Quy tắc khi lỗi**: Chương trình dừng và **không lưu trạng thái dở dang**. Khi người dùng chạy lại, chương trình bắt đầu lại toàn bộ file từ chunk đầu tiên.

---

## 4. QUY TRÌNH CHIA CHUNK THỰC TẾ & QUY ƯỚC GHÉP NỐI

### 4.1. Kích Thước Chunk Thực Tế
* Thông thường, một chương truyện có độ dài từ 3.000 đến 10.000 từ (khoảng 15.000 - 45.000 ký tự).
* Ngưỡng cắt lý tưởng được cấu hình từ **15.000 đến 20.000 ký tự/chunk**.
* Do đó, **thông thường một chương chỉ chia thành 2 đến 3 chunk**, hiếm khi vượt quá 5 chunk.

### 4.2. Giải Thuật Cắt Ưu Tiên Ranh Giới Tự Nhiên
Cắt tại vị trí gần mốc 50% nhất trong dải 20% - 80% theo thứ tự ưu tiên:
1. Dấu xuống dòng đôi `\n\n` (ngắt đoạn văn tự nhiên).
2. Dấu xuống dòng đơn `\n`.
3. Dấu kết thúc câu (`. `, `! `, `? `, `。`, `！`, `？`).
4. Dấu cách thông thường.
5. Cắt cứng tại 50% nếu văn bản không có khoảng trắng.

### 4.3. Quy Ước Ghép Nối Chunk
* **Quy ước Phase 1**: Mỗi chunk được coi là một đơn vị đoạn văn bản lớn; các chunk dịch xong được ghép nối với nhau bằng **một dòng trống (`\n\n`)**.
* Không tuyên bố bảo toàn 100% định dạng; cam kết bảo toàn 100% nội dung chữ và ưu tiên ranh giới đoạn văn tự nhiên.

---

## 5. THIẾT KẾ GIAO DIỆN: 1 PHIÊN DỊCH TẠI 1 THỜI ĐIỂM (PHASE 2 WEBUI)

Giao diện phục vụ duy nhất 1 phiên dịch in-flight, không bảng biểu quản lý rườm rà:

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ [LOGO] CONTENT TRANSLATOR                                    [Gemini: 2 Keys Sẵn Sàng]      │
├─────────────────────────────────────────────────────────────────────────────────────────────┤
│ 📁 Dự Án: [Truyen_Tien_Hiep ▼]   📜 Prompt: [default_translation.txt ▼]   [+ Prompt bổ sung] │
├──────────────────────────────────┬──────────────────────────────────────────────────────────┤
│ DANH SÁCH FILE NGUỒN             │ MÀN HÌNH DUAL-PANE SO SÁNH SONG NGỮ                      │
│ [X] chuong_01.md (2 chunks)      ├────────────────────────────┬─────────────────────────────┤
│ [ ] chuong_02.md (3 chunks)      │ VĂN BẢN GỐC                │ BẢN DỊCH TIẾNG VIỆT         │
│                                  │                            │                             │
│ ℹ️ THÔNG TIN CHUNK ĐANG XỬ LÝ:   │ # Chương 1: Khởi đầu       │ # Chương 1: Khởi đầu        │
│ • Chunk hiện tại: 1 / 2          │ Đêm đã về khuya...         │ Đêm đã về khuya...          │
│ • Ký tự: 16,420 ký tự            │                            │                             │
│ • Token ước lượng: ~4,100 tokens │                            │                             │
├──────────────────────────────────┴────────────────────────────┴─────────────────────────────┤
│ BỘ NÚT ĐIỀU KHIỂN:                                                                          │
│ [▶ Bắt Đầu Dịch]   [📋 Sao Chép Bản Dịch]   [💾 Lưu Vào File]   [❌ Xóa & Gửi Lại]   [🔄 Gửi Lại]│
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

* **Thao tác tức thì**:
  * **[▶ Bắt Đầu Dịch]**: Gửi lần lượt 2-3 chunk lên Gemini.
  * **[📋 Sao Chép]**: 1-click copy kết quả vào Clipboard.
  * **[💾 Lưu Vào File]**: Ghi kết quả vào `workspace/projects/{slug}/translated/{filename}`.
  * **[❌ Xóa & Gửi Lại]**: Xóa kết quả hiện tại để gửi lại từ đầu.
  * **[🔄 Gửi Lại (Retry)]**: Sáng lên khi gặp lỗi mạng / 429 để người dùng chủ động bấm thử lại.
  * **Dual-Pane**: Sync-Scroll cuộn đồng bộ và Inline Edit sửa trực tiếp bản dịch.
