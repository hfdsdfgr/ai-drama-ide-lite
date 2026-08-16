"""智谱 CogVideoX 视频 Adapter：在 OpenAI Compat（chat/image）基础上补齐异步视频。"""

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
    "PROCESSING": "running",
    "SUCCESS": "completed",
    "FAIL": "failed",
}


class ZhipuVideoAdapter(OpenAICompatAdapter):
    name = "zhipu-video"
    protocol = "zhipu_video"
    provider_label = "智谱 CogVideoX"

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
            "quality": "speed",
            "with_audio": bool(request.extra.get("with_audio", False)),
            "watermark": False,
        }
        if request.duration:
            body["duration"] = 10 if request.duration > 10 else request.duration
        if capability == "image_to_video":
            body["image_url"] = image_to_data_url(request.images[0])

        url = ctx.base_url.rstrip("/") + "/videos/generations"
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

        task_id = payload.get("id") if isinstance(payload, dict) else None
        if not task_id:
            raise AdapterError(502, "video_submit_invalid", f"{ctx.provider_name} 未返回视频任务 ID")
        return task_id

    def poll(self, ctx: ProviderContext, job_id: str) -> JobStatus:
        url = f"{ctx.base_url.rstrip('/')}/async-result/{job_id}"
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

        raw_status = payload.get("task_status") if isinstance(payload, dict) else "FAIL"
        status = _STATUS_MAP.get(raw_status, "running")

        error = None
        result = None
        if status == "failed":
            error_obj = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(error_obj, dict):
                error = error_obj.get("message") or error_obj.get("code")
            error = error or f"任务状态：{raw_status}"
        elif status == "completed":
            video_result = payload.get("video_result") if isinstance(payload, dict) else None
            urls = [
                item["url"]
                for item in video_result
                if isinstance(item, dict) and item.get("url")
            ] if isinstance(video_result, list) else []
            result = GenerationResult(urls=urls, meta={"provider": ctx.provider_name, "task_status": raw_status})

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
