# Cloudflare AI Gateway: phân tích lỗi 401/404 khi dịch chunk

Ngày phân tích: 2026-07-31  
Phạm vi: provider `cloudflare`, OpenAI-compatible client, luồng dịch chunk/project và `/api/translate-text`.

## Kết luận ngắn

Base URL đang dùng có dạng đúng cho OpenAI SDK:

    https://gateway.ai.cloudflare.com/v1/{account_id}/{gateway_id}/compat

SDK sẽ nối thêm `/chat/completions`. Không nên thêm `/chat/completions` vào giá trị `base_url`.

Lỗi không nằm ở việc SDK không thể tải danh sách model. Root cause là tổ hợp các lỗi sau:

1. `OpenAIClient` chỉ truyền `api_key` của SDK, tức header `Authorization`; client không hỗ trợ `cf-aig-authorization`. Với AI Gateway, hai header này có ý nghĩa khác nhau: `Authorization` là credential của provider, còn `cf-aig-authorization` là token Cloudflare/Gateway trong flow tương ứng.
2. Provider Cloudflare đang dùng model mặc định có hậu tố `:free`. Đây là quy ước routing của OpenRouter, không nên mang nguyên sang Cloudflare. Compat endpoint yêu cầu model theo dạng `{provider}/{model}` và phải là ID model mà gateway/provider thực sự hỗ trợ. Model ID sai thường tạo 404 khi POST dù GET `/models` vẫn thành công.
3. Luồng `/api/translate-text` không truyền `provider_type` và `base_url` vào `robust_translate`. `_get_client()` vì thế mặc định rơi về Gemini (`provider_type = "gemini"`) và không dùng Cloudflare, trong khi API key lại lấy từ `load_api_keys()` không giới hạn provider.
4. Luồng dịch project có truyền hai trường trên, nhưng không ghi đè model do UI gửi lên nếu model đó không hợp lệ. Validation catalog chỉ kiểm tra biến fallback `default_model`, không kiểm tra `config["model_name"]` đã chọn.

## Bằng chứng trong mã nguồn

- [services/openai_client.py](/Users/narga/Briefcase/Projects/Novel-Translator/services/openai_client.py:54) chỉ khởi tạo OpenAI SDK với `api_key` và `base_url`; không có custom header `cf-aig-authorization`.
- [services/openai_client.py](/Users/narga/Briefcase/Projects/Novel-Translator/services/openai_client.py:89) gửi `chat.completions.create()` với model nguyên trạng, không normalize/validate model.
- [services/openai_client.py](/Users/narga/Briefcase/Projects/Novel-Translator/services/openai_client.py:113) gọi `models.list()` độc lập với POST chat completion. Thành công ở đây chỉ chứng minh GET endpoint/credential của request đó hoạt động, không chứng minh model POST sẽ được route.
- [plugins/translation/translator.py](/Users/narga/Briefcase/Projects/Novel-Translator/plugins/translation/translator.py:43) mặc định `provider_type` là `gemini`, `base_url` là chuỗi rỗng.
- [webui/routes/translation.py](/Users/narga/Briefcase/Projects/Novel-Translator/webui/routes/translation.py:163) lấy tất cả key khi dịch trực tiếp; [webui/routes/translation.py](/Users/narga/Briefcase/Projects/Novel-Translator/webui/routes/translation.py:172) chỉ đưa model/temperature/chunk size vào config.
- [webui/routes/projects.py](/Users/narga/Briefcase/Projects/Novel-Translator/webui/routes/projects.py:1305) kiểm tra `default_model`, nhưng [webui/routes/projects.py](/Users/narga/Briefcase/Projects/Novel-Translator/webui/routes/projects.py:1325) chỉ gán fallback khi `config["model_name"]` rỗng.
- Cấu hình provider hiện tại đặt model Cloudflare là `deepseek/deepseek-chat-v3-0324:free`; cần thay bằng ID Cloudflare trả về/được tài liệu Cloudflare xác nhận, không dùng suffix `:free` của OpenRouter.

GitNexus đã truy vết `_call_api` qua các process `execute`, `translate_file`, `translate_worker`, `spellcheck` và `translate_text`; impact upstream được đánh giá **CRITICAL**, gồm 5 process và 4 module. Việc sửa client/config phải có test hồi quy cho toàn bộ các luồng này.

## Diễn giải hai mã lỗi

### 401

