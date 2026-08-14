"""Phase 9 — 资产版本接口测试。"""

from datetime import datetime, timezone

from app.db.database import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _setup_project_asset(client, project_id="proj_1", asset_id="asset_char_1"):
    client.post("/api/projects", json={"name": "版本项目"})
    project = client.get("/api/projects").json()[0]
    pid = project["id"]
    with get_connection(client.app.state.settings.db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO assets
                (id, project_id, asset_type, name, prompt, created_at, updated_at)
            VALUES (?, ?, 'character', '林凡', '', ?, ?)
            """,
            (asset_id, pid, _now(), _now()),
        )
    return pid, asset_id


def _add_version(client, pid, aid, version=1, current=True):
    service = client.app.state.asset_version_service
    record = service.add_version(
        pid,
        "character",
        aid,
        file_bytes=b"\x89PNG\r\n\x1a\n" + b"0" * 32,
        model_id="model_x",
        provider_id="prov_1",
        job_id="job_1",
        payload={"prompt": f"v{version}"},
    )
    return record


def test_list_versions_empty(client):
    pid, aid = _setup_project_asset(client)
    response = client.get(f"/api/projects/{pid}/assets/{aid}/versions")
    assert response.status_code == 200
    assert response.json() == []


def test_list_versions_and_current(client):
    pid, aid = _setup_project_asset(client)
    v1 = _add_version(client, pid, aid)
    v2 = _add_version(client, pid, aid)

    listed = client.get(f"/api/projects/{pid}/assets/{aid}/versions").json()
    assert [v["version"] for v in listed] == [2, 1]
    assert listed[0]["id"] == v2.id
    assert listed[0]["is_current"] is True
    assert listed[0]["file_url"].endswith(f"/versions/{v2.id}/file")
    assert listed[1]["id"] == v1.id
    assert listed[1]["is_current"] is False

    current = client.get(
        f"/api/projects/{pid}/assets/{aid}/versions/current"
    ).json()
    assert current["id"] == v2.id


def test_version_file(client):
    pid, aid = _setup_project_asset(client)
    record = _add_version(client, pid, aid)
    response = client.get(
        f"/api/projects/{pid}/assets/{aid}/versions/{record.id}/file"
    )
    assert response.status_code == 200
    assert response.content.startswith(b"\x89PNG")


def test_promote_version(client):
    pid, aid = _setup_project_asset(client)
    v1 = _add_version(client, pid, aid)
    v2 = _add_version(client, pid, aid)

    response = client.post(
        f"/api/projects/{pid}/assets/{aid}/versions/{v1.id}/promote"
    )
    assert response.status_code == 200
    assert response.json()["is_current"] is True
    assert response.json()["version"] == 1

    current = client.get(
        f"/api/projects/{pid}/assets/{aid}/versions/current"
    ).json()
    assert current["id"] == v1.id


def test_delete_non_current(client):
    pid, aid = _setup_project_asset(client)
    v1 = _add_version(client, pid, aid)
    v2 = _add_version(client, pid, aid)

    response = client.delete(
        f"/api/projects/{pid}/assets/{aid}/versions/{v1.id}"
    )
    assert response.status_code == 204
    assert client.get(
        f"/api/projects/{pid}/assets/{aid}/versions"
    ).json()[0]["id"] == v2.id


def test_delete_current_rejected(client):
    pid, aid = _setup_project_asset(client)
    v2 = _add_version(client, pid, aid)
    response = client.delete(
        f"/api/projects/{pid}/assets/{aid}/versions/{v2.id}"
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "current_version_cannot_delete"


def test_version_owner_mismatch_rejected(client):
    pid, aid = _setup_project_asset(client)
    record = _add_version(client, pid, aid)
    other_pid, other_aid = _setup_project_asset(
        client, project_id="proj_2", asset_id="asset_char_2"
    )
    response = client.get(
        f"/api/projects/{other_pid}/assets/{other_aid}/versions/{record.id}/file"
    )
    assert response.status_code == 404
