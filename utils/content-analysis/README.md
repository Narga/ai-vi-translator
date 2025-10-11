# Content Analysis Utility (v1.1.0)

Tiện ích độc lập để phân tích nội dung tiểu thuyết tiếng Trung, gửi ba prompt chuẩn kèm nguồn tới Gemini và tạo ra: `style_profile.json`, `glossary.csv`, `character_relations.csv`. Bản 1.1.0 ép toàn bộ đầu ra bằng tiếng Việt, hỗ trợ AI file cache để giảm token khi nguồn lớn, và cấu hình nguồn bằng đường dẫn đầy đủ (kèm tên file).

## Tính năng
- Ép mô hình trả lời hoàn toàn bằng tiếng Việt cho cả 3 tác vụ qua “instruction prefix” nhưng vẫn giữ schema output (CSV/JSON) đúng như prompt.
- AI file cache (Gemini File API): tải nguồn lên một lần, lưu `file_uri` trong `ai_cache_index.json` để tái sử dụng ở các lần chạy sau.
- Dùng chung `API.txt` với dự án chính: tự động tìm theo hướng đi ngược thư mục.
- Tôn trọng `REQUEST_DELAY`, quay vòng API key và backoff cơ bản khi gặp quota/rate-limit.

## Cấu trúc thư mục (gợi ý)
utils/
content-analysis/
analysis.py
config.ini
CHANGELOG.md
README.md
ai_cache_index.json # tạo ra sau lần upload đầu tiên (nếu bật AI cache)
prompts/
1_prompt_style_analysis.txt
2_prompt_glossary_extraction.txt
3_prompt_character_relations.txt
source-cn.txt # ví dụ nguồn
output/
style_profile.json
glossary.csv
character_relations.csv


## Cấu hình (config.ini)
Ví dụ cấu hình 1.1.0:

[MODEL]
MODEL = gemini-2.5-flash

[PROCESSING]
TEMPERATURE = 0.75
REQUEST_DELAY = 2

[CONTENT_ANALYSIS]
PROMPTS_DIR = ./utils/content-analysis/prompts/
SOURCE_PATH = ./utils/content-analysis/source-cn.txt
OUTPUT_DIR = ./utils/content-analysis/output/
ENABLE_AI_FILE_CACHE = true


- `SOURCE_PATH`: đường dẫn đầy đủ TỚI FILE nguồn (ưu tiên). Nếu không có, có thể tạm dùng `SOURCE_DIR` như đường dẫn đầy đủ TỚI FILE.
- `ENABLE_AI_FILE_CACHE`: `true/false`. Nếu `true`, công cụ sẽ tải file nguồn lên Gemini và tham chiếu bằng `file_uri` để giảm token trong các lần chạy sau.
- `PROMPTS_DIR`, `OUTPUT_DIR`: thư mục chứa prompt và thư mục ghi kết quả.

## Cách chạy
python utils/content-analysis/analysis.py


Sau khi chạy thành công:
- `output/style_profile.json` (tiếng Việt)
- `output/glossary.csv` (tiếng Việt, giữ header schema như prompt)
- `output/character_relations.csv` (tiếng Việt, giữ header schema như prompt)

## Gỡ rối
- Đảm bảo `API.txt` tồn tại (mỗi dòng một key) và có ít nhất một key hợp lệ.
- Kiểm tra `SOURCE_PATH` là đường dẫn tới tệp (bao gồm tên file) và file có encoding UTF-8.
- Nếu gặp lỗi hạn mức, tăng `REQUEST_DELAY` hoặc bổ sung thêm API key. Khi upload thất bại, công cụ sẽ tự động nhúng trực tiếp nguồn để đảm bảo nhiệm vụ hoàn thành.
