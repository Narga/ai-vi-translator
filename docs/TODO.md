TODO.md
- Quét thư mục input, dịch tất cả các tập tin .txt, .md, các thư mục con, mỗi thư mục con là một dự án, sau khi dịch xong giữ nguyên cấu trúc, vị trí các tập tin đã dịch tương ứng.
- Tìm các tập tin định hướng dịch nằm trong các thư mục con trước, nếu không có thì nạp thư mục guidlines trong thư mục prompts.
- Kiểm tra, so sánh thư mục input/output nếu đã tồn tại tập tin/thư mục cùng tên để hỏi người dùng tiến hành dịch lại (đối với các tập tin còn kí tự tiếng trung hoặc không có bản dịch bên output).
- Dùng cache files trong quá trình dịch, nếu phải dịch lại truy cập file đã cache thay vì upload lên (xác nhận là có tốn token như upload không), quá trình biên dịch kết thúc nếu tất cả đều được dịch thành công thì xóa trên drive
- kiểm tra mục đích, nhiệm vụ thư mục progress, nếu chỉ lưu logs thì đổi tên thành thư mục logs, định kỳ xóa các log cũ hơn 5 ngày hoặc tối đa 5 logs gần nhất. (sử dụng hàm chung clean up ở cache), tách cơ chế quản lý cache files, upload cache files