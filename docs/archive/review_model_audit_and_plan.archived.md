# Báo cáo Rà soát Chuyên sâu: Tính năng Review Model (QA Model) & Kế hoạch Loại bỏ Triệt để

**Dự án:** Novel-Translator  
**Ngày lập:** 2026-08-27 — Cập nhật quyết định: 2026-08-28 — v2: 2026-08-28 — v3: 2026-08-28 — v4 (tham chiếu triển khai): 2026-08-28  
**Trạng thái:** ✅ ĐÃ CHỐT (v4) — Sẵn sàng triển khai trong 1 PR. Mỗi mục chỉnh sửa có tham chiếu `file:line` cụ thể để tra cứu nhanh.  
**Quyết định:** Phương án 1 — Xóa triệt để. Phương án 2 (opt-in QA) bị loại.  
**Phạm vi:** Rà soát kiến trúc, vòng đời cấu hình, luồng thực thi runtime, ảnh hưởng thực tế và kế hoạch xóa sạch trường `Review Model` (`qa_model`) + tham số liên quan `model_override`.

> **Ý kiến reviewer (Muse Spark — ponytail: full):** Đồng ý 100% với báo cáo gốc. `qa_model` là dead config từ pipeline 2-pass cũ, runtime hiện tại (`robust_translate`) chỉ gọi 1 lần/chunk bằng `model_name` chính, không có caller nào kích hoạt `model_override`/review pass. Giữ lại chỉ gây hiểu lầm UX (người dùng tưởng tốn x2 quota), phình `providers.json`, và kéo theo ~100 vết `qa_model`/`QA_MODEL`/`cfg-qa-model` khắp frontend → backend → DTO → checkpoint → test. Lazy fix đúng là **xóa sạch một chỗ, gọn hơn vá từng caller**. Không có lý do giữ lại hay chuyển thành opt-in khi chưa có nhu cầu QA pass thực sự — YAGNI. Khi nào cần QA thật thì thiết kế lại từ đầu, không tái dùng field thụ động này.

---

## §0 Tham chiếu nhanh (Quick Reference)

Tất cả tham chiếu `file:line` dưới đây trỏ tới `main` tại commit thời điểm viết kế hoạch. Sau khi sửa, dòng sẽ lệch — dùng symbol/function name làm anchor chính, line là gợi ý.

| File | Anchor (function/line) | Hành động |
|---|---|---|
| `webui/templates/partials/tab_config.html` | L160-171 (khối `Review Model`) | Xóa khối HTML |
| `webui/static/js/api-client.js` | `loadModels()` L92-98, `applyModelFilters()` L184-188, `saveAppConfig()` L334-344 | Bỏ `cfg-qa-model` |
| `config/providers.json` | provider `gemini-default` L20 | Xóa key `"qa_model"` |
| `backend/infrastructure/config/app_config_service.py` | `get_qa_model()` L188-206, `get_qa_model_or_none()` L206-224 | Xóa method |
| `backend/infrastructure/providers/provider_service.py` | `_validate_providers_data()` L132, L142, L151; `update_provider()` L329; `get_active_qa_model()` L428-438; **`save_providers()` L162-197 (CHÈN NORMALIZE)** | Xóa field + chèn normalize |
| `backend/infrastructure/providers/provider_resolver.py` | `ResolvedProvider` L36-50 (field `qa_model` L44, `get_masked_info` L67); `resolve_from_document()` L167; `_fetch_models()` L258-272 | Xóa `qa_model` |
| `backend/application/dto/translation_request.py` | L27 (docstring), L42 (field), L60 (`to_config`), L87 (`from_dict`) | Xóa `qa_model` |
| `backend/application/use_cases/translate_text_use_case.py` | `from_services()` L143 | Xóa dòng gán |
| `webui/routes/settings.py` | `list_providers()` L619; **`update_provider_models()` L689-763 (REJECT đầu hàm)**; `save_settings_transaction()` L838-981 (REJECT đầu hàm) | Xóa + reject |
| `webui/routes/projects.py` | L1646, L1795, L1910, L2000, L2228, L2600, L2670 | Xóa `worker_config["qa_model"]` |
| `webui/routes/translation.py` | L93, L303 | Xóa `worker_config["qa_model"]` |
| `scripts/migrate_providers_v2.py` | L12, L159, L180, L187, L223, L287-289 | Dọn logic QA |
| `plugins/translation/translator.py` | `_call_api()` L67-96 (param `model_override` L72, docstring L84, `model_name = ...` L96) | Xóa `model_override` |
| `core/executor.py` | `_build_checkpoint_identity()` L114 | Xóa key |
| `services/checkpoint_service.py` | `EXECUTION_IDENTITY_FIELDS` L57-58 | Xóa `"qa_model"` |
| `tests/unit/test_provider_service_normalize.py` | **MỚI (v3)** | File mới |
| `docs/ROADMAP.md` | L9, L13, L277 (và mọi dòng có `qa_model`) | Dọn sạch |
| `CHANGELOG.md` | toàn file | **GIỮ NGUYÊN** (lịch sử) |

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
- **Trong quá trình dịch thực tế:** Hàm `robust_translate()` (`plugins/translation/translator.py:208-261`) **CHỈ thực hiện 1 lần gọi API duy nhất** cho mỗi chunk văn bản bằng `model_name` chính (gọi `_call_api(original_chunk, main_prompt, api_manager, config_params)` — L243-245, không truyền `model_override`).
- Tham số `model_override` trong `_call_api(text, prompt, api_manager, config, model_override=None)` (signature L67-73, dòng `model_name = model_override or config.get("model_name", "")` L96) **hoàn toàn không có caller** (grep `model_override` chỉ ra 3 hits đều nằm trong `translator.py` định nghĩa). Đây là dead parameter thứ hai, xóa cùng đợt.
- **Kết luận:** Trong runtime hiện tại, **tính năng Review Model là dormant / dead runtime feature**. Không có API call review riêng biệt nào được thực thi.

