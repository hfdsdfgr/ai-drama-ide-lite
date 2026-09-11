"""Phase 11 — 生产依赖图服务测试。"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.services.production_graph import ProductionGraphService
from app.services.asset_version_service import AssetVersionService


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@pytest.fixture()
def service(tmp_path: Path) -> ProductionGraphService:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at)"
            " VALUES ('proj_1', 'p', '', ?, ?)",
            (_now(), _now()),
        )
    return ProductionGraphService(db_path)


def test_add_and_get_edge(service):
    edge = service.add_edge(
        "proj_1",
        "asset",
        "asset_char_1",
        "shot",
        "shot_1",
        relation="shot_references_asset",
        upstream_version=3,
    )
    assert edge.id.startswith("edge_")
    assert edge.upstream_type == "asset"
    assert edge.upstream_version == 3
    assert edge.downstream_type == "shot"
    assert service.get(edge.id).downstream_id == "shot_1"


def _media_versions(service, tmp_path):
    return AssetVersionService(service.db_path, tmp_path / "projects")


def _ref(version, mode="current"):
    return {"type": "shot" if version.entity_type == "shot" else "asset",
            "id": version.entity_id, "entity_type": version.entity_type,
            "version_id": version.id, "version": version.version,
            "selection_mode": mode}


def _version(versions, kind, entity, refs=None, **payload):
    if refs is not None:
        payload["source_refs"] = refs
    return versions.add_version("proj_1", kind, entity, file_bytes=b"test-media", payload=payload)


def test_dependency_golden_path_and_rollback(service, tmp_path):
    versions = _media_versions(service, tmp_path)
    asset1 = _version(versions, "character", "a1")
    image1 = _version(versions, "shot", "s1", [_ref(asset1)])
    video1 = _version(versions, "shot_video", "s1", [_ref(image1)])
    def states():
        result = service.dependency_health("proj_1", [image1.id, video1.id])
        return [result[id]["state"] for id in (image1.id, video1.id)]
    assert states() == ["current", "current"]
    asset2 = _version(versions, "character", "a1")
    assert states() == ["stale", "stale"]
    versions.promote(asset1.id)
    assert states() == ["current", "current"]
    versions.promote(asset2.id)
    image2 = _version(versions, "shot", "s1", [_ref(asset2)])
    result = service.dependency_health("proj_1", [image2.id, video1.id])
    assert result[image2.id]["state"] == "current"
    assert result[video1.id]["state"] == "stale"
    video2 = _version(versions, "shot_video", "s1", [_ref(image2)])
    assert service.dependency_health("proj_1", [video2.id])[video2.id]["state"] == "current"
    assert versions.get(video1.id).id == video1.id


@pytest.mark.parametrize("mode, expected", [("current", "stale"), ("historical", "pinned"), ("legacy", "unknown")])
def test_dependency_selection_intent(service, tmp_path, mode, expected):
    versions = _media_versions(service, tmp_path)
    old = _version(versions, "character", "a1")
    _version(versions, "character", "a1")
    image = _version(versions, "shot", "s1", [_ref(old, mode), _ref(old, mode)])
    result = service.dependency_health("proj_1", [image.id])[image.id]
    assert result["state"] == expected
    assert len(result["issues"]) == 1


@pytest.mark.parametrize("payload, expected", [({}, "unknown"), ({"source_refs": []}, "none"), ({"source": "imported"}, "none"), ({"source_refs": [{"type": "asset", "id": "a"}]}, "unknown")])
def test_dependency_legacy_and_explicit_empty(service, tmp_path, payload, expected):
    versions = _media_versions(service, tmp_path)
    image = _version(versions, "shot", "s1", **payload)
    assert service.dependency_health("proj_1", [image.id])[image.id]["state"] == expected


@pytest.mark.parametrize("damage", ["deleted", "missing_file", "wrong_entity", "wrong_project"])
def test_dependency_broken_reference(service, tmp_path, damage):
    versions = _media_versions(service, tmp_path)
    asset = _version(versions, "character", "a1")
    ref = _ref(asset, "historical")
    if damage == "wrong_entity":
        ref["id"] = "other"
    image = _version(versions, "shot", "s1", [ref])
    if damage == "missing_file":
        Path(asset.file_path).unlink()
    elif damage == "deleted":
        with get_connection(service.db_path) as conn:
            conn.execute("DELETE FROM versions WHERE id = ?", (asset.id,))
    elif damage == "wrong_project":
        with get_connection(service.db_path) as conn:
            conn.execute("INSERT INTO projects (id, name, created_at, updated_at) VALUES ('other', 'other', ?, ?)", (_now(), _now()))
            conn.execute("UPDATE versions SET project_id = 'other' WHERE id = ?", (asset.id,))
    assert service.dependency_health("proj_1", [image.id])[image.id]["state"] == "broken"


def test_pinned_keyframe_does_not_hide_stale_asset(service, tmp_path):
    versions = _media_versions(service, tmp_path)
    asset = _version(versions, "character", "a1")
    image = _version(versions, "shot", "s1", [_ref(asset)])
    video = _version(versions, "shot_video", "s1", [_ref(image, "historical")])
    _version(versions, "character", "a1")
    result = service.dependency_health("proj_1", [video.id])[video.id]
    assert result["state"] == "stale"
    assert {item["state"] for item in result["issues"]} == {"pinned", "stale"}


def test_dependency_view_uses_exact_asset_keyframe_and_video_versions(service, tmp_path):
    with get_connection(service.db_path) as conn:
        now = _now()
        conn.execute("INSERT INTO episodes (id, project_id, title, created_at, updated_at) VALUES ('ep1', 'proj_1', '第一集', ?, ?)", (now, now))
        conn.execute("INSERT INTO scenes (id, project_id, episode_id, title, created_at, updated_at) VALUES ('scene1', 'proj_1', 'ep1', '城门', ?, ?)", (now, now))
        conn.execute("INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, characters, action, dialogue, duration, prompt, created_at, updated_at) VALUES ('s1', 'proj_1', 'scene1', 1, 0, '', '', '', 5, '', ?, ?)", (now, now))
        conn.execute("INSERT INTO assets (id, project_id, asset_type, name, created_at, updated_at) VALUES ('a1', 'proj_1', 'character', '林凡', ?, ?)", (now, now))
    versions = _media_versions(service, tmp_path)
    asset1 = _version(versions, "character", "a1")
    image = _version(versions, "shot", "s1", [_ref(asset1, "historical")])
    video = _version(versions, "shot_video", "s1", [_ref(image)])
    _version(versions, "character", "a1")

    result = service.dependency_view("proj_1", shot_id="s1")
    group = result["shots"][0]
    nodes = {node["id"]: node for node in group["nodes"]}
    assert {asset1.id, image.id, video.id}.issubset(nodes)
    assert nodes[asset1.id]["label"] == "林凡"
    assert nodes[asset1.id]["state"] == "pinned"
    assert {edge["source"] for edge in group["edges"]} >= {asset1.id, image.id}
    assert any(issue["used_version_id"] == asset1.id for issue in group["issues"])


def test_dependency_view_rejects_ambiguous_scope(service):
    with pytest.raises(AppError) as exc:
        service.dependency_view("proj_1")
    assert exc.value.code == "dependency_scope_required"


def test_add_edge_is_idempotent(service):
    first = service.add_edge("proj_1", "asset", "a1", "shot", "s1", relation="r")
    second = service.add_edge("proj_1", "asset", "a1", "shot", "s1", relation="r")
    assert first.id == second.id
    assert len(service.list_edges("proj_1")) == 1


def test_list_downstream(service):
    service.add_edge("proj_1", "asset", "a1", "shot", "s1", relation="r1")
    service.add_edge("proj_1", "asset", "a1", "shot", "s2", relation="r2")
    service.add_edge("proj_1", "asset", "a2", "shot", "s3", relation="r3")
    downstream = service.list_downstream("proj_1", "asset", "a1")
    assert {e.downstream_id for e in downstream} == {"s1", "s2"}


def test_affected_nodes_transitive_closure(service):
    service.add_edge(
        "proj_1", "asset", "a1", "shot", "s1", relation="shot_references_asset"
    )
    service.add_edge(
        "proj_1",
        "shot",
        "s1",
        "image_version",
        "v_img",
        relation="image_generated_from_shot",
    )
    service.add_edge(
        "proj_1",
        "image_version",
        "v_img",
        "video_version",
        "v_vid",
        relation="video_generated_from_image",
    )

    affected = service.affected_nodes("proj_1", "asset", "a1")
    result = {(n["type"], n["id"]) for n in affected}
    assert result == {
        ("shot", "s1"),
        ("image_version", "v_img"),
        ("video_version", "v_vid"),
    }


def test_affected_nodes_deduplicates(service):
    service.add_edge("proj_1", "asset", "a1", "shot", "s1", relation="r1")
    service.add_edge("proj_1", "asset", "a1", "image_version", "v_img", relation="r2")
    service.add_edge("proj_1", "shot", "s1", "image_version", "v_img", relation="r3")

    affected = service.affected_nodes("proj_1", "asset", "a1")
    assert [n["id"] for n in affected].count("v_img") == 1
    assert {n["id"] for n in affected} == {"s1", "v_img"}


def test_regeneration_plan_groups_shot_results(service):
    now = _now()
    with get_connection(service.db_path) as conn:
        conn.execute(
            "INSERT INTO shots (id, project_id, shot_number, created_at, updated_at) VALUES ('s1', 'proj_1', 3, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO versions (id, project_id, entity_type, entity_id, version, is_current, created_at) VALUES ('v_img', 'proj_1', 'shot', 's1', 1, 1, ?)",
            (now,),
        )
        conn.execute(
            "INSERT INTO versions (id, project_id, entity_type, entity_id, version, is_current, created_at) VALUES ('v_vid', 'proj_1', 'shot_video', 's1', 1, 1, ?)",
            (now,),
        )
    service.add_edge("proj_1", "asset", "a1", "shot", "s1", relation="shot_references_asset")
    service.add_edge("proj_1", "shot", "s1", "image_version", "v_img")
    service.add_edge("proj_1", "image_version", "v_img", "video_version", "v_vid")

    plan = service.regeneration_plan("proj_1", "asset", "a1")

    assert [item["shot_id"] for item in plan["image_shots"]] == ["s1"]
    assert [item["shot_id"] for item in plan["video_shots"]] == ["s1"]
    assert plan["image_shots"][0]["dependency_state"] == "unknown"
    assert "缺少来源记录" in plan["image_shots"][0]["reason"]


def test_remove_edge(service):
    edge = service.add_edge("proj_1", "asset", "a1", "shot", "s1")
    service.remove_edge(edge.id)
    with pytest.raises(AppError):
        service.get(edge.id)


def test_invalid_node_type_rejected(service):
    with pytest.raises(AppError) as exc:
        service.add_edge("proj_1", "asset", "a1", "unknown", "x1")
    assert exc.value.code == "invalid_node_type"


def test_persistence_across_instances(tmp_path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at)"
            " VALUES ('p', 'p', '', ?, ?)",
            (_now(), _now()),
        )
    service = ProductionGraphService(db_path)
    edge = service.add_edge("p", "asset", "a1", "shot", "s1")
    service2 = ProductionGraphService(db_path)
    assert service2.get(edge.id).downstream_id == "s1"
