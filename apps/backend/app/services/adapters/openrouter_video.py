"""OpenRouter 视频 Adapter：在 OpenAI Compat（chat/image）基础上补齐异步视频。"""

import httpx

from app.services.adapters.base import (
    AdapterError,
    GenerationRequest,
    GenerationResult,
    JobStatus,
    ProviderContext,
)
from app.services.adapters.openai_compat import OpenAICompatAdapter, image_to_data_url

_STATUS_MAP = {
    "pending": "queued",
    "in_progress": "running",
    "processing": "running",
    "running": "running",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
    "expired": "failed",
}


class OpenRouterVideoAdapter(OpenAICompatAdapter):
    name = "openrouter-video"
    protocol = "openrouter_video"
    provider_label = "OpenRouter Video"

    def submit(
        self,
        ctx: ProviderContext,
        capability: str,
        request: GenerationRequest,
    ) -> str:
        if capability not in {"text_to_video", "image_to_video"}:
            raise AdapterError(
                422,
                "generation_not_supported",
                f"{ctx.provider_name}（{ctx.model_id}）暂不支持能力: {capability}",
            )
        if capability == "image_to_video" and not request.images:
            raise AdapterError(
                422,
                "image_required",
                f"{ctx.provider_name} 的 {ctx.model_id} 图生视频需要一张输入图片",
            )

        body: dict = {
            "model": ctx.model_id,
            "prompt": request.prompt,
            "duration": request.duration or 5,
            "generate_audio": False,
        }
        if request.aspect_ratio and ":" in request.aspect_ratio:
            body["aspect_ratio"] = request.aspect_ratio
        if capability == "image_to_video":
            body["frame_images"] = [
                {
                    "type": "image_url",
                    "image_url": {"url": image_to_data_url(request.images[0])},
                    "frame_type": "first_frame",
                }
            ]

        url = ctx.base_url.rstrip("/") + "/videos"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "video_submit_timeout", f"{ctx.provider_name} 创建视频任务超时") from exc
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                exc.response.status_code,
                "video_submit_failed",
                self._http_detail(exc.response.status_code, ctx.provider_name),
            ) from exc
        except Exception as exc:
            raise AdapterError(
                502, "video_submit_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置"
            ) from exc

        job_id = payload.get("id") if isinstance(payload, dict) else None
        if not job_id:
            raise AdapterError(502, "video_submit_invalid", f"{ctx.provider_name} 未返回视频任务 ID")
        return job_id

    def poll(self, ctx: ProviderContext, job_id: str) -> JobStatus:
        url = f"{ctx.base_url.rstrip('/')}/videos/{job_id}"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "video_poll_timeout", f"查询 {ctx.provider_name} 任务状态超时") from exc
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

        raw_status = payload.get("status") if isinstance(payload, dict) else "failed"
        status = _STATUS_MAP.get(raw_status, "running")

        error = None
        result = None
        if status in ("failed", "cancelled"):
            error = payload.get("error") if isinstance(payload, dict) else None
            error = error or f"任务状态：{raw_status}"
        elif status == "completed":
            unsigned_urls = payload.get("unsigned_urls") if isinstance(payload, dict) else None
            result_url = unsigned_urls[0] if isinstance(unsigned_urls, list) and unsigned_urls else None
            if result_url:
                result = GenerationResult(urls=[result_url], meta={"provider": ctx.provider_name})
            else:
                content_url = f"{ctx.base_url.rstrip('/')}/videos/{job_id}/content?index=0"
                result = GenerationResult(
                    urls=[content_url],
                    meta={"provider": ctx.provider_name},
                    download_headers=({"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}),
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
            return f"{provider_name} 接口或模型不存在（HTTP 404）：请检查 Base URL / 模型 ID"
        if status == 429:
            return f"{provider_name} 触发限流或额度不足（HTTP 429）"
        return f"{provider_name} 返回 HTTP {status}"
