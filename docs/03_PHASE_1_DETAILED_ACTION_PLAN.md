# 03. KẾ HOẠCH TRIỂN KHAI PHASE 1 CHI TIẾT TỈ MỈ (MINIMAL WORKING CORE)
> **Mục tiêu**: Xây dựng bộ mã nguồn cốt lõi tối giản, cắt bỏ hoàn toàn storage trạng thái và checkpoint, **sử dụng được ngay lập tức để dịch từ dòng lệnh CLI mà không cần chờ đến Phase 2**.  
> **Chuẩn mực**: Chi tiết từng file, có sẵn mã nguồn mẫu sẵn sàng triển khai.

---

## 1. CẤU TRÚC THƯ MỤC CỦA PHASE 1

```text
content-translator/
├── pyproject.toml              # Dependencies tối giản (FastAPI, httpx, pydantic)
├── config/
│   ├── config.json             # Cấu hình chung (model, timeout, max_chars)
│   └── keys.json               # Dữ liệu nhạy cảm (API keys) -> nằm trong .gitignore
├── core/
│   ├── __init__.py
│   ├── config.py               # Lớp nạp cấu hình cực mỏng
│   ├── key_rotator.py          # Module xoay key độc lập (gửi -> 429 -> đổi key 1 lần -> dừng)
│   ├── chunker.py              # Cắt chunk thông minh kèm metadata đánh số
│   ├── prompt_engine.py        # Nạp prompt .txt (từ prompts/ chung hoặc assets/ dự án)
│   ├── ai_client.py            # Client gọi Gemini / OpenAI (timeout, lỗi mạng, failover key)
│   └── file_handler.py         # Lớp đọc/ghi file sources/ và translated/
├── prompts/
│   └── default_translation.txt # Prompt chính dịch chuẩn
├── tests/
│   ├── test_key_rotator.py     # Test chuyển key khi 429
│   ├── test_chunker.py         # Test cắt chunk kèm metadata và ghép nối
│   └── test_prompt_engine.py   # Test nạp và ghép prompt
└── run.py                      # Script CLI thực thi dịch ngay trong Phase 1
```

---

## 2. CHI TIẾT MÃ NGUỒN TỪNG FILE ĐỂ SINH MÃ ĐƯỢC NGAY

### Task 1.1: `pyproject.toml` & Cấu hình `.gitignore`
* **File**: `pyproject.toml`
  ```toml
  [project]
  name = "content-translator"
  version = "1.0.0"
  description = "Minimalist AI Content Translator"
  requires-python = ">=3.12"
  dependencies = [
      "fastapi>=0.110.0",
      "uvicorn>=0.28.0",
      "pydantic>=2.6.0",
      "httpx>=0.27.0",
  ]
  [project.optional-dependencies]
  dev = ["pytest>=8.0.0", "pytest-asyncio>=0.23.0"]
  ```
* **File**: `.gitignore`
  ```text
  __pycache__/
  .venv/
  config/keys.json
  workspace/projects/*/translated/*
  ```

---

