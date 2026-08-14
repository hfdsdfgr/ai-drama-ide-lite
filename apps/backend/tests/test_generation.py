"""Generation Job 接口测试（Phase 5）。"""

import time

import httpx


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
    """GET 返回轮询结果（/tasks/），POST 返回提交结果。"""

    def __init__(self, timeout=None, submit=None, poll=None):
        self._submit = submit or {"output": {"task_id": "task-1", "task_status": "PENDING"}}
        self._poll = poll or {"output": {"task_status": "SUCCEEDED", "video_url": "https://oss/v.mp4"}}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        return _FakeResponse(200, self._poll)

    def post(self, url, headers=None, json=None, files=None, data=None):
        return _FakeResponse(200, self._submit)


def _patch_client(monkeypatch, **kwargs):
    monkeypatch.setattr(
        httpx, "Client", lambda timeout=None: _FakeClient(timeout=timeout, **kwargs)
    )


def _add_image_model(client, needs_key=False):
    provider = client.post(
        "/api/providers",
        json={
            "name": "图片测试",
            "api_base_url": "http://127.0.0.1:9999/v1",
            "needs_key": needs_key,
        },
    ).json()
    model = client.post(
        "/api/models",
        json={
            "provider_id": provider["id"],
            "model_id": "test-image",
            "model_type": "image",
        },
    ).json()
    return model


def _add_bailian_video_model(client):
    provider = client.post(
        "/api/providers", json={"preset_key": "bailian", "api_key": "sk-cn"}
    ).json()
    model = client.post(
        "/api/models",
        json={
            "provider_id": provider["id"],
            "model_id": "wan2.2-t2v",
            "model_type": "video",
        },
    ).json()
    return model


def test_sync_image_job_completed(client, monkeypatch):
    _patch_client(monkeypatch, submit={"data": [{"url": "https://cdn/x.png"}]})
    model = _add_image_model(client)
    response = client.post(
        "/api/generation/jobs",
        json={
            "model_id": model["id"],
            "capability": "text_to_image",
            "prompt": "一只猫",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"

    # Phase 10 起由 worker 异步执行，轮询等待终态
    job_id = body["job_id"]
    deadline = time.time() + 10
    status = body["status"]
    while status in ("queued", "running") and time.time() < deadline:
        time.sleep(0.05)
        status = client.get(f"/api/generation/jobs/{job_id}").json()["status"]
    fetched = client.get(f"/api/generation/jobs/{job_id}")
    assert fetched.status_code == 200
    result = fetched.json()
    assert result["status"] == "completed"
    assert result["result"]["urls"] == ["https://cdn/x.png"]


def test_async_video_job_polls_to_completed(client, monkeypatch):
    _patch_client(monkeypatch)
    model = _add_bailian_video_model(client)
    response = client.post(
        "/api/generation/jobs",
        json={
            "model_id": model["id"],
            "capability": "text_to_video",
            "prompt": "一只猫在月光下奔跑",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "queued"

    job_id = body["job_id"]
    deadline = time.time() + 10
    status = body["status"]
    while status in ("queued", "running") and time.time() < deadline:
        time.sleep(0.05)
        status = client.get(f"/api/generation/jobs/{job_id}").json()["status"]
    fetched = client.get(f"/api/generation/jobs/{job_id}")
    assert fetched.status_code == 200
    result = fetched.json()
    assert result["status"] == "completed"
    assert result["result"]["urls"] == ["https://oss/v.mp4"]


def test_generation_requires_capability(client):
    model = _add_image_model(client)
    response = client.post(
        "/api/generation/jobs",
        json={
            "model_id": model["id"],
            "capability": "image_to_video",
            "prompt": "动起来",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "capability_not_supported"


def test_generation_requires_enabled_provider_key(client):
    model = _add_image_model(client, needs_key=True)
    response = client.post(
        "/api/generation/jobs",
        json={
            "model_id": model["id"],
            "capability": "text_to_image",
            "prompt": "一只猫",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "api_key_required"


def test_generation_job_not_found(client):
    response = client.get("/api/generation/jobs/gen_none")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "generation_job_not_found"
