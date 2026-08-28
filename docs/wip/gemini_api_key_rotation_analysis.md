# Báo cáo Phân tích Chuyên sâu: Tính năng Xoay vòng Gemini API Key

**Dự án:** Novel-Translator  
**Ngày lập:** 2026-08-27  
**Phạm vi:** Phân tích toàn diện kiến trúc, luồng logic, giải thuật xoay vòng API Key, đánh giá hạn chế và đề xuất tối ưu hóa tính năng mới cho hệ thống quản lý Gemini API Key.  
**Tập tin liên quan trong mã nguồn:**
- [`services/api_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/api_service.py) (`ApiManager`, `AdaptiveRateLimiter`, `GlobalRPMRateLimiter`)
- [`plugins/translation/translator.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/plugins/translation/translator.py) (`_call_api`, `_get_client`, `robust_translate`, `_client_cache`)
- [`services/genai_client.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/genai_client.py) (`GenAIClient`)
- [`core/executor.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/core/executor.py) (`TranslationExecutor`)
- [`backend/infrastructure/providers/provider_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/backend/infrastructure/providers/provider_service.py) (`ProviderService`)
- [`backend/infrastructure/config/api_key_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/backend/infrastructure/config/api_key_service.py) (`ApiKeyService`)
- [`tests/unit/test_api_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/tests/unit/test_api_service.py)

---

## 1. Tổng quan Kiến trúc & Cơ chế Hoạt động

Trong quá trình dịch các tác phẩm tiểu thuyết/văn bản dung lượng lớn, việc sử dụng Gemini API (đặc biệt là gói **Free Tier**) thường xuyên đối mặt với các giới hạn nghiêm ngặt từ Google:
- **15 RPM** (Requests Per Minute - Giới hạn toàn cục trên IP/Tài khoản).
- **1,500 RPD** (Requests Per Day - Giới hạn cho từng API Key đối với các model Flash chuẩn, hoặc 20-50 RPD đối với một số model Preview thử nghiệm).
- **1,000,000 TPM** (Tokens Per Minute).

Để đạt được hiệu suất dịch liên tục, hệ thống **Novel-Translator** đã xây dựng một kiến trúc quản lý và xoay vòng API Key đa tầng:

```
                  ┌───────────────────────────────────────────────────────────┐
                  │                 config/providers.json                     │
                  │   (Lưu trữ danh sách API Keys của Provider "gemini")      │
                  └─────────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
                  ┌───────────────────────────────────────────────────────────┐
                  │            ProviderService / ApiKeyService                │
                  │             (Nạp cấu hình & danh sách keys)               │
                  └─────────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
                  ┌───────────────────────────────────────────────────────────┐
                  │                   TranslationExecutor                     │
                  │         (Khởi tạo ApiManager cho phiên dịch)              │
                  └─────────────────────────────┬─────────────────────────────┘
                                                │
                                                ▼
         ┌─────────────────────────────────────────────────────────────────────────┐
         │                               ApiManager                                │
         │   ┌───────────────────────────┐     ┌───────────────────────────────┐   │
         │   │   GlobalRPMRateLimiter    │     │      AdaptiveRateLimiter      │   │
         │   │   - Sliding Window 60s    │     │  - Theo dõi RPD/TPD từng Key  │   │
         │   │   - Giới hạn 15 RPM IP    │     │  - Quản lý Cooldown & Retry   │   │
         │   └───────────────────────────┘     │  - Chiến lược Least-Used / RR │   │
         │                                     └───────────────────────────────┘   │
         └──────────────────────────────────────┬──────────────────────────────────┘
                                                │
                                                ▼
         ┌─────────────────────────────────────────────────────────────────────────┐
         │                    plugins/translation/translator.py                    │
         │   1. api_manager.acquire_rpm() ──► Chờ token RPM toàn cục              │
         │   2. api_manager.get_next_available_key() ──► Chọn key tối ưu           │
         │   3. _get_client(key) ──► Lấy GenAIClient từ _client_cache             │
         │   4. client.generate_content() ──► Gửi request sang Google             │
         │   5. Phân loại kết quả:                                                │
         │      ├── Thành công: api_manager.mark_success(key)                      │
         │      └── Thất bại: api_manager.handle_api_error(key, error)             │
         └─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Chi tiết Các Thành phần Tham gia

### 2.1. `ProviderService` & `ApiKeyService` (Lớp Lưu trữ & Cấu hình)
- **Nhiệm vụ:** Lưu trữ và quản lý danh sách `api_keys` dạng mảng JSON trong `config/providers.json`.
- **Đặc điểm:** Hỗ trợ lưu nhiều key cho provider `gemini`. Cung cấp phương thức `load_gemini_keys()` và `get_active_provider_config()`.

### 2.2. `ApiManager` (Lớp Điều phối Trung tâm)
- **Nhiệm vụ:** Đóng vai trò là đầu mối duy nhất (Facade/Coordinator) mà lớp `TranslationExecutor` và `translator.py` tương tác.
- **Khởi tạo:**
  - Nhận danh sách `api_keys: List[str]`.
  - Tự động truy vấn cấu hình từ `ProviderService` để lấy `max_rpm` (mặc định 15) và `rpd_per_key` (mặc định 1,500 cho Gemini, 1,000,000 cho OpenAI).
  - Khởi tạo đồng thời `GlobalRPMRateLimiter` và `AdaptiveRateLimiter`.
  - Hỗ trợ chọn chiến lược xoay key: `least_used` (mặc định) hoặc `round_robin`.

### 2.3. `GlobalRPMRateLimiter` (Điều tiết Tốc độ Toàn cục)
- **Nhiệm vụ:** Đảm bảo toàn bộ ứng dụng (cho dù có bao nhiêu key hay bao nhiêu luồng) không gửi quá `max_rpm` requests trong bất kỳ cửa sổ 60 giây nào.
- **Mục đích:** Ngăn chặn việc Google chặn IP (IP-level rate limit) khi xoay vòng nhiều key cùng lúc.

### 2.4. `AdaptiveRateLimiter` (Quản lý Hạn mức & Cooldown Từng Key)
- **Nhiệm vụ:** Theo dõi độc lập từng API key:
  - Số lượt gọi trong ngày (`daily_usage: Dict[str, int]`).
  - Số token sử dụng trong ngày (`daily_tokens: Dict[str, int]`).
  - Số lần lỗi liên tiếp (`failure_count: Dict[str, int]`).
  - Thời điểm hết cooldown (`cool_down_until: Dict[str, float]`).
  - Ngày reset quota gần nhất (`last_reset_date: str`).
- **Ra quyết định:** Xác định key nào được phép dùng, tính toán thời gian chờ (delay) hoặc thời gian cách ly (cooldown).

### 2.5. `GenAIClient` & `_client_cache` (Lớp Giao tiếp SDK)
- **Nhiệm vụ:** Đóng gói thư viện `google-genai` mới của Google.
- **Client Pooling:** Module `translator.py` duy trì một từ điển toàn cục `_client_cache` ánh xạ `hash(key, config) -> GenAIClient` nhằm tránh overhead khởi tạo lại đối tượng client ở mỗi chunk.

---

## 3. Diễn giải Chi tiết Logic & Giải thuật Xoay vòng

### 3.1. Giải thuật Lựa chọn Key (`Key Selection Algorithm`)

Hệ thống cung cấp hai chiến lược lựa chọn key trong hàm `ApiManager.get_next_available_key()`:

#### A. Chiến lược `least_used` (Mặc định & Khuyến nghị)
Chiến lược này nhằm cân bằng tải tối đa trên toàn bộ danh sách key, ưu tiên sử dụng các key còn nhiều quota ngày nhất.

1. **Bước 1 — Lọc danh sách khả dụng (`get_available_keys`):**
   - Gọi `_check_daily_reset()` để kiểm tra sang ngày mới.
   - Duyệt qua toàn bộ danh sách `all_keys`.
   - **Bỏ qua** nếu key đang trong thời gian cooldown:
     $$\text{current\_time} < \text{cool\_down\_until}[key]$$
   - **Bỏ qua** nếu key đã đạt giới hạn gọi trong ngày:
     $$\text{daily\_usage}[key] \ge \text{daily\_limit}$$
   - Trả về danh sách `available_keys`. Nếu rỗng $\rightarrow$ Trả về `None` (hết key khả dụng).

2. **Bước 2 — Tìm mức sử dụng nhỏ nhất:**
   $$\text{min\_usage} = \min_{k \in \text{available\_keys}} (\text{daily\_usage}.get(k, 0))$$

3. **Bước 3 — Thu thập ứng viên (Candidates):**
   $$\text{candidates} = \{k \in \text{available\_keys} \mid \text{daily\_usage}[k] = \text{min\_usage}\}$$

4. **Bước 4 — Khử thiên lệch (Tie-breaking via Round-Robin Offset):**
   Khi có nhiều key có cùng mức `min_usage` (ví dụ đầu ngày khi tất cả đều bằng 0), nếu chỉ lấy phần tử đầu tiên `candidates[0]`, key đầu sẽ bị gọi liên tục nhiều lần trước khi sang key thứ hai. Hệ thống giải quyết bằng biến offset:
   $$\text{chosen\_key} = \text{candidates}[\text{\_round\_robin\_offset} \pmod{|\text{candidates}|}]$$
   $$\text{\_round\_robin\_offset} \leftarrow \text{\_round\_robin\_offset} + 1$$

#### B. Chiến lược `round_robin` (Tuần tự cổ điển)
- Duyệt tuần tự theo chỉ số `_current_key_index` qua mảng `_key_list`.
- Kiểm tra trạng thái `available`, `cool_down_until` và `daily_limit`.
- Key đầu tiên thỏa mãn sẽ được chọn; `_current_key_index` tăng lên 1 (modulo độ dài danh sách).

---

### 3.2. Giải thuật Điều tiết RPM Toàn cục (`Global RPM Sliding Window`)

`GlobalRPMRateLimiter` sử dụng cấu trúc dữ liệu hàng đợi hai đầu (`collections.deque`) để hiện thực giải thuật **Sliding Window Log**:

```
 Thời gian: t - 60s                                                     t (Hiện tại)
    ├───────────┼───────────┼───────────┼───────────┼───────────┼───────────┤
    │ [Request] │ [Request] │           │ [Request] │ [Request] │ [Mới]     │
    └───────────┴───────────┴───────────┴───────────┴───────────┴───────────┘
         ▲
         │ (Tự động popleft() nếu timestamp < t - 60s)
```

1. **Dọn dẹp log cũ (`_clean_old_requests`):**
   - Lấy `cutoff = current_time - 60.0`.
   - Vòng lặp: nếu `_request_times[0] < cutoff` thì thực hiện `_request_times.popleft()`.

2. **Xin cấp quyền gọi (`acquire`):**
   - Nếu `len(_request_times) < max_rpm`:
     - Thêm `current_time` vào cuối deque: `_request_times.append(current_time)`.
     - Tăng `_total_requests += 1`.
     - Trả về `True`.
   - Nếu `len(_request_times) >= max_rpm`:
     - Nếu `blocking=False`: Trả về `False` ngay lập tức.
     - Nếu `blocking=True`: Ngủ `0.1s` (`time.sleep(0.1)`), sau đó lặp lại quy trình cho đến khi thành công hoặc vượt quá `timeout` (mặc định 60-120s).

---

### 3.3. Giải thuật Phân loại Lỗi & Tính toán Cooldown Thích ứng (`Adaptive Error Handling`)

Khi API trả về lỗi, hàm `AdaptiveRateLimiter.should_retry(api_key, error)` thực hiện phân tích chuỗi thông điệp lỗi và quyết định chiến lược xử lý theo 4 nhóm:

```mermaid
flowchart TD
    Start[Bắt đầu: Nhận Error từ API] --> CheckExpired[Kiểm tra Cooldown cũ & Reset Daily]
    CheckExpired --> MatchError{Phân loại Lỗi}

    MatchError -- "429 / Quota / Resource_Exhausted" --> CheckQuotaType{Có chứa 'quota' hoặc 'resource_exhausted'?}
    CheckQuotaType -- Có (Hết hạn mức ngày) --> ActionQuota[Set Cooldown = now + 1800s (30m)\nReturn: should_retry=False, delay=0\nChuyển ngay sang Key khác]
    CheckQuotaType -- Không (Rate limit tạm thời) --> CheckRetryCount{failure_count > 8?}
    CheckRetryCount -- Có --> ActionRateLimitLong[Set Cooldown = now + 1800s\nReturn: should_retry=False, delay=1800]
    CheckRetryCount -- Không --> ActionBackoff[Progressive Backoff:\ndelay = min(30 * 2^(f-1), 300)s\nReturn: should_retry=True, delay]

    MatchError -- "API_KEY_INVALID / PERMISSION_DENIED / UNAUTHENTICATED" --> ActionDeadKey[Key chết vĩnh viễn:\nSet Cooldown = now + 86400s (24h)\nReturn: should_retry=False, delay=0\nLoại bỏ khỏi phiên dịch]

    MatchError -- "Timeout / Deadline / Connection" --> CheckNetFailures{failure_count > 5?}
    CheckNetFailures -- Có --> ActionNetLong[Set Cooldown = now + 300s (5m)\nReturn: should_retry=False, delay=300]
    CheckNetFailures -- Không --> ActionNetShort[delay = min(10 * f, 60)s\nReturn: should_retry=True, delay]

    MatchError -- "Lỗi Khác" --> CheckOtherFailures{failure_count > 3?}
    CheckOtherFailures -- Có --> ActionOtherFail[Return: should_retry=False, delay=0]
    CheckOtherFailures -- Không --> ActionOtherRetry[Return: should_retry=True, delay=5.0s]
```

#### Ma trận Phân loại Lỗi & Hành vi Chi tiết:

| Nhóm lỗi | Mẫu từ khóa nhận diện | Hành vi xử lý | Thời gian chờ (`delay`) | Thời gian Cooldown |
| :--- | :--- | :--- | :--- | :--- |
| **Cạn Quota Ngày** | `quota`, `resource_exhausted` | Chuyển key lập tức, không retry key hiện tại | `0s` (Không chờ) | **30 phút** (`1800s`) |
| **Vượt Rate Limit Tạm thời** | `rate limit`, `429` | Progressive Exponential Backoff ($f \le 8$) | $\min(30 \times 2^{f-1}, 300)\text{s}$ (30s, 60s, 120s, 240s, 300s) | Không cooldown (nếu $f \le 8$), Cooldown **30 phút** (nếu $f > 8$) |
| **Key Hỏng / Sai Quyền** | `api_key_invalid`, `api key not found`, `invalid api key`, `permission_denied`, `unauthenticated` | Đánh dấu key chết, loại bỏ ngay khỏi phiên dịch | `0s` (Không chờ) | **24 giờ** (`86400s`) |
| **Lỗi Mạng / Timeout** | `timeout`, `deadline`, `connection` | Tuyến tính ngắn ($f \le 5$) | $\min(10 \times f, 60)\text{s}$ (10s, 20s, 30s, 40s, 50s, 60s) | Không cooldown (nếu $f \le 5$), Cooldown **5 phút** (nếu $f > 5$) |
| **Lỗi Khác** | Ngoại lệ chung | Retry tối đa 3 lần | `5.0s` | Không |

---

### 3.4. Vòng đời Xử lý Request Hoàn chỉnh (`Request Lifecycle`)

Trong hàm `_call_api()` (`plugins/translation/translator.py`):
1. **Số lần thử tối đa:** `max_attempts_total = max(3, len(api_keys) * 3)`.
2. **Kiểm tra Dừng Khẩn cấp:** `check_emergency_stop()`.
3. **Giữ nhịp RPM:** `api_manager.acquire_rpm(blocking=True, timeout=120.0)`.
4. **Lấy Key:** `api_key = api_manager.get_next_available_key()`. Nếu không có key và `all_keys_exhausted() == True` $\rightarrow$ Trả về mã dừng `"all_keys_exhausted"`.
5. **Gọi API:** Sử dụng `_get_client(api_key, config)` và gọi `client.generate_content(...)`.
6. **Xử lý phản hồi:**
   - **Thành công:** Gọi `api_manager.mark_success(api_key)`. Trạng thái này sẽ:
     - Reset `failure_count[api_key] = 0`.
     - Tăng `daily_usage[api_key] += 1`.
     - Xóa `cool_down_until[api_key]`.
     - Trả về kết quả dịch.
   - **Empty Response:** Tăng `empty_streak`. Nếu bị 2 lần liên tiếp $\rightarrow$ Ngắt sớm với trạng thái `"upstream_empty"`.
   - **Ngoại lệ API / Lỗi:** Gọi `should_retry, delay = api_manager.handle_api_error(api_key, error)`.
     - Nếu `should_retry == True`: `time.sleep(delay)` và thử lại.
     - Nếu `should_retry == False`: Bỏ qua key hiện tại, tiếp tục vòng lặp để lấy key kế tiếp từ `get_next_available_key()`.

---

## 4. Đánh giá Hiện trạng: Điểm mạnh & Điểm nghẽn (Limitations)

### 4.1. Điểm mạnh
- **Bảo vệ IP 2 tầng:** Kết hợp đồng thời Rate Limit cấp độ IP (`GlobalRPMRateLimiter`) và cấp độ Key (`AdaptiveRateLimiter`), ngăn triệt để nguy cơ bị Google gắn cờ/chặn IP.
- **Xử lý lỗi thông minh (Fail-fast & Adaptive):** Khi phát hiện key chết (400/401/403) hoặc cạn quota ngày (Resource Exhausted), hệ thống loại bỏ hoặc cách ly key ngay lập tức (`delay=0`), chuyển sang key khác trong danh sách mà không làm gián đoạn thời gian chờ của người dùng.
- **Khử thiên lệch tải:** Thuật toán `least_used` kết hợp Round-Robin offset giúp phân phối đều khối lượng công việc, tránh tình trạng "vắt kiệt" key đầu tiên trong danh sách.
- **Tương thích đa luồng:** Sử dụng `threading.Lock` tại tất cả các cấu trúc dữ liệu dùng chung (`_keys`, `_request_times`, `daily_usage`, `cool_down_until`).

---

### 4.2. Các Điểm nghẽn & Rủi ro Kỹ thuật Hiện hữu

| Mức độ | Vấn đề | Vị trí mã nguồn | Phân tích chi tiết |
| :--- | :--- | :--- | :--- |
| **P0 (Critical)** | **Trạng thái Rate Limiter chỉ lưu In-Memory (Ephemeral State)** | [`services/api_service.py:117-121`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/api_service.py#L117-L121) | Toàn bộ `daily_usage`, `cool_down_until`, `failure_count` chỉ tồn tại trong RAM của instance `AdaptiveRateLimiter`. Khi khởi động lại ứng dụng, WebUI restart, hoặc mỗi lần CLI khởi tạo `TranslationExecutor` mới, toàn bộ lịch sử quota bị xóa sạch. Key chết (invalid) hoặc key vừa hết quota sẽ bị gọi lại từ đầu. |
| **P1 (High)** | **Lệch Múi giờ Reset Quota (Timezone Mismatch)** | [`services/api_service.py:127-133`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/api_service.py#L127-L133) | Code reset `daily_usage` vào **00:00 UTC** (`datetime.now(timezone.utc)`). Tuy nhiên, Google Gemini API reset hạn mức ngày vào **Midnight Pacific Time (PT / PST / PDT)** (tương đương 07:00 hoặc 08:00 UTC, tức 14:00-15:00 giờ Việt Nam). Việc reset sớm hơn Google 7-8 tiếng khiến ứng dụng nghĩ key đã hồi phục nhưng thực chất Google vẫn trả về `429 RESOURCE_EXHAUSTED`. |
| **P1 (High)** | **Không có Cơ chế Pre-validation / Health Check Chủ động** | [`backend/infrastructure/providers/provider_service.py`](file:///Users/narga/Briefcase/Projects/Novel-Translator/backend/infrastructure/providers/provider_service.py) | Khi người dùng nhập 10-20 API key trong giao diện Cài đặt, hệ thống chỉ lưu chuỗi string mà không có cơ chế "Test All Keys". Khi bắt đầu dịch, nếu có key nhập sai cú pháp hoặc bị revoke, runtime phải chờ đến lượt key đó gặp lỗi runtime thì mới loại bỏ. |
| **P2 (Medium)** | **Kiểm soát TPD/TPM chưa được Enforce trong `get_available_keys`** | [`services/api_service.py:280-300`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/api_service.py#L280-L300) | `AdaptiveRateLimiter` có trường `daily_tokens` và `daily_token_limit`, nhưng hàm `get_available_keys()` chỉ kiểm tra `daily_usage >= daily_limit` mà **bỏ quên** `daily_tokens >= daily_token_limit`. Ngoài ra, chưa có cơ chế kiểm soát TPM (Tokens Per Minute) theo sliding window. |
| **P2 (Medium)** | **Cấu hình Phẳng, Chưa Hỗ trợ Trộn Key (Hybrid Free & Paid Tiers)** | [`services/api_service.py:388-400`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/api_service.py#L388-L400) | Hệ thống áp đặt một tham số chung `rpd_per_key` (1500) và `max_rpm` (15) cho toàn bộ danh sách key của Gemini. Nếu người dùng sở hữu đồng thời 5 Free Keys (15 RPM / 1500 RPD) và 1 Paid Key (1000 RPM / Pay-as-you-go), hệ thống không thể định tuyến ưu tiên hoặc phân bổ tải theo trọng số. |
| **P3 (Low)** | **Chưa Bóc tách Header `Retry-After` Động** | [`services/api_service.py:180-207`](file:///Users/narga/Briefcase/Projects/Novel-Translator/services/api_service.py#L180-L207) | Khi Google trả về lỗi 429, metadata lỗi thường kèm thời gian khuyến nghị (ví dụ: `Please retry after 12s`). Hiện tại hệ thống đang hardcode bước nhảy số mũ ($30\text{s} \rightarrow 300\text{s}$), có thể gây lãng phí thời gian chờ không cần thiết. |

---

## 5. Đề xuất Tối ưu hóa & Thiết kế Tính năng Mới

Dưới đây là 7 đề xuất nâng cấp toàn diện cho hệ thống xoay vòng Gemini API Key, chia theo mức độ ưu tiên:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│               LỘ TRÌNH ĐỀ XUẤT NÂNG CẤP HỆ THỐNG XOAY VÒNG KEY               │
├─────────────────────────────────────────────────────────────────────────────┤
│  [Giai đoạn 1: Ổn định & Độ chính xác]                                      │
│  ├── 1. Key Pool State Persistence (Lưu trạng thái hạn ngạch liên phiên)    │
│  ├── 2. Chuẩn hóa Múi giờ Reset theo Google Pacific Time (PT)               │
│  └── 3. Hoàn thiện Ràng buộc Hạn ngạch Token (TPD & TPM Sliding Window)     │
│                                                                             │
│  [Giai đoạn 2: Trải nghiệm & Tự động hóa]                                   │
│  ├── 4. Active Health Check & Key Benchmark Suite (CLI + WebUI)             │
│  └── 5. Bóc tách Thông minh Retry-After từ Metadata phản hồi                │
│                                                                             │
│  [Giai đoạn 3: Mở rộng Doanh nghiệp & Quản trị Nâng cao]                     │
│  ├── 6. Định tuyến Đa tầng (Hybrid Tier & Priority Weighted Routing)        │
│  └── 7. Bảng điều khiển Giám sát Key Trực quan (Real-time Key Dashboard)    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Đề xuất 1: Key Pool State Persistence (Lưu trữ Trạng thái Quota Liên phiên)
- **Mục tiêu:** Đảm bảo khi khởi động lại ứng dụng hoặc chuyển đổi giữa các dự án dịch thuật, trạng thái hạn mức (`daily_usage`, `daily_tokens`, `cool_down_until`, `status`) của từng key được bảo toàn.
- **Giải pháp kỹ thuật:**
  - Tạo tệp lưu trữ trạng thái `config/key_state.json` (hoặc bảng SQLite trong `workspace/translator.db`).
  - Cấu trúc dữ liệu đề xuất:
    ```json
    {
      "version": 1,
      "last_reset_date_pt": "2026-08-27",
      "keys": {
        "AIzaSyD...xxxx": {
          "status": "active",
          "daily_usage": 342,
          "daily_tokens": 1250400,
          "failure_count": 0,
          "cooldown_until": 0,
          "last_used": "2026-08-27T19:10:00Z",
          "tier": "free",
          "label": "Acc phụ 01"
        },
        "AIzaSyB...yyyy": {
          "status": "cooldown",
          "daily_usage": 1500,
          "daily_tokens": 4200000,
          "failure_count": 1,
          "cooldown_until": 1787865600,
          "last_used": "2026-08-27T18:45:00Z",
          "tier": "free",
          "label": "Acc chính"
        }
      }
    }
    ```
  - Khi khởi tạo `ApiManager`, nạp dữ liệu từ `key_state.json`. Mỗi khi gọi `mark_success()` hoặc `handle_api_error()`, cập nhật trạng thái với cơ chế debounced write (ghi theo chu kỳ hoặc khi dừng phiên) để tối ưu I/O.

---

### Đề xuất 2: Chuẩn hóa Múi giờ Reset Quota theo Google Pacific Time (PT)
- **Mục tiêu:** Đồng bộ chính xác thời điểm reset hạn mức ngày với hệ thống máy chủ Google.
- **Giải pháp kỹ thuật:**
  - Thay thế `timezone.utc` bằng múi giờ Pacific của Mỹ (`America/Los_Angeles`), tự động xử lý giờ mùa đông (PST - UTC-8) và giờ mùa hè (PDT - UTC-7):
    ```python
    try:
        from zoneinfo import ZoneInfo
        PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
    except ImportError:
        # Fallback cho môi trường không có tzdata
        from datetime import timezone, timedelta
        PACIFIC_TZ = timezone(timedelta(hours=-7))

    def _get_current_pacific_date() -> str:
        return datetime.now(PACIFIC_TZ).strftime("%Y-%m-%d")
    ```

---

### Đề xuất 3: Active Key Health Check & Benchmark Suite
- **Mục tiêu:** Cho phép người dùng kiểm tra nhanh chất lượng toàn bộ danh sách API key trước khi bấm nút dịch.
- **Giải pháp kỹ thuật:**
  - Bổ sung endpoint backend `POST /api/keys/check-health` và lệnh CLI `python cli.py check-keys`.
  - Thực hiện kiểm tra bất đồng bộ (`asyncio` hoặc thread pool song song):
    1. **Format Validation:** Kiểm tra tiền tố (`AIzaSy...`) và độ dài chuỗi (39 ký tự).
    2. **Auth & Permission Ping:** Gửi 1 token request siêu nhẹ (`model="gemini-2.5-flash"`, `prompt="ping"`, `max_output_tokens=1`).
    3. **Đo độ trễ (Latency Rating):** Đo thời gian phản hồi (ms) của từng key.
    4. **Phân loại trạng thái:**
       - 🟢 `HEALTHY` (Key hoạt động tốt, latency < 800ms).
       - 🟡 `RATE_LIMITED` (Đang bị 429 tạm thời).
       - 🟠 `QUOTA_EXHAUSTED` (Key hết hạn ngạch ngày).
       - 🔴 `DEAD / INVALID` (Key bị xóa, sai token, hoặc không có quyền).
  - Tự động gợi ý loại bỏ hoặc vô hiệu hóa các key trạng thái 🔴 khỏi `providers.json`.

---

### Đề xuất 4: Định tuyến Đa tầng (Hybrid Tier & Priority Weighted Routing)
- **Mục tiêu:** Tối ưu hóa chi phí và tốc độ dịch khi người dùng kết hợp cả **Free Keys** và **Paid/Pay-as-you-go Keys**.
- **Giải pháp kỹ thuật:**
  - Cho phép cấu hình thuộc tính `tier` cho từng key trong `providers.json`:
    - `tier: "free"`: Giới hạn 15 RPM / 1500 RPD.
    - `tier: "paid"`: Giới hạn 1000 RPM / Không giới hạn RPD.
  - Cung cấp các chế độ định tuyến (Routing Modes):
    1. **Cost-Saver (Tiết kiệm tối đa - Mặc định):** Sử dụng 100% các Free Keys trước. Khi toàn bộ Free Keys rơi vào cooldown hoặc cạn quota ngày $\rightarrow$ Tự động kích hoạt Paid Key để dịch tiếp mà không bị gián đoạn.
    2. **Performance-Boost (Tối đa tốc độ):** Phân bổ request theo trọng số (Weighted Least-Used). Ví dụ: Paid key nhận 80% tải, các Free key chia nhau 20% tải còn lại.
    3. **Tier-Isolated:** Chỉ sử dụng nhóm key được chỉ định.

---

### Đề xuất 5: Hoàn thiện Hạn ngạch Token (TPD & TPM Sliding Window Limiter)
- **Mục tiêu:** Ngăn chặn lỗi `RESOURCE_EXHAUSTED` do vượt quá số token cho phép mỗi phút (TPM) hoặc mỗi ngày (TPD), đặc biệt khi dịch các chương truyện có ngữ cảnh dài (`previous_chunk_context` lớn).
- **Giải pháp kỹ thuật:**
  - Cập nhật hàm `get_available_keys()` để kiểm tra đồng thời cả 2 điều kiện:
    ```python
    # Bỏ qua nếu vượt quá Request Limit
    if self.daily_usage.get(key, 0) >= self.daily_limit:
        continue
    # Bỏ qua nếu vượt quá Token Limit (nếu có cấu hình)
    if self.daily_token_limit > 0 and self.daily_tokens.get(key, 0) >= self.daily_token_limit:
        continue
    ```
  - Bổ sung `GlobalTPMRateLimiter` (sử dụng Sliding Window lưu `(timestamp, token_count)`) song hành với `GlobalRPMRateLimiter`.

---

### Đề xuất 6: Bóc tách Thông minh `Retry-After` từ Error Metadata
- **Mục tiêu:** Giảm thiểu thời gian chờ vô ích bằng cách đọc trực tiếp khuyến nghị từ máy chủ Google thay vì sử dụng bước nhảy số mũ cố định.
- **Giải pháp kỹ thuật:**
  - Khi bắt được ngoại lệ `google.genai.errors.APIError` hoặc `ClientError`:
    ```python
    def _extract_retry_after(error: Exception) -> Optional[float]:
        # 1. Trích xuất từ HTTP response headers nếu có
        if hasattr(error, 'response') and error.response:
            retry_header = error.response.headers.get('Retry-After')
            if retry_header:
                try:
                    return float(retry_header)
                except ValueError:
                    pass
        # 2. Parse thông điệp chi tiết bằng Regex (ví dụ: "Please retry after 14.5s")
        match = re.search(r"retry after ([\d\.]+)s", str(error), re.IGNORECASE)
        if match:
            return float(match.group(1))
        return None
    ```
  - Nếu trích xuất được `retry_after`, gán thời gian cooldown chính xác:
    $$\text{delay} = \text{retry\_after} + 1.0\text{s (safety buffer)}$$

---

### Đề xuất 7: Bảng Điều khiển Giám sát Key Trực quan (Real-time Key Pool Dashboard)
- **Mục tiêu:** Cung cấp trải nghiệm trực quan, minh bạch cho người dùng trên WebUI về tình trạng tài nguyên API.
- **Giải pháp kỹ thuật:**
  - Bổ sung widget "API Key Pool Monitor" trong tab Cài đặt hoặc ngay góc trên thanh trạng thái tiến trình dịch:
    - **Thanh tổng quan:** Tổng số key, Số key đang sẵn sàng (Active), Số key đang Cooldown, Số key Hỏng.
    - **Bảng chi tiết từng Key:**
      - 4 ký tự cuối của Key (ví dụ: `...X9zB`).
      - Nhãn định danh (Acc 1, Acc 2,...).
      - Progress bar thể hiện % RPD đã dùng (ví dụ: `450 / 1500 (30%)`).
      - Đồng hồ đếm ngược Cooldown (nếu đang bị rate limit: `Hồi phục sau: 04:32`).
      - Nút bấm thủ công: "Reset Cooldown", "Kiểm tra lại", "Vô hiệu hóa".

---

## 6. Bảng Tổng hợp So sánh & Ma trận Đánh giá Đề xuất

| STT | Tên Đề xuất | Lợi ích Chính | Độ phức tạp | Mức độ Ưu tiên |
| :---: | :--- | :--- | :---: | :---: |
| **1** | **Key State Persistence** | Giữ vững quota/cooldown qua các lần restart, không gọi lại key hỏng | Thấp - Trung bình | **P0 (Cần làm ngay)** |
| **2** | **Chuẩn hóa Reset Timezone (Pacific Time)** | Khớp 100% chu kỳ reset của Google, loại bỏ hoàn toàn lỗi 429 ảo | Thấp | **P0 (Cần làm ngay)** |
| **3** | **Enforce TPD & Token Sliding Window** | Chống tràn hạn ngạch Token trên các chunk văn bản lớn | Thấp | **P1 (Quan trọng)** |
| **4** | **Active Key Health Check Suite** | Lọc sạch key chết trước khi bắt đầu dịch, đo độ trễ mạng | Trung bình | **P1 (Quan trọng)** |
| **5** | **Dynamic Retry-After Parsing** | Rút ngắn thời gian chờ khi gặp rate limit tạm thời | Thấp | **P2 (Nên có)** |
| **6** | **Hybrid Tier & Weighted Routing** | Tối ưu chi phí khi kết hợp Free Key và Paid Key | Trung bình - Cao | **P2 (Nên có)** |
| **7** | **Visual Key Pool Dashboard (WebUI)** | Trực quan hóa trạng thái quota và đếm ngược cooldown | Trung bình | **P3 (Giai đoạn sau)** |

---

## 7. Kết luận

Cơ chế xoay vòng Gemini API Key hiện tại của dự án **Novel-Translator** đã được thiết kế bài bản với mô hình 2 tầng bảo vệ (**Global Sliding Window RPM** và **Per-Key Adaptive Rate Limiter**), sở hữu giải thuật phân loại lỗi và lựa chọn key `least_used` khử thiên lệch rất hiệu quả.

Tuy nhiên, hệ thống vẫn tồn tại 2 điểm yếu cốt lõi cần được xử lý sớm:
1. **Tính bền vững của dữ liệu:** Trạng thái key chỉ nằm trong bộ nhớ RAM, dẫn đến việc mất trắng dữ liệu quota/cooldown khi ứng dụng khởi động lại.
2. **Lệch múi giờ reset:** Chu kỳ reset ngày dùng UTC thay vì Pacific Time của Google.

Việc triển khai các giải pháp lưu trữ trạng thái (`Key State Persistence`), đồng bộ múi giờ Mỹ (`America/Los_Angeles`), bổ sung bộ công cụ kiểm tra sức khỏe key chủ động (`Health Check Suite`) và giao diện giám sát trực quan sẽ hoàn thiện tính năng xoay vòng key, mang lại sự ổn định và hiệu suất cao nhất cho toàn bộ hệ thống dịch truyện.