---

## 2. Mặc định Nhận Model nào?

Thứ tự ưu tiên phân giải `qa_model` (sẽ bị xóa toàn bộ):

```
┌─────────────────────────────────────────────────────────────────────────┐
│               THỨ TỰ PHÂN GIẢI MODEL CỦA REVIEW MODEL (QA)               │
├─────────────────────────────────────────────────────────────────────────┤
│ 1. config/providers.json: trường "qa_model" của provider active         │
│ 2. AppConfigService.get_qa_model(): fallback "default_model"            │
│ 3. Chuỗi rỗng "" khi cả hai đều rỗng                                     │
│ 4. webui/routes/translation.py: worker_config["qa_model"] = model_from_req│
└─────────────────────────────────────────────────────────────────────────┘
```

`config/providers.json` hiện tại:
- `gemini-default` (L19-20): `"default_model": "gemini-3.6-flash"`, `"qa_model": "gemini-3.5-live-translate-preview"`.
- OpenAI-compatible khác (`openrouter`, `groq`, `cloudflare`, `nvidia`, `mistral-ai`, `opencode-2`, `9router-2`, `github`, `freemodel`, `stepfun`): không có `qa_model`.

---

## 3. Có thể Tắt Mặc định hay Tự động Chạy?

### 3.1. Runtime
- **Không tự động chạy** bất kỳ request API review nào.

### 3.2. Cấu hình & UI
- Backend đã hỗ trợ `qa_model = ""` qua `PUT /api/providers/<id>/models` (`webui/routes/settings.py:689-763`) và `POST /api/settings/save` (`webui/routes/settings.py:838-981`).
- Frontend (`webui/static/js/api-client.js`) chưa có option `[— Tắt —]` cho `#cfg-qa-model`.

---

## 4. Review Model Chạy bởi Trigger nào?

| Môi trường | Trigger | Hành vi thực tế |
| :--- | :--- | :--- |
| `robust_translate` (`plugins/translation/translator.py:208`) | Không có | 1 lần API call duy nhất với `model_name` |
| `TranslationExecutor` (`core/executor.py:97-118`) | Không có | Không có bước hậu kiểm |
| `_build_checkpoint_identity` (`core/executor.py:97-118`) | Khởi tạo Task | `qa_model` đưa vào `EXECUTION_IDENTITY_FIELDS` |
| `saveAppConfig` (`webui/static/js/api-client.js:330-384`) | Nút "Lưu" | Gửi `qa_model` lên `POST /api/settings/save` |

---

## 5. Review Model Có Ảnh hưởng Gì?

### 5.1. Tài nguyên & Hiệu năng
- **0% ảnh hưởng** (token/quota/latency) — không có API call review nào phát sinh.

### 5.2. UX
- Gây hiểu lầm nghiêm trọng: người dùng tưởng hệ thống gọi 2 model, tốn gấp đôi quota; không rõ model nào dịch/review.

### 5.3. Technical Debt (xem §0 để có tham chiếu file:line)
- `ResolvedProvider.qa_model` + `get_masked_info()` → JSON output có field thừa.
- `ProviderResolver.validate_model(qa_model)` + `list_models()` trả `errors[].field=qa_model`.
- `ProviderService.get_active_qa_model()` + `_validate_providers_data` loop `("default_model", "qa_model")`.
- `AppConfigService.get_qa_model()`, `get_qa_model_or_none()`.
- `TranslationRequest.qa_model` + `to_config()` + `from_dict()`.
- `TranslateTextUseCase.from_services()` gán `config["qa_model"]`.
- `worker_config["qa_model"]` trong `webui/routes/projects.py:1646, 2670` và `webui/routes/translation.py:93`.
- `EXECUTION_IDENTITY_FIELDS` trong `services/checkpoint_service.py:58`.
- `qa_model` field trong `config/providers.json:20`.
- `model_override` param trong `plugins/translation/translator.py:72`.
- 10+ file unit test (xem §7.3 GĐ4).

---

## 6. Có Loại bỏ Được Không?

### 6.1. Khả năng Loại bỏ
**HOÀN TOÀN CÓ THỂ LOẠI BỎ 100%** mà không ảnh hưởng tính năng dịch cốt lõi.

### 6.2. Backward Compatibility

**Checkpoint cũ** (an toàn — đã phân tích):
- `services/checkpoint_service.py:53-56` `SOURCE_IDENTITY_FIELDS` (quyết định checkpoint còn dùng được): `project_file`, `project_slug`, `source_hash`, `chunker_version`, `chunk_size`, `prompt_hash`, `schema_version`.
- `qa_model` chỉ nằm trong `EXECUTION_IDENTITY_FIELDS` (L57-58) — chỉ log drift, không chặn resume.
- `same_source_identity()` (`services/checkpoint_service.py:73-74`) chỉ so sánh `SOURCE_IDENTITY_FIELDS` → bỏ `qa_model` **không hỏng checkpoint cũ**.
- Checkpoint SQLite có `ident_qa_model` trong `metadata` → code mới bỏ qua (thiếu key thì `execution_drift` so sánh `""` vs `""`).

