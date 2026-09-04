# 03. KẾ HOẠCH TRIỂN KHAI PHASE 1 CHI TIẾT TỈ MỈ (CLI WORKING CORE)
> **Mục tiêu**: Xây dựng bộ mã nguồn cốt lõi tối giản, chỉ dùng `httpx` (+ `sqlite3` stdlib), loại bỏ hoàn toàn FastAPI/uvicorn/pydantic và storage trạng thái chunk, **sử dụng được ngay lập tức từ dòng lệnh CLI để dịch file với Gemini + OpenAI-compatible**.  
> **Cam kết**: Đầy đủ mã nguồn mẫu cho toàn bộ các module, bộ test hoàn chỉnh (mock test cả 2 providers), kiểm tra an toàn đường dẫn và chia thành 5 mốc triển khai nhỏ.
> **Phiên bản**: v2.4 (06/09/2026) — providers.json SSOT + dynamic model listing (docs/06).

---

## 1. DANH SÁCH FILE CỦA PHASE 1

```text
content-translator/
├── pyproject.toml              # CHỈ CẦN httpx (dev: pytest, pytest-asyncio) + sqlite3 stdlib
├── .gitignore                  # Bỏ qua workspace/ và config/keys.json
├── config/
│   ├── config.json             # Prefs app (timeout, max_chars)
│   ├── keys.json               # Legacy (migrate 1 chiều sang providers.json)
│   └── providers.json          # SSOT providers + keys + default_model (gitignore)
├── core/
│   ├── __init__.py
│   ├── config.py               # Lớp nạp prefs JSON mỏng (tính theo PROJECT_ROOT)
│   ├── provider_manager.py     # SSOT providers.json: atomic write, mask, dynamic models, validation (docs/06)
│   ├── key_rotator.py          # Module xoay key tối giản (dùng chung 2 providers)
│   ├── chunker.py              # Cắt chunk tự nhiên, xử lý văn bản rỗng/ngắn/không dấu cách
│   ├── prompt_engine.py        # Nạp prompt .txt, bảo toàn Unicode tiếng Việt
│   ├── ai_base.py              # Interface AIClient chung (Protocol)
│   ├── ai_client.py            # Client Gemini REST (timeout, lỗi mạng, xoay key khi 429)
│   ├── openai_client.py        # Client OpenAI-compatible REST (tái dùng KeyRotator)
│   ├── app_db.py + schema.sql  # SQLite index projects/files/runs (không checkpoint)
│   └── file_handler.py         # Đọc/ghi file an toàn (kiểm tra relative_to, chống path traversal)
├── prompts/
│   └── default_translation.txt # Prompt chính dịch chuẩn
├── tests/
│   ├── __init__.py
│   ├── test_chunker.py         # Test cắt chunk, văn bản rỗng, văn bản ngắn
│   ├── test_key_rotator.py     # Test 1 key, nhiều key, danh sách rỗng
│   ├── test_prompt_engine.py   # Test nạp prompt và giữ nguyên Unicode
│   ├── test_provider_manager.py # Test atomic/mask/sentinel/namespace/cache/migration (mock httpx)
│   ├── test_file_handler.py    # Test chống path traversal .. và /
│   ├── test_app_db.py          # Test tạo bảng + ghi files/runs
│   ├── test_ai_client.py       # Mock test httpx Gemini: 200, 429, hết key, timeout, lỗi mạng, response rỗng
│   └── test_openai_client.py   # Mock test httpx OpenAI-compatible: 200, 429 failover, hết key
└── run.py                      # Script CLI: --provider/--model explicit, không fallback
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

### Task 1.2: `core/config.py` (Lớp Cấu Hình Cực Mỏng & Kiểm Tra Hợp Lệ)
* **Mã nguồn** (hỗ trợ 2 nhóm key + danh sách models chọn explicit):
  ```python
  # core/config.py
  import os
  import json
  from pathlib import Path
  from typing import List, Dict, Any

  # Định vị đường dẫn tuyệt đối theo thư mục gốc của project
  PROJECT_ROOT = Path(__file__).resolve().parent.parent
  CONFIG_DIR = PROJECT_ROOT / "config"
  CONFIG_FILE = CONFIG_DIR / "config.json"
  KEYS_FILE = CONFIG_DIR / "keys.json"

  DEFAULT_CONFIG = {
      "default_provider": "gemini",
      "default_model": "gemini-2.5-flash",
      "max_chunk_chars": 16000,
      "timeout_seconds": 90,
      "providers": {
          "gemini": {"models": ["gemini-2.5-flash", "gemini-2.5-flash-lite"]},
          "openai_compat": {"base_url": "https://openrouter.ai/api/v1", "models": ["deepseek-chat"]}
      }
  }

  class AppConfig:
      def __init__(self):
          CONFIG_DIR.mkdir(parents=True, exist_ok=True)
          self._ensure_files()

      def _ensure_files(self):
          if not CONFIG_FILE.exists():
              CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2, ensure_ascii=False), encoding="utf-8")
          if not KEYS_FILE.exists():
              KEYS_FILE.write_text(json.dumps({"gemini_keys": [], "openai_compat_keys": []}, indent=2), encoding="utf-8")

      def get_config(self) -> Dict[str, Any]:
          cfg = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy rẻ, khỏi import copy
          if CONFIG_FILE.exists():
              try:
                  data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                  if isinstance(data, dict):
                      cfg.update(data)
              except Exception:
                  pass

          # Kiểm tra tính hợp lệ tối thiểu
          try:
              max_chars = int(cfg.get("max_chunk_chars", 16000))
              cfg["max_chunk_chars"] = max_chars if max_chars > 0 else 16000
          except (ValueError, TypeError):
              cfg["max_chunk_chars"] = 16000

          try:
              timeout = float(cfg.get("timeout_seconds", 90))
              cfg["timeout_seconds"] = timeout if timeout > 0 else 90.0
          except (ValueError, TypeError):
              cfg["timeout_seconds"] = 90.0

          return cfg

      def _keys_from(self, data: dict, field: str, env_name: str) -> List[str]:
          keys = [k.strip() for k in data.get(field, []) if isinstance(k, str) and k.strip()]
          for k in os.getenv(env_name, "").split(","):
              kc = k.strip()
              if kc and kc not in keys:
                  keys.append(kc)
          return keys

      def get_keys(self, provider: str) -> List[str]:
          try:
              data = json.loads(KEYS_FILE.read_text(encoding="utf-8")) if KEYS_FILE.exists() else {}
          except Exception:
              data = {}
          if not isinstance(data, dict):
              data = {}
          if provider == "openai_compat":
              return self._keys_from(data, "openai_compat_keys", "OPENAI_COMPAT_KEYS")
          return self._keys_from(data, "gemini_keys", "GEMINI_API_KEYS")

      def get_gemini_keys(self) -> List[str]:  # giữ tương thích test cũ
          return self.get_keys("gemini")

      def save_keys(self, provider: str, keys: List[str]):
          try:
              data = json.loads(KEYS_FILE.read_text(encoding="utf-8")) if KEYS_FILE.exists() else {}
          except Exception:
              data = {}
          if not isinstance(data, dict):
              data = {}
          field = "openai_compat_keys" if provider == "openai_compat" else "gemini_keys"
          data[field] = [k.strip() for k in keys if k.strip()]
          KEYS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

      def save_gemini_keys(self, keys: List[str]):
          self.save_keys("gemini", keys)
  ```

---

### Task 1.3: `core/key_rotator.py` (Xoay Vòng Key Tối Giản)
* **Đặc tả logic**:
  * Danh sách key rỗng $\to$ ném `ValueError` khi lấy key.
  * Danh sách có 1 key duy nhất $\to$ khi gặp 429, `try_next_key()` trả về `None` ngay lập tức!
  * Danh sách nhiều key $\to$ chuyển lần lượt, mỗi key chỉ thử tối đa 1 lần cho 1 chunk.
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
              return None  # Đã thử hết toàn bộ key khả dụng

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

  def _find_best_cut(text: str, min_pos: int, max_pos: int, target_pos: int) -> int:
      # 1. Dấu xuống dòng đôi \n\n (ngắt đoạn văn)
      doubles = [m.start() for m in re.finditer(r'\n[ \t]*\n', text) if min_pos <= m.start() <= max_pos]
      if doubles:
          return min(doubles, key=lambda p: abs(p - target_pos))

      # 2. Dấu xuống dòng đơn \n
      singles = [m.start() for m in re.finditer(r'\n', text) if min_pos <= m.start() <= max_pos]
      if singles:
          return min(singles, key=lambda p: abs(p - target_pos))

      # 3. Kết thúc câu (. ! ? 。！？) kèm khoảng trắng
      sentences = [m.end() for m in re.finditer(r'[\.!\?。！？]\s+', text) if min_pos <= m.end() <= max_pos]
      if sentences:
          return min(sentences, key=lambda p: abs(p - target_pos))

      # 4. Khoảng trắng thông thường
      spaces = [m.start() for m in re.finditer(r'\s+', text) if min_pos <= m.start() <= max_pos]
      if spaces:
          return min(spaces, key=lambda p: abs(p - target_pos))

      # 5. Cắt cứng tại 50% nếu văn bản không có khoảng trắng
      return target_pos

  def split_text(text: str, max_chars: int = 16000) -> List[str]:
      """Chia nhỏ văn bản thành các chunk tự nhiên <= max_chars.
      Xử lý được văn bản rỗng, văn bản ngắn <= max_chars, văn bản không có khoảng trắng."""
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

  PROJECT_ROOT = Path(__file__).resolve().parent.parent
  DEFAULT_PROMPTS_DIR = PROJECT_ROOT / "prompts"

  class PromptEngine:
      def __init__(self, prompts_dir: Path = DEFAULT_PROMPTS_DIR):
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
      def __init__(self, key_rotator: KeyRotator, model: str = "gemini-2.5-flash", timeout_seconds: float = 90.0):
          self.rotator = key_rotator
          self.model = model
          self.timeout = float(timeout_seconds)

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
                  async with httpx.AsyncClient(timeout=self.timeout) as client:
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
                      parts = candidates[0].get("content", {}).get("parts", [])
                      if not parts or "text" not in parts[0]:
                          raise ValueError("Cấu trúc response từ AI không chứa trường text!")
                      return parts[0]["text"]

              except httpx.ConnectError:
                  raise ConnectionError("❌ LỖI KẾT NỐI MẠNG! Không thể kết nối tới Google Gemini. Vui lòng kiểm tra mạng.")
              except httpx.TimeoutException:
                  raise TimeoutError(f"❌ QUÁ THỜI GIAN CHỜ ({self.timeout}s)! AI không phản hồi kịp.")
              except httpx.HTTPStatusError as e:
                  if e.response.status_code != 429:
                      raise RuntimeError(f"❌ LỖI TỪ GEMINI (Mã HTTP {e.response.status_code}): {e.response.text}")
                  raise e
  ```

