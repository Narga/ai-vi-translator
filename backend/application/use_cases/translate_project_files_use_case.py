# backend/application/use_cases/translate_project_files_use_case.py
# TranslateProjectFilesUseCase - Use case dịch nhiều file trong project

"""
TranslateProjectFilesUseCase bọc logic dịch multi-file trong project.
Tách từ webui/routes/projects.py:_project_translate_worker.

Phase 11: Tách project translation use case.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TranslateProjectFilesUseCase:
    """
    Use case dịch nhiều file trong project.

    Bọc logic từ _project_translate_worker trong webui/routes/projects.py.
    """

    def __init__(
        self,
        api_keys: List[str],
        config: Dict[str, Any],
        glossary_paths: Optional[List[Path]] = None,
    ):
        """
        Khởi tạo use case.

        Args:
            api_keys: Danh sách API keys
            config: Config dict
            glossary_paths: Glossary paths
        """
        self._api_keys = api_keys
        self._config = config
        self._glossary_paths = glossary_paths

    def execute(
        self,
        project_dir: Path,
        filenames: List[str],
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        translation_memory=None,
        save_meta_callback: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Thực hiện dịch nhiều file trong project.

        Args:
            project_dir: Đường dẫn project directory
            filenames: Danh sách file cần dịch
            progress_callback: Callback cho progress updates
            translation_memory: TranslationMemory instance
            save_meta_callback: Callback để save project meta

        Returns:
            Dict chứa kết quả
        """
        from core.executor import TranslationExecutor
        from backend.infrastructure.progress.progress_mapper import ProgressMapper

        mapper = ProgressMapper(callback=progress_callback)
        emit = mapper.emit

        total_files = len(filenames)
        ok = fail = 0

        for idx, filename in enumerate(filenames, 1):
            file_path = project_dir / "sources" / filename
            if not file_path.exists():
                emit({"type": "info", "message": f"⚠️ File không tồn tại: {filename}"})
                fail += 1
                continue

            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception as e:
                emit({"type": "info", "message": f"❌ Lỗi đọc file {filename}: {str(e)}"})
                fail += 1
                continue

            emit({"type": "info", "message": f"📂 [{idx}/{total_files}] Đang dịch: {filename}"})

            try:
                executor = TranslationExecutor(
                    api_keys=self._api_keys,
                    config=self._config,
                    glossary_paths=self._glossary_paths,
                )

                def cb(data, _idx=idx, _total=total_files, _fname=filename):
                    if data["type"] == "complete":
                        data["message"] = f"✅ Đã dịch xong file {_idx}/{_total}: {_fname}"
                        if _idx < _total:
                            data["type"] = "file_complete"
                    emit(data)

                executor.translate_text(
                    text=text,
                    output_filename=filename,
                    output_file_path=project_dir / "translated" / filename,
                    progress_callback=cb,
                    translation_memory=translation_memory,
                )
                ok += 1

            except Exception as e:
                emit({"type": "info", "message": f"❌ Lỗi dịch {filename}: {str(e)}"})
                fail += 1

        # Save meta nếu có callback
        if save_meta_callback:
            save_meta_callback()

        emit({"type": "complete", "message": f"🚀 Đã hoàn tất {ok}/{total_files} file!"})

        return {"success": ok > 0, "ok": ok, "fail": fail, "total": total_files}
