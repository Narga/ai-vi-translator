# backend/application/use_cases/spellcheck_project_files_use_case.py
# SpellcheckProjectFilesUseCase - Use case spellcheck nhiều file trong project

"""
SpellcheckProjectFilesUseCase bọc logic spellcheck multi-file trong project.
Tách từ webui/routes/projects.py:_project_spellcheck_worker.

Phase 12: Tách spellcheck use case.
"""

import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SpellcheckProjectFilesUseCase:
    """
    Use case spellcheck nhiều file trong project.

    Bọc logic từ _project_spellcheck_worker trong webui/routes/projects.py.
    """

    def __init__(
        self,
        api_keys: List[str],
        config: Dict[str, Any],
    ):
        """
        Khởi tạo use case.

        Args:
            api_keys: Danh sách API keys
            config: Config dict
        """
        self._api_keys = api_keys
        self._config = config

    def execute(
        self,
        project_dir: Path,
        filenames: List[str],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """
        Thực hiện spellcheck nhiều file trong project.

        Args:
            project_dir: Đường dẫn project directory
            filenames: Danh sách file cần spellcheck
            progress_callback: Callback cho progress updates

        Returns:
            Dict chứa kết quả
        """
        from core.spellcheck_executor import SpellcheckExecutor
        from backend.infrastructure.progress.progress_mapper import ProgressMapper

        mapper = ProgressMapper(callback=progress_callback)
        emit = mapper.emit

        total_files = len(filenames)
        ok = fail = 0

        for idx, filename in enumerate(filenames, 1):
            # Ưu tiên tìm trong sources, sau đó là translated
            file_path = project_dir / "sources" / filename
            if not file_path.exists():
                file_path = project_dir / "translated" / filename

            if not file_path.exists():
                emit({"type": "info", "message": f"⚠️ Tệp không tồn tại: {filename}"})
                fail += 1
                continue

            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception as e:
                emit({"type": "info", "message": f"❌ Lỗi đọc file {filename}: {str(e)}"})
                fail += 1
                continue

            emit({"type": "info", "message": f"📂 [{idx}/{total_files}] Đang soát lỗi: {filename}"})

            try:
                executor = SpellcheckExecutor(
                    api_keys=self._api_keys,
                    config=self._config,
                )

                def cb(data):
                    emit(data)

                clean_text, error_log = executor.execute(
                    text=text,
                    progress_callback=cb,
                )

                # Lưu kết quả
                out_path = project_dir / "spelling" / filename
                info_path = project_dir / "spelling" / f"{filename.rsplit('.', 1)[0]}_info.txt"
                out_path.parent.mkdir(parents=True, exist_ok=True)

                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(clean_text)

                with open(info_path, "w", encoding="utf-8") as f:
                    f.write(error_log)

                ok += 1

                msg = f"✅ Đã soát lỗi xong {idx}/{total_files}: {filename}"
                if idx == total_files:
                    emit({"type": "complete", "message": msg})
                else:
                    emit({"type": "file_complete", "message": msg})

            except Exception as e:
                logger.error(f"Lỗi Spellcheck: {str(e)}")
                emit({"type": "error", "message": f"❌ Lỗi hệ thống: {str(e)}"})
                fail += 1

        return {"success": ok > 0, "ok": ok, "fail": fail, "total": total_files}
