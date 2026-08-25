"""OpenAI 兼容 Adapter：文本 chat + 图片生成/编辑（images/generations、images/edits）。

覆盖 openai / deepseek / siliconflow / openrouter / zhipu / ollama / 百炼兼容端点。
"""

import base64
import json
import mimetypes
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


def _persist_b64_image(b64: str, output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    name = f"gen_{uuid.uuid4().hex[:12]}.png"
    (output_dir / name).write_bytes(base64.b64decode(b64))
    return str(output_dir / name)


def image_to_data_url(value: str) -> str:
    """把本地图片路径转成 data URL；http(s)/data 地址原样返回。"""
    if value.startswith(("http://", "https://", "data:")):
        return value
    path = Path(value)
    if not path.is_file():
        raise AdapterError(422, "image_file_not_found", f"输入图片不存在: {value}")
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


class OpenAICompatAdapter(Adapter):
    name = "openai-compatible"
    provider_label = "OpenAI 兼容"

    def chat(
        self,
        ctx: ProviderContext,
        messages: list[dict],
        temperature: float = 0.8,
        timeout: int = 60,
    ) -> str:
        """支持纯文本与多模态 content（[{type:text/image_url}] 数组）。
        图片以 data URL 传入时原样透传；HTTP 地址同样支持。
        """
        url = ctx.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        payload = {"model": ctx.model_id, "messages": messages, "temperature": temperature}
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "llm_timeout", f"{ctx.provider_name} 文本生成超时，请重试") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            detail = self._http_detail(status, ctx.base_url)
            raise AdapterError(status, "llm_failed", f"{ctx.provider_name} 文本生成失败：{detail}") from exc
        except Exception as exc:
            raise AdapterError(502, "llm_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置") from exc

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AdapterError(502, "llm_invalid_response", f"{ctx.provider_name} 返回格式异常") from exc

    def chat_stream(
        self,
        ctx: ProviderContext,
        messages: list[dict],
        temperature: float = 0.8,
        timeout: int = 180,
    ):
        """流式 chat：逐段产出内容增量（SSE 用），错误归一化与 chat 一致。"""
        url = ctx.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        payload = {
            "model": ctx.model_id,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line or not line.startswith("data:"):
                            continue
                        data = line[len("data:") :].strip()
                        if data == "[DONE]":
                            break
                        try:
                            obj = json.loads(data)
                        except ValueError:
                            continue
                        try:
                            delta = obj["choices"][0]["delta"].get("content")
                        except (KeyError, IndexError, TypeError, AttributeError):
                            continue
                        if delta:
                            yield delta
        except httpx.HTTPStatusError as exc:
            raise AdapterError(
                exc.response.status_code,
                "llm_stream_failed",
                f"{ctx.provider_name} 流式生成失败：{self._http_detail(exc.response.status_code, ctx.base_url)}",
            ) from exc
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "llm_stream_timeout", f"{ctx.provider_name} 流式生成超时") from exc
        except Exception as exc:
            raise AdapterError(
                502, "llm_stream_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置"
            ) from exc

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
        if capability == "text_to_speech":
            return self._text_to_speech(ctx, request)
        if capability == "speech_to_text":
            return self._speech_to_text(ctx, request)
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
            raise AdapterError(504, "image_timeout", f"{ctx.provider_name} 图片生成超时") from exc
        except httpx.HTTPStatusError as exc:
            detail = self._http_detail(exc.response.status_code, ctx.base_url)
            raise AdapterError(
                exc.response.status_code,
                "image_failed",
                f"{ctx.provider_name} 图片生成失败：{detail}",
            ) from exc
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
            raise AdapterError(504, "image_timeout", f"{ctx.provider_name} 图片编辑超时") from exc
        except httpx.HTTPStatusError as exc:
            detail = self._http_detail(exc.response.status_code, ctx.base_url)
            raise AdapterError(
                exc.response.status_code,
                "image_failed",
                f"{ctx.provider_name} 图片编辑失败：{detail}",
            ) from exc
        except Exception as exc:
            raise AdapterError(502, "image_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置") from exc
        finally:
            for _, handle, _ in files:
                handle.close()
        return self._normalize_image_response(payload, request.extra.get("output_dir"))

    def _text_to_speech(
        self, ctx: ProviderContext, request: GenerationRequest
    ) -> GenerationResult:
        """OpenAI 兼容 TTS：POST /audio/speech，返回二进制音频并落盘为本地文件。"""
        url = ctx.base_url.rstrip("/") + "/audio/speech"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        response_format = request.extra.get("response_format") or "wav"
        payload: dict = {
            "model": ctx.model_id,
            "input": request.prompt,
            "response_format": response_format,
        }
        voice = request.extra.get("voice")
        if voice:
            payload["voice"] = voice

        try:
            with httpx.Client(timeout=90) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                content = response.content
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "tts_timeout", f"{ctx.provider_name} 语音合成超时") from exc
        except httpx.HTTPStatusError as exc:
            detail = self._http_detail(exc.response.status_code, ctx.base_url)
            raise AdapterError(
                exc.response.status_code,
                "tts_failed",
                f"{ctx.provider_name} 语音合成失败：{detail}",
            ) from exc
        except Exception as exc:
            raise AdapterError(502, "tts_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置") from exc

        if not content:
            raise AdapterError(502, "tts_empty", f"{ctx.provider_name} 未返回音频内容")

        output_dir = Path(request.extra.get("output_dir") or ".")
        output_dir.mkdir(parents=True, exist_ok=True)
        ext = response_format if response_format in ("wav", "mp3", "flac", "aac", "opus", "pcm") else "wav"
        name = f"tts_{uuid.uuid4().hex[:12]}.{ext}"
        target = output_dir / name
        target.write_bytes(content)
        return GenerationResult(
            urls=[str(target)],
            meta={
                "format": response_format,
                "voice": voice or "",
                "bytes": len(content),
            },
        )

    def _speech_to_text(
        self, ctx: ProviderContext, request: GenerationRequest
    ) -> GenerationResult:
        """OpenAI 兼容语音转写：POST /audio/transcriptions（multipart file + model）。
        覆盖 OpenAI whisper / OpenRouter whisper / 百炼 qwen3-asr / 智谱 GLM-ASR。
        """
        audio_path = request.extra.get("audio_path") or (
            request.images[0] if request.images else ""
        )
        if not audio_path:
            raise AdapterError(422, "audio_required", "语音转写需要音频文件")
        path = Path(audio_path)
        if not path.is_file():
            raise AdapterError(
                422, "audio_file_not_found", f"音频文件不存在：{audio_path}"
            )
        url = ctx.base_url.rstrip("/") + "/audio/transcriptions"
        headers = {"Authorization": f"Bearer {ctx.api_key}"} if ctx.api_key else {}
        try:
            with open(path, "rb") as fh:
                files = {"file": (path.name, fh, "application/octet-stream")}
                data = {"model": ctx.model_id, "response_format": "json"}
                with httpx.Client(timeout=120) as client:
                    response = client.post(
                        url, headers=headers, files=files, data=data
                    )
                    response.raise_for_status()
                    payload = response.json()
        except httpx.TimeoutException as exc:
            raise AdapterError(504, "stt_timeout", f"{ctx.provider_name} 语音转写超时") from exc
        except httpx.HTTPStatusError as exc:
            detail = self._http_detail(exc.response.status_code, ctx.base_url)
            raise AdapterError(
                exc.response.status_code,
                "stt_failed",
                f"{ctx.provider_name} 语音转写失败：{detail}",
            ) from exc
        except Exception as exc:
            raise AdapterError(
                502, "stt_failed", f"无法连接 {ctx.provider_name}，请检查网络与配置"
            ) from exc

        text = (payload.get("text") if isinstance(payload, dict) else None) or ""
        if not text.strip():
            raise AdapterError(502, "stt_no_output", f"{ctx.provider_name} 未返回转写文本")
        return GenerationResult(urls=[], meta={"text": text.strip()})

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
            return f"API Key 无效或没有权限（HTTP {status}）"
        if status == 404:
            return "接口或模型不存在（HTTP 404）：请检查 Base URL / 模型 ID"
        if status == 429:
            return "触发限流或额度不足（HTTP 429）"
        return f"提供商返回 HTTP {status}"
