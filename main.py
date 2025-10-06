# main.py - v2.5.1
# Tác giả: Narga
# Chức năng: Điểm khởi đầu (entry point) của ứng dụng.
#            API keys được nạp từ file API.txt riêng biệt.

import sys
import logging
from datetime import datetime
from src.configuration import load_all_configs, setup_directories, load_api_keys, validate_config
from src.workflow import run_translation_workflow
from src.emergency_stop import setup_signal_handlers, emergency_stop


def main():
    """
    Hàm chính, điều phối toàn bộ hoạt động của ứng dụng.
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
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filepath, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        logging.info(f"File log được lưu tại: {log_filepath}")
        
        # Nạp API keys từ file API.txt
        try:
            api_keys = load_api_keys('API.txt')
        except (FileNotFoundError, ValueError) as e:
            logging.critical(f"❌ {e}")
            logging.critical("💡 Hướng dẫn: Tạo file 'API.txt' trong thư mục gốc, mỗi API key trên một dòng.")
            sys.exit(1)
        
        # Validate cấu hình
        if not validate_config(config_parser, api_keys):
            logging.critical("❌ Cấu hình không hợp lệ. Vui lòng kiểm tra lại config.ini và API.txt.")
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
