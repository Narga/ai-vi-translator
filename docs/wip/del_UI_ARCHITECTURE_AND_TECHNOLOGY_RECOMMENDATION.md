# ĐỀ XUẤT KIẾN TRÚC UI VÀ CÔNG NGHỆ FRONTEND

> Dự án: Content Translator  
> Phạm vi: Định hướng xây dựng UI thế hệ mới  
> Ngày: 05/09/2026  
> Trạng thái: Đề xuất kỹ thuật

---

## 1. Kết luận ngắn

Nên chuyển frontend sang:

- **TypeScript**
- **React**
- **Vite**
- **React Router**
- **TailwindCSS**
- **shadcn/ui**
- **Zustand**
- **TanStack Query**
- **CodeMirror 6**
- **Playwright hoặc Vitest cho kiểm thử**

Backend giữ định hướng:

- Python 3.12+
- FastAPI
- Pydantic v2
- Async Queue
- SSE cho streaming tiến trình và token

Tuy nhiên, không nên biến frontend thành một hệ thống quá phức tạp. Số lượng thư viện cần được kiểm soát. React nên được dùng để giải quyết các vấn đề mà vanilla JavaScript hiện tại xử lý kém:

- Quản lý state nhiều trang.
- Điều phối trạng thái loading/error/empty/success.
- Dual-pane editor.
- Sửa nội dung văn bản trực tiếp.
- Cuộn đồng bộ.
- Streaming SSE.
- Upload, kéo thả và cập nhật danh sách file.
- Form cấu hình có validation.
- Điều hướng giữa project, file và task.

UI cần giữ tinh thần:

> Minimalist, rõ ràng, ưu tiên nội dung và trạng thái xử lý, không dùng hiệu ứng trang trí không cần thiết.

---

## 2. Đánh giá blueprint hiện tại

Blueprint định hướng React + Vite + TailwindCSS + shadcn/ui + Zustand là phù hợp với quy mô chức năng dự kiến.

Các chức năng không còn phù hợp với một file HTML/JavaScript duy nhất:

1. Quản lý nhiều trang độc lập.
2. Quản lý project và danh sách file.
3. Cấu hình nhiều provider và API key.
4. Thư viện prompt.
5. Editor song ngữ.
6. Streaming dịch theo chunk.
7. Log thời gian thực.
8. Checkpoint và storage.
9. Công cụ EPUB.
10. Form có nhiều trạng thái và validation.

Vanilla JS vẫn phù hợp với một prototype nhỏ, nhưng sẽ nhanh chóng tạo ra các vấn đề:

- State nằm rải rác trong DOM.
- Khó kiểm soát trạng thái request đồng thời.
- Logic SSE dễ bị trộn lẫn với logic hiển thị.
- Component dùng lại kém.
- Khó kiểm thử.
- Dễ phát sinh lỗi khi một thao tác cập nhật nhiều khu vực giao diện.
- Các editor văn bản phải tự viết nhiều chức năng rủi ro.

Vì vậy, việc chuyển sang React là hợp lý, nhưng cần thực hiện theo từng bước, không nên viết lại toàn bộ trong một sprint lớn.

---

## 3. Kiến trúc frontend được khuyến nghị

### 3.1. Mô hình ứng dụng

Nên xây dựng một React SPA có URL riêng cho từng khu vực:
```
text
/projects
/projects/:projectSlug
/workspace
/workspace/:projectSlug/:fileId
/prompts
/tools/epub
/settings
/logs
/storage
/docs
```
Đây vẫn là “multi-page navigation” ở góc nhìn người dùng, nhưng về kỹ thuật có thể dùng một SPA với React Router.

Không nên tạo nhiều frontend bundle riêng biệt ngay từ đầu vì sẽ:

- Tăng độ phức tạp build.
- Tăng số lượng entry point.
- Khó dùng chung state và component.
- Khó xử lý navigation giữa project, file và task.

React Router vẫn cung cấp URL, history, deep link và back/forward đầy đủ.

