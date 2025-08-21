# file_writer.py - v1.0
# Module chịu trách nhiệm ghi kết quả dịch ra file.
# Phân tích các tiêu đề **...** để tách file theo chương.

import os
import re
from typing import List

def save_chapters(
    translated_chunks: List[str],
    output_dir: str,
    base_filename: str,
    encoding: str,
    create_combined: bool
) -> None:
    """
    Ghi các chunk đã dịch vào các file chương riêng biệt và một file tổng hợp.
    """
    print(f"\n💾 Bắt đầu ghi kết quả ra thư mục '{output_dir}'...")
    os.makedirs(output_dir, exist_ok=True)
    
    full_content = "\n\n".join(translated_chunks)
    
    # Regex để tìm tiêu đề chương đã được dịch (ví dụ: **Chương 1: Thức tỉnh**)
    chapter_pattern = re.compile(r'\*{2}(.*?)\*{2}')
    
    # Tách toàn bộ nội dung dựa trên pattern tiêu đề
    # `split` sẽ tạo ra một list, với phần tử đầu là nội dung trước chương 1,
    # và các phần tử sau xen kẽ giữa tiêu đề và nội dung chương.
    split_content = chapter_pattern.split(full_content)

    # Xử lý nội dung trước chương đầu tiên (nếu có)
    intro_content = split_content[0].strip()
    if intro_content:
        intro_path = os.path.join(output_dir, f"{base_filename}_gioi_thieu.txt")
        with open(intro_path, 'w', encoding=encoding) as f:
            f.write(intro_content)
        print(f"  - Đã ghi: {os.path.basename(intro_path)}")

    # Xử lý các chương
    chapter_index = 1
    # Duyệt qua list theo cặp (tiêu đề, nội dung)
    for i in range(1, len(split_content), 2):
        title = split_content[i].strip()
        content = split_content[i+1].strip()
        
        # Tạo tên file an toàn từ tiêu đề
        safe_title_part = re.sub(r'[^a-zA-Z0-9\s-]', '', title).replace(' ', '_')
        if len(safe_title_part) > 50: # Giới hạn độ dài tên file
            safe_title_part = safe_title_part[:50]

        # Tên file chuẩn: ten-sach_chuong_001_tieu_de_ngan.txt
        chapter_filename = f"{base_filename}_chuong_{chapter_index:03d}_{safe_title_part}.txt"
        chapter_path = os.path.join(output_dir, chapter_filename)
        
        # Ghi nội dung chương, bao gồm cả tiêu đề
        with open(chapter_path, 'w', encoding=encoding) as f:
            f.write(f"**{title}**\n\n{content}")
            
        print(f"  - Đã ghi: {chapter_filename}")
        chapter_index += 1
        
    # Ghi file tổng hợp nếu được yêu cầu
    if create_combined:
        combined_path = os.path.join(output_dir, f"{base_filename}_full.txt")
        try:
            with open(combined_path, 'w', encoding=encoding) as f:
                f.write(full_content)
            print(f"  - Đã ghi file tổng hợp: {os.path.basename(combined_path)}")
        except Exception as e:
            print(f"❌ Lỗi khi ghi file tổng hợp: {e}")
            
    print("✅ Hoàn tất việc ghi file!")


# Có thể chạy độc lập để kiểm thử
if __name__ == '__main__':
    print("Đây là module ghi file, được thiết kế để sử dụng bên trong script chính.")
    
    # Ví dụ kiểm thử
    print("\nChạy kiểm thử ghi file...")
    test_output_dir = "test_output"
    test_chunks = [
        "Đây là phần giới thiệu.\nKhông có tiêu đề.",
        "**Chương 1: Bắt đầu**\n\nNội dung của chương một.",
        "**Chương 2: Tiếp diễn**\n\nNội dung của chương hai.\nDòng thứ hai của chương hai."
    ]
    
    if os.path.exists(test_output_dir):
        import shutil
        shutil.rmtree(test_output_dir) # Dọn dẹp thư mục test cũ

    save_chapters(
        translated_chunks=test_chunks,
        output_dir=test_output_dir,
        base_filename="test_truyen",
        encoding="utf-8",
        create_combined=True
    )
    
    # Kiểm tra kết quả
    if os.path.isdir(test_output_dir) and len(os.listdir(test_output_dir)) > 0:
        print("\nKiểm thử thành công! Vui lòng kiểm tra thư mục 'test_output'.")
    else:
        print("\nKiểm thử thất bại.")