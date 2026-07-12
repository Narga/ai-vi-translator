# Đặc tả Thiết kế API Chuẩn (Novel Translator REST API v1 Specification)

Tài liệu này định nghĩa hệ thống API RESTful và Server-Sent Events (SSE) chuẩn hóa cho Novel Translator. Thiết kế này giúp tách biệt hoàn toàn Core Engine (chạy trong Flask) khỏi các giao diện điều khiển (WebUI, CLI API Client, PHP, Bash, hoặc các ứng dụng khác trong tương lai).

---

## 1. Thiết kế Mô-đun Quản lý Tác vụ (Job Management)

Để hỗ trợ nhiều ứng dụng kết nối cùng lúc mà không xảy ra xung đột hàng đợi tiến độ (Queue consumer conflict), hệ thống chuyển từ sử dụng một hàng đợi toàn cục (`progress_queue`) sang **Mô hình Quản lý Job độc lập**:

```
[Client (CLI/Web)] --(POST /translate)--> [Job Manager] 
                                               |--> Tạo Job ID (UUID)
                                               |--> Chạy luồng dịch ngầm (Background Thread)
                                               |--> Lưu sự kiện tiến độ vào hàng đợi riêng của Job
[Client (CLI/Web)] --(GET /jobs/<id>/stream)--> Xem tiến độ thời gian thực của đúng Job đó
```

### Cấu trúc trạng thái Job (Job State)
Mỗi tác vụ dịch thuật khi được khởi chạy sẽ được cấp một `job_id` (ví dụ: `job_8f2d5e7a...`) với các trạng thái:
*   `pending`: Đang chờ tài nguyên hệ thống.
*   `running`: Đang thực hiện dịch.
*   `completed`: Hoàn thành thành công.
*   `failed`: Bị lỗi (kèm thông điệp lỗi `error_message`).
*   `cancelled`: Đã dừng theo yêu cầu của người dùng.

---

## 2. Danh sách các API Endpoints (v1)

Tất cả các endpoints đều được prefix bằng `/api/v1`.

### 2.1. Kiểm tra trạng thái hệ thống
*   **Endpoint:** `GET /api/v1/status`
*   **Mô tả:** Trả về phiên bản phần mềm, cấu hình nhà cung cấp AI đang kích hoạt và các mô hình khả dụng.
*   **Phản hồi thành công (200 OK):**
    ```json
    {
      "version": "8.3.0",
      "status": "ready",
      "active_provider": {
        "name": "Gemini AI",
        "type": "gemini",
        "default_model": "gemini-3-flash-preview"
      },
      "available_models": ["gemini-3-flash-preview", "gemini-2.5-pro", "gpt-4o-mini"]
    }
    ```

### 2.2. Liệt kê danh sách dự án
*   **Endpoint:** `GET /api/v1/projects`
*   **Mô tả:** Liệt kê toàn bộ dự án hiện có cùng số lượng tập tin tương ứng.
*   **Phản hồi thành công (200 OK):**
    ```json
    [
      {
        "slug": "tay-du-ky",
        "book_title": "Tây Du Ký",
        "author": "Ngô Thừa Ân",
        "source_count": 10,
        "translated_count": 4,
        "progress": 40.0,
        "status": "Đang thực hiện"
      }
    ]
    ```

### 2.3. Tạo dự án mới
*   **Endpoint:** `POST /api/v1/projects`
*   **Headers:** `Content-Type: application/json`
*   **Yêu cầu (Body):**
    ```json
    {
      "book_title": "Tây Du Ký",
      "author": "Ngô Thừa Ân",
      "description": "Dịch tự động tác phẩm Tây Du Ký"
    }
    ```
*   **Phản hồi thành công (201 Created):**
    ```json
    {
      "success": true,
      "slug": "tay-du-ky",
      "meta": {
        "book_title": "Tây Du Ký",
        "author": "Ngô Thừa Ân",
        "slug": "tay-du-ky",
        "created_at": "2026-07-12T10:00:00Z"
      }
    }
    ```

### 2.4. Đọc chi tiết một dự án
*   **Endpoint:** `GET /api/v1/projects/<slug>`
*   **Phản hồi thành công (200 OK):**
    ```json
    {
      "slug": "tay-du-ky",
      "book_title": "Tây Du Ký",
      "author": "Ngô Thừa Ân",
      "sources": [
        {"name": "chuong1.txt", "size": 15240, "has_translation": true},
        {"name": "chuong2.txt", "size": 14210, "has_translation": false}
      ]
    }
    ```

### 2.5. Tải tập tin nguồn lên dự án (Upload)
*   **Endpoint:** `POST /api/v1/projects/<slug>/files`
*   **Headers:** `Content-Type: multipart/form-data`
*   **Yêu cầu (Form Data):** `file=@path/to/local/chuong3.txt`
*   **Phản hồi thành công (200 OK):**
    ```json
    {
      "success": true,
      "filename": "chuong3.txt",
      "size": 18230
    }
    ```

