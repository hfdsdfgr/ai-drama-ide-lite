"""本地内置厂商模型列表（精选快照，见 vendor_models.json）。"""

import json
from pathlib import Path

_CATALOG_PATH = Path(__file__).with_name("vendor_models.json")


def load_catalog() -> dict:
    with _CATALOG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_builtin_models(preset_key: str) -> list[dict]:
    catalog = load_catalog()
    return catalog.get(preset_key, [])


def get_builtin_capabilities(preset_key: str, model_id: str) -> list[str] | None:
    """返回内置目录中该模型的能力集；未收录返回 None。"""
    for item in get_builtin_models(preset_key):
        if item.get("id") == model_id:
            caps = item.get("capabilities")
            return list(caps) if isinstance(caps, list) else []
    return None
