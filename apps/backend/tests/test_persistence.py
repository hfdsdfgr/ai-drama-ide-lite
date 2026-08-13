"""项目跨重启持久化（Phase 1 完成标准）。"""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def _make_client(tmp_path):
    settings = Settings(data_dir=tmp_path, log_level="ERROR")
    return TestClient(create_app(settings=settings))


def test_project_survives_restart(tmp_path):
    client = _make_client(tmp_path)
    created = client.post("/api/projects", json={"name": "持久化项目"}).json()
    project_id = created["id"]
    client.close()

    # 模拟关闭程序后重新打开（同一数据目录重建应用）
    client2 = _make_client(tmp_path)
    fetched = client2.get(f"/api/projects/{project_id}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "持久化项目"
    client2.close()
