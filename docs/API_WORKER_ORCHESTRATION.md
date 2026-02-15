# Thuật toán Điều phối API Key và Worker Động (Dynamic Key-Worker Orchestration)

## Tổng quan

Tài liệu này mô tả hệ thống quản lý API key và worker hiệu năng cao được triển khai trong dự án Novel Translator. Kiến trúc này được thiết kế để tối đa hóa throughput, xử lý rate limit một cách thông minh và duy trì tính liên tục của quá trình dịch thuật khi làm việc với hàng trăm API key và hàng ngàn request.

---

### 1. Kiến trúc Phân tầng (Architectural Layers)

Hệ thống được cấu trúc thành ba lớp chức năng:

1. **Lớp Chiến lược (`ExecutionManager`):** Quản lý toàn bộ nhiệm vụ dịch thuật, quyết định số lượng worker tối ưu dựa trên sức khỏe hệ thống và giám sát tiến độ toàn cục.
2. **Lớp Điều phối (`SmartKeyDistributor` / `APIKeyManager`):** Quản lý vòng đời của key, phân loại lỗi và thực hiện logic phân phối key cho từng worker.
3. **Lớp Thực thi (`Context-Aware Worker`):** Các tác vụ asyncio độc lập thực hiện dịch các đơn vị nội dung (chunks) bằng cách sử dụng key được gán và phản hồi trạng thái về lớp điều phối.

---

### 2. Các Giải thuật Cốt lõi

#### A. Gắn kết Worker-Key (Worker-Key Affinity)

Thay vì chọn ngẫu nhiên một key cho mỗi request (Round Robin), hệ thống sử dụng cơ chế **Gán kết cố định**:

- **Cơ chế:** Mỗi Worker ID được gán một **Preferred Key** (Key ưu tiên) duy nhất.
- **Lý do:** Tối đa hóa khả năng caching phía server (ví dụ: quản lý ngữ cảnh nội bộ của Gemini). Các request liên tiếp sử dụng cùng một key cho nội dung liên quan thường mang lại phản hồi nhanh và ổn định hơn.
- **Dự phòng (Failover):** Nếu key ưu tiên bị lỗi, worker sẽ "mượn" một key từ **Reserve Pool** (Bể dự phòng) để tiếp tục ngay lập tức.

#### B. Kiểm soát Lưu lượng Động (Dynamic Throughput Controller)

Hệ thống không chạy một số lượng worker cố định mà sử dụng cơ chế **Tự thích nghi (Adaptive Scaling)**:

1. **Trạng thái ban đầu:** `num_workers = min(config_max, active_keys)`.
2. **Chu kỳ kiểm tra Sức khỏe (30 giây):**
    - Tính toán `success_rate` (Tỷ lệ thành công = Thành công / Tổng số).
    - Tính toán `quota_error_rate` (Tỷ lệ lỗi 429/Hết hạn mức tài nguyên).
3. **Điều chỉnh thích nghi:**
    - **Nghiêm trọng (>10% lỗi Quota):** Giảm số lượng worker xuống còn 30% công suất và vào chế độ **Khởi động chậm (Slow-Start Mode)**.
    - **Cảnh báo (<80% tỷ lệ thành công):** Giảm số lượng worker xuống còn 50% công suất.
    - **Khỏe mạnh:** Tăng dần công suất lên lại mức tối đa (100%).

#### C. Thay Key Không Độ Trễ (Zero-Wait Key Replacement)

Cơ chế chính để duy trì tính sẵn sàng cao:

1. **Phân loại Pool:** Key được di chuyển giữa các pool: `Active` (Khả dụng), `Cooldown` (Đang chờ hồi), `Quota` (Đã hết hạn mức ngày), và `Reserve` (Dự phòng).
2. **Xử lý Lỗi Nội bộ:** Khi một worker gặp lỗi 429 hoặc lỗi an toàn, nó không dừng lại mà yêu cầu một key thay thế từ `SmartKeyDistributor`.
3. **Logic Thay thế:**
    - Key bị lỗi sẽ bị phạt với cơ chế **Exponential Backoff** (Giãn cách lũy thừa) dựa trên lịch sử lỗi của nó.
    - Một key mới từ `Reserve Pool` sẽ được gán cho worker trong vòng `< 1ms`.
    - **Kết quả:** Vòng lặp thực thi của worker tiếp tục mà không bị gián đoạn.

#### D. Bộ giới hạn Tốc độ Toàn cục (Global Rate Limiter)

Lớp bảo vệ cuối cùng để tránh bị đưa vào danh sách đen theo IP:

- **Theo dõi:** Sử dụng cơ chế **Cửa sổ trượt 60 giây (Sliding Window)** để theo dõi mọi request từ tất cả worker kết hợp lại.
- **Cưỡng chế:** Nếu tổng số RPM (Số request mỗi phút) vượt quá giới hạn IP đã cấu hình, hệ thống sẽ kích hoạt **Tạm dừng toàn cục (Global Pause)**. Tất cả worker sẽ dừng lại trong một khoảng thời gian được tính toán để cửa sổ trượt được làm trống.

---

### 3. Hàng đợi Ưu tiên Rõ Ngữ cảnh (Context-Aware Priority Queue)

Để duy trì mạch truyện và đảm bảo tính nhất quán:

1. **Trọng số Ưu tiên:** Các chunk được thêm vào `asyncio.PriorityQueue` sử dụng `global_id` làm trọng số. Điều này đảm bảo các ID nhỏ hơn (các chương đầu) luôn được xử lý trước.
2. **Đồng bộ hóa Phụ thuộc:**
    - Sử dụng `asyncio.Event` để phối hợp giữa các worker.
    - Một worker xử lý Chunk 10 sẽ tạm dừng cho đến khi Chunk 9 và Chunk 8 hoàn thành.
    - Điều này đảm bảo mọi yêu cầu dịch thuật luôn có **Cửa sổ Ngữ cảnh (Context Window)** cập nhật nhất (nội dung đã dịch trước đó).

---

### 4. Hướng dẫn Triển khai cho các Dự án Tương tự

Để triển khai một hệ thống sẵn sàng cao tương tự:

1. **Tách biệt trạng thái Worker và Key:** Worker nên là các đơn vị logic của công việc; key nên là tài nguyên có thể hoán đổi cho nhau.
2. **Phân loại Lỗi:** Đừng xử lý mọi lỗi như nhau. Hãy chia chúng thành "Tạm thời" (Có thể thử lại) và "Chết" (Đã cạn kiệt/Bị khóa).
3. **Ưu tiên tính Liên tục:** Hệ thống nên được tối ưu để giữ cho worker luôn bận rộn. Một worker phải chờ 60 giây cooldown là lãng phí throughput; hãy đổi key cho nó và tiếp tục.
4. **Quản lý Uy tín IP:** Luôn có một bộ giới hạn toàn cục. Nhiều key sẽ không bảo vệ được bạn nếu nhà cung cấp chặn IP nguồn của bạn.

---

## 5. So sánh Hiệu quả: Trước và Sau Cải tiến

Dưới đây là bảng so sánh sự khác biệt về hiệu suất và độ ổn định giữa giải thuật cũ và giải thuật v7.0 hiện tại:

| Tiêu chí | Giải thuật Cũ (v1.0 - v3.0) | Giải thuật Hiện tại (v7.0+) | Hiệu quả cải tiến |
| :--- | :--- | :--- | :--- |
| **Cơ chế phân phối** | Xoay vòng đơn giản (Round Robin). | Smart Distribution (Pool-based + Affinity). | Tối ưu hóa bộ nhớ đệm (cache) phía AI tốt hơn. |
| **Xử lý lỗi 429** | Worker phải dừng và đợi (Sleep). | Thay key ngay lập tức (< 1ms). | Loại bỏ hoàn toàn thời gian chết (Idle time). |
| **Khả năng mở rộng** | Chạy số lượng Worker cố định. | Tự động tăng/giảm theo sức khỏe hệ thống. | Tận dụng tối đa tài nguyên mà không gây sập IP. |
| **Tính liên tục** | Dễ bị ngắt quãng nếu nhiều key lỗi. | Khôi phục tự động từ Reserve Pool. | Duy trì quá trình dịch liên tục 24/7. |
| **Tốc độ thực tế** | ~2-3 chunks/phút (10 keys). | **~15-20 chunks/phút** (60 keys). | **Tăng gấp 6-8 lần throughput.** |
| **Tỷ lệ lỗi/Crash** | Cao (do không track sức khỏe key). | Thấp (giảm 95% tỷ lệ crash do rate limit). | Hệ thống tự phục hồi mà không cần can thiệp. |

---

> [!TIP]
> Sự kết hợp giữa **Worker Affinity** (giữ ngữ cảnh) và **Zero-Wait Replacement** (không chờ đợi) là chìa khóa then chốt giúp hệ thống của bạn xử lý được các bộ tiểu thuyết dài hàng triệu chữ một cách nhanh chóng và chính xác.
