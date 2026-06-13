# Kế hoạch Clear Project TM, Force Retranslate và loại bỏ Translation Cache theo giai đoạn

Ngày cập nhật: 2026-06-12

## Quyết định hiện tại

Người dùng đã đồng ý:

1. Triển khai Phase 1: `Xóa TM dự án` và `Dịch lại từ đầu`.
2. Xây dựng Phase 2 chi tiết để loại bỏ hoàn toàn Translation Cache khỏi hệ thống theo từng bước bóc tách, sao cho sau mỗi bước hệ thống vẫn hoạt động bình thường.

Kế hoạch này thay thế bản trước. Trọng tâm mới là:

- Giải quyết ngay lỗi “dịch lại vẫn ra bản cũ” bằng Phase 1.
- Sau đó loại bỏ Translation Cache có kiểm soát, không xóa ồ ạt gây gãy import hoặc hỏng flow dịch.

## Đánh giá về Translation Cache

### Cache hiện có tác dụng gì?

Translation Cache hiện lưu bản dịch theo hash chính xác của:

- chunk gốc,
- prompt,
- model,
- temperature,
- previous chunk context.

Cache chỉ hit khi gần như mọi thành phần trên giống hệt. Nó khác Translation Memory ở chỗ:

- Cache là exact key/value.
- TM là bộ nhớ project, có exact/fuzzy match.
- Checkpoint là resume trạng thái dịch dở.

### Khi cache còn hữu ích

Cache có thể hữu ích trong các trường hợp:

1. Dịch thử lặp lại cùng một đoạn ngắn với cùng prompt/model/temperature.
2. Chạy lại cùng file sau lỗi mạng/API mà input chưa đổi.
3. Test thủ công UI/backend nhưng muốn tránh gọi API thật nhiều lần.
4. Provider có quota rất thấp hoặc tính phí cao.

### Khi cache gây nhiễu

Trong workflow dịch sách/novel hiện tại, cache dễ gây nhiễu vì:

1. Người dùng thường thay prompt, glossary, style guide, model hoặc temperature để cải thiện bản dịch.
2. Người dùng muốn “dịch lại thật sự khác”, tức cần gọi API lại.
3. TM project đã đảm nhận vai trò tái sử dụng dài hạn tốt hơn cache.
4. Checkpoint đã đảm nhận vai trò chống mất tiến độ khi dịch file dài.
5. UI từng làm người dùng hiểu nhầm giữa `workspace/cache`, TM project và checkpoint.

### Kết luận đề xuất

Với mục tiêu sản phẩm hiện tại, nên loại bỏ Translation Cache khỏi luồng dịch chính. TM và checkpoint là hai cơ chế nên giữ:

- Giữ TM vì có ích cho project dài hạn.
- Giữ checkpoint vì cần cho dịch file dài.
- Loại bỏ cache vì lợi ích thấp hơn độ phức tạp và rủi ro stale/nhầm lẫn.

Nên loại bỏ theo nhiều bước, không xóa `services/cache_service.py` ngay từ đầu.

## Các lớp lưu trữ sau khi hoàn tất

Sau khi loại bỏ cache, hệ thống chỉ còn:

1. Output file:

```text
workspace/projects/<slug>/translated/<filename>
```

2. Checkpoint:

```text
workspace/checkpoints/*.db
```

3. Project Translation Memory:

```text
workspace/projects/<slug>/assets/translation_memory/memory.json
```

Không còn:

```text
workspace/cache/*.json.gz
```

## Phase 1: Clear Project TM và Force Retranslate

Trạng thái: **Đã được đồng ý triển khai.**

Mục tiêu:

- Người dùng có thể xóa TM riêng của project đang mở.
- Người dùng có thể ép một lần dịch đi API thật, bỏ qua checkpoint/cache/TM.
- Hệ thống vẫn hoạt động với code cache hiện hữu trong lúc Phase 2 chưa hoàn tất.

### Phase 1.1: Backend endpoint Clear Project TM

Thêm endpoint:

```http
POST /api/projects/<slug>/tm/clear
```

File:

```text
webui/routes/projects.py
```

Logic:

1. Resolve project dir bằng `_get_project_dir(slug)`.
2. Kiểm tra project tồn tại.
3. Tạo `TranslationMemory(tm_dir=str(pdir / "assets" / "translation_memory"), enabled=True)`.
4. Gọi `clear()`.
5. Trả JSON:

```json
{
  "success": true,
  "deleted": 123
}
```

Lưu ý:

- Endpoint `/api/tm/clear` hiện tại xóa singleton global TM, không phải TM riêng project.
- UI project phải gọi endpoint mới theo `slug`.

