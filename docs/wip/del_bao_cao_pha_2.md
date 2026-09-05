# Phase 2 – Đánh Giá Chất Lượng Mã Nguồn Và Đề Xuất Tiếp Theo

**Dự án:** Content Translator

**Phạm vi đánh giá:** Sau khi hoàn thành Phase 2 – Lean WebUI

**Ngày đánh giá:** 04/09/2026

**Trạng thái đánh giá:** Phase 2 đã đạt mục tiêu chính và có thể sử dụng thực tế. Tuy nhiên, nên thực hiện một giai đoạn ổn định hóa trước khi mở rộng nhiều tính năng mới trong Phase 3.

---

## 1. Kết Luận Tổng Quan

Phase 2 đã đưa dự án từ một công cụ CLI tối giản thành một ứng dụng có giao diện web phục vụ trực tiếp quy trình dịch nội dung.

Các khả năng chính hiện có gồm:

1. Cấu hình provider và model từ giao diện.
2. Quản lý API key.
3. Xoay API key khi provider trả về lỗi giới hạn.
4. Gửi nội dung tới nhiều loại provider.
5. Điều chỉnh timeout, retry, output token và thinking level.
6. Quản lý tài liệu trong workspace.
7. Đọc và hiển thị nội dung tài liệu.
8. Xử lý nội dung Markdown và HTML.
9. Hỗ trợ các luồng xử lý liên quan đến EPUB.
10. Tách một phần logic thành adapter, service và plugin.

### Đánh giá tổng thể

| Tiêu chí | Mức đánh giá |
|---|---|
| Bám sát mục tiêu sản phẩm | Tốt |
| Tính thực dụng | Tốt |
| Khả năng mở rộng provider | Khá tốt |
| Tách biệt các thành phần | Khá |
| Tính nhất quán của cấu hình | Trung bình khá |
| An toàn dữ liệu và secret | Khá, cần kiểm tra bổ sung |
| Khả năng kiểm thử | Chưa đủ chắc chắn |
| Khả năng xử lý lỗi | Khá, cần chuẩn hóa |
| Độ ổn định với request dài | Cần kiểm tra thêm |
| Mức sẵn sàng để bắt đầu Phase 3 | Có thể bắt đầu sau khi hoàn thành các mục ưu tiên cao của Phase 2.5 |

**Kết luận chính:** Không nên tiếp tục bổ sung nhiều tính năng lớn ngay lập tức. Nên dành một giai đoạn ngắn để ổn định hóa mã nguồn, thống nhất contract cấu hình, củng cố retry, kiểm thử end-to-end và rà soát bảo mật.

**Tên đề xuất cho giai đoạn này:** Phase 2.5 – Stabilization and Contract Hardening

---

## 2. Những Điểm Đã Làm Tốt

### 2.1. Giữ được định hướng sản phẩm gọn nhẹ

Dự án vẫn tập trung vào chu trình chính:

1. Nhập hoặc chọn nội dung nguồn.
2. Chia nội dung thành các chunk.
3. Tạo prompt.
4. Gửi tuần tự tới AI.
5. Nhận kết quả.
6. Ghép kết quả.
7. Hiển thị hoặc ghi ra file.

Đây là hướng phù hợp với mục tiêu ban đầu. Dự án chưa bị biến thành một hệ thống quản lý quy trình quá phức tạp.

Việc chưa đưa database workflow, queue phân tán hoặc cơ chế checkpoint nhiều tầng vào lõi là quyết định đúng ở giai đoạn hiện tại.

### 2.2. Tách provider là hướng kiến trúc phù hợp

Việc tách Gemini và OpenAI-compatible thành các adapter riêng giúp:

- Giảm sự phụ thuộc vào một provider.
- Cho phép thay đổi model dễ hơn.
- Giảm nguy cơ logic riêng của một provider ảnh hưởng tới provider khác.
- Tạo nền tảng cho việc bổ sung provider trong tương lai.

