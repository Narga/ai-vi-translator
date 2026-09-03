# 03. KẾ HOẠCH TRIỂN KHAI PHASE 1 CHI TIẾT TỈ MỈ (CLI WORKING CORE)
> **Mục tiêu**: Xây dựng bộ mã nguồn cốt lõi tối giản, chỉ dùng `httpx`, loại bỏ hoàn toàn FastAPI/uvicorn/pydantic và storage trạng thái, **sử dụng được ngay lập tức từ dòng lệnh CLI để dịch file**.  
> **Cam kết**: Đầy đủ mã nguồn mẫu, xử lý toàn diện các trường hợp biên (file rỗng, Unicode, lỗi mạng, 429, path traversal).

---

## 1. DANH SÁCH FILE CỦA PHASE 1

```text
content-translator/
├── pyproject.toml              # Dependencies tối giản: CHỈ CẦN httpx (dev: pytest)
├── .gitignore                  # Bỏ qua workspace/ và config/keys.json
├── config/
│   ├── config.json             # Cấu hình chung (model, timeout, max_chars)
│   └── keys.json               # API keys nhạy cảm (Google Gemini)
├── core/
│   ├── __init__.py
│   ├── config.py               # Lớp nạp cấu hình JSON mỏng (zero dependency)
│   ├── key_rotator.py          # Module xoay key tối giản (mỗi key thử tối đa 1 lần/chunk)
│   ├── chunker.py              # Cắt chunk tự nhiên (15k-20k chars), xử lý file rỗng
│   ├── prompt_engine.py        # Nạp prompt .txt, bảo toàn Unicode tiếng Việt
│   ├── ai_client.py            # Client Gemini REST (timeout, lỗi mạng, xoay key khi 429)
│   └── file_handler.py         # Đọc/ghi file an toàn (chống path traversal)
├── prompts/
│   └── default_translation.txt # Prompt chính dịch chuẩn
├── tests/
│   ├── test_chunker.py         # Test cắt chunk, văn bản rỗng, văn bản ngắn
│   ├── test_key_rotator.py     # Test chuyển key khi 429 và dừng khi hết key
│   └── test_prompt_engine.py   # Test nạp prompt và giữ nguyên Unicode
└── run.py                      # Script CLI thực thi dịch trực tiếp
```

---

## 2. CHI TIẾT MÃ NGUỒN TỪNG FILE TRIỂN KHAI ĐƯỢC NGAY

### Task 1.1: `pyproject.toml` & `.gitignore`
* **File**: `pyproject.toml`
  ```toml
  [project]
  name = "content-translator"
  version = "1.0.0"
  description = "Minimalist AI Content Translator"
  requires-python = ">=3.12"
  dependencies = [
      "httpx>=0.27.0",
  ]

  [project.optional-dependencies]
  dev = [
      "pytest>=8.0.0",
      "pytest-asyncio>=0.23.0",
  ]
  ```

* **File**: `.gitignore`
  ```text
  __pycache__/
  .venv/
  config/keys.json
  workspace/
  ```

---

### Task 1.2: `core/config.py` (Lớp Cấu Hình Cực Mỏng)
* **Mã nguồn**:
  ```python
  # core/config.py
  import json
  from pathlib import Path
  from typing import List, Dict, Any

  CONFIG_DIR = Path("config")
  CONFIG_FILE = CONFIG_DIR / "config.json"
  KEYS_FILE = CONFIG_DIR / "keys.json"

  DEFAULT_CONFIG = {
      "provider": "gemini",
      "gemini_model": "gemini-2.5-flash",
      "max_chunk_chars": 16000,
      "timeout_seconds": 90
  }

  class AppConfig:
      def __init__(self):
          CONFIG_DIR.mkdir(parents=True, exist_ok=True)
          self._ensure_files()

      def _ensure_files(self):
          if not CONFIG_FILE.exists():
              CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
          if not KEYS_FILE.exists():
              KEYS_FILE.write_text(json.dumps({"gemini_keys": []}, indent=2), encoding="utf-8")

      def get_config(self) -> Dict[str, Any]:
          try:
              return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
          except Exception:
              return DEFAULT_CONFIG

      def get_gemini_keys(self) -> List[str]:
          try:
              data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
              return [k.strip() for k in data.get("gemini_keys", []) if k.strip()]
          except Exception:
              return []
  ```

