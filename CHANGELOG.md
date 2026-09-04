# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi tại đây, theo
[Keep a Changelog](https://keepachangelog.com/vi/1.1.0/) và
[Semantic Versioning](https://semver.org/lang/vi/).

## [2.5.0] - 2026-09-04
### Added
- Trang Cấu Hình 5 khối (docs/wip/SETTINGS_REDESIGN_v2.5.md): CRUD provider OpenAI-compatible, model select + lọc Bao gồm/Loại trừ (Settings + Workspace), info panel (input/output/context/quota + link docs), thinking OFF/LOW/MEDIUM/HIGH (chỉ Gemini), prefs Chunk Size/API delay/Response timeout có label.
- Backend: model metadata full object, `GET /api/settings/model-info`, quota OpenRouter (`/auth/key`), `docs_url` mặc định theo host, `api_delay_seconds` (mặc định 2s giữa chunk chống 429), thinkingBudget cho Gemini.
- Quản lý AI động: `config/providers.json` SSOT, `core/provider_manager.py` (atomic write + backup, dynamic model listing cache 5 phút, namespace validation, migration 1 chiều từ `keys.json`), endpoint `GET /api/settings/providers`, `GET /api/settings/models?provider_id=`, `POST /api/settings/save`.
### Changed
- Single-user: trang Cấu Hình hiện FULL key, sửa/xóa trực tiếp trong danh sách; model dùng select nhìn thấy được + ô custom; chưa nhập key vẫn hiện fallback kèm cảnh báo rõ (trước đây gắn nhãn `api` gây nhầm).
- `main.py` làm điểm vào chính (tự bật WebUI server). CLI giữ nguyên, không đầu tư thêm.
### Fixed
- Không còn hardcode model trong code/config — model lấy live từ API nhà cung cấp, khắc phục model cũ ngừng hoạt động.

## [1.0.0] - 2026-09-04
### Added
- Phase 1 CLI working core: chunker `smartHardSplit` (`chunker.py`), prompt engine Unicode (`prompt_engine.py`), xoay key dùng chung (`key_rotator.py`), client Gemini (`ai_client.py`) + OpenAI-compatible (`openai_client.py`) qua interface `AIClient`, cấu hình đa provider (`config.py`), đọc/ghi an toàn (`file_handler.py`), CLI `run.py` (`--provider/--model/--prompt` explicit, dừng-ngay khi lỗi), SQLite index `workspace/app.db` (`app_db.py` + `schema.sql`).
- Phase 2 Lean WebUI: `main.py` stdlib (12 endpoint JSON + SSE `chunk/done/error`, 1 phiên in-flight, lọc `assets/glossary.txt` theo chunk), UI 1 file (`web/index.html`: 4 trang, sidebar thu gọn, dual-pane sync-scroll + inline-edit).
- Tài liệu `docs/` v2.3 (manifesto, spec lõi, kế hoạch 2 phase, API contract, roadmap; OCR tạm hoãn).
