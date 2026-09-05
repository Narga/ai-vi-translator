# Báo cáo đánh giá và đề xuất công nghệ UI


## 1. Tóm tắt kết luận

Dự án phù hợp nhất với mô hình:

- **Frontend:** HTML semantic, CSS thuần, JavaScript thuần dạng module ES.
- **Backend:** Python hiện tại, tiếp tục dùng `stdlib http.server`.
- **Giao tiếp:** REST/JSON cho thao tác thông thường và SSE cho tiến độ dịch theo chunk.
- **Editor:** Ưu tiên `textarea` nâng cấp bằng CSS/JavaScript; chỉ dùng CodeMirror 6 nếu nhu cầu editor thực tế vượt quá khả năng của textarea.
- **Icon:** SVG inline hoặc một bộ icon SVG nhỏ được lưu nội bộ.
- **Build:** Không dùng bundler, không dùng Node.js trong runtime, không dùng Tailwind build.
- **Phụ thuộc frontend:** Tốt nhất là **không có dependency runtime**.

Đây là lựa chọn cân bằng tốt nhất cho ứng dụng:

- phục vụ một người dùng;
- chạy local;
- dữ liệu là file và SQLite;
- số lượng màn hình ít;
- logic giao diện không quá phức tạp;
- cần sử dụng lâu dài;
- ưu tiên dễ sửa, dễ sao lưu và dễ khởi chạy.

Không nên chuyển sang React, Vue, Svelte hoặc Electron ở giai đoạn hiện tại. Những công nghệ này chỉ nên được cân nhắc khi ứng dụng phát triển thành sản phẩm nhiều người dùng, có trạng thái giao diện rất phức tạp hoặc cần đóng gói desktop chuyên dụng.

---

## 2. Đánh giá hiện trạng

### 2.1. Điểm phù hợp

Kiến trúc hiện tại đã có các đặc điểm rất phù hợp với UI nhẹ:

- Backend Python đơn giản.
- WebUI được phục vụ từ cùng ứng dụng.
- Frontend đang tập trung trong một file HTML.
- Tính năng chính xoay quanh:
  - quản lý dự án;
  - chọn file;
  - chỉnh sửa nội dung;
  - chạy dịch;
  - xem tiến độ;
  - quản lý prompt;
  - cấu hình provider/model;
  - tìm kiếm và thay thế.
- Chỉ có một phiên dịch tại một thời điểm.
- SSE phù hợp với việc hiển thị tiến độ từng chunk.
- File và SQLite là nguồn dữ liệu chính, không cần state management phức tạp ở frontend.

Đặc biệt, mục tiêu “Minimalist — Single-User — Nhanh — UI siêu nhẹ” không phù hợp với việc đưa vào một framework frontend lớn chỉ để tổ chức vài trang.

### 2.2. Các rủi ro cần kiểm soát

#### Một file HTML quá lớn

Một file HTML duy nhất dễ bắt đầu nhưng sẽ nhanh chóng khó bảo trì khi có:

- nhiều trang;
- nhiều dialog;
- nhiều trạng thái loading/error/success;
- editor hai chiều;
- SSE;
- tìm kiếm và thay thế;
- cấu hình model;
- toast và thông báo.

Không nên tiếp tục dồn toàn bộ CSS và JavaScript vào một file quá dài.

#### Trạng thái giao diện dễ bị phân tán

Các trạng thái cần được quản lý rõ ràng:

- dự án hiện tại;
- file đang mở;
- nội dung source;
- nội dung result;
- nội dung đã chỉnh sửa nhưng chưa lưu;
- trạng thái đang dịch;
- tiến độ hiện tại;
- lỗi API;
- provider/model đang chọn;
- kết nối SSE;
- dialog đang mở.

Nếu xử lý bằng nhiều biến global và nhiều event handler rời rạc, chi phí bảo trì sẽ tăng nhanh dù không dùng framework.

#### Editor là khu vực có khả năng trở thành điểm phức tạp

Các yêu cầu như:

- hai vùng source/result;
- đồng bộ cuộn;
- tìm kiếm;
- regex;
- thay thế;
- đánh dấu kết quả;
- hiển thị diff;
- thao tác phím tắt;

