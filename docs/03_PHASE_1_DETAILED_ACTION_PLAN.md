# 03. KẾ HOẠCH TRIỂN KHAI PHASE 1 CHI TIẾT TỈ MỈ (CORE FOUNDATION)
> **Mục tiêu Phase 1**: Xây dựng nền tảng cốt lõi của Backend hoàn chỉnh, bao gồm giải thuật cắt văn bản bảo toàn định dạng `smartHardSplit`, cơ chế xoay vòng Key Pool tự động cooldown 429, bộ nạp prompt `.txt` hỗ trợ prompt bổ sung và client gọi AI đa luồng.  
> **Chuẩn mực thực thi**: Chia nhỏ thành từng bước hành động 2-5 phút, có sẵn mã nguồn mẫu, đường dẫn tệp chính xác và lệnh kiểm thử (`pytest`).

---

## 1. CẤU TRÚC THƯ MỤC CỦA PHASE 1

```text
novel_translator_next/
├── pyproject.toml              # Cấu hình dự án & dependencies tối giản
├── core/
│   ├── __init__.py
│   ├── chunker.py              # Giải thuật smartHardSplit & đếm từ O(N)
│   ├── prompt_engine.py        # Đọc prompt .txt & cơ chế ghép prompt bổ sung
│   ├── key_pool.py             # Quản lý cụm key, Round-robin, Cooldown 60s
│   ├── ai_client.py            # Adapter gọi Gemini & OpenAI-compatible
│   └── storage.py              # 1 file SQLite duy nhất quản lý state/checkpoint
├── prompts/
│   ├── default_translation.txt # Prompt chính dịch chuẩn
│   ├── style_co_trang.txt      # Prompt bổ sung xưng hô cổ trang
│   └── qa_polish.txt           # Prompt bổ sung trau chuốt văn học
└── tests/
    ├── __init__.py
    ├── test_chunker.py         # Test cắt câu, không đứt Markdown/dòng
    ├── test_prompt_engine.py   # Test đọc file .txt & prompt stacking
    ├── test_key_pool.py        # Test xoay key & cooldown 429
    └── test_ai_client.py       # Test gọi AI & auto-failover
```

---

## 2. CHI TIẾT CÁC BƯỚC THỰC HIỆN TỪNG TASK

### Task 1.1: Khởi Tạo Dự Án & Dependencies Tối Giản

* **Mục đích**: Thiết lập môi trường Python 3.12 sạch, loại bỏ toàn bộ các thư viện nặng (không có OCR, không có PDF/EPUB parser DOM).
* **Tệp tạo**: `pyproject.toml`
* **Nội dung code**:
  ```toml
  [project]
  name = "novel-translator-next"
  version = "1.0.0"
  description = "Minimalist AI Novel & Text Translator"
  requires-python = ">=3.12"
  dependencies = [
      "fastapi>=0.110.0",
      "uvicorn>=0.28.0",
      "pydantic>=2.6.0",
      "httpx>=0.27.0",
      "google-genai>=1.0.0",
      "python-dotenv>=1.0.0",
  ]

  [project.optional-dependencies]
  dev = [
      "pytest>=8.0.0",
      "pytest-asyncio>=0.23.0",
  ]
  ```
* **Lệnh kiểm thử môi trường**:
  ```bash
  uv venv && source .venv/bin/activate
  uv pip install -e ".[dev]"
  python -c "import fastapi, httpx, google.genai; print('✅ Môi trường Phase 1 sẵn sàng!')"
  ```

---

### Task 1.2: Xây Dựng `core/chunker.py` (Kế Thừa Giải Thuật `smartHardSplit` Từ silaBook)

* **Mục đích**: Cắt nhỏ văn bản mà không làm gãy vỡ cấu trúc dòng, câu văn hay các thẻ Markdown, khoảng cách thụt lề.
* **Tệp tạo**: `core/chunker.py`
* **Đặc tả logic chi tiết**:
  1. `count_words(text: str) -> int`: Thuật toán đếm từ $O(N)$ bộ nhớ $O(1)$ duyệt qua mã ký tự (không dùng `split(/\s+/)`).
  2. `find_best_cut_position(text: str, min_pos: int, max_pos: int, target_pos: int) -> int`: Quét tìm vị trí cắt lý tưởng theo 4 bậc ưu tiên:
     * Ưu tiên 1: Dấu xuống dòng kép `\n\n` gần mốc 50% nhất.
     * Ưu tiên 2: Dấu xuống dòng đơn `\n` gần mốc 50% nhất.
     * Ưu tiên 3: Dấu chấm kết thúc câu (`. `, `! `, `? `, `。`, `！`, `？`) kèm khoảng trắng gần mốc 50% nhất.
     * Ưu tiên 4: Dấu cách ` ` gần mốc 50% nhất.
     * Fallback: Vị trí 50% (`target_pos`).
  3. `smart_split(text: str, max_chars: int = 15000) -> list[str]`: Đệ quy chia đôi văn bản cho đến khi mọi chunk đều $\le \text{max\_chars}$.

