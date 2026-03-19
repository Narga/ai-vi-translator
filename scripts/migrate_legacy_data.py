# scripts/migrate_legacy_data.py
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

def migrate():
    base_dir = Path(".")
    workspace = base_dir / "workspace"
    project_dir = workspace / "projects" / "default-project"
    
    # 1. Ensure default-project exists
    from webui.helpers import ensure_default_project
    ensure_default_project()
    
    # 2. Migrate Input -> Sources
    legacy_input = workspace / "input"
    if legacy_input.exists():
        logger.info(f"Migrating files from {legacy_input}...")
        for f in legacy_input.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                dest = project_dir / "sources" / f.name
                try:
                    shutil.move(str(f), str(dest))
                    logger.info(f"  [Input] Moved: {f.name}")
                except Exception as e:
                    logger.error(f"  Error moving {f.name}: {e}")

    # 3. Migrate Output -> Translated
    legacy_output = workspace / "output"
    if legacy_output.exists():
        logger.info(f"Migrating files from {legacy_output}...")
        for f in legacy_output.rglob("*"):
            # Skip _archived for now, or move it too? 
            # Let's move everything but skip the dir itself if it's special
            if f.is_file() and not f.name.startswith("."):
                rel_path = f.relative_to(legacy_output)
                dest = project_dir / "translated" / rel_path
                try:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(f), str(dest))
                    logger.info(f"  [Output] Moved: {rel_path}")
                except Exception as e:
                    logger.error(f"  Error moving {rel_path}: {e}")

    # 4. Migrate Done -> Translated
    legacy_done = workspace / "done"
    if legacy_done.exists():
        logger.info(f"Migrating files from {legacy_done}...")
        for f in legacy_done.rglob("*"):
            if f.is_file() and not f.name.startswith("."):
                dest = project_dir / "translated" / f.name
                try:
                    if dest.exists():
                        # Rename if conflict
                        dest = project_dir / "translated" / f"done_{f.name}"
                    shutil.move(str(f), str(dest))
                    logger.info(f"  [Done] Moved: {f.name}")
                except Exception as e:
                    logger.error(f"  Error moving {f.name}: {e}")

    # 5. Merge Translation Memory
    legacy_tm_file = workspace / "translation_memory" / "memory.json"
    project_tm_file = project_dir / "profile" / "translation_memory" / "memory.json"
    
    if legacy_tm_file.exists():
        logger.info("Merging legacy Translation Memory...")
        try:
            with open(legacy_tm_file, "r", encoding="utf-8") as f:
                legacy_tm = json.load(f)
            
            if project_tm_file.exists():
                with open(project_tm_file, "r", encoding="utf-8") as f:
                    project_tm = json.load(f)
            else:
                project_tm = {"entries": {}}

            # Simple merge
            if "entries" in legacy_tm:
                for key, val in legacy_tm["entries"].items():
                    if key not in project_tm["entries"]:
                        project_tm["entries"][key] = val
            
            with open(project_tm_file, "w", encoding="utf-8") as f:
                json.dump(project_tm, f, ensure_ascii=False, indent=2)
            logger.info("  TM Merge complete.")
        except Exception as e:
            logger.error(f"  Error merging TM: {e}")

    logger.info("Migration finished.")

if __name__ == "__main__":
    migrate()
