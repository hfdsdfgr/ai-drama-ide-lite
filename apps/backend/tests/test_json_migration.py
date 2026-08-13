"""Phase 0 JSON 项目 → SQLite 迁移测试。"""

import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_legacy_json_migrated(tmp_path):
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    legacy = {
        "id": "proj_legacy123",
        "name": "旧项目",
        "description": "来自 Phase 0",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    (projects_dir / "proj_legacy123.json").write_text(
        json.dumps(legacy), encoding="utf-8"
    )

    settings = Settings(data_dir=tmp_path, log_level="ERROR")
    client = TestClient(create_app(settings=settings))
    projects = client.get("/api/projects").json()
    assert any(p["id"] == "proj_legacy123" for p in projects)
    assert any(p["name"] == "旧项目" for p in projects)
    client.close()

    # 原文件已归档，不丢数据
    assert not (projects_dir / "proj_legacy123.json").exists()
    assert (projects_dir / ".archive" / "proj_legacy123.json").exists()