### Phase 1.2: Backend Force Retranslate

Mở rộng endpoint:

```http
POST /api/projects/<slug>/translate
```

Payload mới:

```json
{
  "files": ["example.txt"],
  "force_retranslate": true
}
```

Trong `webui/routes/projects.py`:

```python
force_retranslate = bool(data.get("force_retranslate", False))
config["force_retranslate"] = force_retranslate
```

Khi `force_retranslate=True`:

- Set `config["use_cache"] = False` cho lần chạy này.
- Truyền `translation_memory=None` vào `use_case.execute(...)`.

Ví dụ:

```python
project_tm = None
if not force_retranslate:
    project_tm = TranslationMemory(
        tm_dir=str(pdir / "assets" / "translation_memory"),
        enabled=True,
    )
```

### Phase 1.3: Executor bỏ qua checkpoint/cache/TM khi force

File:

```text
core/executor.py
```

Thêm:

```python
force_retranslate = bool(self.config.get("force_retranslate", False))
```

Khi force:

1. Cleanup checkpoint của đúng file trước khi chạy.
2. Bỏ qua checkpoint resume.
3. Không đọc cache.
4. Không dùng TM match.
5. Vẫn ghi output mới.
6. Vẫn cleanup checkpoint khi hoàn tất.

Log đề xuất:

```text
Force retranslate: bỏ qua checkpoint/cache/TM cho lần chạy này.
```

Chính sách lưu sau khi force:

- Vẫn lưu TM mới sau khi dịch thành công.
- Không lưu cache trong lần force vì `use_cache=False`.

### Phase 1.4: Frontend

Thêm nút:

```text
Xóa TM dự án
```

Thêm checkbox:

```text
Dịch lại từ đầu
```

Tooltip:

```text
Bỏ qua checkpoint, cache và TM cho lần dịch này.
```

Yêu cầu UI:

- Không dùng inline `onclick`.
- Chỉ bind event một lần.
- Bấm xóa TM chỉ hiện một hộp xác nhận.
- Gửi `force_retranslate` trong payload khi dịch project.

### Phase 1.5: Test

Automated:

1. `POST /api/projects/<slug>/tm/clear`:
   - Xóa đúng TM của project.
   - Không đụng global TM.
   - Trả đúng số entry đã xóa.

2. `POST /api/projects/<slug>/translate`:
   - Payload `force_retranslate=true` vào config đúng.
   - Không truyền project TM vào use case.

3. `TranslationExecutor`:
   - Force mode không resume checkpoint cũ.
   - Force mode không đọc cache.
   - Force mode không gọi `translation_memory.find_match`.

Manual:

1. Dịch một file để tạo TM.
2. Xóa output trong `translated`.
3. Dịch lại bình thường: log có thể có TM hit.
4. Bật `Dịch lại từ đầu`: log phải báo force và gọi API.
5. Bấm `Xóa TM dự án`: `memory.json` còn tồn tại nhưng nội dung rỗng `{}`.

## Phase 2: Loại bỏ Translation Cache theo từng bước bóc tách

Trạng thái: **Được yêu cầu xây dựng chi tiết.**

Mục tiêu:

- Loại bỏ hoàn toàn Translation Cache.
- Sau mỗi bước, hệ thống vẫn chạy được.
- Frontend cũ không bị lỗi đột ngột.
- Không xóa file/service trước khi mọi reference đã được bóc tách.

Nguyên tắc:

1. Tắt đường ghi/đọc cache trước.
2. Giữ compatibility API trong giai đoạn chuyển tiếp.
3. Xóa UI sau khi backend đã ignore cache an toàn.
4. Xóa service cuối cùng, khi `rg` không còn reference runtime.

### Phase 2.0: Impact analysis trước khi sửa

Trước khi sửa function/class/method nào, chạy GitNexus impact theo quy định project.

Các symbol cần impact tối thiểu:

- `TranslationExecutor.__init__`
- `TranslationExecutor._translate_single_chunk`
- `robust_translate`
- `translate_text` trong `webui/routes/translation.py`
- `translate_project_file` trong `webui/routes/projects.py`
- `calculate_stats`
- `clear_cache`

Nếu impact trả HIGH hoặc CRITICAL, báo lại trước khi sửa.

### Phase 2.1: Vô hiệu hóa cache trong runtime, chưa xóa code

Mục tiêu:

- Từ bước này trở đi, mọi flow dịch không đọc/ghi Translation Cache.
- `services/cache_service.py` vẫn tồn tại để tránh gãy import trong lúc chuyển tiếp.

