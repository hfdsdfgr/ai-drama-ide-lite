# 调研：Phase 8 — Asset Engine（资产引擎）设计依据

> 调研时间：2026-08-14。规则 75（Research Before Every Step）。

## 结论

AI 漫剧/动画生产中「角色一致性」是核心问题，成熟做法高度一致：
**固定人设描述（角色卡）+ 参考图（三视图锚点）**。角色卡是结构化、可复用的文本资产，
后续每次生图/生视频都拼接同一段固定描述，保证不「变脸」。

## 1. 角色卡（Character Sheet）标准结构

多个来源（PixAI、Seedance 教程、AI 漫剧实战、ArcReel、ai-character-designer）收敛为：

| 维度 | 内容 | 说明 |
| --- | --- | --- |
| 身份标签 | 名字 / 身份 / 年龄 / 阵营 | 剧情与角色定位 |
| 面部特征 | 脸型、五官、瞳色、肤色 | 3-4 个面部关键特征最有效 |
| 发型发色 | 长度 / 发型 / 发色 | 必须明确，防漂移 |
| 服装配饰 | 具体单品、颜色、材质、层次 | 越具体越稳定 |
| 体型姿态 | 体态 / 身高 / 姿势习惯 | 可选但有用 |
| 特殊标记 | 泪痣 / 耳钉 / 疤痕 / 纹身 | 一致性锚点 |
| 性格标签 | 3-5 个关键词 | 供剧情/表演使用 |
| 风格参考 | 写实 / 动漫 / 国风 / 赛博 | 全剧统一风格 |

参考：Seedance-2.5 prompting（age/heritage + skin tone + facial landmarks + gaze/emotion +
hair + garment cut/material/wear + build/posture/temperament）。

## 2. 角色一致性方法（漫剧最关键）

1. **固定人设**：性别、发型、发色、瞳色、脸型、身高、气质——每个分镜提示词都带。
2. **参考图/锚点图**：三视图（front/side/back）+ 表情图 + 服装图；
   参考图语法如 PixVerse `@ref_name`、Venice `@Element1 walks through @Image1`。
3. **一致性关键词**：`same character, consistent design, consistent outfit`。
4. 每个分镜提示词末尾固定加：「严格参照角色三视图，五官、发型、服饰、体态无改动」。

## 3. 场景 / 道具资产

- 场景：环境描述、时间段、光线、风格（Blender Studio Pipeline 的 location 资产）。
- 道具：描述、材质、参考（prop = 角色可互动的对象；环境元素可转为 prop）。

## 4. 参考来源

- PixAI OC/VTuber 角色卡与一致性指南：https://blog.pixai.art/en/oc-vtuber-character-sheet-generation-guide-building-a-consistent-ai-character-with-pixai/
- Seedance-2.5 prompting（人物可观测维度）：https://github.com/allenGKC/Seedance-2.5/blob/main/skill/seedance-25/references/prompting.md
- AI 漫剧角色身份卡（五类特征锁定一致性）：https://post.smzdm.com/p/al3p055e/
- 角色设定图提示词模板（身份/年龄/阵营/性格标签）：https://m.toutiao.com/article/7658185505158201898/
- ArcReel 资产生成（角色/场景/道具参考设计图，连贯段落描述外貌/服装/气质）：
  https://github.com/ArcReel/ArcReel/blob/main/agent_runtime_profile/.claude/skills/generate-assets/SKILL.md
- Blender Studio Pipeline（character/prop/location 资产分类）：https://studio.blender.org/tools/naming-conventions/file-types
- PixVerse / Venice 参考图语法（@ref_name）：https://docs.venice.ai/guides/media/reference-to-video

## 5. 对 Phase 8 实现的影响

1. **数据模型**：扩展现有 `characters / locations / props` 表（Phase 6 Story Bible 已用，
   当前只有 name/description）——角色加 identity/appearance/costume/personality/marks/style/
   reference_prompt；场景加 environment/time/lighting/style；道具加 material/reference。
   同时复用 `assets` 表（Asset ID `asset_type_slug_seq` + prompt + version，Phase 9 版本化）。
2. **生成流程**：Story Bible + 剧本 → LLM 提取规格化资产卡（Pydantic 校验 + 修复重试，
   沿用 `llm_json.py`）→ 生成 `reference_prompt`（固定人设提示词，后续生图必须复用）。
3. **一致性落地**：`reference_prompt` 存为资产字段；分镜生图/生视频时拼接
   「固定人设 + 场景动作 + consistent 关键词」；Phase 13 可生成三视图锚点图作为参考图。
4. **UI**：资产页（角色/场景/道具）沿用三栏工作台——左栏资产分类列表、中栏资产卡
   编辑（结构化字段 + reference_prompt 预览）、右栏 AI 提取向导。
