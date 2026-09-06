# BÁO CÁO REVIEW MÃ NGUỒN & ĐỀ XUẤT TỐI ƯU

> **Dự án:** Content Translator (Next-Gen)  
> **Ngày review:** 05/09/2026  
> **Phạm vi:** Backend Python, CLI, WebUI backend, WebUI frontend, cấu hình, SQLite, test và tài liệu  
> **Mục tiêu:** Đánh giá mức độ tuân thủ `00_PROJECT_MANIFESTO.md`, phát hiện lỗi hiện hữu, đề xuất thứ tự sửa tối thiểu và các cải tiến phù hợp với định hướng Minimalist – Single-user – Local-first.

---

## 1. Tóm tắt điều hành

Dự án đã tiến khá xa so với một CLI dịch tối thiểu:

- Có hai provider REST dùng `httpx`, không dùng SDK nặng.
- Có `KeyRotator`, taxonomy lỗi, retry cùng key và đổi key khi 429.
- Có chunker, prompt engine, atomic write và SQLite index/log.
- WebUI dùng `stdlib http.server`, vanilla JavaScript và SSE.
- Có cơ chế hủy request đang bay.
- Có kiểm soát đường dẫn, migration thư mục `translated/` sang `results/`.
- Có test cho phần lớn thành phần lõi.
- Có cơ chế restart dùng `os.execv()` và script tuyệt đối.

Tuy nhiên, trạng thái hiện tại chưa nên xem là ổn định để tiếp tục mở rộng Phase 3. Một số lỗi thuộc nhóm **P0/P1** có thể làm hỏng contract chính của dự án:

1. WebUI dịch một file đơn có thể **không ghi kết quả ra `results/`** sau khi dịch thành công.
2. `run.py` đang sử dụng `SafeFileHandler` và `atomic_write_text` nhưng phần import hiện tại không đầy đủ, có khả năng gây `NameError` ở các nhánh tương ứng.
3. `main.py` chứa quá nhiều trách nhiệm trong một file lớn, khiến lỗi contract và lỗi đường dẫn khó phát hiện.
4. Error model đã được chuẩn hóa ở client nhưng chưa được áp dụng nhất quán cho toàn bộ pipeline.
5. Một số đường dẫn và thao tác file vẫn được tạo trực tiếp trong HTTP handler, không hoàn toàn đi qua lớp chuyên trách như manifesto yêu cầu.
6. Database mới là index/log, nhưng việc cập nhật index chưa nhất quán với vòng đời file và trạng thái phiên dịch.
7. Bộ test tốt về unit test nhưng còn thiếu test tích hợp cho các luồng quan trọng: dịch WebUI thành công, output atomic, cancel, restart và consistency giữa file system với app.db.

**Kết luận:** Kiến trúc hiện tại phù hợp với tôn chỉ dự án, nhưng cần một vòng “stabilization” trước khi bổ sung tính năng mới. Không nên thêm checkpoint, plugin framework, ORM, frontend framework hoặc hệ thống quản lý workflow phức tạp.

---

## 2. Tiêu chí review theo manifesto

### 2.1. Chu trình gửi – nhận

| Tiêu chí | Đánh giá |
|---|---|
| Chia chunk tự nhiên | Đạt phần lớn |
| Không bỏ nội dung có ý nghĩa ở tầng chunk | Đạt về ý tưởng, cần bổ sung property test |
| Prompt đơn giản | Đạt |
| Gửi tuần tự | Đạt |
| Explicit provider/model | Đạt ở phần lớn đường đi |
| Không fallback model ngầm | Đạt |
| Xoay key khi 429 | Đạt |
| Dừng khi thất bại | Đạt |
| Không checkpoint | Đạt |
| Ghép kết quả bằng `\n\n` | Đạt ở CLI và merge, cần kiểm tra single-file WebUI |
| Ghi output atomic | Có helper, cần kiểm tra mọi đường đi |
| Ghi log run | Có, nhưng chưa nhất quán về `file_id` và trạng thái |

### 2.2. Local-first và single-user

Định hướng này đang được giữ đúng:

- Không auth, không multi-user.
- Không masking key mặc định.
- Không reverse proxy hoặc server public.
- Không dùng framework frontend.
- Không dùng database làm nơi lưu checkpoint nội dung.
- Không có background worker hoặc hàng đợi ngầm.

