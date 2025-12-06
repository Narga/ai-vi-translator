# Quick Start - Novel Translator v3.0.1

## 🚀 Bắt Đầu Nhanh (5 phút)

### Bước 1: Cài đặt dependencies

```bash
pip install -r requirements.txt
```

### Bước 2: Cấu hình API keys

```bash
# Sao chép file mẫu
cp config/API.txt.example config/API.txt

# Chỉnh sửa config/API.txt và thêm API keys của bạn
# Lấy API key từ: https://aistudio.google.com/app/apikey
```

**config/API.txt:**
```
AIzaSy...your-first-api-key
AIzaSy...your-second-api-key
AIzaSy...your-third-api-key
```

### Bước 3: Chuẩn bị file nguồn

Đặt file truyện tiếng Trung vào thư mục `workspace/input/`:

```bash
# Ví dụ:
workspace/input/truyen.txt           # File lẻ
# HOẶC
workspace/input/[Ten-Truyen]/        # Thư mục chứa các chương
  ├── 001.txt
  ├── 002.txt
  └── ...
```

### Bước 4: Chạy dịch

```bash
python3 main.py
```

Xong! Bản dịch sẽ xuất hiện trong `workspace/output/[tên-truyện]/`

---

## ⚙️ Cấu hình Nâng Cao

### Điều chỉnh model và nhiệt độ

Chỉnh sửa `config.ini`:

```ini
[MODEL]
MODEL = gemini-2.5-flash              # Model chính (nhanh)
# MODEL = gemini-2.0-flash-exp       # Model thử nghiệm (miễn phí)
# MODEL = gemini-2.5-pro             # Model mạnh hơn

[PROCESSING]
TEMPERATURE = 0.75                    # 0.0-1.0 (cao = sáng tạo hơn)
MIN_CHARS_PER_CHUNK = 18000          # Chunk size tối thiểu
MAX_CHARS_PER_CHUNK = 22000          # Chunk size tối đa
CONTEXT_CHAR_COUNT = 500             # Ngữ cảnh từ chunk trước
```

### Translation Guidelines (Tùy chọn)

Để có bản dịch nhất quán, tạo guidelines:

**Option 1: Tạo thủ công**

```bash
# Tạo các file trong prompts/instructions/
prompts/instructions/
├── glossary.csv              # Bảng thuật ngữ
├── character_relations.csv   # Xưng hô nhân vật
└── style_profile.json        # Văn phong
```

**Option 2: Tạo tự động bằng AI**

```bash
cd utils/content-analysis
# Đặt file nguồn vào input_folder/
python analysis.py
# Guidelines sẽ được tạo tự động
```

---

## 📊 Workflow

```
1. Đọc file từ workspace/input/
2. Chia thành chunks thông minh
3. Dịch từng chunk với context chaining
4. Tự động phát hiện và sửa ký tự Trung còn sót
5. Kiểm tra consistency (nếu bật)
6. Ghi kết quả vào workspace/output/
```

**Features tự động:**
- ✅ Cache thông minh (không dịch lại chunks giống nhau)
- ✅ Auto-retry chunks lỗi
- ✅ Verification mode (kiểm tra bản dịch cũ)
- ✅ Text normalization (dấu câu, quotes)
- ✅ Statistics chi tiết

---

## 🎯 Use Cases

### Use Case 1: Dịch file đơn

```bash
# 1. Đặt file vào input
cp ~/truyen-nguon.txt workspace/input/

# 2. Chạy
python3 main.py

# 3. Kết quả
workspace/output/truyen-nguon_dich.txt
```

### Use Case 2: Dịch truyện nhiều chương

```bash
# 1. Tạo thư mục và đặt các chương
mkdir -p workspace/input/[Ten-Truyen]
# Copy các file 001.txt, 002.txt, ... vào đây

# 2. Chạy
python3 main.py

# 3. Kết quả
workspace/output/[Ten-Truyen]/
  ├── parts/              # Các chunk đã dịch
  └── [Ten-Truyen]_dich.txt  # File tổng hợp
```

### Use Case 3: Tiếp tục dịch khi bị gián đoạn

```bash
# Chỉ cần chạy lại, workflow sẽ tự động resume
python3 main.py

# Workflow sẽ:
# - Phát hiện progress cũ
# - Hỏi có muốn tiếp tục không (y/n)
# - Tiếp tục từ chunk cuối cùng
```

### Use Case 4: Kiểm tra bản dịch cũ

```bash
# Nếu output đã tồn tại, workflow sẽ:
# 1. Hỏi có muốn kiểm tra không
# 2. Quét tất cả chunks
# 3. Chỉ dịch lại chunks có ký tự Trung
# 4. Tiết kiệm API quota

python3 main.py
# Chọn "y" khi được hỏi verification mode
```

---

## 🐛 Troubleshooting

### Lỗi: "No module named 'google'"

```bash
# Cài đặt dependencies
pip install -r requirements.txt

# Hoặc trong venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Lỗi: "File 'config/API.txt' not found"

```bash
# Tạo file API.txt từ template
cp config/API.txt.example config/API.txt
# Sau đó thêm API keys vào file
```

### Chunks vẫn còn ký tự Trung

```ini
# Tăng số lần retry trong config.ini
[PROCESSING]
MAX_REFINEMENT_ATTEMPTS = 3  # Tăng từ 2 lên 3
```

### Bản dịch không nhất quán

```bash
# 1. Tạo translation guidelines
cd utils/content-analysis
python analysis.py

# 2. Bật consistency check
# config.ini:
[PROCESSING]
ENABLE_CONSISTENCY_CHECK = true
```

### API quota hết

```bash
# Workflow sẽ tự động:
# 1. Phát hiện quota hết
# 2. Chuyển sang API key khác
# 3. Nếu hết tất cả keys → tạm dừng và lưu progress
# 4. Chạy lại sau khi quota reset
```

---

## 📚 Tài Liệu Thêm

- [INTEGRATION_GUIDE.md](docs/INTEGRATION_GUIDE.md) - Hướng dẫn chi tiết tất cả tính năng
- [CHANGELOG.md](CHANGELOG.md) - Lịch sử phát triển v1.0 → v3.0.1
- [README.md](README.md) - Tài liệu đầy đủ

---

## 🎉 Hoàn Thành!

Bạn đã sẵn sàng dịch truyện. Nếu có vấn đề, check log file trong `workspace/progress/` hoặc xem documentation.

**Happy Translating! 🚀**
