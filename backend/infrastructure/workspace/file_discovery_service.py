# backend/infrastructure/workspace/file_discovery_service.py
# FileDiscoveryService - File discovery và merge operations

"""
FileDiscoveryService quản lý việc tìm kiếm và gộp file nguồn.

Phase 06: Tách logic file discovery ra khỏi main.py.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


class FileDiscoveryService:
    """
    File discovery và merge service.

    Gom logic từ:
    - main.py:find_input_files
    - main.py:merge_small_files

    Sử dụng:
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        file_service = FileDiscoveryService()
        files = file_service.find_input_files(input_dir)
    """

    def __init__(self):
        """Khởi tạo FileDiscoveryService."""
        pass

    def find_input_files(self, input_dir: Path) -> List[Path]:
        """
        Tìm tất cả file .txt trong input directory.

        Args:
            input_dir: Đường dẫn đến thư mục input

        Returns:
            Danh sách các file path đã sắp xếp
        """
        if not input_dir.exists():
            return []

        # Tìm file .txt trực tiếp trong input_dir
        files = list(input_dir.glob("*.txt"))
        if files:
            return sorted(files)

        # Tìm trong subdirectory (bỏ qua thư mục bắt đầu bằng _)
        for subdir in input_dir.iterdir():
            if subdir.is_dir() and not subdir.name.startswith("_"):
                txt_files = sorted(subdir.glob("*.txt"))
                if txt_files:
                    return txt_files

        return []

    def merge_small_files(
        self,
        files: List[Path],
        min_chunk_size: int = 15000,
        output_dir: Optional[Path] = None,
    ) -> List[Path]:
        """
        Gộp các file nhỏ lại để đủ kích thước tối thiểu.

        Args:
            files: Danh sách các file cần xử lý
            min_chunk_size: Kích thước tối thiểu mong muốn
            output_dir: Thư mục output cho file gộp.
                       Nếu None, gộp vào thư mục chứa file đầu tiên.

        Returns:
            Danh sách file đã gộp hoặc file gốc
        """
        if not files:
            return []

        # Nếu chỉ có 1 file hoặc file đầu tiên đã đủ lớn, giữ nguyên
        first_file_size = files[0].stat().st_size
        if len(files) == 1 or first_file_size >= min_chunk_size * 0.8:
            logger.info(
                f"File đầu tiên đủ lớn ({first_file_size:,} chars), không cần gộp"
            )
            return files

        # Đọc tất cả files và tính tổng kích thước
        total_size = 0
        file_contents = []
        for f in files:
            try:
                with open(f, "r", encoding="utf-8") as fp:
                    content = fp.read()
                    file_contents.append((f, content))
                    total_size += len(content)
            except Exception as e:
                logger.warning(f"Không thể đọc file {f}: {e}")

        if total_size < min_chunk_size:
            # Tổng kích thước nhỏ hơn min, gộp thành 1 file
            merged_name = f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

            if output_dir is None:
                output_dir = files[0].parent

            output_dir.mkdir(parents=True, exist_ok=True)
            merged_path = output_dir / merged_name

            merged_content = "\n\n".join([content for _, content in file_contents])

            with open(merged_path, "w", encoding="utf-8") as f:
                f.write(merged_content)

            logger.info(
                f"✅ Gộp {len(files)} files thành 1 file: {merged_name} "
                f"({len(merged_content):,} chars)"
            )
            return [merged_path]

        # Nếu tổng lớn hơn min, giữ nguyên
        return files

    def get_file_info(self, file_path: Path) -> dict:
        """
        Lấy thông tin file.

        Args:
            file_path: Đường dẫn file

        Returns:
            Dict chứa file info
        """
        if not file_path.exists():
            return {"exists": False}

        stat = file_path.stat()
        size = stat.st_size

        return {
            "exists": True,
            "name": file_path.name,
            "path": str(file_path),
            "size": size,
            "size_display": (
                f"{size / 1024:.1f} KB" if size < 1048576 else f"{size / 1048576:.1f} MB"
            ),
        }

    def list_files_in_directory(
        self,
        directory: Path,
        recursive: bool = True,
        include_hidden: bool = False,
    ) -> List[dict]:
        """
        Liệt kê files trong directory.

        Args:
            directory: Đường dẫn directory
            recursive: Tìm đệ quy
            include_hidden: Include hidden files

        Returns:
            List of file info dicts
        """
        if not directory.exists():
            return []

        files = []
        pattern = "**/*" if recursive else "*"

        for f in sorted(directory.glob(pattern)):
            if not f.is_file():
                continue
            if not include_hidden and f.name.startswith("."):
                continue

            rel = str(f.relative_to(directory))
            stat = f.stat()
            size = stat.st_size

            files.append(
                {
                    "name": rel,
                    "path": str(f),
                    "size": size,
                    "size_display": (
                        f"{size / 1024:.1f} KB"
                        if size < 1048576
                        else f"{size / 1048576:.1f} MB"
                    ),
                }
            )

        return files