Không đề xuất đưa thêm các cơ chế bảo mật dành cho ứng dụng public vì không phù hợp manifesto.

### 2.3. Chính sách dependency

Đang phù hợp:

- Backend chủ yếu là stdlib + `httpx`.
- WebUI vanilla.
- Không có build step bắt buộc.
- Không phụ thuộc CDN.

Cần duy trì nguyên tắc này. Chưa có lý do đủ mạnh để đưa React, Vue, Tailwind, CodeMirror, Monaco hoặc framework backend vào dự án.

---

## 3. Phát hiện mức độ nghiêm trọng

### P0 — Phải sửa trước khi tiếp tục phát triển

#### P0.1. Luồng WebUI dịch một file không ghi output

Trong luồng xử lý dịch đơn file, sau khi `_run_chunks()` hoàn thành, code hiện chỉ cập nhật index với trạng thái:
```
text
_upsert_file(..., "translating")
```
và ghi log `ok`, nhưng không thấy bước tương đương:
```
text
fh.save_output(project, fname, "\n\n".join(outs))
```
Điều này vi phạm trực tiếp chu trình cốt lõi:
```
text
Nhận response → Ghép kết quả → Ghi ra file
```
Hậu quả:

- SSE có thể báo hoàn thành.
- UI có thể nhận được chunk/result tạm thời.
- Nhưng file kết quả thực tế có thể không tồn tại trong `workspace/projects/{slug}/results/`.
- Card dự án và danh sách kết quả không phản ánh kết quả vừa dịch.
- Người dùng có thể tưởng rằng bản dịch đã được lưu trong khi chưa được lưu.

**Đề xuất sửa:**

Sau khi tất cả chunk thành công:

1. Ghép bằng `"\n\n".join(outs)`.
2. Ghi qua `fh.save_output(project, fname, output)`.
3. Chỉ sau khi ghi thành công mới cập nhật `files.status = "done"`.
4. Sau đó ghi `runs.status = "ok"`.
5. SSE `done` chỉ được phát sau cả output và DB đã hoàn tất.

Trạng thái `"translating"` không nên là trạng thái cuối của phiên thành công.

#### P0.2. `run.py` có nguy cơ thiếu import

`run.py` sử dụng các biểu tượng:

- `SafeFileHandler`
- `atomic_write_text`

nhưng phần import cần được kiểm tra và bảo đảm có đầy đủ. Nếu thiếu, các nhánh sau sẽ lỗi runtime:

- Dịch theo `--project`.
- Ghi output CLI.

Đây là lỗi đơn giản nhưng ảnh hưởng trực tiếp Phase 1.

**Đề xuất:** bổ sung import rõ ràng từ `core.file_handler` và thêm test chạy `main()` với filesystem tạm, không chỉ test các client riêng lẻ.

#### P0.3. Thành công của AI chưa đồng nghĩa thành công của run

Pipeline hiện có nguy cơ ghi log `ok` ngay sau khi provider trả response, trước khi xác nhận:

- output được ghi thành công;
- tên file hợp lệ;
- DB index cập nhật thành công;
- trạng thái file đã chuyển sang `done`.

Theo contract thực tế, “run thành công” phải có nghĩa là:
```
text
Tất cả chunk thành công
+ output được ghép
+ output được ghi atomic
+ index/log được ghi
```
Nếu ghi file thất bại, run phải là `error`, không phải `ok`.

---

### P1 — Nên sửa ngay trong stabilization phase

#### P1.1. Error taxonomy chưa bao phủ toàn bộ pipeline

Client đã có phân loại lỗi tương đối rõ:

- 429: đổi key.
- timeout/network/408/5xx: retry cùng key có giới hạn.
- 4xx khác, response rỗng, JSON sai: dừng ngay.

Tuy nhiên, pipeline bên ngoài client vẫn bắt lỗi theo nhóm Python exception chung. Điều này làm mất metadata hữu ích:

- provider;
- model;
- chunk hiện tại;
- attempt;
- key index;
- HTTP status;
- nguyên nhân phân loại;
- file đang xử lý.

**Đề xuất:**

Không cần tạo framework lỗi phức tạp. Chỉ cần thống nhất một exception nhẹ, ví dụ:
```
text
TranslationError
- category: retry_same_key | rotate_key | stop
- provider
- model
- status_code
- chunk_index
- message
```
Client có thể tiếp tục quyết định retry nội bộ, nhưng khi dừng thì trả lỗi có cấu trúc. CLI/WebUI chỉ hiển thị thông điệp và log lỗi, không tự phân loại lại.