### Task 1.6b: `core/ai_base.py` + `core/openai_client.py` (Provider thứ 2, chung interface)
* **Mã nguồn**:
  ```python
  # core/ai_base.py
  from typing import Protocol

  class AIClient(Protocol):
      async def translate_chunk(self, prompt: str) -> str: ...
  ```
  ```python
  # core/openai_client.py — OpenAI-compatible (OpenRouter/Groq/DeepSeek/Ollama), httpx thuần
  import httpx, logging
  from core.key_rotator import KeyRotator
  logger = logging.getLogger(__name__)

  class OpenAICompatClient:
      def __init__(self, key_rotator: KeyRotator, model: str, base_url: str, timeout_seconds: float = 90.0):
          self.rotator = key_rotator
          self.model = model
          self.base_url = base_url.rstrip("/")
          self.timeout = float(timeout_seconds)

      async def translate_chunk(self, prompt: str) -> str:
          self.rotator.start_chunk_attempt()
          while True:
              key = self.rotator.get_current_key()
              url = f"{self.base_url}/chat/completions"
              payload = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.3}
              headers = {"Authorization": f"Bearer {key}"}
              try:
                  async with httpx.AsyncClient(timeout=self.timeout) as client:
                      resp = await client.post(url, json=payload, headers=headers)
                      if resp.status_code == 429:
                          nxt = self.rotator.try_next_key()
                          if nxt is not None:
                              logger.warning("⚠️ Key OpenAI-compat bị 429, đổi key...")
                              continue
                          raise RuntimeError("❌ TẤT CẢ OPENAI-COMPAT KEY ĐỀU 429! Chạy lại sau.")
                      resp.raise_for_status()
                      data = resp.json()
                      text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                      if not text or not text.strip():
                          raise ValueError("AI không trả về nội dung (response rỗng)!")
                      return text
              except httpx.ConnectError:
                  raise ConnectionError("❌ LỖI KẾT NỐI tới OpenAI-compatible endpoint!")
              except httpx.TimeoutException:
                  raise TimeoutError(f"❌ TIMEOUT ({self.timeout}s)!")
  ```
