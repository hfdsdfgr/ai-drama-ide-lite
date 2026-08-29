"""阿里云百炼（DashScope）原生 Adapter：视频异步任务 + 图片同步生成。

参考官方文档（wan 文生视频 API reference）：
- 创建任务 POST {base}/api/v1/services/aigc/video-generation/video-synthesis
  （图生视频为 image2video/video-synthesis），头 X-DashScope-Async: enable
- 轮询 GET {base}/api/v1/tasks/{task_id}
状态：PENDING -> RUNNING -> SUCCEEDED / FAILED / CANCELED / UNKNOWN
"""

import base64
import io
import math
import mimetypes
import uuid
from pathlib import Path

import httpx

from app.services.adapters.base import (
    Adapter,
    AdapterError,
    GenerationRequest,
    GenerationResult,
    JobStatus,
    ProviderContext,
)
from app.services.adapters.openai_compat import OpenAICompatAdapter

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


class DashScopeAdapter(OpenAICompatAdapter):
    name = "dashscope"
    protocol = "dashscope"
    provider_label = "阿里云百炼"

    def generate(
        self,
        ctx: ProviderContext,
        capability: str,
        request: GenerationRequest,
    ) -> GenerationResult:
        if capability == "text_to_speech":
            return self._text_to_speech(ctx, request)
        if capability == "speech_to_text":
            # 百炼兼容模式提供 OpenAI 兼容 /audio/transcriptions
            return OpenAICompatAdapter._speech_to_text(self, ctx, request)
        if capability not in {
            "text_to_image",
            "image_to_image",
            "reference_image",
            "character_reference",
        }:
            raise AdapterError(
                422,
                "generation_not_supported",
                f"{ctx.provider_name}（{ctx.model_id}）暂不支持能力: {capability}",
            )
        if capability != "text_to_image" and not request.images:
            raise AdapterError(
                422,
                "image_required",
                f"{ctx.provider_name} 的 {ctx.model_id} 需要一张输入图片",
            )

        image_inputs = request.images
        max_reference_images = request.extra.get("max_reference_images")
        try:
            max_refs = int(max_reference_images) if max_reference_images is not None else 3
        except (TypeError, ValueError):
            max_refs = 3
        if capability != "text_to_image" and len(image_inputs) > max_refs:
            image_inputs = [self._build_reference_sheet(image_inputs)]

        content: list[dict] = []
        if image_inputs:
            content.extend(
                {"image": self._image_input(image)} for image in image_inputs
            )
        content.append({"text": request.prompt})

        body: dict = {
            "model": ctx.model_id,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            },
            "parameters": {
                "size": self._image_size(request.aspect_ratio),
                "n": 1,
                "prompt_extend": True,
                "watermark": False,
            },
        }
        if request.negative_prompt:
            body["parameters"]["negative_prompt"] = request.negative_prompt

        base = _native_base(ctx.base_url)
        path = "/api/v1/services/aigc/multimodal-generation/generation"
        headers = {
            "Authorization": f"Bearer {ctx.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=240) as client:
                response = client.post(base + path, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "image_timeout", f"{ctx.provider_name} 图片生成超时") from exc
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                exc.response.status_code,
                "image_failed",
                f"{ctx.provider_name} 图片生成失败：{self._http_detail(exc.response.status_code, ctx.provider_name)}",
            ) from exc
        except Exception as exc:
            raise AdapterError(
                502, "image_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置"
            ) from exc

        try:
            content_items = payload["output"]["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(
                502, "image_invalid_response", f"{ctx.provider_name} 图片返回格式异常"
            ) from exc
        urls = [
            item["image"]
            for item in content_items
            if isinstance(item, dict) and item.get("image")
        ]
        if not urls:
            raise AdapterError(502, "image_no_output", f"{ctx.provider_name} 未返回可用图片结果")
        return GenerationResult(
            urls=urls,
            meta={"provider": ctx.provider_name, "model": ctx.model_id},
        )

    def _text_to_speech(
        self, ctx: ProviderContext, request: GenerationRequest
    ) -> GenerationResult:
        base = _native_base(ctx.base_url)
        path = "/api/v1/services/aigc/multimodal-generation/generation"
        voice = request.extra.get("voice") or "Cherry"
        body = {
            "model": ctx.model_id,
            "input": {
                "text": request.prompt,
                "voice": voice,
                "language_type": request.extra.get("language_type") or "Chinese",
            },
        }
        headers = {
            "Authorization": f"Bearer {ctx.api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=90) as client:
                response = client.post(base + path, headers=headers, json=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "tts_timeout", f"{ctx.provider_name} 语音合成超时") from exc
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                exc.response.status_code,
                "tts_failed",
                f"{ctx.provider_name} 语音合成失败：{self._http_detail(exc.response.status_code, ctx.provider_name)}",
            ) from exc
        except Exception as exc:
            raise AdapterError(502, "tts_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置") from exc

        output = payload.get("output") if isinstance(payload, dict) else None
        audio = output.get("audio") if isinstance(output, dict) else None
        url = audio.get("url") if isinstance(audio, dict) else None
        data_b64 = audio.get("data") if isinstance(audio, dict) else None
        if not url and not data_b64:
            raise AdapterError(502, "tts_no_output", f"{ctx.provider_name} 未返回音频结果")

        output_dir = Path(request.extra.get("output_dir") or ".")
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"tts_{uuid.uuid4().hex[:12]}.wav"
        if data_b64:
            target.write_bytes(base64.b64decode(data_b64))
        else:
            try:
                with httpx.Client(timeout=60, follow_redirects=True) as client:
                    download = client.get(url)
                    download.raise_for_status()
                    target.write_bytes(download.content)
            except Exception as exc:
                raise AdapterError(
                    502, "tts_download_failed", f"{ctx.provider_name} 音频下载失败"
                ) from exc
        return GenerationResult(urls=[str(target)], meta={"voice": voice})

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
            path = "/api/v1/services/aigc/video-generation/video-synthesis"
        else:
            raise AdapterError(
                422,
                "generation_not_supported",
                f"{ctx.provider_name}（{ctx.model_id}）暂不支持能力: {capability}",
            )

        if capability == "image_to_video":
            body: dict = {
                "model": ctx.model_id,
                "input": {
                    "prompt": request.prompt,
                    "img_url": self._image_input(request.images[0]),
                },
                "parameters": {
                    "resolution": request.aspect_ratio or "720P",
                    "duration": request.duration or 5,
                    "prompt_extend": True,
                    "watermark": False,
                },
            }
        else:
            body = {
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
    def _image_size(value: str | None) -> str:
        return (value or "1024*1024").replace("x", "*").replace("×", "*")

    @staticmethod
    def _image_input(value: str) -> str:
        if value.startswith(("http://", "https://", "data:")):
            return value
        path = Path(value)
        if not path.is_file():
            raise AdapterError(422, "image_file_not_found", f"输入图片不存在: {value}")
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"

    @staticmethod
    def _build_reference_sheet(images: list[str]) -> str:
        """把超出模型声明上限的本地参考图合并为一张 PNG contact sheet。

        具体阈值由 Job 根据 max_reference_images 动态传入；Adapter 不再写死所有
        模型都只能接收 3 张输入图。
        """
        try:
            from PIL import Image
        except ImportError as exc:
            raise AdapterError(
                500,
                "reference_sheet_dependency_missing",
                "无法合并参考图：图像处理组件 Pillow 未安装",
            ) from exc

        paths: list[Path] = []
        for value in images:
            if value.startswith(("http://", "https://", "data:")):
                raise AdapterError(
                    422,
                    "reference_sheet_local_only",
                    "百炼多参考图合并仅支持本地图片文件",
                )
            path = Path(value)
            if not path.is_file():
                raise AdapterError(
                    422,
                    "image_file_not_found",
                    f"输入图片不存在: {value}",
                )
            paths.append(path)

        count = len(paths)
        columns = math.ceil(math.sqrt(count))
        rows = math.ceil(count / columns)
        max_side = 2048
        cell = max(1, max_side // max(columns, rows))
        padding = max(4, cell // 32)
        canvas_width = columns * cell
        canvas_height = rows * cell
        sheet = Image.new("RGBA", (canvas_width, canvas_height), (255, 255, 255, 255))

        for index, path in enumerate(paths):
            with Image.open(path) as image:
                image = image.convert("RGBA")
                target = cell - padding * 2
                resample = getattr(Image, "Resampling", Image).LANCZOS
                image.thumbnail((target, target), resample)
                column = index % columns
                row = index // columns
                x = column * cell + (cell - image.width) // 2
                y = row * cell + (cell - image.height) // 2
                sheet.alpha_composite(image, (x, y))

        buffer = io.BytesIO()
        sheet.convert("RGB").save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _http_detail(status: int, provider_name: str) -> str:
        if status in (401, 403):
            return f"{provider_name} API Key 无效或没有权限（HTTP {status}）"
        if status == 404:
            return f"{provider_name} 接口或模型不存在（HTTP 404）：请检查模型与地域"
        if status == 429:
            return f"{provider_name} 触发限流或额度不足（HTTP 429）"
        return f"{provider_name} 返回 HTTP {status}"