Đặc biệt, việc không truyền các tham số chỉ dành cho Gemini sang OpenAI-compatible là cách xử lý đúng.

### 2.3. Có các cấu hình thực tế cho request AI

Các tùy chọn như timeout, retry, output token, thinking level, temperature và delay đều phục vụ trực tiếp cho quá trình gửi nội dung.

Điều này hữu ích vì các provider khác nhau có:

- Thời gian phản hồi khác nhau.
- Giới hạn token khác nhau.
- Cách xử lý reasoning khác nhau.
- Mức độ ổn định khác nhau.

Việc đưa các giá trị này ra giao diện giúp người dùng không phải sửa mã nguồn khi thay đổi cách vận hành.

### 2.4. Có quan tâm đến lỗi provider

Cơ chế retry và xoay key là cải tiến cần thiết trong thực tế.

Một request có thể thất bại vì:

- Key tạm thời bị giới hạn.
- Provider quá tải.
- Mạng không ổn định.
- Proxy trả về lỗi tạm thời.
- Model cần thời gian xử lý dài.

Việc có thể thử lại theo cấu hình giúp hệ thống thực dụng hơn so với việc dừng ngay sau lỗi đầu tiên.

Tuy nhiên, chính sách retry cần được phân loại rõ hơn. Nội dung này được trình bày ở phần rủi ro kỹ thuật.

### 2.5. Có chú ý đến an toàn khi hiển thị nội dung

Việc xử lý và làm sạch Markdown hoặc HTML trước khi hiển thị là hướng đi đúng.

Nội dung tài liệu và nội dung AI trả về đều có thể chứa:

- Thẻ HTML.
- Liên kết.
- Đoạn script.
- Thuộc tính sự kiện.
- Nội dung không đáng tin cậy.

Vì vậy, không nên đưa trực tiếp dữ liệu chưa được kiểm soát vào giao diện.

Điểm này cần được áp dụng thống nhất cho:

- Nội dung tài liệu.
- Nội dung bản dịch.
- Nội dung EPUB.
- Nội dung preview.
- Thông báo lỗi có dữ liệu từ backend.

### 2.6. Giao diện tài liệu có trạng thái tương đối rõ ràng

Các trạng thái đang tải, không có tài liệu và lỗi tải giúp người dùng hiểu được ứng dụng đang làm gì.

Đây là điều quan trọng với các thao tác đọc file hoặc gửi request có thể mất nhiều thời gian.

---

## 3. Các Vấn Đề Chất Lượng Cần Xử Lý

### 3.1. Cấu hình chưa có một contract thống nhất

Hiện có nhiều cách đặt tên và nhiều tầng cấu hình khác nhau.

Ví dụ có thể xuất hiện các dạng tương đương cho cùng một giá trị:

- `PROCESSING.REQUEST_TIMEOUT_SECONDS`
- `request_timeout_seconds`
- `REQUEST_TIMEOUT_SECONDS`
- `RUNTIME.THINKING_LEVEL`
- `MODEL.THINKING_LEVEL`
- `max_retries_per_chunk`
- `MAX_RETRIES_PER_CHUNK`

Việc hỗ trợ tên cũ là cần thiết trong giai đoạn chuyển tiếp, nhưng nếu không có quy tắc chuẩn hóa rõ ràng sẽ tạo ra các rủi ro:

- Giao diện hiển thị một giá trị nhưng worker sử dụng giá trị khác.
- Config cũ ghi đè config mới ngoài dự kiến.
- Giá trị số được xử lý như chuỗi.
- Một provider nhận tham số không hỗ trợ.
- Giá trị âm hoặc quá lớn không bị phát hiện sớm.
- Người dùng không biết giá trị nào đang thực sự có hiệu lực.

**Đề xuất:**

Tạo một lớp hoặc module duy nhất để xử lý cấu hình. Module này cần thực hiện:

- Đọc cấu hình thô.
- Chuẩn hóa tên trường.
- Ép kiểu dữ liệu.
- Kiểm tra giá trị bắt buộc.
- Kiểm tra giới hạn tối thiểu và tối đa.
- Xác định thứ tự ưu tiên giữa config mới và config cũ.
- Tạo ra một cấu hình runtime thống nhất.

Không nên để từng module tự đọc trực tiếp các dictionary cấu hình.

Cấu hình sau khi chuẩn hóa nên được xem là bất biến trong suốt một phiên dịch.

### 3.2. Retry chưa phân biệt loại lỗi

Không phải lỗi nào cũng nên retry giống nhau.

**Những lỗi thường có thể retry:**

- Timeout.
- Lỗi kết nối tạm thời.
- HTTP 408.
- HTTP 429.
- HTTP 500.
- HTTP 502.
- HTTP 503.
- HTTP 504.

**Những lỗi thường không nên retry tự động:**

- API key không hợp lệ.
- Model không tồn tại.
- Không có quyền sử dụng model.
- Payload sai.
- Tham số không hợp lệ.
- Nội dung bị chặn bởi chính sách an toàn.
- Request vượt giới hạn cố định của provider.

Nếu retry tất cả lỗi như nhau, hệ thống có thể:

- Lãng phí thời gian.
- Gửi lại một request chắc chắn sẽ thất bại.
- Làm tăng số request không cần thiết.
- Làm người dùng khó biết nguyên nhân thật sự.

**Đề xuất phân loại lỗi theo ba nhóm:**

1. Nhóm 1: Retry lại cùng key.
2. Nhóm 2: Đổi key rồi retry.
3. Nhóm 3: Dừng ngay và báo lỗi.

Mỗi lỗi nên có các thuộc tính:

- Có thể retry hay không.
- Có cần đổi key hay không.
- Mã lỗi nội bộ.
- Thông báo dành cho người dùng.
- Thông tin kỹ thuật dành cho log.
- Mã HTTP nếu có.
- Tên provider.

### 3.3. Cần kiểm tra vòng đời HTTP client

Nếu mỗi lần gửi chunk hoặc mỗi lần retry đều tạo một HTTP client mới, hệ thống có thể:

- Tốn chi phí khởi tạo connection.
- Không tận dụng tốt connection pool.
- Khó quản lý việc đóng kết nối.
- Khó theo dõi request thống nhất.
- Khó gắn request ID cho toàn bộ phiên dịch.

Nên sử dụng HTTP client theo một trong hai phạm vi:

- Một client cho toàn bộ thời gian chạy ứng dụng.
- Hoặc một client cho một phiên dịch.

Không nên tạo client mới cho từng lần gọi nếu không có lý do rõ ràng.

Cũng nên phân biệt:

- Connect timeout.
- Read timeout.
- Write timeout.
- Pool timeout.

Một giá trị timeout duy nhất có thể chưa đủ cho các request AI dài.

### 3.4. Thiếu kiểm thử end-to-end

Unit test cho từng module là cần thiết nhưng chưa đủ để chứng minh luồng hoạt động hoàn chỉnh.

Cần kiểm thử toàn bộ chu trình:

1. Giao diện hoặc API.
2. Đọc cấu hình.
3. Đọc tài liệu.
4. Chuẩn hóa nội dung.
5. Chia chunk.
6. Tạo prompt.
7. Gửi provider.
8. Nhận response.
9. Ghép kết quả.
10. Ghi output.
11. Trả trạng thái về giao diện.

**Các trường hợp tối thiểu cần kiểm thử:**