* **Quy tắc**: CLI/WebUI truyền explicit `--provider/--model`. Không fallback Gemini ↔ OpenAI.

### Task 1.6c: `core/app_db.py` + `core/schema.sql` (SQLite index từ ngày đầu)
* **Mã nguồn**:
  ```python
  # core/schema.sql
  # CREATE TABLE IF NOT EXISTS projects(slug TEXT PRIMARY KEY, title TEXT, created_at TEXT);
  # CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY, project_slug TEXT, filename TEXT,
  #   size_bytes INT, char_count INT, chunk_count INT, status TEXT DEFAULT 'new',
  #   updated_at TEXT, UNIQUE(project_slug, filename));
  # CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, file_id INT, provider TEXT,
  #   model TEXT, started_at TEXT, finished_at TEXT, status TEXT, error TEXT);
  ```
  ```python
  # core/app_db.py — stdlib sqlite3, không dependency
  import sqlite3, datetime
  from pathlib import Path
  PROJECT_ROOT = Path(__file__).resolve().parent.parent
  DB_PATH = PROJECT_ROOT / "workspace" / "app.db"
  def get_db():
      DB_PATH.parent.mkdir(parents=True, exist_ok=True)
      con = sqlite3.connect(DB_PATH)
      con.executescript((Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8"))
      return con
  def log_run(provider: str, model: str, status: str, error: str = ""):
      con = get_db()
      now = datetime.datetime.now().isoformat(timespec="seconds")
      con.execute("INSERT INTO runs(provider, model, started_at, finished_at, status, error) VALUES (?,?,?,?,?,?)",
                  (provider, model, now, now, status, error))
      con.commit(); con.close()
  ```

