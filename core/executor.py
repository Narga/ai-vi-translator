# core/executor.py - v5.0.1
# Tác giả: Narga
# Executor hợp nhất cho cả WebUI và CLI.

import copy
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional

from services.api_service import ApiManager
from services.cache_service import TranslationCache
from services.checkpoint_service import CheckpointService
from services.glossary_service import GlossaryService
from plugins.translation.chunker import process_text_for_chunking
from plugins.translation.translator import robust_translate

logger = logging.getLogger(__name__)


def _try_calculate_stats() -> None:
    """Cố gắng gọi calculate_stats của webui (nếu có). Im lặng nếu không chạyWebUI."""
    try:
        from webui.helpers import calculate_stats
        calculate_stats()
    except Exception:
        pass


from core.log_handler import ProgressLogHandler


class TranslationExecutor:
    """
    Lõi thực thi dịch thuật duy nhất cho cả hệ thống.
    Nhận input, cấu hình và callback để báo cáo tiến độ.
    """

    def __init__(
        self,
        api_keys: List[str],
        config: Dict[str, Any],
        glossary_paths: Optional[List[Path]] = None,
    ):
        """
        Khởi tạo Executor.

        Args:
            api_keys: Danh sách API keys để dùng.
            config: Dict chứa cấu hình (model, prompts, chunk_size, v.v.).
            glossary_paths: Danh sách các file từ điển (tùy chọn).
        """
        self.api_manager = ApiManager(api_keys)
        self.config = config

        # Init caching
        use_cache = config.get("use_cache", True)
        self.cache = TranslationCache("workspace/cache", enabled=use_cache)

        # Init checkpoint
        self.checkpoint_service = CheckpointService("workspace/checkpoints")

        # Init Dynamic Glossary
        self.glossary = GlossaryService(glossary_paths) if glossary_paths else None

        # Deep copy prompts để tránh mutate config gốc
        self.prompts: Dict[str, str] = copy.deepcopy(config.get("prompts", {}))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate_text(
        self,
        text: str,
        output_filename: str = "translated",
        output_file_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        translation_memory: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Thực hiện dịch thuật một đoạn văn bản lớn.

        Args:
            text: Nội dung cần dịch.
            output_filename: Tên file dùng để lưu checkpoint.
            output_file_path: Đường dẫn lưu file kết quả. Nếu None, lưu vào workspace/output.
            progress_callback: Hàm callback nhận thông tin tiến độ.
            translation_memory: Object TranslationMemory (tuỳ chọn).

        Returns:
            Nội dung đã dịch hoàn chỉnh, hoặc None nếu thất bại.
        """

        def emit(event_type: str, **kwargs: Any) -> None:
            if progress_callback:
                progress_callback({"type": event_type, **kwargs})

        # Đăng ký handler để chuyển hướng log vào UI
        ui_log_handler = ProgressLogHandler(emit)
        logging.root.addHandler(ui_log_handler)

        try:
            # 1. Chunking
            emit("progress", percent=5, message="Đang chia nhỏ văn bản...")
            chunk_size = self.config.get("chunk_size", 22000)
            chunks = process_text_for_chunking(
                text, min_chars=chunk_size - 2000, max_chars=chunk_size
            )
            emit("info", message=f"Đã chia thành {len(chunks)} chunks")
            emit("progress", percent=10, message=f"Đã chia thành {len(chunks)} chunks")

            # 2. Checkpoint Resume
            translated_chunks: Dict[int, str] = {}
            prev_context = ""
            start_index = 0

            resume_info = self.checkpoint_service.get_resume_info(output_filename)
            if resume_info and resume_info.get("total_chunks") == len(chunks):
                translated_chunks = self.checkpoint_service.get_translated_chunks(output_filename)
                start_index = resume_info.get("next_chunk_index", 0)
                emit("info", message=f"Resume từ chunk {start_index + 1}/{len(chunks)}")
                emit("progress", percent=15, message=f"Resume từ chunk {start_index + 1}/{len(chunks)}")

                # Lấy context từ chunk dịch trước đó
                if start_index > 0 and (start_index - 1) in translated_chunks:
                    prev_context = self._tail_context(translated_chunks[start_index - 1])
            else:
                self.checkpoint_service.init_session(
                    filename=output_filename,
                    total_chunks=len(chunks),
                    chunks_text=chunks,
                )

            # 3. Dịch từng chunk
            stats = {"cached": 0, "tokens": 0, "tm_hits": 0}

            for i in range(start_index, len(chunks)):
                chunk = chunks[i]
                
                # Granular progress within a chunk
                base_percent = 10 + int((i / len(chunks)) * 90)
                
                emit(
                    "progress",
                    current=i + 1,
                    total=len(chunks),
                    percent=base_percent + 2,
                    message=f"Đang chuẩn bị chunk {i + 1}/{len(chunks)}...",
                )

                emit(
                    "progress",
                    current=i + 1,
                    total=len(chunks),
                    percent=base_percent + 5,
                    message=f"Đang gửi chunk {i + 1} đến AI...",
                )

                result = self._translate_single_chunk(
                    chunk=chunk,
                    chunk_index=i,
                    prev_context=prev_context,
                    output_filename=output_filename,
                    translation_memory=translation_memory,
                    stats=stats,
                    emit=emit,
                )

                if result is None:
                    return None  # Đã emit error bên trong _translate_single_chunk

                emit(
                    "progress",
                    current=i + 1,
                    total=len(chunks),
                    percent=int(((i + 1) / len(chunks)) * 90 + 10),
                    message=f"✅ Chunk {i + 1}/{len(chunks)} thành công!",
                )

                translated_chunks[i] = result
                prev_context = self._tail_context(result)

            # 4. Lưu kết quả
            full_translation = "\n\n".join(
                translated_chunks[i] for i in range(len(chunks)) if i in translated_chunks
            )

            final_path = self._resolve_output_path(output_file_path, output_filename)
            final_path.parent.mkdir(parents=True, exist_ok=True)
            final_path.write_text(full_translation, encoding="utf-8")

            # Dọn checkpoint sau khi thành công
            self.checkpoint_service.cleanup(output_filename)

            _try_calculate_stats()

            cache_info = f"{stats['cached']}/{len(chunks)} cache"
            tm_info = f", {stats['tm_hits']} TM" if stats["tm_hits"] > 0 else ""

            emit(
                "complete",
                message=f"Dịch hoàn tất! ({cache_info}{tm_info})",
                result=full_translation,
                chunks=len(chunks),
                cached=stats["cached"],
                tm_hits=stats["tm_hits"],
                source_length=len(text),
                translated_length=len(full_translation),
                output_file=final_path.name,
                tokens_used=stats["tokens"],
            )

            return full_translation

        except Exception as e:
            logger.error(f"Translation execution error: {e}", exc_info=True)
            emit("error", message=f"Lỗi: {e}")
            return None
        finally:
            # Luôn gỡ handler sau khi xong
            logging.root.removeHandler(ui_log_handler)

    def translate_file(
        self,
        filepath: Path,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Optional[str]:
        """Tiện ích đọc file và dịch."""
        try:
            text = filepath.read_text(encoding="utf-8")
            return self.translate_text(
                text, output_filename=filepath.stem, progress_callback=progress_callback
            )
        except Exception as e:
            if progress_callback:
                progress_callback({"type": "error", "message": f"Không thể đọc file {filepath.name}: {e}"})
            return None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _tail_context(self, text: str) -> str:
        """Lấy đoạn cuối của text làm context cho chunk kế tiếp."""
        ctx_len = self.config.get("context_char_count", 500)
        return text[-ctx_len:] if len(text) > ctx_len else text

    @staticmethod
    def _clean_chunk_result(text: str) -> str:
        """Làm sạch các thông báo kiểm tra thừa từ LLM ở cuối chunk."""
        import re
        # Pattern 1: Xóa block "[KIỂM TRA CUỐI CÙNG]" và nội dung phía sau
        pattern_check = r"\n[\-\*\_]{3,}\s*\n*(?:\*\*)?\[KIỂM TRA CUỐI CÙNG\](?:\*\*)?.*"
        text = re.sub(pattern_check, "", text, flags=re.IGNORECASE | re.DOTALL)
        
        # Pattern 2: Xóa "(Bản dịch tiếp tục...)"
        pattern_continue = r"\n[\-\*\_]{3,}\s*\n*(?:\*\s*)?\([B|b]ản dịch tiếp tục[^\)]*\)\*?.*"
        text = re.sub(pattern_continue, "", text, flags=re.IGNORECASE | re.DOTALL)
        
        # Pattern 3: Dọn dẹp line --- thừa ở cuối
        text = re.sub(r"\n+[\-\*\_]{3,}\s*$", "", text)
        
        return text.strip()

    @staticmethod
    def _resolve_output_path(explicit_path: Optional[Path], fallback_name: str) -> Path:
        """Xác định đường dẫn output file."""
        if explicit_path is not None:
            return Path(explicit_path)
        output_dir = Path("workspace/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return output_dir / f"{fallback_name}_{timestamp}.txt"

    def _translate_single_chunk(
        self,
        chunk: str,
        chunk_index: int,
        prev_context: str,
        output_filename: str,
        translation_memory: Optional[Any],
        stats: Dict[str, int],
        emit: Callable,
    ) -> Optional[str]:
        """
        Dịch một chunk đơn lẻ, xử lý cache/TM/glossary/API.

        Returns:
            Kết quả dịch, hoặc None nếu thất bại.
        """
        i = chunk_index

        # 1. Cache hit?
        cache_key = self.cache.build_key(chunk, self.prompts, self.config, prev_context)
        cached_result = self.cache.get(cache_key)
        if cached_result:
            stats["cached"] += 1
            emit("info", message=f"Chunk {i + 1}: Sử dụng cache ✅")
            return cached_result

        # 2. Translation Memory hit?
        if translation_memory:
            tm_match = translation_memory.find_match(chunk)
            if tm_match and tm_match.get("similarity", 0) >= 0.9:
                stats["tm_hits"] += 1
                emit("info", message=f"Chunk {i + 1}: TM match {tm_match['similarity']:.0%} 📚")
                return tm_match["translation"]

        # 3. Chuẩn bị prompt (nhúng Dynamic Glossary nếu có)
        chunk_prompts = copy.deepcopy(self.prompts)
        if self.glossary and self.glossary.is_active:
            main_prompt = chunk_prompts.get("main", "")
            enriched_prompt, term_count = self.glossary.inject_into_prompt(chunk, main_prompt)
            if term_count > 0:
                chunk_prompts["main"] = enriched_prompt
                emit("info", message=f"Chunk {i + 1}: Nhúng {term_count} thuật ngữ glossary")

        # 4. Gọi API dịch
        result, status, api_key = robust_translate(
            original_chunk=chunk,
            api_manager=self.api_manager,
            cache=self.cache,
            prompts=chunk_prompts,
            config_params=self.config,
            previous_chunk_context=prev_context,
        )

        if status == "success" and result:
            result = self._clean_chunk_result(result)
            if translation_memory:
                translation_memory.add_translation(chunk, result, output_filename)
            stats["tokens"] += len(chunk) // 2
            self.checkpoint_service.save_chunk(
                filename=output_filename,
                chunk_index=i,
                original_text=chunk,
                translated_text=result,
                api_key_used=api_key,
            )
            return result

        emit("error", message=f"Dịch thất bại tại chunk {i + 1}: {status}")
        return None
