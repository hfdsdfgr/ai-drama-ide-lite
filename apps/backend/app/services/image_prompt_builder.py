"""Phase 13 M1 - Image Prompt Builder.

这个模块只负责把“资产生图 / 分镜生图”的业务输入，规范化为一个稳定的图片生成提示词与
像素规格。它不调用任何 AI API，也不接触数据库，便于单独测试。
"""

import re
from dataclasses import dataclass, field

from app.schemas.script import Scene, Shot
from app.services.asset_service import (
    ASPECT_RATIO_OPTIONS,
    ASSET_DEFAULT_SPECS,
    resolve_image_spec,
)

SHOT_ASPECT_RATIO = "16:9"

DEFAULT_NEGATIVE_PROMPT = (
    "lowres, bad anatomy, bad hands, extra fingers, deformed, blurry, "
    "watermark, text, logo, extra limbs, cropped, jpeg artifacts"
)

CHARACTER_CONSISTENCY = (
    "character reference sheet, front view, side view, back view, "
    "same character, consistent character design, consistent outfit, "
    "solo character, no props, no other characters"
)

# 角色设定图必须是三视图。放在 prompt 最前面，避免参考描述里的
# 「front view / full body」等单视图短语把模型带偏成只画正面。
CHARACTER_THREE_VIEW = (
    "Character reference sheet, three views of the same character: "
    "front view, side view, back view, full body, neutral standing pose, "
    "plain background, consistent face, consistent hairstyle, consistent outfit"
)

LOCATION_CONSISTENCY = (
    "cinematic establishing shot, consistent environment, "
    "clear spatial layout, no people, no characters, no specific props"
)

PROP_CONSISTENCY = (
    "product reference shot, empty background, no characters, no scene, "
    "consistent material and design"
)

ASSET_NO_TEXT = "no text, no words, no letters, no watermark"

SHOT_CONSISTENCY = (
    "cinematic still frame, storyboard frame, no text, no subtitles"
)

# 分镜图里的角色一致性约束：与资产卡不同，分镜图可以有多个角色和道具，
# 因此不能复用「solo character, no props」；核心是保持与角色参考图相同的
# 面部、发型、服装，避免模型因剧情描述（痛苦/扭曲等）把脸画崩。
SHOT_CHARACTER_CONSISTENCY = (
    "keep the exact same face, hairstyle and costume as the character references, "
    "same character identity, do not change facial features, age or skin"
)

_VIEW_PHRASE_RE = re.compile(
    r"\b(front|side|back) view\b|\bfull body\b", re.IGNORECASE
)


@dataclass
class ImagePromptPlan:
    """生图前的纯数据契约。"""

    prompt: str
    negative_prompt: str
    aspect_ratio: str
    width: int
    height: int
    source_refs: list[dict] = field(default_factory=list)


def _ratio_spec(aspect_ratio: str | None, fallback: str) -> dict:
    """把比例字符串解析为具体像素规格，未指定时回退到 fallback。"""
    target = aspect_ratio or fallback
    for option in ASPECT_RATIO_OPTIONS:
        if option["value"] == target:
            return {
                "aspect_ratio": option["value"],
                "width": option["width"],
                "height": option["height"],
            }
    raise ValueError(f"未知图片比例: {aspect_ratio}")


def _asset_spec(asset_type: str, aspect_ratio: str | None) -> dict:
    if asset_type not in ASSET_DEFAULT_SPECS:
        raise ValueError(f"未知资产类型: {asset_type}")
    if aspect_ratio:
        return _ratio_spec(aspect_ratio, ASSET_DEFAULT_SPECS[asset_type]["aspect_ratio"])
    default = ASSET_DEFAULT_SPECS[asset_type]
    return {
        "aspect_ratio": default["aspect_ratio"],
        "width": default["width"],
        "height": default["height"],
    }


def _join(parts: list[str]) -> str:
    return ", ".join(part.strip() for part in parts if part and part.strip())


def _append_if_missing(base: str, fragment: str) -> str:
    if not fragment or not fragment.strip():
        return base
    if fragment.strip().lower() in base.lower():
        return base
    return _join([base, fragment.strip()])


def _asset_fields_prompt(asset_type: str, fields: dict | None) -> str:
    fields = fields or {}
    if asset_type == "character":
        parts = [
            fields.get("identity", ""),
            fields.get("appearance", ""),
            fields.get("hairstyle", ""),
            fields.get("costume", ""),
            fields.get("build", ""),
            fields.get("marks", ""),
            fields.get("personality", ""),
            fields.get("style", ""),
        ]
        return _join(parts)
    if asset_type == "location":
        parts = [
            fields.get("description", ""),
            fields.get("environment", ""),
            fields.get("time", ""),
            fields.get("lighting", ""),
            fields.get("style", ""),
        ]
        return _join(parts)
    parts = [
        fields.get("description", ""),
        fields.get("material", ""),
        fields.get("reference", ""),
        fields.get("style", ""),
    ]
    return _join(parts)