#### P1.2. `main.py` quá lớn và có quá nhiều trách nhiệm

`main.py` hiện cùng lúc đảm nhiệm:

- HTTP server;
- static file serving;
- API routing;
- project management;
- file operations;
- prompt API;
- settings API;
- provider API;
- find/replace;
- translation orchestration;
- merge translation;
- SSE;
- cancellation;
- restart;
- database update.

Điều này không vi phạm trực tiếp nguyên tắc “không framework”, nhưng làm tăng rủi ro:

- sửa một endpoint ảnh hưởng endpoint khác;
- logic kiểm tra path bị lặp;
- logic ghi DB bị rải rác;
- khó viết integration test;
- dễ xảy ra tình trạng UI báo thành công nhưng output chưa được lưu.

**Đề xuất tối thiểu, không framework:**

Tách theo trách nhiệm mỏng:
```
text
server/
  http_helpers.py
  routes_projects.py
  routes_files.py
  routes_settings.py
  routes_translation.py
  translation_service.py
```
Nếu chưa muốn tách thư mục, ít nhất tạo các module:
```
text
core/translation_flow.py
core/project_service.py
core/settings_service.py
```
`main.py` chỉ nên giữ:

- tạo server;
- route dispatch;
- request/response helper;
- khởi động ứng dụng.

Không cần dependency injection framework.

#### P1.3. Logic translation flow nên dùng một service chung

Hiện single-file và merge đã có một phần dùng chung như `_run_chunks()`, nhưng phần trước và sau vòng lặp vẫn còn khác nhau:

- cách xác định file;
- cách cập nhật DB;
- cách lưu output;
- cách ghi log;
- cách phát SSE;
- cách xử lý cancellation.

Nên chuẩn hóa thành flow:
```
text
resolve_target()
read_inputs()
build_chunks()
build_prompts()
translate_chunks()
join_outputs()
persist_outputs()
update_index()
log_run()
emit_done()
```
Merge chỉ khác ở:

- input gồm nhiều file;
- marker;
- mapping output về nhiều file.

Các bước còn lại nên dùng chung.

#### P1.4. `app.db` chưa phản ánh đầy đủ trạng thái thực

Database chỉ là index/log, đúng manifesto. Tuy nhiên:

- CLI direct input/output có thể không có `file_id`.
- Merge run không gắn được rõ với từng file.
- `files.status` đôi lúc được cập nhật trước khi output hoàn tất.
- `size_bytes` trong `_upsert_file()` đang được ước lượng từ tên file + số ký tự, không phải kích thước thực tế.

Đề xuất:

- Không thêm bảng checkpoint.
- Giữ nguyên ba bảng.
- Dùng `Path.stat().st_size` khi file thực sự tồn tại.
- Chỉ cập nhật status `done` sau khi output đã ghi xong.
- Khi lỗi, cập nhật `status = "error"` nếu file đã được index.
- Với merge, có thể ghi một run chung và liên kết `file_id` của file đầu tiên; hoặc ghi nhiều run nếu muốn lịch sử từng file. Không cần thêm bảng mới.

#### P1.5. Transaction file và DB chưa đồng bộ

Không thể có transaction thật giữa filesystem và SQLite, nhưng có thể thiết kế thứ tự an toàn:

1. Dịch xong trong memory.
2. Ghi output atomic.
3. Cập nhật DB.
4. Ghi run thành công.

Nếu bước 3 hoặc 4 thất bại:

- output vẫn tồn tại;
- cần log lỗi rõ ràng;
- lần mở UI sau đó nên có cơ chế reindex nhẹ hoặc cập nhật lại metadata.

Không nên ghi DB là `done` trước khi output tồn tại.

#### P1.6. Hủy phiên giữa request cần test mạnh hơn

Cơ chế `_post_or_abort()` dùng task và polling event là phù hợp với mục tiêu local-first, nhưng cần kiểm tra:

- task HTTP có thực sự bị cancel không;
- `httpx.AsyncClient` có đóng connection không;
- cancel trong lúc delay giữa hai chunk;
- cancel sau response nhưng trước khi ghi output;
- cancel đồng thời với restart;
- client không bị giữ lock;
- `_active_job` và `_translate_lock` luôn được giải phóng.

