"""可解释的确定性模型推荐；不调用模型、不自动发起生成。"""

from app.schemas.provider import ModelOut
from app.services.capability_registry import CAPABILITY_LABELS

_FAST_MARKERS = ("fast", "flash", "turbo", "mini", "lite", "schnell")
_QUALITY_MARKERS = ("pro", "max", "plus", "ultra", "hd")
_PRODUCTION_CAPABILITIES = {
    "image": {"image_to_image", "reference_image", "character_reference"},
    "video": {"video_audio", "video_dialogue", "first_last_frame"},
    "llm": {"vision"},
}


def recommend_models(
    models: list[ModelOut],
    *,
    model_type: str,
    required_capabilities: list[str],
    preference: str,
) -> list[dict]:
    """返回已按推荐顺序排列的候选模型与可见理由。"""
    required = set(required_capabilities)
    candidates = []
    for model in models:
        capabilities = set(model.capabilities)
        if model.model_type != model_type or not required.issubset(capabilities):
            continue

        score = 0
        reasons = []
        if required:
            labels = [CAPABILITY_LABELS.get(item, item) for item in sorted(required)]
            reasons.append(f"支持所需能力：{'、'.join(labels)}")

        is_default = (
            model_type == "image" and model.is_default_image
        ) or (model_type == "video" and model.is_default_video)
        if is_default:
            score += 40 if preference == "balanced" else 8
            reasons.append("你已将它设为该类型的默认模型")

        if model.capability_source == "manual":
            score += 2
            reasons.append("能力由你手动确认")

        name = model.model_id.lower()
        fast_marker = next((item for item in _FAST_MARKERS if item in name), None)
        quality_marker = next((item for item in _QUALITY_MARKERS if item in name), None)
        production_caps = capabilities & _PRODUCTION_CAPABILITIES.get(model_type, set())

        if preference == "quality":
            score += len(production_caps) * 4
            if production_caps:
                score += 4
                reasons.append("具备更多一致性或成片能力")
            if quality_marker:
                score += 12
                reasons.append(f"模型名称含质量档标识“{quality_marker}”")
        elif preference in {"speed", "cost"} and fast_marker:
            score += 12
            goal = "速度" if preference == "speed" else "经济型"
            reasons.append(f"模型名称含{goal}档标识“{fast_marker}”")
        elif preference == "balanced":
            score += len(production_caps) * 2

        if not reasons:
            reasons.append("满足当前任务要求；暂无更多可比较的模型元数据")
        candidates.append({"model": model, "score": score, "reasons": reasons})

    return sorted(
        candidates,
        key=lambda item: (
            -item["score"],
            item["model"].model_id.lower(),
            item["model"].id,
        ),
    )