def _asset_consistency(asset_type: str) -> str:
    return {
        "character": CHARACTER_CONSISTENCY,
        "location": LOCATION_CONSISTENCY,
        "prop": PROP_CONSISTENCY,
    }.get(asset_type, "")


def _strip_view_phrases(text: str) -> str:
    """去掉参考描述里写死的单视图/全身短语，避免与三视图模板冲突。"""
    cleaned = _VIEW_PHRASE_RE.sub("", text)
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    return ", ".join(parts)


def build_asset_image_prompt(
    asset_type: str,
    reference_prompt: str = "",
    fields: dict | None = None,
    *,
    aspect_ratio: str | None = None,
    art_style: str | None = None,
    source_refs: list[dict] | None = None,
) -> ImagePromptPlan:
    """组装资产卡生图提示词。

    `reference_prompt` 是 Phase 8 生成的固定人设描述，必须优先复用，不能覆盖。
    只有它为空时，才从结构化字段兜底生成一段基础描述。
    """
    fields = fields or {}
    base = reference_prompt.strip() or _asset_fields_prompt(asset_type, fields)
    if not base:
        base = _asset_consistency(asset_type)

    if asset_type == "character":
        base = _join([CHARACTER_THREE_VIEW, _strip_view_phrases(base)])

    style = art_style or fields.get("art_style") or ""
    base = _append_if_missing(base, style)
    base = _append_if_missing(base, _asset_consistency(asset_type))
    base = _append_if_missing(base, ASSET_NO_TEXT)

    spec = _asset_spec(asset_type, aspect_ratio or fields.get("aspect_ratio") or None)
    return ImagePromptPlan(
        prompt=base,
        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
        aspect_ratio=spec["aspect_ratio"],
        width=spec["width"],
        height=spec["height"],
        source_refs=list(source_refs or []),
    )


def _shot_base_prompt(shot: Shot) -> str:
    if shot.prompt and shot.prompt.strip():
        return shot.prompt.strip()
    return _join(
        [
            shot.shot_type,
            shot.camera,
            shot.characters,
            shot.action,
            shot.lighting,
        ]
    )


def _scene_context_prompt(scene: Scene | None) -> str:
    if scene is None:
        return ""
    return _join(
        [
            scene.slugline,
            scene.action,
        ]
    )


def build_shot_image_prompt(
    shot: Shot,
    scene: Scene | None = None,
    *,
    asset_references: list[dict] | None = None,
    aspect_ratio: str | None = None,
    art_style: str | None = None,
    source_refs: list[dict] | None = None,
) -> ImagePromptPlan:
    """组装分镜生图提示词。

    分镜的 `prompt` 是用户 / AI 已写好的视觉提示词，优先保留；其余字段作为补充。
    资产参考图描述会作为一致性锚点拼入提示词。
    """
    base = _shot_base_prompt(shot)
    scene_context = _scene_context_prompt(scene)
    if scene_context:
        base = _append_if_missing(base, scene_context)

    asset_references = asset_references or []
    reference_lines: list[str] = []
    for ref in asset_references:
        label = ref.get("asset_type") or ref.get("type") or "asset"
        name = ref.get("name", "")
        reference_prompt = ref.get("reference_prompt", "")
        if reference_prompt:
            reference_lines.append(
                f"{label} reference ({name}): {reference_prompt}".strip(": ")
            )
        elif name:
            reference_lines.append(f"{label} reference: {name}")
    if reference_lines:
        base = _join([base, *reference_lines])

    if any(
        ref.get("asset_type") == "character"
        for ref in asset_references
    ):
        base = _append_if_missing(base, SHOT_CHARACTER_CONSISTENCY)
    base = _append_if_missing(base, SHOT_CONSISTENCY)
    if art_style:
        base = _append_if_missing(base, art_style)

    spec = _ratio_spec(aspect_ratio, SHOT_ASPECT_RATIO)
    refs = list(source_refs or [])
    if not refs:
        refs = [{"type": "shot", "id": shot.id, "relation": "image_generated_from_shot"}]
    return ImagePromptPlan(
        prompt=base,
        negative_prompt=DEFAULT_NEGATIVE_PROMPT,
        aspect_ratio=spec["aspect_ratio"],
        width=spec["width"],
        height=spec["height"],
        source_refs=refs,
    )
