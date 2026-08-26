#!/usr/bin/env python3
# scripts/rollback_providers.py
# Nhóm 4 (kế hoạch remediation): rollback manifest-based.
"""
Rollback khôi phục providers.json và app.ini từ manifest migration.

R10: KHÔNG tự chọn backup gần nhất của từng file độc lập (sẽ ghép 2 file từ
2 transaction khác nhau). Rollback LUÔN yêu cầu --manifest cụ thể.

Usage:
  python3 scripts/rollback_providers.py --manifest config/backups/migration-20260826_103045.json
"""

import argparse
import json
import logging
import shutil
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("rollback")


def verify_manifest(manifest_path: Path, config_dir: Path) -> bool:
    """Kiểm tra manifest hợp lệ: file backup tồn tại, checksum trùng, path nằm
    trong backup_dir (tránh path traversal).
    """
    if not manifest_path.exists():
        logger.error("Manifest không tồn tại: %s", manifest_path)
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Manifest không đọc được: %s", e)
        return False
    backup_dir = config_dir / "backups"
    for key in ("providers_json", "app_ini"):
        entry = manifest.get(key, {})
        backup_path = Path(entry.get("backup", ""))
        # Path traversal guard
        try:
            backup_path.resolve().relative_to(backup_dir.resolve())
        except ValueError:
            logger.error("Manifest %s: backup path nằm ngoài backup_dir: %s", key, backup_path)
            return False
        if not backup_path.exists():
            logger.error("Manifest %s: file backup không tồn tại: %s", key, backup_path)
            return False
        expected_sha = entry.get("sha256_before", "")
        actual_sha = __import__("hashlib").sha256(
            backup_path.read_bytes()
        ).hexdigest()
        if expected_sha and expected_sha != actual_sha:
            logger.error(
                "Manifest %s: checksum không khớp (expected %s, got %s)",
                key, expected_sha[:8], actual_sha[:8],
            )
            return False
    return True


def rollback(config_dir: Path, manifest_path: Path) -> bool:
    if not verify_manifest(manifest_path, config_dir):
        return False
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for key, target_name in (("providers_json", "providers.json"), ("app_ini", "app.ini")):
        entry = manifest[key]
        backup = Path(entry["backup"])
        target = config_dir / target_name
        if not target.exists() and target_name == "app.ini":
            # app.ini có thể chưa từng tồn tại trước migration
            target.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(backup, target)
            logger.info("Đã rollback %s từ %s", target_name, backup.name)
        except Exception as e:
            logger.error("Rollback %s thất bại: %s", target_name, e)
            return False
    logger.info("Rollback hoàn tất.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Rollback provider config từ manifest")
    parser.add_argument(
        "--config-dir", type=Path, default=Path("config"),
        help="Thư mục cấu hình (mặc định: config)",
    )
    parser.add_argument(
        "--manifest", type=Path, required=True,
        help="Đường dẫn manifest migration (BẮT BUỘC)",
    )
    args = parser.parse_args()

    success = rollback(args.config_dir, args.manifest)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