Nguyên tắc quan trọng:

- Hủy trước khi ghi output: không ghi output dở dang.
- Hủy sau khi output đã ghi xong: run phải phản ánh đúng là hoàn tất, không đổi thành cancelled.
- SSE phải luôn nhận event kết thúc hoặc lỗi có thể hiểu được.

---

## 4. Review từng thành phần

### 4.1. Chunker

Điểm tốt:

- Xử lý file rỗng.
- Ưu tiên `\n\n`, `\n`, câu, khoảng trắng.
- Có fallback cắt cứng.
- Kết quả đệ quy có giới hạn theo `max_chars`.

Rủi ro:

1. `max_chars <= 0` nếu được gọi trực tiếp sẽ gây hành vi không an toàn hoặc đệ quy bất thường. `normalize_prefs()` có bảo vệ, nhưng hàm lõi nên tự bảo vệ.
2. Việc chọn dải 20%–80% theo toàn bộ văn bản trong mỗi lần đệ quy không tối ưu cho các văn bản có đoạn rất dài.
3. Regex câu chưa bao phủ nhiều dấu câu và trường hợp viết tắt, nhưng đây là chấp nhận được trong Phase 1.
4. Chưa có property test bảo đảm mọi chunk đều `<= max_chars`.
5. Chưa có test bảo đảm nội dung sau khi chuẩn hóa khoảng trắng vẫn không mất token có ý nghĩa.

Đề xuất:

- `max_chars <= 0` → `ValueError`.
- Thêm test:
  - mọi chunk không vượt giới hạn;
  - nối các chunk sau `.strip()` tương ứng với input theo contract whitespace;
  - văn bản Unicode;
  - văn bản không có khoảng trắng;
  - đoạn cực dài không có dấu ngắt.
- Không cần tokenizer hoặc thư viện NLP.

### 4.2. Prompt engine

Điểm tốt:

- Dùng UTF-8.
- Có placeholder `{{source_text}}`.
- Có hỗ trợ `{{glossary_terms}}` ở flow WebUI.
- Đã có kiểm tra tên prompt `.txt`.

Rủi ro:

- `load_prompt()` cần áp dụng cùng một validation `_check_name()` thay vì chỉ kiểm tra tồn tại. Nếu có caller khác gọi trực tiếp với tên chứa path traversal, contract có thể bị phá vỡ.
- Endpoint PUT prompt cần dùng cùng validation helper, không tự lặp điều kiện.
- Prompt mặc định bị xóa/đổi tên đã được chặn ở route; cần thêm invariant ở service layer để CLI hoặc caller khác cũng không phá được.
- Nếu prompt thiếu, manifesto yêu cầu fallback + warn đối với `default_prompt`. Cần bảo đảm hành vi giữa CLI và WebUI giống nhau.

Đề xuất:

- Tất cả thao tác tên prompt đi qua một hàm duy nhất.
- Prompt engine chịu trách nhiệm fallback prompt mặc định.
- HTTP handler không tự kiểm tra chuỗi tên prompt.

### 4.3. Provider manager và config

Điểm tốt:

- `providers.json` được định hướng là SSOT.
- Có migration một chiều.
- Có atomic write.
- Có model explicit.
- Có provider-specific key.
- Thinking chỉ áp dụng cho Gemini.

Rủi ro:

- Một số logic tương thích cũ vẫn tồn tại trong `AppConfig`, có thể làm người đọc nhầm rằng `keys.json` vẫn là runtime SSOT.
- Cần đảm bảo không có module mới tiếp tục đọc trực tiếp `config/keys.json`.
- `run.py` cần lấy prefs từ `AppConfig` nhưng provider/model/key từ `AIProviderManager`, đúng phân tầng này.
- Validation model namespace cần được áp dụng nhất quán cho cả CLI và WebUI.
- “Live model listing” nên là tính năng hỗ trợ cấu hình; không nên khiến đường dịch chính phụ thuộc mạng ngoài khi model đã được chọn explicit.

Đề xuất:

- Ghi rõ trong docstring:
  - `AppConfig`: chỉ prefs app;
  - `AIProviderManager`: providers, model, key;
  - migration legacy chỉ chạy trong một nơi.
- Thêm test kiểm tra một module bất kỳ không cần đọc `keys.json` trực tiếp.
- Không tự động đổi model khi API `/models` lỗi.

