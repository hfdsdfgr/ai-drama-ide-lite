"""能力注册表（Phase 4 — Capability Engine）。

能力检测采用「规则驱动」而非实时实测（参考 models.dev / LiteLLM 的目录思路）：
- 内置规则：模型名片段 → 能力集（保守推断，宁缺毋滥）；
- 手动覆盖：用户对单个模型增删能力，覆盖自动推断结果；
- 不确定的能力不默认开启，留给用户手动开启（Open WebUI 手动 allowlist 兜底思路）。
"""

import json

from app.core.errors import AppError

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
    }
)

# (模型名片段, 能力集)：先匹配先得；model_type 已先过滤。
# 规则只写确定支持的厂商模型，不确定的交给默认值与手动覆盖。
_IMAGE_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("gpt-image", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("dall-e", frozenset({"text_to_image"})),
    ("qwen-image", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("wanx", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("wan", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("flux", frozenset({"text_to_image", "image_to_image", "reference_image"})),
    ("stable-diffusion", frozenset({"text_to_image", "image_to_image"})),
    ("sdxl", frozenset({"text_to_image", "image_to_image"})),
    ("kolors", frozenset({"text_to_image", "image_to_image"})),
    ("cogview", frozenset({"text_to_image"})),
)

_VIDEO_RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("kling", frozenset({"text_to_video", "image_to_video"})),
    ("veo", frozenset({"text_to_video", "image_to_video"})),
    ("pika", frozenset({"text_to_video", "image_to_video"})),
    ("sora", frozenset({"text_to_video", "image_to_video"})),
    ("cogvideox", frozenset({"text_to_video", "image_to_video"})),
    ("happyhorse", frozenset({"text_to_video"})),
    ("wan2.1-t2v", frozenset({"text_to_video"})),
    ("wan2.2-t2v", frozenset({"text_to_video"})),
)


def infer_capabilities(preset_key: str | None, model_id: str, model_type: str) -> list[str]:
    """按规则推断能力；未命中时使用保守默认值。"""
    if model_type == "llm":
        return []
    mid = model_id.lower()
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
        else frozenset()
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
