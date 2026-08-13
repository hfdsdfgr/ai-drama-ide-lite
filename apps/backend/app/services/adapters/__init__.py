"""Provider Adapter 系统（Phase 5）。

业务层只按「能力」调用 ProviderManager，具体厂商差异隔离在 Adapter 内。
"""

from app.services.adapters.base import (
    Adapter,
    AdapterError,
    GenerationRequest,
    GenerationResult,
    JobStatus,
    ProviderContext,
)
from app.services.adapters.dashscope import DashScopeAdapter
from app.services.adapters.manager import ProviderManager
from app.services.adapters.openai_compat import OpenAICompatAdapter

__all__ = [
    "Adapter",
    "AdapterError",
    "GenerationRequest",
    "GenerationResult",
    "JobStatus",
    "ProviderContext",
    "OpenAICompatAdapter",
    "DashScopeAdapter",
    "ProviderManager",
]
