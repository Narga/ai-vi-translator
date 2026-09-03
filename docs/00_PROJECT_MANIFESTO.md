# 00. TÔN CHỈ & BẢN TUYÊN NGÔN CỐT LÕI DỰ ÁN
> **Dự án**: Content Translator (Next-Gen)  
> **Cập nhật ngày**: 03/09/2026

---

## 1. BẢN CHẤT CỐT LÕI (CORE ESSENCE)

> **"Đây KHÔNG PHẢI là một hệ thống quản lý quá trình dịch tiểu thuyết.**  
> **Đây là một CÔNG CỤ GỬI NỘI DUNG CHO AI VÀ NHẬN BẢN DỊCH VỀ, phục vụ duy nhất MỘT NGƯỜI DÙNG."**

Mọi kiến trúc của dự án chỉ xoay quanh chu trình gửi–nhận nguyên bản:

```text
GIAO DIỆN (UI)
 ├── Chọn / Nhập văn bản
 ├── Cắt chunk (theo ngưỡng ký tự xác định)
 ├── Dựng prompt (Prompt chính + Prompt bổ sung)
 ├── Gửi request
 ├── Nhận response
 ├── Hiển thị kết quả (Dual-Pane so sánh)
 └── Gửi lại khi cần (Nút retry thủ công)

AI CLIENT
 ├── Provider adapter (Gemini, OpenAI-compatible)
 ├── Xử lý Timeout
 ├── Bắt lỗi HTTP & Lỗi mạng
 └── Thử key kế tiếp khi gặp lỗi tạm thời (429)

FILE & CẤU HÌNH (LOCAL)
 ├── Prompt dạng file .txt (thư viện chung hoặc assets của dự án)
 └── Cấu hình local mỏng (config.json + keys.json trong .gitignore)
```

---

## 2. NGUYÊN TẮC "VỨT BỎ SỰ PHỨC TẠP" (WHAT TO EXCLUDE)

Để giữ cho hệ thống cực nhẹ, chạy nhanh, không giật lag và không phát sinh lỗi tiềm ẩn, hệ thống **TUYỆT ĐỐI KHÔNG XÂY DỰNG**:

1. ❌ **Không cần Checkpoint & Auto-Resume**: Không lưu trạng thái dịch dở dang vào database. Nếu lỗi, dừng lại báo rõ nguyên nhân và người dùng bấm gửi lại. (Tính năng Checkpoint được đưa vào tài liệu `ROADMAP.md` để nghiên cứu sau nếu thực sự phát sinh nhu cầu).
2. ❌ **Không cần Task Manager & Queue**: Không background worker, không hàng đợi Celery/Redis, không Task ID, không Event bus, không trạng thái job phức tạp.
3. ❌ **Không cần Dashboard quản lý tác vụ nhiều tầng**: Không job history, không resume panel, không recovery panel, không background notification.
4. ❌ **Không cần Orchestrator & Tự động khôi phục**: Không có cơ chế tự động cố gắng phục hồi toàn bộ quá trình, vì dự án không có mục tiêu quản lý luồng phức tạp.
5. ❌ **Không cần Multi-user & Authentication**: Phục vụ 1 người dùng duy nhất, chạy Local hoặc Private VPS tự bảo vệ ở tầng mạng.
6. ❌ **Không cần các engine phụ trợ nặng nề**: Không context memory tự động, không tóm tắt tự động, không quality scoring, không glossary engine nhiều bảng.

---

## 3. CÂU HỎI SÁT HẠCH CHO MỌI TÍNH NĂNG MỚI (LITMUS TEST)

Trước khi viết bất kỳ dòng mã nào hoặc thêm bất kỳ tính năng nào vào hệ thống, tính năng đó bắt buộc phải trả lời được câu hỏi:

> **"Tính năng này có tuân thủ tiêu chí cốt lõi là gửi nội dung cho AI và nhận bản dịch về một cách đơn giản, nhanh và nhẹ nhất không?"**
>
> * **Nếu CÓ**: Viết với số lượng dòng mã ít nhất có thể (Minimal Working Diff).
> * **Nếu KHÔNG**: Kiên quyết loại bỏ hoặc đưa vào phần ROADMAP nghiên cứu sau.