### 4.4. AI clients

Điểm tốt:

- Dùng `httpx` thuần.
- Không SDK.
- Có timeout.
- Có xoay key 429.
- Có retry cùng key có giới hạn.
- Có callback progress.
- Có cancellation.

Rủi ro:

1. Mỗi chunk tạo mới `httpx.AsyncClient`. Với file thường chỉ 2–3 chunk, đây không phải vấn đề hiệu năng nghiêm trọng, nhưng vẫn làm code và connection lifecycle phức tạp hơn.
2. Gemini và OpenAI-compatible có thể lệch nhẹ về validation response.
3. Một số lỗi `httpx` khác ngoài `ConnectError` và `TimeoutException` có thể thoát ra dưới dạng exception thô.
4. Response JSON sai cấu trúc cần được chuyển thành lỗi chuẩn, không để `AttributeError`/`KeyError` lọt ra.
5. Response text chỉ kiểm tra field tồn tại ở Gemini; nên kiểm tra chuỗi không rỗng như OpenAI-compatible.
6. Không nên log URL Gemini có API key trong message lỗi hoặc debug log.

Đề xuất:

- Có helper parse response chung ở mức nhỏ, không cần abstraction framework.
- Chuẩn hóa lỗi `response_empty`, `invalid_response`, `safety_block`.
- Kiểm tra `text.strip()`.
- Bổ sung test cho:
  - JSON không phải object;
  - candidates sai kiểu;
  - parts rỗng;
  - text rỗng;
  - HTTP 408/500/502/503/504;
  - HTTP 400/401/403/404;
  - `httpx.RequestError` ngoài ConnectError.
- Duy trì nguyên tắc không in key.

### 4.5. KeyRotator

Logic đơn giản và phù hợp manifesto.

Cần kiểm tra thêm:

- key trùng nhau;
- key có whitespace;
- danh sách rỗng;
- nhiều lần `try_next_key()` sau khi đã hết;
- bắt đầu chunk mới sau khi key cuối cùng thành công;
- key đang dùng của chunk trước được tái sử dụng đúng như đặc tả.

Nếu key trùng nhau, nên loại trùng lúc khởi tạo để “mỗi key thử tối đa một lần” có nghĩa thực tế.

### 4.6. File handler và fileops

Điểm tốt:

- Có `relative_to()`.
- Có sanitize tên.
- Có Unicode NFC.
- Có atomic write.
- Có tránh ghi đè khi upload.
- Có xử lý `results/`.
- Có archive.

Rủi ro:

1. Một số route vẫn tự xây dựng đường dẫn như `project_dir / side`.
2. Một số route tự lặp validation tên thay vì gọi helper.
3. `archive_project()` tạo zip rồi xóa thư mục. Nếu xóa thất bại hoặc zip chưa hoàn tất, cần báo rõ.
4. Đổi tên paired sources/results có hành vi `_conflict`; cần tài liệu hóa rõ cho UI.
5. `delete_file()` cần được kiểm tra xem xóa source, result hay cả cặp. Contract UI phải nhất quán.
6. `read_text(errors="replace")` phù hợp cho xem nội dung, nhưng không phù hợp cho read-modify-write vì có thể làm hỏng file binary. Logic find/replace đã có strict read; nên áp dụng nguyên tắc tương tự ở các thao tác ghi.

Đề xuất:

- File handler cung cấp các operation cấp cao:
  - `list_files(slug, side)`
  - `read_file(slug, side, filename)`
  - `write_file(slug, side, filename, content)`
  - `delete_file(slug, side, filename)`
  - `rename_file(...)`
- Handler HTTP không tự nối path.
- Không cần một lớp repository phức tạp.

### 4.7. SQLite app_db

Điểm tốt:

- Chỉ dùng stdlib.
- Chỉ có `projects/files/runs`.
- Không lưu checkpoint.
- Có migration cột project metadata.

Rủi ro:

- Migration hiện dùng SQL động cho tên cột, hiện an toàn vì danh sách nội bộ cố định, nhưng nên giữ cách này thật giới hạn.
- Nhiều nơi mở DB, commit và close thủ công.
- Chưa có context manager thống nhất.
- Lỗi DB có thể làm lỗi sau khi output đã ghi mà không có hướng dẫn khôi phục.
- `runs` chưa có thời lượng hoặc số chunk; không bắt buộc nhưng hữu ích cho history.
- Không nên thêm bảng chunks/checkpoints nếu chưa có nhu cầu thực tế.