có thể khiến editor tự phát triển thành một “framework nhỏ”. Vì vậy nên giới hạn phạm vi ngay từ đầu.

---

## 3. Công nghệ được đề xuất

## 3.1. HTML semantic

Dùng HTML chuẩn, ưu tiên các phần tử:

- `header`;
- `nav`;
- `main`;
- `section`;
- `aside`;
- `dialog`;
- `form`;
- `button`;
- `input`;
- `select`;
- `textarea`;
- `details` và `summary`.

Lợi ích:

- ít JavaScript hơn;
- dễ tiếp cận;
- dễ kiểm thử;
- không phụ thuộc framework;
- tương thích tốt trong thời gian dài.

Nên xây dựng layout theo hướng:

```plain text
App Shell
├── Sidebar / Navigation
├── Topbar
└── Main Content
    ├── Projects View
    ├── Translator View
    ├── Prompts View
    └── Settings View
```


Không nhất thiết phải dùng routing library. Có thể dùng một router nhỏ dựa trên:

- hash URL, ví dụ `#/projects`;
- hoặc history API với vài hàm đơn giản.

Đối với ứng dụng local một người dùng, hash routing là lựa chọn đơn giản và ít lỗi hơn.

---

## 3.2. CSS thuần, không build

Nên dùng CSS native với các khả năng hiện đại:

- CSS variables;
- Grid;
- Flexbox;
- `color-mix()` nếu cần;
- `clamp()`;
- container queries nếu thực sự cần;
- `:has()` chỉ dùng có kiểm soát;
- media queries;
- `prefers-color-scheme`;
- `prefers-reduced-motion`.

Tổ chức CSS theo file:

```plain text
web/
├── index.html
├── css/
│   ├── tokens.css
│   ├── base.css
│   ├── layout.css
│   ├── components.css
│   ├── views.css
│   └── utilities.css
└── js/
    ├── app.js
    ├── state.js
    ├── api.js
    ├── router.js
    ├── events.js
    ├── components/
    └── views/
```


Nếu muốn giữ cấu trúc đơn giản hơn, có thể bắt đầu với:

```plain text
web/
├── index.html
├── app.css
└── app.js
```


Sau khi file vượt khoảng 800–1.000 dòng thì mới tách thành nhiều file. Không nên tách file quá sớm thành hàng chục module nhỏ.

### Design token nên có

```css
:root {
  --color-bg: #f5f7fb;
  --color-surface: #ffffff;
  --color-surface-muted: #eef2f7;
  --color-text: #172033;
  --color-text-muted: #687386;
  --color-border: #dce2eb;
  --color-primary: #4f46e5;
  --color-primary-hover: #4338ca;
  --color-success: #16805c;
  --color-warning: #b7791f;
  --color-danger: #c53030;

  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;

  --shadow-sm: 0 1px 3px rgb(15 23 42 / 8%);
  --shadow-md: 0 8px 24px rgb(15 23 42 / 10%);

  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
}
```


Không nên dùng quá nhiều màu, kích thước hoặc kiểu card khác nhau. Giao diện hiện đại thường đến từ tính nhất quán chứ không phải số lượng hiệu ứng.

---

## 3.3. JavaScript thuần dạng ES Modules

Nên dùng:

- `type="module"`;
- `fetch`;
- `AbortController`;
- `EventSource` cho SSE;
- `URLSearchParams`;
- `FormData`;
- `structuredClone` nếu cần;
- `CustomEvent` ở mức vừa phải.

Không cần:

- jQuery;
- Redux;
- Zustand;
- MobX;
- Alpine.js;
- HTMX;
- một framework component lớn.

### Cấu trúc JavaScript đề xuất

```plain text
web/js/
├── app.js
├── state.js
├── api.js
├── router.js
├── notifications.js
├── dialogs.js
├── sse.js
├── views/
│   ├── projects-view.js
│   ├── translator-view.js
│   ├── prompts-view.js
│   └── settings-view.js
└── components/
    ├── file-list.js
    ├── progress-panel.js
    ├── empty-state.js
    └── confirm-dialog.js
```


### Quy tắc state tối thiểu

Nên có một state object duy nhất ở cấp ứng dụng:

```javascript
const state = {
  route: "projects",
  project: null,
  activeFile: null,
  sourceText: "",
  resultText: "",
  sourceDirty: false,
  resultDirty: false,
  translation: {
    running: false,
    progress: 0,
    currentChunk: 0,
    totalChunks: 0,
    error: null
  }
};
```


Không nên biến state thành hệ thống reactive phức tạp. Chỉ cần:

1. cập nhật state;
2. gọi hàm render hoặc cập nhật vùng DOM liên quan;
3. phát event khi một module khác cần biết thay đổi.

### Quy tắc module

Mỗi module nên có trách nhiệm rõ:

- `api.js`: gọi HTTP API;
- `state.js`: lưu trạng thái;
- `router.js`: điều hướng;
- `sse.js`: kết nối và đóng SSE;
- `views/*`: dựng giao diện từng trang;
- `components/*`: thành phần tái sử dụng;
- `notifications.js`: toast và thông báo.

Không để view tự xây URL API, tự xử lý SSE và tự hiển thị toast cùng lúc.

---

## 4. Có nên dùng thư viện JavaScript không?

## 4.1. Khuyến nghị chính: không dùng thư viện lúc đầu

Với phạm vi hiện tại, JavaScript thuần có các ưu điểm:

- không có bước build;
- không có `node_modules`;
- không có rủi ro dependency lỗi thời;
- dễ debug trực tiếp trên trình duyệt;
- dễ chạy offline;
- phù hợp với backend Python hiện tại;
- dễ backup toàn bộ dự án;
- người bảo trì trong tương lai không cần học framework.

Đây là lựa chọn nên chốt cho Phase 2.

## 4.2. Trường hợp có thể dùng thư viện nhỏ

Chỉ nên bổ sung thư viện khi có nhu cầu rõ ràng:

| Nhu cầu | Lựa chọn |
|---|---|
| Icon | SVG nội bộ hoặc Lucide SVG được copy vào dự án |
| Editor nâng cao | CodeMirror 6 |
| Markdown preview | Marked hoặc parser nhỏ được vendoring |
| Diff | diff-match-patch hoặc thư viện diff nhỏ |
| Tooltip/popover | CSS và `dialog` trước, thư viện sau |
| Toast | Tự viết bằng khoảng vài chục dòng JavaScript |
| Date formatting | `Intl.DateTimeFormat` |
| UUID | `crypto.randomUUID()` |

Không nên đưa CDN vào UI chính vì:

- chạy local có thể không có Internet;
- phiên bản CDN có thể thay đổi;
- khó kiểm soát tính toàn vẹn;
- ứng dụng đang có định hướng ít phụ thuộc.

Nếu dùng thư viện, nên:

1. cố định phiên bản;
2. lưu nội bộ trong `web/vendor/`;
3. ghi rõ license;
4. chỉ dùng thư viện thực sự cần thiết;
5. không thêm dependency chỉ để giải quyết vấn đề nhỏ.

---

## 5. Đánh giá các lựa chọn framework

| Công nghệ | Đánh giá | Kết luận |
|---|---|---|
| React | Hệ sinh thái lớn, cần build và quản lý state/component | Không cần thiết |
| Vue | Dễ học hơn React nhưng vẫn thêm build và dependency | Chưa nên dùng |
| Svelte | Nhẹ khi chạy nhưng vẫn cần toolchain/build | Chưa nên dùng |
| Alpine.js | Nhẹ, phù hợp tương tác nhỏ | Có thể dùng, nhưng chưa cần |
| HTMX | Tốt cho server-rendered UI, không lý tưởng cho editor realtime/SSE phức tạp | Không ưu tiên |
| Lit | Component web chuẩn, nhẹ hơn framework lớn | Chỉ cân nhắc khi cần component hóa mạnh |
| Electron | Đóng gói desktop nhưng rất cồng kềnh | Không dùng |
| Tauri | Nhẹ hơn Electron nhưng vẫn thêm Rust/toolchain | Chỉ dùng khi cần app desktop thực sự |
| Vanilla JS | Đủ cho phạm vi hiện tại, bảo trì lâu dài | **Khuyến nghị** |

### Về Alpine.js

Alpine.js là lựa chọn hợp lý nếu dự án muốn:

- viết HTML có directive;
- có một số dropdown, modal, tab;
- không muốn tự viết nhiều event handler.