### 3.2. Cấu trúc thư mục đề xuất
```
text
webui/
├── src/
│   ├── app/
│   │   ├── router.tsx
│   │   ├── providers.tsx
│   │   └── layout/
│   ├── pages/
│   │   ├── projects/
│   │   ├── workspace/
│   │   ├── prompts/
│   │   ├── epub/
│   │   ├── settings/
│   │   ├── logs/
│   │   ├── storage/
│   │   └── docs/
│   ├── components/
│   │   ├── ui/
│   │   ├── layout/
│   │   ├── files/
│   │   ├── editor/
│   │   ├── providers/
│   │   └── feedback/
│   ├── features/
│   │   ├── projects/
│   │   ├── translation/
│   │   ├── prompts/
│   │   ├── settings/
│   │   └── logs/
│   ├── stores/
│   ├── api/
│   ├── hooks/
│   ├── lib/
│   ├── types/
│   └── styles/
├── index.html
├── package.json
├── vite.config.ts
└── tsconfig.json
```
Cần phân biệt:

- `pages`: bố cục của từng trang.
- `features`: nghiệp vụ.
- `components`: thành phần UI dùng lại.
- `stores`: state dùng chung.
- `api`: gọi backend.
- `types`: kiểu dữ liệu từ API.
- `lib`: tiện ích thuần, không chứa logic giao diện.

Không nên để toàn bộ logic trong `components/` hoặc `pages/`.

---

## 4. Bộ công nghệ đề xuất

### 4.1. React + TypeScript

Đây là lựa chọn chính thức nên dùng.

Lý do:

- TypeScript kiểm soát contract giữa API và UI.
- React phù hợp với UI có nhiều trạng thái.
- Component hóa tốt.
- Hỗ trợ editor, streaming, form và bảng dữ liệu.
- Dễ kiểm thử từng phần.
- Có hệ sinh thái ổn định.

Không nên dùng JavaScript thuần cho frontend thế hệ mới vì các tính năng editor và workflow đã vượt quá phạm vi an toàn của DOM trực tiếp.

### 4.2. Vite

Vite phù hợp vì:

- Khởi động dev server nhanh.
- Cấu hình đơn giản.
- Build nhẹ.
- Phù hợp ứng dụng local.
- Không cần framework full-stack như Next.js.

Không nên dùng Next.js ở giai đoạn này vì dự án không cần SSR, server actions hoặc hệ thống routing phía server.

### 4.3. React Router

Dùng cho các trang:

- Projects
- Workspace
- Prompts
- EPUB Tools
- Settings
- Logs
- Storage
- Documentation

Nên đặt tham số project và file trong URL để người dùng có thể bookmark và quay lại đúng ngữ cảnh.

Ví dụ:
```
text
/workspace/novel-a/chapter-01.md
```
### 4.4. TailwindCSS + shadcn/ui

Nên sử dụng nhưng phải giới hạn phạm vi.

TailwindCSS giải quyết:

- Layout.
- Responsive.
- Spacing.
- Typography.
- Design token.
- Trạng thái focus, hover, disabled.

shadcn/ui phù hợp cho:

- Button.
- Input.
- Textarea.
- Select.
- Dialog.
- Sheet.
- Tabs.
- Tooltip.
- Alert.
- Badge.
- Dropdown menu.
- Table.
- Progress.
- Toast.

shadcn/ui không phải một UI runtime nặng. Component được đưa vào source code dự án, vì vậy có thể kiểm soát và chỉnh sửa trực tiếp.

Không nên cài thêm nhiều UI framework khác như:

- Material UI.
- Ant Design.
- Chakra UI.
- Bootstrap.

Chỉ nên chọn một hệ thống UI duy nhất để tránh xung đột thẩm mỹ và kích thước bundle.

---

## 5. Thư viện xử lý text và editor

Đây là phần cần thay đổi quan trọng nhất so với phương án vanilla JavaScript.

### 5.1. Khuyến nghị chính: CodeMirror 6

Nên dùng **CodeMirror 6** làm editor văn bản lõi.

Phù hợp cho:

- Prompt `.txt`.
- Markdown.
- HTML.
- Nội dung nguồn.
- Nội dung dịch.
- Editor song ngữ.
- Highlight syntax.
- Tìm kiếm trong văn bản.
- Undo/redo.
- Selection.
- Keymap.
- Extension tùy chỉnh.
- Hiển thị văn bản dài.