---

### Task 1.7: `core/file_handler.py` (Đọc/Ghi File Có Chống Path Traversal Chặt Chẽ)
* **Kiểm tra an toàn**:
  * Sanitize tên: Không rỗng, không chứa `..`, `/`, `\`.
  * Xác thực đường dẫn bằng `path.resolve().relative_to(base_dir.resolve())`.
* **Mã nguồn**:
  ```python
  # core/file_handler.py
  from pathlib import Path
  from typing import List

  PROJECT_ROOT = Path(__file__).resolve().parent.parent
  DEFAULT_WORKSPACE = PROJECT_ROOT / "workspace"

  class SafeFileHandler:
      def __init__(self, workspace_dir: Path = DEFAULT_WORKSPACE):
          self.base_dir = Path(workspace_dir).resolve()
          self.base_dir.mkdir(parents=True, exist_ok=True)

      def _sanitize_name(self, name: str) -> str:
          if not name or not name.strip():
              raise ValueError("Tên không được để trống!")
          clean = name.strip()
          if ".." in clean or "/" in clean or "\\" in clean:
              raise ValueError(f"Tên chứa ký tự không hợp lệ (path traversal): {name}")
          return clean

      def _validate_path(self, target_path: Path) -> Path:
          resolved = target_path.resolve()
          try:
              resolved.relative_to(self.base_dir)
          except ValueError:
              raise ValueError(f"Đường dẫn không an toàn, nằm ngoài workspace: {target_path}")
          return resolved

      def get_project_dir(self, slug: str) -> Path:
          clean_slug = self._sanitize_name(slug)
          p = self._validate_path(self.base_dir / "projects" / clean_slug)
          (p / "sources").mkdir(parents=True, exist_ok=True)
          (p / "translated").mkdir(parents=True, exist_ok=True)
          return p

      def get_source_path(self, slug: str, filename: str) -> Path:
          clean_file = self._sanitize_name(filename)
          return self._validate_path(self.get_project_dir(slug) / "sources" / clean_file)

      def get_translated_path(self, slug: str, filename: str) -> Path:
          clean_file = self._sanitize_name(filename)
          return self._validate_path(self.get_project_dir(slug) / "translated" / clean_file)

      def list_sources(self, slug: str) -> List[str]:
          sources_dir = self.get_project_dir(slug) / "sources"
          return sorted([f.name for f in sources_dir.iterdir() if f.is_file()])

      def read_source(self, slug: str, filename: str) -> str:
          file_path = self.get_source_path(slug, filename)
          if not file_path.exists():
              raise FileNotFoundError(f"Không tìm thấy file nguồn: {file_path}")
          return file_path.read_text(encoding="utf-8", errors="replace")

      def save_translated(self, slug: str, filename: str, content: str):
          out_path = self.get_translated_path(slug, filename)
          out_path.write_text(content, encoding="utf-8")
  ```

---

### Task 1.8: `run.py` (Script CLI — provider/model từ providers.json)
* **Cách dùng mới (provider = id trong providers.json, model = default_model hoặc override)**:
  ```text
  python run.py input.txt output.txt                        # dùng active provider + default_model
  python run.py input.txt output.txt --provider openai-compat --model deepseek-chat
  python run.py --project Truyen --file ch01.md --provider gemini-default
  ```
  Không fallback ngầm. Model rỗng → báo mở WebUI Cấu Hình chọn từ danh sách live.
* **Mã nguồn** (rút gọn phần đổi so với v2.2 — giữ nguyên chunker/prompt/ghép `\n\n`/dừng-ngay):
  ```python
  # run.py - trích đoạn chọn client
  import argparse
  from core.config import AppConfig
  from core.key_rotator import KeyRotator
  from core.ai_client import GeminiClient
  from core.openai_client import OpenAICompatClient
  from core.app_db import log_run

  ap = argparse.ArgumentParser()
  ap.add_argument("input", nargs="?"); ap.add_argument("output", nargs="?")
  ap.add_argument("--project"); ap.add_argument("--file")
  ap.add_argument("--provider"); ap.add_argument("--model"); ap.add_argument("--prompt", default="default_translation.txt")
  args = ap.parse_args()

  cfg = AppConfig().get_config()
  provider = args.provider or cfg.get("default_provider", "gemini")
  model = args.model or cfg.get("default_model", "gemini-2.5-flash")
  keys = AppConfig().get_keys(provider)  # hỏi + save nếu trống (giữ logic cũ)
  rotator = KeyRotator(keys)
  if provider == "openai_compat":
      base_url = cfg["providers"]["openai_compat"]["base_url"]
      ai = OpenAICompatClient(rotator, model=model, base_url=base_url, timeout_seconds=cfg["timeout_seconds"])
  else:
      ai = GeminiClient(rotator, model=model, timeout_seconds=cfg["timeout_seconds"])
  # ... gửi tuần tự từng chunk như cũ, thành công log_run(provider, model, "ok"), lỗi log_run(..., "error", str(e)) rồi sys.exit(1)
  ```

---

## 3. BỘ TEST TỰ ĐỘNG ĐẦY ĐỦ (BAO GỒM MOCK TEST 2 PROVIDERS + APP_DB)

### 3.1. `tests/test_chunker.py`
```python
import pytest
from core.chunker import split_text

