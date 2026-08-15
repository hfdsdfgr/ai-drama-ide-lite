# 调研：Phase 13 — Image Generation（图片生成）

> 调研时间：2026-08-15。规则 75（Research Before Every Step）。
> 本轮只做调研与设计边界，不直接改业务代码。

## 结论摘要

Phase 13 的目标不是“重写 Provider / Adapter”，而是把项目里已经存在的
`ProviderManager → GenerationService → JobWorker` 与
`AssetVersionService → ProductionGraphService` 串成第一条可运行的视觉生产链路。

推荐按三个最小里程碑推进，避免一次铺开：

1. **M1 Prompt Builder**：纯函数式服务，负责把资产卡 / 分镜信息拼成生图提示词和尺寸。
2. **M2 Image Generation Job**：新增长图任务入口，用户选择单个已启用且支持生图的模型，创建 Job。
3. **M3 Result → Version + Graph**：生图完成后下载远端图片、写入 `versions`，并写 `production_edges`，前端回填预览。

产品约束继续遵守：**一次 Generation Job 只绑定一个 Model / 一个 Provider，不实现多模型并行，也不提前做 Model Router。**

## 1. 当前代码已经具备什么

已经存在、可以直接复用的基础设施：

| 层 | 文件 | 现状 |
| --- | --- | --- |
| Adapter 统一入口 | `apps/backend/app/services/adapters/manager.py` | 能按 `capability` 校验模型并解析 Adapter |
| 同步生图 | `apps/backend/app/services/adapters/openai_compat.py` | 已实现 `text_to_image`、`image_to_image/reference_image` |
| 原生视频异步任务 | `apps/backend/app/services/adapters/dashscope.py` | 已实现 `text_to_video` / `image_to_video` 的 submit/poll |
| 持久化 Job | `apps/backend/app/services/job_worker.py` | 单 worker 顺序执行、真实状态、可取消/暂停/重试 |
| 版本存储 | `apps/backend/app/services/asset_version_service.py` | 已能写文件 + `versions` 表 + 设置 current |
| 生产依赖图 | `apps/backend/app/services/production_graph.py` | 已能写边、查受影响下游节点 |
| 图片规格 | `apps/backend/app/services/asset_service.py` | 已有资产默认比例、可选比例、画风 |

这表明 Phase 13 的关键工作量主要是 **“业务编排 + 下载落盘 + 缺口补齐”**，不是重新发明 Adapter 架构。

## 2. 现有实现中必须补齐的缺口

### 2.1 原生 DashScope 图片能力缺失

当前 `ProviderManager._adapter()` 的逻辑是：

- `video` 能力 + `bailian / bailian-intl` → `DashScopeAdapter`
- 其他能力 → `OpenAICompatAdapter`

因此 Bailian 的图片模型（`wanx`、`qwen-image` 等）目前会走
`POST {base}/images/generations` 这条 OpenAI 兼容路径。

官方原生 `wanx-v1` 文生图使用异步任务：

```text
POST {dashscope_base}/api/v1/services/aigc/text2image/image-synthesis
  X-DashScope-Async: enable
  body:
    model
    input.prompt
    input.negative_prompt
    input.ref_image        # 可选参考图 URL
    parameters.style
    parameters.size        # 例：1024*1024
    parameters.n
    parameters.seed
    parameters.ref_strength
    parameters.ref_mode    # repaint / refonly
```

查询仍复用：

```text
GET {dashscope_base}/api/v1/tasks/{task_id}
```

但成功返回结构和现有 `DashScopeAdapter.poll()` 不同，图片结果在
`output.results[].url`，而不是视频场景里的 `output.video_url`。

Phase 13 应把 `DashScopeAdapter` 扩展为：

- `submit()` 支持 `text_to_image` / `reference_image` / `image_to_image` 的图片能力。
- `poll()` 区分图片结果和视频结果，归一化到同一个 `GenerationResult`。
- 保留视频逻辑不变。

