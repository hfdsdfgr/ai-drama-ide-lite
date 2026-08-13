"""Story Bible 读写（Phase 6）。

复用 Phase 1 基线 schema 的 stories / characters / locations / props 表。
实体同步策略：按 (project_id, name) upsert——新实体插入、已有实体更新描述；
不删除已有行（保护用户可能的手动数据）。完整覆盖式的清理留到后续明确需求。
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db.database import get_connection
from app.schemas.story import BibleCharacter, BibleLocation, BibleProp, StoryBible
from app.services.ids import new_asset_id, slugify


ASSET_TYPES = ("character", "location", "prop")


def asset_type_of(entity: BibleCharacter | BibleLocation | BibleProp) -> str:
    if isinstance(entity, BibleCharacter):
        return "character"
    if isinstance(entity, BibleLocation):
        return "location"
    return "prop"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class StoryRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get_bible(self, project_id: str) -> StoryBible | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT content FROM stories WHERE project_id = ? ORDER BY updated_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row["content"])
            return StoryBible(**data)
        except (ValueError, TypeError):
            return None

    def save_bible(self, project_id: str, bible: StoryBible) -> None:
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM stories WHERE project_id = ? LIMIT 1", (project_id,)
            ).fetchone()
            assigned = self._with_asset_ids(conn, project_id, bible)
            content = json.dumps(assigned.model_dump(), ensure_ascii=False)
            if existing:
                conn.execute(
                    "UPDATE stories SET content = ?, updated_at = ? WHERE id = ?",
                    (content, now, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO stories (id, project_id, content, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (_new_id("story"), project_id, content, now, now),
                )
            self._sync_entities(conn, project_id, "characters", assigned.characters)
            self._sync_entities(conn, project_id, "locations", assigned.locations)
            self._sync_entities(conn, project_id, "props", assigned.props)
            self._sync_assets(conn, project_id, assigned)

    @staticmethod
    def _with_asset_ids(
        conn, project_id: str, bible: StoryBible
    ) -> StoryBible:
        """为每个实体分配稳定 Asset ID（按 project+type+name 复用），并写回实体。"""

        pending: dict[str, int] = {}

        def assign(entity: BibleCharacter | BibleLocation | BibleProp):
            asset_type = asset_type_of(entity)
            row = conn.execute(
                "SELECT id FROM assets WHERE project_id = ? AND asset_type = ? AND name = ?",
                (project_id, asset_type, entity.name),
            ).fetchone()
            if row:
                asset_id = row["id"]
            else:
                count = conn.execute(
                    "SELECT COUNT(*) AS c FROM assets WHERE project_id = ? AND asset_type = ?",
                    (project_id, asset_type),
                ).fetchone()["c"]
                pending[asset_type] = pending.get(asset_type, 0) + 1
                asset_id = new_asset_id(
                    asset_type, slugify(entity.name), count + pending[asset_type]
                )
            return entity.model_copy(update={"asset_id": asset_id})

        return bible.model_copy(
            update={
                "characters": [assign(c) for c in bible.characters],
                "locations": [assign(l) for l in bible.locations],
                "props": [assign(p) for p in bible.props],
            }
        )

    @staticmethod
    def _sync_assets(conn, project_id: str, bible: StoryBible) -> None:
        """把资产卡投影到 assets 表（prompt = reference_prompt，Phase 9 版本化入口）。"""
        now = _now_iso()
        groups = (
            ("character", bible.characters),
            ("location", bible.locations),
            ("prop", bible.props),
        )
        for asset_type, items in groups:
            for item in items:
                prompt = getattr(item, "reference_prompt", "") or ""
                existing = conn.execute(
                    "SELECT id FROM assets WHERE project_id = ? AND asset_type = ? AND name = ?",
                    (project_id, asset_type, item.name),
                ).fetchone()
                if existing:
                    conn.execute(
                        "UPDATE assets SET prompt = ?, name = ?, version = 1, updated_at = ? WHERE id = ?",
                        (prompt, item.name, now, existing["id"]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO assets"
                        " (id, project_id, asset_type, name, prompt, version, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                        (item.asset_id, project_id, asset_type, item.name, prompt, now, now),
                    )

    def list_assets(self, project_id: str, asset_type: str | None = None) -> list[dict]:
        """返回资产卡列表（含 Asset ID）。"""
        bible = self.get_bible(project_id)
        if bible is None:
            return []
        missing = [
            item
            for group in (bible.characters, bible.locations, bible.props)
            for item in group
            if not item.asset_id
        ]
        if missing:
            # 旧数据回填：保存一次即分配稳定 Asset ID 并同步 assets 表
            self.save_bible(project_id, bible)
            bible = self.get_bible(project_id)
            if bible is None:
                return []
        groups = (
            ("character", bible.characters),
            ("location", bible.locations),
            ("prop", bible.props),
        )
        result: list[dict] = []
        for kind, items in groups:
            if asset_type and kind != asset_type:
                continue
            for item in items:
                result.append(
                    {
                        "asset_type": kind,
                        "asset_id": item.asset_id,
                        "name": item.name,
                        "reference_prompt": item.reference_prompt,
                        "fields": item.model_dump(),
                    }
                )
        return result

    def get_asset(
        self, project_id: str, asset_type: str, name: str
    ) -> dict | None:
        for asset in self.list_assets(project_id, asset_type):
            if asset["name"] == name:
                return asset
        return None

    def update_asset(
        self, project_id: str, asset_type: str, name: str, patch: dict
    ) -> dict | None:
        """按 name 更新单个资产卡（名称不可改）；patch 仅允许资产卡字段。"""
        bible = self.get_bible(project_id)
        if bible is None:
            return None
        entity = self._find_entity(bible, asset_type, name)
        if entity is None:
            return None
        allowed = set(type(entity).model_fields) - {"name", "asset_id"}
        clean = {k: v for k, v in patch.items() if k in allowed}
        if not clean:
            return self.get_asset(project_id, asset_type, name)
        updated = entity.model_copy(update=clean)
        new_bible = self._replace_entity(bible, asset_type, updated)
        self.save_bible(project_id, new_bible)
        return self.get_asset(project_id, asset_type, name)

    def delete_asset(self, project_id: str, asset_type: str, name: str) -> bool:
        """从 Story Bible 移除资产卡，并清理投影行（用户主动删除）。"""
        bible = self.get_bible(project_id)
        if bible is None or self._find_entity(bible, asset_type, name) is None:
            return False
        new_bible = self._remove_entity(bible, asset_type, name)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "DELETE FROM assets WHERE project_id = ? AND asset_type = ? AND name = ?",
                (project_id, asset_type, name),
            )
            table = {
                "character": "characters",
                "location": "locations",
                "prop": "props",
            }[asset_type]
            conn.execute(
                f"DELETE FROM {table} WHERE project_id = ? AND name = ?",
                (project_id, name),
            )
        self.save_bible(project_id, new_bible)
        return True

    @staticmethod
    def _find_entity(
        bible: StoryBible, asset_type: str, name: str
    ) -> BibleCharacter | BibleLocation | BibleProp | None:
        items: list = {
            "character": bible.characters,
            "location": bible.locations,
            "prop": bible.props,
        }[asset_type]
        for item in items:
            if item.name == name:
                return item
        return None

    @staticmethod
    def _replace_entity(
        bible: StoryBible,
        asset_type: str,
        updated: BibleCharacter | BibleLocation | BibleProp,
    ) -> StoryBible:
        def replace(items: list):
            return [
                updated if item.name == updated.name else item
                for item in items
            ]

        update = {}
        if asset_type == "character":
            update["characters"] = replace(bible.characters)
        elif asset_type == "location":
            update["locations"] = replace(bible.locations)
        else:
            update["props"] = replace(bible.props)
        return bible.model_copy(update=update)

    @staticmethod
    def _remove_entity(
        bible: StoryBible, asset_type: str, name: str
    ) -> StoryBible:
        def remove(items: list):
            return [item for item in items if item.name != name]

        update = {}
        if asset_type == "character":
            update["characters"] = remove(bible.characters)
        elif asset_type == "location":
            update["locations"] = remove(bible.locations)
        else:
            update["props"] = remove(bible.props)
        return bible.model_copy(update=update)

    @staticmethod
    def _sync_entities(
        conn,
        project_id: str,
        table: str,
        items: list[BibleCharacter | BibleLocation | BibleProp],
    ) -> None:
        prefix = {
            "characters": "char",
            "locations": "loc",
            "props": "prop",
        }[table]
        now = _now_iso()
        for item in items:
            description = getattr(item, "summary", None) or item.description
            if not description:
                description = ""
            existing = conn.execute(
                f"SELECT id FROM {table} WHERE project_id = ? AND name = ?",
                (project_id, item.name),
            ).fetchone()
            if existing:
                conn.execute(
                    f"UPDATE {table} SET description = ?, updated_at = ? WHERE id = ?",
                    (description, now, existing["id"]),
                )
            else:
                conn.execute(
                    f"INSERT INTO {table} (id, project_id, name, description, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (_new_id(prefix), project_id, item.name, description, now, now),
                )


def bible_context_text(db_path: Path, project_id: str) -> str:
    """把项目 Story Bible 压缩成写作上下文；无 Bible 返回空串。"""
    bible = StoryRepository(db_path).get_bible(project_id)
    if bible is None:
        return ""
    lines: list[str] = []
    if bible.synopsis:
        lines.append(f"故事简介：{bible.synopsis}")
    if bible.characters:
        lines.append(
            "角色："
            + "；".join(
                f"{c.name}（{c.role_hint or '角色'}：{c.summary}）"
                for c in bible.characters
            )
        )
    if bible.locations:
        lines.append(
            "地点："
            + "；".join(f"{loc.name}（{loc.description}）" for loc in bible.locations)
        )
    if bible.props:
        lines.append(
            "道具："
            + "；".join(f"{prop.name}（{prop.description}）" for prop in bible.props)
        )
    if bible.plotlines:
        lines.append("情节线：" + "；".join(bible.plotlines))
    return "\n".join(lines)
