# Handoff triển khai: sửa toàn bộ AI Gateway và luồng dịch
+
## Ma trận lựa chọn model

### GPT-5.6 Sol — lựa chọn ưu tiên

Dùng cho lần triển khai đầu tiên nếu có thể. Cấu hình reasoning high hoặc xhigh, workspace-write, có terminal/test tools. Model phải tự sửa code, chạy test và xử lý lỗi phát sinh; không chỉ trả patch trên lý thuyết.

### GPT-5.6 Luna — dùng được

Luna phù hợp cho workload tiết kiệm chi phí và khối lượng cao, nhưng nhiệm vụ này có call graph/state/checkpoint phức tạp. Nếu giao Luna:

- dùng reasoning high; với lỗi khó có thể nâng xhigh/max nếu surface hỗ trợ;
- bắt buộc chạy theo từng pha, không sửa toàn bộ file trong một lượt;
- sau mỗi pha phải chạy test và ghi lại kết quả;
- không được đánh dấu hoàn tất nếu chưa chạy detect_changes và targeted tests;
- phải dừng để kiểm tra nếu có symbol/process ngoài blast radius;
- giữ nguyên toàn bộ acceptance criteria của handoff;
- dùng một phiên liên tục có context đủ dài, không chia nhiều agent cùng sửa code.

Luna có thể hoàn thành nếu tuân thủ các gate trên; không nên giao Luna cho nhiệm vụ “tự sửa nhanh rồi không chạy test”.

### Kimi K3 — dùng được nếu có coding harness thật

Kimi K3 phù hợp long-horizon coding/agent tasks, nhưng khả năng thực thi phụ thuộc surface: Kimi Code/CLI, OpenAI-compatible API hay chat không có tool. Nếu giao Kimi K3:

- xác định model ID thật trước khi chạy; dùng model ID do endpoint cung cấp, không dùng tên hiển thị “Kimi K3” nếu API yêu cầu model ID;
- phải cấp terminal, file read/write, patch và test tools;
- prompt phải yêu cầu “inspect -> impact -> edit -> test -> review” theo từng pha;
- mỗi lượt chỉ hoàn thành một pha; sau đó báo files, symbols, tests và remaining risks;
- không cho phép tự suy đoán API Cloudflare/Vercel; phải dùng URL/provider policy trong handoff;
- bắt buộc đọc file hiện tại trước khi patch, không overwrite toàn file;
- nếu tool call không hoạt động, chuyển sang planner/reviewer, không để model giả lập việc đã chạy;
- giới hạn concurrency: một model duy nhất sửa repository.

Kimi K3 không nên là lựa chọn duy nhất nếu surface chỉ là chat không có terminal hoặc không trả được structured tool result.

### Gemini 3.1 Pro High — rất phù hợp cho phân tích và triển khai

Model API chính thức là gemini-3.1-pro-preview; “High” là mức thinking, không phải model ID. Model này được Google mô tả là tối ưu cho software engineering và agentic workflows. Nếu giao Gemini:

- đặt thinking_level=high qua API/provider config, không chỉ viết “hãy suy nghĩ high” trong prompt;
- nếu surface hỗ trợ custom tools/bash, ưu tiên endpoint gemini-3.1-pro-preview-customtools;
- phải cấp tool shell/file patch/test;
- bắt buộc chia thành các pha nhỏ vì model có thể trả kế hoạch tốt nhưng bỏ qua bước thực thi nếu prompt không nêu rõ action;
- sau mỗi patch phải đọc lại diff và chạy test;
- phải xác nhận status của lệnh bằng output thật; cấm tuyên bố đã test nếu chưa có output;
- không truyền thinking_level sang OpenAI-compatible adapter; tham số này chỉ thuộc Gemini policy;
- giữ giới hạn context cho file cần thiết, không nạp toàn bộ repository nếu chưa có query/impact.