> 是否直接信任 `compatible-mode/v1/images/generations` 取决于具体模型和官方兼容范围；
> 为避免猜测，建议以阿里云百炼当前官方文档为准，先实现原生异步图片接口。

### 2.2 远端图片 URL 还没有被下载到本地

现在 `JobWorker` 只把结果 URL 存进 `jobs.result_payload`；
只有 Adapter 自己把 `b64_json` 解码成本地文件时，`output_files` 才不为空。

对于返回临时 URL 的厂商（DashScope 图片 URL 通常 24 小时有效），不能只保存 URL，
必须下载成项目内文件，否则历史版本会失效。

建议由 Phase 13 新增的图片任务编排服务在 Job 成功后：

1. 读 `GenerationResult.urls`。
2. 逐个下载并写入项目目录。
3. 用 `AssetVersionService.add_version()` 记录新版本。
4. 把远端 URL 作为 `payload.source_url` 保留，但 `file_path` 始终指向本地文件。

### 2.3 OpenAI 兼容图片参数目前过于简陋

`openai_compat.py` 的 `_text_to_image` 当前只传：

```python
{"model", "prompt", "n": 1, "size": request.aspect_ratio}
```

OpenAI / 多数 OpenAI 兼容图片接口的 `size` 是像素串，例如 `1024x1536`；
而项目资产卡目前存的是比例值，例如 `2:3`。

Phase 13 的 Prompt Builder 应在进入 Adapter 前把比例映射为具体像素规格，
Adapter 继续只负责厂商格式转换：

- OpenAI 兼容：`1024x1536`
- DashScope 原生：`1024*1536`

若当前模型支持 `response_format: b64_json`，可由 Adapter 落本地；
否则统一交给 M3 下载 URL。

### 2.4 参考图能力与多图输入

现有 `GenerationRequest.images` 已经支持列表，但 `openai_compat._edit_image()`
只使用了 `images[0]`。对于角色一致性场景，成熟的提示词工程通常需要：

- 角色三视图 / 角色卡参考图
- 场景参考图
- 风格参考图

Phase 13 的 MVP 可以先限制为“**单张参考图**”，因为：

1. 首先生成角色 / 场景基础版本，再拿当前版本作为分镜生图的参考图。
2. 避免一次引入多图上传、多 Provider 参数差异和成本膨胀。
3. 多图一致性和更复杂角色锚点留给后续 Phase 17 / 19。

但 `GenerationRequest` 必须继续保留 `images: list[str]`，Adapter 接口不要因 MVP
限制被写死成单图，否则未来扩展又要改契约。

### 2.5 生图任务接口缺少输入字段

`apps/backend/app/schemas/generation.py` 的 `GenerationJobCreate` 目前只有：

```text
model_id
capability
prompt
aspect_ratio
duration
```

缺少：

- `images`：图生图 / 参考图输入。
- `negative_prompt`：负向提示词。
- 结构化 `extra` 或 `source_asset_ids`：用于生产图依赖边。

Phase 13 应最小扩展 schema 和 `/api/generation/jobs`，只加当前必需字段，不把
所有未来 Provider 参数一次性塞进去。

## 3. 推荐实现设计

### 3.1 M1：Image Prompt Builder

建议新增 `apps/backend/app/services/image_prompt_builder.py`，职责：

- 输入：
  - 资产生成：`asset_type + reference_prompt + fields + aspect_ratio + art_style`
  - 分镜生成：`shot.prompt + characters + action + lighting + camera`
  - 当前可用的角色 / 场景参考图 URL
- 输出：
  - `prompt`：合并固定角色描述、动作描述、镜头 / 光照 / 画风，并追加一致性关键词。
  - `negative_prompt`：默认质量负向词。
  - `aspect_ratio` / `width` / `height`：统一像素规格。
  - `source_refs`：本任务引用到的资产版本 / 镜头 ID。

关键原则：

