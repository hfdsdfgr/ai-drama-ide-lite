"""Provider / Model 仓储（SQLite + SecretStore）。"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.schemas.provider import (
    ModelCreate,
    ModelCapabilityUpdate,
    ModelOut,
    ModelType,
    ModelUpdate,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
)
from app.services.capability_registry import (
    parse,
    resolve_default_capabilities,
    serialize,
    validate_capabilities,
)
from app.services.secret_store import SecretStore
from app.services.vendor_presets import classify_model, get_preset

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_id(value: str, label: str) -> None:
    if not ID_PATTERN.fullmatch(value):
        raise AppError(422, "invalid_id", f"{label} ID 不合法")


class ProviderRepository:
    def __init__(self, db_path: Path, secret_store: SecretStore) -> None:
        self.db_path = db_path
        self.secret_store = secret_store

    # ---------- Providers ----------

    def list_providers(self) -> list[ProviderOut]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT p.*,
                       (SELECT COUNT(*) FROM models m
                         WHERE m.provider_id = p.id AND m.deleted_at IS NULL) AS model_count
                FROM providers p
                WHERE p.deleted_at IS NULL
                ORDER BY p.created_at
                """
            ).fetchall()
        return [_provider_out(row, self.secret_store) for row in rows]

    def get_provider(self, provider_id: str) -> ProviderOut:
        _validate_id(provider_id, "Provider")
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT p.*,
                       (SELECT COUNT(*) FROM models m
                         WHERE m.provider_id = p.id AND m.deleted_at IS NULL) AS model_count
                FROM providers p
                WHERE p.id = ? AND p.deleted_at IS NULL
                """,
                (provider_id,),
            ).fetchone()
        if row is None:
            raise AppError(404, "provider_not_found", f"Provider 不存在: {provider_id}")
        return _provider_out(row, self.secret_store)

    def create_provider(self, data: ProviderCreate) -> ProviderOut:
        preset = get_preset(data.preset_key) if data.preset_key else None
        if data.preset_key and preset is None:
            raise AppError(422, "unknown_preset", f"未知厂商预设: {data.preset_key}")

        name = data.name or (preset.name if preset else None)
        if not name or not name.strip():
            raise AppError(422, "provider_name_required", "请填写 Provider 名称")
        if preset is None and not data.api_base_url.strip():
            raise AppError(422, "base_url_required", "自定义 Provider 需要填写 Base URL")

        base_url = preset.base_url if preset else data.api_base_url.strip()
        needs_key = preset.needs_key if preset else data.needs_key

        # 同一厂商预设不允许重复添加（避免"加了 3 个阿里云"）
        if preset is not None:
            with get_connection(self.db_path) as conn:
                exists = conn.execute(
                    "SELECT 1 FROM providers WHERE preset_key = ? AND deleted_at IS NULL",
                    (preset.key,),
                ).fetchone()
            if exists:
                raise AppError(
                    409,
                    "provider_already_exists",
                    f"已存在该厂商的 Provider：{preset.name}，可直接编辑它",
                )

        provider_id = _new_id("prov")
        key_ref = f"provider:{provider_id}" if (needs_key or data.api_key) else None
        now = _now_iso()

        # 先写密钥再入库：密钥写入失败时不留下空 Provider 记录
        if data.api_key:
            self.secret_store.set(key_ref, data.api_key)
        try:
            with get_connection(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO providers (id, name, preset_key, api_base_url, needs_key, enabled, key_ref, created_at, updated_at, deleted_at)"
                    " VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, NULL)",
                    (
                        provider_id,
                        name.strip(),
                        preset.key if preset else None,
                        base_url,
                        1 if needs_key else 0,
                        key_ref,
                        now,
                        now,
                    ),
                )
        except Exception:
            if key_ref:
                try:
                    self.secret_store.delete(key_ref)
                except Exception:
                    pass
            raise
        return self.get_provider(provider_id)

    def update_provider(self, provider_id: str, data: ProviderUpdate) -> ProviderOut:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM providers WHERE id = ? AND deleted_at IS NULL",
                (provider_id,),
            ).fetchone()
            if row is None:
                raise AppError(404, "provider_not_found", f"Provider 不存在: {provider_id}")
            key_ref = row["key_ref"]
            updates = []
            values = []
            if data.name is not None:
                updates.append("name = ?")
                values.append(data.name.strip())
            if data.api_base_url is not None:
                updates.append("api_base_url = ?")
                values.append(data.api_base_url.strip())
            if data.needs_key is not None:
                updates.append("needs_key = ?")
                values.append(1 if data.needs_key else 0)
            if data.enabled is not None:
                updates.append("enabled = ?")
                values.append(1 if data.enabled else 0)
            updates.append("updated_at = ?")
            values.append(_now_iso())
            values.append(provider_id)
            conn.execute(
                f"UPDATE providers SET {', '.join(updates)} WHERE id = ?",
                values,
            )
        if data.api_key:
            key_ref = key_ref or f"provider:{provider_id}"
            if row["key_ref"] is None:
                with get_connection(self.db_path) as conn:
                    conn.execute(
                        "UPDATE providers SET key_ref = ?, updated_at = ? WHERE id = ?",
                        (key_ref, _now_iso(), provider_id),
                    )
            self.secret_store.set(key_ref, data.api_key)
        return self.get_provider(provider_id)

    def soft_delete_provider(self, provider_id: str) -> None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT key_ref FROM providers WHERE id = ? AND deleted_at IS NULL",
                (provider_id,),
            ).fetchone()
        if row is None:
            raise AppError(404, "provider_not_found", f"Provider 不存在: {provider_id}")
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE providers SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (now, now, provider_id),
            )
            conn.execute(
                "UPDATE models SET deleted_at = ?, updated_at = ? WHERE provider_id = ? AND deleted_at IS NULL",
                (now, now, provider_id),
            )
        if row["key_ref"]:
            self.secret_store.delete(row["key_ref"])

    # ---------- Models ----------

    def list_models(
        self,
        provider_id: str | None = None,
        model_type: str | None = None,
        enabled_only: bool = False,
        capability: str | None = None,
    ) -> list[ModelOut]:
        conditions = ["m.deleted_at IS NULL", "p.deleted_at IS NULL"]
        params: list = []
        if provider_id:
            conditions.append("m.provider_id = ?")
            params.append(provider_id)
        if model_type:
            conditions.append("m.model_type = ?")
            params.append(model_type)
        if enabled_only:
            conditions.append("m.enabled = 1")
        if capability:
            conditions.append("m.capabilities LIKE ?")
            params.append(f'%"{capability}"%')
        where = " AND ".join(conditions)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT m.*, p.name AS provider_name, p.api_base_url AS provider_base_url,
                       p.needs_key AS provider_needs_key, p.key_ref AS provider_key_ref
                FROM models m
                JOIN providers p ON p.id = m.provider_id
                WHERE {where}
                ORDER BY m.model_type, m.model_id
                """,
                params,
            ).fetchall()
        return [_model_out(row, self.secret_store) for row in rows]

    def get_model(self, model_id: str) -> ModelOut:
        _validate_id(model_id, "Model")
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT m.*, p.name AS provider_name, p.api_base_url AS provider_base_url,
                       p.needs_key AS provider_needs_key, p.key_ref AS provider_key_ref
                FROM models m
                JOIN providers p ON p.id = m.provider_id
                WHERE m.id = ? AND m.deleted_at IS NULL AND p.deleted_at IS NULL
                """,
                (model_id,),
            ).fetchone()
        if row is None:
            raise AppError(404, "model_not_found", f"Model 不存在: {model_id}")
        return _model_out(row, self.secret_store)

    def create_model(self, data: ModelCreate) -> ModelOut:
        provider = self.get_provider(data.provider_id)
        now = _now_iso()
        model_id = _new_id("model")
        capabilities = resolve_default_capabilities(
            provider.preset_key, data.model_id.strip(), data.model_type
        )
        with get_connection(self.db_path) as conn:
            exists = conn.execute(
                "SELECT 1 FROM models WHERE provider_id = ? AND model_id = ? AND deleted_at IS NULL",
                (data.provider_id, data.model_id.strip()),
            ).fetchone()
            if exists:
                raise AppError(409, "model_already_exists", f"该 Provider 下已存在模型: {data.model_id}")
            if data.is_default_image:
                conn.execute("UPDATE models SET is_default_image = 0 WHERE is_default_image = 1")
            if data.is_default_video:
                conn.execute("UPDATE models SET is_default_video = 0 WHERE is_default_video = 1")
            conn.execute(
                "INSERT INTO models (id, provider_id, model_id, model_type, capabilities, capability_source, enabled, is_default_image, is_default_video, created_at, updated_at, deleted_at)"
                " VALUES (?, ?, ?, ?, ?, 'auto', ?, ?, ?, ?, ?, NULL)",
                (
                    model_id,
                    data.provider_id,
                    data.model_id.strip(),
                    data.model_type,
                    serialize(capabilities),
                    1 if data.enabled else 0,
                    1 if data.is_default_image else 0,
                    1 if data.is_default_video else 0,
                    now,
                    now,
                ),
            )
        return self.get_model(model_id)

    def update_model_capabilities(
        self, model_id: str, data: ModelCapabilityUpdate
    ) -> ModelOut:
        model = self.get_model(model_id)
        if data.source == "auto":
            provider = self.get_provider(model.provider_id)
            capabilities = resolve_default_capabilities(
                provider.preset_key, model.model_id, model.model_type
            )
            source = "auto"
        else:
            capabilities = validate_capabilities(
                model.model_type, data.capabilities
            )
            source = "manual"
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE models SET capabilities = ?, capability_source = ?, updated_at = ? WHERE id = ?",
                (serialize(capabilities), source, _now_iso(), model_id),
            )
        return self.get_model(model_id)

    def update_model(self, model_id: str, data: ModelUpdate) -> ModelOut:
        current = self.get_model(model_id)
        with get_connection(self.db_path) as conn:
            updates = []
            values = []
            if data.model_type is not None:
                updates.append("model_type = ?")
                values.append(data.model_type)
                if data.model_type in ("image", "video"):
                    _clear_defaults(conn, data.model_type)
            if data.enabled is not None:
                updates.append("enabled = ?")
                values.append(1 if data.enabled else 0)
            if data.is_default_image is True:
                conn.execute("UPDATE models SET is_default_image = 0 WHERE is_default_image = 1")
                updates.append("is_default_image = 1")
            elif data.is_default_image is False:
                updates.append("is_default_image = 0")
            if data.is_default_video is True:
                conn.execute("UPDATE models SET is_default_video = 0 WHERE is_default_video = 1")
                updates.append("is_default_video = 1")
            elif data.is_default_video is False:
                updates.append("is_default_video = 0")
            updates.append("updated_at = ?")
            values.append(_now_iso())
            values.append(model_id)
            conn.execute(f"UPDATE models SET {', '.join(updates)} WHERE id = ?", values)
        return self.get_model(model_id)

    def set_default(self, model_id: str, model_type: str) -> ModelOut:
        model = self.get_model(model_id)
        if model.model_type not in ("image", "video"):
            raise AppError(422, "default_not_supported", "仅 Image / Video 模型可设为默认")
        if model_type != model.model_type:
            raise AppError(422, "default_type_mismatch", "默认类型与模型类型不一致")
        with get_connection(self.db_path) as conn:
            _clear_defaults(conn, model.model_type)
            column = "is_default_image" if model.model_type == "image" else "is_default_video"
            conn.execute(
                f"UPDATE models SET {column} = 1, updated_at = ? WHERE id = ?",
                (_now_iso(), model_id),
            )
        return self.get_model(model_id)

    def soft_delete_model(self, model_id: str) -> None:
        self.get_model(model_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE models SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (_now_iso(), _now_iso(), model_id),
            )

    def upsert_discovered(self, provider_id: str, model_ids: list[str]) -> list[ModelOut]:
        """把拉取到的模型 ID 入库（已存在则跳过），按预设规则归类类型。"""
        provider = self.get_provider(provider_id)
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT preset_key FROM providers WHERE id = ?", (provider_id,)
            ).fetchone()
        preset_key = row["preset_key"] if row else None
        now = _now_iso()
        for mid in model_ids:
            model_type = classify_model(preset_key, mid)
            capabilities = resolve_default_capabilities(preset_key, mid, model_type)
            with get_connection(self.db_path) as conn:
                exists = conn.execute(
                    "SELECT 1 FROM models WHERE provider_id = ? AND model_id = ? AND deleted_at IS NULL",
                    (provider_id, mid),
                ).fetchone()
                if not exists:
                    conn.execute(
                        "INSERT INTO models (id, provider_id, model_id, model_type, capabilities, capability_source, enabled, is_default_image, is_default_video, created_at, updated_at, deleted_at)"
                        " VALUES (?, ?, ?, ?, ?, 'auto', 1, 0, 0, ?, ?, NULL)",
                        (
                            _new_id("model"),
                            provider_id,
                            mid,
                            model_type,
                            serialize(capabilities),
                            now,
                            now,
                        ),
                    )
        return self.list_models(provider_id=provider_id)


def _clear_defaults(conn, model_type: str) -> None:
    column = "is_default_image" if model_type == "image" else "is_default_video"
    conn.execute(f"UPDATE models SET {column} = 0 WHERE {column} = 1")


def _provider_out(row, secret_store: SecretStore) -> ProviderOut:
    key_ref = row["key_ref"]
    has_key = bool(key_ref and secret_store.get(key_ref))
    return ProviderOut(
        id=row["id"],
        name=row["name"],
        preset_key=row["preset_key"],
        api_base_url=row["api_base_url"],
        needs_key=bool(row["needs_key"]),
        enabled=bool(row["enabled"]),
        has_api_key=has_key,
        model_count=row["model_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _model_out(row, secret_store: SecretStore) -> ModelOut:
    key_ref = row["provider_key_ref"]
    has_key = bool(key_ref and secret_store.get(key_ref))
    return ModelOut(
        id=row["id"],
        provider_id=row["provider_id"],
        provider_name=row["provider_name"],
        provider_base_url=row["provider_base_url"],
        provider_needs_key=bool(row["provider_needs_key"]),
        provider_has_api_key=has_key,
        model_id=row["model_id"],
        model_type=row["model_type"],
        capabilities=parse(row["capabilities"]),
        capability_source=row["capability_source"],
        enabled=bool(row["enabled"]),
        is_default_image=bool(row["is_default_image"]),
        is_default_video=bool(row["is_default_video"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
