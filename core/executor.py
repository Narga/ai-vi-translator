# core/executor.py - v5.0.1
# Tác giả: Narga
# Executor hợp nhất cho cả WebUI và CLI.

import copy
import json
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional

from services.api_service import ApiManager
from services.checkpoint_service import (
    CheckpointService,
    execution_drift,
    same_source_identity,
)
from services.glossary_service import GlossaryService
from plugins.translation.chunker import process_text_for_chunking
from plugins.translation.translator import robust_translate

logger = logging.getLogger(__name__)

_STATUS_TO_HTTP = {
    "censorship_blocked": 451,
    "auth_error": 401,
    "model_not_found": 404,
    "invalid_request": 400,
    "upstream_empty": 204,
}

_RETRYABLE_STATUSES = {"all_keys_exhausted", "upstream_empty", "api_error"}


def _status_to_http_status(status: str) -> Optional[int]:
    return _STATUS_TO_HTTP.get(status)


def _status_retryable(status: str) -> bool:
    return status in _RETRYABLE_STATUSES


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

        # Force retranslate mode
        self.force_retranslate = bool(config.get("force_retranslate", False))

        # Init checkpoint
        self.checkpoint_service = CheckpointService(
            self.config.get("checkpoint_dir") or "workspace/checkpoints"
        )

        # Init Dynamic Glossary
        self.glossary = GlossaryService(glossary_paths) if glossary_paths else None

        # Deep copy prompts để tránh mutate config gốc
        self.prompts: Dict[str, str] = copy.deepcopy(config.get("prompts", {}))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    
    def _build_checkpoint_identity(self, filename: str, source_text: str) -> Dict[str, str]:
        import hashlib
        import json
        source_hash = hashlib.sha256(source_text.encode()).hexdigest()
        prompts_str = json.dumps(self.prompts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        prompt_hash = hashlib.sha256(prompts_str.encode()).hexdigest()
        
        return {
            "project_file": filename,
            "project_slug": self.config.get("project_slug", ""),
            "source_hash": source_hash,
            "chunker_version": "v2",
            "chunk_size": str(self.config.get("chunk_size", 22000)),
            "provider_kind": self.config.get("provider_kind", "unknown"),
            "provider_id": self.config.get("provider_id", "unknown"),
            "base_url": self.config.get("base_url", "unknown"),
            "model": self.config.get("model_name", "unknown"),
            "qa_model": self.config.get("qa_model", "unknown"),
            "credential_mode": self.config.get("credential_mode", "default"),
            "prompt_hash": prompt_hash,
            "schema_version": "1.0",
        }

    def _tm_scope(self) -> str:
        """Scope TM theo provider, model và prompt để không tái sử dụng sai ngữ cảnh."""
        import hashlib
        import json
        prompt_data = json.dumps(self.prompts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        prompt_hash = hashlib.sha256(prompt_data.encode()).hexdigest()[:16]
        return ":".join((
            self.config.get("provider_kind", "default"),
            self.config.get("model_name", "default"),
            prompt_hash,
        ))

    def translate_text(
        self,
        text: str,
        output_filename: str = "translated",
        output_file_path: Optional[Path] = None,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        translation_memory: Optional[Any] = None,
        write_output: bool = True,
        job_id: Optional[str] = None,
        lease_keep_alive: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Thực hiện dịch thuật một đoạn văn bản lớn.

        Args:
            text: Nội dung cần dịch.
            output_filename: Tên file dùng để lưu checkpoint.
            output_file_path: Đường dẫn lưu file kết quả. Nếu None, lưu vào workspace/output.
            progress_callback: Hàm callback nhận thông tin tiến độ.
            translation_memory: Object TranslationMemory (tuỳ chọn).
            write_output: Có ghi file kết quả ra đĩa hay không (mặc định True).
            job_id: ID công việc để kiểm soát tiến trình (cancel).
            lease_keep_alive: Đối tượng LeaseKeepAlive kiểm soát lease heartbeat (P1.7).

        Returns:
            Nội dung đã dịch hoàn chỉnh, hoặc None nếu thất bại.
        """

        def emit(event_type: str, **kwargs: Any) -> None:
            if progress_callback:
                progress_callback({"type": event_type, **kwargs})

        def _is_aborted() -> Optional[str]:
            from backend.infrastructure.progress.runtime_state import RuntimeState
            if job_id and RuntimeState().is_cancelled(job_id):
                return "cancelled"
            if lease_keep_alive and getattr(lease_keep_alive, "abort_requested", False):
                return "lease_lost"
            return None

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

            # 2. Khởi tạo identity & state
            translated_chunks: Dict[int, str] = {}
            prev_context = ""
            start_index = 0
            identity = self._build_checkpoint_identity(output_filename, text)

            # 2. Force mode: cleanup checkpoint và tạo session mới
            if self.force_retranslate:
                emit("info", message="Force retranslate: bỏ qua checkpoint/cache/TM cho lần chạy này.")
                self.checkpoint_service.cleanup(output_filename)
                self.checkpoint_service.init_session(
                    filename=output_filename,
                    total_chunks=len(chunks),
                    chunks_text=chunks,
                    identity=identity,
                    reset=True,
                )

            # 3. Checkpoint Resume (chỉ khi không force)
            if not self.force_retranslate:
                resume_info = self.checkpoint_service.get_resume_info(output_filename)
                if resume_info and resume_info.get("can_resume"):
                    saved_identity = resume_info.get("identity") or {}
                    if not same_source_identity(saved_identity, identity):
                        emit("warning", message="Nội dung nguồn hoặc prompt đã thay đổi, bỏ qua checkpoint cũ và dịch lại từ đầu.")
                        self.checkpoint_service.cleanup(output_filename)
                        self.checkpoint_service.init_session(
                            filename=output_filename,
                            total_chunks=len(chunks),
                            chunks_text=chunks,
                            identity=identity,
                            reset=True,
                        )
                    else:
                        drift = execution_drift(saved_identity, identity)
                        if drift:
                            emit("info", message=f"Đổi cấu hình ({', '.join(drift)}) — giữ các chunk đã dịch.")
                        translated_chunks = self.checkpoint_service.get_translated_chunks(output_filename)
                        start_index = resume_info.get("next_chunk_index", 0)
                        emit("info", message=f"Resume từ chunk {start_index + 1}/{len(chunks)}")
                        emit("progress", percent=15, message=f"Resume từ chunk {start_index + 1}/{len(chunks)}")

                        if start_index > 0 and (start_index - 1) in translated_chunks:
                            prev_context = self._tail_context(translated_chunks[start_index - 1])
                else:
                    self.checkpoint_service.init_session(
                        filename=output_filename,
                        total_chunks=len(chunks),
                        chunks_text=chunks,
                        identity=identity,
                    )

            # 3. Dịch từng chunk
            stats = {"tokens": 0, "tm_hits": 0}

            for i in range(start_index, len(chunks)):
                if i in translated_chunks:
                    prev_context = self._tail_context(translated_chunks[i])
                    continue
                chunk = chunks[i]

                base_percent = int((i / len(chunks)) * 90 + 10)
                
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
                    is_aborted=_is_aborted,
                    lease_keep_alive=lease_keep_alive,
                )

                if result is None or (isinstance(result, dict) and result.get("_error")):
                    error_ctx = result.get("context") if isinstance(result, dict) else {}
                    fail_status = error_ctx.get("status") or "unknown_error"
                    if fail_status == "cancelled":
                        emit("cancelled", message=f"Đã dừng theo yêu cầu ở chunk {i + 1}/{len(chunks)}")
                        return None
                    emit("task_failed", error_context=error_ctx, checkpoint_key=output_filename)
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

            if len(translated_chunks) != len(chunks):
                abort_reason = _is_aborted()
                if abort_reason == "cancelled":
                    emit("cancelled", message="Dịch chưa hoàn tất do đã bị dừng.")
                else:
                    emit(
                        "task_failed",
                        error_context={
                            "status": abort_reason or "incomplete_chunks",
                            "http_status": None,
                            "retryable": True,
                            "message": "Dịch chưa hoàn tất: vẫn còn chunk chưa xử lý",
                        },
                        checkpoint_key=output_filename,
                    )
                return None

            # Guard 4: Kiểm tra trước khi assemble & ghi output cuối
            abort_reason = _is_aborted()
            if abort_reason:
                emit("cancelled" if abort_reason == "cancelled" else "task_failed",
                     message=f"Dừng trước khi ghi output: {abort_reason}")
                return None

            # Verification Gate
            is_complete, details = self.checkpoint_service.verify_checkpoint_completeness(output_filename)
            if not is_complete:
                emit(
                    "task_failed",
                    message="Verification Gate: phát hiện chunk thiếu hoặc không hợp lệ trước khi ghi output",
                    error_context={
                        "status": "verification_failed",
                        "missing_indices": details.get("missing_indices"),
                        "marker_violations": details.get("marker_violations"),
                    },
                    checkpoint_key=output_filename,
                )
                return None

            # 4. Lưu kết quả
            full_translation = "\n\n".join(
                translated_chunks[i] for i in range(len(chunks)) if i in translated_chunks
            )

            if write_output:
                final_path = self._resolve_output_path(output_file_path, output_filename)
                manifest_path = final_path.with_suffix(".manifest.json")

                def _durable_lease_guard() -> bool:
                    if _is_aborted():
                        return False
                    if lease_keep_alive and hasattr(lease_keep_alive, "is_durable_valid"):
                        if not lease_keep_alive.is_durable_valid():
                            return False
                    return True

                try:
                    # Last-mile fencing: Kiểm tra durable lease còn hợp lệ trong tasks.db trước khi atomic replace output
                    self.checkpoint_service.atomic_write_file(
                        final_path,
                        full_translation,
                        pre_replace_check=_durable_lease_guard,
                    )
                    output_file_name = final_path.name

                    # Phase 8: Bắt buộc tạo & ghi standard manifest sidecar v1.0
                    manifest = self.checkpoint_service.create_manifest(
                        checkpoint_key=output_filename,
                        provider_id=self.config.get("provider_id"),
                        model=self.config.get("model_name"),
                        output_text=full_translation,
                    )
                    if not isinstance(manifest, dict) or not manifest.get("is_complete"):
                        raise ValueError("Manifest contract v1.0 verification failed (incomplete)")
                    manifest_content = json.dumps(manifest, ensure_ascii=False, indent=2)
                    self.checkpoint_service.atomic_write_file(
                        manifest_path,
                        manifest_content,
                        pre_replace_check=_durable_lease_guard,
                    )
                except Exception as m_err:
                    logger.error(f"Lỗi bắt buộc ghi manifest: {m_err}")
                    # Cleanup output chưa hợp lệ / thiếu manifest
                    if final_path.exists():
                        try:
                            final_path.unlink()
                        except OSError:
                            pass
                    if manifest_path.exists():
                        try:
                            manifest_path.unlink()
                        except OSError:
                            pass

                    emit(
                        "task_failed",
                        message=f"Lỗi tạo standard manifest: {m_err}",
                        error_context={
                            "status": "manifest_generation_failed",
                            "http_status": None,
                            "retryable": True,
                            "message": f"Không thể tạo manifest hợp lệ: {m_err}",
                        },
                        checkpoint_key=output_filename,
                    )
                    return None
            else:
                output_file_name = output_file_path.name if output_file_path else f"{output_filename}.txt"

            # Dọn checkpoint sau khi thành công
            self.checkpoint_service.cleanup(output_filename)

            _try_calculate_stats()

            tm_info = f"{stats['tm_hits']} TM" if stats["tm_hits"] > 0 else "0 TM"

            emit(
                "complete",
                message=f"Dịch hoàn tất! ({tm_info})",
                result=full_translation,
                output_file=output_file_name,
                chunks=len(chunks),
                tokens=stats["tokens"],
                tm_hits=stats["tm_hits"],
            )

            return full_translation

        except Exception as e:
            self.checkpoint_service.set_status(output_filename, "interrupted")
            _try_calculate_stats()
            emit(
                "task_failed",
                error_context={
                    "status": "exception",
                    "http_status": None,
                    "retryable": True,
                    "message": f"Lỗi: {e}",
                },
                checkpoint_key=output_filename,
            )
            return None
        finally:
            # Luôn gỡ handler sau khi xong
            logging.root.removeHandler(ui_log_handler)

    def recover_from_checkpoint(
        self,
        source_checkpoint_key: str,
        recovery_checkpoint_key: str,
        output_file_path: Path,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        job_id: Optional[str] = None,
        lease_keep_alive: Optional[Any] = None,
    ) -> Optional[str]:
        """
        Recovery: chỉ dịch các chunk pending trong checkpoint mới.
        Checkpoint mới đã được clone + import done chunks từ phase preparation.

        Args:
            source_checkpoint_key: Checkpoint gốc (chỉ đọc, không mutate)
            recovery_checkpoint_key: Checkpoint recovery (đã có done + pending)
            output_file_path: Đường dẫn file output cuối
            progress_callback: Progress callback
            job_id: ID recovery job
            lease_keep_alive: Đối tượng LeaseKeepAlive kiểm soát lease heartbeat (P1.7)

        Returns:
            Translated text hoặc None nếu thất bại
        """
        def emit(event_type: str, **kwargs: Any) -> None:
            if progress_callback:
                progress_callback({"type": event_type, **kwargs})

        def _is_aborted() -> Optional[str]:
            from backend.infrastructure.progress.runtime_state import RuntimeState
            if job_id and RuntimeState().is_cancelled(job_id):
                return "cancelled"
            if lease_keep_alive and getattr(lease_keep_alive, "abort_requested", False):
                return "lease_lost"
            return None

        resume_info = self.checkpoint_service.get_resume_info(recovery_checkpoint_key)
        if not resume_info or not resume_info.get("can_resume"):
            emit("error", message="Checkpoint recovery không hợp lệ hoặc đã hoàn tất")
            return None

        total_chunks = resume_info["total_chunks"]
        start_index = resume_info["next_chunk_index"]
        translated_chunks = self.checkpoint_service.get_translated_chunks(recovery_checkpoint_key)

        done_count = len(translated_chunks)
        initial_pct = int((done_count / total_chunks) * 100) if total_chunks > 0 else 0
        emit("info", message=f"Recovery: resume từ chunk {start_index + 1}/{total_chunks}")
        emit(
            "progress",
            current=done_count,
            total=total_chunks,
            percent=initial_pct,
            message=f"Recovery: {done_count}/{total_chunks} chunk đã có",
            completed_chunks=done_count,
            checkpoint_key=recovery_checkpoint_key,
        )

        stats = {"tokens": 0, "tm_hits": 0}
        prev_context = ""

        if start_index > 0 and (start_index - 1) in translated_chunks:
            prev_context = self._tail_context(translated_chunks[start_index - 1])

        for i in range(start_index, total_chunks):
            abort_reason = _is_aborted()
            if abort_reason:
                emit("cancelled" if abort_reason == "cancelled" else "task_failed",
                     message=f"Recovery dừng ở chunk {i + 1}/{total_chunks}: {abort_reason}")
                return None
            if i in translated_chunks:
                prev_context = self._tail_context(translated_chunks[i])
                continue

            chunk_text = self.checkpoint_service._get_connection(recovery_checkpoint_key).execute(
                "SELECT original_text FROM chunks WHERE chunk_index = ?", (i,)
            ).fetchone()
            if not chunk_text:
                emit(
                    "task_failed",
                    message=f"Không tìm thấy chunk {i} trong checkpoint recovery",
                    error_context={"status": "missing_chunk", "chunk_index": i},
                    completed_chunks=len(translated_chunks),
                    checkpoint_key=recovery_checkpoint_key,
                )
                return None

            chunk = chunk_text[0]
            cur_done = len(translated_chunks)
            cur_pct = int((cur_done / total_chunks) * 100) if total_chunks > 0 else 0

            # P1 Phase 7 lease: emit progress TRƯỚC API call để touch heartbeat — nếu API
            # call lâu hơn lease timeout mà không có event nào, worker vẫn không bị đánh dấu
            # interrupted (heartbeat được làm mới ngay trước request).
            emit("progress", current=i + 1, total=total_chunks, percent=cur_pct,
                 message=f"Recovery: đang gửi chunk {i + 1}/{total_chunks}",
                 completed_chunks=cur_done, checkpoint_key=recovery_checkpoint_key)

            result = self._translate_single_chunk(
                chunk=chunk,
                chunk_index=i,
                prev_context=prev_context,
                output_filename=recovery_checkpoint_key,
                translation_memory=None,
                stats=stats,
                emit=emit,
                is_aborted=_is_aborted,
                lease_keep_alive=lease_keep_alive,
            )

            if result is None or (isinstance(result, dict) and result.get("_error")):
                error_ctx = result.get("context") if isinstance(result, dict) else {}
                fail_status = error_ctx.get("status") or "unknown_error"
                if fail_status == "cancelled":
                    emit("cancelled", message=f"Recovery dừng theo yêu cầu ở chunk {i + 1}/{total_chunks}")
                    return None
                emit(
                    "task_failed",
                    message=f"Recovery thất bại tại chunk {i + 1}: {fail_status}",
                    error_context={
                        "status": fail_status,
                        "http_status": error_ctx.get("http_status"),
                        "retryable": error_ctx.get("retryable", False),
                        "message": f"Recovery thất bại tại chunk {i + 1}: {fail_status}",
                        "chunk_index": i,
                    },
                    completed_chunks=len(translated_chunks),
                    checkpoint_key=recovery_checkpoint_key,
                )
                return None

            translated_chunks[i] = result
            prev_context = self._tail_context(result)

            done_after = len(translated_chunks)
            pct_after = int((done_after / total_chunks) * 100) if total_chunks > 0 else 0
            emit("progress", current=i + 1, total=total_chunks, percent=pct_after,
                 message=f"Recovery: hoàn thành chunk {i + 1}/{total_chunks}",
                 completed_chunks=done_after, checkpoint_key=recovery_checkpoint_key)

        # Guard 4: Kiểm tra trước khi assemble & ghi output cuối
        abort_reason = _is_aborted()
        if abort_reason:
            emit("cancelled" if abort_reason == "cancelled" else "task_failed",
                 message=f"Recovery dừng trước khi ghi output: {abort_reason}",
                 completed_chunks=len(translated_chunks),
                 checkpoint_key=recovery_checkpoint_key)
            return None

        # Phase 8: Verification Gate (Kiểm tra 100% chunk 0..total-1 trong SQLite & Zero-marker)
        is_complete, details = self.checkpoint_service.verify_checkpoint_completeness(recovery_checkpoint_key)
        if not is_complete:
            emit(
                "task_failed",
                message="Verification Gate: checkpoint recovery chưa hoàn chỉnh hoặc phát hiện marker lỗi",
                error_context={
                    "status": "verification_failed",
                    "missing_indices": details.get("missing_indices"),
                    "marker_violations": details.get("marker_violations"),
                    "done_count": details.get("done_count"),
                    "total_chunks": total_chunks,
                },
                completed_chunks=details.get("done_count", len(translated_chunks)),
                checkpoint_key=recovery_checkpoint_key,
            )
            return None

        full_translation = "\n\n".join(
            translated_chunks[i] for i in range(total_chunks) if i in translated_chunks
        )

        # Atomic file write với Last-mile durable fencing (Phase 8: ghi ra .tmp -> fsync -> pre_replace_check -> replace)
        manifest_path = output_file_path.with_suffix(".manifest.json")

        def _durable_lease_guard() -> bool:
            if _is_aborted():
                return False
            if lease_keep_alive and hasattr(lease_keep_alive, "is_durable_valid"):
                if not lease_keep_alive.is_durable_valid():
                    return False
            return True

        try:
            self.checkpoint_service.atomic_write_file(
                output_file_path,
                full_translation,
                pre_replace_check=_durable_lease_guard,
            )

            # Tạo & ghi Manifest sidecar chuẩn v1.0 (Phase 8: Bắt buộc)
            provider_info = self.config or {}
            manifest = self.checkpoint_service.create_manifest(
                checkpoint_key=recovery_checkpoint_key,
                source_task_id=source_checkpoint_key,
                recovery_task_id=job_id,
                provider_id=provider_info.get("provider_id"),
                model=provider_info.get("model_name"),
                output_text=full_translation,
            )
            if not isinstance(manifest, dict) or not manifest.get("is_complete"):
                raise ValueError("Recovery manifest incomplete: verification gate failed")
            self.checkpoint_service.atomic_write_file(
                manifest_path,
                json.dumps(manifest, ensure_ascii=False, indent=2),
                pre_replace_check=_durable_lease_guard,
            )
        except Exception as m_err:
            logger.error(f"Lỗi bắt buộc ghi manifest trong recovery: {m_err}")
            if output_file_path.exists():
                try:
                    output_file_path.unlink()
                except OSError:
                    pass
            if manifest_path.exists():
                try:
                    manifest_path.unlink()
                except OSError:
                    pass

            emit(
                "task_failed",
                message=f"Lỗi tạo recovery manifest: {m_err}",
                error_context={
                    "status": "manifest_generation_failed",
                    "http_status": None,
                    "retryable": True,
                    "message": f"Không thể tạo manifest recovery hợp lệ: {m_err}",
                },
                completed_chunks=total_chunks,
                checkpoint_key=recovery_checkpoint_key,
            )
            return None

        emit(
            "complete",
            message=f"Recovery hoàn thành: {total_chunks}/{total_chunks} chunks",
            completed_chunks=total_chunks,
            total_chunks=total_chunks,
            final_output_path=str(output_file_path),
            manifest_path=str(manifest_path),
            output_hash=manifest.get("output_hash"),
            checkpoint_key=recovery_checkpoint_key,
            output_file=output_file_path.name,
            chunks=total_chunks,
        )

        return full_translation

    def translate_file(
        self,
        filepath: Path,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        job_id: Optional[str] = None,
    ) -> Optional[str]:
        """Tiện ích đọc file và dịch."""
        try:
            text = filepath.read_text(encoding="utf-8")
            return self.translate_text(
                text, output_filename=filepath.stem, progress_callback=progress_callback, job_id=job_id
            )
        except Exception as e:
            if progress_callback:
                progress_callback({"type": "error", "message": f"Không thể đọc file {filepath.name}: {e}"})
            return None

    def spellcheck_text(
        self,
        text: str,
        output_filename: str = "spellchecked",
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        job_id: Optional[str] = None,
    ) -> Optional[tuple]:
        """
        Soát lỗi chính tả cho toàn bộ văn bản, tái dùng hoàn toàn:
        - process_text_for_chunking (cùng chunker)
        - CheckpointService (key phân biệt bằng prefix 'spell:')
        - ApiManager & robust_translate (cùng client pool, xoay vòng key)

        Khác biệt duy nhất so với translate_text:
        - Prompt lấy từ self.prompts['chinh_ta'] (fallback 'main')
        - Kết quả mỗi chunk được tách qua _parse_spellcheck_chunk

        Returns:
            Tuple[clean_text, error_log] hoặc None nếu thất bại.
        """
        def emit(event_type: str, **kwargs) -> None:
            if progress_callback:
                progress_callback({"type": event_type, **kwargs})

        ui_log_handler = ProgressLogHandler(emit)
        logging.root.addHandler(ui_log_handler)

        try:
            emit("progress", percent=5, message="Đang chia nhỏ văn bản để soát lỗi...")
            chunk_size = self.config.get("chunk_size", 22000)
            chunks = process_text_for_chunking(
                text, min_chars=chunk_size - 2000, max_chars=chunk_size
            )
            emit("info", message=f"Đã chia thành {len(chunks)} chunks")
            emit("progress", percent=10, message=f"Đã chia thành {len(chunks)} chunks")

            # Checkpoint key phân biệt với translate bằng prefix “spell:”
            ck_key = f"spell:{output_filename}"
            identity = self._build_checkpoint_identity(output_filename, text)

            if not self.force_retranslate:
                resume_info = self.checkpoint_service.get_resume_info(ck_key)
                can_resume = False
                
                if resume_info and resume_info.get("total_chunks") == len(chunks):
                    saved_ident = resume_info.get("identity", {})
                    if saved_ident == identity:
                        can_resume = True
                    else:
                        emit("info", message="Thông số soát lỗi thay đổi. Bỏ qua checkpoint cũ...")
                
                if can_resume:
                    start_index = resume_info.get("next_chunk_index", 0)
                    done_chunks = self.checkpoint_service.get_translated_chunks(ck_key)
                    emit("info", message=f"Resume soát lỗi từ chunk {start_index + 1}/{len(chunks)}")
                else:
                    start_index = 0
                    done_chunks = {}
                    self.checkpoint_service.init_session(ck_key, len(chunks), chunks, identity=identity, reset=True)
            else:
                self.checkpoint_service.cleanup(ck_key)
                self.checkpoint_service.init_session(ck_key, len(chunks), chunks, identity=identity, reset=True)
                start_index = 0
                done_chunks = {}

            clean_parts: Dict[int, str] = {}
            log_parts: Dict[int, str] = {}

            # Khôi phục kết quả từ checkpoint (nếu resume)
            for idx, raw in done_chunks.items():
                clean, log = self._parse_spellcheck_chunk(raw)
                clean_parts[idx] = clean
                log_parts[idx] = f"--- Đoạn {idx + 1} ---\n{log}" if log else ""

            spellcheck_prompt = self.prompts.get("chinh_ta", self.prompts.get("main", ""))

            for i in range(start_index, len(chunks)):
                from backend.infrastructure.progress.runtime_state import RuntimeState
                if RuntimeState().is_cancelled(job_id):
                    emit("info", message="Đã dừng theo yêu cầu")
                    # Emit cancelled terminal event và return — không cleanup checkpoint
                    # để có thể resume lại lần sau.
                    emit("cancelled", message=f"Đã hủy ở đoạn {i + 1}/{len(chunks)}")
                    return None

                base_percent = 10 + int((i / len(chunks)) * 90)
                emit("progress", current=i + 1, total=len(chunks),
                     percent=base_percent + 2,
                     message=f"Đang gửi đoạn {i + 1}/{len(chunks)} đến AI...")

                # robust_translate đã được import ở đầu file, tái dùng trực tiếp
                result, status, api_key_used = robust_translate(
                    original_chunk=chunks[i],
                    api_manager=self.api_manager,
                    prompts={"main": spellcheck_prompt},
                    config_params=self.config,
                    previous_chunk_context="",
                )

                if status != "success" or not result:
                    emit("error", message=f"Soát lỗi thất bại tại đoạn {i + 1}: {status}")
                    # Không được biến chunk lỗi thành kết quả sạch hoặc complete giả.
                    return None

                clean, log = self._parse_spellcheck_chunk(result)
                clean_parts[i] = clean
                log_parts[i] = f"--- Đoạn {i + 1} ---\n{log}" if log else ""

                # Lưu kết quả thô vào checkpoint (để resume có thể parse lại)
                self.checkpoint_service.save_chunk(
                    filename=ck_key,
                    chunk_index=i,
                    original_text=chunks[i],
                    translated_text=result,
                    api_key_used=api_key_used,
                )

                emit("progress", current=i + 1, total=len(chunks),
                     percent=int(((i + 1) / len(chunks)) * 90 + 10),
                     message=f"✅ Soát lỗi đoạn {i + 1}/{len(chunks)} thành công!")

            full_clean = "\n".join(clean_parts.get(i, "") for i in range(len(chunks)))
            full_log = "\n\n".join(log_parts.get(i, "") for i in range(len(chunks)) if log_parts.get(i))

            self.checkpoint_service.cleanup(ck_key)

            emit("complete", message="Soát lỗi chính tả hoàn tất!", result=full_clean, error_log=full_log)
            return full_clean, full_log

        except Exception as e:
            logger.error(f"Lỗi không xác định trong quá trình soát lỗi: {e}", exc_info=True)
            emit("error", status="fatal_error", message=str(e))
            return None
        finally:
            logging.root.removeHandler(ui_log_handler)

    def _parse_spellcheck_chunk(self, result: str) -> tuple:
        """Tách kết quả chunk của prompt chính tả thành (clean_text, error_log)."""
        lines = result.split("\n")
        clean = []
        log = []
        in_log = False
        for line in lines:
            if not in_log and "|" in line and ("---" in line or "Từ gốc" in line):
                in_log = True
            (log if in_log else clean).append(line)
        if log:
            return "\n".join(clean).strip(), "\n".join(log).strip()
        return result.strip(), ""

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
        is_aborted: Optional[Callable[[], Optional[str]]] = None,
        lease_keep_alive: Optional[Any] = None,
    ) -> Any:
        """
        Dịch một chunk đơn lẻ, xử lý TM/glossary/API và kiểm soát 5 Guard points.

        Returns:
            Kết quả dịch (str), hoặc dict {"_error": True, "context": {...}} nếu thất bại.
        """
        i = chunk_index

        # Guard 1: Trước API call
        if is_aborted:
            reason = is_aborted()
            if reason:
                logger.warning(f"🚨 [GUARD_1_ABORT] Bỏ qua chunk {i + 1} do worker bị dừng: {reason}")
                return {"_error": True, "context": {"status": reason, "message": f"Worker aborted: {reason}", "chunk_index": i}}

        # Force mode: bỏ qua TM
        if not self.force_retranslate and translation_memory:
            tm_match = translation_memory.find_match(chunk, provider_kind=self._tm_scope())
            if tm_match and tm_match.get("similarity", 0) >= 0.9:
                stats["tm_hits"] += 1
                emit("info", message=f"Chunk {i + 1}: TM match {tm_match['similarity']:.0%} 📚")
                return tm_match["translation"]

        # Chuẩn bị prompt (nhúng Dynamic Glossary nếu có)
        chunk_prompts = copy.deepcopy(self.prompts)
        if self.glossary and self.glossary.is_active:
            main_prompt = chunk_prompts.get("main", "")
            enriched_prompt, term_count = self.glossary.inject_into_prompt(chunk, main_prompt)
            if term_count > 0:
                chunk_prompts["main"] = enriched_prompt
                emit("info", message=f"Chunk {i + 1}: Nhúng {term_count} thuật ngữ glossary")

        # Gọi API dịch
        result, status, api_key_used = robust_translate(
            original_chunk=chunk,
            api_manager=self.api_manager,
            prompts=chunk_prompts,
            config_params=self.config,
            previous_chunk_context=prev_context,
        )

        # Guard 2: Sau API call (Hủy response nếu lease đã mất trong lúc chờ mạng)
        if is_aborted:
            reason = is_aborted()
            if reason:
                logger.warning(f"🚨 [GUARD_2_ABORT] Nhận kết quả chunk {i + 1} nhưng lease đã mất ({reason}) -> Hủy response!")
                return {"_error": True, "context": {"status": reason, "message": f"Worker aborted: {reason}", "chunk_index": i}}

        # Guard 3: Trước Checkpoint Save (Atomic Fencing CAS)
        if status == "success" and result:
            if is_aborted:
                reason = is_aborted()
                if reason:
                    logger.warning(f"🚨 [GUARD_3_ABORT] Bỏ qua lưu checkpoint chunk {i + 1} ({reason})")
                    return {"_error": True, "context": {"status": reason, "message": f"Worker aborted: {reason}", "chunk_index": i}}

            result = self._clean_chunk_result(result)
            if translation_memory:
                translation_memory.add_translation(chunk, result, output_filename, provider_kind=self._tm_scope())
            stats["tokens"] += len(chunk) // 2
            epoch = getattr(lease_keep_alive, "lease_epoch", None) if lease_keep_alive else None
            token = getattr(lease_keep_alive, "lease_token", None) if lease_keep_alive else None
            lease_val = lease_keep_alive.is_durable_valid if (lease_keep_alive and hasattr(lease_keep_alive, "is_durable_valid")) else None
            saved = self.checkpoint_service.save_chunk(
                filename=output_filename,
                chunk_index=i,
                original_text=chunk,
                translated_text=result,
                api_key_used=api_key_used,
                lease_epoch=epoch,
                lease_token=token,
                lease_validator=lease_val,
            )
            if not saved:
                logger.warning(
                    f"🚨 [GUARD_3_CAS_FAIL] Checkpoint rejected chunk {i + 1} vì lease mismatch (epoch={epoch}, token={token})!"
                )
                return {
                    "_error": True,
                    "context": {
                        "status": "lease_lost",
                        "http_status": 409,
                        "retryable": False,
                        "message": f"Checkpoint CAS rejected write for chunk {i + 1} (lease expired or stolen)",
                        "chunk_index": i,
                    },
                }

            return result

        error_context = {
            "chunk_index": i,
            "status": status,
            "http_status": _status_to_http_status(status),
            "retryable": _status_retryable(status),
            "message": f"Dịch thất bại tại chunk {i + 1}: {status}",
        }
        emit("error", **error_context)
        return {"_error": True, "context": error_context}
