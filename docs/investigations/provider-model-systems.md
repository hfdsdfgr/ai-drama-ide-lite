# 调研：主流开源项目如何实现 Provider / Model 体系

> 调研时间：2026-08-13。目的：为 Phase 3（AI Provider 基础系统）确认设计方向，避免重造轮子。

## 结论摘要

1. **Provider 1 → N Model、多 Provider 并存**是主流做法（Open WebUI、LiteLLM、SillyTavern QIG、ai-selector 均如此）。
2. **动态模型列表**：Open WebUI 通过 `get_all_models` 聚合各 Provider 模型目录；ai-selector 通过 `fetchModels` 动态拉取。即"读已配置且启用的模型"而不是写死。
3. **密钥存储**：成熟做法是系统级安全存储。`keyring`（Windows Credential Manager / macOS Keychain / Linux SecretService）是 Python 标准选择；桌面应用应使用 OS 凭据管理器，而非前端 localStorage 加密。
4. **Adapter / 归一化**：Open WebUI 按 Provider 做 payload 转换与响应归一化；LiteLLM 以 OpenAI 格式统一 100+ 厂商。对应本项目"Model Adapter"层。
5. **类型/能力检测**：InvokeAI 在导入模型时 probe 出模型类型与配置（对应本项目 Phase 4 Capability Engine）。
6. **自动 Router**：LiteLLM Router（负载均衡/回退/重试）是最复杂的部分，MVP 不做（与本项目"单模型生成"约束一致）。
7. **厂商预设**：ai-selector 内置 20+ 厂商配置（Base URL / 是否需要 Key / Models API），用户选厂商 + 填 Key 即可，模型列表自动拉取。

## 参考来源

- Open WebUI LLM Provider Integration（DeepWiki）：https://deepwiki.com/open-webui/open-webui/13-api-client-layer
- LiteLLM：https://github.com/liyedanpdx/llm-python-patterns/blob/main/cases_analysis/litellm_analysis.md ；Router 架构 https://docs.litellm.ai/docs/proxy/architecture
- SillyTavern Quick Image Gen：https://raw.githubusercontent.com/platberlitz/sillytavern-image-gen/main/README.md
- InvokeAI Model Manager：https://github.com/invoke-ai/InvokeAI/blob/main/docs/contributing/MODEL_MANAGER.md
- keyring：https://github.com/jaraco/keyring
- ai-selector（React/Vue Provider 配置组件）：https://github.com/tombcato/ai-selector
- daknoblo/ai-ui（配置不含 secrets）：https://github.com/daknoblo/ai-ui

## 对 Phase 3 的影响

- `providers` + `models` 两表（1:N）；模型显示名 = 模型 ID，不允许用户取名
- 内置厂商预设（OpenAI / OpenRouter / DeepSeek / 阿里云百炼 / 智谱 / 硅基流动 / Ollama），选厂商 + 填 Key 即可
- 动态拉取模型列表（OpenAI 兼容 `/models`），按预设规则归类 llm/image/video
- 密钥用 `keyring` 存 OS 凭据管理器；DB 只存 `key_ref`
- 保留 Provider → Model → Adapter 分层；不引入自动 Router
