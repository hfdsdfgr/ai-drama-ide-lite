"""火山方舟（Volcengine Ark）Adapter：豆包 LLM / Seedream 图像 / Seedance 异步视频。

调研文档：docs/investigations/volcengine-ark.md
- 文本：OpenAI 兼容 POST /chat/completions（复用 OpenAICompatAdapter）。
- 文生图：POST /images/generations（Seedream，size 需满足像素下限，1024x1024 会 400）。
- 视频：POST /contents/generations/tasks 异步提交 + GET /contents/generations/tasks/{id} 轮询。
"""

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
    "queued": "queued",
    "running": "running",
    "succeeded": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
    "expired": "failed",
}

# Seedream 总像素下限 3686400，宽高比范围 [1/16, 16]；
# 常见宽高比映射到满足约束的像素值（详见调研文档）。
_SEEDREAM_SIZES = {
    "1:1": "2048x2048",
    "2:3": "2048x3072",
    "3:4": "2304x3072",
    "4:3": "3072x2304",
    "16:9": "2560x1440",
    "9:16": "1440x2560",
}

# Seedance ratio 支持范围；不支持的比值（如 2:3）映射为 adaptive，避免 400。
_SUPPORTED_RATIOS = frozenset({"16:9", "4:3", "1:1", "3:4", "9:16", "21:9"})


class VolcengineAdapter(OpenAICompatAdapter):
    name = "volcengine"
    protocol = "volcengine"
    provider_label = "火山引擎（方舟）"

    def _text_to_image(
        self, ctx: ProviderContext, request: GenerationRequest
    ) -> GenerationResult:
        url = ctx.base_url.rstrip("/") + "/images/generations"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        payload = {
            "model": ctx.model_id,
            "prompt": request.prompt,
            "n": 1,
            "size": self._seedream_size(request.aspect_ratio),
            "response_format": "url",
            "watermark": False,
        }
        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(
                504, "image_timeout", f"{ctx.provider_name} 图片生成超时"
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = self._http_detail(exc.response.status_code, ctx.provider_name)
            raise AdapterError(
                exc.response.status_code,
                "image_failed",
                f"{ctx.provider_name} 图片生成失败：{detail}",
            ) from exc
        except Exception as exc:
            raise AdapterError(
                502, "image_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置"
            ) from exc
        return self._normalize_image_response(data, request.extra.get("output_dir"))

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
                f"{ctx.provider_name}（{ctx.model_id}）暂不支持能力 {capability}",
            )
        if capability == "image_to_video" and not request.images:
            raise AdapterError(
                422,
                "image_required",
                f"{ctx.provider_name} 的 {ctx.model_id} 图生视频需要一张输入图片",
            )

        content: list[dict] = []
        if capability == "image_to_video":
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image_to_data_url(request.images[0])},
                    "role": "first_frame",
                }
            )
        if request.prompt:
            content.append({"type": "text", "text": request.prompt})

        resolution = "720p"
        ratio = None
        ar = (request.aspect_ratio or "").strip().lower()
        if ar.endswith("p") and ar[:-1].isdigit():
            # 形如 720P / 1080P 的输入是分辨率而非宽高比
            resolution = ar
        else:
            ratio = self._seedance_ratio(ar)

        body: dict = {
            "model": ctx.model_id,
            "content": content,
            "resolution": resolution,
            "duration": request.duration or 5,
            "watermark": False,
        }
        # generate_audio 默认 true（火山方舟默认有声），本项目产品决定「视频默认无声」，
        # 因此必须显式传 false；仅当用户勾选带音频时才传 true。
        if "seedance-1-0" not in ctx.model_id.lower():
            body["generate_audio"] = bool(request.extra.get("with_audio", False))
        if ratio:
            body["ratio"] = ratio

        url = ctx.base_url.rstrip("/") + "/contents/generations/tasks"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(url, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(
                504, "video_submit_timeout", f"{ctx.provider_name} 创建视频任务超时"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                exc.response.status_code,
                "video_submit_failed",
                self._http_detail(exc.response.status_code, ctx.provider_name),
            ) from exc
        except Exception as exc:
            raise AdapterError(
                502,
                "video_submit_failed",
                f"无法连接 {ctx.provider_name}，请检查网络与配置",
            ) from exc

        task_id = payload.get("id") if isinstance(payload, dict) else None
        if not task_id:
            raise AdapterError(
                502, "video_submit_invalid", f"{ctx.provider_name} 未返回视频任务 ID"
            )
        return task_id

    def poll(self, ctx: ProviderContext, job_id: str) -> JobStatus:
        url = f"{ctx.base_url.rstrip('/')}/contents/generations/tasks/{job_id}"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        try:
            with httpx.Client(timeout=30) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(
                504, "video_poll_timeout", f"查询 {ctx.provider_name} 任务状态超时"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                exc.response.status_code,
                "video_poll_failed",
                self._http_detail(exc.response.status_code, ctx.provider_name),
            ) from exc
        except Exception as exc:
            raise AdapterError(
                502,
                "video_poll_failed",
                f"查询 {ctx.provider_name} 任务状态失败：{exc}",
            ) from exc

        raw_status = payload.get("status") if isinstance(payload, dict) else "failed"
        status = _STATUS_MAP.get(raw_status, "running")
        error = None
        result = None
        if status == "failed":
            error_obj = payload.get("error") if isinstance(payload, dict) else None
            message = (
                error_obj.get("message") if isinstance(error_obj, dict) else None
            )
            error = message or f"任务状态：{raw_status}"
        elif status == "completed":
            content = payload.get("content") if isinstance(payload, dict) else None
            url = content.get("video_url") if isinstance(content, dict) else None
            meta: dict = {"provider": ctx.provider_name, "status": raw_status}
            if isinstance(content, dict) and content.get("last_frame_url"):
                meta["last_frame_url"] = content["last_frame_url"]
            result = GenerationResult(urls=[url] if url else [], meta=meta)
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
    def _seedream_size(aspect_ratio: str | None) -> str:
        if not aspect_ratio:
            return "2048x2048"
        key = aspect_ratio.strip().lower()
        if key in _SEEDREAM_SIZES:
            return _SEEDREAM_SIZES[key]
        if "x" in key:
            parts = key.split("x")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return f"{parts[0]}x{parts[1]}"
        return "2048x2048"

    @staticmethod
    def _seedance_ratio(aspect_ratio: str) -> str | None:
        key = aspect_ratio.strip().lower()
        if not key:
            return None
        if key in _SUPPORTED_RATIOS:
            return key
        return "adaptive"

    @staticmethod
    def _http_detail(status: int, provider_name: str) -> str:
        if status in (401, 403):
            return f"{provider_name} API Key 无效或没有权限（HTTP {status}）"
        if status == 404:
            return (
                f"{provider_name} 接口或模型不存在（HTTP 404）：请检查 Base URL / 模型 ID"
            )
        if status == 429:
            return f"{provider_name} 触发限流或额度不足（HTTP 429）"
        return f"{provider_name} 返回 HTTP {status}"