def test_empty_and_whitespace():
    assert split_text("") == []
    assert split_text("   \n\n  ") == []

def test_short_text():
    text = "Đoạn văn ngắn."
    assert split_text(text, max_chars=1000) == [text]

def test_split_at_double_newline():
    p1 = "Đoạn 1.\n\n" * 50
    p2 = "Đoạn 2.\n\n" * 50
    chunks = split_text(p1 + p2, max_chars=len(p1) + 100)
    assert len(chunks) >= 2

def test_split_without_spaces():
    text = "A" * 1000
    chunks = split_text(text, max_chars=600)
    assert len(chunks) == 2
```

### 3.2. `tests/test_key_rotator.py`
```python
import pytest
from core.key_rotator import KeyRotator

def test_empty_keys():
    rotator = KeyRotator([])
    assert not rotator.has_keys()
    with pytest.raises(ValueError):
        rotator.get_current_key()

def test_single_key_stops_on_429():
    rotator = KeyRotator(["KEY_A"])
    rotator.start_chunk_attempt()
    assert rotator.get_current_key() == "KEY_A"
    # Lần 429 đầu tiên với 1 key -> phải trả về None ngay!
    assert rotator.try_next_key() is None

def test_multiple_keys_rotation():
    rotator = KeyRotator(["KEY_1", "KEY_2", "KEY_3"])
    rotator.start_chunk_attempt()
    assert rotator.get_current_key() == "KEY_1"
    assert rotator.try_next_key() == "KEY_2"
    assert rotator.try_next_key() == "KEY_3"
    assert rotator.try_next_key() is None  # Đã hết key

