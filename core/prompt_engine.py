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

    def _check_name(self, name: str) -> str:
        clean = (name or "").strip()
        if not clean or "/" in clean or "\\" in clean or ".." in clean \
                or not clean.endswith(".txt"):
            raise ValueError(f"Tên prompt phải là *.txt, không chứa /: {name}")
        return clean

    def delete_prompt(self, prompt_filename: str) -> None:
        name = self._check_name(prompt_filename)
        p = self.prompts_dir / name
        if not p.is_file():
            raise FileNotFoundError(f"Không tìm thấy prompt: {name}")
        p.unlink()

    def rename_prompt(self, old: str, new: str) -> str:
        clean_old, clean_new = self._check_name(old), self._check_name(new)
        src = self.prompts_dir / clean_old
        if not src.is_file():
            raise FileNotFoundError(f"Không tìm thấy prompt: {clean_old}")
        dst = self.prompts_dir / clean_new
        if dst.exists():
            raise ValueError(f"Đã tồn tại prompt: {clean_new}")
        src.rename(dst)
        return clean_new

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
