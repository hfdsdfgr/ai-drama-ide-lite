"""项目目录结构与本地文件存储。"""

from pathlib import Path

PROJECT_SUBDIRS = [
    "novel",
    "story",
    "scripts",
    "characters",
    "locations",
    "props",
    "storyboards",
    "generations",
    "jobs",
]


def ensure_project_layout(project_dir: Path) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    for name in PROJECT_SUBDIRS:
        (project_dir / name).mkdir(exist_ok=True)