---

### Task 1.3: `core/key_rotator.py` (Xoay Vòng Key Tối Giản)
* **Quy tắc**: Mỗi key chỉ được thử tối đa 1 lần trong 1 lần gửi chunk. Gặp 429 thì chuyển lần lượt sang key kế tiếp. Nếu hết key thì trả về `None`.
* **Mã nguồn**:
  ```python
  # core/key_rotator.py
  from typing import List, Optional

  class KeyRotator:
      def __init__(self, keys: List[str]):
          self.keys = [k.strip() for k in keys if k.strip()]
          self.current_idx = 0
          self._tried_in_chunk = set()

      def has_keys(self) -> bool:
          return len(self.keys) > 0

      def start_chunk_attempt(self):
          """Đặt lại danh sách key đã thử cho chunk mới."""
          self._tried_in_chunk.clear()

      def get_current_key(self) -> str:
          if not self.keys:
              raise ValueError("Danh sách API Key đang trống! Vui lòng nạp key vào config/keys.json.")
          return self.keys[self.current_idx]

      def try_next_key(self) -> Optional[str]:
          """Chuyển sang key tiếp theo khi gặp 429. Trả về None nếu đã thử hết danh sách."""
          self._tried_in_chunk.add(self.current_idx)
          if len(self._tried_in_chunk) >= len(self.keys):
              return None  # Đã thử hết toàn bộ key

          self.current_idx = (self.current_idx + 1) % len(self.keys)
          return self.keys[self.current_idx]
  ```

---

### Task 1.4: `core/chunker.py` (Cắt Chunk Tự Nhiên & Xử Lý Biên)
* **Mã nguồn**:
  ```python
  # core/chunker.py
  import re
  from typing import List

  def count_words(text: str) -> int:
      count = 0
      in_word = False
      for char in text:
          code = ord(char)
          is_whitespace = code <= 32 or code == 160 or (8192 <= code <= 8202) or code == 12288
          if is_whitespace:
              in_word = False
          else:
              if not in_word:
                  count += 1
                  in_word = True
      return count

  def _find_best_cut(text: str, min_pos: int, max_pos: int, target_pos: int) -> int:
      # 1. Ưu tiên dấu xuống dòng kép \n\n (ngắt đoạn văn)
      doubles = [m.start() for m in re.finditer(r'\n[ \t]*\n', text) if min_pos <= m.start() <= max_pos]
      if doubles:
          return min(doubles, key=lambda p: abs(p - target_pos))

      # 2. Ưu tiên dấu xuống dòng đơn \n
      singles = [m.start() for m in re.finditer(r'\n', text) if min_pos <= m.start() <= max_pos]
      if singles:
          return min(singles, key=lambda p: abs(p - target_pos))

      # 3. Ưu tiên kết thúc câu kèm khoảng trắng
      sentences = [m.end() for m in re.finditer(r'[\.!\?。！？]\s+', text) if min_pos <= m.end() <= max_pos]
      if sentences:
          return min(sentences, key=lambda p: abs(p - target_pos))

      # 4. Khoảng trắng thông thường
      spaces = [m.start() for m in re.finditer(r'\s+', text) if min_pos <= m.start() <= max_pos]
      if spaces:
          return min(spaces, key=lambda p: abs(p - target_pos))

      # 5. Cắt cứng tại 50% nếu không có khoảng trắng
      return target_pos

  def split_text(text: str, max_chars: int = 16000) -> List[str]:
      """Chia nhỏ văn bản thành các chunk tự nhiên <= max_chars.
      Xử lý được văn bản rỗng, văn bản nhỏ hơn giới hạn, văn bản không có dấu cách."""
      if not text or not text.strip():
          return []

      if len(text) <= max_chars:
          return [text]

      min_pos = int(len(text) * 0.2)
      max_pos = int(len(text) * 0.8)
      target_pos = int(len(text) * 0.5)

      cut = _find_best_cut(text, min_pos, max_pos, target_pos)
      part1 = text[:cut].rstrip()
      part2 = text[cut:].lstrip()

      result = []
      for part in (part1, part2):
          if len(part) > max_chars:
              result.extend(split_text(part, max_chars))
          else:
              if part:
                  result.append(part)
      return result
  ```