Tuy nhiên, dự án có editor, SSE, file state và tiến trình dịch. Việc trộn Alpine.js với JavaScript module tự viết có thể tạo ra hai mô hình quản lý state khác nhau. Vì vậy:

> Không nên dùng Alpine.js trong phiên bản đầu tiên. Nếu JavaScript thuần trở nên quá dài, hãy đánh giá lại toàn bộ thay vì bổ sung Alpine.js một cách từng phần.

---

## 6. Đề xuất giao diện

## 6.1. Nguyên tắc thẩm mỹ

Nên theo hướng:

- sáng, sạch, ít màu;
- nền xám rất nhạt;
- surface trắng;
- màu nhấn indigo hoặc blue;
- border mảnh;
- bo góc vừa phải;
- bóng nhẹ;
- typography rõ ràng;
- khoảng cách rộng;
- trạng thái được biểu diễn bằng màu và icon;
- tránh gradient và animation quá mức.

Phong cách phù hợp là “desktop productivity tool”, không phải dashboard nhiều biểu đồ.

## 6.2. Thanh điều hướng

Sidebar nên có bốn mục chính:

1. Dự án;
2. Biên dịch;
3. Prompt;
4. Cấu hình.

Mỗi mục gồm:

- icon SVG;
- nhãn;
- trạng thái active;
- tooltip khi sidebar thu gọn.

Nên có khu vực cuối sidebar cho:

- trạng thái server;
- phiên bản ứng dụng;
- nút mở thư mục workspace nếu sau này hỗ trợ.

## 6.3. Trang Dự án

Nên hiển thị:

- tiêu đề trang;
- nút tạo dự án;
- ô tìm kiếm;
- danh sách hoặc card dự án;
- số file nguồn;
- số file đã dịch;
- tiến độ;
- lần cập nhật gần nhất;
- trạng thái dự án.

Không nên hiển thị quá nhiều thông tin kỹ thuật trên card. Thông tin chi tiết có thể nằm trong panel hoặc trang dự án.

## 6.4. Trang Biên dịch

Đây là màn hình quan trọng nhất.

Layout đề xuất:

```plain text
┌────────────────────────────────────────────────────┐
│ Project / File selector       Actions / Translate  │
├──────────────┬──────────────────┬──────────────────┤
│ Source files │ Source editor    │ Result editor    │
│              │                  │                  │
│ file-01.md   │                  │                  │
│ file-02.md   │                  │                  │
│ file-03.md   │                  │                  │
├──────────────┴──────────────────┴──────────────────┤
│ Search / Replace / Progress / Status                │
└────────────────────────────────────────────────────┘
```


Cần hỗ trợ tốt:

- file đang chọn;
- file có thay đổi chưa lưu;
- trạng thái đã dịch/chưa dịch;
- nút lưu;
- nút chạy lại;
- nút copy;
- nút tìm kiếm;
- lỗi được hiển thị gần thao tác gây lỗi;
- trạng thái đang chạy rõ ràng.

Không nên để một nút “Translate” duy nhất làm quá nhiều việc mà không giải thích:

- đang dùng provider nào;
- model nào;
- prompt nào;
- file nào;
- có ghi đè kết quả hay không.

## 6.5. Trang Prompt

Nên có:

- danh sách prompt;
- prompt đang chọn;
- editor văn bản;
- nút lưu;
- nút tạo prompt mới;
- hiển thị prompt mặc định;
- cảnh báo khi có thay đổi chưa lưu.

Không cần markdown editor nâng cao nếu prompt chỉ là văn bản thuần.

## 6.6. Trang Cấu hình

Nên chia thành các nhóm:

### Cấu hình chung

- kích thước chunk;
- độ trễ API;
- timeout;
- thư mục workspace nếu cần.

### Provider

- provider đang dùng;
- API base URL;
- key;
- trạng thái kiểm tra kết nối.

### Model

- model mặc định;
- nút tải danh sách model;
- thời điểm cache cập nhật;
- custom model.

### An toàn

- hiển thị rõ key đang được sử dụng;
- không log API key;
- xác nhận trước khi xóa;
- thông báo việc lưu cấu hình thành công.

Không nên nhồi tất cả thông tin provider vào một form dài. Dùng `details/summary` hoặc các tab đơn giản.

