"""Phase 9 — 资产版本服务测试。"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.services.asset_version_service import AssetVersionService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture()
def service(tmp_path: Path) -> AssetVersionService:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO projects (id, name, description, created_at, updated_at)
            VALUES ('proj_1', 'p', '', ?, ?)
            """,
            (_now(), _now()),
        )
        conn.execute(
            """
            INSERT INTO assets (id, project_id, asset_type, name, prompt, created_at, updated_at)
            VALUES ('asset_char_1', 'proj_1', 'character', '林凡', '', ?, ?)
            """,
            (_now(), _now()),
        )
    return AssetVersionService(db_path, tmp_path / "projects")


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"0" * 32


def test_add_version_creates_file_and_record(service):
    record = service.add_version(
        "proj_1",
        "character",
        "asset_char_1",
        file_bytes=_png_bytes(),
        model_id="model_x",
        provider_id="prov_1",
        job_id="job_1",
        payload={"prompt": "male protagonist", "aspect_ratio": "2:3"},
    )
    assert record.id.startswith("ver_")
    assert record.version == 1
    assert record.is_current is True
    assert record.model_id == "model_x"
    assert record.payload == {"prompt": "male protagonist", "aspect_ratio": "2:3"}
    assert Path(record.file_path).is_file()
    assert Path(record.file_path).name == "v1.png"

    with get_connection(service.db_path) as conn:
        asset_version = conn.execute(
            "SELECT version FROM assets WHERE id = 'asset_char_1'"
        ).fetchone()["version"]
    assert asset_version == 1


def test_add_version_increments_and_switches_current(service):
    v1 = service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())
    v2 = service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())

    assert v1.version == 1
    assert v2.version == 2
    assert service.get(v1.id).is_current is False
    assert service.get(v2.id).is_current is True
    assert service.get_current("proj_1", "character", "asset_char_1").id == v2.id


def test_list_versions_desc(service):
    service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())
    service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())
    versions = service.list_versions("proj_1", "character", "asset_char_1")
    assert [v.version for v in versions] == [2, 1]


def test_promote_switches_current_without_deleting_file(service):
    v1 = service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())
    v2 = service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())
    v1_path = Path(v1.file_path)

    promoted = service.promote(v1.id)
    assert promoted.is_current is True
    assert service.get(v2.id).is_current is False
    assert v1_path.is_file()
    with get_connection(service.db_path) as conn:
        asset_version = conn.execute(
            "SELECT version FROM assets WHERE id = 'asset_char_1'"
        ).fetchone()["version"]
    assert asset_version == v1.version


def test_delete_non_current_removes_file_and_record(service):
    v1 = service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())
    v2 = service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())
    v1_path = Path(v1.file_path)

    service.delete(v1.id)
    assert not v1_path.exists()
    with pytest.raises(AppError):
        service.get(v1.id)
    assert service.get(v2.id).is_current is True


def test_delete_current_raises(service):
    v1 = service.add_version("proj_1", "character", "asset_char_1", file_bytes=_png_bytes())
    with pytest.raises(AppError) as exc:
        service.delete(v1.id)
    assert exc.value.code == "current_version_cannot_delete"
    assert Path(v1.file_path).is_file()


def test_get_missing_raises(service):
    with pytest.raises(AppError) as exc:
        service.get("ver_none")
    assert exc.value.status_code == 404


def test_persistence_across_instances(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES ('p', 'p', '', ?, ?)",
            (_now(), _now()),
        )
        conn.execute(
            "INSERT INTO assets (id, project_id, asset_type, name, prompt, created_at, updated_at) VALUES ('a1', 'p', 'character', 'x', '', ?, ?)",
            (_now(), _now()),
        )
    service = AssetVersionService(db_path, tmp_path / "projects")
    record = service.add_version("p", "character", "a1", file_bytes=_png_bytes())

    service2 = AssetVersionService(db_path, tmp_path / "projects")
    restored = service2.get(record.id)
    assert restored.version == 1
    assert restored.is_current is True
    assert Path(restored.file_path).is_file()
