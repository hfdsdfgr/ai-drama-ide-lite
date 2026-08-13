# 调研：连接测试 / 能力检测 / 手动覆盖（Phase 4 依据）

> 调研时间：2026-08-13。规则 75（Research Before Every Step）要求：先调研、记录来源，再出计划。

## 结论摘要

1. **连接测试 = 可达性 + 鉴权 + 模型可用性 三级**（Open WebUI / ai-key-tester / SillyTavern）：
   - Open WebUI 验证连接时调用 `/models`；`/models` 不可用时允许手动把模型 ID 加入 allowlist（与我们的百炼处理一致）。
   - SillyTavern 强调错误必须指明"是哪个 Provider 返回的什么错误"（可操作错误信息）。
   - ai-key-tester：本地验证 OpenAI/Anthropic/Google 等 Key，无需真实生成。
2. **API 模型的能力检测主流做法是"目录/规则驱动"，不是实时实测**（models.dev + LiteLLM）：
   - models.dev 为模型维护能力目录：modalities（输入 text/image/pdf/audio/video、输出 text）、limits、cost、reasoning/temperature/tool_call/attachment 等能力标志。
   - LiteLLM `model_info.mode`：chat / completion / embedding / **image_generation** / audio_* / moderation / rerank / search；OpenCode 通过 `/model/info` 拉取并提取 vision/PDF/video/tool calling 等能力。
   - 结论：我们"厂商预设 + 模型名规则"推断能力是主流做法；**手动覆盖**兜底（Open WebUI 的模型 allowlist 就是手动补充的形式）。
3. **本地模型文件探测**（InvokeAI probe）只适用于本地模型（读 state dict 判断 base type / variant / 是否 FLUX Fill）；我们的 API 模型不需要也不能这么做。
4. **生成类实测会花钱**：真实生成测试应独立成级（L3）且需用户主动确认；L1/L2 应尽量零成本（网络请求 + 轻量鉴权请求）。

## 参考来源

- Open WebUI：
  - 连接验证 /models + 手动 allowlist：https://hpc-ai.com/doc/docs/Model-APIs/Integration/Open%20WebUI/
  - Check Connection 按钮：https://github.com/open-webui/open-webui/issues/3330
- LiteLLM / models.dev：
  - model_info mode 枚举：https://docs.litellm.ai/docs/provider_registration/add_model_pricing
  - 从 models.dev 映射能力（modalities / capability flags）：https://github.com/i-dot-ai/coding-agent-litellm-config
  - 自动发现 + 能力提取：https://github.com/anomalyco/opencode/pull/14202
- InvokeAI 模型探测：https://github.com/invoke-ai/InvokeAI/blob/main/invokeai/backend/model_management/model_probe.py
- SillyTavern 错误可操作性：https://github.com/SillyTavern/SillyTavern/issues/4249
- ai-key-tester（本地 Key 校验）：https://github.com/rishiskhare/ai-key-tester

## 对 Phase 4 的影响

- L1/L2 测试：可达性 → 鉴权 → 模型可用性；错误信息带 Provider 名称与上下文；L1/L2 零成本。
- 能力检测：预设规则（厂商 + 模型名 → 能力集），与 models.dev 的 catalog 思路一致；手动覆盖作为兜底。
- `/models` 可用则校验模型存在；不可用（百炼）则靠预设规则 + 手动添加。
- L3 生成测试留 Phase 5（适配器就绪 + 用户确认后才触发，避免意外扣费）。
- 聚合查询 `?capability=` 为生成界面提供"已启用 + 类型匹配 + 能力通过"的模型。