Khả năng cao nhất là token Cloudflare được lưu vào trường `api_key`, sau đó OpenAI SDK gửi nó như:

    Authorization: Bearer <cloudflare-token>

Trong compat flow, header này được dùng cho credential provider. Nếu gateway cần token Cloudflare, token phải đi qua `cf-aig-authorization`; nếu dùng BYOK/request key, `Authorization` phải là API key của provider model. Cần xác định rõ một trong hai flow:

- Stored key/BYOK hoặc Unified Billing: dùng Cloudflare API token cho Gateway theo hướng dẫn hiện hành, thường qua `cf-aig-authorization` ở compat endpoint.
- Provider key trong request: `Authorization` là API key của OpenAI/Google/Anthropic/DeepSeek; Cloudflare token (nếu bắt buộc) là header riêng.

Không nên dùng một token cho đồng thời cả hai vai trò.

### 404

Khả năng cao nhất là model ID không tồn tại trong namespace Cloudflare hoặc chứa routing suffix chỉ có ở OpenRouter. Compat endpoint dùng prefix provider, ví dụ `openai/gpt-4.1`, `google/gemini-3-flash`, hoặc format riêng cho Workers AI. Hãy lấy một ID từ catalog tương ứng rồi gọi thử đúng ID đó; không tự ghép `:free`, không dùng model mặc định cũ làm fallback.

## Phương án khắc phục

### 1. Tách credential Gateway và credential provider

Mở rộng `OpenAIClient` để nhận header tùy chọn, tối thiểu:

    OpenAIClient(
        api_key=provider_api_key,
        base_url=cloudflare_compat_base_url,
        default_headers={"cf-aig-authorization": f"Bearer {cloudflare_token}"},
    )

Không ghi token vào log. Nếu dùng stored key/unified billing, thiết kế config riêng như `gateway_api_key` hoặc `cf_aig_token`, thay vì tái sử dụng trường `api_key` vốn đang được hiểu là provider key. Với OpenAI SDK, truyền header qua `default_headers` hoặc HTTP client tương đương theo version SDK đang cài.

### 2. Chuẩn hóa model theo từng provider

- Chọn model ID trực tiếp từ response/catalog của Cloudflare.
- Xóa `:free` khỏi model Cloudflare nếu suffix đó chỉ thuộc OpenRouter.
- Không tự động chèn model fallback generic như `gpt-4o-mini` vào danh sách Cloudflare nếu model đó chưa được xác nhận.
- Nếu request chứa model không thuộc catalog của provider active, báo lỗi cấu hình rõ ràng hoặc thay bằng model hợp lệ trước khi gọi API.

### 3. Sửa luồng dịch trực tiếp

Trong `/api/translate-text`, lấy `active_provider_config()` và truyền ít nhất:

    {
        "provider_type": active["type"],
        "base_url": active.get("base_url"),
        "model_name": active.get("default_model") hoặc model từ request,
    }

API key phải lấy từ active provider, không dùng `load_api_keys()` không tham số cho một request OpenAI-compatible.

### 4. Sửa validation ở luồng project

Validate chính `config["model_name"]` sau khi đọc request/UI. Nếu model không nằm trong catalog Cloudflare, không gửi request; báo model không hợp lệ hoặc thay bằng model Cloudflare hợp lệ và cập nhật cả `model_name` lẫn `qa_model`.

### 5. Test smoke trước khi chạy dịch hàng loạt

    # Chỉ dùng placeholder; không commit token thật.
    curl -i "$CF_COMPAT_BASE_URL/models" \
      -H "cf-aig-authorization: Bearer $CF_AIG_TOKEN"

    curl -i "$CF_COMPAT_BASE_URL/chat/completions" \
      -H "cf-aig-authorization: Bearer $CF_AIG_TOKEN" \
      -H "Authorization: Bearer $PROVIDER_API_KEY" \
      -H "Content-Type: application/json" \
      --data '{"model":"<provider>/<model-tu-catalog>","messages":[{"role":"user","content":"ping"}]}'

Nếu dùng stored key/unified billing, bỏ provider key theo đúng flow trong tài liệu tài khoản; không trộn hai cách xác thực. Kiểm tra riêng `/models` và `/chat/completions`, vì một endpoint thành công không chứng minh endpoint kia đúng.

## Phạm vi secret