**`providers.json` hiện hữu** (⚠️ đã chốt normalize tập trung tại `save_providers()`):
- Giả định "lần save sau tự xóa field" **SAI** nếu giữ logic merge `{**p, **model_kwargs}` ở `webui/routes/settings.py:733` và `webui/routes/settings.py:751` — khi `model_kwargs` không còn `qa_model`, field cũ vẫn spread và ghi lại.
- **Chốt v3:** Normalize tập trung tại `ProviderService.save_providers()` (`backend/infrastructure/providers/provider_service.py:162-197`), chèn **ngay trước** `self._validate_providers_data(data)` (L170). Một chỗ duy nhất, bao phủ mọi nhánh (non-ETag, ETag qua `save_providers_with_etag()` gọi `save_providers()` bên trong).

---

## 7. Quyết định & Kế hoạch Loại bỏ Triệt để (ĐÃ CHỐT — v4)

> **Quyết định:** Loại bỏ hoàn toàn. Mục tiêu **zero residue**: `rg` cho `qa_model|QA_MODEL|cfg-qa-model|Review Model|model_override` trên mã nguồn & tài liệu hiện hành trả về 0. **Ngoại lệ duy nhất:** `CHANGELOG.md` (lịch sử). Báo cáo này sẽ được archive (`docs/archive/`) hoặc xóa sau khi PR merge — xem §7.6 bước 3.