Đề xuất tối thiểu:

- Tạo helper context manager:
```
python
with db_connection() as con:
    ...
```
- Bật `PRAGMA foreign_keys = ON` nếu schema có quan hệ phù hợp.
- Thêm index nhẹ cho:
  - `files(project_slug, filename)`;
  - `runs(started_at)`.
- Duy trì ba bảng.
- Cân nhắc thêm `chunk_count` và `char_count` vào log chỉ nếu không làm đổi contract đáng kể.

### 4.8. CLI

Điểm tốt:

- Hỗ trợ direct file và project file.
- Có provider/model explicit.
- Không fallback.
- Dừng khi chunk lỗi.
- Ghép `\n\n`.
- Ghi atomic output.

Cần sửa:

- Bảo đảm import đầy đủ.
- Dùng `default_prompt` từ normalized prefs khi người dùng không truyền `--prompt`, thay vì hardcode riêng.
- Ghi `error` cho file nếu chạy project mode bị lỗi.
- Xác định rõ output direct path có cần được kiểm tra parent path hay không. Direct mode cho phép file ngoài workspace theo đặc tả, nên không được áp dụng nhầm workspace restriction.
- Không hỏi API key rồi lưu vào legacy `keys.json`; phải lưu qua `providers.json` manager.
- Khi provider không có key, thông báo phải chỉ rõ provider id và đường dẫn cấu hình.

### 4.9. WebUI backend

Điểm tốt:

- Dùng stdlib.
- Có SSE.
- Có lock một phiên.
- Có cancel.
- Có restart.
- Có health version.
- Có kiểm tra path traversal.
- Có atomic save/find-replace.
- Có live provider/model management.

Rủi ro lớn:

- File `main.py` quá lớn.
- Route tự xử lý quá nhiều nghiệp vụ.
- Single-file translation có nguy cơ không lưu output.
- Một số endpoint có cách xử lý lỗi không đồng nhất.
- Có thể có sự khác biệt giữa `provider_id` trong UI và `active_id`.
- Restart endpoint dùng timer và `execv`; cần test khi server đang xử lý request.
- SSE ghi trực tiếp vào `wfile`; client đóng kết nối giữa chừng cần được xử lý để không làm lỗi cleanup.
- `ThreadingHTTPServer` cho nhiều request đồng thời nhưng translation chỉ khóa một phiên; các endpoint đọc/ghi file vẫn có thể chạy song song với thao tác khác. Cần bảo đảm endpoint xóa/đổi tên bị chặn đúng trong lúc dịch.

Đề xuất:

- Ưu tiên sửa persistence flow trước khi refactor lớn.
- Sau đó tách `translation_service`.
- Giữ một phiên dịch duy nhất.
- Không thêm worker queue hoặc background task.

### 4.10. WebUI frontend

Theo định hướng manifesto, vanilla JS/CSS là lựa chọn đúng.

Cần kiểm tra định kỳ:

- `node --check` cho toàn bộ file JS.
- Không có HTML injection khi hiển thị nội dung AI.
- Không dùng `innerHTML` với text chưa escape.
- SSE đóng đúng khi error/cancel.
- UI không báo `done` trước khi server lưu xong.
- Nút retry phải chạy lại toàn bộ file, không giả vờ resume.
- Key hiển thị đầy đủ theo contract single-user.
- Không thêm CDN dependency cứng.
- Không đưa editor framework nặng nếu chưa có bằng chứng bug IME hoặc merge.

---

## 5. Các vấn đề tài liệu cần chỉnh

### 5.1. Tài liệu “đã hoàn thành” đang mạnh hơn bằng chứng runtime

Hồ sơ Phase 2.5 mô tả nhiều exit criteria là hoàn thành. Sau mỗi thay đổi lớn cần kiểm chứng lại bằng test/runtime hiện tại, đặc biệt:

- single-file WebUI save;
- run.py project mode;
- restart;
- output path;
- status DB;
- migration `translated/` → `results/`.

Tài liệu hoàn thành không nên được dùng thay cho smoke test hiện tại.

### 5.2. Tài liệu cần ghi rõ trạng thái code thực tế

Nên thêm một bảng ngắn trong tài liệu review hoặc README:

| Thành phần | Trạng thái |
|---|---|
| CLI direct | Cần smoke test |
| CLI project | Cần kiểm tra import + output |
| WebUI single translation | Cần sửa persistence |
| WebUI merge | Có flow lưu output, cần integration test |
| Cancel | Có code, cần test thực tế |
| Restart | Có code, cần test nhiều launcher |
| Model live listing | Có code, cần test lỗi mạng |
| Archive | Có code, cần test rollback/failure |

### 5.3. Đồng bộ version tài liệu và runtime

Hiện có nhiều mốc version giữa:

- manifesto;
- README;
- `server_version`;
- CHANGELOG;
- tài liệu Phase 2.5;
- docs Phase 1.

Nên có một nguồn version runtime tối thiểu, hoặc ít nhất kiểm tra tự động để phát hiện lệch version. Không cần package/release system phức tạp.

---

## 6. Kế hoạch sửa đề xuất

### Sprint S0 — Khôi phục tính đúng đắn

Ưu tiên tuyệt đối, chưa thêm tính năng:

1. Sửa import trong `run.py`.
2. Sửa single-file WebUI để ghép và lưu output.
3. Chỉ phát `done` sau khi output ghi thành công.
4. Cập nhật `files.status` đúng:
   - `new`;
   - `translating`;
   - `done`;
   - `error`;
   - `cancelled` nếu cần hiển thị.
5. Ghi `runs.error` cho mọi lỗi.
6. Chạy toàn bộ test hiện có.
7. Thêm smoke test cho CLI direct/project và WebUI single translation.

### Sprint S1 — Khóa contract bằng test

Thêm test:

1. `split_text()` luôn tạo chunk không vượt giới hạn.
2. CLI dịch nhiều chunk và ghép bằng `\n\n`.
3. CLI lỗi ở chunk 2 không ghi output mới.
4. WebUI single translation ghi `results/`.
5. WebUI single translation lỗi không tạo output dở dang.
6. WebUI cancel giữa request.
7. WebUI cancel giữa delay.
8. HTTP response JSON sai cấu trúc.
9. HTTP 5xx retry đúng số lần.
10. HTTP 4xx dừng ngay.
11. Provider explicit không fallback.
12. Restart tạo process mới với script tuyệt đối.
13. Find/replace giữ nguyên file khi lỗi.
14. Archive không xóa project nếu tạo archive thất bại.

### Sprint S2 — Refactor mỏng

Không đổi kiến trúc lớn:

1. Tách `translation_service.py`.
2. Tách helper persistence output + DB status.
3. Tách provider/config route nếu cần.
4. Giữ `main.py` làm HTTP adapter.
5. Giữ `http.server`, SSE và vanilla JS.
6. Không thêm framework.

### Sprint S3 — Cải tiến nhỏ có giá trị

Chỉ thực hiện sau khi S0–S2 ổn định:

- Hiển thị thời gian request/chunk.
- Hiển thị số ký tự đã gửi/nhận.
- Lịch sử run rõ hơn.
- Reindex nhẹ khi phát hiện file có nhưng DB thiếu.
- Cảnh báo output cũ sẽ bị thay thế.
- Nút “mở thư mục dự án” nếu phù hợp hệ điều hành.
- Backup prompt/project thủ công.

Không thực hiện:

- checkpoint;
- resume;
- queue;
- parallel translation;
- automatic model fallback;
- account/auth;
- secret vault;
- ORM;
- frontend framework;
- plugin loader động.

---

## 7. Đề xuất thay đổi tính năng

### 7.1. Nên giữ

- Một phiên dịch tại một thời điểm.
- Gửi tuần tự.
- Một key thử tối đa một lần/chunk khi 429.
- Chạy lại thủ công từ đầu khi lỗi.
- Provider/model explicit.
- Full key trong UI.
- `results/` là thư mục kết quả chuẩn.
- Prompt `.txt`.
- Merge nhiều file là tính năng hỗ trợ mỏng.
- Find/replace local theo file.
- Restart thủ công và health version.

### 7.2. Nên điều chỉnh

#### Trạng thái file

Đề xuất hiển thị rõ:
```
text
new
translating
done
error
cancelled
```
Không dùng `translating` làm trạng thái sau khi hoàn thành.

#### Retry

UI nên hiển thị:
```
text
chunk 2/3
attempt 2/2
key 2/3
```
Khi thất bại cần nói rõ:

