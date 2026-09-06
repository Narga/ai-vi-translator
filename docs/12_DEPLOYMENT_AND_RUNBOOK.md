# 12. TRIỂN KHAI & VẬN HÀNH LOCAL (RUNBOOK)

> Đối tượng: 1 người dùng, máy local. Không Docker, không VPS cứng nhắc — nhưng làm đúng các bước dưới để cập nhật code không bao giờ rơi vào bẫy "server cũ".

## 1. Cài đặt mới

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install "httpx>=0.27.0"
python3 main.py            # hoặc: uv run python main.py
# mở http://127.0.0.1:8000
```

Tùy chọn host/port: `python3 main.py 127.0.0.1 8000`. Chỉ bind `127.0.0.1` (không `0.0.0.0` — app không có auth theo manifesto §7).

## 2. Cập nhật code (quy trình chuẩn — tránh server cũ)

1. `git pull` (hoặc checkout branch) trong thư mục dự án.
2. Bấm nút **↻ Khởi động lại server** cuối sidebar (hoặc `POST /api/restart`).
3. Chờ trang tự tải lại sau ~3 giây.
4. Kiểm tra chân sidebar: version phải khớp CHANGELOG mới nhất. Lệch = tiến trình cũ chưa chết → `pkill -f "main.py"` rồi chạy lại.
5. Kiểm tra nhanh: `curl -s localhost:8000/api/health` → `{"ok":true,"version":"<mới>","started_at":"..."}`.

Tuyệt đối không chỉ refresh trình duyệt sau khi pull code — `index.html` thì tươi nhưng tiến trình Python vẫn chạy code cũ (bài học v2.6.0: bản dịch chui vào `translated/` đã xóa).

> **Restart khi đang dịch:** process mới sạch hoàn toàn (lock trong RAM, không kế thừa); SSE cũ đứt ngay; output dở dang không bao giờ được ghi (atomic write); phiên đang chạy coi như hủy. Không test `execv` thật trong pytest — chỉ test `_restart_args()` trả đường dẫn tuyệt đối.

## 3. Sao lưu (backup thủ công, khi cần)

```bash
cd /path/to/content-translator
tar -czf backup-$(date +%F).tgz config/ workspace/ prompts/ *.txt
```

- `config/` — providers, keys, prefs (bí mật, không push git).
- `workspace/` — sources/results/assets/archive + `app.db` (đã gitignore).
- `prompts/` — prompt chung (track git rồi, nhưng backup kèm cho chắc).
- Khôi phục project đã lưu trữ: giải nén `workspace/archive/{slug}.zip` vào `workspace/projects/`.

## 4. Bố cục dữ liệu

```text
workspace/projects/{slug}/sources/    file gốc (.txt/.md/.html)
workspace/projects/{slug}/results/    kết quả AI (dịch, gộp, nâng cao…)
workspace/projects/{slug}/assets/     glossary.txt + prompts/ (backup prompt theo dự án)
workspace/archive/{slug}.zip          project đã lưu trữ
workspace/app.db                      index projects/files/runs (không checkpoint nội dung)
config/providers.json                 SSOT provider (gitignore)
config/config.json                     prefs app
```

## 5. Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Sửa |
|---|---|---|
| Lưu bản dịch nhưng file kết quả không hiện / vào chỗ lạ | Server chạy code cũ | Nút restart sidebar → kiểm tra version chân sidebar |
| `address already in use` | 2 server cùng port (vd. terminal cũ chưa tắt) | `pkill -f "main.py"` rồi chạy 1 cái |
| Nút restart "không tác dụng" | Đã sửa từ v2.6 (argv tuyệt đối); nếu còn: kiểm tra health `started_at` có đổi không | Báo kèm `started_at` trước/sau |
| `429` liên tục | Hết quota key | Đổi provider/model, chờ, bấm Gửi Lại (không fallback ngầm) |
| Phiên treo ở chunk lâu | Model reasoning/provider chậm | Xem thanh tiến độ (chunk/attempt/key/giây); Hủy rồi chạy lại |
| Mất điện giữa chừng | Output cũ còn nguyên (atomic write); phiên đang chạy mất | Chạy lại từ đầu (không resume theo thiết kế) |

## 6. Không làm gì ở tầng vận hành

Không systemd/launchd thường trú (dùng xong tắt theo manifesto), không reverse proxy, không HTTPS nội bộ, không multi-user, không backup tự động (đủ rắc rối hơn lợi ích ở quy mô này).