### 7.1. Nguyên tắc thực hiện (v4)
1. **Xóa sạch, không deprecate nửa vời** — field, method, validate, UI, DTO, test, `model_override` — không để shim/alias.
2. **Không rewrite git history.** `CHANGELOG.md` giữ nguyên. `docs/ROADMAP.md` và mọi `docs/*` hiện hành dọn sạch (kể cả bullet lịch sử v8.29.x).
3. **Normalization tập trung tại `ProviderService.save_providers()`** (`backend/infrastructure/providers/provider_service.py:162-197`) — một chỗ duy nhất, trước `_validate_providers_data(data)`. Bao phủ cả nhánh ETag lẫn non-ETag.
4. **Reject thay vì silent ignore ở HTTP boundary:** `POST /api/settings/save`, `PUT /api/providers/<id>/models` có `qa_model` → `400 unknown field`. DTO `from_dict` bỏ qua (không phải HTTP boundary).
5. **Giữ `scripts/migrate_providers_v2.py`** (v3 chốt) — vẫn là migration/rollback tool hiện hành, integration test [`tests/integration/test_v8_29_0_real_flask_integration.py:281`](file:///Users/narga/Briefcase/Projects/Novel-Translator/tests/integration/test_v8_29_0_real_flask_integration.py:281) gọi `--dry-run`. Chỉ dọn logic QA bên trong.
6. **Một PR, tinh gọn.**
7. **Thứ tự an toàn:** Frontend → Backend API (reject + normalize) → Domain/DTO → Checkpoint/Schema → Config → `model_override` → Tests → Docs.

### 7.2. Definition of Done (v4)
- [ ] `rg -n -i 'qa_model|QA_MODEL|cfg-qa-model|Review Model|model_override' webui backend core services plugins config scripts tests docs README.md -g '!CHANGELOG.md'` trả 0 (xem §9 lệnh chính xác, dùng `rg -g` để loại trừ path đầy đủ; báo cáo này đã archive trước khi verify — §7.6 bước 3).
- [ ] `jq '.providers[] | has("qa_model")' config/providers.json` → tất cả `false`.
- [ ] `ProviderService.save_providers()` chèn normalize `p.pop("qa_model", None)` tại `backend/infrastructure/providers/provider_service.py:170` (trước `_validate_providers_data`). Có unit test xác nhận (cả nhánh ETag/non-ETag).
- [ ] `pytest -q` pass — đã cập nhật **đủ 11 file test** (10 v2 + 1 MỚI v3).
- [ ] Smoke API: `GET /api/providers` không trả `qa_model`; `PUT /api/providers/<id>/models {"qa_model": "x"}` (cả 2 nhánh) → 400; `POST /api/settings/save {"qa_model": "x"}` → 400; `TranslationRequest.from_dict({"qa_model": "x"})` → `to_config()` không có key `qa_model`.
- [ ] Checkpoint cũ resume được (manual).
- [ ] `migrate_providers_v2.py --dry-run` chạy OK với config đã dọn; integration test `test_migration_dry_run_parses_real_config` pass.

### 7.3. Kế hoạch chi tiết — 4 Giai đoạn (file:line cụ thể — v4)

#### Giai đoạn 1: Frontend (WebUI)
- [ ] **`webui/templates/partials/tab_config.html` (L158-171):** Xóa khối `<div class="w-100 w-50-ns ph2 mb3">` chứa `<label>Review Model</label>`, tooltip, `{% set qa_model_val ... %}` và `<select id="cfg-qa-model" name="MODEL.QA_MODEL">`. Layout còn lại (Context Radius, Temperature, API Delay, Polling, Antilag) tự co giãn.
- [ ] **`webui/static/js/api-client.js`:**
  - `loadModels()` L92-98: Xóa `'cfg-qa-model'` khỏi `['cfg-qa-model', 'summarize-model', ...]` và khỏi branch `if (sid === 'summarize-model')` fallback.
  - `applyModelFilters()` L184-188: Xóa block `const qaSel = document.getElementById('cfg-qa-model')...`.
  - `saveAppConfig()` L334-344: Xóa `const qaModel = document.getElementById('cfg-qa-model').value;` (L338) và `qa_model: qaModel,` (L344) trong `body`. Cập nhật comment L335-336 (không còn `+ qa_model`).
  - `loadAppConfig()` L290-328: nếu có tham chiếu `qa_model` (hiện không) — xóa.

#### Giai đoạn 2: Backend & API Layer (reject + normalize)
- [ ] **`backend/infrastructure/config/app_config_service.py`:**
  - Xóa `get_qa_model()` L188-206 (cả docstring L189-205) và `get_qa_model_or_none()` L206-224 (cả docstring L207-223).
  - Verify: caller duy nhất còn lại là `translate_text_use_case.py:143` (sẽ xóa ở GĐ2 khác).
- [ ] **`backend/infrastructure/providers/provider_service.py` — quan trọng nhất:**
  - `_validate_providers_data()` L132: `for field in ("default_model", "qa_model"):` → `for field in ("default_model",):`.
  - L142 whitelist: `("api_key", "base_url", "gateway_api_key", "credential_mode", "default_model", "qa_model")` → bỏ `"qa_model"`.
  - L151: `for field in ("default_model", "qa_model"):` → `for field in ("default_model",):`.
  - `update_provider()` L329: `for key in ("name", "base_url", "default_model", "qa_model", "credential_mode"):` → bỏ `"qa_model"` → `("name", "base_url", "default_model", "credential_mode")`.
  - Xóa method `get_active_qa_model()` L428-438 (cả docstring L429-433).
  - **`save_providers()` L162-197 — CHÈN NORMALIZE TẬP TRUNG (v3, quan trọng nhất):**
    ```python
    def save_providers(self, data: Dict[str, Any]) -> None:
        """Ghi providers.json bằng atomic write + validate."""
        # v4 (zero-residue): chuẩn hóa tập trung — xóa field legacy
        # 'qa_model' khỏi mọi provider trước khi validate/ghi. Áp dụng
        # cho cả nhánh non-ETag (update_provider_models) và ETag
        # (save_providers_with_etag gọi save_providers bên trong).
        for p in data.get("providers", []):
            p.pop("qa_model", None)
        import shutil
        self._providers_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._providers_file.with_suffix(".json.tmp")
        # ... phần còn lại giữ nguyên ...
    ```
    Vị trí chèn: ngay sau signature L162, trước block `import shutil` (L164). 2 dòng normalize + 4 dòng comment.
  - `_is_model_valid_for_type` giữ nguyên.
- [ ] **`backend/infrastructure/providers/provider_resolver.py`:**
  - `ResolvedProvider` dataclass L36-50: Xóa field `qa_model: str` (L44).
  - `get_masked_info()` L60-84: Xóa entry `"qa_model": self.qa_model,` (L67).
  - `resolve_from_document()` L167: Xóa `qa_model=str(provider_data.get("qa_model", "") or "").strip(),`.
  - `_fetch_models()` / `list_models()` L258-272: Xóa branch `if provider.qa_model: valid, err = self.validate_model(...); if not valid: errors.append({"field": "qa_model", "message": err}); qa_invalid = True` (L258-262). Xóa `qa_invalid` (L252). Đổi return `"qa_model": "" if qa_invalid else provider.qa_model,` (L272) → xóa key `qa_model` khỏi dict trả về.
  - `validate_model` L176-212 giữ nguyên.
- [ ] **`backend/application/dto/translation_request.py`:**
  - Docstring L27: Xóa dòng `qa_model: Tên QA model`.
  - Field L42: Xóa `qa_model: str = ""`.
  - `to_config()` L60: Xóa dòng `"qa_model": self.qa_model,`.
  - `from_dict()` L87: Xóa `qa_model=data.get("qa_model", data.get("model", "")),`.
- [ ] **`backend/application/use_cases/translate_text_use_case.py:143`:**
  - Xóa dòng `config["qa_model"] = config_service.get_qa_model()` trong `from_services()`.
- [ ] **`webui/routes/settings.py` — REJECT (HTTP boundary):**
  - `list_providers()` L619: Xóa `"qa_model": p.get("qa_model", ""),` khỏi `item` dict.
  - **`update_provider_models()` L689-763 — REJECT ở đầu hàm, TRƯỚC cả resolve (L702) và cả nhánh ETag (L731-738) lẫn non-ETag (L744-757):**
    ```python
    @settings_bp.route("/api/providers/<provider_id>/models", methods=["PUT"])
    @handle_route_errors
    def update_provider_models(provider_id):
        """PUT model cho provider. Validate namespace trước khi ghi (R1, R4).

        Body: {default_model?: str}
        - Cả hai optional; nếu gửi phải pass provider type validate
        - default_model="" có nghĩa "không có model" (sentinel: key phải tồn tại trong body)
        """
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        data = request.json or {}
        # v4 (zero-residue): reject qa_model ngay đầu hàm, trước cả resolve
        # và cả 2 nhánh ETag/non-ETag. Defense-in-depth cùng save_providers().
        if "qa_model" in data:
            return jsonify({"error": "unknown field: qa_model"}), 400
        resolver = ProviderConfigResolver()
        # ... phần còn lại: bỏ qa_model khỏi for loop L711, L720 ...
    ```
    Sau khi sửa:
    - L711 `for field in ("default_model", "qa_model"):` → `for field in ("default_model",):`.
    - L745-747 comment: bỏ nhắc `qa_model` (viết lại: "không dùng update_provider vì method đó intentionally bỏ qua giá trị rỗng để tránh xoá credential. Model endpoint cần sentinel khác: default_model='' là clear hợp lệ.").
    - KHÔNG thêm normalize ở route — `save_providers()` đã làm.
  - **`save_settings_transaction()` L838-981 — REJECT ở đầu hàm:**
    ```python
    @settings_bp.route("/api/settings/save", methods=["POST"])
    @handle_route_errors
    def save_settings_transaction():
        """D1: Transaction endpoint lưu app config + provider model cùng lúc.

        Body: {
            provider_id?: str,                    # active provider nếu None
            default_model?: str,
            app_config?: {section: {key: value}}  # dùng apply_values
        }
        """
        from backend.infrastructure.providers.provider_resolver import (
            ProviderConfigResolver,
        )
        from backend.infrastructure.providers.provider_service import ProviderService
        from backend.infrastructure.config.app_config_service import AppConfigService

        data = request.json or {}
        # v4 (zero-residue): reject qa_model ngay đầu hàm.
        if "qa_model" in data:
            return jsonify({"error": "unknown field: qa_model"}), 400
        provider_id = data.get("provider_id")
        # ... phần còn lại: bỏ qa_model khỏi L877-895, L888, L962-963 ...
    ```
    Sau khi sửa:
    - L846 docstring: xóa `qa_model?: str,`.
    - L877-895 block `if "qa_model" in data or "default_model" in data:` → `if "default_model" in data:`.
    - L888 `for field in ("default_model", "qa_model"):` → `for field in ("default_model",):`.
    - L962-963 `for field in ("default_model", "qa_model"): if field in data: model_kwargs[field] = data[field] or ""` → `if "default_model" in data: model_kwargs["default_model"] = data["default_model"] or ""`.
    - L969-970 comment: bỏ nhắc `qa_model`.
- [ ] **`webui/routes/projects.py`:**
  - L1646: Xóa `worker_config["qa_model"] = model_from_req`.
  - L1795: Xóa `"qa_model": data.get("model", ""),`.
  - L1910: Xóa `"qa_model": data.get("model", ""),`.
  - L2000: Xóa `"qa_model": saved_identity.get("qa_model", ""),`.
  - L2228: Xóa `"qa_model": saved_identity.get("qa_model", ""),`.
  - L2600: Xóa `"qa_model": data.get("model", ""),`.
  - L2670: Xóa `worker_config["qa_model"] = model_from_req`.
- [ ] **`webui/routes/translation.py`:**
  - L93: Xóa `worker_config["qa_model"] = model_from_req`.
  - L303: Xóa `"qa_model": model,` khỏi response payload.

#### Giai đoạn 3: Checkpoint, Schema, Config & `model_override` & `migrate_providers_v2.py`
- [ ] **`core/executor.py:114`:** Xóa dòng `"qa_model": self.config.get("qa_model", ""),` khỏi `_build_checkpoint_identity()`.
- [ ] **`services/checkpoint_service.py:58`:** Xóa `"qa_model"` khỏi `EXECUTION_IDENTITY_FIELDS = ("provider_kind", "provider_id", "base_url", "model", "qa_model", "credential_mode")` → còn 5 fields.
- [ ] **`config/providers.json:20`:** Xóa key `"qa_model": "gemini-3.5-live-translate-preview"` (và mọi provider nếu có). File sau dọn chỉ còn `default_model`. Có thể one-off `jq 'walk(if type=="object" then del(.qa_model) else . end)' config/providers.json` (xem §9) hoặc để `save_providers()` normalize ở lần save đầu.
- [ ] **`scripts/migrate_providers_v2.py` — DỌN LOGIC QA, GIỮ SCRIPT (v3 chốt):**
  - L12 docstring: "5. Loại bỏ [MODEL] MODEL và QA_MODEL..." → "5. Loại bỏ [MODEL] MODEL...".
  - L159: `if k not in ("model", "MODEL", "MODEL.MODEL", "MODEL.QA_MODEL")` → bỏ `"MODEL.QA_MODEL"` → `if k not in ("model", "MODEL", "MODEL.MODEL")`.
  - L180: Xóa `new_provider.setdefault("qa_model", "")` (nhánh gemini).
  - L187: Xóa `new_provider.setdefault("qa_model", "")` (nhánh openai).
  - L223: `for opt in ("MODEL", "QA_MODEL"):` → `for opt in ("MODEL",):`.
  - L287-289: log `" - Provider: id=%s type=%s name=%s default_model=%r qa_model=%r"` → `" - Provider: id=%s type=%s name=%s default_model=%r"`, và bỏ `p.get("qa_model", "")` khỏi args.
  - Verify integration test [`tests/integration/test_v8_29_0_real_flask_integration.py:281-294`](file:///Users/narga/Briefcase/Projects/Novel-Translator/tests/integration/test_v8_29_0_real_flask_integration.py:281) còn pass (assert `default_model='` count ≥ 11, không nhắc `qa_model`).
- [ ] **`plugins/translation/translator.py` — xóa `model_override` (đã chốt):**
  - L67-73 signature `_call_api`: xóa param `model_override: Optional[str] = None,`.
  - L84 docstring: xóa dòng `model_override (Optional[str]): Model ghi đè (dùng cho QA/correction)`.
  - L96: `model_name = model_override or config.get("model_name", "")` → `model_name = config.get("model_name", "")`.
  - Caller `robust_translate` L243-245 đã không truyền `model_override` → an toàn.

#### Giai đoạn 4: Tests & Tài liệu hiện hành (11 file test — v4)
- [ ] **Tests đã cập nhật (10 file từ v2):**
  - `tests/unit/test_frontend_logic.py` (L141, L173, L185): Xóa mock `'cfg-qa-model'`, xóa `assert "qa_model" in body`.
  - `tests/unit/test_migrate_providers_v2.py` (L56, L99, L150, L219): Xóa `QA_MODEL = step-3.5-flash`, `assert "qa_model" in gemini`, payload `[MODEL] QA_MODEL`. Sửa test `test_migration_*` để assert `default_model=` thay vì `qa_model=`.
  - `tests/unit/test_model_fallback_removed.py` (bổ sung v2): Xóa assert `TranslationRequest.qa_model`. Thêm test: `from_dict({"qa_model": "x", "text": "hi"})` → `to_config()` không có key `qa_model` (xác nhận DTO bỏ qua).
  - `tests/unit/test_app_config_b1_b2.py` (bổ sung v2): Xóa test `get_qa_model` / `get_qa_model_or_none`.
  - `tests/unit/test_provider_resolver.py` (bổ sung v2): Xóa test `ResolvedProvider.qa_model`, `list_models()["qa_model"]`, `errors[]` field `qa_model`. Cập nhật `get_masked_info` expectation.
  - `tests/unit/test_source_identity_resume.py` (bổ sung v2): Xóa test `EXECUTION_IDENTITY_FIELDS` chứa `qa_model`, cập nhật `execution_drift(["qa_model"])` expectations, xóa `ident_qa_model` trong fixture identity.
  - `tests/unit/test_settings_endpoints.py` (bổ sung v2): Xóa test `PUT /api/providers/<id>/models` với `qa_model`, `POST /api/settings/save` với `qa_model`. Thêm test mới: assert `400 {"error": "unknown field: qa_model"}` khi gửi `qa_model` (cả 2 nhánh có/không `If-Match`).
  - `tests/unit/test_config_services.py`: Xóa test `get_qa_model` / `get_qa_model_or_none` (nếu còn).
  - `tests/unit/test_checkpoint_resolver.py`: Xóa test `EXECUTION_IDENTITY_FIELDS` chứa `qa_model`.
  - `tests/unit/test_settings_routes.py`: Xóa test `PUT /api/providers/<id>/models` với `qa_model`, `POST /api/settings/save` với `qa_model`. Thêm test reject 400.
  - **`tests/unit/test_provider_service_normalize.py` — MỚI (v3):**
    ```python
    # Test ProviderService.save_providers() xóa qa_model khỏi file ghi
    # Bao phủ cả nhánh ETag (save_providers_with_etag) lẫn non-ETag.
    import json
    import tempfile
    from pathlib import Path
    from backend.infrastructure.providers.provider_service import ProviderService

    def _setup_providers_file(tmp_path: Path, providers: list) -> Path:
        cfg_dir = tmp_path / "config"
        cfg_dir.mkdir()
        (cfg_dir / "providers.json").write_text(
            json.dumps({"version": 2, "active_id": "x", "providers": providers},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return cfg_dir

    def test_save_providers_normalize_qa_model_non_etag(tmp_path):
        cfg_dir = _setup_providers_file(tmp_path, [
            {"id": "x", "type": "gemini", "name": "X", "default_model": "gemini-2.0-flash",
             "api_keys": ["k"], "qa_model": "gemini-old-qa"},
        ])
        svc = ProviderService(config_dir=cfg_dir)
        data = svc.load_providers()
        data["providers"][0]["default_model"] = "gemini-2.5-flash"
        svc.save_providers(data)
        out = json.loads((cfg_dir / "providers.json").read_text())
        assert "qa_model" not in out["providers"][0]
        assert out["providers"][0]["default_model"] == "gemini-2.5-flash"

    def test_save_providers_normalize_qa_model_etag(tmp_path):
        cfg_dir = _setup_providers_file(tmp_path, [
            {"id": "x", "type": "gemini", "name": "X", "default_model": "gemini-2.0-flash",
             "api_keys": ["k"], "qa_model": "gemini-old-qa"},
        ])
        svc = ProviderService(config_dir=cfg_dir)
        data = svc.load_providers()
        data["providers"][0]["default_model"] = "gemini-2.5-flash"
        etag = svc.get_etag()
        result = svc.save_providers_with_etag(data, etag)
        assert "error" not in result, result
        out = json.loads((cfg_dir / "providers.json").read_text())
        assert "qa_model" not in out["providers"][0]

    def test_save_providers_idempotent_when_no_qa_model(tmp_path):
        cfg_dir = _setup_providers_file(tmp_path, [
            {"id": "x", "type": "gemini", "name": "X", "default_model": "gemini-2.0-flash",
             "api_keys": ["k"]},
        ])
        svc = ProviderService(config_dir=cfg_dir)
        data = svc.load_providers()
        svc.save_providers(data)
        out = json.loads((cfg_dir / "providers.json").read_text())
        assert "qa_model" not in out["providers"][0]

    def test_save_providers_strips_empty_qa_model(tmp_path):
        cfg_dir = _setup_providers_file(tmp_path, [
            {"id": "x", "type": "gemini", "name": "X", "default_model": "gemini-2.0-flash",
             "api_keys": ["k"], "qa_model": ""},
        ])
        svc = ProviderService(config_dir=cfg_dir)
        data = svc.load_providers()
        svc.save_providers(data)
        out = json.loads((cfg_dir / "providers.json").read_text())
        assert "qa_model" not in out["providers"][0]
    ```
  - Sau khi sửa: `rg -n -i 'qa_model|QA_MODEL|cfg-qa-model|Review Model|model_override' tests/` → expect 0.
- [ ] **Tài liệu hiện hành (zero residue, chỉ `CHANGELOG.md` giữ):**
  - `docs/ROADMAP.md`:
    - Dòng open task L277 `📋 Tối giản Hóa & Dọn Dẹp Trường Review Model (QA Model)` → đổi thành `[x] Đã loại bỏ triệt để Review Model / qa_model — zero residue (2026-08-28)` hoặc xóa dòng.
    - Bullet v8.29.0 L9 `get_active_default_model, get_active_qa_model` → bỏ `get_active_qa_model`. L13 `AppConfigService.get_qa_model_or_none()` → xóa hoặc ghi `[đã xóa]`. Mọi dòng khác trong ROADMAP có `qa_model`/`QA_MODEL` → xóa/sửa hết.
  - `README.md` / `docs/MANUAL.md` / `docs/*` nếu nhắc `Review Model` hoặc `qa_model` — xóa/sửa.
  - `CHANGELOG.md` — **giữ nguyên**.
  - Bản báo cáo này (`docs/wip/review_model_audit_and_plan.md`) — **archive vào `docs/archive/` (mkdir -p nếu chưa có) hoặc xóa SAU KHI PR merge** (§7.6 bước 3).

### 7.4. Backward Compatibility & Migration (v4)

| Artefact cũ | Hành vi code mới | Cần migration? |
|---|---|---|
| `providers.json` còn `qa_model` (vd `gemini-default: gemini-3.5-live-translate-preview`) | **Normalize tập trung tại `ProviderService.save_providers()` (`backend/infrastructure/providers/provider_service.py:170`):** `for p in data.get("providers", []): p.pop("qa_model", None)` chạy trước `_validate_providers_data(data)`. Bao phủ cả nhánh ETag (qua `save_providers_with_etag()`) lẫn non-ETag. | **Bắt buộc** — không dựa vào merge `{**p, **model_kwargs}`. One-off `jq` là tùy chọn nhưng code normalize mới là nguồn sự thật. |
| Checkpoint DB có `ident_qa_model` | `get_resume_info()` đọc `identity` dict có key thừa, `same_source_identity()` không so sánh, `execution_drift()` không còn key `qa_model` nên không báo drift. | Không. |
| Client cũ gửi `POST /api/settings/save {"qa_model": "..."}` | **400 `{error: "unknown field: qa_model"}`** — reject ngay đầu hàm (`webui/routes/settings.py:save_settings_transaction`), trước cả validate/ETag. | Không — client phải bỏ field. |
| `PUT /api/providers/<id>/models {"qa_model": "..."}` (cả 2 nhánh) | **400 `{error: "unknown field: qa_model"}`** — reject ngay đầu hàm (`webui/routes/settings.py:update_provider_models`), trước cả check `If-Match` (L731-738) và non-ETag (L744-757). | Không. |
| `TranslationRequest.from_dict({"qa_model": "x"})` | **Bỏ qua** (DTO không phải HTTP boundary). Test xác nhận `to_config()` không chứa key `qa_model`. | Không. |
| Caller cũ truyền `model_override` vào `translator._call_api` | Signature không còn param → `TypeError` nếu caller cũ còn truyền. Grep đã xác nhận 0 caller. | Không. |

**Snippet chuẩn hóa tập trung (v4 — đặt trong `ProviderService.save_providers`):**
```python
# backend/infrastructure/providers/provider_service.py:162-197
def save_providers(self, data: Dict[str, Any]) -> None:
    """Ghi providers.json bằng atomic write + validate."""
    # v4 (zero-residue): chuẩn hóa tập trung — xóa field legacy 'qa_model'
    # khỏi mọi provider trước khi validate/ghi. Đây là single source of
    # truth; route layer chỉ cần reject ở HTTP boundary, không cần
    # normalize lặp lại. Áp dụng cho cả nhánh có/không ETag vì
    # save_providers_with_etag() gọi save_providers() bên trong.
    for p in data.get("providers", []):
        p.pop("qa_model", None)
    import shutil
    self._providers_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = self._providers_file.with_suffix(".json.tmp")
    backup_path = self._providers_file.with_suffix(".json.bak")
    backup_tmp_path = self._providers_file.with_suffix(".json.bak.tmp")
    # Reject malformed user input before creating or touching any file.
    self._validate_providers_data(data)
    # ... phần còn lại giữ nguyên ...
```

### 7.5. Rủi ro & Giảm thiểu (v4)
- **Normalize chỉ ở route** → bỏ sót ETag. **Đã giải quyết** bằng cách đặt tại `save_providers()`.
- **Bỏ sót test** → 11 file test (10 v2 + 1 MỚI v3) + rg DoD.
- **Silent ignore che lỗi client** → reject 400 ở đầu mỗi HTTP route.
- **`model_override`** → đã xóa; grep xác nhận 0 caller.
- **Checkpoint** → an toàn (đã phân tích §6.2).
- **Migration script** → giữ, chỉ dọn logic QA; verify integration test còn pass.

### 7.6. Thứ tự thực hiện (1 PR — v4)
1. Tạo branch `chore/remove-qa-model-zero-residue`.
2. Thực hiện GĐ1 → GĐ2 (reject ở route, normalize ở `save_providers`) → GĐ3 (`model_override` + checkpoint/config + migration script) → GĐ4 (11 file test + ROADMAP).
3. **Archive báo cáo này** trước khi verify cuối:
   ```bash
   mkdir -p docs/archive
   git mv docs/wip/review_model_audit_and_plan.md docs/archive/review_model_audit_and_plan.archived.md
   # hoặc xóa thẳng:
   git rm docs/wip/review_model_audit_and_plan.md
   ```
4. Chạy DoD v4 (lệnh §9 dùng `rg -g`): expect 0 hit.
5. `pytest -q` + smoke: WebUI tab Cấu hình (không còn Review Model), `GET /api/providers` không trả `qa_model`, `PUT .../models {"qa_model":"x"}` (cả có/không `If-Match`) → 400, `POST /api/settings/save {"qa_model":"x"}` → 400, dịch file nhỏ, resume checkpoint cũ.
6. Cập nhật `docs/ROADMAP.md` (cả dòng open task L277 và bullet lịch sử L9, L13), commit `chore: remove Review Model (qa_model) + model_override — zero residue`.

---

## 8. Bảng Tổng kết Đối chiếu

| Câu hỏi | Kết quả |
| :--- | :--- |
| Hoạt động như thế nào? | Dormant config từ 2-pass cũ. Không gọi API review. `model_override` cũng dead. |
| Mặc định nhận model nào? | Trước: từ `providers.json.qa_model` → fallback `default_model` → `""`. Sau: chỉ `default_model`; `save_providers()` normalize xóa `qa_model`. |
| Tắt mặc định / tự động chạy? | Không tự chạy. Nay xóa + reject 400. |
| Chạy bởi trigger nào? | Không có. |
| Ảnh hưởng? | 0% runtime cost; gây hiểu lầm UX + technical debt. |
| Loại bỏ được không? | 100% — ĐÃ CHỐT v4. |
| Loại bỏ ảnh hưởng? | UI trong sáng, codebase tinh gọn, checkpoint cũ an toàn, normalize tập trung + reject 400. |

---

## 9. Phụ lục: Lệnh kiểm tra nhanh (v4 — `rg -g`)

```bash
# 1. Lệnh DoD chính — expect 0 hit
#    (Báo cáo này đã archive vào docs/archive/ hoặc xóa trước — §7.6 bước 3)
rg -n -i 'qa_model|QA_MODEL|cfg-qa-model|Review Model|model_override' \
  webui backend core services plugins config scripts tests docs README.md \
  -g '!CHANGELOG.md'
# expect: no output (rg exit 1 = no match = OK)

# 2. Kiểm tra providers.json sạch
jq '.providers[] | {id, has_qa: has("qa_model")}' config/providers.json
# expect: has_qa: false cho mọi provider

# 3. Kiểm tra checkpoint drift không còn qa_model
grep -n "EXECUTION_IDENTITY_FIELDS" services/checkpoint_service.py
# expect: 5 fields, không có "qa_model"

# 4. Kiểm tra model_override đã xóa khỏi translator.py
grep -n "model_override" plugins/translation/translator.py
# expect: no output

# 5. Smoke API: reject qa_model ở cả nhánh ETag lẫn non-ETag
# 5a. Non-ETag
curl -s -X PUT http://localhost:5000/api/providers/gemini-default/models \
  -H 'Content-Type: application/json' -d '{"qa_model":"x"}' | jq .
# expect: {"error":"unknown field: qa_model"} status 400

# 5b. ETag (lấy etag từ GET /api/providers, vd '"sha256-abc123"')
curl -s -X PUT http://localhost:5000/api/providers/gemini-default/models \
  -H 'Content-Type: application/json' \
  -H 'If-Match: "sha256-abc123"' \
  -d '{"qa_model":"x"}' | jq .
# expect: {"error":"unknown field: qa_model"} status 400

# 5c. POST /api/settings/save
curl -s -X POST http://localhost:5000/api/settings/save \
  -H 'Content-Type: application/json' -d '{"qa_model":"x"}' | jq .
# expect: {"error":"unknown field: qa_model"} status 400

# 6. Verify save_providers() normalize (manual)
# Sửa providers.json thêm "qa_model":"old" vào gemini-default,
# gọi PUT /api/providers/gemini-default/models {"default_model":"x"},
# đọc lại file — expect qa_model đã bị xóa.

# 7. Chạy test (đã cập nhật đủ 11 file, trong đó có test_provider_service_normalize.py MỚI)
pytest -q
```

---

## 10. Lịch sử chỉnh kế hoạch
- **v1 (2026-08-28):** Khảo sát, 2 phương án, 7 file test, giả định merge tự sạch, silent ignore, giữ `model_override`.
- **v2 (2026-08-28):** Review lần 1 — bắt buộc normalize `pop("qa_model")` ở route; đổi silent ignore → reject 400; bổ sung 5 file test; xóa `model_override`; DoD chỉ giữ `CHANGELOG.md`; mở lựa chọn xóa/giữ migration script.
- **v3 (2026-08-28):** Review lần 2 — **(1) chuyển normalize từ route → tập trung tại `ProviderService.save_providers()`** để bao phủ ETag/non-ETag; **(2) lệnh DoD dùng `rg -g` thay `grep --exclude`**; **(3) chốt giữ `migrate_providers_v2.py`** vì integration test; thêm test MỚI `test_provider_service_normalize.py`; bước archive báo cáo; DTO chốt "bỏ qua" + test xác nhận.
- **v4 (2026-08-28):** Review lần 3 — bổ sung **tham chiếu `file:line` cụ thể** cho từng hành động (§0 Quick Reference + §7.3) để tra cứu nhanh khi triển khai; snippet Python đầy đủ cho `save_providers()` normalize, `update_provider_models()` reject, `save_settings_transaction()` reject, test MỚI `test_provider_service_normalize.py`. Sẵn sàng triển khai.