---

## 7. Chiến lược editor

## 7.1. Giai đoạn đầu: textarea nâng cấp

Dùng `textarea` là phương án phù hợp nhất nếu yêu cầu hiện tại chủ yếu là:

- chỉnh sửa văn bản;
- tìm kiếm;
- regex;
- thay thế;
- copy;
- save;
- retry;
- hiển thị source/result;
- đồng bộ cuộn cơ bản.

Ưu điểm:

- native;
- nhanh;
- dễ bảo trì;
- hỗ trợ accessibility tốt;
- không có dependency;
- xử lý tốt văn bản dài vừa phải.

Có thể bổ sung:

- toolbar;
- đếm ký tự;
- đếm dòng;
- trạng thái dirty;
- tìm kiếm bằng `Ctrl/Cmd + F`;
- thay thế bằng `Ctrl/Cmd + H`;
- phím tắt lưu;
- đồng bộ scroll có nút bật/tắt.

## 7.2. Khi nào dùng CodeMirror

Chỉ đưa CodeMirror vào khi cần nhiều tính năng sau:

- syntax highlighting;
- line numbers;
- search panel chuẩn;
- multi-selection;
- bracket matching;
- undo/redo nâng cao;
- xử lý văn bản lớn;
- extension editor ổn định.

Nếu dùng, nên chọn **CodeMirror 6**, không nên dùng Monaco Editor vì Monaco lớn và thiên về IDE.

Cách tích hợp nên là:

- vendor nội bộ;
- chỉ tải editor ở trang Biên dịch;
- không để editor trở thành dependency của các trang khác;
- giữ API adapter riêng để sau này thay thế dễ dàng.

Ví dụ tầng abstraction:

```plain text
EditorAdapter
├── TextareaEditor
└── CodeMirrorEditor
```


Phần còn lại của ứng dụng chỉ gọi:

- `getValue()`;
- `setValue()`;
- `focus()`;
- `onChange()`;
- `find()`;
- `replace()`.

Nhờ vậy có thể bắt đầu bằng textarea và nâng cấp sau mà không sửa toàn bộ ứng dụng.

## 7.3. Không nên tự xây editor kiểu contenteditable

`contenteditable` thường gây nhiều vấn đề:

- xử lý selection phức tạp;
- undo/redo không nhất quán;
- tìm kiếm regex khó;
- copy/paste có định dạng không mong muốn;
- đồng bộ nội dung khó;
- accessibility không tự nhiên.

Nên dùng `textarea` hoặc CodeMirror.

---

## 8. Kiến trúc frontend đề xuất

## 8.1. Không cần SPA framework, nhưng nên có SPA nhẹ

Có thể duy trì trải nghiệm giống SPA bằng:

- một file HTML shell;
- các view được render bằng JavaScript;
- điều hướng hash;
- API backend JSON;
- SSE cho tiến độ.

Điều này giữ được UX mượt nhưng không phải trả chi phí của framework.

## 8.2. API layer

Tất cả gọi backend nên đi qua một module duy nhất:

```javascript
async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      "Accept": "application/json",
      ...(options.body ? {"Content-Type": "application/json"} : {})
    },
    ...options
  });

  if (!response.ok) {
    throw await parseApiError(response);
  }

  return response.json();
}
```


Không nên gọi `fetch()` trực tiếp rải rác trong từng component.

Nên thống nhất cấu trúc lỗi:

```json
{
  "error": {
    "code": "FILE_NOT_FOUND",
    "message": "Không tìm thấy file.",
    "details": {}
  }
}
```


Frontend chỉ cần xử lý:

- thông báo cho người dùng;
- log kỹ thuật ở console;
- trạng thái retry nếu phù hợp.

## 8.3. SSE

SSE phù hợp cho:

- tiến độ từng chunk;
- chunk hiện tại;
- tổng số chunk;
- trạng thái hoàn tất;
- lỗi;
- thông tin file đang xử lý.

Frontend cần bảo đảm:

- đóng `EventSource` khi rời trang;
- không tạo nhiều kết nối trùng;
- xử lý reconnect có kiểm soát;
- hiển thị trạng thái mất kết nối;
- không tự động retry vô hạn khi lỗi logic.

