"""Phase 13 M1 - Image Prompt Builder tests."""

from datetime import datetime, timezone

import pytest

from app.schemas.script import Scene, Shot
from app.services.image_prompt_builder import (
    build_asset_image_prompt,
    build_shot_image_prompt,
)


def _shot(**overrides) -> Shot:
    now = datetime.now(timezone.utc)
    values = {
        "id": "shot_01",
        "project_id": "proj_1",
        "scene_id": "scene_01",
        "shot_number": 1,
        "order_index": 0,
        "shot_type": "中近景",
        "camera": "推镜",
        "characters": "林凡",
        "action": "他望向山门",
        "lighting": "黄昏逆光",
        "dialogue": "",
        "duration": 3.0,
        "prompt": "",
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Shot(**values)


def _scene(**overrides) -> Scene:
    now = datetime.now(timezone.utc)
    values = {
        "id": "scene_01",
        "project_id": "proj_1",
        "episode_id": "ep_1",
        "novel_id": "novel_1",
        "title": "山门",
        "order_index": 0,
        "slugline": "外景 青云山门 黄昏",
        "action": "林凡缓步走向山门",
        "dialogue": "",
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Scene(**values)


def test_asset_prompt_reuses_reference_prompt_and_appends_consistency():
    plan = build_asset_image_prompt(
        "character",
        reference_prompt="male protagonist, short black hair, dark eyes",
        fields={"art_style": "动漫"},
        aspect_ratio="2:3",
    )

    assert plan.prompt.startswith("male protagonist")
    assert "character reference sheet" in plan.prompt
    assert "consistent character design" in plan.prompt
    assert "no text" in plan.prompt
    assert "动漫" in plan.prompt
    assert plan.aspect_ratio == "2:3"
    assert (plan.width, plan.height) == (1024, 1536)
    assert "bad hands" in plan.negative_prompt


def test_asset_prompt_falls_back_to_structured_fields():
    plan = build_asset_image_prompt(
        "location",
        fields={
            "description": "江南小镇",
            "environment": "群山环绕",
            "time": "白天",
            "lighting": "自然光",
            "style": "国风",
        },
    )

    assert "江南小镇" in plan.prompt
    assert "群山环绕" in plan.prompt
    assert "cinematic establishing shot" in plan.prompt
    assert plan.aspect_ratio == "16:9"
    assert (plan.width, plan.height) == (1280, 720)


def test_asset_prompt_custom_aspect_ratio():
    plan = build_asset_image_prompt(
        "prop",
        reference_prompt="white jade pendant",
        aspect_ratio="9:16",
    )

    assert plan.aspect_ratio == "9:16"
    assert (plan.width, plan.height) == (720, 1280)


def test_shot_prompt_keeps_user_prompt_and_adds_references():
    plan = build_shot_image_prompt(
        _shot(prompt="close-up of Lin Fan looking back"),
        _scene(),
        asset_references=[
            {
                "asset_type": "character",
                "name": "林凡",
                "reference_prompt": "male protagonist, green cloth robe",
            }
        ],
    )

    assert plan.prompt.startswith("close-up of Lin Fan")
    assert "character reference (林凡)" in plan.prompt
    assert "male protagonist, green cloth robe" in plan.prompt
    assert "consistent character design" in plan.prompt
    assert "no subtitles" in plan.prompt
    assert plan.aspect_ratio == "16:9"
    assert (plan.width, plan.height) == (1280, 720)
    assert plan.source_refs[0]["id"] == "shot_01"


def test_shot_prompt_falls_back_to_shot_fields():
    plan = build_shot_image_prompt(_shot())

    assert "中近景" in plan.prompt
    assert "推镜" in plan.prompt
    assert "林凡" in plan.prompt
    assert "storyboard frame" in plan.prompt


def test_invalid_asset_type_raises():
    with pytest.raises(ValueError):
        build_asset_image_prompt("unknown", reference_prompt="x")


def test_invalid_aspect_ratio_raises():
    with pytest.raises(ValueError):
        build_shot_image_prompt(_shot(), aspect_ratio="21:9")
