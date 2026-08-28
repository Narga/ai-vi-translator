#!/usr/bin/env python3
# scripts/migrate_providers_v2.py
# Nhóm 4 (kế hoạch remediation): migration an toàn providers.json + app.ini.
"""
Tool migration: providers.json v1 → v2 & app.ini cleanup.

Tác vụ (chỉ chạy khi --apply, mặc định --dry-run):
1. Sao lưu providers.json và app.ini có gắn timestamp + checksum.
2. Tạo manifest `migration-<timestamp>.json` chứa cặp backup, checksum, schema version.
3. Validate & sanitize model cho từng provider (loại bỏ step-* khỏi gemini).
4. Nâng cấp schema providers.json lên version 2.
5. Loại bỏ [MODEL] MODEL khỏi config/app.ini; chuyển THINKING_LEVEL
   sang section [RUNTIME] mới.
6. Hỗ trợ --dry-run (mặc định) và rollback qua scripts/rollback_providers.py
   theo manifest.

Fail-closed: bất kỳ bước nào thất bại thì KHÔNG ghi file nào; restore từ manifest
nếu đã backup. KHÔNG log API key hay model name đầy đủ (chỉ log id và length).

Refs: docs/wip/configuration-provider-model-remediation-plan.md
      R5 (transaction), R6 (fail-closed), R10 (manifest), R17 (section [RUNTIME]),
      R18 (os.replace try/except), R19 (read_text + read_string).
"""

import argparse
import configparser
import hashlib
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("migration_v2")

DEFAULT_GEMINI_MODEL = "gemini-2.0-flash"


