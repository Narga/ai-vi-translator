# 04. KẾ HOẠCH PHASE 2: GIAO DIỆN WEBUI LEAN & PHẢN HỒI NHANH
> **Mục tiêu**: Xây dựng giao diện WebUI siêu nhẹ, phản hồi tức thì, phục vụ MỘT PHIÊN DỊCH TẠI MỘT THỜI ĐIỂM.  
> **Cam kết**: Giúp người dùng thao tác prompt dễ hơn, kiểm tra chunk dễ hơn, sao chép / lưu file nhanh hơn và gửi lại tức thời khi cần.

---

## 1. NGUYÊN TẮC THIẾT KẾ GIAO DIỆN PHASE 2

Mọi thành phần trên giao diện WebUI phải vượt qua câu hỏi sát hạch:  
> *"Thành phần này có giúp người dùng gửi nội dung cho AI và nhận bản dịch về một cách đơn giản, nhanh và nhẹ nhất không?"*

### Những gì LOẠI BỎ KHỎI Phase 2:
* ❌ Không Auto-resume / Checkpoint.
* ❌ Không Task manager / Background worker / Queue / Job status.
* ❌ Không Tóm tắt tự động / Context memory tự động / Quality scoring.
* ❌ Không Multi-user / Auth / Database nhiều bảng.
* ❌ Không Dashboard task / History panel / Recovery panel.

### Những gì TẬP TRUNG XÂY DỰNG trong Phase 2:
* ✅ **Prompt dễ dùng hơn**: Chọn file `.txt`, xem nội dung, chỉnh sửa và lưu prompt trực tiếp trên web.
* ✅ **Chunk dễ kiểm tra hơn**: Hiển thị rõ danh sách các chunk, số ký tự thực tế, số token ước lượng.
* ✅ **Kết quả dễ sao chép & lưu hơn**: Nút **[Sao chép]** (1-click copy) và **[Lưu file]** (ghi thẳng vào `translated/`).
* ✅ **Gửi lại dễ hơn**: Nút **[Xóa & Gửi lại]** và nút **[Gửi lại]** khi gặp lỗi mạng / 429.
* ✅ **Kế thừa các tính năng hữu ích từ UI cũ**: Màn hình song ngữ **Dual-Pane** cuộn đồng bộ (Sync-Scroll) và cho phép sửa trực tiếp văn bản dịch (Inline Edit).

---

## 2. KIẾN TRÚC GIAO DIỆN: ĐA TRANG ĐỘC LẬP & SIDEBAR THU GỌN

```text
Thanh Sidebar (Thu gọn được 260px -> 64px):
 ├── 📁 Dự Án (/projects)     : Quản lý thư mục dự án, nạp file nguồn
 ├── ✍️ Biên Dịch (/workspace) : Trọng tâm cốt lõi, gửi nhận trực tiếp 1 phiên
 ├── 📜 Prompt (/prompts)     : Quản lý, xem và sửa các file prompt .txt
 └── ⚙️ Cấu Hình (/settings)   : Nhập danh sách key Gemini, chỉnh model & timeout
```

---

## 3. CHI TIẾT CÁC MÀN HÌNH TRONG PHASE 2

### 3.1. Trang 1: Quản Lý Dự Án & Nạp File (`/projects`)
* **Thao tác nhanh**:
  * Nhập tên dự án $\to$ Bấm `[Tạo Dự Án]` $\to$ Tự động tạo cấu trúc `sources/`, `translated/`, `assets/`.
  * Kéo thả file `.txt`, `.md`, `.html` trực tiếp vào khung upload để nạp vào thư mục `sources/`.
  * Bảng danh sách file nguồn hiển thị: Tên file, Dung lượng, Trạng thái (Đã dịch / Chưa dịch).
  * Nút `[Chuyển Sang Biên Dịch]` để đưa các file được chọn vào màn hình Workspace.

### 3.2. Trang 2: Workspace Biên Dịch Song Ngữ (`/workspace`) — *TRỌNG TÂM CỐT LÕI*

Giao diện chia làm 2 khu vực trực quan:

#### A. Cột Điều Khiển Bên Trái (30% bề ngang):
1. **Danh sách file nguồn**:
   * Hiển thị các file đã chọn.
   * Hiển thị bảng phân đoạn các chunk của file hiện tại:
     * *Chunk 1: 11,200 ký tự (~2,800 tokens)*
     * *Chunk 2: 10,850 ký tự (~2,710 tokens)*
2. **Bộ chọn Prompt linh hoạt**:
   * Dropdown chọn *Prompt Chính* (`default_translation.txt` hoặc chọn từ `assets/` của dự án).
   * Danh sách checkbox chọn thêm *Prompt Bổ Sung* (ví dụ: `+ style_co_trang.txt`, `+ qa_polish.txt`).
   * Checkbox: `[Sử dụng glossary.txt trong assets]`.
3. **Bộ nút điều khiển phiên gửi–nhận**:
   * `[▶ Bắt Đầu Dịch]`: Gửi tuần tự các chunk của file lên AI.
   * `[📋 Sao Chép Bản Dịch]`: Copy toàn bộ nội dung bản dịch vào clipboard.
   * `[💾 Lưu Vào File]`: Lưu nội dung vào `workspace/projects/{slug}/translated/{filename}`.
   * `[❌ Xóa & Gửi Lại]`: Xóa kết quả hiện tại và gửi lại từ đầu.
   * `[🔄 Gửi Lại (Retry)]`: Nút này sáng lên khi gặp lỗi mạng hoặc lỗi 429 để người dùng chủ động bấm gửi lại.

#### B. Màn hình Dual-Pane Bên Phải (70% bề ngang):
* **Bên trái**: Văn bản gốc (nguyên vẹn cấu trúc dòng, tiêu đề Markdown `#`, trích dẫn `>`).
* **Bên phải**: Văn bản dịch tiếng Việt đang nhận về từ AI.
* **Tính năng kế thừa từ UI cũ**:
  * **Cuộn đồng bộ (Sync-Scroll)**: Cuộn văn bản gốc thì văn bản dịch cuộn theo tương ứng.
  * **Chỉnh sửa trực tiếp (Inline Edit)**: Người dùng có thể click vào khung dịch sửa từ ngữ ngay lập tức trước khi bấm lưu file.

### 3.3. Trang 3: Quản Lý Thư Viện Prompt (`/prompts`)
* Liệt kê danh sách các file prompt `.txt` từ thư mục `prompts/` chung và `assets/` của dự án.
* Cho phép mở ra xem nội dung, chỉnh sửa câu chữ và bấm **[Lưu Prompt]**.
* Cung cấp nút **[+ Tạo Prompt Mới]** (lưu thành file `.txt` mới).

### 3.4. Trang 4: Cấu Hình Tối Giản (`/settings`)
* Textarea nhập danh sách API Key Gemini (mỗi dòng 1 key, tự động lưu vào `config/keys.json` nằm trong `.gitignore`).
* Chọn Model mặc định (`gemini-2.5-flash`) và điều chỉnh `max_chunk_chars` (mặc định 12.000 ký tự).

---

## 4. TIÊU CHÍ NGHIỆM THU PHASE 2 (HOÀN TOÀN DÙNG ĐƯỢC CHO CÔNG VIỆC THỰC TẾ)

Sau khi hoàn thành Phase 2, người dùng:
1. Chạy `python server.py` $\to$ Mở trình duyệt `http://localhost:8000`.
2. Tạo dự án `Kiem_Hiep`, kéo file `chuong_01.md` vào.
3. Vào Workspace: Thấy rõ file được chia thành 2 chunk, số ký tự và token ước lượng rõ ràng.
4. Bấm `[▶ Bắt Đầu Dịch]` $\to$ Thấy văn bản tiếng Việt hiển thị song song ngay bên cạnh.
5. Nếu gặp lỗi 429 hay lỗi mạng $\to$ UI hiển thị thông báo đỏ rõ ràng và hiện nút `[Gửi Lại]`.
6. Dịch xong $\to$ Bấm `[Lưu Vào File]` $\to$ File xuất hiện ngay trong `translated/chuong_01.md`.
