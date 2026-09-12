"""Adapter 基础类型与统一数据契约（Phase 5）。"""

from dataclasses import dataclass, field

from app.core.errors import AppError

DEFAULT_PROTOCOL = "openai_compat"
SUPPORTED_PROTOCOLS = frozenset(
    {
        "openai_compat",
        "dashscope",
        "sora",
        "openrouter_video",
        "zhipu_video",
        "siliconflow_video",
        "volcengine",
        "elevenlabs",
        "syncso",
    }
)


def select_parameter(
    key: str,
    label: str,
    value_type: str,
    values: list,
    default,
    help_text: str,
) -> dict:
    return {
        "key": key,
        "label": label,
        "control": "select",
        "value_type": value_type,
        "default": default,
        "options": [
            {
                "value": value,
                "label": f"{value} 秒" if key == "duration" else str(value),
            }
            for value in values
        ],
        "required": True,
        "help": help_text,
    }


class AdapterError(AppError):
    """适配层错误：message 已带厂商与模型上下文，可直接展示给用户。"""


@dataclass
class ProviderContext:
    """一次调用所需的 Provider 上下文（密钥只存活于调用期间，不落盘）。"""

    provider_id: str
    provider_name: str
    preset_key: str | None
    base_url: str
    api_key: str | None
    model_id: str
    protocol: str = DEFAULT_PROTOCOL


@dataclass
class GenerationRequest:
    capability: str
    prompt: str
    model_id: str = ""
    images: list[str] = field(default_factory=list)
    reference_images: list[str] = field(default_factory=list)
    aspect_ratio: str | None = None
    duration: int | None = None
    negative_prompt: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class GenerationResult:
    urls: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    download_headers: dict = field(default_factory=dict)
    alignment: dict | None = None


@dataclass
class JobStatus:
    job_id: str
    status: str  # queued | running | completed | failed | cancelled
    progress: float | None = None
    error: str | None = None
    result: GenerationResult | None = None


class Adapter:
    """能力级适配器基类：每个厂商实现自己支持的调用形态。

    同步调用实现 generate；异步（任务制）实现 submit / poll / fetch_result。
    """

    name: str = "base"
    provider_label: str = "未知厂商"
    protocol: str = DEFAULT_PROTOCOL

    def parameter_schema(
        self,
        ctx: ProviderContext,
        capability: str,
    ) -> list[dict]:
        """Return only parameters verified for this adapter/model combination."""
        return []

    def validate_parameters(
        self,
        ctx: ProviderContext,
        capability: str,
        values: dict,
    ) -> dict:
        fields = self.parameter_schema(ctx, capability)
        allowed = {field["key"]: field for field in fields}
        unknown = sorted(set(values) - set(allowed))
        if unknown:
            raise AdapterError(
                422,
                "unknown_generation_parameter",
                f"模型不支持参数: {', '.join(unknown)}",
            )
        result = {}
        for key, field in allowed.items():
            value = values.get(key, field.get("default"))
            if value is None:
                if field.get("required"):
                    raise AdapterError(422, "generation_parameter_required", f"缺少参数: {key}")
                continue
            value_type = field["value_type"]
            valid_type = (
                isinstance(value, bool)
                if value_type == "boolean"
                else isinstance(value, int) and not isinstance(value, bool)
                if value_type == "integer"
                else isinstance(value, (int, float)) and not isinstance(value, bool)
                if value_type == "number"
                else isinstance(value, str)
            )
            if not valid_type:
                raise AdapterError(422, "generation_parameter_type", f"参数 {key} 类型错误")
            options = field.get("options", [])
            if options and value not in {option["value"] for option in options}:
                raise AdapterError(422, "generation_parameter_option", f"参数 {key} 取值不受支持")
            if "minimum" in field and value < field["minimum"]:
                raise AdapterError(422, "generation_parameter_range", f"参数 {key} 小于最小值")
            if "maximum" in field and value > field["maximum"]:
                raise AdapterError(422, "generation_parameter_range", f"参数 {key} 超过最大值")
            result[key] = value
        return result

    def chat(
        self,
        ctx: ProviderContext,
        messages: list[dict],
    ) -> str:
        raise AdapterError(
            422,
            "chat_not_supported",
            f"{self.provider_label}（{ctx.provider_name}）不支持文本生成",
        )

    def generate(
        self,
        ctx: ProviderContext,
        capability: str,
        request: GenerationRequest,
    ) -> GenerationResult:
        raise AdapterError(
            422,
            "generation_not_supported",
            f"{self.provider_label}（{ctx.provider_name}）暂不支持能力: {capability}",
        )

    def submit(
        self,
        ctx: ProviderContext,
        capability: str,
        request: GenerationRequest,
    ) -> str:
        raise AdapterError(
            422,
            "async_not_supported",
            f"{self.provider_label}（{ctx.provider_name}）不支持异步任务",
        )

    def poll(self, ctx: ProviderContext, job_id: str) -> JobStatus:
        raise AdapterError(
            422,
            "async_not_supported",
            f"{self.provider_label}（{ctx.provider_name}）不支持任务轮询",
        )

    def fetch_result(self, ctx: ProviderContext, job_id: str) -> GenerationResult:
        raise AdapterError(
            422,
            "async_not_supported",
            f"{self.provider_label}（{ctx.provider_name}）不支持结果获取",
        )