* **Mã nguồn chi tiết**:
  ```python
  # core/chunker.py
  import re

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

  def _find_best_cut_position(text: str, min_pos: int, max_pos: int, target_pos: int) -> int:
      # 1. Tìm \n\n
      double_newlines = [m.start() for m in re.finditer(r'\n[ \t]*\n', text) if min_pos <= m.start() <= max_pos]
      if double_newlines:
          return min(double_newlines, key=lambda pos: abs(pos - target_pos))

      # 2. Tìm \n
      single_newlines = [m.start() for m in re.finditer(r'\n', text) if min_pos <= m.start() <= max_pos]
      if single_newlines:
          return min(single_newlines, key=lambda pos: abs(pos - target_pos))

      # 3. Tìm dấu kết thúc câu (.!?。) kèm khoảng trắng
      sentence_ends = [m.end() for m in re.finditer(r'[\.!\?。！？]\s+', text) if min_pos <= m.end() <= max_pos]
      if sentence_ends:
          return min(sentence_ends, key=lambda pos: abs(pos - target_pos))

      # 4. Tìm dấu cách thông thường
      spaces = [m.start() for m in re.finditer(r'\s+', text) if min_pos <= m.start() <= max_pos]
      if spaces:
          return min(spaces, key=lambda pos: abs(pos - target_pos))

      return target_pos

  def smart_split(text: str, max_chars: int = 15000) -> list[str]:
      if len(text) <= max_chars:
          return [text]

      min_pos = int(len(text) * 0.2)
      max_pos = int(len(text) * 0.8)
      target_pos = int(len(text) * 0.5)

      split_pos = _find_best_cut_position(text, min_pos, max_pos, target_pos)

      part1 = text[:split_pos].rstrip()
      part2 = text[split_pos:].lstrip()

      result = []
      for part in (part1, part2):
          if len(part) > max_chars:
              result.extend(smart_split(part, max_chars))
          else:
              if part:
                  result.append(part)
      return result
  ```

* **Tệp test**: `tests/test_chunker.py`
  ```python
  from core.chunker import smart_split, count_words

  def test_count_words():
      assert count_words("Hello world, this is a test.") == 6
      assert count_words("Toàn Trí Độc Giả") == 4

  def test_smart_split_preserves_paragraphs():
      text = ("Đoạn văn 1.\n\n" * 100) + ("Đoạn văn 2.\n\n" * 100)
      chunks = smart_split(text, max_chars=500)
      assert len(chunks) > 1
      for c in chunks:
          assert len(c) <= 600
  ```
* **Lệnh chạy kiểm thử**: `pytest tests/test_chunker.py -v` (Kết quả: PASS).

---

### Task 1.3: Xây Dựng `core/prompt_engine.py` (Thư Viện Prompt `.txt` & Prompt Stacking)