---

### Task 1.5: `core/prompt_engine.py` (Nạp Prompt & Giữ Unicode Tiếng Việt)
* **Mã nguồn**:
  ```python
  # core/prompt_engine.py
  from pathlib import Path

  class PromptEngine:
      def __init__(self, prompts_dir: str = "prompts"):
          self.prompts_dir = Path(prompts_dir)
          self.prompts_dir.mkdir(parents=True, exist_ok=True)
          self._ensure_default_prompt()

      def _ensure_default_prompt(self):
          default_file = self.prompts_dir / "default_translation.txt"
          if not default_file.exists():
              default_file.write_text(
                  "BẠN LÀ MÁY DỊCH TIỂU THUYẾT CHUYÊN NGHIỆP SANG TIẾNG VIỆT.\n"
                  "QUY TẮC BẢO TOÀN NỘI DUNG & ĐỊNH DẠNG:\n"
                  "1. Dịch chuẩn xác, tự nhiên theo văn phong tiếng Việt, không bỏ sót nội dung.\n"
                  "2. Giữ nguyên các thẻ Markdown (#, **, _, >, ```), HTML và ký tự thụt lề.\n"
                  "3. Giữ nguyên các dòng trống giữa các đoạn văn.\n"
                  "4. KHÔNG thêm lời chào mừng hay bình luận thừa.\n\n"
                  "# VĂN BẢN NGUỒN CẦN DỊCH:\n"
                  "{{source_text}}",
                  encoding="utf-8"
              )

      def load_prompt(self, prompt_filename: str = "default_translation.txt") -> str:
          file_path = self.prompts_dir / prompt_filename
          if not file_path.exists():
              raise FileNotFoundError(f"Không tìm thấy file prompt: {file_path}")
          return file_path.read_text(encoding="utf-8")

      def assemble_prompt(self, source_text: str, prompt_filename: str = "default_translation.txt") -> str:
          template = self.load_prompt(prompt_filename)
          return template.replace("{{source_text}}", source_text)
  ```

---

### Task 1.6: `core/ai_client.py` (Client Gemini REST - Xoay Key Tối Giản)
* **Mã nguồn**:
  ```python
  # core/ai_client.py
  import httpx
  import logging
  from core.key_rotator import KeyRotator

  logger = logging.getLogger(__name__)

  class GeminiClient:
      def __init__(self, key_rotator: KeyRotator, model: str = "gemini-2.5-flash", timeout_seconds: int = 90):
          self.rotator = key_rotator
          self.model = model
          self.timeout = timeout_seconds

      async def translate_chunk(self, prompt: str) -> str:
          self.rotator.start_chunk_attempt()

          while True:
              current_key = self.rotator.get_current_key()
              url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={current_key}"
              payload = {
                  "contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.3}
              }

              try:
                  async with httpx.AsyncClient(timeout=float(self.timeout)) as client:
                      resp = await client.post(url, json=payload)

                      # 1. Gặp lỗi 429 (Rate Limit) -> thử key kế tiếp
                      if resp.status_code == 429:
                          next_key = self.rotator.try_next_key()
                          if next_key is not None:
                              logger.warning("⚠️ Key hiện tại bị 429. Đang chuyển sang key tiếp theo...")
                              continue
                          else:
                              raise RuntimeError("❌ TẤT CẢ API KEY ĐỀU BỊ LỖI 429 (RATE LIMIT)! Vui lòng chạy lại sau ít phút.")

                      # 2. Gặp lỗi HTTP khác -> dừng ngay lập tức, không retry vô hạn
                      resp.raise_for_status()

                      data = resp.json()
                      candidates = data.get("candidates", [])
                      if not candidates:
                          raise ValueError("AI không trả về kết quả nội dung (Có thể bị bộ lọc an toàn chặn)!")
                      return candidates[0]["content"]["parts"][0]["text"]

              except httpx.ConnectError:
                  raise ConnectionError("❌ LỖI KẾT NỐI MẠNG! Không thể kết nối tới Google Gemini. Vui lòng kiểm tra mạng.")
              except httpx.TimeoutException:
                  raise TimeoutError(f"❌ QUÁ THỜI GIAN CHỜ ({self.timeout}s)! AI không phản hồi kịp.")
              except httpx.HTTPStatusError as e:
                  if e.response.status_code != 429:
                      raise RuntimeError(f"❌ LỖI TỪ GEMINI (Mã HTTP {e.response.status_code}): {e.response.text}")
                  raise e
  ```

---

### Task 1.7: `core/file_handler.py` (Đọc/Ghi File Có Chống Path Traversal)
* **Mã nguồn**:
  ```python
  # core/file_handler.py
  from pathlib import Path
  from typing import List

  class SafeFileHandler:
      def __init__(self, base_dir: str = "workspace"):
          self.base_dir = Path(base_dir).resolve()
          self.base_dir.mkdir(parents=True, exist_ok=True)

      def _validate_path(self, target_path: Path) -> Path:
          resolved = target_path.resolve()
          if not str(resolved).startswith(str(self.base_dir)):
              raise ValueError(f"Đường dẫn không an toàn (Path traversal detected): {target_path}")
          return resolved

      def get_project_dir(self, slug: str) -> Path:
          if ".." in slug or "/" in slug or "\\" in slug:
              raise ValueError(f"Tên dự án không hợp lệ: {slug}")
          p = self._validate_path(self.base_dir / "projects" / slug)
          (p / "sources").mkdir(parents=True, exist_ok=True)
          (p / "translated").mkdir(parents=True, exist_ok=True)
          return p

      def list_sources(self, slug: str) -> List[str]:
          sources_dir = self.get_project_dir(slug) / "sources"
          return sorted([f.name for f in sources_dir.iterdir() if f.is_file()])

      def read_source(self, slug: str, filename: str) -> str:
          if ".." in filename or "/" in filename or "\\" in filename:
              raise ValueError(f"Tên file không hợp lệ: {filename}")
          file_path = self._validate_path(self.get_project_dir(slug) / "sources" / filename)
          if not file_path.exists():
              raise FileNotFoundError(f"Không tìm thấy file nguồn: {file_path}")
          return file_path.read_text(encoding="utf-8", errors="replace")

      def save_translated(self, slug: str, filename: str, content: str):
          if ".." in filename or "/" in filename or "\\" in filename:
              raise ValueError(f"Tên file không hợp lệ: {filename}")
          out_path = self._validate_path(self.get_project_dir(slug) / "translated" / filename)
          out_path.write_text(content, encoding="utf-8")
  ```

---

### Task 1.8: `run.py` (Script CLI Tối Giản Dùng Được Ngay)
Hỗ trợ cả 2 chế độ: dịch trực tiếp 2 file (`python run.py input.txt output.txt`) hoặc dịch theo dự án (`python run.py --project Truyen --file ch01.md`).

* **Mã nguồn**:
  ```python
  # run.py - CLI Thực thi dịch Phase 1
  import asyncio
  import sys
  from pathlib import Path
  from core.config import AppConfig
  from core.key_rotator import KeyRotator
  from core.chunker import split_text
  from core.prompt_engine import PromptEngine
  from core.ai_client import GeminiClient

  async def main():
      config_mgr = AppConfig()
      cfg = config_mgr.get_config()
      keys = config_mgr.get_gemini_keys()

      if not keys:
          print("❌ LỖI: Chưa có API Key nào trong config/keys.json! Vui lòng nạp key.")
          sys.exit(1)

      # 1. Xác định file vào và file ra
      if len(sys.argv) == 3 and not sys.argv[1].startswith("--"):
          input_path = Path(sys.argv[1])
          output_path = Path(sys.argv[2])
      elif "--project" in sys.argv and "--file" in sys.argv:
          from core.file_handler import SafeFileHandler
          handler = SafeFileHandler()
          p_idx = sys.argv.index("--project") + 1
          f_idx = sys.argv.index("--file") + 1
          proj = sys.argv[p_idx]
          fname = sys.argv[f_idx]
          proj_dir = handler.get_project_dir(proj)
          input_path = proj_dir / "sources" / fname
          output_path = proj_dir / "translated" / fname
      else:
          print("Cách dùng:")
          print("  1. Dịch trực tiếp: python run.py input.txt output.txt")
          print("  2. Dịch theo dự án: python run.py --project Truyen --file ch01.md")
          sys.exit(1)

      if not input_path.exists():
          print(f"❌ LỖI: File không tồn tại: {input_path}")
          sys.exit(1)

      raw_content = input_path.read_text(encoding="utf-8", errors="replace")
      if not raw_content.strip():
          print("⚠️ CẢNH BÁO: File nguồn rỗng! Không có nội dung cần dịch.")
          sys.exit(0)

      # 2. Cắt chunk tự nhiên (thường 2-3 chunk)
      chunks = split_text(raw_content, max_chars=cfg["max_chunk_chars"])
      total = len(chunks)
      print(f"📄 Bắt đầu dịch: {input_path.name} ({len(raw_content):,} ký tự -> {total} chunk).")

      rotator = KeyRotator(keys)
      ai_client = GeminiClient(rotator, model=cfg["gemini_model"], timeout_seconds=cfg["timeout_seconds"])
      prompt_engine = PromptEngine()

      translated_chunks = []

      # 3. Gửi tuần tự từng chunk
      for idx, chunk_text in enumerate(chunks, 1):
          print(f"⏳ Đang gửi chunk {idx}/{total} ({len(chunk_text):,} ký tự)...", end="", flush=True)
          prompt = prompt_engine.assemble_prompt(chunk_text)

          try:
              res = await ai_client.translate_chunk(prompt)
              translated_chunks.append(res)
              print(" [XONG]")
          except Exception as e:
              print(f"\n🛑 LỖI: {str(e)}")
              print("⚠️ CHƯƠNG TRÌNH ĐÃ DỪNG VÀ KHÔNG LƯU TRẠNG THÁI DỞ DANG.")
              print("👉 Bạn hãy kiểm tra lại kết nối / API key và chạy lại lệnh từ đầu.")
              sys.exit(1)

      # 4. Ghép nối bằng \n\n và ghi file output
      output_path.parent.mkdir(parents=True, exist_ok=True)
      final_result = "\n\n".join(translated_chunks)
      output_path.write_text(final_result, encoding="utf-8")
      print(f"🎉 HOÀN TẤT! Bản dịch đã lưu tại: {output_path}")

  if __name__ == "__main__":
      asyncio.run(main())
  ```

---

## 3. BỘ KIỂM THỬ VÀ NGHIỆM THU PHASE 1 (ACCEPTANCE GATES)

### 3.1. Các Bài Kiểm Thử Tự Động (`pytest`)
* `test_chunker.py`:
  * File rỗng $\to$ trả về `[]`.
  * Văn bản ngắn ($< \text{max\_chars}$) $\to$ giữ nguyên 1 chunk duy nhất.
  * Văn bản dài $\to$ cắt ưu tiên tại `\n\n`, `\n`, dấu chấm câu.
  * Văn bản không có dấu cách $\to$ fallback chia đôi tại 50%.
* `test_key_rotator.py`:
  * Kiểm tra lần lượt đổi key khi gọi `try_next_key()`.
  * Khi hết danh sách key $\to$ trả về `None`.
* `test_prompt_engine.py`:
  * Nạp template, thay thế `{{source_text}}`, kiểm tra bảo toàn nguyên vẹn Unicode tiếng Việt.
* `test_file_handler.py`:
  * Kiểm tra ném lỗi `ValueError` khi tên file chứa `../`.

### 3.2. Nghiệm Thu Thực Tế (Thành Công 100%)
1. Chạy lệnh: `python run.py sample_input.txt sample_output.txt`.
2. Kiểm tra file `sample_output.txt` xuất hiện đầy đủ nội dung dịch tiếng Việt, các đoạn văn được phân tách bằng một dòng trống (`\n\n`).
3. Tắt mạng khi đang chạy $\to$ chương trình dừng ngay lập tức, báo lỗi mạng và không ghi đè kết quả rác.
