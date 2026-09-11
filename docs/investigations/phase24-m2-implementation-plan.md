# Phase 24 M2 落地计划：剧集配置模板与只读依赖视图

日期：2026-09-11。状态：已实施并完成验收。

## 已确认范围

- 执行对象是剧集。
- 模板仅在所属项目内使用。
- 模板只保存配置，不保存 Prompt、资产、参考版本或生成结果。
- 应用模板时逐项选择，不整体覆盖已有设置。
- 延续当前音频功能暂不开发的约束。

## 已确认的执行边界

剧集执行从已有剧本的分镜阶段开始，包含分镜、图片、视频；小说分析、剧本生成和共享资产作为前置检查，不在本轮剧集运行中自动重建。该边界已经用户确认，可避免重复创建剧集或隐式修改跨集共享内容。

## 代码核查结果

1. pipeline_service.py 的 stages 查询、镜头查询和完成度判断主要按 project_id；必须贯穿 episode_id，不能只改前端筛选。
2. pipelines 主键为 (project_id, stage_key)，start 删除整个项目阶段记录；不同剧集或不同运行会互相覆盖。
3. run 每次调用 _pick_stage_model；暂停恢复可能换模型，模板配置无法保证生效。
4. _run_shot_images 固定 text_to_image；_run_videos 使用镜头时长并归一化。参数需要沿完整调用链传递。
5. quality_review 将视觉、剧情和视频台词审核绑在一起，包含 ASR；本轮不能直接复用整个组合开关触发音频流程。
6. pipeline 路由当前没有转发 schema 已有的 quality_review 字段。兼容测试要覆盖此差异，不能借模板功能静默开启审核。
7. 依赖图已有关系、受影响节点和健康计算，缺少按镜头/场景返回实际版本、名称、状态和跳转信息的展示接口。

## 交付一：剧集范围与运行隔离

### 变更

- 保留旧项目 Pipeline 接口供现有调用使用；新增剧集入口：
  - GET /api/projects/{project_id}/pipeline/episodes/{episode_id}/plan
  - POST /api/projects/{project_id}/pipeline/episodes/{episode_id}/start
  - GET /api/projects/{project_id}/pipeline/episodes/{episode_id}/status?job_id=...
- 入口验证剧集属于项目且未删除；所有场景/镜头查询通过 scenes.episode_id 过滤，同时排除删除项。
- 分镜阶段按场景列出缺失分镜；不能用“本集有一个镜头”判断整集分镜完成。
- 图片/视频计划分别返回可执行、已存在、阻塞项及原因；缺关键帧、缺 Prompt、文件失效不能显示为成功完成。
- 依赖过期结果单独提示并保留现有逐镜头重新配置入口；本轮不据此自动批量重生成。
- 新增 pipeline_run_stages，以 (job_id, stage_key) 为主键，保存阶段状态、消息、当前子任务 ID 和更新时间。Job 仍是运行记录和生命周期来源，不新增第二个任务引擎。
- 旧 pipelines 数据保留；旧任务走兼容路径，新剧集任务按 job_id 读写阶段。
- 同集重复启动以及与项目级运行重叠的任务，在事务内检测并返回冲突；不同集即使存在多条运行记录也不能共享阶段状态。

### 暂停和恢复

- 启动保存已确认配置快照、episode_id、模板来源 ID/修订号；模板之后改名、修改或删除不影响运行。
- 保存当前子任务 ID；恢复先读取该子任务状态，避免重复提交付费请求。
- 父任务暂停/取消后停止继续派发镜头；已提交子任务依照现有 Job 取消能力处理，界面显示实际状态。
- 恢复时模型不可用则阻塞并说明原因，不重新自动挑模型。需要改模型时结束原运行，重新确认配置后启动。

### 验收

- 两集各有镜头，执行第二集，第一集的镜头、版本及任务不变。
- 两次运行的阶段记录互不覆盖。
- 暂停、重启应用、恢复后仍使用同一模型和参数；已有子任务不重复创建。
- 重复点击开始只产生一个被接受的运行；取消后不继续派发后续镜头。
- 已删除/跨项目剧集请求被拒绝，空集不会显示为完成。

