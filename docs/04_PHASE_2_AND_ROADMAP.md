# 04. KẾ HOẠCH PHASE 2 (DỊCH THỬ NGHIỆM) & LỘ TRÌNH TỔNG THỂ
> **Cam kết cốt lõi**: **Ngay khi kết thúc Phase 2, hệ thống hoàn toàn có thể tạo một dự án mới và thực hiện dịch thử nghiệm một tệp nội dung bất kỳ từ đầu đến cuối (End-to-End Translation)**.  
> **Lộ trình dài hạn**: Trải qua 5 Phase từ lõi Backend đến giao diện React SPA đa trang với Sidebar thu gọn.

---

## 1. CHI TIẾT KẾ HOẠCH PHASE 2: QUẢN LÝ TẬP TIN & DỊCH THỬ NGHIỆM THỰC TẾ

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   MỤC TIÊU CỦA PHASE 2: END-TO-END PIPELINE                      │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 1. Cấu trúc thư mục dự án chuẩn hóa (sources / translated / glossary.txt)        │
│ 2. Pipeline Orchestrator kết nối: File ──► Chunker ──► Prompt ──► AI ──► Output │
│ 3. Hỗ trợ chọn file chạy kèm Prompt Chính + Prompt Bổ Sung                       │
│ 4. Lưu Checkpoint tập trung vào SQLite và xuất bản dịch hoàn chỉnh               │
│ 5. BÀI TEST THỰC TẾ: Nạp 1 chương truyện thực và dịch thành công ra tiếng Việt   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### Task 2.1: Chuẩn Hóa Cấu Trúc Lưu Trữ Dự Án (`core/project_manager.py`)
* **Mục đích**: Quản lý độc lập từng dự án, phân tách rõ ràng giữa tệp nguồn và tệp bản dịch.
* **Cấu trúc lưu trữ**:
  ```text
  workspace/projects/{project_slug}/
  ├── sources/        # Thư mục chứa các tệp nguồn (.txt, .md, .html)
  ├── translated/     # Thư mục chứa các tệp bản dịch tiếng Việt tương ứng
  └── glossary.txt    # Bảng thuật ngữ nhân vật, địa danh riêng của dự án
  ```
* **Mã nguồn `core/project_manager.py`**:
  ```python
  import os
  import shutil
  from pathlib import Path
  from typing import List, Dict, Any

  class ProjectManager:
      def __init__(self, workspace_dir: str = "workspace/projects"):
          self.workspace_dir = Path(workspace_dir)
          self.workspace_dir.mkdir(parents=True, exist_ok=True)

      def create_project(self, slug: str, title: str) -> Path:
          proj_dir = self.workspace_dir / slug
          (proj_dir / "sources").mkdir(parents=True, exist_ok=True)
          (proj_dir / "translated").mkdir(parents=True, exist_ok=True)
          glossary = proj_dir / "glossary.txt"
          if not glossary.exists():
              glossary.write_text("# BẢNG THUẬT NGỮ DỰ ÁN\n# Cú pháp: Từ gốc = Từ dịch\n", encoding="utf-8")
          return proj_dir

      def list_source_files(self, slug: str) -> List[str]:
          sources_dir = self.workspace_dir / slug / "sources"
          if not sources_dir.exists():
              return []
          return sorted([f.name for f in sources_dir.iterdir() if f.is_file()])

      def get_file_content(self, slug: str, folder: str, filename: str) -> str:
          file_path = self.workspace_dir / slug / folder / filename
          if not file_path.exists():
              raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
          return file_path.read_text(encoding="utf-8")

      def save_translated_file(self, slug: str, filename: str, content: str):
          out_path = self.workspace_dir / slug / "translated" / filename
          out_path.write_text(content, encoding="utf-8")

      def get_project_glossary(self, slug: str) -> str:
          glossary = self.workspace_dir / slug / "glossary.txt"
          if glossary.exists():
              return glossary.read_text(encoding="utf-8")
          return ""
  ```

---

