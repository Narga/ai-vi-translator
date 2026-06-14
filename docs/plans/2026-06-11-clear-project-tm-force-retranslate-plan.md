# Kế hoạch Loại bỏ Cache, Clear Project TM, Force Retranslate và Hướng dẫn viết Unit Tests

> **Phiên bản:** Hợp nhất & Thống nhất (2026-06-14)
> **Mục đích:** Tài liệu duy nhất theo dõi tiến độ, chi tiết hóa hướng dẫn viết Unit Tests cho Cache Removal & Force Retranslate để mô hình AI khác có thể kế thừa và thực thi chính xác.

---

## 1. Trạng thái Hiện tại (Tính đến 2026-06-14)

### ✅ Các phần ĐÃ HOÀN THÀNH 100%
1. **Loại bỏ Translation Cache**:
   - Tệp `services/cache_service.py` đã bị xóa hoàn toàn khỏi dự án.
   - Các logic đọc/ghi cache đã bị gỡ khỏi `core/executor.py`, `plugins/translation/translator.py` (`robust_translate`) và các router backend.
   - Checkbox "Sử dụng cache" đã được loại bỏ khỏi giao diện cấu hình.
2. **API Endpoint Clear Project TM**:
   - Thêm route `POST /api/projects/<slug>/tm/clear` trong `webui/routes/projects.py` để xóa TM riêng của dự án.
   - Nút chức năng "Đặt lại bộ nhớ dịch" (tên cũ là "Xóa TM dự án") đã được đưa lên giao diện workspace dự án.
3. **Chế độ Force Retranslate**:
   - Thêm tùy chọn "Dịch lại từ đầu" (checkbox) trong giao diện.
   - Gửi payload `force_retranslate` xuống backend thông qua API `POST /api/projects/<slug>/translate`.
   - Lõi dịch thuật `TranslationExecutor` sẽ dọn dẹp checkpoint cũ, bỏ qua resume checkpoint, bỏ qua so khớp TM cũ nhưng vẫn ghi nhận TM mới khi dịch thành công.

---

## 2. Các phần CHƯA HOÀN THÀNH (Cần làm)

Cần bổ sung các unit tests cho những tính năng mới của Cache Removal & Force Retranslate nhằm đảm bảo hệ thống không bị lỗi hồi quy (regression) và hoạt động đúng đặc tả.

### Danh mục công việc kiểm thử:
- **[ ] Task B.1**: Unit test kiểm tra lõi `TranslationExecutor` với cấu hình `force_retranslate=True`.
- **[ ] Task B.2**: Unit test kiểm tra API Route `POST /api/projects/<slug>/tm/clear`.
- **[ ] Task B.3**: Unit test kiểm tra API Route `POST /api/projects/<slug>/translate` khi truyền payload `force_retranslate=True`.
- **[ ] Task B.4**: Chạy toàn bộ test suite để đảm bảo 100% test pass.

---

## 3. Chỉ dẫn Chi tiết viết Unit Tests (Dành cho AI Models khác thực thi)

Dưới đây là chi tiết mã nguồn giả lập (mocking) và cấu trúc kiểm thử cần được thêm vào thư mục `tests/`.

### 3.1. Hướng dẫn viết Task B.1: Kiểm thử `TranslationExecutor` với `force_retranslate=True`

- **Tệp cần tạo**: `tests/unit/test_translation_executor.py`
- **Mục tiêu**: Đảm bảo rằng khi `force_retranslate` là `True`, executor sẽ:
  1. Gọi hàm `cleanup` của `CheckpointService` trước khi dịch.
  2. Không gọi hàm `find_match` của `TranslationMemory` (không dùng bản dịch cũ).
  3. Vẫn gọi hàm `add_translation` để lưu lại kết quả dịch mới sau khi gọi API thành công.
  4. Không tải thông tin checkpoint resume dở dang.