## 交付二：模板和剧集配置持久化

### 数据结构

- workflow_templates：id、project_id、name、description、schema_version、revision、config_json、created_at、updated_at。
- episode_workflow_configs：episode_id 主键、project_id、revision、config_json、updated_at。
- 模板保存可复用设置，剧集配置保存实际逐项应用后的结果；二者均不作为运行状态。
- 模板配置白名单：已批准阶段的 enabled、capability、model_id、已支持参数，以及 auto_continue。
- 图片只开放已有调用链支持的参数，如 aspect_ratio；视频使用明确的 duration_mode（按镜头/固定）及固定时长、现有画幅或分辨率字段。
- 不将视频接口的 aspect_ratio 字段直接当成图片比例；按现有 Adapter 实际参数语义验证和显示。
- 未选择固定时长时保留按镜头时长的现有行为；用户明确选择固定时长后才传统一值，不修改剧本中的 shot.duration。
- 不新增音频参数或组合审核执行功能。已有任务和接口的音频行为不借迁移修改。
- 不保存 Prompt、参考资产/版本、源关键帧、密钥、Provider 认证、文件路径和 Job 状态。
- 使用 Pydantic 严格字段校验，拒绝未知字段；序列化从白名单构建，不能复制整个模型或 Provider 对象。

### 接口

- GET/POST /api/projects/{project_id}/workflow-templates
- GET/PATCH/DELETE /api/projects/{project_id}/workflow-templates/{template_id}
- GET/PUT /api/projects/{project_id}/episodes/{episode_id}/workflow-config
- PATCH/PUT 携带 expected_revision；并发修改返回 409，不能后写入者静默覆盖。
- 模板按 ID 引用，名称不作为身份；删除模板不删除已应用配置或历史运行。

### 验收

- 项目 A 不能列出或使用项目 B 的模板。
- 保存后重启仍存在，应用后独立修改剧集配置不会反向修改模板。
- 非白名单字段被拒绝，数据库及返回值中没有认证信息。
- 旧数据库重复初始化成功，现有项目和历史任务可读。

## 交付三：逐项预览与应用

### 接口与合并规则

- POST .../episodes/{episode_id}/workflow-config/preview-template：输入 template_id，返回模板修订、配置修订和字段差异。
- 每行包含 field_path、当前值、模板值、兼容性、阻塞原因；相同值不要求用户重复选择。
- POST .../episodes/{episode_id}/workflow-config/apply-template：输入两份修订号及 selected_fields。
- 服务端重新读取数据，只合并用户选择的白名单字段，事务内校验并递增配置修订。
- 预览期间任一来源变化返回 409 并要求刷新差异，不能继续套用旧预览。
- 更换模型而保留原参数时，校验合并后的完整配置；有冲突就列出字段，不偷偷调整参数。
- 模型失效时列出满足 Capability 的候选；用户选定后重新计算预览。选中了无法应用的字段时阻止提交。
- 模板缺失字段表示“不参与本次合并”，不等于清空。显式 false、0 和空值按字段 Schema 处理，不能用真假值判断是否有配置。
- 预览和应用不创建 Job，也不覆盖镜头 Prompt、参考选择或既有版本。

### 界面

- 在剧集制作台选中集后打开“制作配置”，显示明确集名。
- 配置区提供“保存为模板”“使用模板”；模板列表仅显示当前项目。
- 差异表列为“配置 / 当前 / 模板 / 应用”，差异项由用户勾选，默认不勾选。
- 页脚显示已选项数量和阻塞项；零选项禁止确认。取消不写入。
- 开始生产为独立操作，展示目标集、阶段、镜头数量、缺失项和明确模型。不能根据模板选择动作直接开始。

### 验收

- 模板改变模型、比例和时长，只勾选比例，另外两项保持原值。
- 更换模型造成参数冲突时无法静默应用。
- 关闭预览、切集、网络失败不留下半次写入；重入时从服务端读取配置。
- 模板/配置在另一窗口更新后，旧预览提交返回冲突。
- 键盘可选择每项，900px 下字段和值不截断到无法判断。

## 交付四：配置真正进入生成调用