def test_reset_chunk_attempt():
    rotator = KeyRotator(["KEY_1", "KEY_2"])
    rotator.start_chunk_attempt()
    rotator.try_next_key()
    # Sang chunk mới
    rotator.start_chunk_attempt()
    assert rotator.try_next_key() is not None
```

### 3.3. `tests/test_prompt_engine.py` (Bổ sung — trước đây thiếu)
```python
from pathlib import Path
from core.prompt_engine import PromptEngine

def test_unicode_preserved(tmp_path):
    eng = PromptEngine(tmp_path)
    out = eng.assemble_prompt("Tiếng Việt có dấu: ễ ộ ư đ.")
    assert "ễ" in out and "{{source_text}}" not in out

def test_missing_prompt_raises(tmp_path):
    import pytest
    eng = PromptEngine(tmp_path)
    with pytest.raises(FileNotFoundError):
        eng.load_prompt("khong_ton_tai.txt")
```

### 3.4. `tests/test_app_db.py`
```python
from core.app_db import get_db
def test_tables_created(tmp_path, monkeypatch):
    import core.app_db as m
    monkeypatch.setattr(m, "DB_PATH", tmp_path / "app.db")
    con = m.get_db()
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"projects", "files", "runs"} <= tables
    con.close()
```

### 3.5. `tests/test_openai_client.py` (Mock OpenAI-compatible)
```python
import pytest, httpx
from unittest.mock import AsyncMock, patch
from core.key_rotator import KeyRotator
from core.openai_client import OpenAICompatClient

def _mk(text="ok", status=200):
    return httpx.Response(status_code=status,
        json={"choices": [{"message": {"content": text}}]},
        request=httpx.Request("POST", "http://test"))

@pytest.mark.asyncio
async def test_openai_success():
    c = OpenAICompatClient(KeyRotator(["K1"]), model="m", base_url="http://x")
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as p:
        p.return_value = _mk("Bản dịch")
        assert await c.translate_chunk("Hi") == "Bản dịch"

