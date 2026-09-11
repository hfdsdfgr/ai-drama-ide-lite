"""Phase 11 — 生产依赖图服务。

职责：维护生产链路的有向依赖边（谁依赖谁的哪个版本），并在某个节点变化时
沿出边计算受影响的传递闭包。只负责检测与查询，不自动重新生成。
"""

import uuid
import json
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
    "reference",
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

    def dependency_health(self, project_id: str, version_ids: list[str]) -> dict:
        """Read immutable recipes in one batch; graph reachability alone is not stale.

        Only project-local versions can resolve a reference. Memoization is local
        to this read, so promoting/rolling back a version needs no invalidation.
        """
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM versions WHERE project_id = ?", (project_id,)
            ).fetchall()
            names = {row['id']: row['name'] for row in conn.execute(
                "SELECT id, name FROM assets WHERE project_id = ?", (project_id,)
            )}
        versions = {row['id']: dict(row) for row in rows}
        current = {(row['entity_type'], row['entity_id']): row for row in rows if row['is_current']}
        memo = {}
        visiting = set()
        priority = {'none': 0, 'current': 1, 'pinned': 2, 'unknown': 3, 'stale': 4, 'broken': 5}

        def inspect(version_id):
            if version_id in memo:
                return memo[version_id]
            if version_id in visiting:
                return {'state': 'unknown', 'issues': []}
            visiting.add(version_id)
            row = versions.get(version_id)
            issues = []
            states = ['none']

            def issue(state, label, ref=None, used=None, latest=None):
                ref = ref or {}
                states.append(state)
                issues.append({
                    'state': state, 'label': label,
                    'source_id': ref.get('id', ''),
                    'source_name': names.get(ref.get('id'), '关键帧' if ref.get('type') == 'shot' else '参考图'),
                    'used_version_id': used['id'] if used else ref.get('version_id', ''),
                    'used_version': used['version'] if used else ref.get('version'),
                    'current_version_id': latest['id'] if latest else '',
                    'current_version': latest['version'] if latest else None,
                })

            if row is None:
                issue('broken', '来源版本不存在或不属于当前项目，请重新选择参考图')
            else:
                try:
                    payload = json.loads(row['payload'] or '{}')
                except (TypeError, ValueError):
                    payload = {}
                if not isinstance(payload, dict):
                    payload = {}
                refs = payload.get('source_refs')
                if payload.get('source') == 'imported':
                    refs = []
                elif not isinstance(refs, list):
                    issue('unknown', '历史结果缺少来源记录，请核实参考图')
                    refs = []
                for ref in refs:
                    if not isinstance(ref, dict) or not isinstance(ref.get('type'), str) or not isinstance(ref.get('id'), str) or (ref.get('version_id') is not None and not isinstance(ref['version_id'], str)):
                        issue('unknown', '来源记录不完整，请核实参考图')
                        continue
                    if ref.get('type') not in {'asset', 'shot'}:
                        continue
                    if ref.get('type') == 'shot' and row['entity_type'] != 'shot_video':
                        continue  # script linkage is not an image-version reference
                    used_id = ref.get('version_id')
                    if not used_id:
                        issue('unknown', '历史引用未记录具体版本，请核实参考图', ref)
                        continue
                    used = versions.get(used_id)
                    expected_types = {'shot'} if ref.get('type') == 'shot' else {'character', 'location', 'prop', 'reference_image'}
                    if used is None or used['entity_id'] != ref.get('id') or used['entity_type'] not in expected_types or (ref.get('entity_type') and used['entity_type'] != ref['entity_type']):
                        issue('broken', '引用版本已删除或不属于对应来源，请重新选择', ref)
                        continue
                    latest = current.get((used['entity_type'], used['entity_id']))
                    name = names.get(used['entity_id'], '关键帧' if used['entity_type'] == 'shot' else '参考图')
                    if not used['file_path'] or not Path(used['file_path']).is_file():
                        issue('broken', f'{name} v{used["version"]} 文件不可用，请重新导入或选择', ref, used, latest)
                    elif latest is None:
                        issue('broken', f'{name} 缺少当前版本，请重新选择', ref, used)
                    elif ref.get('selection_mode') == 'historical':
                        issue('pinned', f'{name}：沿用指定 v{used["version"]}', ref, used, latest)
                    elif used_id == latest['id']:
                        states.append('current')
                    elif ref.get('selection_mode') == 'current':
                        issue('stale', f'{name}：使用 v{used["version"]}，当前 v{latest["version"]}，请确认', ref, used, latest)
                    else:
                        issue('unknown', f'{name}：使用 v{used["version"]}，当前 v{latest["version"]}，历史选择意图未知', ref, used, latest)
                    if used['entity_type'] == 'shot':
                        upstream = inspect(used_id)
                        for item in upstream['issues']:
                            if item['state'] in {'stale', 'broken', 'unknown'}:
                                states.append(item['state'])
                                issues.append({**item, 'label': '源关键帧依赖：' + item['label']})
                if row['entity_type'] == 'shot_video' and not any(isinstance(ref, dict) and ref.get('type') == 'shot' for ref in refs) and payload.get('source') != 'imported':
                    issue('unknown', '视频缺少源关键帧记录，请核实')
            visiting.remove(version_id)
            unique = {json.dumps(item, sort_keys=True): item for item in issues}
            result = {'state': max(states, key=priority.get), 'issues': list(unique.values())}
            memo[version_id] = result
            return result

        return {version_id: inspect(version_id) for version_id in dict.fromkeys(version_ids)}

    def dependency_view(
        self,
        project_id: str,
        *,
        shot_id: str | None = None,
        scene_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        if bool(shot_id) == bool(scene_id):
            raise AppError(422, "dependency_scope_required", "请选择一个镜头或场景查看依赖")
        with get_connection(self.db_path) as conn:
            if shot_id:
                rows = conn.execute(
                    """SELECT s.id, s.shot_number, sc.title AS scene_title
                       FROM shots s JOIN scenes sc ON sc.id = s.scene_id
                       WHERE s.id = ? AND s.project_id = ? AND s.deleted_at IS NULL AND sc.deleted_at IS NULL""",
                    (shot_id, project_id),
                ).fetchall()
                scope = {"type": "shot", "id": shot_id}
            else:
                scene = conn.execute(
                    "SELECT id FROM scenes WHERE id = ? AND project_id = ? AND deleted_at IS NULL",
                    (scene_id, project_id),
                ).fetchone()
                if scene is None:
                    raise AppError(404, "scene_not_found", "场景不存在")
                all_rows = conn.execute(
                    """SELECT s.id, s.shot_number, sc.title AS scene_title
                       FROM shots s JOIN scenes sc ON sc.id = s.scene_id
                       WHERE sc.id = ? AND s.project_id = ? AND s.deleted_at IS NULL
                       ORDER BY s.order_index, s.created_at""",
                    (scene_id, project_id),
                ).fetchall()
                rows = all_rows[offset : offset + limit]
                scope = {"type": "scene", "id": scene_id}
            if shot_id and not rows:
                raise AppError(404, "shot_not_found", "镜头不存在")
            versions = [
                dict(row)
                for row in conn.execute(
                    "SELECT * FROM versions WHERE project_id = ?",
                    (project_id,),
                ).fetchall()
            ]
            asset_names = {
                row["id"]: row["name"]
                for row in conn.execute(
                    "SELECT id, name FROM assets WHERE project_id = ?", (project_id,)
                ).fetchall()
            }
            reference_names = {
                row["id"]: row["name"]
                for row in conn.execute(
                    "SELECT id, name FROM reference_media WHERE project_id = ?", (project_id,)
                ).fetchall()
            }
        by_id = {row["id"]: row for row in versions}
        current = {(row["entity_type"], row["entity_id"]): row for row in versions if row["is_current"]}
        shot_ids = [row["id"] for row in rows]
        output_ids = [
            row["id"]
            for row in versions
            if row["entity_id"] in shot_ids and row["is_current"] and row["entity_type"] in {"shot", "shot_video"}
        ]
        health = self.dependency_health(project_id, output_ids)

        def payload(row):
            try:
                data = json.loads(row["payload"] or "{}")
            except (TypeError, ValueError):
                return {}
            return data if isinstance(data, dict) else {}

        def version_node(version_id: str, selection_mode: str = "") -> dict:
            version = by_id.get(version_id)
            if version is None:
                return {"id": version_id or "missing", "entity_type": "missing", "entity_id": "", "label": "来源版本不存在", "version": None, "current_version": None, "state": "broken", "target": {}}
            latest = current.get((version["entity_type"], version["entity_id"]))
            label = asset_names.get(version["entity_id"]) or reference_names.get(version["entity_id"])
            if not label:
                label = "关键帧" if version["entity_type"] == "shot" else "视频" if version["entity_type"] == "shot_video" else "参考图"
            state = "pinned" if selection_mode == "historical" else "current" if latest and latest["id"] == version_id else "stale"
            media = "video" if version["entity_type"] == "shot_video" else "image"
            target = {}
            if version["entity_type"] in {"shot", "shot_video"}:
                target = {"type": "shot", "id": version["entity_id"], "media": media}
            elif version["entity_type"] in {"character", "location", "prop"}:
                target = {"type": "asset", "id": version["entity_id"], "media": media}
            return {"id": version_id, "entity_type": version["entity_type"], "entity_id": version["entity_id"], "label": label, "version": version["version"], "current_version": latest["version"] if latest else None, "state": state, "target": target}

        groups = []
        for shot in rows:
            nodes, edges, seen, seen_edges = [], [], set(), set()

            def add_edge(source: str, target: str, relation: str) -> None:
                key = (source, target, relation)
                if key not in seen_edges:
                    seen_edges.add(key)
                    edges.append({"source": source, "target": target, "relation": relation})

            def add_ref(ref: dict, downstream: str) -> None:
                version_id = ref.get("version_id")
                if version_id:
                    add_version(version_id, ref.get("selection_mode", ""), downstream, ref.get("relation", ""))
                    return
                entity_type = ref.get("type", "missing")
                entity_id = ref.get("id", "")
                node_id = f"missing:{entity_type}:{entity_id or 'unknown'}"
                if node_id not in seen:
                    seen.add(node_id)
                    label = asset_names.get(entity_id) or reference_names.get(entity_id) or "来源版本未记录"
                    target = {"type": "asset", "id": entity_id, "media": "image"} if entity_type in {"character", "location", "prop"} and entity_id else {}
                    nodes.append({"id": node_id, "entity_type": entity_type, "entity_id": entity_id, "label": label, "version": None, "current_version": None, "state": "unknown", "target": target})
                add_edge(node_id, downstream, ref.get("relation", ""))

            def add_version(version_id: str, selection_mode: str = "", downstream: str = "", relation: str = "") -> None:
                node = version_node(version_id, selection_mode)
                if node["id"] not in seen:
                    seen.add(node["id"])
                    nodes.append(node)
                if downstream:
                    add_edge(node["id"], downstream, relation)
                version = by_id.get(version_id)
                if version is None or version["entity_type"] != "shot":
                    return
                refs = payload(version).get("source_refs", [])
                if not isinstance(refs, list):
                    return
                for ref in refs:
                    if isinstance(ref, dict):
                        add_ref(ref, version_id)

            for entity_type in ("shot", "shot_video"):
                output = current.get((entity_type, shot["id"]))
                if output is None:
                    continue
                add_version(output["id"])
                result = health.get(output["id"], {"state": "unknown", "issues": []})
                next(node for node in nodes if node["id"] == output["id"])["state"] = result["state"]
                refs = payload(output).get("source_refs", [])
                if entity_type == "shot_video" and isinstance(refs, list):
                    for ref in refs:
                        if isinstance(ref, dict):
                            add_ref(ref, output["id"])
            issues = []
            for entity_type, media in (("shot", "image"), ("shot_video", "video")):
                output = current.get((entity_type, shot["id"]))
                for issue in health.get(output["id"], {}).get("issues", []) if output else []:
                    issues.append({**issue, "media": media, "shot_id": shot["id"]})
            groups.append({"shot_id": shot["id"], "label": f"{shot['scene_title']} · 镜头 {shot['shot_number'] or '?'}", "nodes": nodes, "edges": edges, "issues": issues})
        total = len(rows) if shot_id else len(all_rows)
        return {"project_id": project_id, "scope": scope, "shots": groups, "total": total}

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

    def regeneration_plan(
        self, project_id: str, node_type: str, node_id: str
    ) -> dict:
        """把图谱节点投影为可由用户确认的分镜再生成清单。"""
        affected = self.affected_nodes(project_id, node_type, node_id)
        targets: dict[str, dict[str, str]] = {"image": {}, "video": {}}

        with get_connection(self.db_path) as conn:
            current = {(row['entity_type'], row['entity_id']): row['id'] for row in conn.execute(
                "SELECT id, entity_type, entity_id FROM versions WHERE project_id = ? AND is_current = 1 AND entity_type IN ('shot', 'shot_video')", (project_id,)
            )}
        health = self.dependency_health(project_id, list(current.values()))
        for (entity_type, shot_id), version_id in current.items():
            if any(issue['source_id'] == node_id for issue in health[version_id]['issues']):
                targets['image' if entity_type == 'shot' else 'video'][shot_id] = ''

        with get_connection(self.db_path) as conn:
            for node in affected:
                target_kind = "image" if node["type"] == "shot" else ""
                shot_id = node["id"] if target_kind else ""
                if node["type"] in {"image_version", "video_version"}:
                    row = conn.execute(
                        "SELECT entity_type, entity_id FROM versions WHERE id = ? AND project_id = ?",
                        (node["id"], project_id),
                    ).fetchone()
                    if row is None or row["entity_type"] not in {"shot", "shot_video"}:
                        continue
                    target_kind = "image" if node["type"] == "image_version" else "video"
                    shot_id = row["entity_id"]
                if not target_kind or not shot_id:
                    continue
                targets[target_kind].setdefault(shot_id, node["relation"])

            def items(kind: str) -> list[dict]:
                result = []
                for shot_id, reason in targets[kind].items():
                    version_id = current.get(('shot' if kind == 'image' else 'shot_video', shot_id))
                    if not version_id:
                        continue
                    dependency = health[version_id]
                    if dependency['state'] in {'current', 'none'}:
                        continue
                    row = conn.execute(
                        """
                        SELECT shots.shot_number, scenes.order_index AS scene_order,
                               episodes.order_index AS episode_order
                        FROM shots
                        LEFT JOIN scenes ON scenes.id = shots.scene_id
                        LEFT JOIN episodes ON episodes.id = scenes.episode_id
                        WHERE shots.id = ? AND shots.project_id = ? AND shots.deleted_at IS NULL
                        """,
                        (shot_id, project_id),
                    ).fetchone()
                    if row is None:
                        continue
                    else:
                        episode = int(row["episode_order"] or 0) + 1
                        scene = int(row["scene_order"] or 0) + 1
                        shot = row["shot_number"] or "-"
                        label = f"第 {episode} 集 · 场 {scene} · 镜头 {shot}"
                    result.append(
                        {
                            "shot_id": shot_id,
                            "label": label,
                            "dependency_state": dependency['state'],
                            "reason": '；'.join(issue['label'] for issue in dependency['issues']),
                        }
                    )
                return sorted(result, key=lambda item: item["label"])

            return {
                "changed_node": {"type": node_type, "id": node_id},
                "image_shots": items("image"),
                "video_shots": items("video"),
            }

    def remove_edge(self, edge_id: str) -> None:
        self.get(edge_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "DELETE FROM production_edges WHERE id = ?", (edge_id,)
            )