* **Mục đích**: Nạp các file prompt `.txt`, hỗ trợ ghép linh hoạt Prompt Chính + các Prompt Bổ Sung và thay thế biến hệ thống.
* **Tệp tạo**: `core/prompt_engine.py`
* **Mã nguồn chi tiết**:
  ```python
  # core/prompt_engine.py
  from pathlib import Path
  from typing import Optional, List

  class PromptEngine:
      def __init__(self, prompts_dir: str = "prompts"):
          self.prompts_dir = Path(prompts_dir)
          self.prompts_dir.mkdir(parents=True, exist_ok=True)
          self._ensure_default_prompts()

      def _ensure_default_prompts(self):
          default_file = self.prompts_dir / "default_translation.txt"
          if not default_file.exists():
              default_file.write_text(
                  "BẠN LÀ MÁY DỊCH TIỂU THUYẾT CHUYÊN NGHIỆP SANG TIẾNG VIỆT.\n"
                  "QUY TẮC BẢO TOÀN ĐỊNH DẠNG TUYỆT ĐỐI:\n"
                  "1. Dịch chuẩn xác, tự nhiên theo văn phong tiếng Việt.\n"
                  "2. Giữ nguyên 100% các thẻ định dạng Markdown (#, **, _, >, ```), HTML và ký tự thụt đầu dòng.\n"
                  "3. Giữ nguyên các dòng trống giữa các đoạn văn.\n"
                  "4. KHÔNG thêm lời chào mừng hay giải thích thêm.\n\n"
                  "{{glossary_terms}}\n"
                  "{{previous_summary}}\n"
                  "{{additional_instructions}}\n\n"
                  "# VĂN BẢN NGUỒN CẦN DỊCH:\n"
                  "{{source_text}}",
                  encoding="utf-8"
              )

      def list_prompts(self) -> List[str]:
          """Trả về danh sách tên file prompt .txt có sẵn."""
          return sorted([f.name for f in self.prompts_dir.glob("*.txt")])

      def load_prompt(self, filename: str) -> str:
          file_path = self.prompts_dir / filename
          if not file_path.exists():
              raise FileNotFoundError(f"Không tìm thấy prompt file: {filename}")
          return file_path.read_text(encoding="utf-8")

      def assemble_prompt(
          self,
          source_text: str,
          main_prompt_file: str = "default_translation.txt",
          complementary_prompt_files: Optional[List[str]] = None,
          glossary_content: str = "",
          previous_summary: str = "",
      ) -> str:
          """Ghép prompt chính, prompt bổ sung và các biến động vào chunk."""
          main_template = self.load_prompt(main_prompt_file)

          # 1. Ghép các prompt bổ sung
          additional_text = ""
          if complementary_prompt_files:
              addons = []
              for cf in complementary_prompt_files:
                  addons.append(f"--- CHỈ THỊ BỔ SUNG ({cf}) ---\n{self.load_prompt(cf)}")
              additional_text = "\n\n" + "\n\n".join(addons)

          # 2. Xử lý phần Glossary
          glossary_block = ""
          if glossary_content.strip():
              glossary_block = f"# BẢNG THUẬT NGỮ CỐ ĐỊNH:\n{glossary_content.strip()}"

          # 3. Xử lý Previous Summary (Context Handoff từ silaBook)
          summary_block = ""
          if previous_summary.strip():
              summary_block = (
                  "<previous_chunk_handoff>\n"
                  "**Tóm tắt bối cảnh từ phần trước để tham khảo:**\n"
                  f"{previous_summary.strip()}\n"
                  "*LƯU Ý: Không lặp lại tóm tắt này vào bản dịch.*\n"
                  "</previous_chunk_handoff>"
              )

          # 4. Thay thế các biến động vào template
          rendered = main_template.replace("{{source_text}}", source_text)
          rendered = rendered.replace("{{glossary_terms}}", glossary_block)
          rendered = rendered.replace("{{previous_summary}}", summary_block)
          rendered = rendered.replace("{{additional_instructions}}", additional_text)

          return rendered
  ```

* **Tệp test**: `tests/test_prompt_engine.py` (Kiểm thử nạp file, thay biến, ghép prompt bổ sung).
* **Lệnh chạy kiểm thử**: `pytest tests/test_prompt_engine.py -v` (PASS).

---

### Task 1.4: Xây Dựng `core/key_pool.py` (Cụm Key Tự Động Cooldown 429)

* **Mục đích**: Tự động luân chuyển danh sách API key, đóng băng 60s đối với key bị HTTP 429, không làm đứt mạch dịch.
* **Tệp tạo**: `core/key_pool.py`
* **Mã nguồn chi tiết**:
  ```python
  # core/key_pool.py
  import time
  from threading import Lock
  from typing import List, Dict, Any, Optional

  class KeyPoolManager:
      def __init__(self, api_keys: List[str], cooldown_seconds: float = 60.0):
          self._lock = Lock()
          self.cooldown_seconds = cooldown_seconds
          # Lưu trạng thái: {"key": "AIza...", "cooldown_until": timestamp, "success_count": int}
          self._keys = [
              {"key": k.strip(), "cooldown_until": 0.0, "success_count": 0}
              for k in api_keys if k.strip()
          ]
          self._current_idx = 0

      def get_available_key(self) -> str:
          """Lấy key khả dụng theo vòng tròn Round-Robin."""
          with self._lock:
              if not self._keys:
                  raise ValueError("Key pool trống! Vui lòng nạp ít nhất một API key.")

              now = time.time()
              # Quét 1 vòng tìm key đã hết thời gian cooldown
              for _ in range(len(self._keys)):
                  item = self._keys[self._current_idx]
                  self._current_idx = (self._current_idx + 1) % len(self._keys)
                  if item["cooldown_until"] <= now:
                      return item["key"]

              # Nếu toàn bộ đều đang bị cooldown -> Chờ key có thời gian hồi phục gần nhất
              min_wait = min(item["cooldown_until"] for item in self._keys) - now
              wait_time = max(min_wait, 0.5)

          time.sleep(wait_time)
          return self.get_available_key()

      def mark_rate_limited(self, key_str: str):
          """Đánh dấu key bị HTTP 429, tạm khóa trong cooldown_seconds."""
          with self._lock:
              now = time.time()
              for item in self._keys:
                  if item["key"] == key_str:
                      item["cooldown_until"] = now + self.cooldown_seconds
                      break

      def mark_success(self, key_str: str):
          with self._lock:
              for item in self._keys:
                  if item["key"] == key_str:
                      item["success_count"] += 1
                      break

      def get_status(self) -> List[Dict[str, Any]]:
          """Trả về tình trạng sức khỏe của từng key để WebUI hiển thị."""
          with self._lock:
              now = time.time()
              status = []
              for item in self._keys:
                  is_cooling = item["cooldown_until"] > now
                  status.append({
                      "key_masked": item["key"][:8] + "..." + item["key"][-4:],
                      "is_ready": not is_cooling,
                      "cooldown_remaining": round(max(0.0, item["cooldown_until"] - now), 1),
                      "success_count": item["success_count"]
                  })
              return status
  ```

* **Tệp test**: `tests/test_key_pool.py` (Kiểm tra Round-robin, kiểm tra 429 lock 60s, kiểm tra phục hồi).
* **Lệnh chạy kiểm thử**: `pytest tests/test_key_pool.py -v` (PASS).

---

### Task 1.5: Xây Dựng `core/ai_client.py` (Adapter Gọi Gemini & OpenAI-Compatible Có Tự Động Failover)

* **Mục đích**: Gửi prompt đã ghép lên AI, tự động bắt lỗi 429 để chuyển key và thử lại.
* **Tệp tạo**: `core/ai_client.py`
* **Mã nguồn chi tiết**:
  ```python
  # core/ai_client.py
  import httpx
  import logging
  from typing import Optional, Tuple
  from core.key_pool import KeyPoolManager

  logger = logging.getLogger(__name__)

  class AIClient:
      def __init__(self, key_pool: KeyPoolManager, provider: str = "gemini", model: str = "gemini-2.5-flash", base_url: Optional[str] = None):
          self.key_pool = key_pool
          self.provider = provider
          self.model = model
          self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"

      async def generate_text(self, prompt: str, max_retries: int = 5) -> str:
          for attempt in range(max_retries):
              api_key = self.key_pool.get_available_key()
              try:
                  if self.provider == "gemini":
                      result = await self._call_gemini(prompt, api_key)
                  else:
                      result = await self._call_openai_compatible(prompt, api_key)

                  self.key_pool.mark_success(api_key)
                  return result
              except httpx.HTTPStatusError as e:
                  if e.response.status_code == 429:
                      logger.warning(f"⚠️ Key gặp lỗi 429 (Rate Limit), đang chuyển key... (Thử lại {attempt+1}/{max_retries})")
                      self.key_pool.mark_rate_limited(api_key)
                  else:
                      logger.error(f"❌ Lỗi HTTP: {e.response.status_code} - {e.response.text}")
                      raise e
              except Exception as e:
                  logger.error(f"❌ Lỗi ngoại lệ khi gọi AI: {str(e)}")
                  raise e

          raise RuntimeError("Tất cả API keys trong pool đều bị kiệt sức hoặc rate limit!")

      async def _call_gemini(self, prompt: str, api_key: str) -> str:
          url = f"{self.base_url}/models/{self.model}:generateContent?key={api_key}"
          payload = {
              "contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.3}
          }
          async with httpx.AsyncClient(timeout=120.0) as client:
              resp = await client.post(url, json=payload)
              resp.raise_for_status()
              data = resp.json()
              return data["candidates"][0]["content"]["parts"][0]["text"]

      async def _call_openai_compatible(self, prompt: str, api_key: str) -> str:
          url = f"{self.base_url}/chat/completions"
          headers = {"Authorization": f"Bearer {api_key}"}
          payload = {
              "model": self.model,
              "messages": [{"role": "user", "content": prompt}],
              "temperature": 0.3
          }
          async with httpx.AsyncClient(timeout=120.0) as client:
              resp = await client.post(url, json=payload, headers=headers)
              resp.raise_for_status()
              data = resp.json()
              return data["choices"][0]["message"]["content"]
  ```

---

### Task 1.6: Xây Dựng `core/storage.py` (1 File SQLite Duy Nhất Cho Toàn Bộ Hệ Thống)

* **Mục đích**: Thay thế toàn bộ hệ thống phân mảnh cũ (`tasks.db` + hàng chục file `.db` riêng của từng file) bằng **1 file SQLite duy nhất** lưu trữ gọn nhẹ.
* **Tệp tạo**: `core/storage.py`
* **Mã nguồn chi tiết**:
  ```python
  # core/storage.py
  import sqlite3
  from pathlib import Path
  from typing import Optional, Dict, Any, List

  class SingleStorage:
      def __init__(self, db_path: str = "workspace/translator.db"):
          self.db_path = Path(db_path)
          self.db_path.parent.mkdir(parents=True, exist_ok=True)
          self._init_tables()

      def _get_connection(self) -> sqlite3.Connection:
          conn = sqlite3.connect(self.db_path)
          conn.row_factory = sqlite3.Row
          conn.execute("PRAGMA journal_mode=WAL")
          return conn

      def _init_tables(self):
          with self._get_connection() as conn:
              conn.executescript("""
                  CREATE TABLE IF NOT EXISTS projects (
                      slug TEXT PRIMARY KEY,
                      title TEXT NOT NULL,
                      created_at TEXT NOT NULL
                  );
                  CREATE TABLE IF NOT EXISTS file_checkpoints (
                      project_slug TEXT NOT NULL,
                      filename TEXT NOT NULL,
                      chunk_index INTEGER NOT NULL,
                      source_text TEXT NOT NULL,
                      translated_text TEXT,
                      status TEXT NOT NULL DEFAULT 'done',
                      updated_at TEXT NOT NULL,
                      PRIMARY KEY (project_slug, filename, chunk_index)
                  );
              """)

      def save_chunk_result(self, project_slug: str, filename: str, chunk_index: int, source_text: str, translated_text: str):
          import datetime
          now = datetime.datetime.now(datetime.timezone.utc).isoformat()
          with self._get_connection() as conn:
              conn.execute("""
                  INSERT OR REPLACE INTO file_checkpoints (project_slug, filename, chunk_index, source_text, translated_text, status, updated_at)
                  VALUES (?, ?, ?, ?, ?, 'done', ?)
              """, (project_slug, filename, chunk_index, source_text, translated_text, now))

      def get_saved_chunks(self, project_slug: str, filename: str) -> Dict[int, str]:
          with self._get_connection() as conn:
              rows = conn.execute("""
                  SELECT chunk_index, translated_text FROM file_checkpoints
                  WHERE project_slug = ? AND filename = ?
                  ORDER BY chunk_index ASC
              """, (project_slug, filename)).fetchall()
              return {row["chunk_index"]: row["translated_text"] for row in rows}
  ```

---

## 3. TIÊU CHÍ HOÀN TẤT PHASE 1 (PHASE 1 ACCEPTANCE CRITERIA)

Để nghiệm thu và tuyên bố Phase 1 hoàn tất, tất cả các bài kiểm tra sau phải vượt qua 100%:
1. `pytest tests/test_chunker.py` $\to$ Đếm từ chuẩn $O(1)$, chia đoạn bảo toàn `\n\n` và câu văn hoàn hảo.
2. `pytest tests/test_prompt_engine.py` $\to$ Đọc file prompt `.txt`, tự động dồn prompt bổ sung vào template.
3. `pytest tests/test_key_pool.py` $\to$ Đạt cơ chế xoay vòng key và tự động chuyển trạng thái cooldown 60s khi gặp 429.
4. `pytest tests/test_storage.py` $\to$ Lưu và đọc lại checkpoint từ file SQLite duy nhất mà không bị lỗi lock database.
