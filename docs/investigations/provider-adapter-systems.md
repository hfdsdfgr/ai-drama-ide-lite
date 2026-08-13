# 调研：Provider Adapter 系统设计依据（Phase 5）

> 调研时间：2026-08-13。规则 75（Research Before Every Step）。
> 目的：确定「统一调用不同 AI API」的适配层结构，避免业务代码与具体厂商耦合。

## 结论摘要

1. **统一接口 + 每厂商一个 Adapter 是主流**：
   - LiteLLM：所有请求从 OpenAI 格式转入厂商原生格式，响应再归一化回统一格式；
     每个 Provider 实现一组契约方法（请求转换 / 响应转换 / 错误归一化）。
   - Vercel AI SDK 7：统一 `generateImage()` / `generateVideo()` 等能力级接口，
     各 Provider 插件补充厂商特有元数据——即「业务按能力调用，不按模型 if/else」。
   - SillyTavern：中心管理器 + 每个 Provider 一个类实现具体 API 逻辑（30+ 厂商）。
2. **生图/生视频的异步范式是「提交 → 轮询 → 取结果」**（fal.ai / Replicate）：
   提交任务得到 job id → 轮询状态（IN_QUEUE / IN_PROGRESS / COMPLETED / FAILED）
   → 完成后取资源（图片 images[]、视频 video.url，多为签名 URL）。
   同步接口（如 OpenAI 图片直接返回）可包装为「立即完成」的同一接口。
3. **错误必须带 Provider 上下文且可操作**（SillyTavern 教训，Phase 4 已采用）：
   适配层统一把厂商错误转成带厂商名/模型名/HTTP 状态/建议的 AppError。
4. **Webhook 属于可选优化**：多数图片/视频 API 只提供轮询；本轮只做轮询，
   Webhook 留到 Phase 10 Job 系统再按需扩展。

## 参考来源

- LiteLLM Provider 抽象层（请求/响应转换 + 错误归一化）：https://zread.ai/BerriAI/litellm/8-provider-abstraction-layer
- LiteLLM Provider Integrations（统一适配层架构）：https://deepwiki.com/BerriAI/litellm/2.4-provider-integrations
- LiteLLM 注册新 Provider 文档（Transform request / adapt response）：https://docs.litellm.ai/docs/provider_registration/
- Vercel AI SDK 7（能力级统一接口：image / video / speech）：https://vercel.com/changelog/ai-sdk-7
- fal.ai 队列推理（提交→轮询→取结果，状态枚举）：https://raw.githubusercontent.com/api-evangelist/fal-ai/refs/heads/main/openapi/fal-ai-queue-api-openapi.yml
- Replicate → fal 迁移（HTTP + queue 模式对比）：https://fal.ai/docs/documentation/development/migrate-from-replicate
- SillyTavern AI 集成架构（Provider 抽象层 / 集中管理器 + 厂商类）：https://deepwiki.com/SillyTavern/SillyTavern/3-server-architecture

## 对 Phase 5 的影响

- 适配层接口按「能力」组织：`LLMAdapter` / `ImageAdapter` / `VideoAdapter`，
  每个 Adapter 内部完成请求归一化、响应归一化、错误归一化。
- 异步接口统一为 `submit(request) -> job_id`、`poll(job_id) -> status`、
  `fetch_result(job_id) -> result`；同步接口包装为立即完成的 Adapter。
- ProviderManager 负责「Provider → Model → Adapter」解析，业务代码只按
  capability 调用，禁止 `if model == xxx`。
- 完成标准：接入 2 个不同调用形态（如 OpenAI 兼容同步 + 百炼原生异步任务轮询），
  证明更换 Provider/Model 无需改业务层。
