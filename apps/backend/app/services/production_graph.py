"""Phase 11 — 生产依赖图服务。

职责：维护生产链路的有向依赖边（谁依赖谁的哪个版本），并在某个节点变化时
沿出边计算受影响的传递闭包。只负责检测与查询，不自动重新生成。
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection


NODE_TYPES = (
    "novel",
    "chapter",
    "story_bible",
    "character",
    "location",
    "prop",
    "asset",
    "episode",
    "scene",
    "shot",
    "image_version",
    "video_version",
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


@dataclass
class ProductionEdge:
    id: str
    project_id: str
    upstream_type: str
    upstream_id: str
    upstream_version: int | None
    downstream_type: str
    downstream_id: str
    relation: str
    created_at: str


def _row_to_edge(row) -> ProductionEdge:
    return ProductionEdge(
        id=row["id"],
        project_id=row["project_id"],
        upstream_type=row["upstream_type"],
        upstream_id=row["upstream_id"],
        upstream_version=row["upstream_version"],
        downstream_type=row["downstream_type"],
        downstream_id=row["downstream_id"],
        relation=row["relation"],
        created_at=row["created_at"],
    )


class ProductionGraphService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _validate_node_type(self, node_type: str) -> None:
        if node_type not in NODE_TYPES:
            raise AppError(
                422,
                "invalid_node_type",
                f"未知生产节点类型: {node_type}",
            )

    def add_edge(
        self,
        project_id: str,
        upstream_type: str,
        upstream_id: str,
        downstream_type: str,
        downstream_id: str,
        relation: str = "",
        upstream_version: int | None = None,
    ) -> ProductionEdge:
        """新增一条生产依赖边；相同自然键重复写入时返回已有边（幂等）。"""
        self._validate_node_type(upstream_type)
        self._validate_node_type(downstream_type)
        now = _now_iso()
        key = (
            project_id,
            upstream_type,
            upstream_id,
            upstream_version,
            downstream_type,
            downstream_id,
            relation,
        )
        with get_connection(self.db_path) as conn:
            existing = conn.execute(
                """
                SELECT * FROM production_edges
                WHERE project_id = ? AND upstream_type = ? AND upstream_id = ?
                  AND upstream_version IS ? AND downstream_type = ?
                  AND downstream_id = ? AND relation = ?
                LIMIT 1
                """,
                key,
            ).fetchone()
            if existing is not None:
                return _row_to_edge(existing)
            edge_id = _new_id("edge")
            conn.execute(
                """
                INSERT INTO production_edges (
                    id, project_id, upstream_type, upstream_id, upstream_version,
                    downstream_type, downstream_id, relation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (edge_id, *key, now),
            )
            row = conn.execute(
                "SELECT * FROM production_edges WHERE id = ?", (edge_id,)
            ).fetchone()
        if row is None:
            raise AppError(500, "edge_not_created", "生产依赖边创建失败")
        return _row_to_edge(row)

    def get(self, edge_id: str) -> ProductionEdge:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM production_edges WHERE id = ?", (edge_id,)
            ).fetchone()
        if row is None:
            raise AppError(404, "edge_not_found", f"生产依赖边不存在: {edge_id}")
        return _row_to_edge(row)

    def list_edges(self, project_id: str) -> list[ProductionEdge]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM production_edges WHERE project_id = ? ORDER BY created_at",
                (project_id,),
            ).fetchall()
        return [_row_to_edge(row) for row in rows]

    def list_downstream(
        self, project_id: str, node_type: str, node_id: str
    ) -> list[ProductionEdge]:
        """列出某节点的直接下游边。"""
        self._validate_node_type(node_type)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM production_edges
                WHERE project_id = ? AND upstream_type = ? AND upstream_id = ?
                ORDER BY created_at
                """,
                (project_id, node_type, node_id),
            ).fetchall()
        return [_row_to_edge(row) for row in rows]

    def affected_nodes(
        self, project_id: str, node_type: str, node_id: str
    ) -> list[dict]:
        """计算某节点变化后受影响的下游节点（传递闭包，去重）。"""
        self._validate_node_type(node_type)
        visited: set[tuple[str, str]] = set()
        affected: dict[tuple[str, str], dict] = {}
        queue: list[tuple[str, str]] = [(node_type, node_id)]

        with get_connection(self.db_path) as conn:
            while queue:
                current_type, current_id = queue.pop(0)
                key = (current_type, current_id)
                if key in visited:
                    continue
                visited.add(key)
                rows = conn.execute(
                    """
                    SELECT * FROM production_edges
                    WHERE project_id = ? AND upstream_type = ? AND upstream_id = ?
                    ORDER BY created_at
                    """,
                    (project_id, current_type, current_id),
                ).fetchall()
                for row in rows:
                    edge = _row_to_edge(row)
                    downstream_key = (edge.downstream_type, edge.downstream_id)
                    if downstream_key not in affected:
                        affected[downstream_key] = {
                            "type": edge.downstream_type,
                            "id": edge.downstream_id,
                            "relation": edge.relation,
                        }
                    if downstream_key not in visited:
                        queue.append(downstream_key)

        return list(affected.values())

    def remove_edge(self, edge_id: str) -> None:
        self.get(edge_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "DELETE FROM production_edges WHERE id = ?", (edge_id,)
            )
