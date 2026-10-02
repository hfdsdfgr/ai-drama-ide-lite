"""Project-scoped prompt overrides, optimistic revisions and task snapshots."""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.services.prompt_catalog import (
    INPUT_DATA_CONTRACT,
    PROMPT_DEFINITIONS,
    PromptDefinition,
    compile_system_prompt,
    get_definition,
)

_UNSET = object()


def validate_override(definition: PromptDefinition, override: dict) -> dict:
    """Validate both API values and untrusted settings imported in a project ZIP."""
    if not isinstance(override, dict) or set(override) - {"rules", "negative_prompt"}:
        raise AppError(422, "prompt_settings_invalid", "提示词配置格式不正确")
    validated = {}
    for name, limit in (("rules", 12000), ("negative_prompt", 1000)):
        if name not in override:
            continue
        value = override[name]
        if not isinstance(value, str) or len(value) > limit:
            raise AppError(422, "prompt_settings_invalid", "提示词配置必须为长度限制内的文本")
        if name == "rules" and not definition.allow_empty_rules and not value.strip():
            raise AppError(422, "prompt_rules_required", "文本环节的创作规则不能为空，请填写规则或恢复默认")
        if name == "negative_prompt" and definition.default_negative_prompt is None:
            raise AppError(422, "prompt_negative_unsupported", "该环节不支持负向提示词")
        validated[name] = value
    return validated


def validate_overrides(overrides: dict) -> dict:
    if not isinstance(overrides, dict):
        raise AppError(422, "prompt_settings_invalid", "提示词配置格式不正确")
    return {
        stage_id: validate_override(get_definition(stage_id), values)
        for stage_id, values in overrides.items()
    }


