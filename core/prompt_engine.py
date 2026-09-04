"""Nạp prompt .txt và thay biến {{source_text}} (+ {{glossary_terms}})."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROMPTS_DIR = PROJECT_ROOT / "prompts"

DEFAULT_PROMPT = (
    "BẠN LÀ MÁY DỊCH TIỂU THUYẾT CHUYÊN NGHIỆP SANG TIẾNG VIỆT.\n"
    "QUY TẮC BẢO TOÀN NỘI DUNG & ĐỊNH DẠNG:\n"
    "1. Dịch chuẩn xác, tự nhiên theo văn phong tiếng Việt, không bỏ sót nội dung.\n"
    "2. Giữ nguyên các thẻ Markdown (#, **, _, >, ```), HTML và ký tự thụt lề.\n"
    "3. Giữ nguyên các dòng trống giữa các đoạn văn.\n"
    "4. KHÔNG thêm lời chào mừng hay bình luận thừa.\n\n"
    "# VĂN BẢN NGUỒN CẦN DỊCH:\n"
    "{{source_text}}"
)


class PromptEngine:
    def __init__(self, prompts_dir: Path = DEFAULT_PROMPTS_DIR):
        self.prompts_dir = Path(prompts_dir)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_default_prompt()

    def _ensure_default_prompt(self):
        default_file = self.prompts_dir / "default_translation.txt"
        if not default_file.exists():
            default_file.write_text(DEFAULT_PROMPT, encoding="utf-8")

    def load_prompt(self, prompt_filename: str = "default_translation.txt") -> str:
        file_path = self.prompts_dir / prompt_filename
        if not file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy file prompt: {file_path}")
        return file_path.read_text(encoding="utf-8")

    def assemble_prompt(self, source_text: str, prompt_filename: str = "default_translation.txt",
                        glossary_terms: str = "") -> str:
        template = self.load_prompt(prompt_filename)
        out = template.replace("{{source_text}}", source_text)
        return out.replace("{{glossary_terms}}", glossary_terms)
