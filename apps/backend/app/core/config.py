"""Application settings loaded from environment variables / .env file."""

import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
    """数据目录：PyInstaller 打包版用用户目录（防临时解压目录丢数据），开发版保持项目内。"""
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            # macOS 惯例：~/Library/Application Support/<App>/data
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
        return base / "AI Drama IDE Lite" / "data"
    return BACKEND_ROOT / "data"


class Settings(BaseSettings):
    """Runtime configuration.

    优先级：环境变量 > .env 文件 > 默认值。
    API Key 等密钥绝不放入本配置或项目文件（见 DEVELOPMENT_RULES.md 第 15 条）。
    """

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Drama IDE Lite"
    env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    data_dir: Path = Field(default_factory=_default_data_dir)
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "tauri://localhost",
        "http://tauri.localhost",
    ]

    @property
    def projects_dir(self) -> Path:
        """项目存储根目录（每个项目一个子目录，大文件落盘）。"""
        return self.data_dir / "projects"

    @property
    def db_path(self) -> Path:
        """SQLite 数据库文件路径（Phase 1 起为结构化数据唯一事实源）。"""
        return self.data_dir / "ai_drama_ide.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