### 2.6. Khởi động tác vụ dịch thuật (Translate Job)
*   **Endpoint:** `POST /api/v1/projects/<slug>/translate`
*   **Headers:** `Content-Type: application/json`
*   **Yêu cầu (Body):**
    ```json
    {
      "files": ["chuong2.txt"],
      "model": "gemini-3-flash-preview",
      "temperature": 1.0,
      "force_retranslate": false
    }
    ```
*   **Phản hồi thành công (202 Accepted):**
    *Server tạo tác vụ ngầm và trả về Job ID ngay lập tức để client theo dõi.*
    ```json
    {
      "status": "started",
      "job_id": "job_d98f72a1e64c",
      "files_count": 1
    }
    ```

### 2.7. Lấy thông tin tóm tắt của Job (Polling)
*   **Endpoint:** `GET /api/v1/jobs/<job_id>`
*   **Phản hồi thành công (200 OK):**
    ```json
    {
      "job_id": "job_d98f72a1e64c",
      "status": "running",
      "progress": 45.5,
      "current_chunk": 9,
      "total_chunks": 20,
      "error_message": null
    }
    ```

### 2.8. Stream tiến trình trực tiếp qua SSE (Server-Sent Events)
*   **Endpoint:** `GET /api/v1/jobs/<job_id>/stream`
*   **Headers nhận được:** `Content-Type: text/event-stream`
*   **Các sự kiện được stream liên tục từ server:**
    *   *Tiến trình:* `data: {"type": "progress", "current": 9, "total": 20, "message": "Đang dịch chunk 9/20"}`
    *   *Hoàn thành:* `data: {"type": "complete", "message": "Hoàn thành dịch chuong2.txt"}`
    *   *Lỗi:* `data: {"type": "error", "message": "Lỗi API quota exceeded"}`

---

## 3. Khung Triển khai Backend (Python/Flask) tham khảo

Mã nguồn triển khai API core module trên Flask (Đặt tại `webui/routes/api.py`):

```python
import uuid
import queue
from threading import Thread
from flask import Blueprint, jsonify, request, Response

api_v1_bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

# Kho lưu trữ Job tạm thời trong bộ nhớ RAM
ACTIVE_JOBS = {}

class TranslationJob:
    def __init__(self, job_id, slug, filenames):
        self.job_id = job_id
        self.slug = slug
        self.filenames = filenames
        self.status = "pending"
        self.progress = 0.0
        self.error_message = None
        self.event_queue = queue.Queue()

@api_v1_bp.route("/status")
def get_status():
    return jsonify({
        "version": "8.3.0",
        "status": "ready"
    })

@api_v1_bp.route("/projects/<slug>/translate", methods=["POST"])
def start_translation(slug):
    data = request.json or {}
    filenames = data.get("files", [])
    if not filenames:
        return jsonify({"error": "Thiếu danh sách file"}), 400
        
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job = TranslationJob(job_id, slug, filenames)
    ACTIVE_JOBS[job_id] = job
    
    # Kích hoạt worker thread
    def worker():
        job.status = "running"
        try:
            # (GỌI ĐẾN CORE EXECUTOR DỰA TRÊN USE CASE CÓ SẴN)
            # Trong callback tiến trình của executor, gửi data vào job.event_queue:
            # job.event_queue.put({"type": "progress", "current": ...})
            pass
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.event_queue.put({"type": "error", "message": str(e)})

    thread = Thread(target=worker, daemon=True)
    thread.start()
    
    return jsonify({
        "status": "started",
        "job_id": job_id,
        "files_count": len(filenames)
    }), 202

@api_v1_bp.route("/jobs/<job_id>/stream")
def stream_job(job_id):
    job = ACTIVE_JOBS.get(job_id)
    if not job:
        return jsonify({"error": "Job không tồn tại"}), 404
        
    def event_generator():
        while True:
            try:
                # Chờ sự kiện mới từ worker với timeout 30s để gửi ping giữ kết nối
                data = job.event_queue.get(timeout=30)
                yield f"data: {json.dumps(data)}\n\n"
                if data.get("type") in ["complete", "error", "cancelled"]:
                    break
            except queue.Empty:
                yield "data: {\"type\": \"ping\"}\n\n"
                
    return Response(
        event_generator(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
```

---

## 4. Hướng dẫn Tích hợp Phía Client (Đa ngôn ngữ)

Bất kỳ hệ thống nào cũng có thể gửi lệnh CLI/API theo tài liệu hướng dẫn cURL và PHP ở file `CLI_REMOVAL_PLAN.md`. Thiết kế này đảm bảo tính bền vững lâu dài, việc can thiệp thêm bớt mã nguồn ở WebUI hay Core dịch thuật hoàn toàn độc lập và không ảnh hưởng đến các ứng dụng ngoại vi kết nối sau này.
