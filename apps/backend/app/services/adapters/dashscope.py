"""阿里云百炼（DashScope）原生 Adapter：异步任务制视频生成。

参考官方文档（wan 文生视频 API reference）：
- 创建任务 POST {base}/api/v1/services/aigc/video-generation/video-synthesis
  （图生视频为 image2video/video-synthesis），头 X-DashScope-Async: enable
- 轮询 GET {base}/api/v1/tasks/{task_id}
状态：PENDING -> RUNNING -> SUCCEEDED / FAILED / CANCELED / UNKNOWN
"""

import httpx

from app.services.adapters.base import (
    Adapter,
    AdapterError,
    GenerationRequest,
    GenerationResult,
    JobStatus,
    ProviderContext,
)

_STATUS_MAP = {
    "PENDING": "queued",
    "RUNNING": "running",
    "SUCCEEDED": "completed",
    "FAILED": "failed",
    "CANCELED": "cancelled",
    "UNKNOWN": "failed",
}


def _native_base(compatible_base: str) -> str:
    """兼容模式 Base URL -> 原生 API 根地址。"""
    marker = "/compatible-mode/v1"
    if marker in compatible_base:
        return compatible_base.split(marker)[0].rstrip("/")
    return compatible_base.rstrip("/")


class DashScopeAdapter(Adapter):
    name = "dashscope"
    provider_label = "阿里云百炼"

    def submit(
        self,
        ctx: ProviderContext,
        capability: str,
        request: GenerationRequest,
    ) -> str:
        base = _native_base(ctx.base_url)
        if capability == "text_to_video":
            path = "/api/v1/services/aigc/video-generation/video-synthesis"
        elif capability == "image_to_video":
            if not request.images:
                raise AdapterError(
                    422,
                    "image_required",
                    f"{ctx.provider_name} 的 {ctx.model_id} 图生视频需要一张输入图片 URL",
                )
            path = "/api/v1/services/aigc/image2video/video-synthesis"
        else:
            raise AdapterError(
                422,
                "generation_not_supported",
                f"{ctx.provider_name}（{ctx.model_id}）暂不支持能力: {capability}",
            )

        body: dict = {
            "model": ctx.model_id,
            "input": {"prompt": request.prompt},
            "parameters": {
                "size": request.aspect_ratio or "832*480",
                "prompt_extend": True,
                "watermark": False,
            },
        }
        if request.duration:
            body["parameters"]["duration"] = request.duration
        if request.negative_prompt:
            body["input"]["negative_prompt"] = request.negative_prompt
        if capability == "image_to_video":
            body["input"]["img_url"] = request.images[0]

        headers = {
            "Authorization": f"Bearer {ctx.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(base + path, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                exc.response.status_code,
                "video_submit_failed",
                self._http_detail(exc.response.status_code, ctx.provider_name),
            ) from exc
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "video_submit_timeout", f"{ctx.provider_name} 创建视频任务超时") from exc
        except Exception as exc:
            raise AdapterError(
                502, "video_submit_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置"
            ) from exc

        output = payload.get("output") if isinstance(payload, dict) else None
        task_id = output.get("task_id") if isinstance(output, dict) else None
        if not task_id:
            raise AdapterError(502, "video_submit_invalid", f"{ctx.provider_name} 未返回任务 ID")
        return task_id

    def poll(self, ctx: ProviderContext, job_id: str) -> JobStatus:
        base = _native_base(ctx.base_url)
        headers = {"Authorization": f"Bearer {ctx.api_key}"}
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(f"{base}/api/v1/tasks/{job_id}", headers=headers)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                exc.response.status_code,
                "video_poll_failed",
                self._http_detail(exc.response.status_code, ctx.provider_name),
            ) from exc
        except Exception as exc:
            raise AdapterError(
                502, "video_poll_failed", f"查询 {ctx.provider_name} 任务状态失败：{exc}"
            ) from exc

        output = payload.get("output") if isinstance(payload, dict) else {}
        task_status = output.get("task_status") if isinstance(output, dict) else "UNKNOWN"
        status = _STATUS_MAP.get(task_status, "running")
        error = None
        result = None
        if status == "failed":
            error = output.get("message") or f"任务状态：{task_status}"
        elif status == "completed":
            url = output.get("video_url") if isinstance(output, dict) else None
            result = GenerationResult(
                urls=[url] if url else [],
                meta={"task_status": task_status},
            )
        return JobStatus(job_id=job_id, status=status, error=error, result=result)

    def fetch_result(self, ctx: ProviderContext, job_id: str) -> GenerationResult:
        status = self.poll(ctx, job_id)
        if status.status != "completed" or not status.result:
            raise AdapterError(
                502,
                "video_result_not_ready",
                f"{ctx.provider_name} 任务尚未完成（{status.status}）",
            )
        return status.result

    @staticmethod
    def _http_detail(status: int, provider_name: str) -> str:
        if status in (401, 403):
            return f"{provider_name} API Key 无效或没有权限（HTTP {status}）"
        if status == 404:
            return f"{provider_name} 接口或模型不存在（HTTP 404）：请检查模型与地域"
        if status == 429:
            return f"{provider_name} 触发限流或额度不足（HTTP 429）"
        return f"{provider_name} 返回 HTTP {status}"