Nếu tác vụ chỉ chạy một phiên tại một thời điểm, backend nên trả về mã rõ ràng khi đã có phiên đang chạy.

---

## 9. Quản lý file

Vì tính năng file đơn giản, không nên xây file manager quá phức tạp.

### Nên có

- danh sách file nguồn;
- danh sách file kết quả;
- file đang chọn;
- trạng thái đã dịch;
- trạng thái dirty;
- tạo/xóa/đổi tên nếu thực sự cần;
- lưu atomic;
- cảnh báo ghi đè;
- tải lại danh sách sau thao tác file.

### Không nên có ở giai đoạn đầu

- kéo thả file giữa nhiều panel;
- virtualized file tree;
- multi-select phức tạp;
- drag-and-drop reorder;
- đồng bộ file hệ thống realtime;
- upload manager riêng;
- permission system.

### Quy tắc quan trọng

Frontend không nên tự suy đoán đường dẫn file. Backend phải là nguồn sự thật cho:

- danh sách file;
- đường dẫn hợp lệ;
- khả năng đọc/ghi;
- trạng thái tồn tại;
- lỗi encoding;
- xung đột khi lưu.

Frontend chỉ gửi `project_id`, `file_name` hoặc identifier an toàn do backend cấp.

---

## 10. Chiến lược bảo trì dài hạn

## 10.1. Giữ dependency thấp

Mục tiêu nên là:

```plain text
Runtime frontend dependency: 0
Runtime backend dependency: httpx
Build tool: không bắt buộc
```


Nếu sau này dùng CodeMirror hoặc thư viện diff:

- ghi rõ lý do;
- ghi phiên bản;
- ghi license;
- lưu nội bộ;
- có test hoặc adapter;
- có phương án loại bỏ.

## 10.2. Không trộn các mô hình kiến trúc

Nên tránh đồng thời:

- một phần React;
- một phần Alpine;
- một phần script global;
- một phần template server;
- một phần web component.

Chọn một mô hình chính:

> HTML + CSS + ES Modules + REST/SSE.

## 10.3. Quy ước code

Nên đặt quy ước:

- không dùng biến global ngoài `window.app`;
- mỗi module có một trách nhiệm;
- không thao tác trực tiếp với state của module khác;
- không gọi API trong hàm render;
- render phải có thể gọi lại nhiều lần;
- event listener phải được đăng ký có kiểm soát;
- mọi thao tác bất đồng bộ cần trạng thái loading/error;
- không nuốt lỗi bằng `catch` rỗng.

## 10.4. Kiểm thử

Nên kiểm thử ở ba lớp:

### Backend

- API file;
- API project;
- API prompt;
- API settings;
- SSE;
- lỗi provider;
- atomic write.

### JavaScript

Không nhất thiết phải đưa Jest vào ngay. Có thể bắt đầu bằng:

- kiểm tra thủ công có checklist;
- các hàm thuần được tách riêng;
- test bằng trình duyệt;
- test API bằng Python.

Chỉ thêm test runner frontend khi logic tăng đáng kể.

### E2E

Chưa cần Playwright/Cypress ở giai đoạn đầu. Có thể bổ sung khi:

- số lượng thao tác UI tăng;
- có nhiều lỗi hồi quy;
- có quy trình release thường xuyên.

---

## 11. Những điều không nên làm

1. Không dùng Tailwind CDN trong sản phẩm chính.
2. Không đưa React/Vue chỉ để xử lý vài trang.
3. Không dùng Electron.
4. Không thêm bundler nếu không có nhu cầu rõ ràng.
5. Không dùng CDN cho dependency cốt lõi.
6. Không tự xây hệ thống reactive phức tạp.
7. Không biến một editor đơn giản thành IDE.
8. Không để API call nằm rải rác trong mọi file.
9. Không để mỗi view tự có một cách hiển thị lỗi khác nhau.
10. Không lưu trạng thái quan trọng chỉ ở frontend.
11. Không để frontend trực tiếp quyết định đường dẫn filesystem.
12. Không thêm animation làm ảnh hưởng khả năng đọc và thao tác.
13. Không tách thành quá nhiều file nhỏ khiến việc tìm code khó hơn.
14. Không trộn nhiều thư viện UI có phong cách khác nhau.
15. Không khóa ứng dụng vào framework khi yêu cầu nghiệp vụ còn đơn giản.

