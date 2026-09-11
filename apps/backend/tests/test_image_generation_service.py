"""Phase 13 M2 - ImageGenerationService tests."""

from datetime import datetime, timezone
from types import SimpleNamespace

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

    def list_jobs(self, project_id, limit=50):
        return []


class _FakeProviderManager:
    def adapter_for(self, model_id, capability):
        return object()


class _FakeRecord:
    def __init__(self, project_id):
        self.project_id = project_id


class _FakeAssetVersionService:
    def get_current(self, project_id, entity_type, entity_id):
        return _FakeVersion(f"{entity_id}.png")

    def get(self, version_id):
        raise AssertionError(f"unexpected version lookup: {version_id}")


class _FakeVersion:
    def __init__(self, file_path):
        self.file_path = file_path


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
        _FakeProviderManager(),
        "unused.db",
        _FakeAssetVersionService(),
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


def test_start_shot_uses_explicit_reference_assets(monkeypatch):
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
            }
        ],
    )

    service.start_shot(
        "proj_1",
        "shot_01",
        "model_img",
        "reference_image",
        reference_asset_ids=["character_lin_001"],
    )

    args, kwargs = fake.calls[0]
    assert kwargs["images"] == ["character_lin_001.png"]
    assert kwargs["extra"]["source_refs"][1]["id"] == "character_lin_001"


def test_start_shot_uses_exact_reference_version(monkeypatch, tmp_path):
    fake = _FakeGenerationService()
    service = _service(fake)
    reference_file = tmp_path / "character-v2.png"
    reference_file.write_bytes(b"image")
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
                "reference_prompt": "green robe",
                "fields": {},
            }
        ],
    )
    monkeypatch.setattr(
        service.asset_version_service,
        "get",
        lambda version_id: SimpleNamespace(
            id=version_id,
            project_id="proj_1",
            entity_type="character",
            entity_id="character_lin_001",
            version=2,
            file_path=str(reference_file),
        ),
    )

    service.start_shot(
        "proj_1",
        "shot_01",
        "model_img",
        "reference_image",
        reference_version_ids=["ver_character_v2"],
    )

    _args, kwargs = fake.calls[0]
    assert kwargs["images"] == [str(reference_file)]
    assert kwargs["extra"]["source_refs"][1]["version_id"] == "ver_character_v2"
    assert kwargs["extra"]["source_refs"][1]["version"] == 2


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


def test_explicit_empty_references_and_prompt_override(monkeypatch):
    fake = _FakeGenerationService()
    service = _service(fake)
    monkeypatch.setattr(ScriptRepository, "get_shot_with_scene", lambda *args: (_shot(), _scene()))
    def unexpected(*args):
        pytest.fail("Explicit empty selection must not auto-match assets")
    monkeypatch.setattr(service, "_resolve_shot_asset_references", unexpected)
    service.start_shot("proj_1", "shot_1", "model_img", reference_version_ids=[], prompt="用户新的画面描述")
    _, kwargs = fake.calls[0]
    assert kwargs["images"] == []
    assert kwargs["extra"]["user_prompt"] == "用户新的画面描述"
    assert not any(ref["type"] == "asset" for ref in kwargs["extra"]["source_refs"])


def test_pinned_reference_must_be_selected():
    with pytest.raises(AppError) as exc:
        _service(_FakeGenerationService()).start_shot("proj_1", "shot_1", "model_img", reference_version_ids=[], pinned_version_ids=["other"])
    assert exc.value.code == "invalid_pinned_reference"


def test_plan_shots_skips_existing_versions_and_keeps_ready_shots(monkeypatch):
    service = _service(_FakeGenerationService())
    monkeypatch.setattr(
        ScriptRepository,
        "get_shot_with_scene",
        lambda self, project_id, shot_id: (_shot(id=shot_id), _scene()),
    )
    monkeypatch.setattr(StoryRepository, "list_assets", lambda self, project_id: [])
    monkeypatch.setattr(
        service.asset_version_service,
        "get_current",
        lambda project_id, entity_type, entity_id: _FakeVersion("old.png")
        if entity_id == "shot_existing"
        else None,
    )

    plan = service.plan_shots(
        "proj_1", "model_img", ["shot_ready", "shot_existing", "shot_ready"]
    )

    assert [item["shot_id"] for item in plan["ready"]] == ["shot_ready"]
    assert plan["skipped"][0]["reason"] == "已有当前关键帧版本"


def test_start_shots_adds_shared_batch_metadata(monkeypatch):
    fake = _FakeGenerationService()
    service = _service(fake)
    monkeypatch.setattr(
        ScriptRepository,
        "get_shot_with_scene",
        lambda self, project_id, shot_id: (
            _shot(id=shot_id, shot_number=1 if shot_id == "shot_01" else 2),
            _scene(),
        ),
    )
    monkeypatch.setattr(StoryRepository, "list_assets", lambda self, project_id: [])
    monkeypatch.setattr(
        service.asset_version_service,
        "get_current",
        lambda project_id, entity_type, entity_id: None,
    )

    result = service.start_shots(
        "proj_1", "model_img", ["shot_01", "shot_02"], "第 1 集 · 青云镇"
    )

    assert result["batch_id"].startswith("batch_")
    assert len(fake.calls) == 2
    extras = [kwargs["extra"] for _, kwargs in fake.calls]
    assert {extra["batch_id"] for extra in extras} == {result["batch_id"]}
    assert {extra["batch_label"] for extra in extras} == {"第 1 集 · 青云镇"}
    assert [extra["target_label"] for extra in extras] == [
        "青云镇 · 镜头 1",
        "青云镇 · 镜头 2",
    ]
