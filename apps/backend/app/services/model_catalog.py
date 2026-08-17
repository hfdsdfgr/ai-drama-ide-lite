"""本地内置厂商模型列表（精选快照，见 vendor_models.json）。"""

import json
from pathlib import Path

from app.services.vendor_presets import get_preset

_CATALOG_PATH = Path(__file__).with_name("vendor_models.json")


def load_catalog() -> dict:
    with _CATALOG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_builtin_models(preset_key: str) -> list[dict]:
    catalog = load_catalog()
    preset = get_preset(preset_key)
    key = preset.catalog_key if preset and preset.catalog_key else preset_key
    return catalog.get(key, [])


def get_builtin_capabilities(preset_key: str, model_id: str) -> list[str] | None:
    """返回内置目录中该模型的能力集；未收录返回 None。"""
    for item in get_builtin_models(preset_key):
        if item.get("id") == model_id:
            caps = item.get("capabilities")
            return list(caps) if isinstance(caps, list) else []
    return None


def get_builtin_max_reference_images(preset_key: str, model_id: str) -> int | None:
    """返回内置目录中该模型最多可接收的参考图数量；未收录或无字段返回 None。"""
    for item in get_builtin_models(preset_key):
        if item.get("id") == model_id:
            value = item.get("max_reference_images")
            if isinstance(value, int) and value > 0:
                return value
            return None
    return None
