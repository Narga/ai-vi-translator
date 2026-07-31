# backend/application/use_cases/spellcheck_project_files_use_case.py
# SpellcheckProjectFilesUseCase — wrapper mỏng, gọi TranslationExecutor.spellcheck_text

"""
SpellcheckProjectFilesUseCase tái dùng TranslationExecutor.spellcheck_text.
Không có logic AI riêng — xoay vòng key, checkpoint và retry đều từ TranslationExecutor.

FIX: progress_callback được truyền qua lambda để không double-emit
với ProgressMapper đang dùng bên trong use case này.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpellcheckProjectFilesUseCase:
    """
    Use case spellcheck nhiều file trong project.
    Tái dùng TranslationExecutor.spellcheck_text — không có logic riêng.
    """

    def __init__(self, api_keys: List[str], config: Dict[str, Any]):
        self._api_keys = api_keys
        self._config = config

    def execute(
        self,
        project_dir: Path,
        filenames: List[str],
        folder_type: str = "sources",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        from core.executor import TranslationExecutor
        from backend.infrastructure.progress.progress_mapper import ProgressMapper

        mapper = ProgressMapper(callback=progress_callback)
        emit = mapper.emit

        total_files = len(filenames)
        ok = fail = 0

        for idx, filename in enumerate(filenames, 1):
            source_folder = "translated" if folder_type == "translated" else "sources"
            file_path = project_dir / source_folder / filename

            if not file_path.exists():
                emit({"type": "info", "message": f"⚠️ Không tìm thấy: {filename}"})
                fail += 1
                continue

            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception as e:
                emit({"type": "info", "message": f"❌ Lỗi đọc file {filename}: {e}"})
                fail += 1
                continue

            emit({"type": "info", "message": f"📂 [{idx}/{total_files}] Soát lỗi: {filename}"})

            executor = TranslationExecutor(api_keys=self._api_keys, config=self._config)

            # FIX: Truyền progress_callback gốc trực tiếp (không qua mapper) vào
            # spellcheck_text để tránh double-emit. ProgressMapper ở trên chỉ dùng
            # cho các emit file_complete/info của use case này, không cho emit nội bộ executor.
            result = executor.spellcheck_text(
                text=text,
                output_filename=filename,
                progress_callback=progress_callback,
            )

            if result is None:
                emit({"type": "info", "message": f"❌ Soát lỗi thất bại: {filename}"})
                fail += 1
                continue

            clean_text, error_log = result
            out_path = project_dir / "spelling" / filename
            info_path = project_dir / "spelling" / f"{filename.rsplit('.', 1)[0]}_info.txt"
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(clean_text, encoding="utf-8")
            info_path.write_text(error_log, encoding="utf-8")
            ok += 1

            msg = f"✅ [{idx}/{total_files}]: {filename}"
            if idx == total_files:
                emit({"type": "complete", "message": msg})
            else:
                emit({"type": "file_complete", "message": msg})

        return {"success": ok > 0, "ok": ok, "fail": fail, "total": total_files}
