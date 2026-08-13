"""ID 生成规范（DEVELOPMENT.md 第 10 节：唯一 Asset ID）。"""

import re
import uuid

ASSET_TYPES = {
    "character",
    "location",
    "prop",
    "costume",
    "creature",
    "vehicle",
    "other",
}

def new_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


def slugify(name: str) -> str:
    """把名称转成 ID 可用的 slug：保留中英文词，用下划线连接。"""
    parts = re.findall(r"\w+", name.strip().lower())
    return "_".join(parts) if parts else "unnamed"


def new_asset_id(asset_type: str, name: str, seq: int) -> str:
    """例如：character_lin_fan_001（DEVELOPMENT.md 示例格式）。"""
    if asset_type not in ASSET_TYPES:
        raise ValueError(f"未知资产类型: {asset_type}")
    return f"{asset_type}_{slugify(name)}_{seq:03d}"
