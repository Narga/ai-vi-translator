# src/translators/file_manager.py - v2.7.0
# Tác giả: Narga
# Chức năng: Quản lý "cache nguồn" phía AI bằng Gemini File API.
# Ý tưởng:
# - Mỗi dự án (file đơn hoặc thư mục) được đóng gói (zip) một lần và upload lên Gemini.
# - Lưu lại file_uri để tái sử dụng xuyên suốt phiên dịch và giữa các API keys (không phụ thuộc key cụ thể).
# - Nếu nội dung nguồn thay đổi (chữ ký SHA256 khác), thực hiện re-upload để tạo phiên bản mới.
# - Nếu không có quyền upload/truy cập, raise lỗi hướng dẫn cấp quyền/public.
#
# Ghi chú:
# - Triển khai này không tích hợp trực tiếp Google Drive SDK; sử dụng Gemini Python SDK (google.generativeai)
#   với genai.upload_file() để lưu "file nguồn" bên phía Gemini, sau đó truyền {file_data: {file_uri}} khi gọi model.
# - Mapping local được lưu tại .project_assets.json trong thư mục cache_dir do workflow cung cấp.

import os
import io
import json
import time
import hashlib
import logging
import zipfile
from pathlib import Path
from typing import Dict, Any, Optional, List

import google.generativeai as genai

class GeminiProjectFileManager:
    """
    Quản lý upload/tái sử dụng "gói nguồn" cho một dự án.
    - Xác định "project_id" (tên dự án) từ base_filename hoặc tên thư mục.
    - Sinh chữ ký nội dung (SHA256) dựa trên danh sách file nguồn (*.txt).
    - Nếu chữ ký khác bản đã upload → tạo zip và upload, lưu file_uri.
    - Nếu gặp lỗi quyền truy cập → raise lỗi hướng dẫn cấp quyền/public.
    """

    def __init__(self, project_id: str, cache_dir: Path) -> None:
        """
        Args:
            project_id (str): Định danh dự án (ví dụ: tên file không phần mở rộng hoặc tên thư mục).
            cache_dir (Path): Thư mục cache chung của ứng dụng để lưu .project_assets.json.
        """
        self.project_id = project_id
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.mapping_file = self.cache_dir / ".project_assets.json"
        self.mapping: Dict[str, Any] = self._load_mapping()

    def _load_mapping(self) -> Dict[str, Any]:
        """Nạp mapping project_id -> {'sha':..., 'file_uri':..., 'uploaded_at':...}."""
        if self.mapping_file.exists():
            try:
                return json.load(self.mapping_file.open("r", encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_mapping(self) -> None:
        """Lưu mapping ra đĩa (ghi bền vững)."""
        try:
            with self.mapping_file.open("w", encoding="utf-8") as f:
                json.dump(self.mapping, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.warning(f"⚠️ Không thể lưu mapping project assets: {e}")

    def _sha256_of_texts(self, files: List[Path]) -> str:
        """
        Tính SHA256 trên toàn bộ nội dung các file nguồn theo thứ tự tên, để tạo chữ ký dự án.
        Chỉ xét *.txt theo pipeline hiện tại.
        """
        sha = hashlib.sha256()
        for p in sorted(files, key=lambda x: x.name.lower()):
            try:
                data = p.read_bytes()
                # Thêm tên file để phân biệt cùng nội dung nhưng khác tập hợp/đặt tên
                sha.update(p.name.encode("utf-8"))
                sha.update(b"\0")
                sha.update(data)
                sha.update(b"\0\0")
            except Exception:
                # Bỏ qua file lỗi để không chặn toàn bộ; chữ ký sẽ phản ánh các file đọc được
                continue
        return sha.hexdigest()

    def _zip_sources(self, files: List[Path]) -> bytes:
        """Đóng gói các file nguồn vào một archive .zip trong bộ nhớ để upload."""
        bio = io.BytesIO()
        with zipfile.ZipFile(bio, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for p in sorted(files, key=lambda x: x.name.lower()):
                try:
                    zf.writestr(p.name, p.read_bytes())
                except Exception as e:
                    logging.warning(f"⚠️ Bỏ qua khi đóng gói (không đọc được): {p.name} ({e})")
        bio.seek(0)
        return bio.read()

    def ensure_uploaded_for_directory(self, source_dir: Path) -> Optional[str]:
        """
        Đảm bảo tất cả *.txt trong thư mục source_dir được đóng gói và upload.
        Trả về file_uri (str) nếu thành công, None nếu không cần/không thể upload.
        """
        txt_files = list(source_dir.glob("*.txt"))
        if not txt_files:
            logging.warning("ℹ️ Thư mục nguồn không có file .txt để upload.")
            return None
        signature = self._sha256_of_texts(txt_files)
        return self._ensure_uploaded(signature, txt_files)

    def ensure_uploaded_for_file(self, source_file: Path) -> Optional[str]:
        """
        Đảm bảo file đơn được upload.
        Trả về file_uri (str) nếu thành công, None nếu không cần/không thể upload.
        """
        if not source_file.exists():
            logging.warning("ℹ️ File nguồn không tồn tại để upload.")
            return None
        signature = self._sha256_of_texts([source_file])
        return self._ensure_uploaded(signature, [source_file])

    def _ensure_uploaded(self, signature: str, files: List[Path]) -> Optional[str]:
        """
        Kiểm tra mapping theo project_id:
        - Nếu chữ ký trùng → trả về file_uri hiện có (tái sử dụng).
        - Nếu khác → đóng gói zip và upload lên Gemini, cập nhật mapping.
        """
        entry = self.mapping.get(self.project_id)
        if entry and entry.get("sha") == signature and entry.get("file_uri"):
            logging.info("🗂️ Tái sử dụng file_uri đã upload cho dự án này.")
            return entry["file_uri"]

        # Đóng gói zip trong bộ nhớ và ghi tạm ra đĩa để upload (SDK yêu cầu path)
        try:
            zip_bytes = self._zip_sources(files)
            zip_path = self.cache_dir / f"{self.project_id}.zip"
            with open(zip_path, "wb") as f:
                f.write(zip_bytes)
        except Exception as e:
            logging.error(f"❌ Lỗi tạo gói nguồn để upload: {e}")
            return None

        # Upload qua Gemini SDK
        try:
            display_name = f"project_{self.project_id}_{int(time.time())}.zip"
            uploaded = genai.upload_file(path=str(zip_path), display_name=display_name)
            file_uri = getattr(uploaded, "uri", None) or getattr(uploaded, "file_uri", None)
            if not file_uri:
                raise RuntimeError("Upload thành công nhưng không nhận được file_uri.")

            # Lưu mapping
            self.mapping[self.project_id] = {
                "sha": signature,
                "file_uri": file_uri,
                "uploaded_at": int(time.time()),
                "file_name": display_name
            }
            self._save_mapping()
            logging.info(f"✅ Đã upload gói nguồn, file_uri: {file_uri}")
            return file_uri
        except Exception as e:
            msg = str(e).lower()
            # Nhận diện lỗi quyền/không thể truy cập, yêu cầu grant/public
            if any(k in msg for k in ["permission", "forbidden", "unauthorized", "access denied", "credential"]):
                logging.critical("🚫 Không có quyền upload hoặc truy cập Gemini File API.")
                logging.critical("Vui lòng cấp quyền hoặc đặt tài nguyên ở chế độ public để tiếp tục.")
                raise
            logging.error(f"❌ Lỗi upload gói nguồn lên Gemini: {e}")
            return None
