# Kế hoạch thiết kế lại trang Cấu Hình (v2.5) — đã duyệt

> Nguồn: đối chiếu `docs/02`, `docs/04`, `docs/06` + pattern Novel-Translator
> (`tab_config.html`, `api-client.js`, `settings.py`).
> Quyết định đã chốt: thinking 4 mức · hiện quota khi lấy được · filter ở cả Settings + Workspace.

## 1. Bố cục trang mới — 5 khối có nhãn

- **A. Providers**: list + radio active ★, form `＋ Thêm provider` (tên, loại gemini/openai,
  base_url, key), nút xóa (chặn xóa active). Card mỗi provider: keys textarea full,
  `base_url` (chỉ openai), link `ⓘ Thông tin` (docs_url).
- **B. Model**: select + `🔄` + ô lọc tên + dropdown Bao gồm/Loại trừ + badge 🆓 +
  mục `…tự nhập…`. Panel info: Input/Output/Context/RPM/RPD — thiếu thì `—` + link docs.
- **C. Thinking** (mặc định OFF): OFF/LOW/MEDIUM/HIGH → thinkingBudget 0/1024/8192/24576.
  Chỉ áp dụng Gemini; OpenAI-compatible bỏ qua hoàn toàn (ghi chú + tooltip).
- **D. Request tuning**: Chunk Size (`max_chunk_chars`, ký tự), API delay
  (`api_delay_seconds` mới, giây giữa các chunk), Response timeout (`timeout_seconds`,
  đã có nhưng UI chưa lộ). Mỗi field có label + đơn vị + tooltip.
- **E. Lưu theo khối**: Lưu Provider / Lưu Prefs riêng.

## 2. Backend (stdlib + httpx, không thêm dep)

- `list_models` giữ full object `{id, name, context_length, pricing, is_free}`
  (OpenRouter có sẵn; Gemini REST `models/{m}` cho input/outputTokenLimit).
- Mới `GET /api/settings/model-info?provider_id=&model=` (fail-soft).
- Quota: OpenRouter `GET /api/v1/auth/key` (usage/limit); Gemini REST không trả
  quota → link AI Studio quotas page.
- Provider record thêm `docs_url` (default theo host quen) + `thinking: "OFF"`.
- CRUD: `POST /api/settings/providers`, `DELETE /api/settings/providers/{id}`
  + `add/remove_provider()` (atomic write).
- Prefs mới `api_delay_seconds`; sleep giữa các chunk ở `run.py` + vòng SSE.
- `thinking` per-provider, chỉ Gemini client đọc.
- CLI chỉ pass-through prefs mới, không đầu tư thêm.

## 3. Lọc model (Settings + Workspace)

Search + Bao gồm/Loại trừ, lọc client-side trên list đã fetch; giữ selection hiện tại
nếu còn, fallback về default_model.

## 4. Docs + test

- Cập nhật 02/04/README/CHANGELOG (Unreleased) + thinking-matrix.
- Tests: metadata parsers (mock), thinking mapping + skip ở openai client,
  prefs validate, add/remove provider, endpoint mới, filter giữ selection.
- Checklist tay: thêm provider → key → 🔄 thấy models + context/pricing →
  badge 🆓 → lọc Bao gồm/Loại trừ → info panel → đổi thinking → dịch thử 1 chunk.