- 用户已填写的 `reference_prompt` 必须原样复用，不覆盖。
- 同一角色 / 场景在多次生图时固定使用同一段描述，保证视觉一致。
- 不在这里做模型差异判断；厂商格式转换属于 Adapter。

### 3.2 M2：Image Generation Job

建议新增 `apps/backend/app/services/image_generation_service.py`，对外 API 可以是：

```text
POST /api/projects/{project_id}/images/generate
```

入参最小化为：

```text
target_type: asset | shot
target_id:   asset_id 或 shot_id
model_id:    用户选择的一个图片模型
capability:  text_to_image | image_to_image | reference_image
aspect_ratio / art_style / negative_prompt
```

服务内部：

1. `ProviderManager.adapter_for(model_id, capability)` 做 fail-fast 校验。
2. 用 `ImagePromptBuilder` 组装 `GenerationRequest`。
3. 创建持久化 `generation` Job，`project_id` 绑定到当前项目。
4. Job 完成回调 / 查询时再走 M3 落盘。

一次只创建一个 Job，不批量创建、不并行创建。

### 3.3 M3：Result → Asset Version → Production Graph

建议在图片 Job 完成时新增一个明确的落盘步骤：

```text
Generation Job completed
  → download result image to projects/{project_id}/assets/{asset_id}/v{n}.png
  → versions.add_version(...)
  → production_graph.add_edge(...)
```

关系边至少覆盖：

```text
asset(v3) → image_version(v2)     relation: image_generated_from_asset
shot(shot_03) → image_version(v1) relation: image_generated_from_shot
```

如果是资产生图，`entity_type = asset`，`entity_id = asset_id`；
如果是分镜生图，可先写入该分镜对应的图片版本，或扩展一个
`shot_image` 实体。当前 `versions` 表使用 `entity_type + entity_id` 通用引用，
可继续用 `entity_type = shot`，不破坏既有 schema。

## 4. 生成状态与 UI 边界

Phase 13 UI 应在现有基础上做最小改动：

- 资产页“生成图片”占位按钮接入真实 Job，模型下拉只显示已启用且能力匹配的图片模型。
- 分镜卡“待生成”状态根据 `jobs` / `versions` / `production_edges` 回填。
- 生成过程中显示真实 Job 状态；厂商不给进度时显示“生成中……”，不做假进度。
- 模型下拉默认显示模型 ID，不写死模型名称。

## 4.1 易用性设计：假设“我就是用户”，我期望看到什么

这一节是产品可用性约束，后续做 M1/M2/M3 时 UI 必须围绕它设计。

### 资产页：生成角色 / 场景 / 道具图片

我进入资产页，选中“林凡”这个角色后，最自然的期待是：

1. 在当前资产卡的“图片版本”区域直接看到一个主操作按钮：**生成图片**。
2. 按钮附近有一个**图片模型下拉框**，默认已经选好我在设置里配的“默认图片模型”，不用每次重选。
3. 下拉框旁有一个小信息图标，悬停说明：
   - API 在哪里配置；
   - 该操作会调用我的 API，可能产生费用。
4. 如果系统没有可用图片模型，不要只显示一个灰色按钮，而是明确告诉我：

   > 还没有可用的图片模型。请先到“设置”启用一个支持文生图的模型。

   并给出可直接跳转的设置入口。
5. 如果还没选项目，先提示“先选择项目”，不要显示一堆空面板。
6. 生成成功后，新图片应该立刻出现在下方“图片版本”列表里，并标记为“当前”，
   不需要我手动刷新页面，也不需要我理解 `v1` 背后的技术概念。
7. 生成失败时，错误要出现在模型下拉框附近，而不是页面顶部：

   > 生成失败：当前模型不支持 image_to_image，请选择支持“参考图/图生图”的模型。

### 分镜页：生成分镜图片

我进入分镜页，看到的是一排分镜卡片。我的真实工作流是“逐个镜头决定画面”，所以：

