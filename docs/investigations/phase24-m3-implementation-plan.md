# Phase 24 M3 落地计划：结构化导演控制

日期：2026-09-11。状态：完成代码调研，等待 3 项产品边界确认。

## 目标与用户收益

M3 不再要求用户把人物质感、表情和站位全部手写进一段长 Prompt，而是把这些导演意图拆成可见字段，并在付费生成前展示最终合成结果。

- 人物质感：调通一次后可复用、可修改、可查看历史版本，减少每个镜头重复抄写。
- 情绪：明确“谁、什么情绪、多强”，避免多人镜头中模型把表情作用到错误角色。
- 站位 / Pose：外部参考图中的人物标签显式映射到项目角色，减少“左边的人是谁”这类歧义。
- 可审计：原始镜头 Prompt 永不被隐式覆盖；每次生成保存实际 Patch 版本、情绪参数、映射和参考图片版本。

它在完整 AI 漫剧中的位置是：M1 判断一集缺什么，M2 固定按什么流程运行，M3 让导演能以结构化方式控制单个镜头的表演与画面，同时仍进入现有 Image Job、Version 和依赖追踪链路。

## 当前代码事实

1. `shots.prompt` 是镜头原始视觉描述，`build_shot_image_prompt` 会在其后追加场景、资产一致性和画风；适合新增显式 Patch 参数，不应修改原字段。
2. 图片生成已支持 `reference_version_ids`、历史版本固定、`source_refs` 和重生成 recipe；导演参考应沿这条链路传递，不能只保存参考媒体 ID。
3. 项目已有 `reference_media` 导入和版本文件，但只有名称，没有用途和角色映射。
4. 通用 `versions` 当前是媒体版本，服务要求实际文件；文本 Prompt Patch 不应伪装成空文件媒体版本。
5. Storyboard 页面已经承载镜头字段、模型、参考图与生成按钮；导演控制应折叠在图片配置内，不新增顶级页面或画布。
6. `Shot.characters` 是名称字符串，匹配存在歧义；新配置必须保存稳定的 `character_asset_id`，名称只用于显示。
7. 项目导入 / 导出会显式枚举表和 ID 映射；新增数据必须加入 transfer，不能只在当前数据库可用。

## 数据模型

### 1. Prompt Patch 预设和版本

`prompt_patch_presets`

- `id`, `project_id`, `name`, `description`, `created_at`, `updated_at`
- 预设身份不随内容更新变化，删除使用软删除或被引用保护。

`prompt_patch_versions`

- `id`, `preset_id`, `project_id`, `version`, `positive_patch`, `negative_patch`
- `parameters_json` 保存生成 Patch 的结构化输入，不保存模型密钥或媒体文件。
- `is_current`, `created_at`
- 编辑内容创建新版本，不覆盖历史；同一预设版本号唯一。

首版 Patch 参数建议保持小而稳定：

- `render_medium`：插画 / 3D / 写实 / 自定义。
- `surface_finish`：干净 / 细腻纹理 / 粗粝纹理 / 自定义。
- `detail_level`：1–5。
- `custom_instruction`：用户补充的短文本。

服务端使用确定性词典生成初稿，不调用 LLM，因此预览与保存不收费；用户可直接修改生成后的 positive / negative Patch。

### 2. 镜头导演配置

`shot_director_configs`

- `shot_id` 主键、`project_id`、`revision`、`config_json`、`updated_at`。
- 严格 Schema，只保存以下三组白名单字段。

`prompt_patches`

- `patch_version_id`
- `character_asset_ids[]`：Patch 作用的目标角色；空数组若获批准才表示全画面。

`emotions`

- `character_asset_id`
- `emotion`：首版离散值 + 自定义文本的取舍见待确认项。
- `intensity`：1–5，避免假装模型支持精确连续坐标。

`composition_references`

- `reference_version_id`：必须是项目内图片的精确版本。
- `purpose`：`blocking` 或 `pose`。
- `subject_label`：用户对参考图人物的短标签，例如“左侧人物”。
- `character_asset_id`：映射到项目角色；同一参考图允许多行映射。

配置 PUT 携带 `expected_revision`，冲突返回 409。删除预设不级联删除已保存的版本；被镜头引用的版本不可物理删除。

## 编译与生成语义

新增纯函数 `compile_shot_director_recipe`，输入原始镜头、场景、角色资产、Patch 精确版本和导演配置，输出：

