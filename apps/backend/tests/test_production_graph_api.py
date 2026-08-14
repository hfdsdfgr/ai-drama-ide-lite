"""Phase 11 — 生产依赖图接口测试。"""


def _create_project(client) -> str:
    client.post("/api/projects", json={"name": "生产图项目"})
    return client.get("/api/projects").json()[0]["id"]


def _add_edge(client, pid, **overrides):
    payload = {
        "upstream_type": "asset",
        "upstream_id": "a1",
        "upstream_version": None,
        "downstream_type": "shot",
        "downstream_id": "s1",
        "relation": "shot_references_asset",
    }
    payload.update(overrides)
    return client.post(f"/api/projects/{pid}/graph/edges", json=payload)


def test_add_and_list_edges(client):
    pid = _create_project(client)
    created = _add_edge(client, pid)
    assert created.status_code == 201
    assert created.json()["upstream_type"] == "asset"
    assert created.json()["downstream_id"] == "s1"

    listed = client.get(f"/api/projects/{pid}/graph/edges")
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_add_edge_is_idempotent(client):
    pid = _create_project(client)
    first = _add_edge(client, pid).json()
    second = _add_edge(client, pid).json()
    assert first["id"] == second["id"]
    assert len(client.get(f"/api/projects/{pid}/graph/edges").json()) == 1


def test_affected_nodes_transitive(client):
    pid = _create_project(client)
    _add_edge(client, pid)
    _add_edge(
        client,
        pid,
        upstream_type="shot",
        upstream_id="s1",
        downstream_type="image_version",
        downstream_id="v_img",
        relation="image_generated_from_shot",
    )
    _add_edge(
        client,
        pid,
        upstream_type="image_version",
        upstream_id="v_img",
        downstream_type="video_version",
        downstream_id="v_vid",
        relation="video_generated_from_image",
    )

    response = client.get(
        f"/api/projects/{pid}/graph/affected?node_type=asset&node_id=a1"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["changed_node"] == {"type": "asset", "id": "a1"}
    assert {(n["type"], n["id"]) for n in body["affected"]} == {
        ("shot", "s1"),
        ("image_version", "v_img"),
        ("video_version", "v_vid"),
    }


def test_invalid_node_type_rejected(client):
    pid = _create_project(client)
    response = _add_edge(client, pid, downstream_type="unknown")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_node_type"


def test_delete_edge(client):
    pid = _create_project(client)
    edge_id = _add_edge(client, pid).json()["id"]
    response = client.delete(f"/api/projects/{pid}/graph/edges/{edge_id}")
    assert response.status_code == 204
    assert client.get(f"/api/projects/{pid}/graph/edges").json() == []


def test_delete_edge_owner_mismatch(client):
    pid = _create_project(client)
    edge_id = _add_edge(client, pid).json()["id"]
    other_pid = _create_project(client)
    response = client.delete(f"/api/projects/{other_pid}/graph/edges/{edge_id}")
    assert response.status_code == 404
