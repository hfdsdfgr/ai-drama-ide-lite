"""版本 API 测试。"""

from app.version import APP_VERSION


def test_get_version(client):
    body = client.get("/api/version").json()
    assert body["version"] == APP_VERSION
    assert body["app_name"] == "AI Drama IDE Lite"


def test_check_version_returns_structure(client):
    body = client.get("/api/version/check").json()
    assert body["current"] == APP_VERSION
    # 网络不可用时 latest 为 None 且 error 非空；可用时结构完整
    assert "latest" in body
    assert "has_update" in body
