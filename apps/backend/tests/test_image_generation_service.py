"""Phase 13 M2 - ImageGenerationService tests."""

from datetime import datetime, timezone

import pytest

from app.core.errors import AppError
from app.schemas.script import Scene, Shot
from app.services.image_generation_service import ImageGenerationService
from app.services.script_repo import ScriptRepository
from app.services.story_repo import StoryRepository


class _FakeGenerationService:
    def __init__(self):
        self.calls = []
        self.store = _FakeStore()
        self.public = {"job_id": "job_1", "status": "queued"}

    def create_job(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return dict(self.public)

    def get_job(self, job_id):
        return dict(self.public)


class _FakeStore:
    def __init__(self):
        self.project_id = "proj_1"

    def get(self, job_id):
        return _FakeRecord(self.project_id)


class _FakeRecord:
    def __init__(self, project_id):
        self.project_id = project_id


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
        "title": "青云镇",
        "order_index": 0,
        "slugline": "外景 青云镇 黄昏",
        "action": "林凡走向山门",
        "dialogue": "",
        "created_at": now,
        "updated_at": now,
    }
    values.update(overrides)
    return Scene(**values)


def _service(fake):
    return ImageGenerationService(
        fake,
        object(),
        "unused.db",
    )


def test_start_asset_builds_prompt_and_creates_job(monkeypatch):
    fake = _FakeGenerationService()
    service = _service(fake)
    monkeypatch.setattr(
        StoryRepository,
        "list_assets",
        lambda self, project_id: [
            {
                "asset_type": "character",
                "asset_id": "character_lin_001",
                "name": "林凡",
                "reference_prompt": "male protagonist, green cloth robe",
                "fields": {"art_style": "国风"},
            }
        ],
    )

    result = service.start_asset(
        "proj_1",
        "character_lin_001",
        "model_img",
        "text_to_image",
    )

    assert result["job_id"] == "job_1"
    args, kwargs = fake.calls[0]
    assert args[:3] == ("model_img", "text_to_image", args[2])
    assert "male protagonist, green cloth robe" in args[2]
    assert "character reference sheet" in args[2]
    assert kwargs["project_id"] == "proj_1"
    assert kwargs["aspect_ratio"] == "1024x1536"
    assert kwargs["extra"]["target_type"] == "asset"
    assert kwargs["extra"]["target_id"] == "character_lin_001"


def test_start_shot_builds_prompt_with_matched_asset_references(monkeypatch):
    fake = _FakeGenerationService()
    service = _service(fake)
    monkeypatch.setattr(
        ScriptRepository,
        "get_shot_with_scene",
        lambda self, project_id, shot_id: (_shot(), _scene()),
    )
    monkeypatch.setattr(
        StoryRepository,
        "list_assets",
        lambda self, project_id: [
            {
                "asset_type": "character",
                "asset_id": "character_lin_001",
                "name": "林凡",
                "reference_prompt": "male protagonist, green cloth robe",
                "fields": {},
            },
            {
                "asset_type": "location",
                "asset_id": "location_qingyun_001",
                "name": "青云镇",
                "reference_prompt": "mountain town, sunset",
                "fields": {},
            },
        ],
    )

    service.start_shot(
        "proj_1",
        "shot_01",
        "model_img",
        "text_to_image",
        aspect_ratio="9:16",
    )

    args, kwargs = fake.calls[0]
    prompt = args[2]
    assert "character reference (林凡)" in prompt
    assert "location reference (青云镇)" in prompt
    assert "male protagonist, green cloth robe" in prompt
    assert "mountain town, sunset" in prompt
    assert kwargs["aspect_ratio"] == "720x1280"
    assert kwargs["extra"]["target_type"] == "shot"


def test_invalid_image_capability_is_rejected():
    service = _service(_FakeGenerationService())

    with pytest.raises(AppError) as exc:
        service.start_asset(
            "proj_1",
            "character_lin_001",
            "model_img",
            "chat",
        )

    assert exc.value.code == "invalid_image_capability"


def test_get_job_checks_project_ownership():
    fake = _FakeGenerationService()
    service = _service(fake)

    assert service.get_job("proj_1", "job_1")["job_id"] == "job_1"

    fake.store.project_id = "proj_other"
    with pytest.raises(AppError) as exc:
        service.get_job("proj_1", "job_1")
    assert exc.value.code == "image_job_not_found"