CodeMirror 6 nhẹ và linh hoạt hơn Monaco trong ứng dụng local tối giản.

Các package có thể dùng:
```
text
@codemirror/view
@codemirror/state
@codemirror/lang-markdown
@codemirror/lang-html
@codemirror/language
@codemirror/search
```
Không nên tự viết textarea editor với các chức năng:

- Undo/redo nâng cao.
- Tìm kiếm.
- Highlight.
- Selection tracking.
- Keyboard shortcut.
- Line handling.
- Large text rendering.

Đây là những tính năng dễ tạo lỗi và không đáng tự phát triển.

### 5.2. Khi nào dùng Monaco Editor?

Monaco chỉ nên được cân nhắc nếu cần:

- Trải nghiệm giống VS Code.
- IntelliSense mạnh.
- Multi-cursor nâng cao.
- Editor code chuyên sâu.
- File rất lớn và cần hệ thống editor phong phú.

Đối với prompt, Markdown và bản dịch văn học, Monaco có thể quá nặng. Vì vậy, **CodeMirror 6 nên là lựa chọn mặc định**.

### 5.3. Dual-pane editor

Trang `/workspace` nên có hai editor độc lập:
```
text
┌──────────────────────────┬──────────────────────────┐
│ Nội dung nguồn           │ Bản dịch                 │
│ CodeMirror instance      │ CodeMirror instance      │
└──────────────────────────┴──────────────────────────┘
```
Cần hỗ trợ:

- Cuộn đồng bộ tùy chọn.
- Chỉ đọc với nội dung nguồn.
- Chỉnh sửa nội dung dịch.
- Highlight Markdown/HTML.
- Hiển thị trạng thái đang stream.
- Đánh dấu chunk hiện tại.
- Nút lưu bản dịch.
- Khôi phục bản dịch gần nhất.
- So sánh thay đổi trước khi lưu.

Không nên dùng một textarea duy nhất cho cả hai bên.

### 5.4. Markdown rendering

Đối với preview Markdown, nên dùng thư viện chuyên dụng có sanitize HTML.

Có thể dùng:

- `marked` hoặc `remark`
- kết hợp `DOMPurify`

Quy tắc bắt buộc:

1. Không đưa HTML do AI tạo trực tiếp vào `dangerouslySetInnerHTML`.
2. Luôn sanitize trước khi render.
3. Không cho phép script, event handler và URL nguy hiểm.
4. Phân biệt rõ chế độ raw text, editor và preview.

---

## 6. State management

### 6.1. Zustand

Zustand phù hợp cho state giao diện dùng chung, ví dụ:

- Project đang chọn.
- File đang mở.
- Sidebar đang thu gọn hay mở rộng.
- Preferences của editor.
- Trạng thái task hiện tại.
- Bộ lọc log.
- Theme hoặc density của giao diện.
- Trạng thái kết nối SSE.

Không nên đưa toàn bộ dữ liệu API vào Zustand.

### 6.2. TanStack Query

Nên dùng TanStack Query cho server state:

- Danh sách project.
- Danh sách file.
- Nội dung prompt.
- Cấu hình provider.
- Model metadata.
- Trạng thái checkpoint.
- Dữ liệu logs đã tải.
- Cache và refetch.

Phân biệt rõ:
```
text
Zustand        = client state
TanStack Query = server state
React state    = state cục bộ của component
```
Nếu chỉ dùng Zustand cho tất cả, cache, invalidation và loading state sẽ nhanh chóng trở nên khó kiểm soát.

### 6.3. Form và validation

Nên dùng:

- `react-hook-form`
- `zod`

Áp dụng cho:

- Tạo project.
- Cấu hình provider.
- API key.
- Request tuning.
- EPUB metadata.
- Prompt metadata.

Validation frontend chỉ là lớp phản hồi sớm. Backend Pydantic vẫn là nơi xác thực chính thức.

---

## 7. Giao tiếp với backend

### 7.1. API client

Tạo một lớp API client duy nhất:
```
text
src/api/client.ts
src/api/projects.ts
src/api/prompts.ts
src/api/settings.ts
src/api/translation.ts
src/api/storage.ts
```
Không gọi `fetch()` trực tiếp rải rác trong component.

