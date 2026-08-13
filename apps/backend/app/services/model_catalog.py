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
