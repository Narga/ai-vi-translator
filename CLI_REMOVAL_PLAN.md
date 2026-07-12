# Kế hoạch: Gộp CLI & Chuyển WebUI sang main.py

> Ngày: 2026-07-12  
> Căn cứ: Phân tích thực trạng codebase — không có file nào import lẫn nhau.

## Bối cảnh thực trạng (PHẢI ĐỌC TRƯỚC KHI LÀM)

Dự án hiện có **3 file entry point độc lập**, không ai import nhau, không ai gọi nhau nội bộ:

| File | Vai trò thực tế | Được gọi bởi |
|---|---|---|
| `main.py` | CLI cũ — dịch file qua `TranslationExecutor` (layer cũ hơn) | `pyproject.toml`: `content-translator = "main:main"` |
| `cli.py` | CLI đầy đủ — dùng `TranslateTextUseCase` (Clean Architecture, đúng kiến trúc) | `pyproject.toml`: `nt = "cli:main"` |
| `webui.py` | Flask runner — 60 dòng, gọi `webui.create_app()`, chạy server | Chỉ chạy tay: `python webui.py` |

**Vấn đề:**
- `main.py` và `cli.py` trùng chức năng nhưng `main.py` dùng layer cũ hơn → giữ `cli.py`, bỏ `main.py`.
- `webui.py` là file quan trọng nhất nhưng tên không phản ánh vai trò → đổi thành `main.py`.
- Sau khi làm xong: `main.py` = Flask runner, `cli.py` = CLI, không có gì thừa.

**Không cần:** wrapper, `old_cli/`, thư mục tạm, `.gitignore` thêm, bất kỳ layer trung gian nào.

---

## COMMIT 1: Gộp CLI, xóa `main.py` cũ

### Bước 1.1 — Xác nhận `main.py` không bị import nội bộ

Chạy lệnh kiểm tra, **phải trả về rỗng**:

```bash
grep -rn "from main import\|import main" --include="*.py" .
```

Nếu có kết quả → dừng, báo cáo trước khi tiếp tục.

### Bước 1.2 — Sửa `pyproject.toml`

Mở `pyproject.toml`, tìm đoạn `[project.scripts]`:

```toml
# TRƯỚC:
[project.scripts]
content-translator = "main:main"
nt = "cli:main"

# SAU:
[project.scripts]
content-translator = "cli:main"
nt = "cli:main"
```

Lý do: `cli.py` dùng `TranslateTextUseCase` (đúng Clean Architecture), thay thế hoàn toàn `main.py` CLI.

### Bước 1.3 — Xóa `main.py`

```bash
git rm main.py
```

### Bước 1.4 — Verify

```bash
# 1. Không còn reference đến main.py trong code (README/docs không tính):
grep -rn "from main import\|import main" --include="*.py" .
# Kết quả mong đợi: rỗng

# 2. Test suite không vỡ:
pytest tests/ -x -q
# Kết quả mong đợi: tất cả test pass như trước (baseline 200 passed)

# 3. CLI vẫn hoạt động:
python cli.py --help
python cli.py status
```

### Bước 1.5 — Commit

```bash
git add pyproject.toml
git commit -m "refactor: xóa main.py CLI cũ, gộp vào cli.py

- main.py (TranslationExecutor layer cũ) trùng chức năng với cli.py
  (TranslateTextUseCase, Clean Architecture) → giữ cli.py, bỏ main.py
- Chuyển entrypoint content-translator từ main:main sang cli:main
- Không thay đổi behavior: cli.py đã có subcommand translate đầy đủ
- Zero regression: pytest pass baseline"
```

---

## COMMIT 2: Đổi `webui.py` → `main.py`

### Bước 2.1 — Xác nhận `webui.py` không bị import nội bộ

```bash
grep -rn "from webui import\b\|^import webui$" --include="*.py" .
```