API client cần thống nhất:

- Base URL.
- Parse JSON.
- HTTP error.
- Timeout.
- AbortController.
- Error message.
- Kiểu dữ liệu trả về.

### 7.2. OpenAPI và TypeScript types

FastAPI đã cung cấp OpenAPI. Nên tận dụng để sinh TypeScript types hoặc client.

Mục tiêu:

- Backend Pydantic schema là contract chính.
- Frontend không tự đoán tên field.
- Không tồn tại đồng thời nhiều tên cho cùng một cấu hình.
- Kiểm soát kiểu số, boolean, enum và nullable.

Đây là điểm cần ưu tiên vì đánh giá Phase 2 đã chỉ ra nguy cơ config bị lệch giữa UI, backend và worker.

### 7.3. SSE streaming

Tạo một abstraction riêng cho SSE:
```
text
src/api/sse.ts
src/features/translation/useTranslationStream.ts
src/features/logs/useLogStream.ts
```
Abstraction cần xử lý:

- Kết nối.
- Reconnect có giới hạn.
- Abort khi rời trang.
- Event type.
- Parse payload.
- Heartbeat.
- Lỗi server.
- Kết thúc task.
- Trạng thái mất kết nối.

Không nên đặt toàn bộ logic `ReadableStream` hoặc SSE vào component editor.

Nên thống nhất event schema:
```
json
{
  "event": "chunk.delta",
  "task_id": "task-123",
  "file_id": "chapter-01",
  "chunk_index": 3,
  "content": "..."
}
```
Các event khác:
```
text
task.started
task.progress
chunk.started
chunk.delta
chunk.completed
task.paused
task.failed
task.completed
```
---

## 8. Đề xuất bố cục UI

### 8.1. Layout tổng thể
```
text
┌──────────────────────────────────────────────────────────┐
│ Header: Tên trang | Project hiện tại | Trạng thái task   │
├───────────────┬──────────────────────────────────────────┤
│ Sidebar       │ Main content                              │
│               │                                          │
│ Projects      │ Card / Table / Editor                    │
│ Workspace     │                                          │
│ Prompts       │                                          │
│ EPUB Tools    │                                          │
│ Settings      │                                          │
│ Logs          │                                          │
│ Storage       │                                          │
│ Docs          │                                          │
└───────────────┴──────────────────────────────────────────┘
```
Sidebar cần:

- Có thể thu gọn.
- Hiển thị route đang active.
- Hiển thị task đang chạy.
- Không dùng animation dài.
- Không chiếm quá nhiều diện tích.

### 8.2. Projects

Nên dùng:

- Header trang.
- Project cards hoặc bảng tùy số lượng project.
- Khu vực upload.
- Bảng file.
- Drawer hoặc detail panel cho file.
- Confirm dialog khi xóa.

Không nên mở quá nhiều modal lồng nhau. File detail nên dùng route hoặc side panel.

### 8.3. Workspace

Đây là trang quan trọng nhất.

Bố cục khuyến nghị:
```
text
┌───────────────────────┬──────────────────────────────────┐
│ Task controls         │ Dual-pane editor                │
│                       │                                  │
│ File list             │ Source        Translation       │
│ Main prompt           │                                  │
│ Additional prompts    │                                  │
│ Glossary              │                                  │
│ Provider/model        │                                  │
│ Start/pause/retry     │                                  │
└───────────────────────┴──────────────────────────────────┘
```
Trên màn hình nhỏ, chuyển thành:

1. Task controls.
2. File selection.
3. Editor source.
4. Editor translation.
5. Progress/log summary.

Không cố giữ hai cột trên màn hình quá hẹp.

### 8.4. Settings

Trang Settings nên chia thành card độc lập:

1. Provider và API key.
2. Model.
3. Thinking level.
4. Request tuning.
5. Key pool health.
6. Save và validation feedback.

Không nên trộn cấu hình provider, model và runtime vào một form dài không có nhóm.

### 8.5. Logs

Logs nên có:

- Bộ lọc.
- Mức độ log.
- Search.
- Pause auto-scroll.
- Copy log.
- Clear view, không xóa log server.
- Trạng thái kết nối SSE.
- Thống kê task.