---

## 12. Lộ trình triển khai đề xuất

## Phase A — Chuẩn hóa nền tảng

- Tách CSS khỏi HTML.
- Tách JavaScript khỏi HTML.
- Xây app shell.
- Thêm router hash đơn giản.
- Chuẩn hóa API layer.
- Chuẩn hóa state.
- Xây toast, dialog và loading state dùng chung.
- Giữ nguyên chức năng hiện có.

## Phase B — Hoàn thiện UI cốt lõi

- Trang Dự án.
- Trang Biên dịch ba cột.
- Trang Prompt.
- Trang Cấu hình.
- Responsive ở mức desktop nhỏ/tablet.
- Dark mode nếu thực sự cần.
- Phím tắt cơ bản.
- Trạng thái dirty và xác nhận trước khi rời trang.

## Phase C — Cải thiện editor

- Bắt đầu bằng textarea.
- Thêm tìm kiếm/thay thế.
- Thêm regex có xác nhận.
- Thêm đồng bộ scroll.
- Đo hiệu năng với file thực tế.
- Chỉ chuyển sang CodeMirror nếu textarea không còn đáp ứng.

## Phase D — Ổn định

- Kiểm thử các luồng chính.
- Kiểm thử lỗi SSE.
- Kiểm thử file lớn.
- Kiểm thử mất kết nối API.
- Kiểm thử ghi đè và atomic write.
- Tài liệu hóa API và quy ước frontend.
- Ghi lại các quyết định kiến trúc.

---

## 13. Tiêu chí đánh giá trước khi thêm framework

Chỉ nên chuyển sang framework frontend nếu có ít nhất một số dấu hiệu sau:

- trên 10–15 view có tương tác độc lập;
- state chia sẻ giữa nhiều màn hình trở nên khó kiểm soát;
- có nhiều bảng dữ liệu realtime;
- có nhiều workflow song song;
- cần component library lớn;
- nhiều người cùng phát triển frontend;
- cần TypeScript ở quy mô lớn;
- kiểm thử component trở thành nhu cầu bắt buộc;
- việc render thủ công gây lỗi lặp lại thường xuyên.

Hiện tại, các dấu hiệu này chưa đủ rõ để biện minh cho chi phí framework.

---

## 14. Quyết định công nghệ đề xuất

### Quyết định chính thức

```plain text
Frontend:
- HTML semantic
- CSS thuần
- JavaScript ES Modules
- Không framework
- Không bundler
- Không CDN dependency

Backend:
- Python hiện tại
- stdlib http.server
- REST/JSON
- SSE cho tiến độ

Editor:
- textarea nâng cấp ở giai đoạn đầu
- CodeMirror 6 chỉ là phương án nâng cấp có điều kiện

Icons:
- SVG nội bộ

Storage:
- API backend
- filesystem workspace
- SQLite hiện tại
```


### Mức độ phụ thuộc

```plain text
Bắt buộc:
- Không thêm frontend dependency

Có thể bổ sung:
- CodeMirror 6 cho editor
- thư viện diff nhỏ nếu cần diff thực sự

Không khuyến nghị:
- React
- Vue
- Svelte
- Electron
- Tailwind build
- UI component framework lớn
```


---

## 15. Kết luận cuối cùng

Đối với dự án này, lựa chọn bền vững nhất không phải là framework hiện đại nhất mà là kiến trúc có ít lớp nhất:

> **HTML + CSS thuần + JavaScript module + Python REST/SSE.**

Kiến trúc này đáp ứng tốt mục tiêu:

- giao diện đẹp và hiện đại;
- nhẹ;
- không cần build phức tạp;
- dễ chạy local;
- dễ backup;
- ít phụ thuộc;
- dễ bảo trì lâu dài;
- phù hợp với xử lý file và một phiên dịch duy nhất.

Nên đầu tư vào:

1. design token và component CSS nhất quán;
2. cấu trúc JavaScript module rõ ràng;
3. API layer thống nhất;
4. trạng thái loading/error/dirty;
5. editor có abstraction để dễ nâng cấp;
6. UX tốt cho thao tác file và tiến độ dịch.

Không nên đầu tư vào framework frontend lớn ở thời điểm hiện tại.