Theo phạm vi vận hành hiện tại, đây là app cá nhân, `providers.json` nằm trong `.gitignore`, remote private và chỉ một người sử dụng. Handoff không bao gồm secret scan, rotation, migration secret store hoặc thay đổi cơ chế lưu key. Chỉ giữ nguyên yêu cầu kỹ thuật: không in secret vào log/test/error message.

## Tài liệu Cloudflare tham chiếu

- [Unified API (OpenAI compat)](https://developers.cloudflare.com/ai-gateway/usage/chat-completion/) — endpoint `/v1/{account}/{gateway}/compat`, format model có provider prefix, và trạng thái deprecated/compatibility.
- [Cloudflare AI Gateway troubleshooting](https://developers.cloudflare.com/ai-gateway/reference/troubleshooting/) — phân biệt `Authorization` của provider với `cf-aig-authorization` của Cloudflare và cách xử lý 401.
- [REST API](https://developers.cloudflare.com/ai-gateway/usage/rest-api/) — endpoint mới `api.cloudflare.com/client/v4/accounts/{account}/ai/v1/chat/completions`, auth bằng Cloudflare API token, model naming và Unified Billing.
- [OpenAI provider endpoint](https://developers.cloudflare.com/ai-gateway/usage/providers/openai/) — cách dùng provider-specific endpoint và header khi cần.

## Kết luận triển khai

Không cần thay base URL chỉ vì thấy 404/401. Ưu tiên sửa theo thứ tự: (1) xác định flow credential và truyền đúng header, (2) chọn model ID Cloudflare hợp lệ, (3) truyền provider config vào mọi luồng dịch, đặc biệt `/api/translate-text`, (4) thêm smoke test và hồi quy cho `_call_api` trước khi bật dịch hàng loạt.
+
# Addendum: chỉ dẫn triển khai sửa provider, retry, empty response và resume

Phần này là đặc tả triển khai. Không sửa từng phần rời rạc; phải giữ invariant: mọi request dịch dùng đúng provider, credential, model, retry policy và session state của chính request đó.

## A. Phân loại provider bằng base URL

Tạo một hàm thuần, dùng chung ở mọi route/worker, ví dụ classify_endpoint(base_url). Chuẩn hóa URL bằng urlparse: lowercase hostname, bỏ trailing slash, giữ path để kiểm tra.

Kết quả tối thiểu:

- cloudflare_ai_gateway nếu hostname là gateway.ai.cloudflare.com và path khớp /v1/<account_id>/<gateway_id>/compat hoặc nhánh con.
- vercel_ai_gateway nếu hostname là ai-gateway.vercel.sh; base chuẩn là https://ai-gateway.vercel.sh/v1.
- openai_compatible cho endpoint khác có format OpenAI.
- native_openai nếu không truyền base URL hoặc endpoint OpenAI chính thức.

Không dùng kiểm tra lỏng kiểu “cloudflare có trong base_url” làm điều kiện duy nhất. Nếu provider config có endpoint_kind rõ ràng thì ưu tiên giá trị đó, sau đó kiểm tra hostname để phát hiện mâu thuẫn và báo lỗi.

Validation phải từ chối Cloudflare URL thiếu account/gateway/compat, Vercel URL bị nối /chat/completions vào base, query/fragment không cần thiết, model rỗng hoặc model không khớp namespace. Lưu provider_kind vào runtime config và đưa nó vào cache key.

## B. Tách credential Gateway và credential provider

Runtime config phải phân biệt provider_api_key và gateway_api_key/cf_aig_token. Không dùng một trường api_key cho hai vai trò.

Cloudflare:

- Request-key/BYOK: Authorization là provider_api_key.
- Khi gateway yêu cầu token Cloudflare: gửi thêm cf-aig-authorization: Bearer <cf_aig_token>.
- Stored key/Unified Billing: dùng đúng flow của tài khoản; không dùng Cloudflare token như provider key.
- Không log giá trị header; chỉ log provider_kind, hostname, model, request id và credential mode.

Vercel:

- Authorization là Bearer <AI_GATEWAY_API_KEY>.
- Không gửi cf-aig-authorization.
- Không áp dụng account/gateway path hoặc quy tắc token Cloudflare.
- Model dùng dạng creator/model.
- Fallback nhiều model của Vercel phải được triển khai rõ bằng providerOptions.gateway hoặc application layer; base URL không tự tạo fallback.

Provider OpenAI/Groq/Mistral/NVIDIA thông thường chỉ gửi provider key trong Authorization, không gửi custom gateway header và không dùng model ID của Cloudflare/Vercel.

## C. Sửa OpenAIClient và hợp đồng lỗi

OpenAIClient phải nhận headers/default_headers và endpoint classification. Header tạo một lần khi khởi tạo client.

Không được bắt mọi Exception rồi trả về chuỗi error như response bình thường. Khuyến nghị tạo ProviderRequestError có http_status, error_code, retryable, provider_kind, request_id, raw_message rồi raise để _call_api xử lý.

Phân loại:

- 401/403: auth/permission; không retry cùng credential.
- 404: endpoint/model không tồn tại; không retry cùng request.
- 400/422: payload/model/parameter sai; không retry.
- 408/429/5xx/timeout/connection: retry giới hạn/backoff.
- HTTP 200 nhưng choices/content rỗng: empty_response thật; retry theo empty policy tối đa 1-2 lần.
- HTTP 200 reasoning-only: kiểm tra schema trước khi coi là empty.

generate_content chỉ gửi temperature khi provider/model hỗ trợ. Không truyền thinking_level kiểu Gemini vào OpenAI-compatible request; nếu provider có reasoning phải có mapping riêng.

## D. Sửa _call_api: không biến lỗi thành empty

Giữ empty_streak chỉ cho response thực sự rỗng. Luồng bắt buộc:

1. Lấy provider_kind, model, endpoint và runtime fingerprint.
2. Chọn key đúng active provider.
3. Gọi client.
4. Success và content không rỗng: mark_success và trả success.
5. Response rỗng: tăng empty counter và dùng empty retry policy.
6. ProviderRequestError: đặt last_error đúng loại; chỉ gọi handle_api_error nếu retryable.
7. Không tăng empty counter cho 400/401/404/429/5xx, parse error hoặc network error.
8. Hết retry phải trả api_error:401, model_not_found:404, upstream_empty, timeout... để UI hiển thị nguyên nhân.

Bắt buộc loại bỏ logic hiện tại tương đương “mọi status khác success đều tăng empty_streak”. Đây là nguyên nhân trực tiếp khiến 401/404 bị đổi thành empty_response sau hai lần thử.

401/404 không được xoay cùng key nhiều lần. Với gateway, retry cùng token không làm mapping header/model đúng hơn.

## E. Rà soát mọi entry point

### Project translation

Tạo immutable runtime config từ active provider trước khi worker chạy, gồm provider_id, provider_kind, provider_type, base_url, provider_api_key, gateway_api_key, model_name, qa_model, temperature, chunk_size, prompt_fingerprint và source/session fingerprint.

Validate model thực tế từ request/UI trong worker. Nếu sai, dừng trước chunk đầu tiên với lỗi cấu hình; không âm thầm dùng model cũ/fallback provider khác. Không mutate config dùng chung nếu job có thể chạy song song.

### Direct translate /api/translate-text

Đây là lỗi độc lập bắt buộc sửa:

- Không gọi load_api_keys() không tham số.
- Lấy active provider config.
- OpenAI-compatible chỉ lấy key của provider đó.
- Truyền provider_type, provider_kind, base_url và credential fields vào config_params.
- Không mặc định Gemini khi active provider là gateway.
- Dùng cùng resolver/factory với project translation.

### Legacy translate_worker

webui/routes/translation.py:translate_worker hiện lấy Gemini keys trực tiếp. Chuyển nó sang resolver chung hoặc deprecate route và xác nhận UI không gọi nó. Không để một entry point luôn dùng Gemini khi UI chọn Cloudflare/Vercel.

### Spellcheck

Spellcheck dùng chung robust_translate nhưng đang tiếp tục sau lỗi và có thể báo complete với partial text. Với lỗi API, không ghi lỗi thành bản dịch hợp lệ; job phải failed/partial, giữ checkpoint để resume và dùng cùng provider/model fingerprint.

### Summary, model-info, model-list

Các route này cũng phải dùng active provider config và header classification. Model listing không chứng minh chat completion hoạt động. Live model list phải chứa id, provider_kind, source_endpoint, capabilities và fetched_at; không chèn fallback generic vào list Cloudflare/Vercel.

## F. Nguyên nhân “lần sau empty”: bốn state khác nhau

1. _client_cache là cache object SDK, không phải response cache. Thêm provider kind, normalized URL, header/credential fingerprint, model vào key; đổi config phải tạo object mới.
2. Translation Memory lưu persistent memory.json. Project dùng pdir/assets/translation_memory; WebUI singleton dùng workspace/projects/default-project/profile/translation_memory. Hai nút clear có thể xóa khác path. Clear/stats/find phải nhận cùng project path executor dùng và trả path/count.
3. Checkpoint SQLite ở workspace/checkpoints, key hiện chỉ hash output_filename. Nó không phân biệt source, provider, model, prompt hoặc chunk size. Khi fail, checkpoint cố ý còn để resume.
4. Rate limiter/cooldown nằm trong ApiManager của executor, không phải cache/memory. 401/404 không được coi là quota.

### Checkpoint fix bắt buộc

Identity phải gồm project/file, source SHA-256, chunker version/chunk size, provider id/kind, normalized base URL, model, prompt/glossary fingerprint và schema version.

Identity không khớp thì không resume checkpoint cũ. Tạo session mới hoặc yêu cầu force retranslate. Không dùng chỉ done_count để suy ra next index; tìm pending đầu tiên vì done rows có thể không liên tục.

Không lưu error/empty/partial vào trạng thái done. File fail giữ trạng thái failed và error metadata. force_retranslate phải xóa đúng checkpoint identity. Đổi Cloudflare sang OpenAI/Vercel phải tạo identity mới hoặc xóa checkpoint cũ.

### Translation Memory fix bắt buộc

Chỉ add_translation sau success đã validate. Không lưu empty/partial/error. Match phải kèm provider/model/prompt policy hoặc phải xác định rõ TM provider-neutral. Test clear project phải xác nhận find_match trả None đúng path.

## G. Vercel có phải trường hợp đặc biệt?

Có, nhưng chỉ ở lớp gateway adapter:

- Hostname, base URL và auth khác Cloudflare.
- Vercel dùng một gateway key trong Authorization.
- Không có cf-aig-authorization.
- Model naming vẫn creator/model.
- Model GET có thể có auth khác POST; không suy luận chat auth từ GET.
- Vercel có routing/fallback/provider options riêng.

Không tạo nhánh Cloudflare/Vercel rải rác trong route. Dùng CloudflareGatewayPolicy, VercelGatewayPolicy và OpenAICompatiblePolicy; mỗi policy trả headers, normalize_model, validate_model, retry_policy và supports_feature.

## H. Test bắt buộc

Unit:

- classify đúng Cloudflare, Vercel, OpenAI và unknown.
- Cloudflare tạo đúng Authorization/cf-aig-authorization theo mode.
- Vercel không tạo cf-aig-authorization.
- model provider/model được giữ; suffix OpenRouter :free bị từ chối hoặc chỉ normalize trong OpenRouter adapter.
- HTTP 401/404 là typed error, không là empty.
- _call_api không tăng empty counter cho 400/401/404/429/5xx.
- 401 không retry ba lần cùng key.
- checkpoint identity đổi khi đổi provider/model/prompt/chunk size/source.
- clear TM xóa đúng file mà executor đọc.
- empty/error không vào TM hoặc checkpoint done.

Integration fake client:

1. 401, 401 => auth error, không phải empty.
2. 404 model => model-not-found, không retry vô hạn.
3. 429 rồi success => backoff và save đúng chunk.
4. 200 empty rồi success => chỉ trường hợp này dùng empty retry.
5. fail ở chunk 2 rồi chạy lại => chunk 0/1 resume, chunk 2 gọi lại.
6. đổi Cloudflare sang Vercel => checkpoint cũ không resume.
7. clear TM project A không ảnh hưởng project B/checkpoint.
8. spellcheck có lỗi => không báo complete giả.

Smoke thật: gọi riêng GET /models và POST /chat/completions bằng model ID từ catalog provider. Chỉ log status, schema, request id, model và hostname; không log secret hoặc full body.

## I. Tiêu chí hoàn thành

Mọi entry point đi qua resolver chung; Cloudflare/Vercel/provider thường có policy header riêng; không còn đường mặc định Gemini khi active provider là OpenAI-compatible; 401/404 không còn báo empty_response; empty thật và API error phân biệt trong log/UI/job; checkpoint không resume chéo provider/model/config; TM clear đúng path và chỉ lưu success; test bao phủ project, direct, spellcheck, summary và model list; plaintext secrets được loại khỏi repository và key đã lộ được rotate.

