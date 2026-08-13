# 调研：Phase 7 — Script Engine（剧本引擎）设计依据

> 调研时间：2026-08-13。规则 75（Research Before Every Step）。

## 结论：分层生成流程（与现有「AI 整本撰写」交互一致）

成熟开源项目（Openframe / Jellyfish / novel-to-script-team / MediaGo Drama / Toonflow）的
「小说 → 剧本 → 分镜」流程高度一致：

```text
小说（章节）
  ↓ 改编分析 + 分集规划
Episode（分集，含分集大纲/情节点）
  ↓ 分集剧本写作
Scene（场景：slugline 场景标题 + 动作 + 对话）
  ↓ 剧本复核（业务/一致性/连续性）
Shot（分镜：景别 / 运镜 / 主体 / 动作 / 光影 / 台词 / 时长）
  ↓（Phase 8+）视觉 prompt → 图片 / 视频生成
```

关键共识：

1. **以「章节」为单位**做剧本、分镜与生成（Jellyfish 明确以 chapter 为单元）。
2. **分集规划独立成层**：先规划 Episode（事件边界、情感曲线、钩子/卡点），再写剧本
   （novel-to-script-team 的 episode-architect + emotion-architect）。
3. **每一层都允许人工确认/修改**（写第 N 集 → 复核第 N 集 → 再分镜）。
4. **剧本格式遵循影视规范**：Scene Heading（INT/EXT + 地点 + 日/夜）、
   Action（现在时、简洁动作块）、Character cue + Dialogue。
5. **Shot 是后续所有视觉生产的输入**，字段必须结构化，不能只存一段文字。

## Shot 数据结构（多家项目一致）

| 字段 | 说明 | 参考 |
| --- | --- | --- |
| shot_index | 镜头序号 | 通用 |
| shot_type | 景别：wide / medium / close-up / ECU | vision-builder、SceneCraft |
| camera | 运镜 / 机位 / 角度（推拉摇移、仰俯） | MediaGo Drama、Hitchcock |
| characters | 出现角色（引用角色资产） | Openframe、Jellyfish |
| action | 主体动作描述 | MediaGo Drama |
| lighting | 光影 / 氛围 | MediaGo Drama |
| dialogue | 台词 / 旁白 | MediaGo Drama |
| duration | 时长（秒） | shot-list-creator、Hitchcock |
| scene_id | 所属场景 | 通用 |
| prompt | 视觉描述（Phase 8+ 生成图片/视频用） | PenShot、SceneCraft |

## 参考项目

- Openframe（AI 漫剧工作台，project → script → character/prop/scene → shots → production）：
  https://github.com/murongg/openframe
- Jellyfish（短剧端到端，以 chapter 为单元拆解 shots、提取角色/场景）：
  https://github.com/Forget-C/Jellyfish
- novel-to-script-team（小说改编流水线：分析 → 分集规划 → 写集 → 复核 → 分镜）：
  https://github.com/Supreme-Ultimate/novel-to-script-team
- MediaGo Drama（剧本=场景标题/动作/对白；分镜=主体/动作/运镜/光影/台词/时长）：
  https://github.com/mediago-dev/mediago-drama
- Toonflow（开源一站式 AI 短剧创作工具）：https://github.com/HBAI-Ltd/Toonflow-app
- PenShot / story-shot-agent（剧本 → Sora/Veo-ready 分镜提示词）：
  https://github.com/neopen/story-shot-agent
- SceneCraft MCP（文本 → 场景 → 镜头计划）：https://github.com/snippetWizard/scenecraft_mcp
- 影视剧本格式规范（slugline / action / dialogue）：BBC Script Formatting、
  Arc Studio Script Formatting 101

## 对 Phase 7 实现的影响

1. **数据模型**：Episode（分集规划）→ Scene（场景：slugline/动作/对话）→ Shot（结构化字段）。
   现有 SQLite `episodes / scenes / shots` 表需核对字段并幂等迁移补齐。
2. **生成管线**：章节 → Episode 规划 → Scene 生成 → Shot 拆分，LLM 结构化输出（Pydantic 校验
   + 修复重试，沿用 `llm_json.py`）。
3. **交互**：复用「AI 整本撰写」向导模式——每层生成后人工确认（接受/重写/放弃），
   长任务 Job 化（Phase 10 之前先用内存 Job + 轮询，与 Story Analysis 一致）。
4. **UI**：沿用三栏工作台——左栏剧本树（分集/场景/镜头），中栏场景与镜头编辑，
   右栏 AI 生成向导 + Story Bible。
5. **与 Story Bible 联动**：角色/地点/道具从 Bible 注入，保证剧本与设定一致。
