# Báo cáo Rà soát Chuyên sâu: Tính năng Review Model (QA Model) & Kế hoạch Tối ưu

**Dự án:** Novel-Translator  
**Ngày lập:** 2026-08-27  
**Phạm vi:** Rà soát kiến trúc, vòng đời cấu hình, luồng thực thi runtime, ảnh hưởng thực tế và phương án loại bỏ / tái cấu trúc trường `Review Model` (`qa_model`).  
**Tập tin mã nguồn liên quan:**
- [`webui/templates/partials/tab_config.html`](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/tab_config.html) (`#cfg-qa-model`, nhãn "Review Model")
- [`webui/static/js/api-client.js`](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/static/js/api-client.js) (`loadModels`, `saveAppConfig`)
- [`config/providers.json`](file:///Users/narga/Briefcase/Projects/Novel-Translator/config/providers.json) (`qa_model` trong từng provider)
- [`backend/infrastructure/config/app_config_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/backend/infrastructure/config/app_config_service.py) (`get_qa_model()`, `get_qa_model_or_none()`)
- [`backend/infrastructure/providers/provider_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/backend/infrastructure/providers/provider_service.py) (`get_active_qa_model()`, validate namespace)
- [`backend/infrastructure/providers/provider_resolver.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/backend/infrastructure/providers/provider_resolver.py) (`ProviderConfig.qa_model`, `validate_model`)
- [`backend/application/dto/translation_request.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/backend/application/dto/translation_request.py) (`qa_model`)
- [`core/executor.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/core/executor.py) (`_build_checkpoint_identity`)
- [`services/checkpoint_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/checkpoint_service.py) (`EXECUTION_IDENTITY_FIELDS`)
- [`plugins/translation/translator.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/plugins/translation/translator.py) (`robust_translate`, `_call_api`)

---

## 1. Bản chất & Cơ chế Hoạt động Hiện tại của "Review Model"

### 1.1. Nguồn gốc Lịch sử
- Trong các phiên bản trước **v7.0.0**, Novel-Translator từng có pipeline dịch đa giai đoạn (Multi-pass Pipeline):
  1. *Giai đoạn 1 (Translation Pass):* Dịch thô văn bản với `default_model`.
  2. *Giai đoạn 2 (QA / Review Pass):* Dùng `qa_model` (hoặc prompt kiểm tra chất lượng) để rà soát lỗi ngữ pháp, sót câu, sai lệch thuật ngữ.
- Từ **phiên bản v7.0.0**, hệ thống đã tinh giản và chuyển hoàn toàn sang **Single-pass Translation Pipeline** (`plugins/translation/translator.py::robust_translate`):
  1. Dịch 1 lần duy nhất bằng prompt chính có ngữ cảnh (`main prompt` + `previous_chunk_context`).
  2. Chuẩn hóa văn bản bằng thuật toán thuần Python regex (`normalizer`).
  3. Trả kết quả và lưu checkpoint.

### 1.2. Hiện trạng Thực thi trong Runtime (Runtime Execution)
- **Trong quá trình dịch thực tế:** Hàm `robust_translate()` **CHỈ thực hiện 1 lần gọi API duy nhất** cho mỗi chunk văn bản bằng `model_name` chính.
- Tham số `model_override` trong `_call_api` vẫn còn chú thích `(dùng cho QA/correction)` nhưng **hoàn toàn không có bất kỳ caller nào trong toàn bộ runtime kích hoạt lượt gọi thứ hai này**.
- **Kết luận:** Trong runtime hiện tại, **tính năng Review Model là một tính năng "thụ động" (dormant / dead runtime feature)**. Không có API call review riêng biệt nào được thực thi trong quá trình dịch.

---

## 2. Mặc định Nhận Model nào?

Thứ tự ưu tiên phân giải `qa_model` trong hệ thống:

```
┌─────────────────────────────────────────────────────────────────────────┐
│               THỨ TỰ PHÂN GIẢI MODEL CỦA REVIEW MODEL (QA)               │
├─────────────────────────────────────────────────────────────────────────┤
│ 1. config/providers.json: Đọc trường "qa_model" của provider active     │
│    (Ví dụ provider Gemini hiện tại lưu: "gemini-3.5-live-translate...") │
│                                   │                                     │
│                                   ▼ (Nếu rỗng "")                       │
│ 2. AppConfigService.get_qa_model(): Fallback về "default_model"         │
│    (Ví dụ: "gemini-3.6-flash")                                          │
│                                   │                                     │
│                                   ▼ (Nếu default_model cũng rỗng)       │
│ 3. Trả về chuỗi rỗng: "" (Không fallback cứng về gemini-3-flash nữa)    │
│                                   │                                     │
│                                   ▼ (Khi gọi qua Translation Route)     │
│ 4. webui/routes/translation.py: Gán worker_config["qa_model"] bằng      │
│    chính model người dùng đang chọn để dịch (model_from_req).           │
└─────────────────────────────────────────────────────────────────────────┘
```

- Trong file `config/providers.json` hiện tại:
  - Provider `gemini-default`: `"qa_model": "gemini-3.5-live-translate-preview"`.
  - Các provider OpenAI-compatible khác (`openrouter`, `groq`, `cloudflare`, `nvidia`, `mistral-ai`...): hầu hết không có trường `qa_model` hoặc để trống.
- Trên giao diện WebUI tab Cấu hình: Dropdown `#cfg-qa-model` tự động nạp danh sách model từ catalog và chọn model tương ứng với `providers.json`.

---

## 3. Có thể Tắt Mặc định hay Tự động Chạy Mặc định?

### 3.1. Về mặt Thực thi (Runtime Execution)
- **Nó KHÔNG tự động chạy bất kỳ request API review nào:** Người dùng không cần phải "tắt" để tránh tốn API, vì bản thân pipeline dịch đã không hề gọi nó.

### 3.2. Về mặt Cấu hình (Configuration & UI)
- **Backend:** Đã hỗ trợ nhận `qa_model = ""` (chuỗi rỗng) qua các endpoint:
  - `PUT /api/providers/<id>/models` (body `{qa_model: ""}`)
  - `POST /api/settings/save` (body `{qa_model: ""}`)
  Khi nhận chuỗi rỗng, backend sẽ xóa/clear trường `qa_model` trong `providers.json`.
- **Frontend WebUI:** Hiện tại hàm `ApiClient.renderModelOptions()` khi gán vào `#cfg-qa-model` **chưa có option `[— Tắt / Không dùng —]`** (không giống như dropdown `#summarize-model` có option `— Mặc định —`). Do đó, trên UI luôn hiển thị một model cụ thể, tạo cảm giác tính năng này bắt buộc phải bật.

---

## 4. Review Model Chạy bởi Trigger nào?

| Môi trường | Trigger | Hành vi thực tế |
| :--- | :--- | :--- |
| **Dịch từng Chunk (`robust_translate`)** | **Không có trigger** | Không gọi API review. Chỉ dịch 1 lần với model chính. |
| **Dịch toàn bộ Sách (`TranslationExecutor`)** | **Không có trigger** | Không có bước hậu kiểm sau khi dịch xong. |
| **Lưu Checkpoint (`_build_checkpoint_identity`)** | **Khi khởi tạo Task** | `qa_model` được đưa vào dictionary identity để băm metadata. |
| **Lưu Cấu hình (`saveAppConfig`)** | **Khi bấm nút "Lưu" ở Tab Cấu hình** | Đọc giá trị từ `#cfg-qa-model` và gửi lên `POST /api/settings/save`. |

---

## 5. Review Model Có Ảnh hưởng Gì?

### 5.1. Về Tài nguyên, Chi phí & Hiệu năng
- **Chi phí API / Quota / Token:** **0% ảnh hưởng**. Hoàn toàn không tốn thêm token hay request nào vì không có API call phát sinh.
- **Tốc độ Dịch (Latency):** **0% ảnh hưởng**. Quá trình dịch diễn ra với tốc độ thông thường của model chính.

### 5.2. Về Trải nghiệm Người dùng (UX Confusion)
- **Gây hiểu lầm nghiêm trọng:** Người dùng nhìn thấy mục "Review Model" với tooltip *"Dùng để rà soát & sửa lỗi bản dịch sau khi hoàn tất"* sẽ nghĩ rằng:
  1. Hệ thống đang gọi 2 model cho mỗi chunk $\rightarrow$ lo ngại tốn gấp đôi Quota (1500 RPD biến thành 750 chunks).
  2. Băn khoăn không biết model nào thực sự đang dịch chính, model nào đang review.
  3. Nếu chọn nhầm một model review đắt tiền hoặc hết quota, người dùng lo sợ phiên dịch sẽ bị lỗi.

### 5.3. Về Kiến trúc & Mã nguồn (Technical Debt)
- **Dead Configuration Parameter:** Tạo ra một chuỗi phụ thuộc không cần thiết xuyên suốt hệ thống:
  - `ProviderConfig.qa_model`
  - `ProviderResolver.validate_model(qa_model)`
  - `AppConfigService.get_qa_model()`, `get_qa_model_or_none()`
  - `TranslationRequest.qa_model`
  - `worker_config["qa_model"]`
  - `EXECUTION_IDENTITY_FIELDS` trong `checkpoint_service.py`
  - Hàng loạt unit test (`test_config_services.py`, `test_checkpoint_resolver.py`, `test_settings_routes.py`) phải duy trì test case cho một trường không còn sử dụng trong runtime.

---

## 6. Có Loại bỏ Được Không? Đánh giá Ảnh hưởng khi Loại bỏ

### 6.1. Khả năng Loại bỏ
**HOÀN TOÀN CÓ THỂ LOẠI BỎ 100%** mà không làm ảnh hưởng đến tính năng dịch cốt lõi của ứng dụng.

### 6.2. Đánh giá Ảnh hưởng Khi Loại bỏ (Impact Analysis)

#### A. Điểm Tích cực (Pros):
1. **Giao diện WebUI minh bạch, sạch sẽ:** Xóa bỏ trường chọn gây hiểu lầm trong Cấu hình nâng cao.
2. **Loại bỏ Technical Debt:** Cắt giảm mã nguồn thừa ở 10+ tập tin (Frontend JS, HTML template, Backend routes, DTOs, Services).
3. **Đơn giản hóa Quản lý Provider:** `providers.json` chỉ còn `default_model`, không còn phải validate chéo `qa_model` thuộc cùng namespace.

#### B. Đánh giá Khả năng Tương thích Ngược (Backward Compatibility):
- **Đối với Checkpoint cũ:**
  - Trong [`services/checkpoint_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/checkpoint_service.py#L53-L80):
    - `SOURCE_IDENTITY_FIELDS` (quyết định checkpoint có dùng tiếp được hay không) gồm: `project_file`, `project_slug`, `source_hash`, `chunker_version`, `chunk_size`, `prompt_hash`, `schema_version`.
    - `qa_model` chỉ nằm trong `EXECUTION_IDENTITY_FIELDS` (chỉ dùng để ghi nhận log cảnh báo drift).
    - Hàm so sánh `same_source_identity()` **chỉ so sánh `SOURCE_IDENTITY_FIELDS`**, do đó việc bỏ `qa_model` **KHÔNG LÀM HỎNG bất kỳ checkpoint dịch dở nào của người dùng**.
- **Đối với Cấu hình `providers.json` hiện hữu:**
  - Trường `"qa_model"` trong JSON có thể được xóa tự động thông qua script migration hoặc đơn giản là schema mới bỏ qua không đọc field này.

---

## 7. Phương án Đề xuất & Kế hoạch Xử lý (Remediation Plan)

Có 2 phương án xử lý:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           2 PHƯƠNG ÁN XỬ LÝ ĐỀ XUẤT                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [PHƯƠNG ÁN 1: LOẠI BỎ HOÀN TOÀN (KHUYẾN NGHỊ CAO THEO LAZY DEV)]           │
│  ├── Xóa triệt để field Review Model khỏi WebUI, Backend & Schema           │
│  ├── Tinh gọn codebase, không còn dead code & không còn gây hiểu lầm UX    │
│  └── Chi phí bảo trì = 0                                                    │
│                                                                             │
│  [PHƯƠNG ÁN 2: CHUYỂN THÀNH TÍNH NĂNG QA HẬU KIỂM TỰ CHỌN (OPT-IN)]        │
│  ├── Thêm Option "Tắt (Mặc định)" trên UI                                   │
│  ├── Chỉ chạy khi người dùng chủ động check "Kích hoạt QA Review"           │
│  └── Hiện thực hóa code gọi API Review thực sự sau khi hoàn tất dịch        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Kế hoạch Chi tiết cho Phương án 1 (Loại bỏ Triệt để):

#### Giai đoạn 1: Dọn dẹp Giao diện & Frontend
1. **`webui/templates/partials/tab_config.html`:** Xóa bỏ khối HTML `<div class="w-100 w-50-ns ph2 mb3">` chứa nhãn `Review Model` và `<select id="cfg-qa-model">`.
2. **`webui/static/js/api-client.js`:**
   - Xóa `cfg-qa-model` khỏi danh sách `loadModels()`.
   - Xóa `qa_model: qaModel` trong body của `saveAppConfig()`.

#### Giai đoạn 2: Tinh giản Backend & API Layer
1. **`webui/routes/settings.py` & `routes/translation.py`:**
   - Xóa xử lý `qa_model` trong payload của `POST /api/settings/save` và `PUT /api/providers/<id>/models`.
   - Xóa gán `worker_config["qa_model"]`.
2. **`backend/infrastructure/config/app_config_service.py`:**
   - Deprecate hoặc xóa `get_qa_model()` và `get_qa_model_or_none()`.
3. **`backend/infrastructure/providers/provider_service.py` & `provider_resolver.py`:**
   - Xóa `qa_model` khỏi danh sách trường cần validate namespace.
   - Xóa `get_active_qa_model()`.
4. **`backend/application/dto/translation_request.py`:**
   - Xóa field `qa_model` khỏi `TranslationRequest`.

#### Giai đoạn 3: Checkpoint & Schema Cleanup
1. **`core/executor.py`:** Xóa `"qa_model"` khỏi `_build_checkpoint_identity()`.
2. **`services/checkpoint_service.py`:** Xóa `"qa_model"` khỏi `EXECUTION_IDENTITY_FIELDS`.
3. **`config/providers.json`:** Dọn dẹp trường `"qa_model"` khỏi các provider object.

---

## 8. Bảng Tổng kết Đối chiếu

| Câu hỏi Rà soát | Kết quả Phân tích & Trả lời |
| :--- | :--- |
| **Hoạt động như thế nào?** | Là trường cấu hình thừa (dormant config) còn sót lại từ kiến trúc đa bước cũ. **Không chạy bất kỳ logic gọi API nào trong runtime dịch hiện tại.** |
| **Mặc định nhận model nào?** | Nhận từ `"qa_model"` trong `providers.json` (Gemini đang lưu `gemini-3.5-live-translate-preview`), nếu rỗng sẽ fallback về `default_model` (`gemini-3.6-flash`). |
| **Có thể tắt mặc định hay tự động chạy?** | **Không tự động chạy ngầm**, hoàn toàn không tốn API call. Tuy nhiên trên WebUI chưa có nút chọn `[Tắt]` rõ ràng. |
| **Chạy bởi trigger nào?** | Không có trigger runtime dịch. Chỉ được đọc khi lưu cấu hình và băm metadata checkpoint. |
| **Có ảnh hưởng gì?** | Không tốn token/tiền/latency, nhưng **gây hiểu lầm UX nghiêm trọng** và tạo technical debt trong mã nguồn. |
| **Có loại bỏ được không?** | **Hoàn toàn loại bỏ được 100%**. |
| **Loại bỏ ảnh hưởng ra sao?** | Giúp UI trong sáng, codebase tinh gọn, không làm hỏng bất kỳ checkpoint cũ nào của người dùng. |
