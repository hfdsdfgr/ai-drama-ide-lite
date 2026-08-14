"""Phase 11 — 生产依赖图服务测试。"""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.services.production_graph import ProductionGraphService


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