Thay đổi:

1. `backend/infrastructure/config/app_config_service.py`
   - `is_cache_enabled()` trả `False`.
   - Có thể giữ method để tương thích.

2. `webui/routes/projects.py`
   - Không tin payload `use_cache` từ client.
   - Set `config["use_cache"] = False` cho translate project.
   - Spellcheck nếu đang nhận `use_cache` cũng ignore field này.

3. `backend/application/use_cases/translate_text_use_case.py`
   - Không set `config["use_cache"]` từ config service, hoặc set cứng `False`.

4. `main.py`
   - CLI config `"use_cache"` set `False` hoặc deprecate option đọc từ config.

Verification sau Phase 2.1:

- Dịch project bình thường vẫn gọi API/TM/checkpoint đúng.
- Force retranslate vẫn bỏ qua TM/checkpoint.
- Không có log `Sử dụng cache`.
- `workspace/cache` không tăng file mới sau khi dịch.

Rollback:

- Khôi phục `is_cache_enabled()` và `config["use_cache"]` nếu cần.

### Phase 2.2: Bỏ cache read/write khỏi executor và translator

Mục tiêu:

- Runtime core không còn phụ thuộc `TranslationCache`.
- Chưa xóa `cache_service.py`.

Thay đổi:

1. `core/executor.py`
   - Xóa import `TranslationCache`.
   - Xóa `self.cache`.
   - Xóa nhánh `cache.get(...)` trong `_translate_single_chunk`.
   - Xóa stats `cached`.
   - Message hoàn tất không còn `cache_info`.

2. `plugins/translation/translator.py`
   - Xóa import type `TranslationCache`.
   - Xóa tham số `cache` khỏi `robust_translate`.
   - Xóa `cache.get_by_components(...)`.
   - Xóa `cache.set_by_components(...)`.
   - Giữ nguyên logic `_client_cache` cho GenAI/OpenAI client, vì đây là cache client trong RAM, không phải Translation Cache.

3. Cập nhật tất cả call site của `robust_translate`.
   - `core/executor.py`
   - `webui/routes/translation.py`
   - Bất kỳ test/caller nào khác tìm được bằng `rg "robust_translate\\("`.

Verification sau Phase 2.2:

- Import app không lỗi.
- Dịch trực tiếp `/api/translate-text` không lỗi chữ ký hàm.
- Dịch project vẫn chạy.
- `rg -n "TranslationCache|cache_service" core plugins webui/routes` không còn reference runtime, ngoại trừ file service còn tồn tại và docs nếu có.

Rollback:

- Khôi phục chữ ký `robust_translate` và `self.cache` từ commit trước nếu phát hiện lỗi.

### Phase 2.3: Bóc tách frontend khỏi cache setting

Mục tiêu:

- UI không còn gửi/hiển thị tùy chọn cache.
- Người dùng không còn nhầm `Xóa Cache` với `Xóa TM dự án`.

Thay đổi:

1. `webui/templates/partials/tab_config.html`
   - Xóa checkbox `Sử dụng Cache API`.
   - Xóa hoặc đổi khối “Dọn dẹp cache” thành trạng thái deprecated nếu cần.

2. `webui/static/js/api-client.js`
   - Không đọc `CACHE.ENABLE_CACHE` vào checkbox.
   - Không ghi `CACHE.ENABLE_CACHE` trong `saveAppConfig()`.
   - Nếu vẫn giữ nút xóa cache trong giai đoạn chuyển tiếp, message phải nói rõ cache đang deprecated.

3. `webui/static/js/translation-worker.js`
   - Không đọc `#use-cache`.
   - Không gửi `use_cache` trong payload translate/spellcheck.
   - Thêm `force_retranslate` ở các flow dịch project.

4. `webui/static/js/main.js`
   - Gỡ binding `btn-clear-cache` nếu nút bị xóa.

Verification sau Phase 2.3:

- Load trang không lỗi console do thiếu `#use-cache`.
- Save config không lỗi.
- Dịch project không gửi `use_cache`.
- Spellcheck không phụ thuộc `use_cache`.

Rollback:

- Re-add checkbox và JS block nếu UI bị lỗi, backend vẫn đang ignore cache nên an toàn.

### Phase 2.4: Compatibility API cho cache endpoint và stats

Mục tiêu:

- Frontend cũ hoặc tab đang mở không bị 500 nếu còn gọi `/api/cache/clear`.
- Header/stats không hiển thị cache sai.

Thay đổi:

1. `webui/routes/settings.py`
   - Biến `/api/cache/clear` thành no-op tạm thời:

```json
{
  "success": true,
  "deleted": 0,
  "message": "Translation Cache đã bị loại bỏ khỏi luồng dịch."
}
```

2. `webui/helpers.py`
   - `calculate_stats()` trả:

```json
{
  "cache_files": 0,
  "cache_size_mb": 0
}
```

   - Hoặc xóa field sau khi frontend đã không dùng nữa.

3. `webui/templates/partials/header.html`
   - Xóa hiển thị Cache trong header, hoặc đổi thành hidden/deprecated.

4. `webui/static/js/api-client.js`
   - Không cập nhật `cache-count/cache-size` nếu element đã xóa.

Verification sau Phase 2.4:

- `/api/stats` vẫn trả JSON hợp lệ.
- Header không hiện cache sai.
- Nếu gọi `/api/cache/clear` thủ công vẫn nhận response 200.

Rollback:

- Restore endpoint xóa file cache nếu cần.

### Phase 2.5: Dọn config và DTO/use case

Mục tiêu:

- Không còn field cache trong config/runtime DTO mới.
- Vẫn đọc config cũ mà không lỗi.

Thay đổi:

1. `config/app.ini`
   - Có thể giữ `[CACHE] ENABLE_CACHE = false` một release để tương thích.
   - Sau đó xóa section `[CACHE]`.

2. `backend/application/dto/translation_request.py`
   - Deprecate hoặc xóa field `use_cache`.
   - Nếu xóa, đảm bảo `from_dict()` ignore key cũ thay vì lỗi.

3. `backend/application/use_cases/translate_text_use_case.py`
   - Không set `config["use_cache"]`.

4. `main.py`
   - Không đọc `CACHE.ENABLE_CACHE`.

Verification sau Phase 2.5:

- API nhận payload cũ có `use_cache` vẫn không lỗi.
- CLI vẫn chạy.
- Tests DTO/use case được cập nhật.

Rollback:

- Giữ field deprecated lâu hơn nếu còn caller cũ.

### Phase 2.6: Xóa service cache cuối cùng

Chỉ thực hiện sau khi Phase 2.1 đến 2.5 đều pass.

Điều kiện trước khi xóa:

```bash
rg -n "TranslationCache|cache_service|use_cache|ENABLE_CACHE|/api/cache/clear|btn-clear-cache|cache_files|cache_size"
```

Kết quả mong muốn:

- Không còn reference runtime.
- Chỉ còn docs lịch sử hoặc plan đang làm.

Thay đổi:

1. Xóa:

```text
services/cache_service.py
```

2. Cập nhật:

```text
services/__init__.py
```

- Xóa `from .cache_service import TranslationCache`.
- Xóa `TranslationCache` khỏi `__all__`.

3. Tests:

- Xóa test import `TranslationCache`.
- Cập nhật test stats nếu còn assert `cache_files`.

4. Docs:

- `README.md`
- `docs/MANUAL.md`
- `docs/DEVELOPMENT.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`

Verification sau Phase 2.6:

- App import không lỗi.
- `pytest` pass.
- WebUI load không lỗi.
- Dịch project, force retranslate, spellcheck, direct translate đều hoạt động.

Rollback:

- Khôi phục `cache_service.py` và `services/__init__.py` nếu import vỡ.

### Phase 2.7: Dọn dữ liệu cache trên disk

Mục tiêu:

- Xóa dữ liệu cũ trong `workspace/cache` sau khi code không còn dùng.

Thay đổi:

- Có thể xóa thủ công thư mục/file cache cũ.
- Hoặc thêm migration một lần để dọn:

```text
workspace/cache/*.json
workspace/cache/*.json.gz
workspace/cache/*.pkl
workspace/cache/*.pkl.gz
```

Lưu ý:

- Đây là dữ liệu sinh ra, không cần giữ nếu Translation Cache đã bị loại bỏ.
- Không xóa `workspace/checkpoints`.
- Không xóa `assets/translation_memory`.

Verification:

- `workspace/cache` trống hoặc không còn tồn tại.
- App không tạo lại file cache khi dịch.

## Checklist reference cache hiện tại

Kết quả rà soát hiện có cho thấy các khu vực cần xử lý khi bóc cache:

### Runtime backend

- `main.py`
- `core/executor.py`
- `plugins/translation/translator.py`
- `webui/routes/projects.py`
- `webui/routes/translation.py`
- `webui/routes/settings.py`
- `webui/helpers.py`
- `backend/application/dto/translation_request.py`
- `backend/application/use_cases/translate_text_use_case.py`
- `backend/infrastructure/config/app_config_service.py`
- `services/__init__.py`
- `services/cache_service.py`

