"""ID 规范测试（DEVELOPMENT.md 第 10 节）。"""

import re

from app.services.ids import new_asset_id, new_project_id, slugify


def test_project_id_format():
    assert re.fullmatch(r"proj_[0-9a-f]{12}", new_project_id())


def test_asset_id_format():
    assert new_asset_id("character", "Lin Fan", 1) == "character_lin_fan_001"
    assert new_asset_id("character", "林凡", 1) == "character_林凡_001"
    assert new_asset_id("location", "青云门", 12) == "location_青云门_012"


def test_slugify_fallback():
    assert slugify("!!!") == "unnamed"
