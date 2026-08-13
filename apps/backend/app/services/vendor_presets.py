"""内置厂商预设目录：Base URL / 是否需要 Key / 模型类型归类规则。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class VendorPreset:
    key: str
    name: str
    base_url: str
    needs_key: bool
    # (模型 ID 片段, 类型) 有序规则，先匹配先得；未匹配默认 llm
    type_rules: tuple[tuple[str, str], ...] = ()


PRESETS: dict[str, VendorPreset] = {
    "openai": VendorPreset(
        "openai",
        "OpenAI",
        "https://api.openai.com/v1",
        True,
        (("gpt-image", "image"), ("dall-e", "image"), ("gpt", "llm"), ("o1", "llm"), ("o3", "llm")),
    ),
    "openrouter": VendorPreset(
        "openrouter",
        "OpenRouter",
        "https://openrouter.ai/api/v1",
        True,
        (
            ("kling", "video"),
            ("veo", "video"),
            ("pika", "video"),
            ("flux", "image"),
            ("dall-e", "image"),
            ("gpt-image", "image"),
            ("stable-diffusion", "image"),
            ("sdxl", "image"),
        ),
    ),
    "deepseek": VendorPreset(
        "deepseek",
        "DeepSeek",
        "https://api.deepseek.com/v1",
        True,
    ),
    "bailian": VendorPreset(
        "bailian",
        "阿里云百炼",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
        True,
        (
            ("qwen-image", "image"),
            ("wanx", "image"),
            ("wan2.1-t2v", "video"),
            ("wan2.2-t2v", "video"),
            ("wan-video", "video"),
            ("qwen-video", "video"),
            ("qwen", "llm"),
            ("text-embedding", "llm"),
        ),
    ),
    "zhipu": VendorPreset(
        "zhipu",
        "智谱",
        "https://open.bigmodel.cn/api/paas/v4",
        True,
        (("cogvideox", "video"), ("cogview", "image"), ("glm", "llm"), ("embedding", "llm")),
    ),
    "siliconflow": VendorPreset(
        "siliconflow",
        "硅基流动",
        "https://api.siliconflow.cn/v1",
        True,
        (
            ("wan2.2-t2v", "video"),
            ("wan2.1-t2v", "video"),
            ("wan-video", "video"),
            ("flux", "image"),
            ("stable-diffusion", "image"),
            ("kolors", "image"),
            ("qwen-image", "image"),
            ("gpt-image", "image"),
            ("deepseek", "llm"),
            ("qwen", "llm"),
            ("glm", "llm"),
            ("doubao", "llm"),
            ("embedding", "llm"),
        ),
    ),
    "ollama": VendorPreset(
        "ollama",
        "Ollama（本地）",
        "http://127.0.0.1:11434/v1",
        False,
    ),
}


def get_preset(key: str | None) -> VendorPreset | None:
    if not key:
        return None
    return PRESETS.get(key)


def classify_model(preset_key: str | None, model_id: str) -> str:
    """按预设规则归类模型类型；未命中默认 llm（Phase 4 能力检测修正）。"""
    preset = get_preset(preset_key)
    mid = model_id.lower()
    for fragment, model_type in (preset.type_rules if preset else ()):
        if fragment in mid:
            return model_type
    return "llm"
