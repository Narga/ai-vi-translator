# backend/infrastructure/config/app_config_service.py
# AppConfigService - Centralized config access cho backend

"""
AppConfigService bọc services/config_service.py hiện có
và cung cấp API dùng chung cho CLI và WebUI.

Phase 04: Tách logic config ra khỏi main.py và webui/helpers.py.
"""

import configparser
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class AppConfigService:
    """
    Centralized configuration service cho backend.

    Bọc services/config_service.py:ConfigService hiện có
    và cung cấp API tiện lợi hơn cho các use case.

    Sử dụng:
        from backend.infrastructure.config.app_config_service import AppConfigService
        config_service = AppConfigService()
        model = config_service.get_default_model()
    """

    def __init__(self, config_dir: Optional[Path] = None):
        """
        Khởi tạo AppConfigService.

        Args:
            config_dir: Đường dẫn đến config directory.
                       Mặc định: Path("config")
        """
        self._config_dir = config_dir or Path("config")
        self._config = configparser.ConfigParser()
        self._config.optionxform = str  # Preserve case
        # B2: _pending buffer cho double-buffering pattern (R25)
        self._pending: Optional[configparser.ConfigParser] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load config từ app.ini."""
        config_file = self._config_dir / "app.ini"
        if config_file.exists():
            self._config.read(config_file, encoding="utf-8")
            logger.debug(f"Loaded config from {config_file}")
        else:
            logger.warning(f"Config file not found: {config_file}")

    def reload(self) -> None:
        """Reload config từ disk."""
        self._load_config()

    # ------------------------------------------------------------------
    # Generic access
    # ------------------------------------------------------------------

    def get(
        self,
        section: str,
        key: str,
        fallback: Any = None,
        value_type: type = str,
    ) -> Any:
        """
        Lấy giá trị config.

        Args:
            section: Tên section (e.g., 'MODEL', 'PROCESSING')
            key: Tên key
            fallback: Giá trị mặc định
            value_type: Kiểu dữ liệu (str, int, float, bool)

        Returns:
            Giá trị config đã convert
        """
        if not self._config.has_section(section):
            return fallback

        if not self._config.has_option(section, key):
            return fallback

        if value_type == bool:
            return self._config.getboolean(section, key, fallback=fallback)
        elif value_type == int:
            return self._config.getint(section, key, fallback=fallback)
        elif value_type == float:
            return self._config.getfloat(section, key, fallback=fallback)
        else:
            return self._config.get(section, key, fallback=fallback)

    def get_section(self, section: str) -> Dict[str, str]:
        """Lấy tất cả key-value trong section."""
        if self._config.has_section(section):
            return dict(self._config.items(section))
        return {}

    def set_value(self, section: str, key: str, value: str) -> None:
        """
        Set giá trị config (in-memory).

        Args:
            section: Tên section
            key: Tên key
            value: Giá trị
        """
        if not self._config.has_section(section):
            self._config.add_section(section)
        self._config.set(section, key, str(value))

    def save(self) -> None:
        """Lưu config ra file app.ini (backward compat: in-memory state).

        Nếu có _pending (do apply_values trước đó), ghi _pending thay vì _config
        rồi swap. Nếu không có _pending, ghi _config như cũ.
        """
        config_file = self._config_dir / "app.ini"
        self._config_dir.mkdir(parents=True, exist_ok=True)
        # Nếu có _pending, ghi _pending thay vì _config hiện tại
        target_config = self._pending if self._pending is not None else self._config
        # R12: atomic write với .tmp + os.replace
        tmp = config_file.with_suffix(config_file.suffix + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                target_config.write(f)
            os.replace(str(tmp), str(config_file))
        except OSError:
            # Fallback: cross-filesystem
            import shutil
            if tmp.exists():
                tmp.unlink()
            shutil.move(str(tmp), str(config_file))
        # Commit: swap _pending → _config nếu có
        if self._pending is not None:
            self._config = self._pending
            self._pending = None
        logger.info(f"Saved config to {config_file}")

    def apply_values(self, pending_values: Dict[Tuple[str, str], str]) -> None:
        """B2: apply staged values lên _pending buffer (deep copy từ _config).

        pending_values: dict mapping (section, key) → value. Validate đã được
        route thực hiện trước khi gọi; method này chỉ stage thay đổi.

        Pattern double-buffering (R25):
        - apply_values(): copy _config → _pending, mutate _pending theo values
        - save(): ghi _pending ra file atomic, swap _config ← _pending
        - Nếu save() fail (vd disk full), _config không bị thay đổi; retry được

        Lưu ý: get() trả fallback mặc định khi section/option không tồn tại;
        apply_values KHÔNG thêm option mới nếu caller truyền key không tồn tại
        trong section. Caller phải đảm bảo section/option hợp lệ.
        """
        import copy
        # R12/R-O2: deep copy để mọi thay đổi nằm trong _pending
        self._pending = copy.deepcopy(self._config)
        for (section, key), value in pending_values.items():
            if not self._pending.has_section(section):
                self._pending.add_section(section)
            self._pending.set(section, key, str(value))

    def get_pending_snapshot(self) -> Optional[str]:
        """B2: trả text INI của _pending (nếu có) hoặc None. Dùng cho test/rollback."""
        if self._pending is None:
            return None
        import io
        buf = io.StringIO()
        self._pending.write(buf)
        return buf.getvalue()

    # ------------------------------------------------------------------
    # Convenience methods cho các giá trị thường dùng
    # ------------------------------------------------------------------

    def get_default_model(self) -> str:
        """Lấy model mặc định từ active provider."""
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService(self._config_dir)
        return provider_service.get_active_default_model()

    def get_qa_model(self) -> str:
        """Lấy QA model từ active provider (providers.json là nguồn sự thật).

        R-O2 + B1: đọc từ ProviderService thay vì app.ini legacy field [MODEL] QA_MODEL.
        Fallback về default_model nếu qa_model chưa cấu hình. Trả '' nếu cả hai đều
        rỗng — caller (TranslationService, route) phải check '' và xử lý cấu hình
        thiếu. KHÔNG fallback cứng về "gemini-3-flash-preview" cho mọi provider type.

        Backward compat: giữ signature trả str (không None) để 3 caller hiện tại
        (`translate_text_use_case.py:143`, `webui/helpers.py`,
        `core/executor.py:114`) không cần đổi. Caller nào cần phân biệt
        'rỗng' với 'không có' thì dùng `get_qa_model_or_none()`.
        """
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService(self._config_dir)
        qa = provider_service.get_active_qa_model()
        if qa:
            return qa
        return provider_service.get_active_default_model()

    def get_qa_model_or_none(self) -> Optional[str]:
        """B1: trả Optional[str] để phân biệt 'rỗng' với 'không có config'.

        None = providers.json không tồn tại hoặc providers rỗng (không có active provider).
        "" = active provider không cấu hình qa_model và default_model.
        "<model>" = cả hai đều cấu hình, trả về qa_model (ưu tiên) hoặc default_model.

        Caller mới (route /api/translate, /api/providers/<id>/models) nên dùng method
        này để trả 400 có cấu trúc khi provider thiếu model.
        """
        from backend.infrastructure.providers.provider_service import ProviderService
        provider_service = ProviderService(self._config_dir)
        if not provider_service.get_active_provider_config():
            return None
        qa = provider_service.get_active_qa_model()
        if qa:
            return qa
        default = provider_service.get_active_default_model()
        return default if default else ""

    def get_default_chunk_size(self) -> int:
        """Lấy chunk size mặc định. Bảng default kế hoạch mục 1.2: 20000."""
        return self.get(
            "PROCESSING", "MAX_CHARS_PER_CHUNK", fallback=20000, value_type=int
        )

    def get_temperature(self) -> float:
        """Lấy temperature mặc định. Bảng default kế hoạch mục 1.2: 1.0."""
        return self.get(
            "PROCESSING", "TEMPERATURE", fallback=1.0, value_type=float
        )

    def get_context_char_count(self) -> int:
        """Lấy context char count."""
        return self.get(
            "PROCESSING", "CONTEXT_CHAR_COUNT", fallback=500, value_type=int
        )

    def get_thinking_level(self) -> str:
        """Lấy thinking level cho Gemini API (OFF/MINIMAL/LOW/MEDIUM/HIGH).

        Bảng default kế hoạch mục 1.2: OFF (section [RUNTIME] sau khi đổi tên từ
        [MODEL] cũ). Chỉ truyền vào adapter hỗ trợ thinking; các provider không hỗ
        trợ sẽ bị adapter bỏ qua.
        """
        return self.get("RUNTIME", "THINKING_LEVEL", fallback="OFF")

    def get_active_provider(self) -> str:
        """Lấy active AI provider (gemini hoặc openai). Delegate sang ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService(self._config_dir).get_active_provider()

    def set_active_provider(self, provider: str) -> None:
        """Set active AI provider. Delegate sang ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        ProviderService(self._config_dir).select_provider_by_type(provider)

    def get_openai_base_url(self) -> Optional[str]:
        """Lấy OpenAI base URL. Delegate sang ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService(self._config_dir).get_active_base_url()

    def get_openai_model(self) -> str:
        """Lấy OpenAI model mặc định. Delegate sang ProviderService."""
        from backend.infrastructure.providers.provider_service import ProviderService
        return ProviderService(self._config_dir).get_active_default_model()



    def get_logs_dir(self) -> str:
        """Lấy logs directory path."""
        return self.get("DIRECTORIES", "LOGS_DIR", fallback="workspace/logs")

    def get_checkpoints_dir(self) -> str:
        """Lấy checkpoints directory path."""
        return self.get(
            "DIRECTORIES", "CHECKPOINTS_DIR", fallback="workspace/checkpoints"
        )