- 扩展 Pipeline plan/start 请求，启动时校验 episode config revision 并保存完整有效快照。
- 将快照内模型、Capability、参数传给对应阶段，不修改全局默认模型。
- 分镜生成使用本集有效场景；图片按所选能力校验模型；视频使用现有镜头 Prompt 与关键帧解析。
- 不在模板中复制参考选择。新增结果继续使用现有生成服务记录实际 source_refs。
- 启用后继阶段但关闭前置阶段时，检查已有前置输出；满足则允许执行，不满足则返回具体镜头阻塞项。
- 配置预检覆盖全部启用阶段，不能只因为任意一个阶段可执行就忽略其他已知配置错误。

验收必须检查模拟生成服务实际收到的模型 ID、图片参数、视频时长和 episode 范围；仅检查数据库保存正确不算完成。运行途中修改模板和剧集配置，尚未派发的子任务仍使用启动快照。

## 交付五：只读镜头/场景依赖视图

### 后端

- GET /api/projects/{project_id}/graph/view?shot_id=... 或 scene_id=...；两个参数互斥，校验归属。
- 从当前结果的 source_refs 解析精确上游版本，复用 dependency_health；production_edges 提供补充关系，不能代替实际来源记录。
- 返回 nodes、edges、issues 和跳转目标。版本节点以 version_id 为身份，同一资产 v1/v2 不合并。
- 显示来源名称、使用版本、当前版本、媒体类型、依赖状态及原因。
- 旧数据和损坏引用返回明确占位节点，不以最新版本补造来源。
- 场景视图按镜头返回分组；列表分页，避免一次展示整个项目。按页批量读取版本，避免每个节点单独查库。

### 前端

- 从剧集制作台或分镜详情的依赖入口打开只读视图，保留原编辑位置。
- 镜头视图展示资产版本 → 实际关键帧版本 → 视频版本；场景视图按镜头分组展示同样的关系。
- 节点带版本文本和状态，问题原因按需展开；点击进入对应资产/分镜配置。
- 沿用现有主题、按钮和状态色；宽屏横向，窄屏纵向，语义列表保留键盘访问。
- 首版不增加自由布局、连线编辑和画布库。

### 验收

- 固定历史版本正确显示 pinned；旧来源显示 unknown；文件失效显示 broken。
- 视频即使使用历史关键帧也沿该关键帧继续展示真实资产依赖。
- 场景包含多个镜头时，引用同一版本可识别共享，但不同版本不能混为一项。
- 查看和跳转没有付费请求，1440px/900px 可读，空状态和加载失败均有出口。

## 文件落点

- 修改：db/schema.sql、db/database.py、schemas/pipeline.py、services/pipeline_service.py、api/routes/pipeline.py、服务注册处。
- 新增：schemas/workflow_template.py、services/workflow_template_service.py、api/routes/workflow_templates.py。
- 扩展：schemas/production_graph.py、services/production_graph.py、api/routes/production_graph.py。
- 前端修改：api/pipeline.ts、GenerationPage.tsx、EpisodeWorkspace.tsx、StoryboardPage.tsx、App.tsx。
- 前端新增：api/workflowTemplates.ts、EpisodeWorkflowConfig.tsx、DependencyView.tsx；差异列表保持在配置组件内，不为一次性结构额外建组件。
- 测试：Pipeline 范围/恢复/快照，模板 CRUD/隔离/合并/并发，图来源语义，前端逐项选择与浏览器完整路径。

## 执行顺序与收尾

1. 确认剧集阶段起点，固定字段 Schema 和验收样例。
2. 完成剧集查询范围、运行状态隔离和恢复测试。
3. 完成模板/剧集配置存储、白名单和修订控制。
4. 完成差异预览、逐项合并及生成配置传递。
5. 接入前端模板闭环，跑双剧集测试样例。
6. 完成依赖聚合接口和只读视图。
7. 回归后端、前端、构建、Lint；浏览器走真实组件和模拟 Provider，检查请求数量与内容。
8. 更新 Roadmap 实际完成项、测试记录和 pitfalls；清理本轮临时产物，记录本地提交结果。

本计划未承诺测试数量和通过结果。公开推送、Release 和真实付费调用不包含在此计划执行授权内。
