# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi tại đây, theo
[Keep a Changelog](https://keepachangelog.com/vi/1.1.0/) và
[Semantic Versioning](https://semver.org/lang/vi/).

## [Unreleased]
### Added
- M0: cấu hình đa provider (`config.py`), SQLite index `workspace/app.db` (`app_db.py` + `schema.sql`).
- M1: cắt chunk tự nhiên `smartHardSplit` (`chunker.py`), nạp prompt Unicode (`prompt_engine.py`).
- M2: xoay key dùng chung (`key_rotator.py`), client Gemini (`ai_client.py`) + OpenAI-compatible (`openai_client.py`) qua interface `AIClient`. Test mock dùng `asyncio.run` stdlib (môi trường thiếu `pytest-asyncio`).
- M3-M4: đọc/ghi an toàn (`file_handler.py`, sanitize + `relative_to()`), CLI `run.py` (`--provider/--model/--prompt` explicit, dừng-ngay khi lỗi, log `runs` vào app.db).
- Phase 2: `server.py` stdlib (12 endpoint JSON + SSE `chunk/done/error`, 1 phiên in-flight, lọc `assets/glossary.txt` theo chunk), WebUI 1 file (`web/index.html`: 4 trang, sidebar thu gọn, dual-pane sync-scroll + inline-edit).

## [1.0.0] - 2026-09-04
### Added
- Phase 1 CLI working core: chunker, prompt engine, Gemini + OpenAI-compatible clients, key rotation, safe file handler, SQLite index (`workspace/app.db`).
- Phase 2 Lean WebUI: `server.py` stdlib + 12 endpoint JSON + SSE dịch tuần tự, UI 4 trang siêu nhẹ.