### Task 1.2: `core/config.py` (Lớp Quản Lý Cấu Hình Cực Mỏng)
* **Mục đích**: Đọc cấu hình chung từ `config/config.json` và API keys từ `config/keys.json`.
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
      "default_provider": "gemini",
      "gemini_model": "gemini-2.5-flash",
      "openai_base_url": "https://openrouter.ai/api/v1",
      "openai_model": "qwen/qwen-2.5-72b-instruct",
      "max_chunk_chars": 12000,
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
              KEYS_FILE.write_text(json.dumps({"gemini_keys": [], "openai_api_key": ""}, indent=2), encoding="utf-8")

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

      def save_gemini_keys(self, keys: List[str]):
          data = {}
          if KEYS_FILE.exists():
              try:
                  data = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
              except Exception:
                  pass
          data["gemini_keys"] = [k.strip() for k in keys if k.strip()]
          KEYS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
  ```

---

### Task 1.3: `core/key_rotator.py` (Xoay Vòng Key Độc Lập, Tối Giản)
* **Mục đích**: Gửi bằng key hiện tại $\to$ nếu 429 và còn key thì thử key tiếp theo 1 lần $\to$ nếu hết key thì dừng báo lỗi cho user bấm gửi lại. Không pool state, không cooldown UI, không scheduler.
* **Mã nguồn**:
  ```python
  # core/key_rotator.py
  from typing import List, Optional

  class KeyRotator:
      def __init__(self, keys: List[str]):
          self.keys = [k.strip() for k in keys if k.strip()]
          self.current_idx = 0
          self.attempted_in_session = set()

      def has_keys(self) -> bool:
          return len(self.keys) > 0

      def get_current_key(self) -> str:
          if not self.keys:
              raise ValueError("Danh sách API Key đang trống! Vui lòng thêm key vào config/keys.json.")
          return self.keys[self.current_idx]

      def try_next_key(self) -> Optional[str]:
          """Khi gặp 429, chuyển sang key tiếp theo. Nếu đã thử hết danh sách, trả về None."""
          self.attempted_in_session.add(self.current_idx)
          if len(self.attempted_in_session) >= len(self.keys):
              # Đã thử hết toàn bộ các key trong danh sách
              return None
          
          self.current_idx = (self.current_idx + 1) % len(self.keys)
          return self.keys[self.current_idx]

      def reset_session(self):
          """Đặt lại trạng thái phiên để sẵn sàng khi người dùng bấm Gửi lại."""
          self.attempted_in_session.clear()
  ```

---

### Task 1.4: `core/chunker.py` (Cắt Chunk Thông Minh Kèm Metadata Đánh Số)
* **Mục đích**: Cắt theo lượng ký tự xác định bằng giải thuật `smartHardSplit` (ưu tiên `\n\n`), gắn metadata `file_index`, `chunk_index`, `total_chunks` để khi dịch về ghép nối chuẩn xác.
* **Mã nguồn**:
  ```python
  # core/chunker.py
  import re
  from typing import List, Dict, Any

  def _find_best_cut(text: str, min_pos: int, max_pos: int, target_pos: int) -> int:
      # Ưu tiên 1: Dấu xuống dòng đôi (\n\n) ngắt đoạn văn hoàn hảo
      doubles = [m.start() for m in re.finditer(r'\n[ \t]*\n', text) if min_pos <= m.start() <= max_pos]
      if doubles:
          return min(doubles, key=lambda p: abs(p - target_pos))

      # Ưu tiên 2: Dấu xuống dòng đơn (\n)
      singles = [m.start() for m in re.finditer(r'\n', text) if min_pos <= m.start() <= max_pos]
      if singles:
          return min(singles, key=lambda p: abs(p - target_pos))

      # Ưu tiên 3: Dấu chấm câu (. ! ? 。！？) kèm khoảng trắng
      sentences = [m.end() for m in re.finditer(r'[\.!\?。！？]\s+', text) if min_pos <= m.end() <= max_pos]
      if sentences:
          return min(sentences, key=lambda p: abs(p - target_pos))

      # Ưu tiên 4: Dấu cách
      spaces = [m.start() for m in re.finditer(r'\s+', text) if min_pos <= m.start() <= max_pos]
      if spaces:
          return min(spaces, key=lambda p: abs(p - target_pos))

      return target_pos

  def split_text(text: str, max_chars: int = 12000) -> List[str]:
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

  def prepare_chunks_for_file(filename: str, file_index: int, content: str, max_chars: int = 12000) -> List[Dict[str, Any]]:
      raw_chunks = split_text(content, max_chars)
      total = len(raw_chunks)
      chunks = []
      for idx, raw in enumerate(raw_chunks):
          char_count = len(raw)
          # Ước lượng token đơn giản (~4 ký tự/token)
          estimated_tokens = char_count // 4
          chunks.append({
              "file_index": file_index,
              "filename": filename,
              "chunk_index": idx,
              "total_chunks": total,
              "char_count": char_count,
              "estimated_tokens": estimated_tokens,
              "source_text": raw
          })
      return chunks
  ```

---

### Task 1.5: `core/prompt_engine.py` (Nạp Prompt Từ prompts/ Chung & assets/ Dự Án)
* **Mã nguồn**:
  ```python
  # core/prompt_engine.py
  from pathlib import Path
  from typing import List, Optional

  class PromptEngine:
      def __init__(self, global_prompts_dir: str = "prompts"):
          self.global_dir = Path(global_prompts_dir)
          self.global_dir.mkdir(parents=True, exist_ok=True)
          self._ensure_default_prompt()

      def _ensure_default_prompt(self):
          default_file = self.global_dir / "default_translation.txt"
          if not default_file.exists():
              default_file.write_text(
                  "BẠN LÀ MÁY DỊCH TIỂU THUYẾT CHUYÊN NGHIỆP SANG TIẾNG VIỆT.\n"
                  "QUY TẮC:\n"
                  "1. Dịch chuẩn xác, tự nhiên theo văn phong tiếng Việt.\n"
                  "2. Giữ nguyên 100% các thẻ Markdown (#, **, _, >, ```), HTML và ký tự thụt lề.\n"
                  "3. Giữ nguyên toàn bộ dòng trống giữa các đoạn văn.\n"
                  "4. KHÔNG thêm lời chào mừng hay giải thích thừa.\n\n"
                  "{{glossary_terms}}\n"
                  "{{additional_instructions}}\n\n"
                  "# VĂN BẢN NGUỒN CẦN DỊCH:\n"
                  "{{source_text}}",
                  encoding="utf-8"
              )

      def load_prompt_text(self, prompt_name: str, project_assets_dir: Optional[Path] = None) -> str:
          # Kiểm tra trong assets của dự án trước (nếu có)
          if project_assets_dir:
              custom_file = project_assets_dir / prompt_name
              if custom_file.exists():
                  return custom_file.read_text(encoding="utf-8")

          # Sau đó kiểm tra trong prompts/ chung
          global_file = self.global_dir / prompt_name
          if global_file.exists():
              return global_file.read_text(encoding="utf-8")

          raise FileNotFoundError(f"Không tìm thấy file prompt: {prompt_name}")

      def assemble_prompt(
          self,
          source_text: str,
          main_prompt_name: str = "default_translation.txt",
          addon_prompt_names: Optional[List[str]] = None,
          glossary_text: str = "",
          project_assets_dir: Optional[Path] = None
      ) -> str:
          main_content = self.load_prompt_text(main_prompt_name, project_assets_dir)

          # Ghép các prompt bổ sung (nếu có)
          addons_str = ""
          if addon_prompt_names:
              addons_parts = []
              for name in addon_prompt_names:
                  content = self.load_prompt_text(name, project_assets_dir)
                  addons_parts.append(f"--- CHỈ THỊ BỔ SUNG ({name}) ---\n{content}")
              addons_str = "\n\n" + "\n\n".join(addons_parts)

          glossary_block = f"# THUẬT NGỮ CỐ ĐỊNH:\n{glossary_text.strip()}" if glossary_text.strip() else ""

          rendered = main_content.replace("{{source_text}}", source_text)
          rendered = rendered.replace("{{glossary_terms}}", glossary_block)
          rendered = rendered.replace("{{additional_instructions}}", addons_str)
          return rendered
  ```

---

### Task 1.6: `core/ai_client.py` (Client Gọi Gemini / OpenAI Có Xoay Key Tối Giản)
* **Xử lý tối thiểu**: Timeout (90s), Bắt lỗi HTTP, Bắt lỗi mạng, Xoay key 1 lần khi 429, Dừng và báo lỗi cho người dùng bấm gửi lại.
* **Mã nguồn**:
  ```python
  # core/ai_client.py
  import httpx
  import logging
  from typing import Optional
  from core.key_rotator import KeyRotator

  logger = logging.getLogger(__name__)

  class AIClient:
      def __init__(self, key_rotator: KeyRotator, model: str = "gemini-2.5-flash", timeout_seconds: int = 90):
          self.rotator = key_rotator
          self.model = model
          self.timeout = timeout_seconds

      async def translate_chunk(self, prompt: str) -> str:
          self.rotator.reset_session()
          
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
                      
                      # 1. Nếu gặp lỗi 429 (Rate Limit) -> Thử key tiếp theo
                      if resp.status_code == 429:
                          next_key = self.rotator.try_next_key()
                          if next_key is not None:
                              logger.warning("⚠️ Key hiện tại bị 429. Đang thử key tiếp theo...")
                              continue
                          else:
                              raise RuntimeError("❌ TẤT CẢ API KEY ĐỀU BỊ LỖI 429 (RATE LIMIT)! Vui lòng bấm 'Gửi lại' sau ít phút.")

                      # 2. Nếu gặp lỗi HTTP khác (400, 403, 500) -> Dừng ngay, không retry vô hạn
                      resp.raise_for_status()

                      data = resp.json()
                      # Trích xuất an toàn bản dịch
                      candidates = data.get("candidates", [])
                      if not candidates:
                          raise ValueError("AI không trả về kết quả nội dung (Blocked hoặc rỗng)!")
                      return candidates[0]["content"]["parts"][0]["text"]

              except httpx.ConnectError:
                  raise ConnectionError("❌ LỖI KẾT NỐI MẠNG! Không thể kết nối tới AI Provider. Vui lòng kiểm tra mạng và bấm 'Gửi lại'.")
              except httpx.TimeoutException:
                  raise TimeoutError(f"❌ YÊU CẦU QUÁ THỜI GIAN CHỜ ({self.timeout}s)! Vui lòng bấm 'Gửi lại'.")
              except httpx.HTTPStatusError as e:
                  if e.response.status_code != 429:
                      raise RuntimeError(f"❌ LỖI TỪ AI PROVIDER (Mã {e.response.status_code}): {e.response.text}")
                  raise e
  ```

---

### Task 1.7: `core/file_handler.py` (Lớp Đọc/Ghi File Dự Án Cực Mỏng)
* **Mã nguồn**:
  ```python
  # core/file_handler.py
  from pathlib import Path
  from typing import List

  class ProjectFileHandler:
      def __init__(self, workspace_dir: str = "workspace/projects"):
          self.base_dir = Path(workspace_dir)

      def get_project_dir(self, slug: str) -> Path:
          p = self.base_dir / slug
          (p / "sources").mkdir(parents=True, exist_ok=True)
          (p / "translated").mkdir(parents=True, exist_ok=True)
          (p / "assets").mkdir(parents=True, exist_ok=True)
          return p

      def list_sources(self, slug: str) -> List[str]:
          sources_dir = self.get_project_dir(slug) / "sources"
          return sorted([f.name for f in sources_dir.iterdir() if f.is_file()])

      def read_source(self, slug: str, filename: str) -> str:
          file_path = self.get_project_dir(slug) / "sources" / filename
          return file_path.read_text(encoding="utf-8")

      def save_translated(self, slug: str, filename: str, content: str):
          out_path = self.get_project_dir(slug) / "translated" / filename
          out_path.write_text(content, encoding="utf-8")

      def read_asset(self, slug: str, asset_filename: str) -> str:
          asset_path = self.get_project_dir(slug) / "assets" / asset_filename
          if asset_path.exists():
              return asset_path.read_text(encoding="utf-8")
          return ""
  ```

---

### Task 1.8: `run.py` (Script CLI Chạy Dịch Dùng Được Ngay Trong Phase 1)
* **Mã nguồn**:
  ```python
  # run.py - Thực thi dịch trực tiếp trong Phase 1
  import asyncio
  import argparse
  from core.config import AppConfig
  from core.key_rotator import KeyRotator
  from core.chunker import prepare_chunks_for_file
  from core.prompt_engine import PromptEngine
  from core.ai_client import AIClient
  from core.file_handler import ProjectFileHandler

  async def main():
      parser = argparse.ArgumentParser(description="Content Translator - Phase 1 CLI")
      parser.add_argument("--project", required=True, help="Tên thư mục dự án")
      parser.add_argument("--file", required=True, help="Tên file nguồn cần dịch trong sources/")
      parser.add_argument("--prompt", default="default_translation.txt", help="Tên file prompt chính")
      args = parser.parse_args()

      config_mgr = AppConfig()
      cfg = config_mgr.get_config()
      keys = config_mgr.get_gemini_keys()

      if not keys:
          print("❌ Lỗi: Chưa có API Key nào trong config/keys.json! Vui lòng nạp key.")
          return

      file_handler = ProjectFileHandler()
      proj_dir = file_handler.get_project_dir(args.project)
      source_content = file_handler.read_source(args.project, args.file)

      # 1. Cắt chunk
      chunks = prepare_chunks_for_file(args.file, 0, source_content, cfg["max_chunk_chars"])
      print(f"📄 Bắt đầu dịch file '{args.file}': {len(chunks)} chunk(s).")

      # 2. Khởi tạo Engine
      rotator = KeyRotator(keys)
      ai_client = AIClient(rotator, model=cfg["gemini_model"], timeout_seconds=cfg["timeout_seconds"])
      prompt_engine = PromptEngine()
      glossary_text = file_handler.read_asset(args.project, "glossary.txt")

      translated_chunks = []

      # 3. Dịch lần lượt từng chunk và ghép nối
      for chunk_info in chunks:
          c_idx = chunk_info["chunk_index"] + 1
          total = chunk_info["total_chunks"]
          chars = chunk_info["char_count"]
          print(f"⏳ Đang dịch chunk {c_idx}/{total} ({chars} ký tự)...", end="", flush=True)

          assembled = prompt_engine.assemble_prompt(
              source_text=chunk_info["source_text"],
              main_prompt_name=args.prompt,
              glossary_text=glossary_text,
              project_assets_dir=(proj_dir / "assets")
          )

          try:
              translated_text = await ai_client.translate_chunk(assembled)
              translated_chunks.append(translated_text)
              print(" [XONG]")
          except Exception as e:
              print(f"\n{str(e)}")
              print("🛑 ĐÃ DỪNG LẠI. Bạn có thể bấm chạy lại lệnh trên bất cứ lúc nào.")
              return

      # 4. Ghép nối và lưu file
      final_result = "\n\n".join(translated_chunks)
      file_handler.save_translated(args.project, args.file, final_result)
      print(f"🎉 HOÀN TẤT! Bản dịch đã được lưu tại: workspace/projects/{args.project}/translated/{args.file}")

  if __name__ == "__main__":
      asyncio.run(main())
  ```

---

## 3. NGHIỆM THU PHASE 1 (SỬ DỤNG ĐƯỢC NGAY)

Ngay sau khi lập trình xong 7 file trên:
1. Bạn tạo dự án: `workspace/projects/Truyen_Test/sources/ch01.md`.
2. Dán key vào: `config/keys.json`.
3. Chạy: `python run.py --project Truyen_Test --file ch01.md`.
4. **Kết quả**: File dịch xuất hiện ngay tại `workspace/projects/Truyen_Test/translated/ch01.md` với đầy đủ định dạng và nội dung tiếng Việt chuẩn xác! **Hoàn toàn không cần chờ đến Phase 2!**
