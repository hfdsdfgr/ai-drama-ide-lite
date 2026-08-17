"""GenerationService - model metadata injection tests."""

from pathlib import Path
from types import SimpleNamespace

from app.services.generation_service import GenerationService


class _FakeRepo:
    def get_model(self, model_id):
        return SimpleNamespace(
            provider_id="prov_1",
            provider_preset_key="bailian",
            model_id=model_id,
        )


class _FakeManager:
    repo = _FakeRepo()

    def adapter_for(self, model_id, capability):
        return object()


class _FakeStore:
    def __init__(self):
        self.created = None

    def create(self, job_type, project_id, **kwargs):
        self.created = kwargs
        return SimpleNamespace(
            id="job_1",
            status="queued",
            model_id=kwargs.get("model_id", ""),
            capability=kwargs.get("capability", ""),
            result_payload=None,
            error=None,
            created_at="now",
        )


def test_create_job_injects_max_reference_images(tmp_path):
    store = _FakeStore()
    service = GenerationService(
        store,
        _FakeManager(),
        Path(tmp_path),
    )

    service.create_job(
        "qwen-image-2.0-pro",
        "reference_image",
        "prompt",
        project_id="proj_1",
        images=[],
        extra={"target_type": "shot"},
    )

    assert store.created["input_payload"]["extra"] == {
        "target_type": "shot",
        "max_reference_images": 3,
    }
