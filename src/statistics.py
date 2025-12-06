# src/statistics.py - v2.4.1
# Tác giả: Narga
# Chức năng: Module theo dõi và thống kê chi tiết quá trình dịch thuật,
#            bao gồm số từ, token, chunks thành công/thất bại, và thông tin API.

import time
import logging
from typing import Dict, List, Any
from threading import Lock
from pathlib import Path


class TranslationStatistics:
    """
    Lớp quản lý thống kê toàn diện cho quá trình dịch thuật.
    
    Attributes:
        total_chars (int): Tổng số ký tự đã xử lý từ văn bản gốc
        total_words (int): Tổng số từ đã xử lý (ước tính)
        total_tokens (int): Tổng số token ước tính đã sử dụng (1 token ≈ 4 chars)
        successful_chunks (List[int]): Danh sách chỉ số các chunk dịch thành công
        failed_chunks (List[int]): Danh sách chỉ số các chunk dịch thất bại
        api_call_count (Dict[str, int]): Số lần gọi API cho từng key
        start_time (float): Thời điểm bắt đầu quá trình dịch
        end_time (float): Thời điểm kết thúc quá trình dịch
    """
    
    def __init__(self):
        """Khởi tạo đối tượng thống kê với các giá trị ban đầu."""
        self.total_chars: int = 0
        self.total_words: int = 0
        self.total_tokens: int = 0
        self.successful_chunks: List[int] = []
        self.failed_chunks: List[int] = []
        self.api_call_count: Dict[str, int] = {}
        self.start_time: float = time.time()
        self.end_time: float = 0
        self._lock = Lock()
        
        logging.info("📊 Hệ thống thống kê đã được khởi tạo.")
    
    def add_chunk_result(self, chunk_index: int, chunk_text: str, 
                        status: str, api_key: str) -> None:
        """
        Ghi nhận kết quả dịch của một chunk.
        
        Args:
            chunk_index (int): Chỉ số của chunk trong danh sách
            chunk_text (str): Nội dung văn bản gốc của chunk
            status (str): Trạng thái dịch ('success' hoặc 'failed')
            api_key (str): API key đã được sử dụng cho chunk này
        """
        with self._lock:
            # Cập nhật số lượng ký tự và từ
            chunk_chars = len(chunk_text)
            chunk_words = len(chunk_text.split())
            
            self.total_chars += chunk_chars
            self.total_words += chunk_words
            
            # Ước tính token: 1 token ≈ 4 ký tự cho tiếng Trung/Việt
            # Thực tế có thể dao động từ 3-5, ta dùng 4 để ước tính trung bình
            chunk_tokens = chunk_chars // 4
            self.total_tokens += chunk_tokens
            
            # Ghi nhận trạng thái chunk
            if status == "success":
                self.successful_chunks.append(chunk_index)
            else:
                self.failed_chunks.append(chunk_index)
            
            # Đếm số lần gọi API
            key_suffix = api_key[-4:] if len(api_key) >= 4 else api_key
            self.api_call_count[key_suffix] = self.api_call_count.get(key_suffix, 0) + 1
    
    def finalize(self) -> None:
        """Đánh dấu kết thúc quá trình dịch và ghi nhận thời gian."""
        with self._lock:
            self.end_time = time.time()
    
    def get_elapsed_time(self) -> float:
        """
        Tính toán thời gian đã trôi qua.
        
        Returns:
            float: Thời gian đã trôi qua tính bằng giây
        """
        end = self.end_time if self.end_time > 0 else time.time()
        return end - self.start_time
    
    def format_time(self, seconds: float) -> str:
        """
        Định dạng thời gian thành chuỗi dễ đọc.
        
        Args:
            seconds (float): Số giây cần định dạng
            
        Returns:
            str: Chuỗi thời gian định dạng (VD: "2h 15m 30s")
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"
    
    def print_summary(self) -> None:
        """In ra bảng tổng kết chi tiết về quá trình dịch thuật."""
        self.finalize()
        
        elapsed = self.get_elapsed_time()
        total_chunks = len(self.successful_chunks) + len(self.failed_chunks)
        success_rate = (len(self.successful_chunks) / total_chunks * 100) if total_chunks > 0 else 0
        
        logging.info("\n" + "="*80)
        logging.info("📊 THỐNG KÊ QUÁ TRÌNH DỊCH THUẬT")
        logging.info("="*80)
        
        # Thống kê văn bản
        logging.info(f"📝 Tổng số ký tự đã xử lý: {self.total_chars:,}")
        logging.info(f"📝 Tổng số từ đã xử lý: {self.total_words:,}")
        logging.info(f"🎯 Token ước tính đã sử dụng: {self.total_tokens:,}")
        
        # Thống kê chunks
        logging.info(f"\n✅ Chunks dịch thành công: {len(self.successful_chunks)}/{total_chunks} ({success_rate:.1f}%)")
        if self.failed_chunks:
            logging.info(f"❌ Chunks dịch thất bại: {len(self.failed_chunks)}")
            logging.info(f"   Danh sách chunks thất bại: {sorted(self.failed_chunks)}")
        
        # Thống kê API
        logging.info(f"\n🔑 Thống kê sử dụng API keys:")
        for key_suffix, count in sorted(self.api_call_count.items()):
            logging.info(f"   Key ...{key_suffix}: {count} lần gọi")
        
        # Thống kê thời gian
        logging.info(f"\n⏱️  Tổng thời gian thực hiện: {self.format_time(elapsed)}")
        if total_chunks > 0:
            avg_time = elapsed / total_chunks
            logging.info(f"⏱️  Thời gian trung bình mỗi chunk: {self.format_time(avg_time)}")
        
        logging.info("="*80 + "\n")


def get_api_quota_info(api_manager: Any) -> Dict[str, str]:
    """
    Lấy thông tin quota còn lại của các API keys.
    
    Note: Gemini API không cung cấp endpoint trực tiếp để kiểm tra quota còn lại.
    Hàm này chỉ trả về trạng thái hiện tại dựa trên thông tin nội bộ của ApiManager.
    
    Args:
        api_manager: Đối tượng ApiManager quản lý các API keys
        
    Returns:
        Dict[str, str]: Dictionary chứa thông tin trạng thái của từng key
    """
    quota_info = {}
    
    with api_manager._lock:
        for key in api_manager._key_list:
            key_suffix = key[-4:] if len(key) >= 4 else key
            status = api_manager._keys.get(key, 'unknown')
            
            # Kiểm tra xem key có đang trong thời gian cooldown không
            cooldown_until = api_manager._rate_limiter.cool_down_until.get(key, 0)
            current_time = time.time()
            
            if current_time < cooldown_until:
                remaining_cooldown = int(cooldown_until - current_time)
                quota_info[key_suffix] = f"Cooldown ({remaining_cooldown}s còn lại)"
            elif status == 'available':
                failure_count = api_manager._rate_limiter.failure_count.get(key, 0)
                quota_info[key_suffix] = f"Khả dụng (Lỗi: {failure_count})"
            else:
                quota_info[key_suffix] = f"Trạng thái: {status}"
    
    return quota_info


def print_api_status(api_manager: Any) -> None:
    """
    In ra trạng thái hiện tại của tất cả các API keys.
    
    Args:
        api_manager: Đối tượng ApiManager quản lý các API keys
    """
    quota_info = get_api_quota_info(api_manager)
    
    logging.info("\n" + "-"*60)
    logging.info("🔑 TRẠNG THÁI CÁC API KEYS")
    logging.info("-"*60)
    
    for key_suffix, status in quota_info.items():
        logging.info(f"   Key ...{key_suffix}: {status}")
    
    logging.info("-"*60 + "\n")
