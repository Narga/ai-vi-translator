# 00. TÔN CHỈ & BẢN TUYÊN NGÔN CỐT LÕI CỦA DỰ ÁN
> **Dự án**: Novel & Text Translator (Next-Gen)  
> **Tôn chỉ tối thượng**: **Minimalist — Single-User — Hiệu Quả — Nhanh — UI Siêu Nhẹ**  
> **Cập nhật ngày**: 03/09/2026

---

## 1. TÔN CHỈ CỐT LÕI (CORE MANIFESTO)

Mọi quyết định thiết kế kiến trúc, mã nguồn và giao diện người dùng của dự án này PHẢI tuân thủ tuyệt đối 5 nguyên tắc sau:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               5 NGUYÊN TẮC BẤT BIẾN                                    │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. ĐƠN NGƯỜI DÙNG (SINGLE-USER ONLY)   │ Chỉ phục vụ duy nhất 1 người dùng cá nhân.   │
│ 2. TỰ DO & CHỦ ĐỘNG NỘI DUNG           │ Người dùng tự kiểm soát nội dung nguồn 100%. │
│ 3. RIÊNG TƯ & TỰ BẢO VỆ                │ Chạy Local / Private VPS, không public ra ngoài│
│ 4. TỐC ĐỘ & HIỆU QUẢ LÀ SỐ 1           │ Tối ưu thông lượng dịch, 0% độ trễ thừa thãi.│
│ 5. UI SIÊU NHẸ, THỰC DỤNG (LEAN UI)    │ Tinh gọn, rõ ràng, KHÔNG hào nhoáng bóng bẩy.│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. LÀM RÕ TỪNG NGUYÊN TẮC THIẾT KẾ

### 2.1. Đơn Người Dùng (Single-User Only)
* **Ý nghĩa**: Ứng dụng này sinh ra cho MỘT NGƯỜI DÙNG DUY NHẤT (Cá nhân tự dịch truyện/sách để đọc hoặc biên soạn riêng).
* **Điều KHÔNG CẦN xây dựng**:
  * ❌ Không cần hệ thống đăng nhập / đăng ký (User Auth, JWT, OAuth).
  * ❌ Không cần phân quyền người dùng (Role-Based Access Control - RBAC).
  * ❌ Không cần Multi-tenancy hay tách biệt dữ liệu đa người dùng.
  * ❌ Không cần session token phức tạp hay rate limiter người dùng.
* **Lợi ích**: Cắt giảm 100% boilerplate về xác thực, mã nguồn chạy trực tiếp với hiệu năng tối đa.

### 2.2. Người Dùng Tự Chủ Động & Toàn Quyền Kiểm Soát Nội Dung
* **Ý nghĩa**: Người dùng tự cấp file nguồn và tự biết nội dung của mình là gì.
* **Điều KHÔNG CẦN xây dựng**:
  * ❌ Không cần bộ lọc kiểm duyệt nội dung (Censorship / Moderation Filters).
  * ❌ Không cần các bộ parser can thiệp sâu để "dọn dẹp" văn bản làm sai lệch ý đồ của tác giả.
  * ❌ Không cần kiểm tra định dạng khắt khe: Bất kỳ tệp văn bản nào (`.txt`, `.md`, `.html`) đưa vào đều được xem là dữ liệu hợp lệ và giữ nguyên vẹn 100% khi xuất xưởng.

### 2.3. Riêng Tư & Tự Bảo Vệ (Private Deployment)
* **Ý nghĩa**: Ứng dụng chạy trực tiếp trên máy tính cá nhân (Localhost) hoặc deploy trên một VPS riêng tư (Private VPS) của người dùng.
* **Quan điểm bảo vệ**:
  * Việc bảo vệ ứng dụng thuộc về **tầng mạng & hạ tầng** của người dùng (dùng SSH Tunnel, VPN WireGuard, Firewall IP Whitelist, hoặc Nginx Basic Auth nếu đưa lên VPS).
  * Ứng dụng **KHÔNG ôm đồm các lớp mã hóa bảo mật nặng nề** (như cơ chế mã hóa AES-GCM Web Crypto API rườm rà của silaBook). API Key chỉ cần lưu trong file cấu hình local hoặc SQLite đơn giản.

### 2.4. Tập Trung Tuyệt Đối Vào Tính Hiệu Quả & Tốc Độ (Performance-First)
* **Trọng tâm duy nhất**: Gửi chunk nội dung kèm prompt cho AI $\to$ Nhận về bản dịch mượt mà nhanh nhất có thể.
* Tối ưu hóa tối đa nguồn token miễn phí (Gemini Free Tier 15 RPM / key) thông qua cơ chế tự động xoay vòng key và tự phục hồi sau khi gặp 429.
* Không có tiến trình chạy ngầm vô bổ, không có cơ chế polling liên tục làm tốn CPU/RAM.

### 2.5. Giao Diện Siêu Nhẹ & Thực Dụng (Utilitarian Lean UI)
* **KHÔNG PHẢI LÀ**:
  * ❌ Không thiết kế UI hào nhoáng bóng bẩy, không lạm dụng hiệu ứng làm mờ kính (Glassmorphism), gradient cầu kỳ hay hiệu ứng chuyển động (animations) làm chậm máy.
  * ❌ Không dùng các thư viện giao diện nặng hàng MB gây giật lag khi tải tệp văn bản lớn hàng triệu từ.
* **LÀ GIAO DIỆN**:
  * ✅ **Siêu nhẹ, tải tức thì (<0.2 giây)**.
  * ✅ **Thực dụng (Utilitarian)**: Màu sắc tương phản cao, phông chữ đơn sắc/sans-serif dễ đọc, tập trung vào con chữ (Text-centric).
  * ✅ **Tối đa hóa diện tích làm việc**: Hỗ trợ Sidebar thu gọn để dành 95% diện tích màn hình cho khung so sánh song ngữ và đọc văn bản.
  * ✅ **Phản hồi tức thì**: Bấm là chạy, cuộn chuột mượt mà, lưu tức thời.

---

## 3. KIM CHỈ NAM THỰC THI CHO TOÀN DỰ ÁN

> *"Nếu một tính năng không giúp việc dịch văn bản nhanh hơn, chính xác hơn hoặc làm UI nặng hơn dù chỉ 1% — HÃY VỨT BỎ NÓ."*

Tất cả các tài liệu kỹ thuật, kiến trúc và lộ trình triển khai trong thư mục `docs/new_project_plan/` đều được hiệu chỉnh và vận hành xoay quanh Tôn chỉ này.
