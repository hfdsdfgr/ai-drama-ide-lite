"""能力注册表（Phase 4 — Capability Engine）。

能力检测采用「规则驱动」而非实时实测（参考 models.dev / LiteLLM 的目录思路）：
- 内置规则：模型名片段 → 能力集（保守推断，宁缺毋滥）；
- 手动覆盖：用户对单个模型增删能力，覆盖自动推断结果；
- 不确定的能力不默认开启，留给用户手动开启（Open WebUI 手动 allowlist 兜底思路）。
"""

import json

from app.core.errors import AppError
from app.services.model_catalog import (
    get_builtin_capabilities,
    get_builtin_max_reference_images,
)

CAPABILITY_LABELS: dict[str, str] = {
    "text_to_image": "文生图",
    "image_to_image": "图生图",
    "reference_image": "参考图",
    "character_reference": "角色参考",
    "text_to_video": "文生视频",
    "image_to_video": "图生视频",
    "video_to_video": "视频生视频",
    "first_frame": "首帧控制",
    "last_frame": "尾帧控制",
    "first_last_frame": "首尾帧控制",
    "video_audio": "视频自带音效",
    "video_dialogue": "原生对白/台词",
    "text_to_speech": "文本转语音",
    "speech_to_text": "语音转写",
    "vision": "图像理解",
    "tts_timestamps": "语音时间戳",
    "voice_clone": "声音复刻",
    "voice_design": "声音设计",
    "lip_sync": "对口型",
}

IMAGE_CAPABILITIES = frozenset(
    {"text_to_image", "image_to_image", "reference_image", "character_reference"}
)
VIDEO_CAPABILITIES = frozenset(
    {
        "text_to_video",
        "image_to_video",
        "video_to_video",
        "first_frame",
        "last_frame",
        "first_last_frame",
        "video_audio",
        "video_dialogue",
    }
)

AUDIO_CAPABILITIES = frozenset(
    {"text_to_speech", "speech_to_text", "tts_timestamps", "voice_clone", "voice_design"}
)
VISION_CAPABILITIES = frozenset({"vision"})

# 图片模型“最多可接收参考图数量”的兜底规则。
# 优先使用 vendor_models.json 中的精确字段；这里用于服务商返回的新模型或未收录模型。
_MAX_REFERENCE_IMAGES_RULES: tuple[tuple[str, int], ...] = (
    ("gpt-image", 16),
    ("qwen-image", 3),
    ("wan2.7-image", 9),
)

# (模型名片段, 能力集)：先匹配先得；model_type 已先过滤。
# 规则基于厂商公开文档调研（见 docs/investigations/vendor-capability-catalog.md），
# 只写确定支持的，不确定的交给保守默认值与手动覆盖。
_IMAGE_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("gpt-image", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("dall-e", frozenset({"text_to_image"})),
    ("qwen-image", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("wanx", frozenset({"text_to_image"})),
    ("wan", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("kontext", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("flux", frozenset({"text_to_image"})),
    ("stable-diffusion", frozenset({"text_to_image", "image_to_image"})),
    ("sdxl", frozenset({"text_to_image", "image_to_image"})),
    ("kolors", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("cogview", frozenset({"text_to_image"})),
)

_VIDEO_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("kling", frozenset({"text_to_video", "image_to_video"})),
    ("veo", frozenset({"text_to_video", "image_to_video"})),
    ("pika", frozenset({"text_to_video", "image_to_video"})),
    ("sora", frozenset({"text_to_video", "image_to_video", "video_to_video"})),
    ("cogvideox", frozenset({"text_to_video", "image_to_video"})),
    ("happyhorse", frozenset({"text_to_video", "image_to_video", "video_audio"})),
    ("seedance", frozenset({"text_to_video", "image_to_video", "video_audio"})),
    ("wan2.6-t2v", frozenset({"text_to_video", "video_audio"})),
    ("wan2.6-i2v", frozenset({"image_to_video", "video_audio"})),
    ("wan2.5-t2v", frozenset({"text_to_video", "video_audio"})),
    ("wan2.5-i2v", frozenset({"image_to_video", "video_audio"})),
    ("wan2.1-t2v", frozenset({"text_to_video"})),
    ("wan2.2-t2v", frozenset({"text_to_video"})),
)


def resolve_default_capabilities(
    preset_key: str | None, model_id: str, model_type: str
) -> list[str]:
    """模型能力默认值：优先内置目录（调研数据），未收录时按规则推断。"""
    if preset_key:
        catalog_caps = get_builtin_capabilities(preset_key, model_id)
        if catalog_caps is not None:
            return sorted(set(catalog_caps))
    return infer_capabilities(preset_key, model_id, model_type)


def resolve_max_reference_images(preset_key: str | None, model_id: str) -> int | None:
    """返回模型最多可接收的参考图数量。

    优先读取本地调研目录 vendor_models.json；若该模型未收录，则按名称片段
    保守推断。None 表示没有明确的参考图数量声明。
    """
    if preset_key:
        catalog_value = get_builtin_max_reference_images(preset_key, model_id)
        if catalog_value is not None:
            return catalog_value
    mid = model_id.lower()
    for fragment, value in _MAX_REFERENCE_IMAGES_RULES:
        if fragment in mid:
            return value
    return None


def infer_capabilities(preset_key: str | None, model_id: str, model_type: str) -> list[str]:
    """按规则推断能力；未命中时使用保守默认值。"""
    mid = model_id.lower()
    if model_type == "llm":
        return []
    if model_type == "audio":
        if "asr" in mid or "whisper" in mid or "speech-to-text" in mid:
            return ["speech_to_text"]
        return ["text_to_speech"]
    rules = _VIDEO_RULES if model_type == "video" else _IMAGE_RULES
    for fragment, caps in rules:
        if fragment in mid:
            return sorted(caps)
    if model_type == "video":
        return ["text_to_video"]
    return ["text_to_image"]


def validate_capabilities(model_type: str, capabilities: list[str]) -> list[str]:
    """校验能力集：必须已知、且属于该模型类型允许的范围。"""
    allowed = (
        IMAGE_CAPABILITIES
        if model_type == "image"
        else VIDEO_CAPABILITIES
        if model_type == "video"
        else AUDIO_CAPABILITIES
        if model_type == "audio"
        else VISION_CAPABILITIES
    )
    unknown = [c for c in capabilities if c not in CAPABILITY_LABELS]
    if unknown:
        raise AppError(422, "unknown_capability", f"未知能力: {', '.join(unknown)}")
    forbidden = [c for c in capabilities if c not in allowed]
    if forbidden:
        raise AppError(
            422,
            "capability_type_mismatch",
            f"该模型类型不支持能力: {', '.join(forbidden)}",
        )
    return sorted(set(capabilities))


def serialize(capabilities: list[str]) -> str:
    return json.dumps(sorted(set(capabilities)), ensure_ascii=False)


def parse(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [c for c in data if isinstance(c, str)]
    except (ValueError, TypeError):
        return []
