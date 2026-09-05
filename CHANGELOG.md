# Changelog

Mọi thay đổi đáng chú ý của dự án được ghi tại đây, theo
[Keep a Changelog](https://keepachangelog.com/vi/1.1.0/) và
[Semantic Versioning](https://semver.org/lang/vi/).

## [2.6.0] - 2026-09-05
### Added
- Atomic write toàn repo (`core/file_handler.atomic_write_text`): output/config/prompt không bao giờ dở dang, crash giữ nguyên file cũ.
- Error taxonomy chuẩn (`core/errors.py` + `docs/02` §5.1): 429 đổi key, timeout/5xx retry cùng key tối đa 2 attempt/chunk, 401/404/rỗng/malformed dừng ngay; SSE thêm event `progress` (chunk/attempt/key).
- Contract prefs duy nhất (`normalize_prefs`): `get_config()` và `PUT /api/settings` cùng 1 nơi validate.
- Thư mục kết quả đổi `translated/` → `results/` (chứa bản dịch, bản dịch lại, bản nâng cao…), tự migrate file cũ sang.
- Trang Dự Án chỉ còn cards dự án (số file nguồn/kết quả, tiến độ, mở workspace, xóa).
- Workspace 3 cột: danh sách file (sources/results, kéo-thả upload, đổi tên, xóa, bulk) + editor nguồn + editor kết quả; click file nguồn tự nạp kết quả cùng tên; lưu vào `results/`.
- Tìm/thay thế kiểu Sigil cho 2 editor: regex, hoa/thường, cả từ, `$1` backref, đếm, trước/tiếp.
- Endpoint file: `GET .../file`, `DELETE .../files`, `POST .../rename`, `DELETE /api/projects/{slug}` (409 khi đang dịch).
- Gộp nhiều file dịch 1 phiên (`POST /api/translate/merge`): nối file với marker `===== FILE`, chia chunk, SSE ghi rõ chunk thuộc file nào, dialog ước lượng chunk + cảnh báo quá 2 chunk; giữ tùy chọn dịch tuần tự từng file.
- Dropzone gộp thẳng vào panel danh sách file (không ô riêng).
- `/api/health` trả `version` để phát hiện server chạy code cũ.
- Nút ↻ khởi động lại server ở sidebar (đúng mọi launcher nhờ argv tuyệt đối) + hiện version/giờ chạy + nhớ tab sau reload.
- Tìm/thay thế phạm vi tất cả file (`POST /api/find-replace`, Python re, atomic write từng file).
- Workspace: tabs Nguồn/Kết quả (nút dùng chung, đổi tab là thao tác mới), layout fluid khi thu gọn sidebar.
- Manifesto v2.5: chính sách lib local (thuần trước, minimal vendor sau, cấm framework/build-chain).
### Changed
- Manifesto v2.4: chốt local-first security (FULL key hiển thị, khỏi đề xuất lại) + điều kiện READ-FIRST + contract runtime SSOT (`config/config.json`, `config/providers.json`).
- Retry giữ nguyên: mỗi key thử 1 lần/chunk với 429 (không fallback model); network/5xx retry cùng key ≤2 attempt/chunk rồi dừng.
### Fixed
- Config/PUT /api/settings không còn ghi đè giá trị sai bằng default — giữ giá trị đang lưu khi input vô hiệu.

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
