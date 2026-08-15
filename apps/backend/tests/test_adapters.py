"""Provider Adapter 单元测试（Phase 5）。"""

import httpx
import pytest

from app.core.errors import AppError
from app.services.adapters.base import (
    GenerationRequest,
    ProviderContext,
)
from app.services.adapters.dashscope import DashScopeAdapter
from app.services.adapters.openai_compat import OpenAICompatAdapter


def _ctx(model_id="gpt-4o", base_url="https://api.openai.com/v1", preset=None, key="sk-test"):
    return ProviderContext(
        provider_id="prov_1",
        provider_name="OpenAI",
        preset_key=preset,
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
    def __init__(self, timeout=None, payload=None, status_code=200, raise_exc=None):
        self._payload = payload
        self._status_code = status_code
        self._raise_exc = raise_exc
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def _respond(self, method, url):
        self.calls.append((method, url))
        if self._raise_exc:
            raise self._raise_exc
        return _FakeResponse(self._status_code, self._payload)

    def get(self, url, headers=None):
        return self._respond("GET", url)

    def post(self, url, headers=None, json=None, files=None, data=None):
        return self._respond("POST", url)


def _patch_client(monkeypatch, **kwargs):
    monkeypatch.setattr(
        httpx, "Client", lambda timeout=None: _FakeClient(timeout=timeout, **kwargs)
    )


# ---------- OpenAI 兼容：chat ----------


def test_chat_success(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={"choices": [{"message": {"content": "你好"}}]},
    )
    adapter = OpenAICompatAdapter()
    text = adapter.chat(_ctx(), [{"role": "user", "content": "hi"}])
    assert text == "你好"


def test_chat_stream_parses_deltas(monkeypatch):
    lines = [
        'data: {"choices":[{"delta":{"content":"你"}}]}',
        "",
        'data: {"choices":[{"delta":{"content":"好"}}]}',
        "",
        "data: [DONE]",
        "",
    ]

    class _FakeStreamCtx:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self):
            return iter(lines)

    class _FakeStreamingClient:
        def __init__(self, timeout=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, method, url, headers=None, json=None):
            return _FakeStreamCtx()

    monkeypatch.setattr(
        httpx, "Client", lambda timeout=None: _FakeStreamingClient(timeout=timeout)
    )
    adapter = OpenAICompatAdapter()
    chunks = list(
        adapter.chat_stream(_ctx(), [{"role": "user", "content": "hi"}])
    )
    assert chunks == ["你", "好"]


def test_chat_auth_fail(monkeypatch):
    _patch_client(monkeypatch, status_code=401, payload={})
    adapter = OpenAICompatAdapter()
    with pytest.raises(AppError):
        adapter.chat(_ctx(), [{"role": "user", "content": "hi"}])


