"""火山方舟（Volcengine Ark）Adapter 单元测试（全部 mock HTTP，不触发真实 API）。"""

import httpx
import pytest

from app.core.errors import AppError
from app.services.adapters.base import GenerationRequest, ProviderContext
from app.services.adapters.volcengine import VolcengineAdapter
from app.services.capability_registry import resolve_default_capabilities
from app.services.vendor_presets import classify_model


def _ctx(model_id="doubao-seedance-2-0-260128"):
    return ProviderContext(
        provider_id="prov_1",
        provider_name="火山方舟",
        preset_key="volcengine",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        api_key="ark-test",
        model_id=model_id,
        protocol="volcengine",
    )


class _FakeResponse:
    def __init__(self, status_code, payload):
        self._status_code = status_code
        self._payload = payload

    @property
    def status_code(self):
        return self._status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self._status_code >= 400:
            request = httpx.Request("POST", "http://fake")
            raise httpx.HTTPStatusError(
                f"HTTP {self._status_code}",
                request=request,
                response=httpx.Response(self._status_code, request=request),
            )


class _FakeClient:
    def __init__(self, timeout=None, payload=None, status_code=200):
        self._payload = payload
        self._status_code = status_code
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def _respond(self, method, url, headers=None, json=None):
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "json": json}
        )
        return _FakeResponse(self._status_code, self._payload)

    def get(self, url, headers=None):
        return self._respond("GET", url, headers=headers)

    def post(self, url, headers=None, json=None, files=None, data=None):
        return self._respond("POST", url, headers=headers, json=json)


def _patch_client(monkeypatch, **kwargs):
    monkeypatch.setattr(
        httpx, "Client", lambda timeout=None: _FakeClient(timeout=timeout, **kwargs)
    )


def _request(
    capability,
    images=None,
    reference_images=None,
    aspect_ratio=None,
    with_audio=False,
    duration=5,
    extra=None,
):
    return GenerationRequest(
        capability=capability,
        prompt="一只小猫对着镜头打哈欠",
        images=images or [],
        reference_images=reference_images or [],
        aspect_ratio=aspect_ratio,
        duration=duration,
        extra={"with_audio": with_audio, **(extra or {})},
    )


# ---------- 视频：submit ----------