1. 每张分镜卡应一眼看出状态：**待生成 / 生成中 / 已完成 / 失败**。
2. 未生成时，卡片显示 16:9 空画框和“生成图片”入口，而不是逼我点进详情才想起来怎么生成。
3. 点击某张分镜卡后，右侧详情面板里同时提供：
   - 图片模型下拉框；
   - **生成图片**主按钮；
   - 取消 / 重试按钮；
   - 错误信息放在模型下拉附近。
4. 生成成功后，分镜卡片里直接显示缩略图；我切到别的镜头再切回来，状态和图片不能丢。
5. 剧本页已有“一键生成当前分集所有分镜”时，分镜页应该能看到同一条进度，
   不要出现“剧本页说在生成，分镜页却显示待生成”的不一致。
6. 文案用中文行业术语，不要出现 `medium close`、`INT` 这类用户看不懂的词。

### 模型选择

- 只显示**已启用且能力匹配**的图片模型，不要列出无关模型。
- 显示名直接用模型 ID / 官方模型名，不允许写死。
- 默认值优先使用“默认图片模型”；如果用户临时切换，只影响本次操作，不必回设置页。

### 状态与成本

- 状态只有真实状态：待生成、生成中、已完成、失败、已取消。
- 厂商没有返回百分比时，只显示“生成中……”，绝不显示假进度。
- 生成按钮触发付费 API 前，用一句简短说明让用户知道会花 API 额度，但不做多余弹窗打断流程。
- 取消和重试要就近可用；同时生成中心仍保留完整任务记录作为兜底。

### 空状态与首次使用

- 没有可用模型时，优先展示“去设置启用模型”这个下一步，而不是空白。
- 如果角色 / 场景的 `reference_prompt` 为空，仍允许生成，但提示：

  > 填写参考提示词后，生成结果会更稳定。

- 不要因为用户少填一个可选项就阻止主流程。

## 5. 本轮调研参考来源

- OpenAI Images API — Create image（官方参考）：
  https://developers.openai.com/api/reference/resources/images/methods/generate
- OpenAI Images API — Create image edit（官方参考，参考图 / 多图编辑）：
  https://developers.openai.com/api/reference/resources/images/methods/edit
- OpenAI Image generation guide（模型、尺寸、一致性说明）：
  https://developers.openai.com/api/docs/guides/image-generation
- Alibaba Cloud Model Studio — Wanx text-to-image V1 API reference：
  https://help.aliyun.com/en/model-studio/text-to-image-api-reference
- 阿里云百炼 — 万相文生图 V2 API reference：
  https://help.aliyun.com/zh/model-studio/text-to-image-v2-api-reference
- 阿里云百炼 — Qwen-Image 2.0 / 2.0 Pro / 3.0 模型能力说明：
  https://help.aliyun.com/zh/model-studio/qwen-image-2-0.md
  https://help.aliyun.com/zh/model-studio/qwen-image-2-0-pro.md
  https://help.aliyun.com/zh/model-studio/qwen-image-3-0.md
- Seedance-2.5 Prompting（角色一致性 / 参考图使用方式）：
  https://github.com/allenGKC/Seedance-2.5/blob/main/skill/seedance-25/references/prompting.md
  https://github.com/allenGKC/Seedance-2.5/blob/main/skill/seedance-25/references/references.md
- Storyboard / Character Reference 提示词工程参考：
  https://github.com/ww849906675ww-bot/storyboard-generator

## 6. Phase 13 本轮边界

本轮先不实现：

- 多模型并行生成。
- 自动 Model Router。
- 批量一键生图（可后续做，但必须先验证单张闭环）。
- 视频生成。
- Quality Agent / Director Agent。
- 复杂多图参考机制。

先把“资产图 + 分镜图 → 单模型 Job → 本地版本 → 依赖边 → UI 回填”这一条
最小闭环跑通，再谈批量与自动化。
