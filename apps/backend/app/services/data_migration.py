"""数据目录迁移：把旧版本存放的数据导入当前数据目录（幂等、只复制不删除）。"""

import shutil
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("data_migration")


def migrate_data_dir(data_dir: Path, *, frozen: bool) -> bool:
    """若当前数据目录为空但旧位置有数据，自动复制迁移。返回是否执行了迁移。

    旧位置候选：打包版早期版本把数据直接放在
    %LOCALAPPDATA%\\AI Drama IDE Lite（无 data 子目录）。
    开发版数据固定在项目内，路径稳定，不参与迁移。
    """
    if not frozen:
        return False
    current_db = data_dir / "ai_drama_ide.db"
    if current_db.exists():
        return False  # 当前目录已有数据

    base = data_dir.parent  # %LOCALAPPDATA%\AI Drama IDE Lite
    legacy_db = base / "ai_drama_ide.db"
    legacy_projects = base / "projects"
    if not legacy_db.exists() and not legacy_projects.exists():
        return False

    data_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    if legacy_db.exists():
        target = data_dir / "ai_drama_ide.db"
        if not target.exists():
            shutil.copy2(legacy_db, target)
            copied.append(str(target))
    if legacy_projects.exists():
        target = data_dir / "projects"
        if not target.exists():
            shutil.copytree(legacy_projects, target)
            copied.append(str(target))
    if copied:
        logger.info("已从旧数据目录迁移数据到 %s: %s", data_dir, ", ".join(copied))
    return bool(copied)