### Frontend

- `webui/templates/partials/tab_config.html`
- `webui/templates/partials/header.html`
- `webui/static/js/api-client.js`
- `webui/static/js/translation-worker.js`
- `webui/static/js/main.js`

### Tests/docs

- `tests/unit/test_helpers.py`
- `README.md`
- `docs/MANUAL.md`
- `docs/DEVELOPMENT.md`
- `ARCHITECTURE.md`
- `CHANGELOG.md`

### Không được nhầm với Translation Cache

Không xóa các cache khác không liên quan:

- `_client_cache` trong `plugins/translation/translator.py`: cache client SDK trong RAM.
- `_client_cache` trong `plugins/spellcheck/spellchecker.py`: cache client SDK trong RAM.
- Cache detect PDF trong `plugins/ocr/modules/pdf.py`.
- OCR image cache trong plugin OCR.

Các cache này khác mục tiêu và không nằm trong phase loại bỏ Translation Cache.

## Thứ tự triển khai đề xuất

1. Phase 1: Clear Project TM + Force Retranslate.
2. Phase 2.1: Disable runtime cache.
3. Phase 2.2: Remove cache from executor/translator.
4. Phase 2.3: Remove cache from UI request/config.
5. Phase 2.4: Compatibility endpoint/stats.
6. Phase 2.5: DTO/config cleanup.
7. Phase 2.6: Delete cache service.
8. Phase 2.7: Clean disk cache data.

Sau mỗi bước:

- Chạy test/syntax phù hợp.
- Chạy `rg` để kiểm tra reference còn lại.
- Manual test dịch project tối thiểu một file nhỏ.

## Verification tổng thể

Automated:

```bash
uv run pytest
```

Nếu môi trường thiếu dependency, ghi rõ dependency thiếu và chạy tối thiểu:

```bash
python3 -m py_compile <các file đã sửa>
```

Manual:

1. Mở WebUI.
2. Mở project có TM.
3. Dịch bình thường: TM vẫn hoạt động.
4. Bật `Dịch lại từ đầu`: gọi API lại, không TM/checkpoint/cache.
5. Xóa TM dự án: đúng project, không xóa global/default TM.
6. Sau khi loại cache: không còn UI cache, không còn file cache mới được tạo.
7. Direct translate vẫn gọi API và trả kết quả.
8. Spellcheck không lỗi vì thiếu `use_cache`.

## Tiêu chí hoàn thành

Phase 1 hoàn thành khi:

- Có nút `Xóa TM dự án`.
- Có checkbox `Dịch lại từ đầu`.
- Force mode bỏ qua checkpoint/cache/TM.
- Hệ thống vẫn hoạt động bình thường.

Phase 2 hoàn thành khi:

- Không còn đọc/ghi Translation Cache.
- Không còn UI cache gây nhầm lẫn.
- Không còn runtime import `TranslationCache`.
- `services/cache_service.py` đã được xóa an toàn.
- `workspace/cache` không còn được tạo lại khi dịch.
- Test và manual verification pass.

## Rủi ro và cách giảm rủi ro

### Rủi ro 1: Gãy import khi xóa service quá sớm

Giảm rủi ro:

- Chỉ xóa `services/cache_service.py` ở Phase 2.6.
- Trước đó luôn giữ file để compatibility.

### Rủi ro 2: Frontend cũ còn gửi `use_cache`

Giảm rủi ro:

- Backend ignore `use_cache` thay vì báo lỗi.
- `/api/cache/clear` no-op 200 trong giai đoạn chuyển tiếp.

### Rủi ro 3: Nhầm cache dịch với cache client/OCR

Giảm rủi ro:

- Chỉ remove `TranslationCache` file-based trong `services/cache_service.py`.
- Không đụng `_client_cache`, OCR PDF/image cache.

### Rủi ro 4: Tăng chi phí API

Giảm rủi ro:

- TM vẫn được giữ để tái sử dụng bản dịch theo project.
- Checkpoint vẫn được giữ để tránh dịch lại sau gián đoạn.
- Người dùng có `Dịch lại từ đầu` khi cần output mới.

## Khuyến nghị phê duyệt

Phê duyệt triển khai theo thứ tự:

1. Phase 1 ngay.
2. Phase 2.1 đến 2.4 trong cùng một nhánh nhỏ nếu có thể.
3. Phase 2.5 đến 2.7 sau khi Phase 2.1 đến 2.4 đã chạy ổn.

Không nên nhảy thẳng tới xóa `services/cache_service.py` khi các call site vẫn còn tồn tại.
