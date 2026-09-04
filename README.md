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

## Cấu hình API key (3 cách)

1. File `config/keys.json` (tự tạo khi chạy lần đầu, đã gitignore):
   ```json
   {"gemini_keys": ["AIzaSy..."], "openai_compat_keys": ["sk-or-..."]}
   ```
2. Biến môi trường: `GEMINI_API_KEYS`, `OPENAI_COMPAT_KEYS` (phân tách dấu phẩy).
3. Nhập trực tiếp khi CLI hỏi (tự lưu vào `config/keys.json`).

Cấu hình chung: `config/config.json` (`default_provider/default_model`,
danh sách `providers.*.models`, `max_chunk_chars: 16000`, `timeout_seconds: 90`).

## Phase 1 — CLI

```bash
# Dịch trực tiếp
python run.py input.txt output.txt --provider gemini --model gemini-2.5-flash
# Dịch theo dự án (file trong workspace/projects/{ten}/sources/)
python run.py --project Truyen --file ch01.md --provider openai_compat --model deepseek-chat
```

Nguyên tắc: mỗi chunk thử mỗi key 1 lần, 429 thì đổi key, hết key thì **dừng ngay,
không lưu dở dang** — chạy lại từ đầu. **Không fallback ngầm** sang model khác.
Mọi lượt chạy được log vào `workspace/app.db`.

## Phase 2 — WebUI

```bash
python server.py   # mở http://127.0.0.1:8000
```

4 trang: Dự Án → Biên Dịch (dual-pane sync-scroll, inline-edit, copy/save/retry) →
Prompt → Cấu Hình. Một phiên dịch tại một thời điểm, stream từng chunk qua SSE.

## Cấu trúc

```text
core/            chunker, prompt_engine, key_rotator, ai_client (Gemini),
                 openai_client, file_handler, config, app_db
prompts/         prompt *.txt (thêm file = thêm prompt)
run.py           CLI Phase 1        server.py  backend Phase 2 (stdlib)
web/index.html   UI 1 file          tools/     công cụ độc lập (EPUB…)
workspace/       sources/translated/assets + app.db (gitignore, riêng tư)
tests/           pytest (mock, không gọi API thật)
```

## Test

```bash
python -m pytest tests/ -q
```

## Thay đổi

Xem `CHANGELOG.md` (Keep a Changelog).
