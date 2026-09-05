# Ý Kiến Về Stack UI: Giữ Lean, Chỉ Thêm Thư Viện Editor

> **Ngày:** 05/09/2026
> **Ngữ cảnh:** Đề xuất dùng FastAPI + Pydantic v2 + Async Queue (backend), TypeScript + React (Vite) + Tailwind + Shadcn + Zustand (frontend), điều hướng multi-page độc lập.
> **Tài liệu tham khảo:** `docs/00_PROJECT_MANIFESTO.md` (v2.3), `docs/02_CORE_SYSTEM_AND_UI_SPECIFICATIONS.md`, `docs/04_PHASE_2_LEAN_WEBUI_AND_BEYOND.md`, `docs/wip/PLAN_REDESIGN_PROJECTS_AND_SETTINGS_UI.md`, `docs/wip/bao_cao_pha_2.md`.
> **Ghi chú:** Không tìm thấy file `NEW_PROJECT_BLUEPRINT_AND_ROADMAP.md` trong repo nên ý kiến dưới đây đối chiếu với các đặc tả hiện có.

## Kết luận (1 đoạn)

**Chưa nên rewrite sang FastAPI + React.** Stack hiện tại (stdlib `http.server` + 1 file `web/index.html` vanilla) vẫn vượt qua litmus test của manifesto — 1 user local, 4 trang, 1 phiên in-flight — và báo cáo Phase 2 đã chốt hướng "ổn định hóa trước, mở rộng sau" (Phase 2.5). Đề xuất React/Shadcn giải quyết vấn đề ta chưa có (multi-user, state phức tạp, team frontend), nhưng mang vào ngay bây giờ cả build-chain npm, version drift và đuôi bảo trì dài. **Điểm duy nhất tôi đồng ý với đề xuất: tác vụ editor xử lý text (dual-pane, sync-scroll, inline edit, diff, search-replace) viết tay bằng vanilla JS rất rủi ro** — nhưng lời giải cho nó là **một thư viện editor duy nhất, nạp lười (lazy-load) chỉ ở trang Workspace**, không phải cả hệ React.

## Backend: giữ stdlib, đặt cửa rõ ràng cho FastAPI

`main.py` hiện phục vụ ~12–18 endpoint JSON + 1 luồng SSE, không auth, không queue. stdlib kham được.

Lên FastAPI + Pydantic v2 + Async Queue **khi và chỉ khi** một trong các điều này xảy ra:

- Có queue/worker thật (batch nhiều file, job nền, hủy phiên giữa chừng).
- Có multi-user hoặc auth.
- Schema request/response phình đến mức validation tay bắt đầu lỗi (hiện tại 3 prefs + providers.json, chưa tới ngưỡng).

Trước đó, FastAPI chỉ thêm dependency (`fastapi`, `uvicorn`, `pydantic`) mà không đổi được hành vi người dùng nào. Phase 2.5 (chuẩn hóa config contract, error model, atomic write — xem `bao_cao_pha_2.md` §5.1) làm được hết trên stdlib.

## Frontend: giữ vanilla shell, không mang React vào lúc này

4 trang (`#v-projects`, `#v-workspace`, `#v-prompts`, `#v-settings`) thực chất đã là multi-page navigation dạng hash-view; Zustand giải quyết bài toán state toàn cục mà app này không có (state = 1 phiên dịch + prefs). Tailwind/Shadcn đẹp nhưng:

- Phá mục tiêu `< 35KB, tải < 20ms, zero npm` trong `PLAN_REDESIGN...` §6.2.
- Phá trải nghiệm `python main.py` → mở là chạy (người dùng phải `npm install/build`).
- Mọi form hiện tại (provider card, model strip, thinking, tuning) đã được đặc tả chi tiết bằng CSS variables + class `.card/.btn/.table-minimal` — đủ dùng.

**Cửa lên React:** khi có tài khoản multi-user, dashboard lịch sử/runs phức tạp, hoặc team > 1 người làm frontend. Chưa có tín hiệu nào trong Phase 3 (glossary, prompt profile, diff, batch nhẹ tuần tự).

## Điểm đồng ý: cần 1 thư viện editor, và chỉ 1

Viết tay sync-scroll + inline edit + diff + search-replace trên văn bản 30–45k ký tự (Unicode Việt, Markdown/HTML lẫn lộn) là nơi bug ẩn: lệch offset cuộn, mất cấu trúc Markdown khi sửa, XSS qua `innerHTML` (báo cáo Phase 2 §3.8 đã cảnh báo). Đây là chỗ duy nhất đáng "mua" thay vì "xây".

**Đề xuất: CodeMirror 6**, vì:

- Nhẹ và modular (chỉ lấy gói cần: view, state, search, merge-diff), khác Monaco (~MB, sức mạnh VS Code nhưng quá nặng cho mục tiêu lean).
- Không phải ProseMirror/TipTap (rich-text editing — thừa, input của tool chỉ là text/md/html).
- Xử lý tốt văn bản lớn, search/replace, highlight glossary term, gutter đánh dấu chunk — đúng việc Phase 3 cần (diff nguồn–dịch, batch search-replace, glossary highlight).

**Cách tích hợp mà không phá lean:**

1. Giữ toàn bộ shell vanilla như hiện tại (sidebar, projects, prompts, settings không đụng tới editor lib).
2. Lazy-load CodeMirror **chỉ ở trang Workspace** (dynamic `import()` khi vào tab Biên Dịch; vendor 1 file hoặc CDN pin version, không đưa vào trang khác).
3. Dùng cho 2 pane nguồn–dịch + view diff ở Phase 3; phần còn lại (fetch, SSE, upload) giữ nguyên.
4. Sanitization vẫn ở **backend boundary** (theo báo cáo §3.8), editor chỉ là lớp hiển thị — không giao việc XSS cho frontend lib.

## Lộ trình đề xuất

1. **Phase 2.5:** giữ nguyên stack, làm P0 (config contract, error model, atomic write, test) — không thêm lib nào.
2. **Phase 3:** khi làm diff + search-replace + glossary highlight, nhét CodeMirror 6 vào Workspace theo cách lazy-load ở trên.
3. **Sau Phase 3:** chỉ xét FastAPI/React khi xuất hiện queue nền, auth multi-user, hoặc validation tay bắt đầu gây lỗi thật — quyết định bằng nhu cầu đo được, không bằng "stack hiện đại".

## Nguyên tắc quyết định (kế thừa litmus test của manifesto)

> Thư viện/framework mới phải giúp **gửi nội dung cho AI và nhận bản dịch nhanh hơn, ổn định hơn, an toàn hơn hoặc dễ kiểm soát hơn** — đo được trên 4 trang hiện có. Nếu chỉ làm code "hiện đại hơn" mà hành vi người dùng không đổi, trì hoãn.