Gemini 3.1 Pro High phù hợp làm primary implementer hoặc reviewer độc lập. Nếu dùng Gemini để review code do model khác sửa, yêu cầu review diff + test output, không yêu cầu viết lại toàn bộ từ đầu.

### NVIDIA Nemotron 3 — chỉ giao sau khi chốt variant và harness

NVIDIA Nemotron 3 là một family, không đủ để chọn model thực thi. Phải chốt chính xác Nano, Super hoặc Ultra và model ID/endpoint thật. Nếu giao Nemotron:

- ghi rõ variant, provider, endpoint và model ID trong task;
- xác nhận endpoint có tool calling, terminal/file editing, streaming và structured errors;
- chạy một smoke task nhỏ: đọc file, sửa một dòng trong file tạm, chạy test, đọc diff;
- nếu smoke task không chứng minh được tool execution, chỉ dùng Nemotron làm planner/reviewer;
- bắt buộc prompt ngắn, có checklist, phase gates và output schema;
- không giao một lượt “sửa toàn bộ repo”; giao từng pha có test;
- yêu cầu kiểm tra lại mọi thay đổi bằng diff và test output;
- không dựa vào khả năng reasoning của model để thay thế GitNexus impact hoặc test;
- nếu dùng model open-weight qua NVIDIA/OpenAI-compatible endpoint, áp dụng endpoint policy theo base URL thật, không gọi nó là Cloudflare/Vercel nếu không đúng hostname.

Nemotron 3 có tiềm năng cho agentic workflow, nhưng variant/harness ảnh hưởng trực tiếp đến độ tin cậy. Không nên chọn làm primary implementer nếu chưa smoke-test tool loop.

## Profile giao việc cụ thể

Nếu chỉ được chọn một model:

- ưu tiên GPT-5.6 Sol;
- chọn GPT-5.6 Luna nếu ưu tiên chi phí và chấp nhận chạy chậm theo từng gate;
- chọn Gemini 3.1 Pro High nếu có tool/bash harness tốt và muốn reviewer/implementer mạnh;
- chọn Kimi K3 nếu có Kimi Code/CLI hoặc agent harness đã xác minh;
- chọn Nemotron 3 chỉ sau khi xác minh đúng variant và tool execution.

Nếu muốn dùng hai model tuần tự:

1. Gemini 3.1 Pro High hoặc GPT-5.6 Sol triển khai;
2. model thứ hai chỉ review diff, test, state machine và checkpoint;
3. reviewer không sửa song song; chỉ sửa sau khi báo finding rõ ràng và chạy impact lại.

Không khuyến nghị dùng Luna/Kimi/Nemotron để ba agent cùng chỉnh một worktree.



## Model và execution profile khuyến nghị

Giao cho **GPT-5.6 Sol** với reasoning `high` hoặc `xhigh`, workspace-write và quyền chạy test cục bộ. Đây là nhiệm vụ sửa liên module, cần truy vết call graph, thay đổi state machine và kiểm thử hồi quy; không nên giao cho model mini/fast.

Nếu môi trường chỉ cung cấp model chuyên Codex, dùng **GPT-5.3-Codex** với mức reasoning cao. Không chia task thành nhiều model sửa code song song vì các thay đổi ở resolver, retry, checkpoint và executor phụ thuộc lẫn nhau.

## Mục tiêu

Sửa hệ thống để mọi request dịch:

1. dùng đúng provider đang active;
2. nhận diện đúng Cloudflare, Vercel và OpenAI-compatible bằng base URL;
3. gửi đúng credential/header/model;
4. phân biệt API error với response rỗng;
5. không resume nhầm checkpoint/TM sau khi đổi provider/model/config;
6. retry có kiểm soát;
7. không trả nhầm empty response sau lỗi 401/404;
8. có test hồi quy cho project translation, direct translation, spellcheck, summary và model listing.

Không đổi provider mặc định ngoài phạm vi yêu cầu. Không thêm fallback im lặng sang Gemini/OpenAI. Không làm lộ secret. Không xóa thay đổi mã nguồn có sẵn của người dùng.

