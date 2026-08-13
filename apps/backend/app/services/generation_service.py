"""Generation Job 内存注册表（Phase 5）。

真实调用厂商 API：同步厂商（OpenAI 兼容图片）立即完成；异步厂商（百炼视频）
提交后由轮询接口实时查询厂商状态。状态全部来自厂商真实返回，不做假进度。
Phase 10 再引入持久化 Job 系统（本注册表重启即清空）。
"""

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.services.adapters.base import GenerationRequest, GenerationResult
from app.services.adapters.manager import ProviderManager


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class GenerationService:
    def __init__(self, manager: ProviderManager, output_dir: Path) -> None:
        self.manager = manager
        self.output_dir = output_dir
        self._jobs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create_job(
        self,
        model_id: str,
        capability: str,
        prompt: str,
        aspect_ratio: str | None = None,
        duration: int | None = None,
        images: list[str] | None = None,
    ) -> dict:
        request = GenerationRequest(
            capability=capability,
            prompt=prompt,
            model_id=model_id,
            aspect_ratio=aspect_ratio,
            duration=duration,
            images=images or [],
            extra={"output_dir": str(self.output_dir)},
        )
        started = self.manager.start_job(model_id, capability, request)
        job_id = f"gen_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        job = {
            "job_id": job_id,
            "model_id": model_id,
            "capability": capability,
            "status": "completed" if started["mode"] == "sync" else "queued",
            "task_id": started.get("task_id"),
            "error": None,
            "result": started.get("result"),
            "created_at": now,
        }
        with self._lock:
            self._jobs[job_id] = job
        return self._public(job)

    def get_job(self, job_id: str) -> dict:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise AppError(404, "generation_job_not_found", f"生成任务不存在: {job_id}")
        if job["task_id"] and job["status"] in ("queued", "running"):
            adapter = self.manager.adapter_for(job["model_id"], job["capability"])
            status = adapter.poll(
                self.manager.ctx_for(job["model_id"]), job["task_id"]
            )
            job["status"] = status.status
            job["error"] = status.error
            if status.result is not None:
                job["result"] = status.result
        return self._public(job)

    def _public(self, job: dict) -> dict:
        result = job["result"]
        public_result = None
        if isinstance(result, GenerationResult):
            public_result = {
                "urls": [
                    self._to_public_url(u) for u in result.urls
                ],
                "meta": result.meta,
            }
        elif isinstance(result, dict):
            public_result = result
        return {
            "job_id": job["job_id"],
            "model_id": job["model_id"],
            "capability": job["capability"],
            "status": job["status"],
            "error": job["error"],
            "result": public_result,
            "created_at": job["created_at"],
        }

    def _to_public_url(self, url: str) -> str:
        """本地生成文件 -> 可访问 URL；远程 URL 原样返回。"""
        path = Path(url)
        if path.is_absolute() and self.output_dir in path.parents:
            return f"/api/generation/files/{path.name}"
        return url