#### Mẫu code đề xuất:
```python
# tests/unit/test_translation_executor.py
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from core.executor import TranslationExecutor

@pytest.fixture
def mock_dependencies():
    with patch("core.executor.CheckpointService") as mock_cp_service, \
         patch("core.executor.robust_translate") as mock_translate:
        
        # Thiết lập robust_translate trả về kết quả thành công giả lập
        mock_translate.return_value = ("Bản dịch thành công từ AI", "success", "mock-api-key")
        
        # Cấu hình checkpoint_service mock
        cp_instance = MagicMock()
        mock_cp_service.return_value = cp_instance
        
        yield cp_instance, mock_translate

def test_executor_force_retranslate(mock_dependencies):
    mock_cp, mock_translate = mock_dependencies
    
    # Cấu hình có force_retranslate = True
    config = {
        "model_name": "gemini-3-flash-preview",
        "temperature": 0.5,
        "chunk_size": 10000,
        "force_retranslate": True,
        "prompts": {"main": "Dịch:"}
    }
    
    executor = TranslationExecutor(api_keys=["test-key"], config=config)
    
    # Mock TranslationMemory
    mock_tm = MagicMock()
    mock_tm.find_match.return_value = {"similarity": 1.0, "translation": "Bản dịch cũ trong TM"}
    
    text_to_translate = "Văn bản kiểm thử."
    output_filename = "test_file"
    
    # Thực thi
    result = executor.translate_text(
        text=text_to_translate,
        output_filename=output_filename,
        translation_memory=mock_tm
    )
    
    # KIỂM TRA (ASSERTIONS):
    # 1. Trả về kết quả dịch giả lập mới
    assert result == "Bản dịch thành công từ AI"
    
    # 2. Phải gọi cleanup checkpoint trước khi chạy
    mock_cp.cleanup.assert_called_with(output_filename)
    
    # 3. KHÔNG được gọi find_match vì force_retranslate = True
    mock_tm.find_match.assert_not_called()
    
    # 4. Vẫn PHẢI gọi add_translation để lưu bản dịch mới vào bộ nhớ dịch
    mock_tm.add_translation.assert_called_once_with(
        "Văn bản kiểm thử.", 
        "Bản dịch thành công từ AI", 
        output_filename
    )
```

---

### 3.2. Hướng dẫn viết Task B.2 & B.3: Kiểm thử các API Routes của dự án

- **Tệp cần tạo**: `tests/unit/test_project_routes.py`
- **Mục tiêu**: Sử dụng `flask_client` có sẵn trong `conftest.py` để gửi request giả lập, kiểm tra mã trả về (HTTP Status Code) và JSON payload.

#### Mẫu code đề xuất:
```python
# tests/unit/test_project_routes.py
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

def test_clear_project_tm_route(flask_client):
    """Kiểm tra API xóa TM của dự án (Task B.2)."""
    # Mock _get_project_dir để trỏ về thư mục tạm và mock TranslationMemory
    with patch("webui.routes.projects._get_project_dir") as mock_get_dir, \
         patch("webui.routes.projects.TranslationMemory") as mock_tm_class:
        
        # Giả lập thư mục dự án tồn tại
        tmp_dir = MagicMock(spec=Path)
        tmp_dir.exists.return_value = True
        mock_get_dir.return_value = tmp_dir
        
        # Giả lập TranslationMemory.clear() xóa được 10 mục
        tm_instance = MagicMock()
        tm_instance.clear.return_value = 10
        mock_tm_class.return_value = tm_instance
        
        # Gửi request POST
        response = flask_client.post("/api/projects/test-project-slug/tm/clear")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["deleted"] == 10
        tm_instance.clear.assert_called_once()

def test_translate_project_route_force_retranslate(flask_client):
    """Kiểm tra API dịch dự án nhận diện đúng cờ force_retranslate (Task B.3)."""
    with patch("webui.routes.projects._get_project_dir") as mock_get_dir, \
         patch("webui.routes.projects._load_project_meta") as mock_load_meta, \
         patch("webui.routes.projects.TranslateProjectFilesUseCase") as mock_use_case, \
         patch("webui.routes.projects.Thread") as mock_thread:
        
        # Giả lập tồn tại project
        tmp_dir = MagicMock(spec=Path)
        tmp_dir.exists.return_value = True
        mock_get_dir.return_value = tmp_dir
        mock_load_meta.return_value = {"book_title": "Test Book"}
        
        # Payload gửi xuống có chứa force_retranslate=True
        payload = {
            "files": ["chapter1.txt"],
            "model": "gemini-3-flash-preview",
            "force_retranslate": True
        }
        
        response = flask_client.post(
            "/api/projects/test-project-slug/translate",
            json=payload
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "started"
        
        # Kiểm tra xem Use Case có được khởi tạo thông qua luồng chạy hay không.
        # Ở đây ta kiểm thử luồng truyền nhận param của config trong Flask handler.
```

---

### 3.3. Hướng dẫn chạy kiểm thử (Task B.4)

Sau khi viết xong các tệp test trên, chạy lệnh sau ở terminal để kiểm tra kết quả:
```bash
uv run pytest tests/unit/test_translation_executor.py tests/unit/test_project_routes.py -v
```
Và chạy toàn bộ suite để đảm bảo không lỗi hồi quy:
```bash
uv run pytest
```
