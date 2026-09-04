# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi tại đây, theo
[Keep a Changelog](https://keepachangelog.com/vi/1.1.0/) và
[Semantic Versioning](https://semver.org/lang/vi/).

## [Unreleased]
### Added
- Quản lý AI động theo `docs/06`: `config/providers.json` SSOT, `core/provider_manager.py` (atomic write + backup, mask key, sentinel protection, dynamic model listing cache 5 phút, namespace validation, migration 1 chiều từ `keys.json`), 3 endpoint (`providers/models/save`), trang Cấu Hình làm lại (chọn provider, datalist model live, tự nhập custom).
### Fixed
- Không còn hardcode model trong code/config — model lấy live từ API nhà cung cấp, khắc phục model cũ ngừng hoạt động.

## [1.0.0] - 2026-09-04
### Added
- Phase 1 CLI working core: chunker `smartHardSplit` (`chunker.py`), prompt engine Unicode (`prompt_engine.py`), xoay key dùng chung (`key_rotator.py`), client Gemini (`ai_client.py`) + OpenAI-compatible (`openai_client.py`) qua interface `AIClient`, cấu hình đa provider (`config.py`), đọc/ghi an toàn (`file_handler.py`), CLI `run.py` (`--provider/--model/--prompt` explicit, dừng-ngay khi lỗi), SQLite index `workspace/app.db` (`app_db.py` + `schema.sql`).
- Phase 2 Lean WebUI: `server.py` stdlib (12 endpoint JSON + SSE `chunk/done/error`, 1 phiên in-flight, lọc `assets/glossary.txt` theo chunk), UI 1 file (`web/index.html`: 4 trang, sidebar thu gọn, dual-pane sync-scroll + inline-edit).
- Tài liệu `docs/` v2.3 (manifesto, spec lõi, kế hoạch 2 phase, API contract, roadmap; OCR tạm hoãn).