def test_submit_text_to_video(monkeypatch):
    client = _FakeClient(payload={"id": "task_123"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    task_id = VolcengineAdapter().submit(_ctx(), "text_to_video", _request("text_to_video"))
    assert task_id == "task_123"
    body = client.calls[0]["json"]
    assert body["model"] == "doubao-seedance-2-0-260128"
    assert body["content"] == [{"type": "text", "text": "一只小猫对着镜头打哈欠"}]
    assert body["resolution"] == "720p"
    assert body["duration"] == 5
    # 产品约定：默认无声，必须显式传 false（火山方舟默认 true）
    assert body["generate_audio"] is False
    assert body["watermark"] is False
    assert "/contents/generations/tasks" in client.calls[0]["url"]


def test_submit_image_to_video_requires_image():
    adapter = VolcengineAdapter()
    with pytest.raises(AppError) as exc:
        adapter.submit(_ctx(), "image_to_video", _request("image_to_video"))
    assert exc.value.code == "image_required"


def test_submit_image_to_video_with_local_image(monkeypatch, tmp_path):
    image = tmp_path / "frame.png"
    image.write_bytes(b"fake-png-bytes")
    client = _FakeClient(payload={"id": "task_456"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    adapter = VolcengineAdapter()
    task_id = adapter.submit(
        _ctx(), "image_to_video", _request("image_to_video", images=[str(image)])
    )
    assert task_id == "task_456"
    body = client.calls[0]["json"]
    assert body["content"][0]["type"] == "image_url"
    assert body["content"][0]["role"] == "first_frame"
    assert body["content"][0]["image_url"]["url"].startswith("data:image/png;base64,")
    assert body["content"][1]["type"] == "text"


def test_submit_image_to_video_with_reference_images(monkeypatch, tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"fake-png-bytes")
    ref_a = tmp_path / "ref_a.png"
    ref_a.write_bytes(b"fake-png-bytes")
    ref_b = tmp_path / "ref_b.png"
    ref_b.write_bytes(b"fake-png-bytes")
    client = _FakeClient(payload={"id": "task_789"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    VolcengineAdapter().submit(
        _ctx(),
        "image_to_video",
        _request(
            "image_to_video",
            images=[str(frame)],
            reference_images=[str(ref_a), str(ref_b)],
        ),
    )
    body = client.calls[0]["json"]
    roles = [item.get("role") for item in body["content"]]
    assert roles == ["first_frame", "reference_image", "reference_image", None]
    assert all(
        item["image_url"]["url"].startswith("data:image/png;base64,")
        for item in body["content"]
        if item["type"] == "image_url"
    )


def test_submit_ignores_reference_images_on_seedance_1x(monkeypatch, tmp_path):
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"fake-png-bytes")
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"fake-png-bytes")
    client = _FakeClient(payload={"id": "task_1"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    VolcengineAdapter().submit(
        _ctx(model_id="doubao-seedance-1-5-pro-251215"),
        "image_to_video",
        _request(
            "image_to_video",
            images=[str(frame)],
            reference_images=[str(ref)],
        ),
    )
    body = client.calls[0]["json"]
    roles = [item.get("role") for item in body["content"]]
    assert "reference_image" not in roles


def test_submit_combines_reference_images_when_exceeding_limit(
    monkeypatch, tmp_path
):
    from PIL import Image

    frame = tmp_path / "frame.png"
    Image.new("RGB", (64, 64), (10, 20, 30)).save(frame)
    refs = []
    for i in range(10):
        ref = tmp_path / f"ref_{i}.png"
        Image.new("RGB", (64, 64), (i * 10, 80, 120)).save(ref)
        refs.append(str(ref))
    client = _FakeClient(payload={"id": "task_999"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    VolcengineAdapter().submit(
        _ctx(),
        "image_to_video",
        _request(
            "image_to_video",
            images=[str(frame)],
            reference_images=refs,
            extra={"max_reference_images": 9},
        ),
    )
    body = client.calls[0]["json"]
    roles = [item.get("role") for item in body["content"]]
    assert roles == ["first_frame", "reference_image", None]
    ref_items = [
        item
        for item in body["content"]
        if item.get("role") == "reference_image"
    ]
    assert len(ref_items) == 1
    assert ref_items[0]["image_url"]["url"].startswith("data:image/png;base64,")


def test_submit_with_audio_true(monkeypatch):
    client = _FakeClient(payload={"id": "task_1"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    VolcengineAdapter().submit(
        _ctx(), "text_to_video", _request("text_to_video", with_audio=True)
    )
    assert client.calls[0]["json"]["generate_audio"] is True


def test_submit_seedance_1_0_omits_generate_audio(monkeypatch):
    client = _FakeClient(payload={"id": "task_1"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    VolcengineAdapter().submit(
        _ctx(model_id="doubao-seedance-1-0-lite-t2v"),
        "text_to_video",
        _request("text_to_video"),
    )
    assert "generate_audio" not in client.calls[0]["json"]


def test_submit_ratio_mapping(monkeypatch):
    client = _FakeClient(payload={"id": "task_1"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    VolcengineAdapter().submit(
        _ctx(), "text_to_video", _request("text_to_video", aspect_ratio="16:9")
    )
    assert client.calls[0]["json"]["ratio"] == "16:9"

    client.calls.clear()
    VolcengineAdapter().submit(
        _ctx(), "text_to_video", _request("text_to_video", aspect_ratio="2:3")
    )
    assert client.calls[0]["json"]["ratio"] == "adaptive"

    client.calls.clear()
    VolcengineAdapter().submit(
        _ctx(), "text_to_video", _request("text_to_video", aspect_ratio="1080P")
    )
    assert client.calls[0]["json"]["resolution"] == "1080p"
    assert "ratio" not in client.calls[0]["json"]


# ---------- 视频：poll ----------


def test_poll_completed(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={
            "id": "task_1",
            "status": "succeeded",
            "content": {"video_url": "https://cdn/v.mp4"},
        },
    )
    status = VolcengineAdapter().poll(_ctx(), "task_1")
    assert status.status == "completed"
    assert status.result.urls == ["https://cdn/v.mp4"]


def test_poll_failed_with_message(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={
            "id": "task_1",
            "status": "failed",
            "error": {"code": "BadRequest", "message": "参数不合法"},
        },
    )
    status = VolcengineAdapter().poll(_ctx(), "task_1")
    assert status.status == "failed"
    assert status.error == "参数不合法"


def test_poll_failed_real_person_maps_to_chinese_hint(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={
            "id": "task_1",
            "status": "failed",
            "error": {
                "code": "BadRequest",
                "message": (
                    "The request failed because the input image 'content[0]' "
                    "may contain real person."
                ),
            },
        },
    )
    status = VolcengineAdapter().poll(_ctx(), "task_1")
    assert status.status == "failed"
    assert "真实人脸" in status.error
    assert "Seedance" in status.error
    assert "asset://" in status.error


def test_detail_from_response_maps_real_person_to_chinese_hint():
    exc = httpx.HTTPStatusError(
        "Bad Request",
        request=httpx.Request("POST", "http://fake"),
        response=httpx.Response(
            400,
            request=httpx.Request("POST", "http://fake"),
            json={
                "error": {
                    "code": "BadRequest",
                    "message": (
                        "The request failed because the input image 'content[0]' "
                        "may contain real person."
                    ),
                }
            },
        ),
    )
    detail = VolcengineAdapter._detail_from_response(exc, "火山方舟")
    assert "真实人脸" in detail
    assert "火山 Seedance" in detail


def test_detail_from_response_passthrough_unknown_message():
    exc = httpx.HTTPStatusError(
        "Bad Request",
        request=httpx.Request("POST", "http://fake"),
        response=httpx.Response(
            400,
            request=httpx.Request("POST", "http://fake"),
            json={"error": {"code": "BadRequest", "message": "参数不合法"}},
        ),
    )
    assert VolcengineAdapter._detail_from_response(exc, "火山方舟") == "参数不合法"


def test_poll_running(monkeypatch):
    _patch_client(monkeypatch, payload={"id": "task_1", "status": "running"})
    status = VolcengineAdapter().poll(_ctx(), "task_1")
    assert status.status == "running"
    assert status.result is None


def test_fetch_result_not_ready(monkeypatch):
    _patch_client(monkeypatch, payload={"id": "task_1", "status": "running"})
    with pytest.raises(AppError) as exc:
        VolcengineAdapter().fetch_result(_ctx(), "task_1")
    assert exc.value.code == "video_result_not_ready"


# ---------- 图像：Seedream ----------


def test_text_to_image_size_mapping(monkeypatch):
    client = _FakeClient(payload={"data": [{"url": "https://cdn/i.png"}]})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    adapter = VolcengineAdapter()
    result = adapter.generate(
        _ctx(model_id="doubao-seedream-4-0-250828"),
        "text_to_image",
        _request("text_to_image", aspect_ratio="1:1"),
    )
    assert result.urls == ["https://cdn/i.png"]
    body = client.calls[0]["json"]
    assert body["size"] == "2048x2048"
    assert body["watermark"] is False
    assert body["response_format"] == "url"

    client.calls.clear()
    adapter.generate(
        _ctx(model_id="doubao-seedream-4-0-250828"),
        "text_to_image",
        _request("text_to_image", aspect_ratio="16:9"),
    )
    assert client.calls[0]["json"]["size"] == "2560x1440"


def test_text_to_image_default_size(monkeypatch):
    client = _FakeClient(payload={"data": [{"url": "https://cdn/i.png"}]})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    VolcengineAdapter().generate(
        _ctx(model_id="doubao-seedream-4-0-250828"),
        "text_to_image",
        _request("text_to_image"),
    )
    assert client.calls[0]["json"]["size"] == "2048x2048"


# ---------- 预设与能力 ----------


def test_volcengine_classification():
    assert classify_model("volcengine", "doubao-seed-1-6-250615") == "llm"
    assert classify_model("volcengine", "doubao-seedream-4-0-250828") == "image"
    assert classify_model("volcengine", "doubao-seedance-2-0-260128") == "video"


def test_volcengine_capabilities():
    video_caps = resolve_default_capabilities(
        "volcengine", "doubao-seedance-2-0-260128", "video"
    )
    assert {"text_to_video", "image_to_video", "video_audio", "video_dialogue"} <= set(
        video_caps
    )
    image_caps = resolve_default_capabilities(
        "volcengine", "doubao-seedream-4-0-250828", "image"
    )
    assert image_caps == ["text_to_image"]
    llm_caps = resolve_default_capabilities(
        "volcengine", "doubao-seed-1-6-250615", "llm"
    )
    assert llm_caps == []
