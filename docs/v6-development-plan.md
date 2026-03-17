# Content Translator v6.0 – Kế hoạch phát triển

> Tài liệu này theo dõi tiến trình phát triển v6.0, tích hợp multi-provider AI và tái cấu trúc giao diện.

## Tổng quan kiến trúc v6.0

```
templates/
├── index.html              ← Composition (6 includes)
└── partials/
    ├── header.html          ← DOCTYPE, head, navbar
    ├── tab_workspace.html   ← Tab Dự án (sources, translated, prompt, profile)
    ├── tab_config.html      ← Tab Cấu hình (dual-provider Gemini/OpenAI)
    ├── tab_prompts.html     ← Tab Prompts (genre manager)
    ├── tab_plugins.html     ← Tab Plugins (EPUB, OCR)
    └── footer.html          ← Modals, toast, scripts

services/
├── genai_client.py          ← Google Gemini SDK wrapper (có sẵn)
├── openai_client.py         ← [NEW] OpenAI SDK wrapper (sync + async)
├── ai_provider.py           ← [NEW] Adapter pattern + Factory
└── ...

webui/
├── helpers.py               ← [MODIFIED] Provider-aware functions
└── routes/
    └── settings.py          ← [MODIFIED] 4 new API endpoints
```

## Trạng thái các Phase

### ✅ Phase 1: Multi-Provider AI Integration (DONE)

| File | Thay đổi |
|------|----------|
| `services/openai_client.py` | **[NEW]** Sync + Async OpenAI wrapper |
| `services/ai_provider.py` | **[NEW]** Protocol adapter + Factory |
| `templates/index.html` | Tách thành 6 partials (Jinja2 include) |
| `templates/partials/*.html` | **[NEW]** 6 template chuyên biệt |
| `config/app.ini` | Thêm `[PROVIDER]`, `[OPENAI]` sections |
| `.env.example` | Thêm `OPENAI_API_KEY` |
| `requirements.txt` | Thêm `openai>=1.0.0` |
| `webui/helpers.py` | 7 functions mới cho provider |
| `webui/routes/settings.py` | 4 API endpoints mới |
| `static/css/style.css` | CSS dual-provider grid |
| `static/js/main.js` | 4 JS functions provider |

**API Endpoints mới:**
- `GET /api/provider` – Lấy provider đang hoạt động
- `POST /api/provider` – Chuyển đổi provider (gemini ↔ openai)
- `GET /api/openai/models` – Liệt kê models OpenAI/OpenRouter
- `POST /api/openai/config` – Lưu cấu hình OpenAI

### ✅ Phase 2: Project Workflow Tabs 1–3 (DONE)

| File | Thay đổi |
|------|----------|
| `webui/routes/projects.py` | Thêm `genre` vào project metadata (create + update) |
| `templates/partials/footer.html` | **[NEW]** Modal tạo dự án với genre selector |
| `templates/partials/tab_workspace.html` | Genre badge, inline chunk-size input, `.html/.epub` upload |
| `static/js/main.js` | Modal-based `showCreateProjectDialog()`, `initProjectDialog()`, genre display, chunk-size inline |

**Tab 1 Info:** Genre selector liên kết với prompt sets, hiển thị badge màu tím.
**Tab 2 Files:** Inline chunk-size input cạnh nút chia chunk (placeholder = config mặc định).
**Tab 3 Translation:** Đã hoàn thể từ v5.0 (SBS editor, sync scroll, save inline).

### ⬜ Phase 3: Tab 4 Guidelines
- AI summarization (tóm tắt tự động)
- Bảng nhân vật, thuật ngữ, ghi chú bổ sung
- Textarea chỉnh sửa trực tiếp

### ⬜ Phase 4: Tab 5 Prompts
- Nạp prompt từ thư viện chuẩn
- Lưu prompt riêng cho dự án
- Ưu tiên prompt dự án > prompt hệ thống

### ⬜ Phase 5: HTML/Markdown Preservation
- Thuật toán bảo toàn cấu trúc markup
- Cập nhật prompt chính `01-main.txt`

## Ghi chú kỹ thuật

- **Lint errors**: Tất cả do Pyre2 IDE chưa cấu hình venv – không phải lỗi code thực tế
- **Template splitting**: `index.html` 729 dòng → 6 dòng composition. Mỗi partial chỉnh sửa độc lập.
- **Provider UI**: CSS grid + opacity/pointer-events disable cột không active
- **Tab 3**: SBS editor đã có từ v5.0 (sync scroll, save inline)
- Cần `pip install openai` trước khi test OpenAI provider
