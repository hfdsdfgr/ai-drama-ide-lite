"""Capability Engine 测试（Phase 4）。"""

import pytest

from app.core.errors import AppError
from app.services.capability_registry import (
    infer_capabilities,
    parse,
    serialize,
    validate_capabilities,
)


def _create_provider(client, preset="openai", **kwargs):
    payload = {"preset_key": preset, "api_key": "sk-test-123", **kwargs}
    return client.post("/api/providers", json=payload).json()


def _add_model(client, provider_id, model_id, model_type):
    response = client.post(
        "/api/models",
        json={"provider_id": provider_id, "model_id": model_id, "model_type": model_type},
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------- 规则推断（单元） ----------


def test_infer_image_rules():
    assert infer_capabilities("openai", "gpt-image-1", "image") == [
        "image_to_image",
        "reference_image",
        "text_to_image",
    ]
    assert infer_capabilities("openai", "dall-e-3", "image") == ["text_to_image"]
    assert infer_capabilities("bailian", "qwen-image-plus", "image") == [
        "image_to_image",
        "reference_image",
        "text_to_image",
    ]


def test_infer_video_rules():
    assert infer_capabilities("openai", "sora-2", "video") == [
        "image_to_video",
        "text_to_video",
    ]
    assert infer_capabilities("bailian", "wan2.1-t2v", "video") == ["text_to_video"]


def test_infer_llm_and_defaults():
    assert infer_capabilities("openai", "gpt-4o", "llm") == []
    assert infer_capabilities(None, "custom-image", "image") == ["text_to_image"]
    assert infer_capabilities(None, "custom-video", "video") == ["text_to_video"]


def test_validate_capabilities():
    assert validate_capabilities("image", ["text_to_image", "image_to_image"]) == [
        "image_to_image",
        "text_to_image",
    ]
    with pytest.raises(AppError) as exc:
        validate_capabilities("image", ["text_to_video"])
    assert exc.value.code == "capability_type_mismatch"
    with pytest.raises(AppError) as exc:
        validate_capabilities("video", ["unknown_cap"])
    assert exc.value.code == "unknown_capability"


def test_serialize_parse_roundtrip():
    raw = serialize(["image_to_image", "text_to_image"])
    assert parse(raw) == ["image_to_image", "text_to_image"]
    assert parse("") == []
    assert parse("not-json") == []


# ---------- API 集成 ----------


def test_model_auto_capabilities(client):
    provider = _create_provider(client)
    image = _add_model(client, provider["id"], "gpt-image-1", "image")
    assert image["capabilities"] == [
        "image_to_image",
        "reference_image",
        "text_to_image",
    ]
    assert image["capability_source"] == "auto"

    dalle = _add_model(client, provider["id"], "dall-e-3", "image")
    assert dalle["capabilities"] == ["text_to_image"]

    llm = _add_model(client, provider["id"], "gpt-4o", "llm")
    assert llm["capabilities"] == []


def test_manual_override_and_reset(client):
    provider = _create_provider(client)
    model = _add_model(client, provider["id"], "dall-e-3", "image")

    override = client.put(
        f"/api/models/{model['id']}/capabilities",
        json={"capabilities": ["text_to_image", "image_to_image"], "source": "manual"},
    )
    assert override.status_code == 200
    body = override.json()
    assert body["capabilities"] == ["image_to_image", "text_to_image"]
    assert body["capability_source"] == "manual"

    reset = client.put(
        f"/api/models/{model['id']}/capabilities",
        json={"capabilities": [], "source": "auto"},
    )
    assert reset.status_code == 200
    body = reset.json()
    assert body["capabilities"] == ["text_to_image"]
    assert body["capability_source"] == "auto"


def test_capability_filter(client):
    provider = _create_provider(client)
    _add_model(client, provider["id"], "gpt-image-1", "image")
    _add_model(client, provider["id"], "dall-e-3", "image")

    response = client.get("/api/models", params={"capability": "image_to_image"})
    assert response.status_code == 200
    ids = [m["model_id"] for m in response.json()]
    assert ids == ["gpt-image-1"]

    response = client.get("/api/models", params={"capability": "text_to_image"})
    ids = [m["model_id"] for m in response.json()]
    assert ids == ["dall-e-3", "gpt-image-1"]


def test_capability_type_mismatch_rejected(client):
    provider = _create_provider(client)
    model = _add_model(client, provider["id"], "gpt-image-1", "image")
    response = client.put(
        f"/api/models/{model['id']}/capabilities",
        json={"capabilities": ["text_to_video"], "source": "manual"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "capability_type_mismatch"


def test_llm_capability_rejected(client):
    provider = _create_provider(client)
    model = _add_model(client, provider["id"], "gpt-4o", "llm")
    response = client.put(
        f"/api/models/{model['id']}/capabilities",
        json={"capabilities": ["text_to_image"], "source": "manual"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "capability_type_mismatch"