### Task 2.2: Xây Dựng Bộ Điều Phối Dịch Thuật (`core/pipeline.py`)
* **Mục đích**: Ghép nối toàn bộ các module từ Phase 1: đọc file $\to$ chia chunk $\to$ nạp prompt chính + bổ sung $\to$ gọi AI (tự xoay key khi 429) $\to$ lưu checkpoint $\to$ xuất file hoàn chỉnh.
* **Mã nguồn `core/pipeline.py`**:
  ```python
  import asyncio
  import logging
  from typing import List, Optional, Callable
  from core.chunker import smart_split
  from core.prompt_engine import PromptEngine
  from core.key_pool import KeyPoolManager
  from core.ai_client import AIClient
  from core.storage import SingleStorage
  from core.project_manager import ProjectManager

  logger = logging.getLogger(__name__)

  class TranslationPipeline:
      def __init__(
          self,
          project_manager: ProjectManager,
          prompt_engine: PromptEngine,
          ai_client: AIClient,
          storage: SingleStorage,
      ):
          self.pm = project_manager
          self.pe = prompt_engine
          self.ai = ai_client
          self.storage = storage

      async def translate_file(
          self,
          project_slug: str,
          filename: str,
          main_prompt: str = "default_translation.txt",
          addon_prompts: Optional[List[str]] = None,
          attach_glossary: bool = True,
          progress_callback: Optional[Callable[[int, int, str], None]] = None
      ) -> str:
          # 1. Đọc nội dung nguồn
          raw_text = self.pm.get_file_content(project_slug, "sources", filename)

          # 2. Phân đoạn bảo toàn định dạng bằng thuật toán smartHardSplit
          chunks = smart_split(raw_text, max_chars=15000)
          total_chunks = len(chunks)
          logger.info(f"📂 Bắt đầu dịch file {filename} ({total_chunks} chunks)")

          # 3. Đọc glossary của dự án nếu được chọn
          glossary_content = self.pm.get_project_glossary(project_slug) if attach_glossary else ""

          # 4. Kiểm tra các chunk đã có trong checkpoint SQLite
          saved_chunks = self.storage.get_saved_chunks(project_slug, filename)
          translated_chunks = []
          previous_summary = ""

          # 5. Duyệt dịch từng chunk tuần tự
          for idx, chunk in enumerate(chunks):
              if idx in saved_chunks:
                  logger.info(f"⏩ Chunk {idx+1}/{total_chunks} đã có trong checkpoint, bỏ qua.")
                  translated_chunks.append(saved_chunks[idx])
                  continue

              if progress_callback:
                  progress_callback(idx + 1, total_chunks, f"Đang dịch chunk {idx+1}/{total_chunks}...")

              # Ghép prompt động
              prompt = self.pe.assemble_prompt(
                  source_text=chunk,
                  main_prompt_file=main_prompt,
                  complementary_prompt_files=addon_prompts,
                  glossary_content=glossary_content,
                  previous_summary=previous_summary
              )

              # Gọi AI với cơ chế tự động chuyển key khi gặp 429
              translated_text = await self.ai.generate_text(prompt)

              # Lưu kết quả chunk vào SQLite
              self.storage.save_chunk_result(project_slug, filename, idx, chunk, translated_text)
              translated_chunks.append(translated_text)

          # 6. Ghép toàn bộ các chunk lại thành văn bản hoàn chỉnh
          final_content = "\n\n".join(translated_chunks)

          # 7. Lưu file kết quả vào thư mục translated của dự án
          self.pm.save_translated_file(project_slug, filename, final_content)
          logger.info(f"✅ Hoàn tất dịch file {filename}!")
          return final_content
  ```

---

### Task 2.3: Xây Dựng Runner Thực Thi Độc Lập (`run_trial.py`)
* **Mục đích**: Cung cấp công cụ chạy thử nghiệm ngay lập tức để kiểm chứng toàn bộ hệ thống trước khi bắt tay làm giao diện WebUI phức tạp.
* **Mã nguồn `run_trial.py`**:
  ```python
  # run_trial.py - Script chạy dịch thử nghiệm Phase 2
  import asyncio
  import sys
  import os
  from core.project_manager import ProjectManager
  from core.prompt_engine import PromptEngine
  from core.key_pool import KeyPoolManager
  from core.ai_client import AIClient
  from core.storage import SingleStorage
  from core.pipeline import TranslationPipeline

  async def main():
      print("🚀 BẮT ĐẦU CHƯƠNG TRÌNH DỊCH THỬ NGHIỆM PHASE 2")
      
      # 1. Khởi tạo components
      pm = ProjectManager()
      pe = PromptEngine()
      storage = SingleStorage()

      # 2. Đọc API Key từ môi trường hoặc file
      api_keys = os.getenv("GEMINI_API_KEYS", "").split(",")
      api_keys = [k.strip() for k in api_keys if k.strip()]
      if not api_keys:
          api_key = input("👉 Nhập ít nhất 1 Gemini API Key để dịch thử: ").strip()
          api_keys = [api_key]

      key_pool = KeyPoolManager(api_keys)
      ai_client = AIClient(key_pool=key_pool, provider="gemini", model="gemini-2.5-flash")

      # 3. Tạo dự án thử nghiệm
      proj_slug = "demo_test"
      pm.create_project(proj_slug, "Dự Án Thử Nghiệm")
      
      # 4. Tạo một file nguồn mẫu
      sample_file = "chuong_01.md"
      sample_content = (
          "# CHƯƠNG 1: KHỞI ĐẦU MỚI\n\n"
          "Đêm đã về khuya, ánh trăng bàng bạc chiếu qua khung cửa sổ.\n\n"
          "> \"Ngươi có tin vào vận mệnh không?\" - Lão nhân khẽ hỏi.\n\n"
          "Tiêu Viêm im lặng một hồi lâu, bàn tay nắm chặt thanh hắc kiếm:\n"
          "- Ta không tin mệnh trời, ta chỉ tin vào thanh kiếm trong tay mình!"
      )
      (pm.workspace_dir / proj_slug / "sources" / sample_file).write_text(sample_content, encoding="utf-8")
      print(f"📄 Đã tạo tệp nguồn mẫu: {sample_file}")

      # 5. Khởi chạy pipeline dịch
      pipeline = TranslationPipeline(pm, pe, ai_client, storage)
      print("⏳ Đang gửi chunk lên AI dịch...")
      
      result = await pipeline.translate_file(
          project_slug=proj_slug,
          filename=sample_file,
          main_prompt="default_translation.txt",
          addon_prompts=None,
          attach_glossary=False
      )

      print("\n" + "="*50)
      print("🎉 KẾT QUẢ BẢN DỊCH HOÀN TẤT:")
      print("="*50)
      print(result)
      print("="*50)
      print(f"📁 Tệp kết quả đã lưu tại: workspace/projects/{proj_slug}/translated/{sample_file}")

  if __name__ == "__main__":
      asyncio.run(main())
  ```

