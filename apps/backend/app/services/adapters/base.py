"""Adapter 基础类型与统一数据契约（Phase 5）。"""

from dataclasses import dataclass, field

from app.core.errors import AppError


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


@dataclass
class GenerationRequest:
    capability: str
    prompt: str
    model_id: str = ""
    images: list[str] = field(default_factory=list)
    aspect_ratio: str | None = None
    duration: int | None = None
    negative_prompt: str = ""
    extra: dict = field(default_factory=dict)


@dataclass
class GenerationResult:
    urls: list[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


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