- `base_prompt`：原始镜头 Prompt，不修改。
- `positive_patch`：按角色分组的质感、情绪、站位 / Pose 描述。
- `negative_patch`：版本化负面约束。
- `final_prompt` / `final_negative_prompt`：实际提交文本。
- `reference_version_ids`：去重后的精确图片版本。
- `warnings`：角色不在本镜头、版本失效、参考图文件缺失、映射不完整。

规则：

1. 顺序固定为原始镜头 → 场景 / 资产一致性 → 人物质感 → 情绪 → 站位 / Pose → 通用一致性；用户可在预览中判断每层来源。
2. 不使用真假值合并，不自动补角色，不将未映射人物猜成任一资产。
3. 保存配置不创建 Job；预览编译不创建 Job。
4. 点击生成时提交 `director_config_revision`。服务端重新编译并校验，修订不一致则阻止付费请求。
5. Job input 和结果版本 payload 保存完整导演快照与精确 Patch / 参考版本 ID，依赖图可继续追踪。
6. 模型参考图数量上限沿用现有 Capability 校验；超限时列出具体参考，不偷偷裁掉。

## API

Prompt Patch：

- `GET/POST /api/projects/{project_id}/prompt-patches`
- `GET/PATCH/DELETE /api/projects/{project_id}/prompt-patches/{preset_id}`
- `GET /api/projects/{project_id}/prompt-patches/{preset_id}/versions`
- `POST /api/projects/{project_id}/prompt-patches/{preset_id}/versions`
- `POST /api/projects/{project_id}/prompt-patches/{preset_id}/versions/{version_id}/promote`

镜头导演配置：

- `GET/PUT /api/projects/{project_id}/shots/{shot_id}/director-config`
- `POST /api/projects/{project_id}/shots/{shot_id}/director-config/preview`

现有图片生成请求增加可选 `director_config_revision`。未设置导演配置的旧调用完全保持当前行为。

## 前端落点

在 Storyboard 的“分镜图片”卡片内增加折叠区“导演控制”，不增加顶级导航。

1. 顶部始终展示本次控制摘要：质感数、情绪数、构图参考数、是否有阻塞。
2. “人物质感”按角色添加 Patch；选择预设后显示精确版本，允许查看 Patch 文本和版本历史。
3. “情绪”逐行选择目标角色、情绪、强度；默认不创建任何行。
4. “站位与 Pose”从现有参考图库选择精确版本，再逐行填写参考人物标签并映射角色。
5. “预览最终 Prompt”展示原始内容、每类 Patch 和最终文本，不生成图片。
6. 保存按钮与生成按钮分离；有未保存修改、失效引用或角色映射缺失时禁用生成并说明具体行。
7. 900px 使用单列，宽屏字段保持紧凑表格；不画自由连线，不新增第三方 UI / 图形依赖。

## 测试与验收

后端：

- 项目 / 镜头 / 角色 / 版本归属隔离。
- Patch 编辑新增版本且历史不变；引用中的版本不能被误删。
- 情绪强度边界、重复目标、未知角色和未映射标签被拒绝。
- 编译顺序稳定；原始 `shots.prompt` 不变化。
- 生成服务实际收到最终 Prompt、负面 Patch、精确参考版本和配置快照。
- 配置预览后被另一窗口修改，旧修订生成返回 409 且不创建 Job。
- 旧数据库、项目导入导出、无导演配置的现有生成路径回归通过。

前端 / 浏览器：

- 添加、编辑、版本化和选择 Patch；零配置默认不改变当前路径。
- 多角色情绪不会串到其他角色。
- 同一 blocking 图可映射多个参考人物；未完成映射不可生成。
- 预览不创建 Job，单击生成只创建一个 Job。
- 1440px / 900px、键盘操作、加载失败和空状态可用。

## 实施顺序

1. 确认下方 3 项产品语义并冻结严格 Schema。
2. 实现 Prompt Patch 存储、版本、归属与 API 测试。
3. 实现镜头导演配置、编译纯函数和预览接口。
4. 将编译结果接入现有图片生成服务、Job recipe、source refs 和项目 transfer。
5. 接入 Storyboard 折叠 UI，复用现有角色资产、参考图库和版本选择器。
6. 定向测试 → 全量后端 / 前端 → 浏览器 1440 / 900 验收。
7. 更新 Roadmap、README、pitfalls 和实施报告，清理临时产物并本地提交；不推送、不发布。

## 必须由用户确认的 3 项

1. Patch 预设归属：项目内通用并在镜头中绑定角色，还是每个角色私有。
2. 镜头绑定 Patch 时：固定所选精确版本，还是自动跟随预设最新版本。
3. 首版导演控制作用范围：仅关键帧生图，还是关键帧和视频都直接追加同一套控制与参考图。