- File ngắn chỉ có một chunk.
- File dài có nhiều chunk.
- Chunk đầu thành công, chunk sau timeout.
- Key đầu tiên bị giới hạn, key thứ hai thành công.
- Tất cả key đều thất bại.
- Provider trả response rỗng.
- Provider trả JSON sai cấu trúc.
- Provider trả lỗi 5xx.
- Người dùng tải lại trang trong lúc request đang chạy.
- Nội dung có Unicode tiếng Việt.
- Nội dung có emoji và ký tự đặc biệt.
- Nội dung có Markdown và HTML.
- Tên file có ký tự không hợp lệ.
- Hai request cùng xử lý một tài liệu.
- Output mới bị lỗi trong lúc output cũ đang tồn tại.

### 3.5. Cần bảo vệ output khỏi trạng thái dở dang

Dù không triển khai checkpoint hay resume đầy đủ, hệ thống vẫn nên tránh làm hỏng output hiện có.

Nếu ghi trực tiếp vào file đích và process bị dừng giữa chừng, file có thể bị:

- Rỗng.
- Thiếu một phần nội dung.
- Không còn là bản dịch hoàn chỉnh.

**Đề xuất dùng atomic write:**

1. Ghi kết quả vào file tạm.
2. Đảm bảo ghi hoàn tất.
3. Đổi tên file tạm thành file chính ở bước cuối.

Nếu phiên dịch thất bại, giữ nguyên output cũ.

Điều này không vi phạm chính sách không checkpoint. Đây chỉ là biện pháp bảo vệ file đầu ra.

### 3.6. Cần rà soát path traversal và symlink

Mọi path do người dùng hoặc frontend truyền lên đều phải được kiểm tra ở backend.

Không nên chỉ kiểm tra chuỗi có chứa hai dấu chấm hay không.

Cần:

- Chuẩn hóa path.
- Resolve path.
- Kiểm tra path nằm trong workspace.
- Kiểm tra symlink không trỏ ra ngoài workspace.
- Không cho endpoint đọc tùy ý file trên hệ thống.
- Không dùng path frontend gửi lên mà chưa xác thực lại.

### 3.7. Cần bảo vệ API key

API key không nên xuất hiện trong:

- Log.
- Traceback.
- Thông báo lỗi.
- HTML.
- JavaScript.
- Response API.
- Tên URL được lưu trong lịch sử trình duyệt nếu có thể tránh.

Khi hiển thị key, chỉ nên hiển thị dạng rút gọn hoặc fingerprint.

Cần kiểm tra:

- File key có nằm trong ignore hay không.
- Key có từng bị commit vào Git hay không.
- Log có ghi toàn bộ URL chứa key hay không.
- Lỗi provider có trả lại request URL hay không.
- Key có bị gửi về frontend hay không.

### 3.8. Cần kiểm soát nội dung HTML

Sanitization nên được thực hiện ở ranh giới backend, không chỉ ở frontend.

Cần kiểm thử các trường hợp:

- Thẻ script.
- Thuộc tính onerror.
- Liên kết javascript.
- Iframe không cần thiết.
- Thẻ object hoặc embed.
- URL hình ảnh nguy hiểm.
- HTML bị chèn vào thông báo lỗi.

Không nên đưa dữ liệu chưa làm sạch trực tiếp vào `innerHTML`.

---

## 4. Đánh Giá Các Thay Đổi Quan Trọng

### 4.1. Timeout rất lớn

Timeout dài có thể cần thiết cho model reasoning hoặc provider phản hồi chậm.

Tuy nhiên, timeout quá lớn cũng có mặt trái:

- Worker bị giữ lâu.
- Người dùng tưởng ứng dụng bị treo.
- Không thể biết request còn hoạt động hay không.
- Khó hủy request.
- Khó phân biệt provider chậm với kết nối bị mất.

**Đề xuất:**

- Hiển thị thời gian đã chờ.
- Hiển thị chunk hiện tại.
- Hiển thị attempt hiện tại.
- Cho phép hủy phiên.
- Ghi log thời gian bắt đầu và kết thúc.
- Có thể đặt cảnh báo khi timeout vượt quá một ngưỡng lớn.

### 4.2. Retry theo key