Không nên mô phỏng terminal bằng quá nhiều hiệu ứng. Đây là bảng sự kiện có thể đọc được, không phải màn hình trình diễn.

---

## 9. Design system

### 9.1. Màu sắc

Giữ palette trung tính:

- Nền ứng dụng: slate rất nhạt.
- Card: trắng.
- Text chính: slate đậm.
- Text phụ: slate trung bình.
- Primary: xanh dương vừa phải.
- Success: xanh lá dịu.
- Warning: amber dịu.
- Danger: đỏ dịu.

Không dùng:

- Gradient neon.
- Glassmorphism.
- Background động.
- Shadow quá đậm.
- Animation liên tục.

### 9.2. Mật độ giao diện

Ứng dụng xử lý văn bản cần ưu tiên diện tích nội dung:

- Sidebar không quá rộng.
- Padding card vừa phải.
- Editor chiếm phần lớn chiều cao.
- Toolbar ngắn gọn.
- Button có label rõ ràng.
- Icon chỉ dùng cho thao tác quen thuộc.
- Không biến mọi thao tác thành icon-only.

### 9.3. Accessibility

Cần có:

- Keyboard navigation.
- Focus ring rõ ràng.
- Label thật cho form.
- `aria-label` cho icon button.
- Contrast đạt mức chấp nhận được.
- Không chỉ dùng màu để biểu thị trạng thái.
- Thông báo lỗi gắn với field.
- Dialog có focus trap.
- Editor có shortcut tài liệu rõ ràng.

---

## 10. Những thư viện không nên đưa vào

Để giữ frontend nhẹ, không nên cài sẵn:

- Redux nếu Zustand và TanStack Query đã đủ.
- Nhiều UI framework đồng thời.
- Monaco nếu CodeMirror đáp ứng được nhu cầu.
- Next.js.
- Electron khi chưa có yêu cầu desktop package.
- Drag-and-drop framework lớn nếu HTML Drag and Drop API đủ dùng.
- Animation library cho các hiệu ứng đơn giản.
- Chart library trước khi có nhu cầu thống kê thực tế.
- Rich text editor WYSIWYG nếu yêu cầu chính là bảo toàn Markdown/HTML.
- Translation Memory hoặc text processing library ở frontend.

Frontend không nên xử lý logic dịch, chunking hoặc chuẩn hóa nội dung thay backend.

---

## 11. Bảo toàn định dạng văn bản

UI phải tôn trọng nguyên tắc bảo toàn dữ liệu:

1. Editor không tự động trim nội dung.
2. Không tự động đổi line ending nếu chưa được xác định rõ.
3. Không tự động chuẩn hóa khoảng trắng.
4. Không parse Markdown rồi serialize lại khi người dùng chỉ muốn xem.
5. Raw content phải được giữ nguyên trong state.
6. Preview là một representation riêng, không ghi đè raw content.
7. Khi lưu phải gửi đúng nội dung người dùng đang chỉnh sửa.
8. Hiển thị cảnh báo nếu backend phát hiện conflict phiên bản.
9. Có thể xem diff trước khi ghi đè file.

Đây là lý do không nên dùng các rich text editor thiên về HTML document model cho luồng dịch Markdown/text.

---

## 12. Lộ trình triển khai đề xuất

### Phase A — Frontend foundation

- Khởi tạo Vite + React + TypeScript.
- Thiết lập TailwindCSS.
- Thêm các component shadcn/ui tối thiểu.
- Thiết lập React Router.
- Thiết lập API client.
- Thiết lập error boundary.
- Thiết lập design tokens.
- Dựng app shell và sidebar.

### Phase B — Projects

- Project list.
- Tạo project.
- Upload file.
- File table.
- File detail.
- Trạng thái nguồn/bản dịch.
- Điều hướng sang workspace.

### Phase C — Settings

- Provider list.
- API key editor.
- Model selection.
- Runtime tuning.
- Validation bằng Zod.
- Đồng bộ contract với Pydantic.

### Phase D — Prompt library

- Danh sách prompt.
- CodeMirror editor.
- Tạo, sửa, nhân bản, xóa prompt.
- Hiển thị biến prompt được hỗ trợ.
- Preview template.