## Quy tắc bắt buộc trước khi sửa

Đọc AGENTS.md và skill GitNexus debugging/impact-analysis.

Trước khi chỉnh sửa bất kỳ function/class/method nào:

1. chạy GitNexus impact upstream cho symbol đó;
2. nếu risk HIGH/CRITICAL, ghi nhận blast radius và kiểm tra callers/processes;
3. đọc source và test của toàn bộ caller trực tiếp;
4. sau khi sửa, chạy test liên quan;
5. trước commit, chạy gitnexus_detect_changes().

Không dùng find-and-replace để rename symbol. Không sửa secret thật trong log/test. Nếu GitNexus báo index stale, chạy npx gitnexus analyze.

## Phạm vi file chính

Rà soát và chỉ sửa khi cần:

- services/openai_client.py
- services/ai_provider.py
- plugins/translation/translator.py
- webui/routes/translation.py
- webui/routes/projects.py
- core/executor.py
- services/checkpoint_service.py
- services/translation_memory.py
- services/api_service.py
- backend/infrastructure/providers/provider_service.py
- backend/infrastructure/providers/model_catalog_service.py
- webui/helpers.py
- tests/unit/ và tests/smoke/ liên quan

Không sửa trực tiếp các file unrelated đang modified trong worktree.

## Pha 1 — tạo endpoint/provider resolver

Tạo module dùng chung, ưu tiên backend/infrastructure/providers/endpoint_policy.py hoặc vị trí kiến trúc tương đương.

Hàm resolver phải:

- chuẩn hóa base URL;
- phân loại bằng hostname và path;
- trả policy/type rõ ràng;
- không dựa duy nhất vào tên provider hoặc substring.

Các loại:

- cloudflare_ai_gateway: hostname gateway.ai.cloudflare.com và path /v1/<account>/<gateway>/compat;
- vercel_ai_gateway: hostname ai-gateway.vercel.sh;
- native_openai: base URL rỗng hoặc OpenAI chính thức;
- openai_compatible: endpoint còn lại.

Runtime policy phải có:

- provider_kind;
- normalized_base_url;
- build_headers();
- normalize_model();
- validate_model();
- classify_error();
- retry_policy;
- supports_feature().

Từ chối base URL sai cấu trúc. Không tự nối /chat/completions vào base URL. Không tự chèn provider prefix nếu model đã có prefix. Không tự bỏ :free trừ khi policy OpenRouter được xác định rõ; không áp dụng quy tắc OpenRouter cho Cloudflare/Vercel.

## Pha 2 — credential/header policy

Mở rộng provider config/runtime để phân biệt:

- provider_api_key;
- gateway_api_key hoặc cf_aig_token;
- credential_mode.

Backward compatibility chỉ được giữ ở provider thường. Không dùng một trường api_key mơ hồ cho Cloudflare.

Cloudflare compat:

- Authorization dùng provider key nếu chạy request-key/BYOK;
- cf-aig-authorization dùng Cloudflare gateway token khi flow yêu cầu;
- stored key/Unified Billing phải theo đúng flow tài khoản;
- không gửi nhầm Cloudflare token vào Authorization như provider key.

Vercel:

- Authorization: Bearer AI_GATEWAY_API_KEY;
- không gửi cf-aig-authorization;
- base chuẩn: https://ai-gateway.vercel.sh/v1;
- model dạng creator/model;
- fallback Vercel chỉ hoạt động nếu adapter thực sự hỗ trợ providerOptions hoặc application fallback.

Provider thường:

- Authorization: Bearer provider key;
- không gửi Cloudflare/Vercel custom header.

Header không được ghi log. Chỉ log hostname, provider_kind, model, request id và credential mode.

## Pha 3 — sửa OpenAIClient

Sửa services/openai_client.py:

1. nhận headers/default_headers và provider policy;
2. đưa header fingerprint/provider kind vào client cache identity;
3. truyền đúng base URL;
4. gửi model sau khi policy validate;
5. không nuốt mọi exception thành chuỗi error.

