# main.py - v1.0
# Script chính điều phối toàn bộ quy trình dịch thuật tiểu thuyết.

import os
import sys
import configparser
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# Import các module tùy chỉnh
import smart_chunker
import translator
import file_writer

def load_config():
    """Tải cấu hình từ config.ini và prompts.ini."""
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        raise FileNotFoundError("Lỗi: Không tìm thấy file 'config.ini'.")
    config.read('config.ini', encoding='utf-8')
    
    prompts = configparser.ConfigParser()
    if not os.path.exists('prompts.ini'):
        raise FileNotFoundError("Lỗi: Không tìm thấy file 'prompts.ini'.")
    prompts.read('prompts.ini', encoding='utf-8')
    
    return config, prompts

def get_language_name(lang_code: str) -> str:
    """Chuyển đổi mã ngôn ngữ (CN, EN) thành tên đầy đủ."""
    return {"CN": "tiếng Trung", "EN": "tiếng Anh"}.get(lang_code.upper(), "không xác định")

def main():
    """Hàm chính điều phối quy trình dịch thuật."""
    print("🚀 Bắt đầu chương trình Dịch Thuật Tiểu Thuyết v1.0 🚀")
    
    # 1. Tải cấu hình
    try:
        config, prompts = load_config()
        
        # Lấy các giá trị cấu hình
        api_keys = [key.strip() for key in config.get('API', 'GEMINI_API_KEYS').split(',') if key.strip()]
        model_name = config.get('MODEL', 'MODEL')
        input_lang = config.get('INPUT', 'INPUT_LANG')
        chunk_size = config.getint('PROCESSING', 'CHUNK_SIZE')
        max_workers = config.getint('PROCESSING', 'MAX_WORKERS')
        if max_workers == 0:
            max_workers = os.cpu_count() or 4 # Tự động phát hiện hoặc mặc định là 4
        temperature = config.getfloat('PROCESSING', 'TEMPERATURE')
        
        enable_cache = config.getboolean('CACHE', 'ENABLE_CACHE')
        cache_dir = config.get('CACHE', 'CACHE_DIR')
        
        output_encoding = config.get('OUTPUT', 'ENCODING')
        create_combined = config.getboolean('OUTPUT', 'CREATE_COMBINED')
        
        main_prompt_template = prompts.get('PROMPTS', 'MAIN_PROMPT')
        
    except (configparser.NoSectionError, configparser.NoOptionError, FileNotFoundError) as e:
        print(f"❌ Lỗi nghiêm trọng khi đọc file cấu hình: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ Lỗi giá trị trong file cấu hình: {e}")
        sys.exit(1)
        
    # 2. Tìm file trong thư mục 'input'
    input_dir = Path('input')
    files_in_input = list(input_dir.glob('*.*'))
    if not files_in_input:
        print("📁 Không tìm thấy file nào trong thư mục 'input'. Vui lòng thêm file truyện cần dịch và chạy lại.")
        sys.exit(0)
    
    # Giả định chỉ xử lý file đầu tiên tìm thấy
    source_file = files_in_input[0]
    base_filename = source_file.stem # Tên file không có phần mở rộng

    # 3. Đọc và chia chunk
    original_text = smart_chunker.read_and_detect_encoding(str(source_file))
    if not original_text:
        sys.exit(1)
    
    chunks = smart_chunker.smart_chunking(original_text, chunk_size)
    
    if not chunks:
        print("⚠️ Không có chunk nào được tạo ra từ file nguồn. Dừng chương trình.")
        sys.exit(0)

    # 4. Khởi tạo các trình quản lý
    try:
        api_manager = translator.ApiManager(api_keys=api_keys)
    except ValueError as e:
        print(f"❌ Lỗi: {e}")
        sys.exit(1)

    cache_manager = translator.TranslationCache(cache_dir=cache_dir, enabled=enable_cache)

    # Chuẩn bị prompt cuối cùng
    language_name = get_language_name(input_lang)
    final_prompt = main_prompt_template.format(language_name=language_name)
    
    # 5. Dịch song song
    print(f"\n🌐 Bắt đầu dịch {len(chunks)} chunk với tối đa {max_workers} luồng...")
    translated_chunks = [None] * len(chunks) # Dùng list để giữ đúng thứ tự
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(
                translator.translate_text,
                chunk, api_manager, cache_manager, model_name, final_prompt, temperature
            ): i for i, chunk in enumerate(chunks)
        }
        
        progress = tqdm(as_completed(future_to_index), total=len(chunks), desc="🤖 Đang dịch")
        for future in progress:
            index = future_to_index[future]
            try:
                result = future.result()
                if result:
                    translated_chunks[index] = result
                    progress.set_postfix_str(f"Chunk {index + 1}/{len(chunks)} ✅")
                else:
                    # Ghi nhận lỗi nhưng không dừng toàn bộ quá trình
                    translated_chunks[index] = f"### DỊCH LỖI CHUNK {index + 1} ###"
                    progress.set_postfix_str(f"Chunk {index + 1}/{len(chunks)} ❌")
            except Exception as exc:
                print(f"Lỗi không mong muốn khi dịch chunk {index + 1}: {exc}")
                translated_chunks[index] = f"### DỊCH LỖI NGHIÊM TRỌNG CHUNK {index + 1} ###"
                progress.set_postfix_str(f"Chunk {index + 1}/{len(chunks)} ❌")

    # 6. Ghi kết quả ra file
    output_dir = Path('output') / base_filename
    file_writer.save_chapters(
        translated_chunks=translated_chunks,
        output_dir=str(output_dir),
        base_filename=base_filename,
        encoding=output_encoding,
        create_combined=create_combined
    )
    
    print("\n🎉 Dịch thuật hoàn tất! 🎉")

if __name__ == '__main__':
    main()