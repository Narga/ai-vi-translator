# backend/facade/app_service.py
# AppService - Entrypoint chung cho CLI và WebUI
# Phase 03: Tạo khung, chưa triển khai logic

"""
AppService là facade chính để CLI và WebUI gọi về backend.

Sau khi hoàn tất các phase, AppService sẽ cung cấp:
- Translation use case
- Spellcheck use case
- Project CRUD operations
- Config/Key/Prompt management
- Workspace management

Hiện tại chỉ tạo khung, chưa có logic.
"""


class AppService:
    """
    Facade service cho toàn bộ backend.

    Sử dụng:
        from backend.facade.app_service import AppService
        app_service = AppService()
    """

    def __init__(self):
        """Khởi tạo AppService."""
        self._initialized = False

    def initialize(self):
        """
        Khởi tạo các dependencies cần thiết.

        Gọi một lần khi application start.
        """
        # TODO: Phase 04+ sẽ thêm config, key services
        self._initialized = True

    @property
    def is_initialized(self) -> bool:
        """Kiểm tra đã khởi tạo chưa."""
        return self._initialized

    # ------------------------------------------------------------------
    # Placeholder methods - sẽ được implement trong các phase sau
    # ------------------------------------------------------------------

    def get_version(self) -> str:
        """Lấy phiên bản backend."""
        return "0.1.0"

    def get_status(self) -> dict:
        """
        Lấy trạng thái hệ thống.

        Returns:
            Dict chứa status info
        """
        # TODO: Phase 04+ sẽ implement
        return {
            "initialized": self._initialized,
            "version": self.get_version(),
        }
