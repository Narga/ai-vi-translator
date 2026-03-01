# core/executor.py - v5.0.0
# Tác giả: Narga
# Executor hợp nhất cho cả WebUI và CLI.

import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Callable, Optional

from services.api_service import ApiManager
from services.cache_service import TranslationCache
from services.checkpoint_service import CheckpointService
from plugins.translation.chunker import process_text_for_chunking
from plugins.translation.translator import robust_translate
from webui.helpers import calculate_stats

logger = logging.getLogger(__name__)

class TranslationExecutor:
    """
    Lõi thực thi dịch thuật duy nhất cho cả hệ thống.
    Nhận input, cấu hình và callback để báo cáo tiến độ.
    """

    def __init__(self, api_keys: list[str], config: Dict[str, Any]):
        """
        Khởi tạo Executor.
        
        Args:
            api_keys: Danh sách API keys để dùng
            config: C Dict chứa cấu hình (model, prompts, chunk_size, v.v.)
        """
        self.api_manager = ApiManager(api_keys)
        self.config = config
        
        # Init caching
        use_cache = config.get("use_cache", True)
        self.cache = TranslationCache("workspace/cache", enabled=use_cache)
        
        # Init checkpoint
        self.checkpoint_service = CheckpointService("workspace/checkpoints")
        
        # Prompts
        self.prompts = config.get("prompts", {})

    def translate_text(
        self, 
        text: str, 
        output_filename: str = "translated", 
        output_file_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        translation_memory: Optional[Any] = None
    ) -> Optional[str]:
        """
        Thực hiện dịch thuật một đoạn văn bản lớn.
        
        Args:
            text: Nội dung cần dịch.
            output_filename: Tên file dùng để lưu checkpoint (ví dụ: 'chapter1.txt').
            output_file_path: Đường dẫn lưu file kết quả. Nếu None, lưu vào workspace/output.
            progress_callback: Hàm callback nhận thông tin tiến độ.
            translation_memory: Object TranslationMemory (tuỳ chọn)
            
        Returns:
            str: Nội dung đã dịch hoàn chỉnh, hoặc None nếu thất bại.
        """
        def emit(event_type: str, **kwargs):
            if progress_callback:
                data = {"type": event_type}
                data.update(kwargs)
                progress_callback(data)

        try:
            # 1. Chunking
            chunk_size = self.config.get("chunk_size", 22000)
            min_chunk = chunk_size - 2000
            max_chunk = chunk_size
            
            chunks = process_text_for_chunking(text, min_chars=min_chunk, max_chars=max_chunk)
            emit("info", message=f"Đã chia thành {len(chunks)} chunks")
            
            # 2. Checkpoint Resume
            translated_chunks = {}
            prev_context = ""
            start_index = 0
            
            resume_info = self.checkpoint_service.get_resume_info(output_filename)
            if resume_info and resume_info.get("total_chunks") == len(chunks):
                translated_chunks = self.checkpoint_service.get_translated_chunks(output_filename)
                start_index = resume_info.get("next_chunk_index", 0)
                emit("info", message=f"Resume từ chunk {start_index + 1}/{len(chunks)}")
                
                # Retrieve context from last translated chunk
                if start_index > 0 and (start_index - 1) in translated_chunks:
                    last_text = translated_chunks[start_index - 1]
                    ctx_len = self.config.get("context_char_count", 500)
                    prev_context = last_text[-ctx_len:] if len(last_text) > ctx_len else last_text
            else:
                self.checkpoint_service.init_session(
                    filename=output_filename, 
                    total_chunks=len(chunks),
                    chunks_text=chunks
                )

            # 3. Processing
            cached_count = 0
            total_tokens = 0
            tm_hits = 0

            for i in range(start_index, len(chunks)):
                chunk = chunks[i]
                
                emit("progress", 
                     current=i + 1, 
                     total=len(chunks), 
                     percent=int((i + 1) / len(chunks) * 100),
                     message=f"Đang dịch chunk {i + 1}/{len(chunks)}..."
                )

                # Check Cache
                cache_key = self.cache.build_key(chunk, self.prompts, self.config, prev_context)
                cached_result = self.cache.get(cache_key)

                if cached_result:
                    cached_count += 1
                    result = cached_result
                    emit("info", message=f"Chunk {i + 1}: Sử dụng cache ✅")
                else:
                    # Check TM
                    tm_match = None
                    if translation_memory:
                        tm_match = translation_memory.find_match(chunk)

                    if tm_match and tm_match.get("similarity", 0) >= 0.9:
                        tm_hits += 1
                        result = tm_match["translation"]
                        emit("info", message=f"Chunk {i + 1}: TM match {tm_match['similarity']:.0%} 📚")
                    else:
                        # Thực sự gọi API dịch
                        result, status, api_key = robust_translate(
                            original_chunk=chunk,
                            api_manager=self.api_manager,
                            cache=self.cache,
                            prompts=self.prompts,
                            config_params=self.config,
                            previous_chunk_context=prev_context,
                        )

                        if status == "success" and result:
                            if translation_memory:
                                translation_memory.add_translation(chunk, result, output_filename)
                            total_tokens += len(chunk) // 2
                            # Save checkpoint
                            self.checkpoint_service.save_chunk(
                                filename=output_filename,
                                chunk_index=i,
                                original_text=chunk,
                                translated_text=result,
                                api_key_used=api_key
                            )
                        else:
                            emit("error", message=f"Dịch thất bại tại chunk {i + 1}: {status}")
                            return None

                translated_chunks[i] = result
                ctx_len = self.config.get("context_char_count", 500)
                prev_context = result[-ctx_len:] if len(result) > ctx_len else result

            # 4. Finalizing
            final_chunks_list = [translated_chunks[i] for i in range(len(chunks)) if i in translated_chunks]
            full_translation = "\n\n".join(final_chunks_list)

            if output_file_path is None:
                output_dir = Path("workspace/output")
                output_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_file_path = output_dir / f"{output_filename}_{timestamp}.txt"
            else:
                output_file_path = Path(output_file_path)
                output_file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file_path, "w", encoding="utf-8") as f:
                f.write(full_translation)
            
            # Clean checkpoint on success mode
            self.checkpoint_service.delete(self.checkpoint_service._get_db_path(output_filename))

            try:
                calculate_stats()
            except Exception:
                pass

            cache_info = f"{cached_count}/{len(chunks)} cache"
            tm_info = f", {tm_hits} TM" if tm_hits > 0 else ""

            emit("complete", 
                 message=f"Dịch hoàn tất! ({cache_info}{tm_info})",
                 result=full_translation,
                 chunks=len(chunks),
                 cached=cached_count,
                 tm_hits=tm_hits,
                 source_length=len(text),
                 translated_length=len(full_translation),
                 output_file=str(output_file_path.name),
                 tokens_used=total_tokens
            )
            
            return full_translation

        except Exception as e:
            logger.error(f"Translation execution error: {e}", exc_info=True)
            emit("error", message=f"Lỗi: {str(e)}")
            return None

    def translate_file(self, filepath: Path, progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None) -> Optional[str]:
        """Tiện ích đọc file và dịch"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            return self.translate_text(text, output_filename=filepath.stem, progress_callback=progress_callback)
        except Exception as e:
            if progress_callback:
                progress_callback({"type": "error", "message": f"Không thể đọc file {filepath.name}: {e}"})
            return None