### Phase E — Workspace

- Chọn project và file.
- Chọn prompt.
- Chọn provider/model.
- Dual-pane CodeMirror.
- Streaming SSE.
- Progress theo chunk.
- Pause, retry, resume.
- Lưu bản dịch.

### Phase F — Logs, storage và EPUB

- Live logs.
- Checkpoint.
- Resume.
- Export.
- EPUB tool.
- Documentation page.

### Phase G — Hardening

- E2E test.
- Test stream bị ngắt.
- Test upload lỗi.
- Test file lớn.
- Test provider timeout.
- Test API key cooldown.
- Test conflict khi lưu.
- Test XSS qua Markdown/HTML/AI output.
- Test responsive.
- Test keyboard accessibility.

---

## 13. Tiêu chí nghiệm thu frontend

### Kiến trúc

- [ ] Không còn logic DOM trực tiếp cho các page chính.
- [ ] Không gọi API rải rác trong component.
- [ ] Có type rõ ràng cho response chính.
- [ ] Server state và client state được tách biệt.
- [ ] Mỗi page có route độc lập.
- [ ] Có error boundary và trạng thái lỗi rõ ràng.

### Editor

- [ ] Có editor chuyên dụng, không dùng textarea thuần cho chức năng chính.
- [ ] Có undo/redo.
- [ ] Có tìm kiếm.
- [ ] Có syntax highlighting phù hợp.
- [ ] Không tự ý trim hoặc normalize nội dung.
- [ ] Hỗ trợ nội dung dài ở mức chấp nhận được.
- [ ] Dual-pane có thể dùng được với streaming.

### Streaming

- [ ] Có thể hủy stream.
- [ ] Có xử lý reconnect hoặc lỗi kết nối.
- [ ] Hiển thị tiến trình theo chunk.
- [ ] Không làm treo toàn bộ UI.
- [ ] Task vẫn được theo dõi khi chuyển trang.
- [ ] Có trạng thái completed/failed/paused rõ ràng.

### UI/UX

- [ ] Giao diện tối giản, không hiệu ứng thừa.
- [ ] Responsive ở kích thước laptop và màn hình nhỏ.
- [ ] Focus keyboard rõ ràng.
- [ ] Có loading, empty, error và success state.
- [ ] Không dùng màu làm tín hiệu duy nhất.
- [ ] Các thao tác xóa hoặc ghi đè có xác nhận.

### Hiệu năng

- [ ] Không load editor nặng ở những page không cần.
- [ ] Code splitting theo route.
- [ ] Không render lại toàn bộ editor khi một token stream đến.
- [ ] Danh sách file lớn có cơ chế virtualization khi cần.
- [ ] Không lưu toàn bộ log vô hạn trong memory.
- [ ] Preview Markdown được sanitize.

---

## 14. Quyết định cuối cùng

Đề xuất chính thức:
```
text
Frontend:
React + TypeScript + Vite
React Router
TailwindCSS
shadcn/ui
Zustand
TanStack Query
React Hook Form + Zod
CodeMirror 6
DOMPurify
Vitest + Playwright

Backend:
Python 3.12+
FastAPI
Pydantic v2
Async Queue
SSE
```
Trong đó, ba quyết định quan trọng nhất là:

1. **Dùng React/TypeScript thay cho vanilla JavaScript cho frontend mới.**
2. **Dùng CodeMirror 6 thay vì tự phát triển editor bằng textarea/DOM thuần.**
3. **Tách server state, client state và editor state; không đưa tất cả vào một store duy nhất.**

Mục tiêu không phải là xây dựng một giao diện nhiều hiệu ứng, mà là xây dựng một workspace xử lý văn bản ổn định, dễ kiểm thử và không làm mất định dạng gốc.

Nếu phải ưu tiên tối giản hơn nữa, bộ tối thiểu có thể là:
```
text
React
TypeScript
Vite
React Router
TailwindCSS
shadcn/ui
Zustand
CodeMirror 6
```
TanStack Query, React Hook Form và Zod nên được bổ sung ngay khi số lượng API/form tăng lên, thay vì tự viết các cơ chế tương đương.