Retry theo key là cải tiến hợp lý, nhưng cần đặt tên chính xác.

Nếu giá trị đại diện cho tổng số lần thử, nên dùng tên có nghĩa là số attempt.

Nếu giá trị đại diện cho số lần thử lại sau lần đầu, nên dùng tên có nghĩa là số retry.

Không nên dùng một tên nhưng xử lý theo nghĩa khác.

Cần kiểm thử:

- Một key.
- Nhiều key.
- 429 ở key đầu.
- 429 ở mọi key.
- Timeout ở key đầu.
- Lỗi không retryable.
- Chuyển sang chunk mới có reset trạng thái đúng hay không.

### 4.3. Max output tokens

Cấu hình output token cần đi kèm:

- Kiểm tra giới hạn theo model.
- Cảnh báo nếu giá trị quá thấp.
- Phát hiện output bị cắt.
- Đọc finish reason nếu provider cung cấp.
- Thông báo khi kết quả có dấu hiệu truncate.

Output bị cắt có thể làm mất phần cuối bản dịch mà người dùng không nhận ra.

### 4.4. Thinking level

Thinking level có thể hữu ích với provider hỗ trợ reasoning.

Tuy nhiên:

- Giao diện cần cho biết tùy chọn này áp dụng cho provider nào.
- Backend không nên gửi tham số này sang provider không hỗ trợ.
- Config cũ cần được migrate rõ ràng.
- Cần test payload của từng adapter.

---

## 5. Phase 2.5 – Stabilization and Contract Hardening

Trước khi mở rộng Phase 3, nên thực hiện các nhiệm vụ sau.

### 5.1. Ưu tiên P0

1. Chuẩn hóa schema cấu hình.
2. Tạo một nơi duy nhất để validate và normalize config.
3. Chuẩn hóa error model.
4. Phân biệt lỗi retry được và lỗi phải dừng.
5. Kiểm tra retry và xoay key bằng test đầy đủ.
6. Bảo vệ API key khỏi log và response.
7. Rà soát toàn bộ endpoint đọc file.
8. Kiểm tra path traversal và symlink.
9. Dùng atomic write cho config và output.
10. Bổ sung integration test cho luồng nhiều chunk.
11. Kiểm tra timeout thực tế ở từng provider.
12. Đảm bảo output cũ không bị ghi đè khi phiên mới thất bại.

### 5.2. Ưu tiên P1

1. Thêm exponential backoff và jitter.
2. Tôn trọng header Retry-After nếu provider trả về.
3. Tái sử dụng HTTP client trong một phiên xử lý.
4. Hiển thị tiến độ theo chunk và attempt.
5. Thêm request ID hoặc correlation ID.
6. Chuẩn hóa migration config cũ.
7. Thêm test xử lý đồng thời.
8. Thêm health check cho provider.
9. Thêm cảnh báo output bị truncate.
10. Thêm test XSS cho Markdown và HTML.
11. Cho phép hủy request đang chạy.

### 5.3. Ưu tiên P2

1. Drag and drop tài liệu.
2. Preview diff giữa nguồn và bản dịch.
3. Tìm kiếm và thay thế hàng loạt.
4. Glossary theo project.
5. Preset cấu hình theo model.
6. Lịch sử các lần dịch gần đây.
7. Ước tính token và chi phí.
8. Export metadata.
9. Xử lý nhiều file theo batch.
10. Cải thiện giao diện và dark mode.

---

## 6. Đề Xuất Cho Phase 3

### 6.1. Glossary theo project

Mỗi project nên có glossary riêng.

Glossary giúp:

- Giữ nhất quán tên riêng.
- Giữ nhất quán thuật ngữ.
- Kiểm soát cách dịch các từ đặc biệt.
- Giảm việc sửa thủ công sau dịch.

Glossary cần được giới hạn kích thước trước khi đưa vào prompt để tránh làm request quá lớn.

### 6.2. Prompt profile

Nên hỗ trợ các profile đơn giản như:

- Dịch tiểu thuyết.
- Dịch tài liệu kỹ thuật.
- Giữ nguyên Markdown.
- Giữ nguyên HTML.
- Hiệu đính bản dịch.
- Chuẩn hóa tên riêng.

Mỗi profile nên là một file hoặc cấu hình đơn giản. Chưa cần xây dựng hệ thống prompt động phức tạp.

### 6.3. Diff nguồn và bản dịch

Nên hiển thị:

- Số chunk.
- Số ký tự nguồn.
- Số ký tự kết quả.
- Chunk có output rỗng.
- Chunk có output ngắn bất thường.
- Các đoạn có dấu hiệu bị cắt.
- So sánh theo từng chunk nếu cần.

Không nên tự động dùng một model khác để đánh giá chất lượng ngay từ đầu. Các heuristic đơn giản sẽ nhẹ và dễ kiểm soát hơn.

### 6.4. Phát hiện output bất thường

Có thể cảnh báo nếu:

- Output rỗng.
- Output ngắn hơn nguồn quá nhiều.
- Output vẫn giữ nguyên phần lớn văn bản nguồn.
- AI thêm lời giải thích ngoài bản dịch.
- Markdown bị mất nhiều cấu trúc.
- Output bị cắt giữa câu.

Các kiểm tra này chỉ nên cảnh báo. Không nên tự động sửa bản dịch nếu chưa có sự xác nhận của người dùng.

### 6.5. Hủy request

Đây là tính năng có giá trị thực tế cao.

Người dùng nên có thể:

- Hủy chunk hiện tại.
- Dừng toàn bộ phiên dịch.
- Biết request đang ở attempt nào.
- Biết đang dùng provider và key index nào, nhưng không hiển thị key thật.
- Không ghi output chưa hoàn tất.
- Nhận trạng thái cuối cùng rõ ràng.

### 6.6. Batch nhẹ

Sau khi luồng một file ổn định, có thể hỗ trợ nhiều file theo thứ tự.

Đề xuất mặc định:

- File thứ nhất hoàn tất.
- Chuyển sang file thứ hai.
- Nếu lỗi thì dừng toàn bộ.
- Cho phép người dùng chọn sau này có bỏ qua file lỗi hay không.

Không nên xử lý song song mặc định vì có thể làm tăng rate limit và làm phức tạp trạng thái.

---

## 7. Những Tính Năng Chưa Nên Làm Ngay

Chưa nên ưu tiên các tính năng sau:

- Hệ thống tài khoản nhiều người dùng.
- Phân quyền phức tạp.
- Queue phân tán.
- Database workflow lớn.
- Resume nhiều tầng.
- Checkpoint tự động cho mọi chunk.
- Đồng bộ cloud.
- Plugin marketplace.
- Tự động đánh giá chất lượng bằng nhiều model.
- Dịch nền không kiểm soát.
- Tối ưu cho hàng nghìn file trước khi có nhu cầu thực tế.

Các tính năng này làm tăng trạng thái và độ phức tạp nhưng chưa trực tiếp cải thiện chu trình gửi nội dung và nhận bản dịch.

---

## 8. Tiêu Chí Nghiệm Thu Trước Khi Đóng Phase 2

### 8.1. Chức năng

- Dịch được file một chunk.
- Dịch được file nhiều chunk.
- Xoay key đúng khi gặp lỗi giới hạn.
- Retry đúng số lần cấu hình.
- Dừng đúng với lỗi không retryable.
- Không ghi output dở dang.
- Không làm mất output cũ nếu phiên mới thất bại.
- Đọc và ghi Unicode chính xác.
- Hiển thị Markdown và HTML an toàn.

### 8.2. Cấu hình

