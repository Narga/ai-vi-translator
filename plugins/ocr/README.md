# OCR Reader Module v3.0.3

Plugin nhận dạng chữ (OCR) cho Novel Translator, hỗ trợ chuyển đổi PDF scan và ảnh thành văn bản.

## 🎯 Chức năng

- **OCR PDF**: Nhận dạng chữ từ PDF (bao gồm cả PDF scan và có text layer)
- **OCR Image**: Nhận dạng chữ từ ảnh (JPG, PNG, BMP, TIFF)
- **AI Cleanup**: Làm sạch văn bản bằng Gemini API (loại bỏ lỗi OCR)
- **Table Extraction**: Trích xuất bảng với 3 tầng fallback (unstructured → pdfplumber → OpenCV)
- **Chinese Variant Detection**: Tự động nhận biết Tiếng Trung giản thể/phồn thể

## 📦 Dependencies

Cài đặt hệ thống (bắt buộc):
```bash
# macOS
brew install tesseract poppler

# Ubuntu/Debian
sudo apt install tesseract-ocr poppler-utils

# Windows
# Tải Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# Tải Poppler: https://github.com/oschwartz10612/poppler-windows/releases
```

Python packages (tự động cài khi chạy):
- pytesseract, pdf2image, Pillow (core OCR)
- pdfplumber, PyPDF2, PyMuPDF (PDF processing)
- python-docx, ocrmypdf (output generation)
- tqdm (progress bar)

## 🚀 Cách Sử Dụng

### Chạy Độc Lập (Standalone)

Module này có thể chạy **hoàn toàn độc lập** mà không cần các thành phần khác của Novel Translator.

```bash
# Từ thư mục gốc dự án
cd plugins/ocr

# OCR một file PDF
python -c "
from ocr_engine import ocr_file
result = ocr_file('path/to/input.pdf', output_path='output.txt')
print(result['text'][:500])  # In 500 ký tự đầu
"
```

### Tích Hợp với Novel Translator

Nếu dùng qua PluginManager:
```python
from core import PluginManager, ServiceBus, EventBus

# Khởi tạo
plugin_manager = PluginManager(service_bus, event_bus, Path('plugins'))
plugin_manager.load_plugin('ocr')

# Sử dụng
ocr_plugin = plugin_manager.get_plugin('ocr')
success = ocr_plugin.convert(
    input_path=Path('input.pdf'),
    output_path=Path('output.txt'),
    pages='1-10',  # Optional: chỉ OCR trang 1-10
    lang='vie+eng'  # Optional: ngôn ngữ
)
```

## 📁 Input/Output

### Input (Đầu vào)
- **Vị trí**: Bất kỳ đường dẫn nào trên hệ thống
- **Định dạng hỗ trợ**: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tiff`, `.tif`

### Output (Đầu ra)
- **Mặc định**: Cùng thư mục với file input, đuôi `_ocr.txt` hoặc `_ocr.docx`
- **Tùy chỉnh**: Chỉ định `output_path` khi gọi hàm
- **Định dạng hỗ trợ**: `.txt`, `.docx`

## ⚙️ Cấu Hình

Tạo file `config/config.yaml`:
```yaml
ocr:
  enabled: true
  lang: "vie+eng"  # Ngôn ngữ: vie, eng, chi_sim, chi_tra
  psm: 3           # Page Segmentation Mode (1-13)
  dpi: 300         # Độ phân giải ảnh
  auto_rotate_exif: true
  auto_rotate_osd: true
  show_progress: true
  
  # Đường dẫn Tesseract (nếu không trong PATH)
  # tesseract_cmd: "/usr/local/bin/tesseract"
  
  # Đường dẫn Poppler (nếu không trong PATH)
  # poppler_path: "/usr/local/bin"

# API keys cho AI cleanup (optional)
api_keys:
  - "YOUR_GEMINI_API_KEY"
```

## 🔄 Giải Thuật (Algorithm)

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT FILE                               │
│              (PDF hoặc Image)                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              1. DETECT FORMAT                               │
│  - PDF? → Convert pages to images (pdf2image)               │
│  - Image? → Load directly (Pillow)                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              2. AUTO-ROTATE                                 │
│  - Check EXIF orientation metadata                          │
│  - Use Tesseract OSD to detect skew                         │
│  - Rotate image to correct orientation                      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              3. LANGUAGE DETECTION (if auto)                │
│  - Sample first few pages                                   │
│  - Detect Chinese variant (simplified/traditional)          │
│  - Set appropriate Tesseract lang parameter                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              4. OCR PROCESSING                              │
│  - Tesseract OCR với lang và psm từ config                  │
│  - Trích xuất text từ từng page                             │
│  - Gom thành văn bản đầy đủ                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              5. AI CLEANUP (Optional)                       │
│  - Gọi Gemini API để sửa lỗi OCR (typos, spacing)           │
│  - Spell check và format lại văn bản                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              6. OUTPUT                                      │
│  - Lưu ra file .txt hoặc .docx                              │
│  - Return dict với 'text' và metadata                       │
└─────────────────────────────────────────────────────────────┘
```

## 📊 API Reference

### `ocr_file(input_path, pages=None, output_path=None, skip_steps=None, process_mode='process')`

Hàm chính để OCR một file.

**Parameters:**
- `input_path` (str): Đường dẫn file PDF hoặc ảnh
- `pages` (str, optional): Trang cần OCR, VD: "1-5,7,10-12"
- `output_path` (str, optional): Đường dẫn file output
- `skip_steps` (dict, optional): Bước bỏ qua `{'cleanup': True, 'spell_check': True}`
- `process_mode` (str): 'process', 'cleanup-only', 'spellcheck-only'

**Returns:**
```python
{
    'text': str,           # Văn bản đã OCR
    'pages_processed': int, # Số trang đã xử lý
    'output_path': str,    # Đường dẫn file output
    'success': bool        # Thành công hay không
}
```

---

**Version**: 3.0.3  
**Author**: Narga  
**License**: Same as Novel Translator
