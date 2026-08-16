"""多 Provider 视频 Adapter 单元测试（全部 mock HTTP，不触发真实 API）。"""

import httpx
import pytest

from app.core.errors import AppError
from app.services.adapters.base import GenerationRequest, ProviderContext
from app.services.adapters.openrouter_video import OpenRouterVideoAdapter
from app.services.adapters.siliconflow_video import SiliconFlowVideoAdapter
from app.services.adapters.sora import SoraVideoAdapter
from app.services.adapters.zhipu_video import ZhipuVideoAdapter


def _ctx(model_id="sora-2", base_url="https://api.openai.com/v1", key="sk-test"):
    return ProviderContext(
        provider_id="prov_1",
        provider_name="TestProvider",
        preset_key=None,
        base_url=base_url,
        api_key=key,
        model_id=model_id,
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
        self.calls.append({"method": method, "url": url, "headers": headers, "json": json})
        return _FakeResponse(self._status_code, self._payload)

    def get(self, url, headers=None):
        return self._respond("GET", url, headers=headers)

    def post(self, url, headers=None, json=None, files=None, data=None):
        return self._respond("POST", url, headers=headers, json=json)


def _patch_client(monkeypatch, **kwargs):
    monkeypatch.setattr(
        httpx, "Client", lambda timeout=None: _FakeClient(timeout=timeout, **kwargs)
    )


def _request(capability, images=None):
    return GenerationRequest(
        capability=capability,
        prompt="一个镜头",
        images=images or [],
    )


# ---------- Sora ----------


def test_sora_submit_text_to_video(monkeypatch):
    _patch_client(monkeypatch, payload={"id": "video_123"})
    adapter = SoraVideoAdapter()
    task_id = adapter.submit(_ctx(), "text_to_video", _request("text_to_video"))
    assert task_id == "video_123"


def test_sora_submit_image_to_video_requires_image():
    adapter = SoraVideoAdapter()
    with pytest.raises(AppError) as exc:
        adapter.submit(_ctx(), "image_to_video", _request("image_to_video"))
    assert exc.value.code == "image_required"


def test_sora_poll_completed(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={"status": "completed", "url": "https://cdn/v.mp4"},
    )
    status = SoraVideoAdapter().poll(_ctx(), "video_123")
    assert status.status == "completed"
    assert status.result.urls == ["https://cdn/v.mp4"]


def test_sora_poll_content_requires_headers(monkeypatch):
    _patch_client(monkeypatch, payload={"status": "completed"})
    status = SoraVideoAdapter().poll(_ctx(), "video_123")
    assert status.result.download_headers == {"Authorization": "Bearer sk-test"}
    assert "/videos/video_123/content" in status.result.urls[0]


# ---------- OpenRouter ----------


def test_openrouter_submit(monkeypatch):
    _patch_client(monkeypatch, payload={"id": "job_1"})
    task_id = OpenRouterVideoAdapter().submit(
        _ctx(model_id="google/veo-3.1", base_url="https://openrouter.ai/api/v1"),
        "text_to_video",
        _request("text_to_video"),
    )
    assert task_id == "job_1"


def test_openrouter_poll_unsigned_urls(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={"status": "completed", "unsigned_urls": ["https://cdn/v.mp4"]},
    )
    status = OpenRouterVideoAdapter().poll(
        _ctx(model_id="google/veo-3.1", base_url="https://openrouter.ai/api/v1"),
        "job_1",
    )
    assert status.status == "completed"
    assert status.result.urls == ["https://cdn/v.mp4"]


def test_openrouter_image_to_video_requires_image():
    adapter = OpenRouterVideoAdapter()
    with pytest.raises(AppError) as exc:
        adapter.submit(
            _ctx(model_id="google/veo-3.1", base_url="https://openrouter.ai/api/v1"),
            "image_to_video",
            _request("image_to_video"),
        )
    assert exc.value.code == "image_required"


# ---------- Zhipu ----------


def test_zhipu_submit(monkeypatch):
    _patch_client(monkeypatch, payload={"id": "task_1"})
    task_id = ZhipuVideoAdapter().submit(
        _ctx(model_id="cogvideox-3", base_url="https://open.bigmodel.cn/api/paas/v4"),
        "text_to_video",
        _request("text_to_video"),
    )
    assert task_id == "task_1"


def test_zhipu_poll_completed(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={
            "task_status": "SUCCESS",
            "video_result": [{"url": "https://cdn/v.mp4"}],
        },
    )
    status = ZhipuVideoAdapter().poll(
        _ctx(model_id="cogvideox-3", base_url="https://open.bigmodel.cn/api/paas/v4"),
        "task_1",
    )
    assert status.status == "completed"
    assert status.result.urls == ["https://cdn/v.mp4"]


def test_zhipu_duration_clamped_to_supported(monkeypatch):
    client = _FakeClient(payload={"id": "task_1"})
    monkeypatch.setattr(httpx, "Client", lambda timeout=None: client)
    request = GenerationRequest(capability="text_to_video", prompt="x", duration=15)
    ZhipuVideoAdapter().submit(
        _ctx(model_id="cogvideox-3", base_url="https://open.bigmodel.cn/api/paas/v4"),
        "text_to_video",
        request,
    )
    assert client.calls[0]["json"]["duration"] == 10


# ---------- SiliconFlow ----------


def test_siliconflow_submit(monkeypatch):
    _patch_client(monkeypatch, payload={"requestId": "req_1"})
    task_id = SiliconFlowVideoAdapter().submit(
        _ctx(model_id="Wan-AI/Wan2.2-T2V-A14B", base_url="https://api.siliconflow.cn/v1"),
        "text_to_video",
        _request("text_to_video"),
    )
    assert task_id == "req_1"


def test_siliconflow_poll_completed(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={"status": "Succeed", "results": {"videos": [{"url": "https://cdn/v.mp4"}]}},
    )
    status = SiliconFlowVideoAdapter().poll(
        _ctx(model_id="Wan-AI/Wan2.2-I2V-A14B", base_url="https://api.siliconflow.cn/v1"),
        "req_1",
    )
    assert status.status == "completed"
    assert status.result.urls == ["https://cdn/v.mp4"]


def test_siliconflow_image_to_video_requires_image():
    adapter = SiliconFlowVideoAdapter()
    with pytest.raises(AppError) as exc:
        adapter.submit(
            _ctx(model_id="Wan-AI/Wan2.2-I2V-A14B", base_url="https://api.siliconflow.cn/v1"),
            "image_to_video",
            _request("image_to_video"),
        )
    assert exc.value.code == "image_required"