**Lưu ý:** Kết quả sẽ có `from webui import create_app` trong nhiều file — đó là import vào **package `webui/`** (thư mục), không phải file `webui.py`. Đây là bình thường, không phải vấn đề.  
Chỉ lo nếu có `from webui import main` hoặc `import webui` rồi gọi `webui.app.run()` — trường hợp này không tồn tại trong codebase hiện tại.

### Bước 2.2 — Đổi tên file

```bash
git mv webui.py main.py
```

### Bước 2.3 — Sửa `pyproject.toml` (nếu cần)

Kiểm tra `[project.scripts]` sau Commit 1 — `content-translator` đang trỏ vào `cli:main`.  
Nếu muốn `content-translator` khởi động Flask WebUI (khuyến nghị vì đây là entry point chính):

```toml
[project.scripts]
content-translator = "main:main"   # Flask WebUI — đây là main.py mới (cũ là webui.py)
nt = "cli:main"                    # CLI
```

Nếu muốn `content-translator` vẫn là CLI → giữ `cli:main`, không sửa.  
**Quyết định tùy bạn — ghi rõ vào commit message.**

### Bước 2.4 — Verify

```bash
# 1. Flask WebUI khởi động bình thường:
python main.py
# Mở http://localhost:7860 — kiểm tra UI load, dịch thử 1 file ngắn

# 2. Test suite pass:
pytest tests/ -x -q
```

### Bước 2.5 — Cập nhật tài liệu (cùng commit)

Thay tất cả `python webui.py` → `python main.py` trong:

| File | Dòng cần sửa |
|---|---|
| `README.md` | Dòng 45: `python webui.py` |
| `README.md` | Dòng 65: `webui.py ──→ webui/` |
| `docs/MANUAL.md` | Dòng 33, 35: `python webui.py` |
| `docs/MANUAL.md` | Dòng 164: `python webui.py --port 8080` |
| `docs/DEVELOPMENT.md` | Dòng 42: `webui.py  # Entry point cho Web UI` |
| `docs/DEVELOPMENT.md` | Dòng 103: đề cập `webui.py` |

```bash
# Nhanh hơn — tìm tất cả tham chiếu còn lại:
grep -rn "webui\.py" --include="*.md" .
```

### Bước 2.6 — Commit

```bash
git add main.py README.md docs/MANUAL.md docs/DEVELOPMENT.md pyproject.toml
git commit -m "refactor: đổi webui.py → main.py, main.py là Flask WebUI runner

- webui.py (Flask runner) đổi tên thành main.py — phản ánh đúng vai trò
  entry point chính của ứng dụng
- Cập nhật README, MANUAL, DEVELOPMENT thay python webui.py → python main.py
- Kết quả: main.py = Flask WebUI, cli.py = CLI, không có file thừa
- Không thay đổi logic bên trong, zero regression"
```

---

## Trạng thái sau khi hoàn thành

```
main.py     → Flask WebUI runner (cũ là webui.py)
cli.py      → CLI đầy đủ, dùng Clean Architecture backend
webui/      → Flask package (không đổi)
backend/    → Clean Architecture (không đổi)
core/       → Pipeline dịch (không đổi)
services/   → Services (không đổi)
```

`pyproject.toml` entrypoints:
```toml
content-translator = "main:main"   # python main.py — khởi động Flask WebUI
nt = "cli:main"                    # python cli.py — CLI
```

---

## Ghi chú cho model thực thi

1. **Làm tuần tự** — Commit 1 trước, verify xong mới làm Commit 2.
2. **Không tạo file wrapper, thư mục tạm** — Đây là rename/delete thuần túy.
3. **`from webui import create_app`** trong `main.py` (sau đổi tên) vẫn đúng — nó import package `webui/`, không phải file `webui.py` cũ.
4. Nếu `pytest` thất bại ở bước verify → dừng ngay, không tiếp tục commit.
5. **CLI client tương lai** (kết nối Flask qua HTTP API) là việc riêng biệt, KHÔNG thuộc phạm vi kế hoạch này — xem `docs/API_DESIGN_SPEC.md`.