- lỗi mạng;
- timeout;
- 429 hết key;
- lỗi auth;
- model không hợp lệ;
- response rỗng/safety block.

#### Save semantics

Khi dịch thành công:

1. Output mới thay output cũ bằng atomic replace.
2. UI nhận `done`.
3. Lịch sử ghi `ok`.

Khi thất bại:

1. Output cũ giữ nguyên.
2. Không tạo output mới.
3. UI nhận `error`.
4. Lịch sử ghi `error`.

Đây là behavior quan trọng hơn các cải tiến UI khác.

---

## 8. Đề xuất kiểm tra thủ công sau khi sửa

### CLI direct
```
bash
python run.py input.txt output.txt --provider <id> --model <model>
```
Kiểm tra:

- output tồn tại;
- nội dung có số chunk tương ứng;
- lỗi chunk 2 không ghi output mới;
- provider/model trong log đúng.

### CLI project
```
bash
python run.py --project <slug> --file <filename> \
  --provider <id> --model <model>
```
Kiểm tra:

- đọc từ `sources/`;
- ghi vào `results/`;
- không tạo path ngoài workspace;
- tên Unicode hoạt động.

### WebUI

1. Tạo project.
2. Upload source.
3. Dịch một file.
4. Chờ event `done`.
5. Refresh trình duyệt.
6. Kiểm tra file kết quả vẫn tồn tại.
7. Mở lại file kết quả.
8. Kiểm tra card cập nhật `done`.
9. Dịch file nhiều chunk.
10. Hủy giữa request.
11. Hủy giữa delay.
12. Thử lỗi 429 và hết key.
13. Thử lỗi auth/model.
14. Restart bằng `python main.py`.
15. Restart bằng `uv run python main.py`.
16. Kiểm tra `started_at` thay đổi.

### Filesystem/DB

Sau mỗi kịch bản:
```
text
workspace/projects/{slug}/sources/
workspace/projects/{slug}/results/
workspace/app.db
```
Đối chiếu:

- file thật có tồn tại;
- DB không báo `done` khi file không tồn tại;
- run error có message;
- không có file `.tmp` còn sót;
- không có thư mục `translated/` phát sinh lại.

---

## 9. Tiêu chí nghiệm thu đề xuất

Chỉ xem stabilization hoàn tất khi tất cả điều kiện sau đạt:

- [ ] CLI direct chạy được từ CWD bất kỳ.
- [ ] CLI project chạy được với tên project/file Unicode.
- [ ] WebUI single translation thực sự ghi output.
- [ ] WebUI merge thực sự ghi output.
- [ ] Output cũ không bị hỏng khi request mới thất bại.
- [ ] Không fallback provider/model.
- [ ] 429 xoay key đúng.
- [ ] Timeout/network retry đúng giới hạn.
- [ ] 4xx dừng ngay.
- [ ] Cancel giải phóng lock.
- [ ] Restart hoạt động với `python`, venv và `uv run`.
- [ ] Không còn `NameError` trên các nhánh CLI.
- [ ] Tất cả test pass.
- [ ] Có ít nhất một integration test cho mỗi đường dịch.
- [ ] Không thêm checkpoint, queue hoặc framework ngoài manifesto.
- [ ] README và docs phản ánh đúng behavior runtime hiện tại.

---

## 10. Kết luận cuối

Dự án đang đi đúng hướng kiến trúc:
```
text
UI/CLI
  → chunker
  → prompt engine
  → explicit provider/model
  → REST client
  → tuần tự từng chunk
  → ghép kết quả
  → atomic output
  → log tối thiểu
```
Đây là kiến trúc phù hợp với bản chất công cụ local single-user và không nên bị thay thế bằng hệ thống workflow lớn hơn.

Điểm cần ưu tiên không phải là thêm tính năng, mà là bảo đảm contract cơ bản luôn đúng:

> Nếu AI trả về thành công, người dùng phải nhận được file kết quả thật.  
> Nếu có lỗi, output cũ phải còn nguyên và chương trình phải dừng rõ ràng.  
> Nếu UI báo hoàn tất, filesystem và database phải phản ánh đúng trạng thái đó.

Sau khi sửa các lỗi P0/P1 và khóa bằng integration test, dự án có thể tiếp tục các tính năng Phase 3 theo hướng mở rộng mỏng, không làm tăng trạng thái ẩn hoặc độ phức tạp không cần thiết.