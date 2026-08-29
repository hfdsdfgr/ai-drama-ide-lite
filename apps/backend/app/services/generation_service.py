"""Phase 10 — 持久化 Generation Job 服务。

创建 Job（queued）后由 JobWorker 执行；查询从 JobStore 读取并转换为原接口
输出结构（对外 API 兼容 Phase 5）。原内存注册表已废弃（重启即丢的问题解决）。

创建时做 fail-fast 校验（模型/Provider/Key/能力），不实际调用厂商 API。
"""

from pathlib import Path

from app.core.errors import AppError
from app.services.adapters.manager import ProviderManager
from app.services.capability_registry import resolve_max_reference_images
from app.services.job_store import JOB_TYPE_GENERATION, JobStore


class GenerationService:
    def __init__(
        self,
        store: JobStore,
        manager: ProviderManager,
        output_dir: Path,
    ) -> None:
        self.store = store
        self.manager = manager
        self.output_dir = Path(output_dir)

    def create_job(
        self,
        model_id: str,
        capability: str,
        prompt: str,
        aspect_ratio: str | None = None,
        duration: int | None = None,
        *,
        project_id: str | None = None,
        images: list[str] | None = None,
        reference_images: list[str] | None = None,
        negative_prompt: str = "",
        extra: dict | None = None,
    ) -> dict:
        # fail-fast：校验模型启用/Key/能力（不触发任何 API 调用或费用）
        self.manager.adapter_for(model_id, capability)
        model = self.manager.repo.get_model(model_id)
        extra = dict(extra or {})
        max_reference_images = resolve_max_reference_images(
            model.provider_preset_key, model.model_id
        )
        if max_reference_images is not None:
            extra["max_reference_images"] = max_reference_images
        record = self.store.create(
            JOB_TYPE_GENERATION,
            project_id or None,
            model_id=model_id,
            provider_id=model.provider_id,
            capability=capability,
            input_payload={
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "duration": duration,
                "images": images or [],
                "reference_images": reference_images or [],
                "negative_prompt": negative_prompt or "",
                "extra": extra,
            },
        )
        return self._public(record)

    def get_job(self, job_id: str) -> dict:
        try:
            record = self.store.get(job_id)
        except AppError as exc:
            if exc.code == "job_not_found":
                raise AppError(
                    404, "generation_job_not_found", f"生成任务不存在: {job_id}"
                ) from exc
            raise
        return self._public(record)

    def _public(self, record) -> dict:
        result = None
        if record.status == "completed" and record.result_payload:
            urls = record.result_payload.get("urls") or []
            result = {
                "urls": [self._to_public_url(url) for url in urls],
                "meta": record.result_payload.get("meta") or {},
            }
        return {
            "job_id": record.id,
            "model_id": record.model_id,
            "capability": record.capability,
            "status": record.status,
            "error": record.error or None,
            "result": result,
            "created_at": record.created_at,
        }

    def _to_public_url(self, url: str) -> str:
        path = Path(url)
        if path.is_absolute() and self.output_dir in path.parents:
            return f"/api/generation/files/{path.name}"
        return url
