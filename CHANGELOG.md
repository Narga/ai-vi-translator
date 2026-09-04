# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi tại đây, theo
[Keep a Changelog](https://keepachangelog.com/vi/1.1.0/) và
[Semantic Versioning](https://semver.org/lang/vi/).

## [Unreleased]

## [1.0.0] - 2026-09-04
### Added
- Phase 1 CLI working core: chunker `smartHardSplit` (`chunker.py`), prompt engine Unicode (`prompt_engine.py`), xoay key dùng chung (`key_rotator.py`), client Gemini (`ai_client.py`) + OpenAI-compatible (`openai_client.py`) qua interface `AIClient`, cấu hình đa provider (`config.py`), đọc/ghi an toàn (`file_handler.py`), CLI `run.py` (`--provider/--model/--prompt` explicit, dừng-ngay khi lỗi), SQLite index `workspace/app.db` (`app_db.py` + `schema.sql`).
- Phase 2 Lean WebUI: `server.py` stdlib (12 endpoint JSON + SSE `chunk/done/error`, 1 phiên in-flight, lọc `assets/glossary.txt` theo chunk), UI 1 file (`web/index.html`: 4 trang, sidebar thu gọn, dual-pane sync-scroll + inline-edit).
- Tài liệu `docs/` v2.3 (manifesto, spec lõi, kế hoạch 2 phase, API contract, roadmap; OCR tạm hoãn).