Tạo ProviderRequestError hoặc exception tương đương với:

- http_status;
- error_code;
- retryable;
- provider_kind;
- request_id;
- safe_message.

Quy tắc:

- 400/422: payload/model/parameter error, không retry;
- 401/403: auth/permission error, không retry cùng credential;
- 404: endpoint/model not found, không retry cùng request;
- 408/429/5xx/timeout/connection: retry giới hạn;
- HTTP 200 nhưng choices/content rỗng: upstream_empty;
- response reasoning-only phải được parse đúng, không tự coi content None là success.

Không truyền thinking_level của Gemini vào OpenAI-compatible request. Chỉ gửi temperature khi model/provider cho phép.

Giữ list_models nhưng coi đó là discovery độc lập, không phải bằng chứng chat completion hoạt động. Trả lỗi discovery có cấu trúc thay vì im lặng trả list fallback.

## Pha 4 — sửa translator retry/state

Sửa plugins/translation/translator.py.

### _get_client

- nhận đầy đủ provider_kind, base_url, headers, credential mode;
- tạo client theo policy;
- cache key gồm provider id/kind, normalized URL, model, credential/header fingerprint;
- không cache chéo provider/model/config.

### _call_api

Tách ba trường hợp:

1. success có content;
2. upstream response rỗng;
3. request thất bại.

Chỉ trường hợp 2 mới tăng empty_streak.

Không được có logic coi mọi status khác success là empty. Khi bắt ProviderRequestError:

- nếu retryable thì gọi ApiManager retry policy;
- nếu không retryable thì trả api_error/model_not_found/auth_error ngay;
- không xoay key vô ích với 401/403/404;
- không cooldown auth/model error như quota nếu không đúng bản chất.

Status phải phân biệt tối thiểu:

- success;
- upstream_empty;
- auth_error;
- permission_error;
- model_not_found;
- invalid_request;
- rate_limited;
- provider_unavailable;
- timeout;
- stopped;
- all_keys_exhausted.

Giữ nguyên signature công khai nếu có thể; nếu đổi phải cập nhật mọi caller và test.

## Pha 5 — gom toàn bộ entry point về resolver chung

### Project translation

Trong webui/routes/projects.py:

- lấy active provider một lần;
- tạo runtime config đầy đủ trước khi worker chạy;
- validate model request/UI trong worker;
- không fallback sang model của provider khác;
- không mutate config dùng chung nếu job song song;
- truyền provider_type/provider_kind/base_url/credentials/model vào TranslationExecutor.

### Direct /api/translate-text

Sửa lỗi hiện tại:

- không gọi load_api_keys() không tham số;
- lấy active provider config;
- chỉ dùng key của active provider;
- truyền provider_type, provider_kind, base_url và credential fields;
- default model phải thuộc active provider;
- dùng cùng factory/client với project translation.

### Legacy translate_worker

webui/routes/translation.py:translate_worker không được luôn lấy Gemini keys. Chuyển sang resolver chung hoặc deprecate route. Xác nhận UI không còn gọi route cũ.

### Spellcheck

Dùng cùng provider/error/checkpoint policy. Nếu một chunk lỗi:

- không ghi lỗi thành done;
- không báo complete giả;
- job status phải failed/partial;
- giữ checkpoint để resume đúng chunk lỗi.

### Summary/model-info/model-list

Dùng active provider và policy chung. Không dùng helper OpenAI cũ để bỏ qua Cloudflare/Vercel header. Model info phải từ chối model không thuộc provider active.

## Pha 6 — sửa checkpoint

Sửa services/checkpoint_service.py và core/executor.py.

Checkpoint identity phải gồm:

- project/file;
- source SHA-256;
- chunker version;
- chunk size;
- provider id/kind;
- normalized base URL;
- model;
- prompt/glossary fingerprint;
- checkpoint schema version.

