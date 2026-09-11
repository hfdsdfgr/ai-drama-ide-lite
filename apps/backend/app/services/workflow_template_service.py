"""Persistence and explicit field-by-field application of workflow templates."""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.schemas.workflow_template import WorkflowConfig


FIELDS = {
    "auto_continue": "自动继续",
    "storyboard.enabled": "生成分镜",
    "storyboard.model_id": "分镜模型",
    "shot_images.enabled": "生成关键帧",
    "shot_images.model_id": "图片模型",
    "shot_images.capability": "图片能力",
    "shot_images.aspect_ratio": "图片比例",
    "videos.enabled": "生成视频",
    "videos.model_id": "视频模型",
    "videos.capability": "视频能力",
    "videos.aspect_ratio": "视频规格",
    "videos.duration_mode": "视频时长来源",
    "videos.duration": "固定视频时长",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return f"workflow_{uuid.uuid4().hex[:16]}"


def _value(data: dict, path: str):
    current = data
    for part in path.split("."):
        current = current[part]
    return current


def _set_value(data: dict, path: str, value) -> None:
    parts = path.split(".")
    current = data
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


class WorkflowTemplateService:
    def __init__(self, db_path: Path, manager) -> None:
        self.db_path = db_path
        self.manager = manager

    def _episode(self, project_id: str, episode_id: str) -> None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM episodes WHERE id = ? AND project_id = ? AND deleted_at IS NULL",
                (episode_id, project_id),
            ).fetchone()
        if row is None:
            raise AppError(404, "episode_not_found", f"剧集不存在: {episode_id}")

    def _project(self, project_id: str) -> None:
        with get_connection(self.db_path) as conn:
            row = conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise AppError(404, "project_not_found", f"项目不存在: {project_id}")

    def list_templates(self, project_id: str) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_templates WHERE project_id = ? ORDER BY updated_at DESC",
                (project_id,),
            ).fetchall()
        return [self._template_out(row) for row in rows]

    def get_template(self, project_id: str, template_id: str) -> dict:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM workflow_templates WHERE id = ? AND project_id = ?",
                (template_id, project_id),
            ).fetchone()
        if row is None:
            raise AppError(404, "workflow_template_not_found", "制作模板不存在")
        return self._template_out(row)

    def create_template(self, project_id: str, name: str, description: str, config: WorkflowConfig) -> dict:
        self._project(project_id)
        now = _now()
        template_id = _new_id()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """INSERT INTO workflow_templates
                   (id, project_id, name, description, schema_version, revision, config_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?, 1, 1, ?, ?, ?)""",
                (template_id, project_id, name.strip(), description.strip(), config.model_dump_json(), now, now),
            )
        return self.get_template(project_id, template_id)

    def update_template(self, project_id: str, template_id: str, *, expected_revision: int, name=None, description=None, config=None) -> dict:
        current = self.get_template(project_id, template_id)
        if current["revision"] != expected_revision:
            raise AppError(409, "workflow_template_changed", "模板已被修改，请刷新后重试")
        values = {
            "name": name.strip() if name is not None else current["name"],
            "description": description.strip() if description is not None else current["description"],
            "config": config or current["config"],
        }
        with get_connection(self.db_path) as conn:
            result = conn.execute(
                """UPDATE workflow_templates SET name = ?, description = ?, config_json = ?,
                   revision = revision + 1, updated_at = ? WHERE id = ? AND project_id = ? AND revision = ?""",
                (values["name"], values["description"], WorkflowConfig.model_validate(values["config"]).model_dump_json(), _now(), template_id, project_id, expected_revision),
            )
        if result.rowcount == 0:
            raise AppError(409, "workflow_template_changed", "模板已被修改，请刷新后重试")
        return self.get_template(project_id, template_id)

    def delete_template(self, project_id: str, template_id: str) -> None:
        with get_connection(self.db_path) as conn:
            result = conn.execute(
                "DELETE FROM workflow_templates WHERE id = ? AND project_id = ?",
                (template_id, project_id),
            )
        if result.rowcount == 0:
            raise AppError(404, "workflow_template_not_found", "制作模板不存在")

    def get_episode_config(self, project_id: str, episode_id: str) -> dict:
        self._episode(project_id, episode_id)
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM episode_workflow_configs WHERE episode_id = ? AND project_id = ?",
                (episode_id, project_id),
            ).fetchone()
        if row is None:
            return {"project_id": project_id, "episode_id": episode_id, "revision": 0, "config": self.default_config(), "updated_at": None}
        return {"project_id": project_id, "episode_id": episode_id, "revision": row["revision"], "config": WorkflowConfig.model_validate_json(row["config_json"]), "updated_at": row["updated_at"]}

    def put_episode_config(self, project_id: str, episode_id: str, expected_revision: int, config: WorkflowConfig) -> dict:
        current = self.get_episode_config(project_id, episode_id)
        if current["revision"] != expected_revision:
            raise AppError(409, "episode_workflow_config_changed", "剧集配置已被修改，请刷新后重试")
        now = _now()
        with get_connection(self.db_path) as conn:
            if expected_revision == 0:
                try:
                    conn.execute(
                        "INSERT INTO episode_workflow_configs (episode_id, project_id, revision, config_json, updated_at) VALUES (?, ?, 1, ?, ?)",
                        (episode_id, project_id, config.model_dump_json(), now),
                    )
                except sqlite3.IntegrityError as exc:
                    raise AppError(409, "episode_workflow_config_changed", "剧集配置已被修改，请刷新后重试") from exc
            else:
                result = conn.execute(
                    "UPDATE episode_workflow_configs SET revision = revision + 1, config_json = ?, updated_at = ? WHERE episode_id = ? AND project_id = ? AND revision = ?",
                    (config.model_dump_json(), now, episode_id, project_id, expected_revision),
                )
                if result.rowcount == 0:
                    raise AppError(409, "episode_workflow_config_changed", "剧集配置已被修改，请刷新后重试")
        return self.get_episode_config(project_id, episode_id)

    def preview(self, project_id: str, episode_id: str, template_id: str) -> dict:
        current = self.get_episode_config(project_id, episode_id)
        template = self.get_template(project_id, template_id)
        current_data = current["config"].model_dump()
        template_data = template["config"].model_dump()
        differences = []
        for path, label in FIELDS.items():
            old, new = _value(current_data, path), _value(template_data, path)
            if old == new:
                continue
            compatible, reason = self._compatible(path, new)
            differences.append({"field_path": path, "label": label, "current_value": old, "template_value": new, "compatible": compatible, "reason": reason, "candidates": self._candidates(path, template_data) if not compatible else []})
        return {"template_id": template_id, "template_revision": template["revision"], "config_revision": current["revision"], "differences": differences}

    def apply(self, project_id: str, episode_id: str, *, template_id: str, template_revision: int, config_revision: int, selected_fields: list[str]) -> dict:
        template = self.get_template(project_id, template_id)
        current = self.get_episode_config(project_id, episode_id)
        if template["revision"] != template_revision or current["revision"] != config_revision:
            raise AppError(409, "workflow_preview_expired", "模板或剧集配置已变化，请重新预览")
        invalid = [path for path in selected_fields if path not in FIELDS]
        if invalid:
            raise AppError(422, "invalid_workflow_fields", f"未知配置项: {', '.join(invalid)}")
        current_data = current["config"].model_dump()
        template_data = template["config"].model_dump()
        touched_stages = set()
        for path in dict.fromkeys(selected_fields):
            compatible, reason = self._compatible(path, _value(template_data, path))
            if not compatible:
                raise AppError(422, "workflow_field_incompatible", reason)
            _set_value(current_data, path, _value(template_data, path))
            if "." in path and path.rsplit(".", 1)[1] in {"enabled", "model_id", "capability"}:
                touched_stages.add(path.split(".", 1)[0])
        config = WorkflowConfig.model_validate(current_data)
        for stage_name in touched_stages:
            stage = getattr(config, stage_name)
            if not stage.enabled:
                continue
            kind = {"storyboard": "llm", "shot_images": "image", "videos": "video"}[stage_name]
            compatible, reason = self._model_compatible(stage.model_id, kind, stage.capability)
            if not compatible:
                raise AppError(422, "workflow_model_unavailable", reason)
        return self.put_episode_config(project_id, episode_id, config_revision, config)

    def default_config(self) -> WorkflowConfig:
        config = WorkflowConfig()
        for key, kind, capability in (("storyboard", "llm", "llm"), ("shot_images", "image", "text_to_image"), ("videos", "video", "image_to_video")):
            models = self.manager.repo.list_models(model_type=kind, enabled_only=True)
            model = next(
                (item for item in models if kind == "llm" or capability in item.capabilities),
                None,
            )
            if model:
                getattr(config, key).model_id = model.id
        return config

    def validate_config(self, config: WorkflowConfig) -> None:
        for key, kind in (("storyboard", "llm"), ("shot_images", "image"), ("videos", "video")):
            stage = getattr(config, key)
            if not stage.enabled:
                continue
            compatible, reason = self._model_compatible(stage.model_id, kind, stage.capability)
            if not compatible:
                raise AppError(422, "workflow_model_unavailable", reason)

    def _compatible(self, path: str, value) -> tuple[bool, str]:
        if path.endswith("model_id"):
            stage = path.split(".")[0]
            kind = {"storyboard": "llm", "shot_images": "image", "videos": "video"}[stage]
            return self._model_compatible(str(value), kind, "")
        return True, ""

    def _model_compatible(self, model_id: str, kind: str, capability: str) -> tuple[bool, str]:
        if not model_id:
            return False, "尚未选择模型"
        available = {model.id: model for model in self.manager.repo.list_models(model_type=kind, enabled_only=True)}
        model = available.get(model_id)
        if model is None:
            return False, "模型不存在、已停用或缺少可用凭据"
        if kind != "llm" and capability and capability not in model.capabilities:
            return False, f"模型不支持 {capability}"
        return True, ""

    def _candidates(self, path: str, config: dict) -> list[dict]:
        if not path.endswith("model_id"):
            return []
        stage = path.split(".")[0]
        kind = {"storyboard": "llm", "shot_images": "image", "videos": "video"}[stage]
        capability = config[stage]["capability"]
        models = self.manager.repo.list_models(model_type=kind, enabled_only=True)
        return [
            {"id": model.id, "name": model.model_id}
            for model in models
            if kind == "llm" or capability in model.capabilities
        ][:5]

    @staticmethod
    def _template_out(row) -> dict:
        return {"id": row["id"], "project_id": row["project_id"], "name": row["name"], "description": row["description"], "schema_version": row["schema_version"], "revision": row["revision"], "config": WorkflowConfig.model_validate_json(row["config_json"]), "created_at": row["created_at"], "updated_at": row["updated_at"]}
