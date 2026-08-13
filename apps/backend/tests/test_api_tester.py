"""API 连接测试（Phase 4 — L1/L2）测试。"""

from types import SimpleNamespace

import httpx

from app.services.api_tester import run_provider_test


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, timeout=None, status_code=200, payload=None, raise_exc=None):
        self._status_code = status_code
        self._payload = payload
        self._raise_exc = raise_exc

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        if self._raise_exc:
            raise self._raise_exc
        return _FakeResponse(self._status_code, self._payload)


def _fake_factory(monkeypatch, **kwargs):
    monkeypatch.setattr(
        httpx, "Client", lambda timeout=None: _FakeClient(timeout=timeout, **kwargs)
    )


def _models(*ids):
    return [SimpleNamespace(model_id=mid) for mid in ids]


def test_success_with_model_checks(monkeypatch):
    _fake_factory(
        monkeypatch,
        status_code=200,
        payload={"data": [{"id": "gpt-4o"}, {"id": "gpt-image-1"}]},
    )
    result = run_provider_test(
        provider_id="prov_1",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        needs_key=True,
        has_key=True,
        discoverable=True,
        models=_models("gpt-4o", "gpt-image-1"),
    )
    assert result.ok is True
    labels = [c.label for c in result.checks]
    assert labels == ["连接测试（Endpoint）", "鉴权测试（API Key）", "模型可用性"]
    assert all(c.status == "ok" for c in result.checks)
    assert len(result.model_checks) == 2
    assert all(m.ok for m in result.model_checks)


def test_missing_model_detected(monkeypatch):
    _fake_factory(
        monkeypatch,
        status_code=200,
        payload={"data": [{"id": "gpt-4o"}]},
    )
    result = run_provider_test(
        provider_id="prov_1",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        needs_key=True,
        has_key=True,
        discoverable=True,
        models=_models("gpt-4o", "ghost-model"),
    )
    assert result.ok is False
    model_checks = {m.model_id: m.ok for m in result.model_checks}
    assert model_checks == {"gpt-4o": True, "ghost-model": False}


def test_auth_fail(monkeypatch):
    _fake_factory(monkeypatch, status_code=401, payload={})
    result = run_provider_test(
        provider_id="prov_1",
        base_url="https://api.openai.com/v1",
        api_key="sk-bad",
        needs_key=True,
        has_key=True,
        discoverable=True,
        models=[],
    )
    assert result.ok is False
    auth = [c for c in result.checks if c.label == "鉴权测试（API Key）"][0]
    assert auth.status == "fail"
    assert "无效" in auth.detail


def test_timeout(monkeypatch):
    _fake_factory(monkeypatch, raise_exc=httpx.TimeoutException("timeout"))
    result = run_provider_test(
        provider_id="prov_1",
        base_url="https://api.openai.com/v1",
        api_key="sk-test",
        needs_key=True,
        has_key=True,
        discoverable=True,
        models=[],
    )
    assert result.ok is False
    statuses = {c.label: c.status for c in result.checks}
    assert statuses["连接测试（Endpoint）"] == "fail"
    assert statuses["鉴权测试（API Key）"] == "skipped"


def test_endpoint_missing(monkeypatch):
    _fake_factory(monkeypatch, status_code=404, payload={})
    result = run_provider_test(
        provider_id="prov_1",
        base_url="https://api.openai.com",
        api_key="sk-test",
        needs_key=True,
        has_key=True,
        discoverable=True,
        models=[],
    )
    assert result.ok is True  # 连接可达，鉴权未验证 → 不算失败
    auth = [c for c in result.checks if c.label == "鉴权测试（API Key）"][0]
    assert auth.status == "skipped"
    assert "404" in auth.detail


def test_non_discoverable_config_ok(monkeypatch):
    _fake_factory(monkeypatch, status_code=404, payload={})
    result = run_provider_test(
        provider_id="prov_2",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-bailian",
        needs_key=True,
        has_key=True,
        discoverable=False,
        models=_models("qwen-plus"),
    )
    assert result.ok is True
    labels = [c.label for c in result.checks]
    assert labels == [
        "连接测试（Endpoint）",
        "鉴权测试（API Key）",
        "模型可用性",
    ]
    assert all(c.status in ("ok", "skipped") for c in result.checks)


def test_missing_key_fails():
    result = run_provider_test(
        provider_id="prov_1",
        base_url="https://api.openai.com/v1",
        api_key=None,
        needs_key=True,
        has_key=False,
        discoverable=True,
        models=[],
    )
    assert result.ok is False
    assert result.checks[0].label == "配置检查"
    assert result.checks[0].status == "fail"