Không resume checkpoint nếu identity mismatch. Đổi provider/model/prompt/chunk size phải tạo session mới.

Không dùng done_count làm next index. Tìm pending index nhỏ nhất hoặc lưu trạng thái từng chunk chính xác; xử lý trường hợp done rows không liên tục.

Không lưu error/empty/partial vào trạng thái done.

Khi fail:

- giữ checkpoint với status failed và error metadata;
- chunk thành công trước đó có thể resume;
- chunk lỗi phải được gọi lại;
- force_retranslate phải xóa đúng checkpoint của session hiện tại.

Đảm bảo output không bị ghi như hoàn tất khi chỉ có partial chunks.

## Pha 7 — sửa Translation Memory

Sửa services/translation_memory.py và các route TM.

- chỉ add_translation sau response success đã validate;
- không lưu empty/error/partial;
- xác định rõ TM provider-neutral hay gắn provider/model/prompt;
- khuyến nghị thêm metadata provider/model/prompt fingerprint;
- project clear/stats/find phải dùng đúng TM path mà executor sử dụng;
- không nhầm global singleton TM với project TM.

Test phải chứng minh clear project A không xóa/match dữ liệu của project B.

## Pha 8 — sửa rate limiter

Sửa services/api_service.py nếu cần.

- quota/rate limit mới dùng cooldown/backoff;
- 401/403/404/400/422 không được xử lý như quota;
- một gateway token không được retry nhiều lần chỉ vì key rotation;
- retry budget phải gắn theo request/session/provider;
- log safe error, không log secret hoặc full response body.

## Pha 9 — test bắt buộc

Thêm test không dùng network thật cho:

1. classify Cloudflare/Vercel/OpenAI/unknown;
2. Cloudflare header theo credential mode;
3. Vercel chỉ dùng Authorization;
4. model validation và namespace;
5. HTTP 401/404 tạo typed error;
6. _call_api không biến 401/404 thành empty;
7. empty response thật mới tăng empty counter;
8. 401 không retry ba lần cùng key;
9. 429 rồi success có backoff;
10. checkpoint identity đổi theo provider/model/source/prompt/chunk size;
11. checkpoint resume đúng pending chunk;
12. error/empty không vào checkpoint done;
13. TM clear đúng path;
14. error/empty không vào TM;
15. direct translation truyền active provider;
16. legacy worker không âm thầm dùng Gemini;
17. spellcheck không báo complete giả;
18. model listing không làm hỏng runtime model selection.

Integration fake client:

- 401, 401 => auth_error;
- 404 => model_not_found;
- 429 rồi success => success;
- 200 empty rồi success => upstream empty retry rồi success;
- fail chunk 2, chạy lại => resume 0/1 và gọi lại 2;
- đổi Cloudflare sang Vercel => không resume checkpoint cũ;
- clear TM project A => project B không đổi.

Smoke test thật chỉ chạy sau khi credential đã rotate và cấu hình lại. Gọi riêng GET /models và POST /chat/completions. Log status/schema/request id/model/hostname, không log secret.

## Pha 10 — verification và bàn giao

Chạy formatter/linter nếu dự án có. Chạy test targeted trước, sau đó test suite phù hợp.

Kiểm tra:

- mọi entry point đều dùng resolver;
- không còn default Gemini khi active provider là gateway;
- 401/404 không còn xuất hiện dưới dạng empty_response;
- empty thật được phân biệt;
- checkpoint không resume chéo provider/model;
- TM clear đúng path;
- project/direct/spellcheck/summary/model-list cùng hành xử.

Chạy gitnexus_detect_changes() trước commit. Nếu diff có symbol/process ngoài phạm vi, dừng và rà soát. Báo cáo cuối phải gồm:

- files đã sửa;
- tests đã chạy;
- provider policy đã hỗ trợ;
- status/error taxonomy;
- checkpoint/TM behavior;
- secret scan/rotation status;
- rủi ro còn lại.