def test_chat_region_hint_for_dashscope(monkeypatch):
    _patch_client(monkeypatch, status_code=401, payload={})
    adapter = OpenAICompatAdapter()
    with pytest.raises(AppError) as exc:
        adapter.chat(
            _ctx(base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"),
            [{"role": "user", "content": "hi"}],
        )
    assert "dashscope" in str(exc.value.message)


# ---------- OpenAI 兼容：图片 ----------


def test_text_to_image_url(monkeypatch, tmp_path):
    _patch_client(monkeypatch, payload={"data": [{"url": "https://cdn/x.png"}]})
    adapter = OpenAICompatAdapter()
    result = adapter.generate(
        _ctx(model_id="gpt-image-1"),
        "text_to_image",
        GenerationRequest(
            capability="text_to_image",
            prompt="一只猫",
            extra={"output_dir": str(tmp_path)},
        ),
    )
    assert result.urls == ["https://cdn/x.png"]


def test_text_to_image_b64_saved(monkeypatch, tmp_path):
    import base64
    from pathlib import Path

    png = base64.b64encode(b"fake-png-bytes").decode()
    _patch_client(monkeypatch, payload={"data": [{"b64_json": png}]})
    adapter = OpenAICompatAdapter()
    result = adapter.generate(
        _ctx(model_id="dall-e-3"),
        "text_to_image",
        GenerationRequest(
            capability="text_to_image",
            prompt="一只猫",
            extra={"output_dir": str(tmp_path)},
        ),
    )
    assert len(result.urls) == 1
    saved = tmp_path / Path(result.urls[0]).name
    assert saved.read_bytes() == b"fake-png-bytes"


def test_image_edit_requires_input_image():
    adapter = OpenAICompatAdapter()
    try:
        adapter.generate(
            _ctx(model_id="gpt-image-1"),
            "image_to_image",
            GenerationRequest(capability="image_to_image", prompt="改一下"),
        )
    except AppError as exc:
        assert exc.code == "image_required"
    else:
        raise AssertionError("should raise image_required")


# ---------- DashScope：图片同步生成 ----------


def test_dashscope_generate_text_to_image(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={
            "output": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": [{"image": "https://cdn/qwen.png"}],
                        },
                    }
                ]
            }
        },
    )
    adapter = DashScopeAdapter()
    result = adapter.generate(
        _ctx(
            model_id="qwen-image-2.0-pro",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            preset="bailian",
        ),
        "text_to_image",
        GenerationRequest(
            capability="text_to_image",
            prompt="一只猫",
            aspect_ratio="1024x1536",
        ),
    )

    assert result.urls == ["https://cdn/qwen.png"]


def test_dashscope_generate_image_to_image_requires_image():
    adapter = DashScopeAdapter()
    try:
        adapter.generate(
            _ctx(
                model_id="qwen-image-2.0-pro",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                preset="bailian",
            ),
            "image_to_image",
            GenerationRequest(capability="image_to_image", prompt="改一下"),
        )
    except AppError as exc:
        assert exc.code == "image_required"
    else:
        raise AssertionError("should raise image_required")


# ---------- DashScope：视频异步任务 ----------


def test_dashscope_submit_text_to_video(monkeypatch):
    _patch_client(
        monkeypatch,
        payload={"output": {"task_id": "task-123", "task_status": "PENDING"}},
    )
    adapter = DashScopeAdapter()
    task_id = adapter.submit(
        _ctx(
            model_id="wan2.2-t2v",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            preset="bailian",
        ),
        "text_to_video",
        GenerationRequest(capability="text_to_video", prompt="一只猫在跑"),
    )
    assert task_id == "task-123"


def test_dashscope_poll_mapping(monkeypatch):
    adapter = DashScopeAdapter()
    ctx = _ctx(
        model_id="wan2.2-t2v",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        preset="bailian",
    )

    _patch_client(
        monkeypatch,
        payload={"output": {"task_status": "RUNNING", "task_id": "t1"}},
    )
    assert adapter.poll(ctx, "t1").status == "running"

    _patch_client(
        monkeypatch,
        payload={
            "output": {
                "task_status": "SUCCEEDED",
                "task_id": "t1",
                "video_url": "https://oss/v.mp4",
            }
        },
    )
    status = adapter.poll(ctx, "t1")
    assert status.status == "completed"
    assert status.result.urls == ["https://oss/v.mp4"]

    _patch_client(
        monkeypatch,
        payload={"output": {"task_status": "FAILED", "task_id": "t1", "message": "boom"}},
    )
    status = adapter.poll(ctx, "t1")
    assert status.status == "failed"
    assert status.error == "boom"


def test_dashscope_image_to_video_requires_image():
    adapter = DashScopeAdapter()
    try:
        adapter.submit(
            _ctx(
                model_id="wan2.1-t2v",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                preset="bailian",
            ),
            "image_to_video",
            GenerationRequest(capability="image_to_video", prompt="动起来"),
        )
    except AppError as exc:
        assert exc.code == "image_required"
    else:
        raise AssertionError("should raise image_required")