class PromptSettingsService:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    @staticmethod
    def _check_project(conn, project_id: str) -> None:
        if conn.execute(
            "SELECT 1 FROM projects WHERE id = ? AND deleted_at IS NULL", (project_id,)
        ).fetchone() is None:
            raise AppError(404, "project_not_found", "项目不存在，请重新选择项目")

    def _read(self, project_id: str) -> tuple[int, dict]:
        with get_connection(self.db_path) as conn:
            self._check_project(conn, project_id)
            row = conn.execute(
                "SELECT revision, overrides_json FROM project_prompt_settings WHERE project_id = ?",
                (project_id,),
            ).fetchone()
        if row is None:
            return 0, {}
        try:
            overrides = json.loads(row["overrides_json"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise AppError(500, "prompt_settings_corrupt", "项目提示词配置无法读取，请恢复备份后重试") from exc
        return row["revision"], validate_overrides(overrides)

    @staticmethod
    def _effective(definition: PromptDefinition, override: dict) -> dict:
        return {
            "rules": override.get("rules", definition.default_rules),
            "negative_prompt": override.get("negative_prompt", definition.default_negative_prompt),
        }

    def resolve(self, project_id: str, stage_id: str, snapshot: dict | None = None) -> dict:
        definition = get_definition(stage_id)
        if snapshot is not None:
            # Old in-process callers can supply an empty snapshot for built-in defaults.
            values = snapshot.get("stages", {}).get(stage_id, {})
            return self._effective(definition, values)
        _revision, overrides = self._read(project_id)
        return self._effective(definition, overrides.get(stage_id, {}))

    def system_prompt(
        self, project_id: str, stage_id: str, snapshot: dict | None = None,
        variant: str = "default",
    ) -> str:
        return compile_system_prompt(
            get_definition(stage_id), self.resolve(project_id, stage_id, snapshot)["rules"], variant
        )

    def snapshot(self, project_id: str) -> dict:
        revision, overrides = self._read(project_id)
        return {
            "revision": revision,
            "stages": {
                stage_id: self._effective(definition, overrides.get(stage_id, {}))
                for stage_id, definition in PROMPT_DEFINITIONS.items()
            },
        }

    @staticmethod
    def _contract(definition: PromptDefinition) -> str:
        if not definition.contract:
            return ""
        variants = "\n\n".join(
            f"{variant} 输出：{contract}" for variant, contract in definition.variants.items()
        )
        return "\n\n".join(part for part in (
            INPUT_DATA_CONTRACT, definition.contract, variants
        ) if part)

    def _stage(self, definition: PromptDefinition, values: dict) -> dict:
        return {
            "id": definition.id,
            "label": definition.label,
            "group": definition.group,
            "description": definition.description,
            "default_rules": definition.default_rules,
            "default_negative_prompt": definition.default_negative_prompt,
            **values,
            "customized": values != self._effective(definition, {}),
            "allow_empty_rules": definition.allow_empty_rules,
            "contract": self._contract(definition),
            "preview": compile_system_prompt(definition, values["rules"]),
        }

    def list_settings(self, project_id: str) -> dict:
        snapshot = self.snapshot(project_id)
        return {
            "revision": snapshot["revision"],
            "stages": [
                self._stage(definition, snapshot["stages"][stage_id])
                for stage_id, definition in PROMPT_DEFINITIONS.items()
            ],
        }

    def update(
        self, project_id: str, stage_id: str, expected_revision: int,
        rules: str | None, negative_prompt=_UNSET,
    ) -> dict:
        definition = get_definition(stage_id)
        if type(expected_revision) is not int or expected_revision < 0:
            raise AppError(422, "prompt_revision_invalid", "提示词修订号必须为非负整数")
        proposed = {} if rules is None else {"rules": rules}
        if rules is not None and negative_prompt not in (_UNSET, None):
            proposed["negative_prompt"] = negative_prompt
        validate_override(definition, proposed)
        with get_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._check_project(conn, project_id)
            row = conn.execute(
                "SELECT revision, overrides_json FROM project_prompt_settings WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            revision = row["revision"] if row else 0
            if revision != expected_revision:
                raise AppError(409, "prompt_revision_conflict", "项目提示词已被修改，请刷新配置后重新保存")
            overrides = json.loads(row["overrides_json"]) if row else {}
            validate_overrides(overrides)
            if rules is None:
                overrides.pop(stage_id, None)
            else:
                current = self._effective(definition, overrides.get(stage_id, {}))
                current["rules"] = rules
                if negative_prompt is not _UNSET:
                    current["negative_prompt"] = (
                        definition.default_negative_prompt if negative_prompt is None else negative_prompt
                    )
                override = {
                    key: value for key, value in current.items()
                    if value != self._effective(definition, {})[key]
                }
                if override:
                    overrides[stage_id] = override
                else:
                    overrides.pop(stage_id, None)
            conn.execute(
                """INSERT INTO project_prompt_settings (project_id, revision, overrides_json, updated_at)
                VALUES (?, ?, ?, ?) ON CONFLICT(project_id) DO UPDATE SET
                revision=excluded.revision, overrides_json=excluded.overrides_json,
                updated_at=excluded.updated_at""",
                (project_id, revision + 1, json.dumps(overrides, ensure_ascii=False),
                 datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")),
            )
        return self.list_settings(project_id)

    def preview(
        self, project_id: str, stage_id: str, rules: str | None, negative_prompt=_UNSET,
    ) -> dict:
        definition = get_definition(stage_id)
        current = self.resolve(project_id, stage_id)
        if rules is None:
            values = self._effective(definition, {})
        else:
            values = {**current, "rules": rules}
            if negative_prompt is not _UNSET:
                values["negative_prompt"] = (
                    definition.default_negative_prompt if negative_prompt is None else negative_prompt
                )
        validate_override(definition, {key: value for key, value in values.items() if value is not None})
        prompt = compile_system_prompt(definition, values["rules"])
        return {
            "stage_id": stage_id, "id": stage_id,
            "system_prompt": prompt, "preview": prompt,
            **values, "contract": self._contract(definition),
        }
