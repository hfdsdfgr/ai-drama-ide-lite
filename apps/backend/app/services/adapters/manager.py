"""ProviderManager：按模型 + 能力解析 Adapter，业务层只调这里。"""

from app.core.errors import AppError
from app.schemas.provider import ModelOut
from app.services.adapters.base import (
    Adapter,
    GenerationRequest,
    GenerationResult,
    ProviderContext,
)
from app.services.adapters.dashscope import DashScopeAdapter
from app.services.adapters.openai_compat import OpenAICompatAdapter
from app.services.capability_registry import VIDEO_CAPABILITIES
from app.services.provider_repo import ProviderRepository


class ProviderManager:
    def __init__(self, repo: ProviderRepository) -> None:
        self.repo = repo
        self._openai = OpenAICompatAdapter()
        self._dashscope = DashScopeAdapter()

    # ---------- 校验与上下文 ----------

    def _check_model(self, model: ModelOut, capability: str | None) -> None:
        if not model.enabled:
            raise AppError(422, "model_disabled", "该模型已禁用，请先在设置中启用")
        if not model.provider_enabled:
            raise AppError(422, "provider_disabled", "该模型的 Provider 已禁用")
        if model.provider_needs_key and not model.provider_has_api_key:
            raise AppError(422, "api_key_required", "该模型的 Provider 未配置 API Key")
        if capability and capability not in model.capabilities:
            raise AppError(
                422,
                "capability_not_supported",
                f"模型 {model.model_id} 不支持能力: {capability}",
            )

    def _ctx(self, model: ModelOut) -> ProviderContext:
        api_key = (
            self.repo.secret_store.get(f"provider:{model.provider_id}")
            if model.provider_needs_key
            else None
        )
        return ProviderContext(
            provider_id=model.provider_id,
            provider_name=model.provider_name,
            preset_key=model.provider_preset_key,
            base_url=model.provider_base_url,
            api_key=api_key,
            model_id=model.model_id,
        )

    def _adapter(self, model: ModelOut, capability: str) -> Adapter:
        if capability in VIDEO_CAPABILITIES and model.provider_preset_key in (
            "bailian",
            "bailian-intl",
        ):
            return self._dashscope
        return self._openai

    # ---------- 对外：文本 ----------

    def chat(
        self, model_id: str, messages: list[dict], temperature: float = 0.8
    ) -> str:
        model = self.repo.get_model(model_id)
        if model.model_type != "llm":
            raise AppError(422, "not_llm_model", "请选择文本模型（LLM）")
        self._check_model(model, None)
        return self._openai.chat(self._ctx(model), messages, temperature)

    # ---------- 对外：生成 ----------

    def adapter_for(self, model_id: str, capability: str) -> Adapter:
        """校验并返回适配器（生成前检查）。"""
        model = self.repo.get_model(model_id)
        self._check_model(model, capability)
        return self._adapter(model, capability)

    def ctx_for(self, model_id: str) -> ProviderContext:
        return self._ctx(self.repo.get_model(model_id))

    def generate(
        self,
        model_id: str,
        capability: str,
        request: GenerationRequest,
    ) -> GenerationResult:
        adapter = self.adapter_for(model_id, capability)
        return adapter.generate(self.ctx_for(model_id), capability, request)

    def start_job(
        self,
        model_id: str,
        capability: str,
        request: GenerationRequest,
    ) -> dict:
        """启动一次生成：异步厂商提交任务；同步厂商直接生成并返回结果。"""
        adapter = self.adapter_for(model_id, capability)
        ctx = self.ctx_for(model_id)
        if isinstance(adapter, DashScopeAdapter):
            task_id = adapter.submit(ctx, capability, request)
            return {
                "mode": "async",
                "adapter": adapter,
                "ctx": ctx,
                "task_id": task_id,
                "result": None,
            }
        result = adapter.generate(ctx, capability, request)
        return {
            "mode": "sync",
            "adapter": adapter,
            "ctx": ctx,
            "task_id": None,
            "result": result,
        }
