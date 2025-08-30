# main.py - v2.0.1
# Tác giả: Narga
# Chức năng: Điểm khởi đầu (entry point) của ứng dụng.

import sys
import logging
from datetime import datetime
from src.configuration import load_all_configs, setup_directories
from src.workflow import run_translation_workflow
from src.emergency_stop import setup_signal_handlers, emergency_stop

def main():
    """
    Hàm chính, thực hiện các bước:
    1. Tải cấu hình và các tham số.
    2. Thiết lập môi trường (thư mục, logging).
    3. Chạy quy trình dịch thuật chính.
    """
    # Thiết lập cơ chế bắt tín hiệu dừng (Ctrl+C) ngay từ đầu
    setup_signal_handlers()
    
    try:
        # Tải cấu hình và thiết lập các thư mục làm việc
        config_parser = load_all_configs()
        dirs = setup_directories(config_parser)
        
        # Thiết lập logging sau khi đã có đường dẫn thư mục progress
        progress_dir = dirs['progress']
        log_filename = datetime.now().strftime('%Y-%m-%d_%H-%M') + '_translator.log'
        log_filepath = progress_dir / log_filename
        
        # Xóa các handler cũ để tránh ghi log trùng lặp khi resume
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filepath, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ])
        logging.info(f"File log được lưu tại: {log_filepath}")
        
        # Xử lý lỗi thiếu API key một cách an toàn
        api_keys = [key.strip() for key in config_parser.get('API', 'GEMINI_API_KEYS').split(',') if key.strip()]
        if not api_keys:
            logging.critical("❌ LỖI: Không có API key nào được cung cấp trong [API] của file config.ini. Vui lòng thêm API key và chạy lại.")
            sys.exit(1)

        # Chạy quy trình dịch chính
        run_translation_workflow(config_parser, dirs)

    except FileNotFoundError as e:
        # Lỗi nghiêm trọng không thể ghi log, dùng print
        print(f"CRITICAL: Lỗi không tìm thấy file cấu hình hoặc prompt: {e}")
        sys.exit(1)
    except Exception as e:
        # Ghi lại các lỗi nghiêm trọng khác nếu có thể
        logging.critical(f"❌ Lỗi không xác định ở tầng cao nhất: {e}", exc_info=True)
        emergency_stop(f"Lỗi nghiêm trọng: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()