- Có một schema cấu hình chính.
- UI và backend sử dụng cùng giá trị.
- Giá trị sai được từ chối hoặc sửa theo quy tắc rõ ràng.
- Config cũ có cơ chế migrate hoặc fallback minh bạch.
- Provider không nhận tham số không được hỗ trợ.
- Các giá trị số được ép kiểu rõ ràng.
- Các giá trị có giới hạn tối thiểu và tối đa.

### 8.3. An toàn

- Không có path traversal.
- Không vượt workspace thông qua symlink.
- Không log API key.
- Không trả secret về frontend.
- Không để key xuất hiện trong thông báo lỗi.
- Ghi file theo cơ chế atomic write.
- Không đưa HTML chưa xử lý vào giao diện.
- Xử lý đồng thời không làm hỏng config hoặc output.

### 8.4. Kiểm thử

- Có unit test cho chunker.
- Có unit test cho config.
- Có unit test cho retry.
- Có unit test cho từng provider adapter.
- Có integration test cho luồng dịch hoàn chỉnh.
- Có test timeout.
- Có test lỗi 429.
- Có test lỗi 5xx.
- Có test malformed response.
- Có test response rỗng.
- Có test XSS.
- Có test file Unicode.
- Có test file lớn.
- Có test reload giao diện trong khi request đang chạy.
- Có test trong môi trường cài đặt sạch.

---

## 9. Thứ Tự Triển Khai Khuyến Nghị

**Bước 1:** Hoàn thành kiểm tra và sửa các lỗi P0 của Phase 2.5.

**Bước 2:** Chuẩn hóa cấu hình và error model.

**Bước 3:** Hoàn thiện retry, timeout, atomic write và bảo mật file.

**Bước 4:** Bổ sung integration test.

**Bước 5:** Bổ sung khả năng hủy request và hiển thị tiến độ rõ ràng.

**Bước 6:** Triển khai glossary theo project.

**Bước 7:** Triển khai prompt profile.

**Bước 8:** Triển khai diff và cảnh báo output bất thường.

**Bước 9:** Triển khai batch nhẹ.

**Bước 10:** Chỉ sau đó mới xem xét các tính năng mở rộng khác.

---

## 10. Kết Luận Cuối Cùng

Phase 2 là một bước tiến tốt và đã tạo ra nền tảng có giá trị thực tế.

Các quyết định đúng gồm:

- Giữ phạm vi tương đối gọn.
- Tập trung vào chu trình gửi và nhận bản dịch.
- Tách provider.
- Có cấu hình timeout và retry.
- Quan tâm đến nội dung dài.
- Có xử lý sanitization.
- Có giao diện quản lý tài liệu.

Các vấn đề lớn nhất hiện tại không phải là thiếu tính năng mà là:

- Cấu hình chưa có contract duy nhất.
- Retry chưa được phân loại theo loại lỗi.
- Kiểm thử end-to-end chưa đủ.
- Cần rà soát bảo mật secret và path.
- Cần bảo vệ output bằng atomic write.
- Cần cải thiện khả năng quan sát request dài.
- Cần có cách hủy request đang chạy.

**Khuyến nghị cuối cùng:**

Không mở rộng Phase 3 theo hướng thêm thật nhiều tính năng ngay lập tức.

Nên hoàn thành Phase 2.5 trước, sau đó triển khai Phase 3 theo thứ tự:

1. Phase 2.5 – Ổn định hóa.
2. Glossary và prompt profile.
3. Diff và phát hiện output bất thường.
4. Hủy request và batch nhẹ.
5. Các công cụ xử lý nội dung nâng cao.

**Nguyên tắc quyết định cho mọi tính năng mới:**

Tính năng đó phải giúp quá trình gửi nội dung cho AI và nhận bản dịch nhanh hơn, ổn định hơn, an toàn hơn hoặc dễ kiểm soát hơn.

Nếu một tính năng làm tăng nhiều trạng thái, tạo luồng ngầm hoặc làm phức tạp hệ thống nhưng không cải thiện trực tiếp chu trình trên, nên trì hoãn hoặc loại bỏ.