@pytest.mark.asyncio
async def test_openai_429_failover():
    c = OpenAICompatClient(KeyRotator(["BAD", "GOOD"]), model="m", base_url="http://x")
    r429 = httpx.Response(status_code=429, request=httpx.Request("POST", "http://test"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as p:
        p.side_effect = [r429, _mk("ok2")]
        assert await c.translate_chunk("Hi") == "ok2"
```

### 3.6. `tests/test_file_handler.py`
```python
import pytest
from pathlib import Path
from core.file_handler import SafeFileHandler

def test_path_traversal_detection(tmp_path):
    handler = SafeFileHandler(tmp_path)
    with pytest.raises(ValueError):
        handler.get_project_dir("../evil_proj")
    with pytest.raises(ValueError):
        handler.get_source_path("my_proj", "../../../etc/passwd")
    with pytest.raises(ValueError):
        handler.get_source_path("my_proj", "sub/file.txt")

def test_valid_file_handling(tmp_path):
    handler = SafeFileHandler(tmp_path)
    p_dir = handler.get_project_dir("my_proj")
    assert (p_dir / "sources").exists()
    src_file = handler.get_source_path("my_proj", "ch01.md")
    src_file.write_text("Nội dung gốc", encoding="utf-8")
    assert handler.read_source("my_proj", "ch01.md") == "Nội dung gốc"
```

### 3.4. `tests/test_ai_client.py` (Mock httpx Không Gọi API Thật)
```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from core.key_rotator import KeyRotator
from core.ai_client import GeminiClient

@pytest.mark.asyncio
async def test_successful_translation():
    rotator = KeyRotator(["KEY_1"])
    client = GeminiClient(rotator)

    mock_resp = httpx.Response(
        status_code=200,
        json={"candidates": [{"content": {"parts": [{"text": "Bản dịch tiếng Việt"}]}}]},
        request=httpx.Request("POST", "http://test")
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.translate_chunk("Hello")
        assert result == "Bản dịch tiếng Việt"

@pytest.mark.asyncio
async def test_429_failover_to_next_key():
    rotator = KeyRotator(["KEY_BAD", "KEY_GOOD"])
    client = GeminiClient(rotator)

    resp_429 = httpx.Response(status_code=429, request=httpx.Request("POST", "http://test"))
    resp_200 = httpx.Response(
        status_code=200,
        json={"candidates": [{"content": {"parts": [{"text": "Thành công ở key 2"}]}}]},
        request=httpx.Request("POST", "http://test")
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [resp_429, resp_200]
        result = await client.translate_chunk("Hello")
        assert result == "Thành công ở key 2"

@pytest.mark.asyncio
async def test_all_keys_429_exhausted():
    rotator = KeyRotator(["KEY_1"])
    client = GeminiClient(rotator)

    resp_429 = httpx.Response(status_code=429, request=httpx.Request("POST", "http://test"))
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = resp_429
        with pytest.raises(RuntimeError, match="TẤT CẢ API KEY ĐỀU BỊ LỖI 429"):
            await client.translate_chunk("Hello")

@pytest.mark.asyncio
async def test_network_connect_error():
    rotator = KeyRotator(["KEY_1"])
    client = GeminiClient(rotator)

    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Network down")):
        with pytest.raises(ConnectionError, match="LỖI KẾT NỐI MẠNG"):
            await client.translate_chunk("Hello")

@pytest.mark.asyncio
async def test_empty_candidates_safety_block():
    rotator = KeyRotator(["KEY_1"])
    client = GeminiClient(rotator)

    mock_resp = httpx.Response(
        status_code=200,
        json={"candidates": []},
        request=httpx.Request("POST", "http://test")
    )
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        with pytest.raises(ValueError, match="bộ lọc an toàn"):
            await client.translate_chunk("Hello")
```

---

## 4. NĂM MỐC TRIỂN KHAI NHỎ (IMPLEMENTATION MILESTONES)

Thay vì sinh toàn bộ mã một lần, việc code được chia thành **5 mốc rất nhỏ**:

* **MỐC 0: Config + providers.json SSOT + app.db**:
  * Tạo `pyproject.toml`, `.gitignore`, `core/config.py`, `core/provider_manager.py` (docs/06), `core/app_db.py`, `core/schema.sql`.
  * Chạy test: `pytest tests/test_provider_manager.py tests/test_app_db.py` $\to$ PASS.
* **MỐC 1: Chunker & Prompt Engine**:
  * Tạo `pyproject.toml`, `.gitignore`, `core/chunker.py`, `core/prompt_engine.py`.
  * Chạy test: `pytest tests/test_chunker.py tests/test_prompt_engine.py` $\to$ PASS.
  * Chứng minh luồng: `Văn bản nguồn -> Chunks -> Prompt`.

* **MỐC 2: KeyRotator & 2 Clients Độc Lập**:
  * Tạo `core/key_rotator.py`, `core/ai_base.py`, `core/ai_client.py`, `core/openai_client.py`.
  * Chạy test: `pytest tests/test_key_rotator.py tests/test_ai_client.py tests/test_openai_client.py` $\to$ PASS.

* **MỐC 3: CLI 1 Chunk (Vertical Slice Nhỏ Nhất)**:
  * Tạo `core/file_handler.py` và phiên bản `run.py` dịch 1 chunk duy nhất với `--provider/--model` explicit.
  * Chạy thử với file nhỏ 1 câu thực tế để xác nhận gọi AI thật thành công (thử cả 2 providers).

* **MỐC 4: Hoàn Thiện CLI Đầy Đủ & Ghi File**:
  * Hoàn thiện `run.py`: cắt 2-3 chunk, gửi tuần tự, ghép nối `\n\n`, ghi ra file `output.txt` hoặc `translated/{file}`, ghi log `runs` vào app.db.
  * Kiểm tra failure policy: Nếu 1 chunk lỗi thì dừng ngay lập tức, không lưu dở dang, không fallback model.
