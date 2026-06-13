# Kế hoạch hợp nhất — Content Translator

> **Mục đích:** Tài liệu duy nhất theo dõi tất cả kế hoạch phát triển, đã lọc bỏ các việc đã hoàn thành.
> **Ngày hợp nhất:** 2026-06-13

---

## ✅ Các kế hoạch đã hoàn thành

Các kế hoạch sau đã được thực thi 100% và đã xóa khỏi `docs/plans/`:

| Kế hoạch | Phiên bản | Ngày |
|----------|-----------|------|
| API Key Invalid Fix | v7.5.0 | 2026-06-13 |
| File Selection & Deletion Fix | v7.5.0 | 2026-06-11 |
| Tab State Preservation | v7.5.0 | 2026-06-11 |
| Provider Routing Fix (shim `/api/provider`, switchProvider, initProvider, loadModels) | v7.5.0 | 2026-06-11 |
| Generate tab Thông tin (dropdown source file, Generate/Lưu theo subtab) | v7.5.0 | 2026-06-11 |
| ProjectContextService + tích hợp prompt dịch | v7.5.0 | 2026-06-11 |
| ProjectContextService Unit Tests | v7.5.0 | 2026-06-13 |

---

## 📋 Các việc chưa hoàn thành

### A. Xóa Cache & Force Retranslate

> **Kế hoạch gốc:** `docs/plans/2026-06-11-clear-project-tm-force-retranslate-plan.md` (giữ lại để tham khảo chi tiết)

**Mục tiêu:** Loại bỏ Translation Cache, thêm Clear Project TM và Force Retranslate.

#### A.1 Dọn dẹp Cache

- [ ] **A.1.1** Xóa file `services/cache_service.py`
- [ ] **A.1.2** Cập nhật `is_cache_enabled()` trong `AppConfigService` luôn trả về `False`
- [ ] **A.1.3** Xóa test case `test_import_cache_service` trong `tests/unit/test_helpers.py`
- [ ] **A.1.4** Xóa import/logic cache trong `plugins/translation/translator.py` (`robust_translate`)
- [ ] **A.1.5** Xóa import/logic cache trong `core/executor.py`
- [ ] **A.1.6** Xóa import/logic cache trong `webui/routes/translation.py`
- [ ] **A.1.7** Xóa checkbox "Sử dụng cache" trong `tab_config.html`
- [ ] **A.1.8** Cứng `ENABLE_CACHE: 'false'` trong `api-client.js` (`saveAppConfig`)

#### A.2 API Endpoint Clear TM

- [ ] **A.2.1** Thêm endpoint `POST /api/projects/<slug>/tm/clear` trong `projects.py`
- [ ] **A.2.2** Thêm nút "Xóa TM dự án" trong `tab_projects.html`

#### A.3 Force Retranslate

- [ ] **A.3.1** Thêm checkbox "Dịch lại từ đầu" trong toolbar tab Biên tập (`tab_projects.html`)
- [ ] **A.3.2** Cập nhật `translation-worker.js` gửi `force_retranslate` trong payload
- [ ] **A.3.3** Backend: nhận `force_retranslate` trong `/api/projects/<slug>/translate` và dùng deploy config
- [ ] **A.3.4** Executor: bỏ qua checkpoint, cache, TM khi `force_retranslate=True`

#### A.4 Kiểm thử

- [ ] **A.4.1** Unit test: `TranslationExecutor` với `force_retranslate=True`
- [ ] **A.4.2** Unit test: route `POST /api/projects/<slug>/tm/clear`
- [ ] **A.4.3** Unit test: route `POST /api/projects/<slug>/translate` với payload `force_retranslate=true`
- [ ] **A.4.4** Chạy toàn bộ test suite: `uv run pytest`
- [ ] **A.4.5** Manual test theo checklist trong kế hoạch gốc

---

## 🗺️ Tài liệu tham khảo

- Kế hoạch gốc chi tiết (có source code): `docs/plans/2026-06-11-clear-project-tm-force-retranslate-plan.md`
- Roadmap tổng thể: `docs/ROADMAP.md`
- Lịch sử thay đổi: `CHANGELOG.md`