---

### Task 2.4: Tiêu Chí Nghiệm Thu Hoàn Tất Phase 2 (Acceptance Gate)
Sau khi thực hiện xong Phase 2, bạn chỉ cần chạy:
```bash
python run_trial.py
```
**Yêu cầu nghiệm thu thành công**:
1. Tự động sinh dự án `demo_test` với đầy đủ thư mục `sources/` và `translated/`.
2. Gửi văn bản lên Gemini AI và nhận về bản dịch tiếng Việt chuẩn xác.
3. Bản dịch tiếng Việt giữ nguyên 100% tiêu đề `#`, trích dẫn `>`, danh sách `-` và khoảng cách dòng trống.
4. Thông tin chunk được lưu trọn vẹn vào `workspace/translator.db`.
5. **Khẳng định**: Hệ thống đã sẵn sàng 100% về mặt nghiệp vụ dịch thuật để chuyển sang làm giao diện WebUI.

---

## 2. LỘ TRÌNH TRIỂN KHAI TỔNG THỂ CẢ DỰ ÁN (MASTER ROADMAP)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   PHASE 1    │───►│   PHASE 2    │───►│   PHASE 3    │───►│   PHASE 4    │───►│   PHASE 5    │
│  Nền Tảng Lõi │    │ Dịch Thử     │    │  WebUI Đa    │    │  Tính Năng   │    │  Đóng Gói &  │
│  & Key Pool  │    │ Nghiệm End2End│   │  Trang & Side│    │  Nâng Cao    │    │  Phát Hành   │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

### Phase 1: Nền Tảng Backend Cốt Lõi (Đã chi tiết ở tài liệu 03)
* Giải thuật `smartHardSplit` và đếm từ $O(N)$.
* Quản lý Key Pool (Google Gemini + OpenAI-compatible) tự động cooldown 60s khi gặp 429.
* Bộ nạp Prompt `.txt` hỗ trợ ghép prompt bổ sung.
* Quản lý trạng thái bằng 1 file SQLite duy nhất.

### Phase 2: Quản Lý Dự Án & Chạy Thử Nghiệm Thực Tế (Hoàn tất mục tiêu cốt lõi)
* Quản lý thư mục dự án `sources/` và `translated/`.
* Xây dựng `TranslationPipeline` kết nối toàn diện.
* Chạy thử nghiệm thành công một file tiểu thuyết thực tế từ đầu đến cuối.

### Phase 3: Giao Diện Người Dùng Đa Trang (React SPA Frontend)
* Xây dựng layout với **Collapsible Sidebar** (thu gọn từ 260px $\to$ 64px).
* Thiết lập 8 trang chuyên biệt:
  * Trang Dự án (`/projects`).
  * Trang Workspace Biên dịch Song ngữ (`/workspace`) với Dual-Pane sync-scroll và bộ chọn prompt linh hoạt.
  * Trang Thư viện Prompt (`/prompts`) trực tiếp sửa file `.txt`.
  * Trang Công cụ EPUB (`/tools/epub`).
  * Trang Cấu hình Cụm Key (`/settings`).
  * Trang Nhật ký Live Logs (`/logs`).
  * Trang Lưu trữ Checkpoint (`/storage`).
  * Trang Tài liệu Hướng dẫn (`/docs`).

### Phase 4: Nâng Cao & Kế Thừa silaBook
* Tích hợp cơ chế tự động tóm tắt chương trước và truyền ngữ cảnh nối tiếp qua `<previous_chunk_handoff>`.
* Tích hợp bộ lọc thuật ngữ nhanh (`filterGlossary`) trước khi gửi chunk.
* Hoàn thiện Công cụ EPUB (đầu vào text/md/html, convert 2 chiều).

### Phase 5: Đóng Gói & Tối Ưu Hóa Trải Nghiệm
* Đóng gói One-Click Launcher (file chạy tự động cho Windows/macOS/Linux).
* Kiểm thử tải với 100 chương tiểu thuyết và cụm 10 Google API key miễn phí.
* Xuất bản tài liệu hướng dẫn hoàn chỉnh.
