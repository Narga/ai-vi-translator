# backend/application/use_cases/translate_project_files_use_case.py
# TranslateProjectFilesUseCase - Use case dịch nhiều file trong project

"""
TranslateProjectFilesUseCase bọc logic dịch multi-file trong project.
Tách từ webui/routes/projects.py:_project_translate_worker.

Phase 11: Tách project translation use case.
"""

import copy
import logging
import secrets
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BATCH_INSTRUCTION = """[BATCH TRANSLATION MODE]
Văn bản đầu vào chứa nhiều tài liệu độc lập, phân tách bằng các marker kỹ thuật dạng:
  <<<{token}:0>>>
  <<</{token}:0>>>
QUY TẮC B� BUỘC:
1. Giữ nguyên hoàn toàn các marker — không dịch, không thay đổi, không bỏ sót.
2. Chỉ dịch nội dung văn bản nằm giữa cặp marker mở và đóng tương ứng.
3. Không gộp, không đổi thứ tự, không thêm marker mới.
"""


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
        import logging
        logger = logging.getLogger(__name__)

    def _delimiter_overhead(self, token: str, index: int) -> int:
        """Tính chính xác số ký tự delimiter cho một file theo index trong batch."""
        open_tag = f"<<<{token}:{index}>>>\n"
        close_tag = f"\n<<</{token}:{index}>>>\n"
        return len(open_tag) + len(close_tag)

    def _build_batches(
        self,
        filenames: List[str],
        file_contents: Dict[str, str],
        chunk_size: int,
        session_token: str,
    ) -> List[List[str]]:
        """
        Gom nhóm file thành Batches.
        
        Trả về danh sách các batch, mỗi batch là danh sách filename.
        File lớn hơn chunk_size tạo thành batch đơn [filename].
        """
        batches = []
        current_batch = []
        current_batch_size = 0
        
        for filename in filenames:
            content = file_contents[filename]
            file_overhead = 0
            
            if current_batch:
                batch_index = len(current_batch)
                file_overhead = self._delimiter_overhead(session_token, batch_index)
            
            file_size = len(content)
            batch_instruction_overhead = len(BATCH_INSTRUCTION)
            
            if file_size > chunk_size:
                if current_batch:
                    batches.append(current_batch.copy())
                    current_batch = []
                    current_batch_size = 0
                
                batches.append([filename])
            elif current_batch_size + file_size + file_overhead + batch_instruction_overhead <= chunk_size:
                current_batch.append(filename)
                current_batch_size += file_size + file_overhead
            else:
                if current_batch:
                    batches.append(current_batch.copy())
                current_batch = [filename]
                current_batch_size = file_size
        
        if current_batch:
            batches.append(current_batch)
        
        return batches

    def _wrap_batch(
        self,
        session_token: str,
        batch_files: List[str],
        file_contents: Dict[str, str],
    ) -> Tuple[str, Dict[int, str]]:
        """
        Gom batch thành text với Session Token Delimiter.
        
        Trả về:
          - batch_text: chuỗi gộp với delimiter dạng <<<token:N>>>
          - batch_index_map: {0: filename, 1: filename, ...}
        """
        batch_index_map = {i: filename for i, filename in enumerate(batch_files)}
        batch_parts = []
        
        for i, filename in enumerate(batch_files):
            batch_parts.append(f"<<<{session_token}:{i}>>>")
            batch_parts.append(file_contents[filename])
            batch_parts.append(f"<<</{session_token}:{i}>>>")
        
        batch_text = "\n".join(batch_parts)
        return batch_text, batch_index_map

    def _make_batch_config(self, session_token: str) -> Dict[str, Any]:
        """Trả về bản copy config với Batch Instruction đã được inject vào prompts['main']."""
        batch_config = copy.deepcopy(self._config)
        instruction = BATCH_INSTRUCTION.replace("{token}", session_token)
        main_prompt = batch_config.get("prompts", {}).get("main", "")
        batch_config.setdefault("prompts", {})["main"] = instruction + "\n\n" + main_prompt
        return batch_config

    def _parse_batch_response(
        self,
        session_token: str,
        response: str,
        batch_index_map: Dict[int, str],
    ) -> Optional[Dict[str, str]]:
        """
        Parse response và trả về {filename: translated_content}.
        Trả về None nếu index sequence trong response không khớp expected [0, 1, ..., N-1].
        """
        pattern = rf'<<<{re.escape(session_token)}:(\d+)>>>\n(.*?)\n<<</{re.escape(session_token)}:\1>>>'
        matches = re.findall(pattern, response, re.DOTALL)

        parsed_indices = [int(m[0]) for m in matches]
        expected_indices = list(range(len(batch_index_map)))

        if parsed_indices != expected_indices:
            return None

        return {batch_index_map[int(m[0])]: m[1].strip() for m in matches}

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
        
        # Đọc nội dung tất cả files trước
        file_contents = {}
        for filename in filenames:
            file_path = project_dir / "sources" / filename
            if not file_path.exists():
                emit({"type": "info", "message": f"⚠️ File không tồn tại: {filename}"})
                fail += 1
                continue
            
            try:
                file_contents[filename] = file_path.read_text(encoding="utf-8")
            except Exception as e:
                emit({"type": "info", "message": f"❌ Lỗi đọc file {filename}: {str(e)}"})
                fail += 1
                continue
        
        if fail == total_files:
            emit({"type": "complete", "message": f"🚫 Không có file nào để dịch!"})
            return {"success": False, "ok": 0, "fail": fail, "total": total_files}
        
        # Chỉ xử lý những file đã đọc được
        valid_filenames = [f for f in filenames if f in file_contents]
        
        # Sinh session token ngẫu nhiên 1 lần
        session_token = secrets.token_hex(8)
        
        # Gom nhóm file thành Batches
        chunk_size = self._config.get("chunk_size", 22000)
        batches = self._build_batches(valid_filenames, file_contents, chunk_size, session_token)
        
        # Xử lý từng batch
        for batch_idx, batch_files in enumerate(batches, 1):
            emit({
                "type": "info",
                "message": f"📦 [{batch_idx}/{len(batches)}] Đang dịch batch có {len(batch_files)} file: {batch_files}"
            })
            
            # Trường hợp batch đơn (1 file lớn) - sử dụng luồng dịch đơn lẻ cũ
            if len(batch_files) == 1 and len(file_contents[batch_files[0]]) > chunk_size:
                filename = batch_files[0]
                text = file_contents[filename]
                emit({"type": "info", "message": f"📂 [1/{1}] Đang dịch (batch đơn): {filename}"})
                
                try:
                    executor = TranslationExecutor(
                        api_keys=self._api_keys,
                        config=self._config,
                        glossary_paths=self._glossary_paths,
                    )

                    def cb(data, _fname=filename):
                        if data["type"] == "complete":
                            data["message"] = f"✅ Đã dịch xong file: {_fname}"
                        emit(data)

                    result = executor.translate_text(
                        text=text,
                        output_filename=filename,
                        output_file_path=project_dir / "translated" / filename,
                        progress_callback=cb,
                        translation_memory=translation_memory,
                    )
                    
                    if result:
                        ok += 1
                    else:
                        fail += 1
                        
                except Exception as e:
                    emit({"type": "info", "message": f"❌ Lỗi dịch {filename}: {str(e)}"})
                    fail += 1
            
            # Trường hợp batch nhiều file - sử dụng Smart Batching
            elif len(batch_files) > 1:
                # Wrap batch text với session token
                batch_text, batch_index_map = self._wrap_batch(
                    session_token, batch_files, file_contents
                )
                
                # Tạo batch config với batch instruction
                batch_config = self._make_batch_config(session_token)
                
                try:
                    executor = TranslationExecutor(
                        api_keys=self._api_keys,
                        config=batch_config,
                        glossary_paths=self._glossary_paths,
                    )

                    def cb(data):
                        emit(data)

                    # Dịch batch text
                    translated_text = executor.translate_text(
                        text=batch_text,
                        output_filename=f"batch_{batch_idx}",
                        progress_callback=cb,
                        translation_memory=translation_memory,
                    )
                    
                    if translated_text:
                        # Parse response
                        parsed_result = self._parse_batch_response(
                            session_token, translated_text, batch_index_map
                        )
                        
                        if parsed_result:
                            # Write từng file
                            for filename, translated_content in parsed_result.items():
                                output_path = project_dir / "translated" / filename
                                output_path.parent.mkdir(parents=True, exist_ok=True)
                                output_path.write_text(translated_content, encoding="utf-8")
                            
                            ok += len(batch_files)
                            emit({
                                "type": "info",
                                "message": f"✅ Batch {batch_idx} hoàn tất: {len(batch_files)} file đã dịch"
                            })
                        else:
                            # Fallback: dịch tuần tự từng file
                            emit({
                                "type": "warning",
                                "message": f"⚠️ Phát hiện lỗi cấu trúc phản hồi từ AI cho nhóm file [{batch_files}]. Tự động chuyển sang chế độ rã nhóm dịch riêng lẻ..."
                            })
                            
                            for fallback_filename in batch_files:
                                fallback_text = file_contents[fallback_filename]
                                emit({
                                    "type": "info",
                                    "message": f"📂 [1/{len(batch_files)}] Đang dịch lại (fallback): {fallback_filename}"
                                })
                                
                                try:
                                    # Tạo executor mới cho mỗi file fallback
                                    fallback_executor = TranslationExecutor(
                                        api_keys=self._api_keys,
                                        config=self._config,
                                        glossary_paths=self._glossary_paths,
                                    )

                                    def fallback_cb(data, _fname=fallback_filename):
                                        if data["type"] == "complete":
                                            data["message"] = f"✅ Đã dịch xong file ({fallback}): {_fname}"
                                        emit(data)

                                    result = fallback_executor.translate_text(
                                        text=fallback_text,
                                        output_filename=fallback_filename,
                                        output_file_path=project_dir / "translated" / fallback_filename,
                                        progress_callback=fallback_cb,
                                        translation_memory=translation_memory,
                                    )
                                    
                                    if result:
                                        ok += 1
                                    else:
                                        fail += 1
                                        
                                except Exception as e:
                                    emit({"type": "info", "message": f"❌ Lỗi dịch fallback {fallback_filename}: {str(e)}"})
                                    fail += 1
                    
                    else:
                        fail += len(batch_files)
                        emit({
                            "type": "error",
                            "message": f"❌ Dịch batch {batch_idx} thất bại"
                        })
                
                except Exception as e:
                    emit({
                        "type": "error",
                        "message": f"❌ Lỗi nghiêm trọng batch {batch_idx}: {str(e)}"
                    })
                    fail += len(batch_files)
        
        # Save meta nếu có callback
        if save_meta_callback:
            save_meta_callback()

        total_processed = len(valid_filenames)
        emit({"type": "complete", "message": f"🚀 Đã hoàn tất {ok}/{total_processed} file ({len(valid_filenames) - total_processed} file bị bỏ qua)!"})

        return {"success": ok > 0, "ok": ok, "fail": fail + (total_files - total_processed), "total": total_files}
