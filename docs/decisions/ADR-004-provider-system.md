# ADR-004: Phase 3 Provider / Model 体系（简化版）

## Context

用户要求极简配置：模型不允许用户取名（显示名 = 模型 ID）；尽量只填 API Key；隐藏不需要的字段。同时遵循单模型生成约束（不做多模型并行、不提前实现自动 Router）。

## Decision

- **内置厂商预设**（providers/presets）：OpenAI、OpenRouter、DeepSeek、阿里云百炼、智谱、硅基流动、Ollama（本地免 Key）。预设提供 Base URL / 是否需要 Key / 模型类型归类规则；选择预设后用户只需填 API Key。
- **models 显示名 = model_id**：不提供取名字段；下拉显示模型 ID。
- **动态模型发现**：`POST /api/providers/{id}/discover-models` 调用 OpenAI 兼容 `/models` 拉取模型并入库；按预设规则归类 llm/image/video（未命中默认 llm，Phase 4 能力检测修正）。
- **密钥存储**：`keyring` → 系统凭据管理器（Windows Credential Manager / Keychain / SecretService）；DB 只存 `key_ref`；响应只返回 `has_api_key`；无明文回退。
- **默认模型**：全局唯一（同一类型仅一个默认），事务内先清后设。
- **聚合查询**：`GET /api/models?model_type=&enabled_only=true` 返回跨 Provider 已启用模型（含 provider 信息），作为生成界面动态下拉数据源。
- **自定义 Provider**：高级折叠区，需填名称 + Base URL + 可选 Key，支持手动添加模型兜底。
- **不实现**：能力检测（Phase 4）、自动 Model Router（P1）、任何生成界面（Phase 13/14）、多模型并行。

## Alternatives

- 允许用户给模型取名（独立显示名字段）：用户明确否决，取消失。
- 密钥存 localStorage（ai-selector 做法）：仅适合浏览器场景，桌面应用用 OS 凭据管理器更安全。
- 全部字段始终显示：违背"不需要填的不列出"。

## Reason

调研结论（docs/investigations/provider-model-systems.md）：Open WebUI 多 Provider + 模型聚合、ai-selector 厂商预设 + 动态模型拉取、keyring 系统安全存储均为成熟模式；模型取名不是刚需。

## Consequences

- 新厂商加入 = 加一条 preset（含类型规则），无需改业务层。
- 模型类型归类可能不准（依赖命名规则），Phase 4 能力检测会实测修正。
- 密钥所在系统不同（Windows Credential Locker / WinVaultKeyring 因版本而异），需在目标平台实测。
