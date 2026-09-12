# Phase 24 M4 预研：Schema 驱动参数与薄 Agent 入口

日期：2026-09-11。状态：参数 Schema 子集已实施；CLI / Agent 入口待后续明确授权后排期。

## 当前事实

1. `GenerationRequest` 只有跨厂商公共字段：Prompt、参考图片、比例 / 分辨率、时长、负面词和 `extra`。
2. 各 Adapter 已经在代码中硬编码真实厂商约束，例如 Sora 时长映射、智谱 10 秒上限、Seedream 合法像素映射、Seedance 分辨率和音频开关；这些规则没有形成可供 UI 查询的描述。
3. 前端在资产、分镜和工作流模板中分别硬编码比例、时长和规格，新增模型参数会继续产生重复分支。
4. Capability 只表示“能不能做”，不表示该模型对某参数的选项、默认值和限制。
5. 项目没有业务 CLI；唯一 `argparse` 入口仅用于启动后端。现有 FastAPI 已覆盖业务，因此 CLI 不应直接访问数据库或复制 Service。

## 用户收益

- 选择模型后只看到该模型实际支持的参数，不再用一个固定表单猜所有厂商。
- 参数在创建付费 Job 前由同一份服务端规则校验，避免 UI 能选但 Adapter 拒绝。
- Agent / 脚本先调用 plan 和 schema，明确目标、模型、费用动作后再执行；桌面 UI 和自动化共享同一业务结果。
- 新增 Provider 时主要扩展 Adapter 描述和映射，不需要在多个页面追加模型名判断。

## 第一部分：最小参数描述协议

不直接暴露厂商原始 JSON Schema，也不引入表单库。Adapter 返回项目内部的稳定参数描述：

```json
{
  "model_id": "...",
  "capability": "image_to_video",
  "schema_version": 1,
  "fields": [
    {
      "key": "duration",
      "label": "时长",
      "control": "select",
      "value_type": "integer",
      "default": 5,
      "options": [{"value": 5, "label": "5 秒"}],
      "required": true,
      "help": "..."
    }
  ]
}
```

首版控件只支持 `select`、`boolean`、`integer`、`number`、`text`；描述字段只允许白名单：

- `key`, `label`, `control`, `value_type`, `default`
- `options`, `minimum`, `maximum`, `step`, `required`, `help`
- `visible_when` 仅支持同级字段等值判断；不加入表达式语言。

安全边界：

- 不返回 API Key、Provider URL、请求头或任意厂商 body。
- 参数 key 是内部 canonical key；Adapter 负责映射到 `seconds`、`resolution`、`size` 等厂商字段。
- 未经真实 Adapter 实现或测试验证的参数不进入描述。
- 服务端在 Job 创建前调用同一 Adapter 的 `validate_parameters`；前端校验只用于即时反馈。
- 不允许未知参数穿过 `extra` 直接发给厂商。

## 第二部分：Adapter 落地

基类新增两个只读方法：

- `parameter_schema(ctx, capability) -> ParameterSchema`
- `validate_parameters(ctx, capability, values) -> canonical values`

实现顺序按现有已验证调用链：

1. 图片：OpenAI-compatible、DashScope、Volcengine 的比例 / 尺寸；保留现有业务画幅到厂商尺寸映射。
2. 视频：Sora、DashScope、Volcengine、OpenRouter、智谱的时长、比例 / 分辨率；音频字段本轮排除。
3. 未覆盖 Adapter 返回公共字段的保守描述，不虚构选项。

新增接口：

- `GET /api/models/{model_id}/generation-schema?capability=...`
- `POST /api/models/{model_id}/generation-schema/validate`

模型禁用、Provider 禁用、Capability 不匹配继续使用 `ProviderManager` 现有校验。

## 第三部分：前端动态控件

新增一个 `GenerationParameterFields` 组件，输入 schema、values、disabled 和 onChange。

- 首先替换工作流模板中的视频规格 / 时长，以及分镜图片 / 视频对应字段。
- 资产页的资产类型默认画幅仍由业务规格决定；模型 schema 只过滤可兼容值，不覆盖资产设计规则。
- 切换模型后保留仍合法的值；非法值明确标记并要求用户选择，不自动换默认值。
- 保存模板时仍只保存白名单 canonical values，不保存整份 schema。
- Schema 加载失败时禁止付费提交，并提供重试；不回退到猜测参数。
- 900px 单列，宽屏使用现有紧凑字段栅格，不增加新的设置页面。

## 第四部分：薄 CLI / Agent 接口

使用 Python 标准库 `argparse` + `urllib`，不新增依赖。CLI 只调用本机 FastAPI：

- `projects list`
- `episodes plan --project ... --episode ...`
- `models schema --model ... --capability ...`
- `pipeline start --project ... --episode ... --expected-revision ...`
- `jobs status --job ...`
- `jobs pause|resume|cancel --job ...`

原则：

- 默认输出 JSON；列表流可选 NDJSON，便于 Agent 逐条处理。
- 付费启动命令必须显式传 `--confirm-paid`，否则只打印 plan 并以非零状态结束。
- CLI 不读取 SQLite、不解析模板、不选择模型、不实现重试；所有规则由 API / Service 决定。
- 错误输出稳定包含 HTTP 状态、业务 code、message；密钥和内部路径不输出。
- 首版只连接显式 `--base-url` 或默认 loopback，不开放远程监听或认证方案。

## 测试

- 每个已接入 Adapter 的 schema 与实际请求映射参数一致。
- schema 默认值通过自身校验；越界、未知字段、错误类型在创建 Job 前被拒绝。
- 切换模型不会把旧模型的非法值静默发送。
- 工作流模板保存 / 应用和恢复运行仍使用启动快照。
- CLI plan 不创建 Job；缺少 `--confirm-paid` 不创建 Job；确认后只创建一个 Job。
- CLI 与桌面端对相同 API 返回相同业务错误。
- 后端、前端全量回归与 1440px / 900px 浏览器验收。

## 尚需确认的产品边界

1. 首版参数 Schema 是否只覆盖图片 / 视频，继续排除音频。建议：是。
2. CLI 是否允许启动付费生成。建议：允许，但强制 `--confirm-paid`，默认只 plan。
3. 首版 Agent 入口是否以 CLI 的稳定 JSON 输出为止，不额外实现 MCP Server。建议：是，先验证真实自动化需求。

## 实施顺序

1. 固定参数描述 Schema 和后端验证器。
2. 为已有 Adapter 逐个迁移代码中已验证的约束并补映射测试。
3. 接入模型 schema API，再替换图片 / 视频硬编码控件。
4. 增加薄 CLI 和付费确认门槛。
5. 全量回归、浏览器验收、README / Roadmap / pitfalls / 实施报告和本地提交。

不包含音频能力扩展、任意厂商参数透传、远程 API 暴露、MCP Server、无限节点画布、公开推送或 Release。
