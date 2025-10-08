# Changelog - Lịch sử thay đổi

## [2.6.1] - 2025-10-08

### Fixed
- Verification: thay prompt hỏi tương tác sang input không chặn với timeout mặc định 'y', tránh treo khi chạy headless/CI.
- Verification: chuẩn hóa ánh xạ tên file parts bằng cách strip hậu tố "_translated" trước khi đối chiếu nguồn; bổ sung dự phòng so khớp không phân biệt hoa/thường.
- Verification: chặn sớm chế độ kiểm tra đối với dự án file đơn (đã chia chunk) để tránh retry vô nghĩa và lãng phí API [attached_file:19].

### Added
- io_utils: bổ sung hàm input_with_timeout dùng chung (đa nền tảng) cho workflow và verification để đảm bảo không chặn tiến trình.

### Changed
- Quy ước đặt tên (file đơn): giữ thống nhất "chunk_{index}.txt" cho parts, không thêm hậu tố "_translated" để đảm bảo ánh xạ và ghép nối ổn định.

### Refactor
- Tách translator thành facade mỏng, tái xuất các thành phần con (ApiManager, TranslationCache, robust_translate, consistency_check_chunk) từ gói translators/* nhằm giảm kích thước và tăng khả năng bảo trì mà không phá vỡ import hiện có [attached_file:9].

## [2.6.0] - 2025-10-06

### Thêm mới (Added)
- **Auto-retry cho chunks lỗi**: Tự động phát hiện và dịch lại các chunks còn sót ký tự tiếng Trung
  - Sau khi dịch xong tất cả chunks, quét toàn bộ để tìm chunks lỗi
  - Lặp lại chu trình dịch lại chỉ các chunks lỗi cho đến khi sạch hoàn toàn
  - Giới hạn tối đa 3 vòng retry để tránh vòng lặp vô hạn
- **Verification Mode**: Chế độ kiểm tra bản dịch cũ khi file output đã tồn tại
  - Nếu cả input và output đều tồn tại, hỏi người dùng có muốn kiểm tra không
  - Quét tất cả chunks trong output, chỉ dịch lại chunks có ký tự tiếng Trung
  - Tự động chạy consistency check sau khi dịch lại
  - Tiết kiệm thời gian và chi phí API
- **Module chinese_detector.py (MỚI)**: Module chuyên xử lý phát hiện ký tự tiếng Trung
  - Function `has_chinese_characters()`: Kiểm tra có ký tự Hán trong văn bản
  - Function `count_chinese_characters()`: Đếm số lượng ký tự Hán
  - Function `find_chinese_chunks()`: Tìm tất cả chunks chứa ký tự Hán
  - Sử dụng regex tối ưu, hỗ trợ kiểm tra nhanh

### Thay đổi (Changed)
- **Module workflow.py**: 
  - Thêm function `retry_failed_chunks()`: Xử lý vòng lặp retry cho chunks lỗi
  - Thêm function `verify_existing_translation()`: Chế độ verification
  - Cập nhật `run_translation_workflow()` để tích hợp các tính năng mới
  - Thêm interaction hỏi người dùng khi phát hiện output cũ
- **Module translator.py**:
  - Import `chinese_detector` để sử dụng kiểm tra ký tự
  - Cải thiện logging khi phát hiện ký tự tiếng Trung
- **Quy trình dịch mới**: 
Dịch tất cả chunks → Phát hiện chunks lỗi → Retry (max 3 lần)
↓
Consistency Check

### Cải tiến (Improved)
- **Tăng độ tin cậy**: Đảm bảo 100% chunks không còn ký tự tiếng Trung trước khi hoàn tất
- **Tiết kiệm chi phí**: Chế độ verification chỉ dịch lại chunks cần thiết
- **User Experience**: Thông báo rõ ràng về số chunks lỗi và tiến trình retry
- **Logging chi tiết**: Ghi log đầy đủ về chunks lỗi và số vòng retry

## [2.5.1] - 2025-10-06

### Thêm mới (Added)
- **Hệ thống Translation Guidelines nâng cao**: Hỗ trợ nạp chỉ dẫn dịch thuật nằm trong `prompts/instructions/` từ:
  - `style_profile.json`: Hồ sơ văn phong, thể loại, tone
  - `glossary.csv`: Bảng thuật ngữ chuẩn
  - `character_relations.csv`: Ma trận xưng hô nhân vật
- **Module translation_guide.py (MỚI)**: Xử lý và format guidelines thành prompt
  - Class `StyleProfile`, `GlossaryManager`, `CharacterRelationsManager`
  - Function `build_translation_guidelines()`
- **Placeholder {translation_guidelines}**: Tích hợp vào tất cả prompt templates

### Thay đổi (Changed)
- **Module configuration.py**: Nạp và chèn guidelines vào prompts
- **Tất cả prompt templates**: Thêm section [TRANSLATION GUIDELINES]

## [2.4.2] - 2025-10-06

### Thay đổi (Changed)
- **Tách API keys ra file riêng**: API keys giờ được nạp từ file `API.txt` (mỗi key một dòng) thay vì cấu hình cứng trong `config.ini`
  - Tăng bảo mật: file `API.txt` có thể bỏ qua trong `.gitignore` dễ dàng hơn
  - Dễ quản lý: thêm/xóa key chỉ cần chỉnh sửa file text đơn giản
  - Tự động bỏ qua dòng trống và comment (dòng bắt đầu bằng #)
- **Module configuration.py**: Thêm hàm `load_api_keys()` để đọc và validate API keys từ file
- **Loại bỏ tham số INPUT_LANG**: Đơn giản hóa cấu hình khi chỉ dịch tiếng Trung → tiếng Việt
  - Hard-code kiểm tra ký tự Hán trong `translator.py`
  - Giảm phức tạp không cần thiết cho use case chính

### Tài liệu (Documentation)
- **Thêm file API.txt.example**: File mẫu hướng dẫn định dạng API keys
- **Cập nhật README.md**: Hướng dẫn cách thiết lập file API.txt

## [2.4.1] - 2025-10-01

### Thêm mới (Added)
- **Đếm ngược tự động xóa cache**: Khi phát hiện cache cũ, hệ thống sẽ đếm ngược 5 giây và tự động chọn 'y' để xóa nếu người dùng không phản hồi
- **Thống kê chi tiết quá trình dịch**: Thêm module `statistics.py` để theo dõi và báo cáo:
  - Tổng số từ và ký tự đã xử lý
  - Số token ước tính đã sử dụng (dựa trên tỷ lệ 1 token ≈ 4 ký tự)
  - Danh sách chunks thành công/thất bại với chỉ số cụ thể
  - Thông tin quota còn lại của từng API key
  - Tổng thời gian thực hiện
- **Đặt tên file chunk đã dịch theo nguồn gốc**: File chunk đã dịch giờ có tên tương ứng với chunk gốc để dễ so sánh và kiểm tra
- **Xử lý ký tự đặc biệt và định dạng**: Module `text_normalizer.py` để chuẩn hóa bản dịch:
  - Chuyển đổi dấu gạch ngang dài (—) thành dấu gạch ngang thường ở đầu hội thoại
  - Giữ nguyên ký tự `--` dùng để ngăn cách nội dung (như nhật ký)
  - Chuyển đổi dấu ngoặc kép thành smart quotes ("" và '')
  - Chuyển đổi dấu ngoặc vuông tiếng Trung (【】〔〕) thành dấu ngoặc vuông tiêu chuẩn []
  - Loại bỏ các ký tự markdown (```
- **Tự động dừng khi hết quota tất cả API**: Khi tất cả API keys đều hết quota, hệ thống tự động lưu trạng thái và dừng lại để tiếp tục sau

### Thay đổi (Changed)
- **Cải thiện xử lý lỗi quota trong `translator.py`**: Tăng cường logic phát hiện và xử lý trạng thái `all_keys_exhausted`
- **Nâng cấp workflow trong `workflow.py`**: Tích hợp module thống kê và chuẩn hóa văn bản vào quy trình dịch
- **Cải tiến `file_writer.py`**: Lưu chunk với tên có thể truy xuất nguồn gốc, hỗ trợ chuẩn hóa văn bản trước khi ghi

### Tài liệu (Documentation)
- **Giải thích về cấu hình INPUT_LANG**: 
  - `INPUT_LANG = CN`: Ngôn ngữ nguồn là tiếng Trung, prompt sẽ sử dụng thuật ngữ "tiếng Trung" và kiểm tra ký tự Hán
  - `INPUT_LANG = EN`: Ngôn ngữ nguồn là tiếng Anh, cần cập nhật prompt thay "tiếng Trung" thành "tiếng Anh" và vô hiệu hóa kiểm tra ký tự Hán trong `translator.py`
  - Đề xuất: Tạo bộ prompt riêng cho EN (01-main-en.txt, 02-retranslate-en.txt, 03-correction-en.txt) và thêm logic chọn prompt theo INPUT_LANG trong `configuration.py`

### Sửa lỗi (Fixed)
- Sửa lỗi không có timeout khi chờ input người dùng xóa cache
- Cải thiện xử lý định dạng văn bản để đảm bảo tính nhất quán

## [2.3.0] - Nâng cấp toàn diện Hệ thống Prompt và Tích hợp Bộ nhớ ngữ cảnh

- Tái thiết kế hoàn toàn 01-main.txt với MỆNH LỆNH TỐI THƯỢNG
- Nâng cấp 02-retranslate.txt tích hợp project_notes
- Mở rộng 03-correction.txt thành quy trình 4 bước chi tiết  
- Cải tiến 04-consistency_check.txt với 3 giai đoạn kiểm tra
- Nâng cấp notes.txt thành hệ thống translation memory
- Thống nhất placeholders và cấu trúc cho tất cả prompt

# [2.2.0] - Tích hợp Nối ngữ cảnh và Tinh chỉnh Quy trình

### ✨ Tính năng mới (Features)

* **Tích hợp "Nối ngữ cảnh" (Context Chaining):**
    * Đây là nâng cấp quan trọng nhất. Khi dịch một chunk, chương trình sẽ tự động lấy một phần cuối của chunk **đã dịch** trước đó để làm "mồi" ngữ cảnh cho AI.
    * Giúp AI nhận biết và duy trì văn phong, cách xưng hô, tình tiết truyện một cách liền mạch và nhất quán hơn giữa các chunk.
    * Kích thước của phần ngữ cảnh này có thể được tùy chỉnh trong `config.ini` (`CONTEXT_CHAR_COUNT`).
* **Bổ sung Thư mục Lưu trữ (`_archive`):**
    * Chương trình sẽ tự động bỏ qua tất cả các file và thư mục con nằm trong một thư mục đặc biệt trong `workspace/input`.
    * Tên của thư mục này có thể được cấu hình trong `config.ini` (`ARCHIVE_DIR_NAME`).

### ♻️ Thay đổi (Changes)

* **Thay đổi Quy trình Dịch (Tuần tự):**
    * Do tính chất của việc "nối ngữ cảnh" (chunk sau phải chờ chunk trước dịch xong), quy trình dịch chính đã được thay đổi từ song song (multi-thread) sang **tuần tự (single-thread)**.
    * **Lưu ý:** Việc này sẽ làm **tốc độ dịch tổng thể chậm hơn** so với các phiên bản trước, nhưng bù lại chất lượng và sự liền mạch của bản dịch sẽ được cải thiện đáng kể.
* **Tinh chỉnh Quy trình Resume:**
    * Khi người dùng từ chối `resume` một phiên dịch cũ, chương trình sẽ ngay lập tức quét lại thư mục `input` để tìm một truyện mới và bắt đầu quy trình dịch mới, thay vì chỉ xóa và làm lại truyện cũ.

## [2.0.1] - Sửa lỗi Nghiêm trọng và Hoàn thiện Tái cấu trúc

### 🐛 Sửa lỗi (Bug Fixes)

* **Sửa lỗi `ImportError`:** Khắc phục lỗi không nhất quán về tên hàm (`load_prompts`) giữa `workflow.py` và `configuration.py`, đảm bảo module được nạp chính xác.
* **Sửa lỗi `SyntaxError`:** Sửa các lỗi cú pháp do thiếu dấu ngoặc nhọn `}` trong các chuỗi f-string ở `workflow.py` và `translator.py`.
* **Sửa lỗi `NameError`:** Bổ sung `from threading import Lock` vào `translator.py` để khắc phục lỗi `name 'Lock' is not defined`.

### ✒️ Chất lượng Mã nguồn (Code Quality)

* **Hoàn thiện Ghi chú:** Rà soát và bổ sung comment chi tiết, chuyên nghiệp cùng docstring đầy đủ cho tất cả các file và hàm trong dự án, đảm bảo mã nguồn rõ ràng, dễ đọc, dễ bảo trì và nâng cấp.


# [2.0.0] - Phiên bản Tái cấu trúc Lớn

## 🚀 Tái cấu trúc & Tối ưu hóa (Refactoring & Optimizations)

* **Tái cấu trúc mã nguồn sang `src/`:**
    * Di chuyển toàn bộ các module xử lý lõi (`translator.py`, `smart_chunker.py`, `file_writer.py`) vào thư mục `src/`.
    * Tách `main.py` thành các module chức năng chuyên biệt:
        * `src/configuration.py`: Quản lý việc nạp và xử lý tất cả các file cấu hình.
        * `src/workflow.py`: Chứa toàn bộ logic điều phối quy trình dịch thuật từ đầu đến cuối.
    * `main.py` giờ đây chỉ còn vai trò là điểm khởi đầu (entry point), giúp cấu trúc dự án cực kỳ gọn gàng, chuyên nghiệp và dễ bảo trì.

## ✨ Cải tiến (Enhancements)

* **Nâng cấp Thuật toán Cắt file:**
    * Tích hợp hoàn toàn thuật toán `intelligent_chunking` mới do người dùng cung cấp vào module `src/smart_chunker.py`.
    * Thuật toán mới kết hợp khả năng nhận diện tiêu đề chương và phương pháp cắt đoạn dựa trên ngữ cảnh (trọng số dấu câu), giúp các chunk được chia ra một cách tự nhiên nhất.
* **Cập nhật Cấu hình Mặc định:**
    * Bổ sung các comment chi tiết, tỉ mỉ cho từng mục trong `config.ini`.

## ✒️ Chất lượng Mã nguồn

* **Review và Ghi chú Chi tiết:** Toàn bộ mã nguồn đã được rà soát và bổ sung comment chi tiết, chuyên nghiệp theo chuẩn phát hành chính thức, giúp người khác có thể đọc hiểu, bảo trì và nâng cấp trong tương lai.

## [1.2.3] - Tái cấu trúc Lớn và Tối ưu hóa Cấu hình

### ✨ Cải tiến & Tái cấu trúc (Enhancements & Refactoring)

* **Tối ưu hóa Cấu trúc Dự án:**
    * Tạo thư mục `src/` mới để chứa tất cả các module xử lý lõi (`translator.py`, `file_writer.py`, `smart_chunker.py`).
    * Thư mục gốc của dự án giờ đây gọn gàng hơn, chỉ chứa các file chính: `main.py`, `README.md`, `CHANGELOG.md`, `config.ini`, và `requirements.txt`.

* **Tái cấu trúc `main.py`:**
    * `main.py` đã được tinh gọn lại, chỉ còn vai trò là điểm khởi đầu của chương trình.
    * Toàn bộ logic phức tạp đã được tách ra các module chuyên biệt mới trong `src/`:
        * `src/config_manager.py`: Chuyên quản lý việc đọc/ghi file `config.ini` và nạp toàn bộ các prompt.
        * `src/workflow_manager.py`: Chuyên điều phối toàn bộ quy trình dịch thuật (resume, chia chunk, dịch, kiểm tra, ghép file, dọn dẹp).

* **Cập nhật Cấu hình Mặc định:**
    * File `config.ini` đã được cập nhật với một bộ giá trị mặc định mới, toàn diện và tối ưu hơn, dựa trên các tham số từ phiên bản tham khảo `v13.3.9`.

## [1.2.2] - Tối ưu hóa Quy trình Ghi chú và Đầu ra

### ✨ Cải tiến (Enhancements)

* **Tối ưu hóa quy trình Ghi chú (`notes.txt`):**
    * Ghi chú cho truyện giờ đây được đưa trực tiếp vào prompt dịch chính (`01-main.txt`) và prompt dịch lại (`02-retranslate.txt`).
    * Điều này giúp AI có được ngữ cảnh về tên riêng và thuật ngữ ngay từ đầu, tăng cường tính nhất quán và giảm thiểu việc phải sửa lỗi ở các bước sau.
    * Ghi chú không còn được đưa vào prompt kiểm tra sự nhất quán cuối cùng.

### ♻️ Thay đổi (Changes)

* **Đơn giản hóa kết quả đầu ra:**
    * Chương trình giờ đây sẽ chỉ tạo ra **một file duy nhất** chứa toàn bộ bản dịch với tên `[tên_truyện]_dich.txt`.
    * Đã **loại bỏ hoàn toàn** việc tạo các file chương riêng lẻ (`_chuong_...`) và file giới thiệu (`_gioi_thieu.txt`) không cần thiết.
* **Tinh gọn Cấu hình:**
    * Xóa bỏ tùy chọn `CREATE_COMBINED` khỏi `config.ini` vì việc tạo file tổng hợp duy nhất là hành vi mặc định.

### [1.2.1] - Cải tiến & Tối ưu hóa

* **Tối ưu hóa Cấu trúc Thư mục:**
    * Tạo thư mục `workspace/` mới để chứa tất cả các thư mục làm việc và dữ liệu tạm thời.
    * Các thư mục `input`, `output`, `cache`, và `progress` giờ đây sẽ nằm gọn bên trong `workspace/` để giữ cho thư mục gốc của dự án luôn sạch sẽ.

* **Triển khai Lưu trữ Cache (Cache Archiving):**
    * Sau khi quá trình dịch hoàn tất, các file cache sẽ không bị xóa.
    * Thay vào đó, chúng sẽ được tự động di chuyển vào một thư mục lưu trữ có đánh dấu thời gian, ví dụ: `workspace/cache/bin_2025-08-25_18-00/`.

* **Lưu trữ các Chunk đã dịch:**
    * Sau khi ghép các chunk thành file tổng hợp, các file chunk riêng lẻ (trong thư mục `progress`) sẽ không bị xóa.
    * Chúng sẽ được di chuyển vào thư mục con `parts/` bên trong thư mục kết quả cuối cùng (ví dụ: `workspace/output/[Tên Truyện]/parts/`), giúp bạn dễ dàng đối chiếu và kiểm tra lại sau này.

## [1.2] - Giải thuật Cắt file Mới

Module `smart_chunker.py` đã được viết lại hoàn toàn để triển khai thuật toán `intelligent_chunking` mới, kết hợp ưu điểm của cả hai phiên bản:

   1. Phát hiện và Đánh dấu Tiêu đề: Trước khi cắt, toàn bộ văn bản sẽ được quét để tìm các tiêu đề chương/hồi. Các tiêu đề này sẽ được đánh dấu bằng định dạng **...** như cũ. Đây là bước ưu tiên hàng đầu.

   2. Cắt đoạn Thông minh theo Ngữ cảnh:

       - Chương trình sẽ tìm điểm cắt "tối ưu" nhất trong một khoảng cho phép (min_chars và max_chars trong config.ini).

       - Ưu tiên cắt ở cuối câu: Các dấu .!?。！？ có trọng số cao nhất.

       - Sau đó đến cuối đoạn: Dấu ngắt đoạn \n\n có ưu tiên cao thứ hai.

       - Các điểm ngắt khác như xuống dòng \n, dấu phẩy, dấu cách... sẽ được xem xét với độ ưu tiên thấp dần.

    3. Hậu xử lý: Sau khi cắt, chương trình sẽ tự động tìm các chunk quá nhỏ (thường là các đoạn ngắn cuối chương) và gộp chúng vào chunk trước đó để đảm bảo các phần dịch luôn đủ ngữ cảnh.

## [1.1.1] - Bản nâng cấp Lõi và Tăng cường Chất lượng

Phiên bản này tập trung vào việc hoàn thiện quy trình dịch thuật, tăng cường độ tin cậy và đưa vào các cơ chế đảm bảo chất lượng bản dịch một cách tự động.

### ✨ Tính năng mới (Features)

-   **Hỗ trợ dịch nguyên thư mục truyện**:
    -   Chương trình giờ đây có thể nhận một thư mục con trong `input` làm nguồn dịch.
    -   Tự động đọc và dịch tất cả các file `.txt` bên trong thư mục đó theo thứ tự tên file.
-   **Tối ưu hóa logic chia chunk**:
    -   Khi xử lý một thư mục, các file chương có dung lượng nhỏ hơn `CHUNK_SIZE` sẽ được coi là một chunk duy nhất để giữ ngữ cảnh tốt hơn.
-   **Triển khai thuật toán "Sửa lỗi Lặp lại"**:
    -   Tự động quét bản dịch sau mỗi lần dịch để tìm ký tự tiếng Trung còn sót.
    -   Nếu phát hiện lỗi, chương trình sẽ gửi lại chính bản dịch lỗi đó cho AI và yêu cầu sửa lại một cách lặp đi lặp lại cho đến khi chunk hoàn toàn "sạch".
-   **Tích hợp bước "Kiểm tra sự nhất quán"**:
    -   Sau khi dịch xong, chương trình thực hiện một bước cuối cùng: rà soát lại toàn bộ bản dịch và đối chiếu với file ghi chú (`notes.txt`) để đảm bảo tên riêng, thuật ngữ được thống nhất toàn truyện.
    -   Tính năng này có thể được bật/tắt trong `config.ini`.
-   **Hệ thống "Ghi chú cho AI" (`notes.txt`)**:
    -   Cho phép người dùng tạo một file `notes.txt` chứa danh sách tên riêng, thuật ngữ... cho từng truyện.
    -   Chương trình sẽ tự động nạp file ghi chú này và đưa vào prompt để AI tuân thủ, tăng cường tính nhất quán.
-   **Số luồng dịch bằng số API key**:
    -   Loại bỏ cấu hình `MAX_WORKERS`. Số luồng dịch song song được tự động đặt bằng số lượng API key cung cấp để tối ưu hóa việc sử dụng.

### 🐛 Sửa lỗi (Bug Fixes)

-   **Sửa lỗi `re.PatternError`**: Khắc phục lỗi nghiêm trọng khi biên dịch biểu thức chính quy (regex) để tìm ký tự tiếng Trung.
-   **Sửa lỗi `NameError` và `TypeError`**: Khắc phục các lỗi liên quan đến việc thiếu import thư viện và truyền sai tham số cho hàm dịch.
-   **Ổn định quy trình**: Loại bỏ các bước xác nhận và đếm ký tự không cần thiết ở đầu chương trình để quy trình chạy mượt mà hơn.


## [1.1] - (Bản ổn định hiện tại)

Đây là phiên bản được tinh chỉnh và bổ sung các tính năng cốt lõi để đảm bảo chất lượng và sự linh hoạt.

### ✨ Tính năng mới (Features)

-   **Triển khai thuật toán "Sửa lỗi Lặp lại"**:
    -   Tự động quét bản dịch sau mỗi lần dịch.
    -   Nếu phát hiện còn sót ký tự tiếng Trung, chương trình sẽ gửi lại chính bản dịch lỗi đó cho AI và yêu cầu sửa lại.
    -   Quá trình này lặp lại cho đến khi chunk hoàn toàn "sạch", được kiểm soát bởi tham số `MAX_REFINEMENT_ATTEMPTS` trong `config.ini`.
-   **Hỗ trợ dịch nguyên thư mục truyện**:
    -   Chương trình giờ đây có thể nhận một thư mục con trong `input` làm nguồn dịch.
    -   Tự động đọc và dịch tất cả các file `.txt` bên trong thư mục đó theo thứ tự tên file.
-   **Tối ưu hóa logic chia chunk**:
    -   Khi xử lý một thư mục, các file chương có dung lượng nhỏ hơn `CHUNK_SIZE` sẽ được coi là một chunk duy nhất, giúp giữ ngữ cảnh tốt hơn.
-   **Số luồng dịch bằng số API key**:
    -   Loại bỏ cấu hình `MAX_WORKERS`. Số luồng dịch song song được tự động đặt bằng số lượng API key cung cấp để tối ưu hóa việc sử dụng.

### 🐛 Sửa lỗi (Bug Fixes)

-   **Sửa lỗi `re.PatternError`**: Khắc phục lỗi nghiêm trọng khi biên dịch biểu thức chính quy (regex) để tìm ký tự tiếng Trung trong `translator.py`.
-   **Ổn định quy trình**: Loại bỏ các bước xác nhận và đếm ký tự không cần thiết ở đầu chương trình để quy trình chạy mượt mà hơn.

## [1.0] - Phiên bản Module hóa Đầu tiên

Phiên bản này đánh dấu bước chuyển đổi lớn từ một script đơn lẻ thành một dự án có cấu trúc module hóa rõ ràng.

### ✨ Tính năng mới (Features)

-   **Tái cấu trúc thành Module**: Toàn bộ mã nguồn được chia thành các file chức năng: `main.py`, `translator.py`, `smart_chunker.py`, `file_writer.py`.
-   **Cấu hình ngoài**: Tách toàn bộ cài đặt ra `config.ini` và "bộ não" AI ra `prompts.ini`.
-   **Triển khai tính năng Resume**: Xây dựng cơ chế lưu trạng thái vào thư mục `progress`, cho phép tiếp tục công việc nếu bị gián đoạn.
-   **Quản lý API và Quota**: Xây dựng `ApiManager` để xoay vòng API key và tự động xử lý khi một key hết quota.
-   **Hệ thống Logging**: Thay thế toàn bộ lệnh `print()` bằng module `logging` chuyên nghiệp, ghi lại mọi hoạt động vào file log.

### 🐛 Sửa lỗi (Bug Fixes)

-   **Sửa lỗi `configparser`**: Khắc phục các lỗi liên quan đến ký tự đặc biệt (`%`) và việc đọc giá trị nhiều dòng trong file `.ini`.
-   **Sửa lỗi đọc file ẩn**: Thêm logic để bỏ qua các file hệ thống như `.gitkeep` trong thư mục `input`.