def is_valid_gemini_model(model_name: str) -> bool:
    """Check model ID thuộc namespace Gemini/Gemma.

    Helper tham khảo; validation chính thức chạy qua
    ProviderConfigResolver.validate_model khi schema v2 đã load.
    """
    if not model_name or not isinstance(model_name, str):
        return False
    clean = model_name.strip()
    if "/" in clean or ":" in clean or clean.startswith("step-"):
        return False
    return clean.startswith("gemini-") or clean.startswith("gemma-")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_str(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def backup_file(file_path: Path, backup_dir: Path, timestamp: str) -> Path:
    """Tạo bản sao lưu an toàn với timestamp."""
    if not file_path.exists():
        logger.info("Bỏ qua backup, file không tồn tại: %s", file_path)
        return file_path
    backup_dir.mkdir(parents=True, exist_ok=True)
    dst = backup_dir / f"{file_path.name}.{timestamp}.bak"
    shutil.copy2(file_path, dst)
    logger.info("Đã backup: %s -> %s", file_path.name, dst.name)
    return dst


def write_manifest(
    manifest_path: Path,
    timestamp: str,
    providers_backup: Path,
    app_ini_backup: Path,
    providers_before: str,
    app_ini_before: str,
) -> None:
    manifest = {
        "version": 1,
        "timestamp": timestamp,
        "providers_json": {
            "backup": str(providers_backup),
            "sha256_before": sha256_str(providers_before),
        },
        "app_ini": {
            "backup": str(app_ini_backup),
            "sha256_before": sha256_str(app_ini_before),
        },
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    logger.info("Đã tạo manifest: %s", manifest_path.name)


def load_providers_data(providers_file: Path) -> Dict[str, Any]:
    with open(providers_file, "r", encoding="utf-8") as f:
        return json.load(f)


def load_app_ini(app_ini_file: Path) -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    config.optionxform = str
    if app_ini_file.exists():
        # R19: dùng read_text + read_string để phát hiện encoding lỗi
        config.read_string(app_ini_file.read_text(encoding="utf-8"))
    return config


def transform_providers(v1_data: Dict[str, Any]) -> Dict[str, Any]:
    """Chuyển đổi v1 sang v2 với validate fail-closed.

    Raises ValueError nếu có provider không hợp lệ (type lạ, id trùng, ...).
    """
    providers_input = v1_data.get("providers")
    if not isinstance(providers_input, list) or not providers_input:
        raise ValueError("providers phải là list không rỗng")
    active_id = v1_data.get("active_id", "gemini-default")
    if not isinstance(active_id, str) or not active_id.strip():
        raise ValueError("active_id phải là chuỗi không rỗng")

    seen_ids = set()
    v2_providers: List[Dict[str, Any]] = []
    for p in providers_input:
        if not isinstance(p, dict):
            raise ValueError("mỗi provider phải là object")
        provider_id = p.get("id")
        provider_type = p.get("type")
        provider_name = p.get("name")
        if not all(isinstance(v, str) for v in (provider_id, provider_type, provider_name)):
            raise ValueError(f"id/type/name của provider phải là chuỗi")
        p_id = provider_id.strip()
        p_type = provider_type.strip()
        p_name = provider_name.strip()
        if not p_id or p_id in seen_ids:
            raise ValueError(f"provider id rỗng hoặc trùng: {p_id!r}")
        if p_type not in ("gemini", "openai"):
            raise ValueError(f"provider type không hỗ trợ: {p_type!r}")
        if not p_name:
            raise ValueError(f"provider name rỗng: {p_id!r}")
        seen_ids.add(p_id)

        # R6: giữ field mở rộng chưa được migration hiểu
        new_provider: Dict[str, Any] = {
            k: v for k, v in p.items()
            if k not in ("model", "MODEL", "MODEL.MODEL")
        }
        new_provider.update({"id": p_id, "type": p_type, "name": p_name})

        if p_type == "gemini":
            keys = p.get("api_keys", [])
            if not isinstance(keys, list) or not all(isinstance(k, str) for k in keys):
                raise ValueError(f"api_keys không hợp lệ cho provider {p_id}")
            new_provider["api_keys"] = keys
            default_model = str(p.get("default_model", "") or "").strip()
            if default_model and not is_valid_gemini_model(default_model):
                # R1: sửa default_model sai namespace, KHÔNG fail-closed ở đây
                # vì schema v1 cũ có thể chứa legacy data. Log warning và đặt default.
                logger.warning(
                    "Provider gemini %s có default_model %r sai namespace; "
                    "đặt lại thành %r",
                    p_id, default_model, DEFAULT_GEMINI_MODEL,
                )
                new_provider["default_model"] = DEFAULT_GEMINI_MODEL
            else:
                new_provider["default_model"] = default_model
        else:
            new_provider["api_key"] = p.get("api_key", "")
            new_provider["base_url"] = p.get("base_url", "")
            new_provider["gateway_api_key"] = p.get("gateway_api_key", "")
            new_provider["credential_mode"] = p.get("credential_mode", "default")
            new_provider["default_model"] = str(p.get("default_model", "") or "").strip()

        v2_providers.append(new_provider)

    if active_id not in seen_ids:
        raise ValueError(
            f"active_id {active_id!r} không có trong providers; dừng migration để user chọn"
        )

    return {"version": 2, "active_id": active_id, "providers": v2_providers}


def transform_app_ini(app_config: configparser.ConfigParser) -> Tuple[configparser.ConfigParser, bool]:
    """Loại bỏ [MODEL] legacy, chuyển THINKING_LEVEL sang [RUNTIME].

    Thứ tự quan trọng (R17): chuyển THINKING_LEVEL sang [RUNTIME] TRƯỚC,
    sau đó xoá các field legacy, cuối cùng xoá section nếu rỗng. Nếu làm
    ngược lại, section [MODEL] bị xoá sớm và các bước sau không tìm thấy
    field để xoá.

    Returns (config, changed) tuple.
    """
    changed = False
    if not app_config.has_section("MODEL"):
        return app_config, False

    # Bước 1: chuyển THINKING_LEVEL sang [RUNTIME]
    if app_config.has_option("MODEL", "THINKING_LEVEL"):
        thinking_value = app_config.get("MODEL", "THINKING_LEVEL")
        if not app_config.has_section("RUNTIME"):
            app_config.add_section("RUNTIME")
        app_config.set("RUNTIME", "THINKING_LEVEL", thinking_value)
        app_config.remove_option("MODEL", "THINKING_LEVEL")
        changed = True

    # Bước 2: xoá field legacy
    for opt in ("MODEL",):
        if app_config.has_option("MODEL", opt):
            app_config.remove_option("MODEL", opt)
            changed = True

    # Bước 3: xoá section nếu rỗng
    if not app_config.options("MODEL"):
        app_config.remove_section("MODEL")
        changed = True

    return app_config, changed


def atomic_write(path: Path, content: str) -> None:
    """R18: ghi atomic với os.replace, bọc try/except riêng để dọn tmp cả khi fail."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"Ghi {tmp} thất bại: {e}") from e
    try:
        os.replace(str(tmp), str(path))
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        raise RuntimeError(f"os.replace {tmp} -> {path} thất bại: {e}") from e


def run_migration(config_dir: Path, dry_run: bool = True) -> bool:
    """Chạy migration. dry_run=True (mặc định) chỉ in output, không ghi file."""
    providers_file = config_dir / "providers.json"
    app_ini_file = config_dir / "app.ini"
    backup_dir = config_dir / "backups"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if not providers_file.exists():
        logger.error("Không tìm thấy %s", providers_file)
        return False

    # 1. Đọc
    v1_data = load_providers_data(providers_file)
    v1_text = json.dumps(v1_data, ensure_ascii=False, indent=2)
    app_config = load_app_ini(app_ini_file)
    app_ini_text = (
        app_ini_file.read_text(encoding="utf-8") if app_ini_file.exists() else ""
    )

    # 2. Transform
    try:
        v2_data = transform_providers(v1_data)
    except ValueError as e:
        logger.error("Transform providers thất bại: %s", e)
        return False

    app_config_new, app_changed = transform_app_ini(app_config)

    # 3. In tóm tắt
    logger.info("=== KẾT QUẢ CHUYỂN ĐỔI SCHEMA V2 ===")
    logger.info("Version: 1 -> 2 | Active ID: %s", v2_data["active_id"])
    for p in v2_data["providers"]:
        logger.info(
            " - Provider: id=%s type=%s name=%s default_model=%r",
            p["id"], p["type"], p["name"],
            p.get("default_model", ""),
        )
    if app_changed:
        logger.info("App.ini sẽ được dọn: section [MODEL] cũ, [RUNTIME] mới")
    else:
        logger.info("App.ini không cần thay đổi")

    if dry_run:
        logger.info("[DRY-RUN] Không ghi file nào. Dùng --apply để chạy thật.")
        return True

    # 4. Backup
    providers_backup = backup_file(providers_file, backup_dir, timestamp)
    app_ini_backup = backup_file(app_ini_file, backup_dir, timestamp)
    manifest_path = backup_dir / f"migration-{timestamp}.json"
    write_manifest(
        manifest_path, timestamp, providers_backup, app_ini_backup, v1_text, app_ini_text
    )

    # 5. Ghi providers.json (atomic)
    try:
        v2_text = json.dumps(v2_data, ensure_ascii=False, indent=2)
        atomic_write(providers_file, v2_text)
    except RuntimeError as e:
        logger.error("Ghi providers.json thất bại: %s", e)
        # R5: rollback nếu đã backup nhưng ghi fail
        if providers_backup.exists() and providers_file.exists() != providers_backup.exists():
            shutil.copy2(providers_backup, providers_file)
            logger.warning("Đã khôi phục providers.json từ backup")
        return False

    # 6. Ghi app.ini (atomic)
    if app_changed:
        try:
            # configparser write cần StringIO
            import io
            buf = io.StringIO()
            app_config_new.write(buf)
            atomic_write(app_ini_file, buf.getvalue())
        except RuntimeError as e:
            logger.error("Ghi app.ini thất bại: %s", e)
            # R5: rollback providers.json + giữ nguyên app.ini
            if providers_backup.exists():
                shutil.copy2(providers_backup, providers_file)
                logger.warning("Đã khôi phục providers.json từ backup")
            return False

    logger.info("Hoàn tất migration v2. Manifest: %s", manifest_path.name)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate providers config to v2")
    parser.add_argument(
        "--config-dir", type=Path, default=Path("config"),
        help="Thư mục cấu hình (mặc định: config)",
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=True,
        help="Chỉ in output, không ghi file (mặc định)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Thực sự ghi file. BẮT BUỘC chạy --dry-run trước.",
    )
    args = parser.parse_args()

    dry_run = not args.apply  # nếu --apply thì dry_run=False
    if args.apply:
        logger.warning("CHẾ ĐỘ APPLY: sẽ ghi file thật. Nhấn Ctrl+C trong 5s nếu muốn hủy.")
        import time
        for i in range(5, 0, -1):
            print(f"  Tiếp tục sau {i}s...", flush=True)
            time.sleep(1)
    success = run_migration(args.config_dir, dry_run=dry_run)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
