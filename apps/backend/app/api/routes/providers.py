"""Provider / Model endpoints（Phase 3 — AI Provider 基础系统）。"""

from fastapi import APIRouter, Request, Response

from app.core.errors import AppError
from app.schemas.provider import (
    BulkModelsRequest,
    BuiltinModelOut,
    DefaultRequest,
    ModelCreate,
    ModelCapabilityUpdate,
    ModelOut,
    ModelUpdate,
    PresetOut,
    ProviderCreate,
    ProviderOut,
    ProviderTestOut,
    ProviderUpdate,
)
from app.services.api_tester import run_provider_test
from app.services.model_catalog import get_builtin_models
from app.services.model_discovery import fetch_model_ids
from app.services.provider_repo import ProviderRepository
from app.services.vendor_presets import PRESETS, get_preset

router = APIRouter(prefix="/api/providers", tags=["providers"])
models_router = APIRouter(prefix="/api/models", tags=["models"])


def _repo(request: Request) -> ProviderRepository:
    settings = request.app.state.settings
    return ProviderRepository(settings.db_path, request.app.state.secret_store)


@router.get("/presets", response_model=list[PresetOut])
def list_presets() -> list[PresetOut]:
    return [
        PresetOut(
            key=p.key,
            name=p.name,
            base_url=p.base_url,
            needs_key=p.needs_key,
            discoverable=p.discoverable,
        )
        for p in PRESETS.values()
    ]


@router.get("/presets/{preset_key}/models", response_model=list[BuiltinModelOut])
def list_preset_models(preset_key: str) -> list[BuiltinModelOut]:
    if preset_key not in PRESETS:
        raise AppError(422, "unknown_preset", f"未知厂商预设: {preset_key}")
    return [
        BuiltinModelOut(
            id=item["id"],
            type=item["type"],
            capabilities=item.get("capabilities", []),
        )
        for item in get_builtin_models(preset_key)
    ]


@router.get("", response_model=list[ProviderOut])
def list_providers(request: Request) -> list[ProviderOut]:
    return _repo(request).list_providers()


@router.post("", response_model=ProviderOut, status_code=201)
def create_provider(payload: ProviderCreate, request: Request) -> ProviderOut:
    return _repo(request).create_provider(payload)


@router.get("/{provider_id}", response_model=ProviderOut)
def get_provider(provider_id: str, request: Request) -> ProviderOut:
    return _repo(request).get_provider(provider_id)


@router.put("/{provider_id}", response_model=ProviderOut)
def update_provider(
    provider_id: str, payload: ProviderUpdate, request: Request
) -> ProviderOut:
    return _repo(request).update_provider(provider_id, payload)


@router.delete("/{provider_id}", status_code=204)
def delete_provider(provider_id: str, request: Request) -> Response:
    _repo(request).soft_delete_provider(provider_id)
    return Response(status_code=204)


@router.post("/{provider_id}/discover-models", response_model=list[ModelOut])
def discover_models(provider_id: str, request: Request) -> list[ModelOut]:
    repo = _repo(request)
    provider = repo.get_provider(provider_id)
    preset = get_preset(provider.preset_key) if provider.preset_key else None
    if preset and not preset.discoverable:
        raise AppError(
            422,
            "discovery_unsupported",
            "该厂商不支持自动拉取模型列表，请手动添加模型（填模型 ID 即可）",
        )
    if provider.needs_key and not provider.has_api_key:
        raise AppError(422, "api_key_required", "请先为该 Provider 配置 API Key")
    api_key = (
        repo.secret_store.get(f"provider:{provider_id}") if provider.needs_key else None
    )
    model_ids = fetch_model_ids(provider.api_base_url, api_key)
    return repo.upsert_discovered(provider_id, model_ids)


@router.post("/{provider_id}/test", response_model=ProviderTestOut)
def test_provider(provider_id: str, request: Request) -> ProviderTestOut:
    """L1/L2 连接测试：可达性、鉴权、模型可用性（零成本）。"""
    repo = _repo(request)
    provider = repo.get_provider(provider_id)
    preset = get_preset(provider.preset_key) if provider.preset_key else None
    discoverable = preset.discoverable if preset else True
    api_key = (
        repo.secret_store.get(f"provider:{provider_id}")
        if provider.needs_key
        else None
    )
    models = repo.list_models(provider_id=provider_id, enabled_only=True)
    return run_provider_test(
        provider_id=provider_id,
        base_url=provider.api_base_url,
        api_key=api_key,
        needs_key=provider.needs_key,
        has_key=provider.has_api_key,
        discoverable=discoverable,
        models=models,
    )


@router.post("/{provider_id}/models/bulk", response_model=list[ModelOut], status_code=201)
def bulk_add_models(
    provider_id: str, payload: BulkModelsRequest, request: Request
) -> list[ModelOut]:
    repo = _repo(request)
    provider = repo.get_provider(provider_id)
    builtin_map = {
        item["id"]: item["type"]
        for item in get_builtin_models(provider.preset_key or "")
    }
    created: list[ModelOut] = []
    for model_id in payload.model_ids:
        model_type = builtin_map.get(model_id, "llm")
        try:
            created.append(
                repo.create_model(
                    ModelCreate(
                        provider_id=provider_id,
                        model_id=model_id.strip(),
                        model_type=model_type,
                    )
                )
            )
        except AppError as exc:
            if exc.code != "model_already_exists":
                raise
            continue
        except Exception:
            raise
    return created


@models_router.get("", response_model=list[ModelOut])
def list_models(
    request: Request,
    provider_id: str | None = None,
    model_type: str | None = None,
    enabled_only: bool = False,
    capability: str | None = None,
) -> list[ModelOut]:
    return _repo(request).list_models(
        provider_id=provider_id,
        model_type=model_type,
        enabled_only=enabled_only,
        capability=capability,
    )


@models_router.post("", response_model=ModelOut, status_code=201)
def create_model(payload: ModelCreate, request: Request) -> ModelOut:
    return _repo(request).create_model(payload)


@models_router.get("/{model_id}", response_model=ModelOut)
def get_model(model_id: str, request: Request) -> ModelOut:
    return _repo(request).get_model(model_id)


@models_router.put("/{model_id}", response_model=ModelOut)
def update_model(
    model_id: str, payload: ModelUpdate, request: Request
) -> ModelOut:
    return _repo(request).update_model(model_id, payload)


@models_router.put("/{model_id}/capabilities", response_model=ModelOut)
def update_model_capabilities(
    model_id: str, payload: ModelCapabilityUpdate, request: Request
) -> ModelOut:
    """能力手动覆盖或重置为自动推断。"""
    return _repo(request).update_model_capabilities(model_id, payload)


@models_router.delete("/{model_id}", status_code=204)
def delete_model(model_id: str, request: Request) -> Response:
    _repo(request).soft_delete_model(model_id)
    return Response(status_code=204)


@models_router.post("/{model_id}/default", response_model=ModelOut)
def set_default(
    model_id: str, payload: DefaultRequest, request: Request
) -> ModelOut:
    model_type = payload.model_type or _repo(request).get_model(model_id).model_type
    return _repo(request).set_default(model_id, model_type)
