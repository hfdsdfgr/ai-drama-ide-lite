"""OpenAI 兼容 Adapter：文本 chat + 图片生成/编辑（images/generations、images/edits）。

覆盖 openai / deepseek / siliconflow / openrouter / zhipu / ollama / 百炼兼容端点。
"""

import base64
import uuid
from pathlib import Path

import httpx

from app.services.adapters.base import (
    Adapter,
    AdapterError,
    GenerationRequest,
    GenerationResult,
    ProviderContext,
)


def _region_hint(base_url: str) -> str:
    if "dashscope" in base_url:
        return "；如为阿里云百炼，请确认 Key 所属站点与 Base URL 匹配（国内 dashscope.aliyuncs.com / 国际 dashscope-intl.aliyuncs.com）"
    return ""


def _persist_b64_image(b64: str, output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    name = f"gen_{uuid.uuid4().hex[:12]}.png"
    (output_dir / name).write_bytes(base64.b64decode(b64))
    return str(output_dir / name)


class OpenAICompatAdapter(Adapter):
    name = "openai-compatible"
    provider_label = "OpenAI 兼容"

    def chat(self, ctx: ProviderContext, messages: list[dict]) -> str:
        url = ctx.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        payload = {"model": ctx.model_id, "messages": messages, "temperature": 0.8}
        try:
            with httpx.Client(timeout=60) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(502, "llm_timeout", f"{ctx.provider_name} 文本生成超时，请重试") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = self._http_detail(status, ctx.base_url)
            raise AdapterError(502, "llm_failed", f"{ctx.provider_name} 文本生成失败：{detail}") from exc
        except Exception as exc:
            raise AdapterError(502, "llm_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(502, "llm_invalid_response", f"{ctx.provider_name} 返回格式异常") from exc

    def generate(
        self,
        ctx: ProviderContext,
        capability: str,
        request: GenerationRequest,
    ) -> GenerationResult:
        if capability == "text_to_image":
            return self._text_to_image(ctx, request)
        if capability in ("image_to_image", "reference_image"):
            return self._edit_image(ctx, request)
        raise AdapterError(
            422,
            "generation_not_supported",
            f"{ctx.provider_name}（{ctx.model_id}）暂不支持能力: {capability}",
        )

    def _text_to_image(
        self, ctx: ProviderContext, request: GenerationRequest
    ) -> GenerationResult:
        url = ctx.base_url.rstrip("/") + "/images/generations"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        payload = {
            "model": ctx.model_id,
            "prompt": request.prompt,
            "n": 1,
            "size": request.aspect_ratio or "1024x1024",
        }
        try:
            with httpx.Client(timeout=90) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(502, "image_timeout", f"{ctx.provider_name} 图片生成超时") from exc
        except httpx.HTTPStatusError as exc:
            detail = self._http_detail(exc.response.status_code, ctx.base_url)
            raise AdapterError(502, "image_failed", f"{ctx.provider_name} 图片生成失败：{detail}") from exc
        except Exception as exc:
            raise AdapterError(502, "image_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置") from exc
        return self._normalize_image_response(data, request.extra.get("output_dir"))

    def _edit_image(
        self, ctx: ProviderContext, request: GenerationRequest
    ) -> GenerationResult:
        if not request.images:
            raise AdapterError(
                422,
                "image_required",
                f"{ctx.provider_name} 的 {ctx.model_id} 需要一张输入图片（图生图/参考图）",
            )
        url = ctx.base_url.rstrip("/") + "/images/edits"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        files = [("image", (Path(request.images[0]).name, open(request.images[0], "rb"), "image/png"))]
        data = {
            "model": ctx.model_id,
            "prompt": request.prompt,
            "n": "1",
            "size": request.aspect_ratio or "1024x1024",
        }
        try:
            with httpx.Client(timeout=90) as client:
                response = client.post(url, headers=headers, files=files, data=data)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(502, "image_timeout", f"{ctx.provider_name} 图片编辑超时") from exc
        except httpx.HTTPStatusError as exc:
            detail = self._http_detail(exc.response.status_code, ctx.base_url)
            raise AdapterError(502, "image_failed", f"{ctx.provider_name} 图片编辑失败：{detail}") from exc
        except Exception as exc:
            raise AdapterError(502, "image_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置") from exc
        finally:
            for _, handle, _ in files:
                handle.close()
        return self._normalize_image_response(payload, request.extra.get("output_dir"))

    @staticmethod
    def _normalize_image_response(data: dict, output_dir: str | None) -> GenerationResult:
        items = data.get("data") if isinstance(data, dict) else None
        if not isinstance(items, list) or not items:
            raise AdapterError(502, "image_invalid_response", "提供商返回格式异常（缺少 data 列表）")
        urls: list[str] = []
        meta: dict = {}
        for item in items:
            if isinstance(item, dict):
                if item.get("url"):
                    urls.append(item["url"])
                elif item.get("b64_json") and output_dir:
                    urls.append(_persist_b64_image(item["b64_json"], Path(output_dir)))
                elif item.get("b64_json"):
                    meta["b64_present"] = True
        if not urls:
            raise AdapterError(502, "image_no_output", "提供商未返回可用的图片结果")
        return GenerationResult(urls=urls, meta=meta)

    @staticmethod
    def _http_detail(status: int, base_url: str) -> str:
        if status in (401, 403):
            return f"API Key 无效或没有权限（HTTP {status}）{_region_hint(base_url)}"
        if status == 404:
            return "接口或模型不存在（HTTP 404）：请检查 Base URL / 模型 ID"
        if status == 429:
            return "触发限流或额度不足（HTTP 429）"
        return f"提供商返回 HTTP {status}"
