# Content Translator (Next-Gen)

Công cụ gửi nội dung cho AI và nhận bản dịch về — phục vụ duy nhất một người dùng.
Tôn chỉ: **Minimalist — Single-User — Nhanh — UI siêu nhẹ**. Chi tiết kiến trúc xem `docs/`.

## Yêu cầu

- Python ≥ 3.12, chỉ 1 dependency runtime: `httpx`
- API key: Google Gemini và/hoặc provider OpenAI-compatible (OpenRouter, Groq, DeepSeek, Ollama)

## Cài đặt

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install "httpx>=0.27.0"
```

## Cấu hình AI (không hardcode model)

`config/providers.json` là nguồn sự thật duy nhất (chi tiết `docs/06_AI_MODELS_MANAGEMENT_SPEC.md`).
Model lấy **live từ API nhà cung cấp** (cache 5 phút), chọn trên WebUI trang Cấu Hình
hoặc tự nhập custom model. File chứa secret nên đã gitignore.

Nhập key: WebUI Cấu Hình (hiển thị đầy đủ, sửa trực tiếp) → hoặc CLI tự hỏi khi thiếu.
`keys.json` cũ được migrate tự động 1 lần.

Cấu hình chung: `config/config.json` (`max_chunk_chars`, `api_delay_seconds`,
`timeout_seconds`, `default_prompt`). Provider/model/thinking chỉnh trên WebUI trang Cấu Hình.

## Phase 1 — CLI

```bash
# Dịch trực tiếp (dùng active provider + default_model)
python run.py input.txt output.txt
# Override provider/model
python run.py input.txt output.txt --provider openai-compat --model deepseek-chat
# Dịch theo dự án (file trong workspace/projects/{ten}/sources/)
python run.py --project Truyen --file ch01.md
```

Nguyên tắc: mỗi chunk thử mỗi key 1 lần, 429 thì đổi key, hết key thì **dừng ngay,
không lưu dở dang** — chạy lại từ đầu. **Không fallback ngầm** sang model khác.
Mọi lượt chạy được log vào `workspace/app.db`.

## Phase 2 — WebUI (chính)

```bash
python main.py   # mở http://127.0.0.1:8000 (WebUI backend trong cùng file)
```

4 trang: Dự Án (cards, tiến độ, lưu trữ, lịch sử) → Biên Dịch 3 cột (file sources/results theo tab, dual editor, tìm/thay regex 1 file + tất cả file, gộp/tuần tự, hủy, tiến độ) →
Prompt (đổi tên/xóa/backup vào dự án) → Cấu Hình. Một phiên dịch tại một thời điểm, stream từng chunk qua SSE, atomic write bảo vệ output.

## Cấu trúc

```text
core/            chunker, prompt_engine, key_rotator, ai_client (Gemini),
                 openai_client, file_handler, config, app_db, errors
prompts/         prompt *.txt (thêm file = thêm prompt)
run.py           CLI Phase 1        main.py  WebUI backend (stdlib http.server)
web/index.html   UI shell           web/css/   tokens + components
web/js/          JS theo trang (app/projects/workspace/findreplace/prompts/settings/init)
web/vendor/      lib vendored khi duyệt (hiện trống, xem manifesto §9)
workspace/       sources/results/assets + archive/ + app.db (gitignore, riêng tư)
tests/           pytest (mock, không gọi API thật)
```

## Test

```bash
python -m pytest tests/ -q
```

## Thay đổi

Xem `CHANGELOG.md` (Keep a Changelog).
