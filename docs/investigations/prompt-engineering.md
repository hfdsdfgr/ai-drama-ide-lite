# Prompt Engineering 调研与改造记录

> 日期：2026-09-02
> 起因：用户反馈「运镜单调不专业」「分镜都是 5 秒」「测试画面人物对不上、画风不统一」，要求调研整个项目所有提示词位置，并参考成熟开源产品统一优化。

## 一、项目提示词位置清单（15 处）

| 文件 | 用途 | 本次是否改动 |
|---|---|---|
| `app/services/ai_script.py` | 分集剧本 / 分镜生成（`_EPISODE_SYSTEM` / `_SHOTS_SYSTEM`） | 是（分镜决策引擎规则） |
| `app/services/image_prompt_builder.py` | 资产生图 / 分镜生图提示词组装 | 是（负面词 + 画风锁定） |
| `app/services/video_generation_service.py` | 分镜图生视频提示词 | 是（运动 + 一致性约束） |
| `app/services/pipeline_service.py` | 一键生产：分镜视频时长 | 是（时长硬编码 bug） |
| `app/services/story_analysis.py` | 逐章抽取 + Story Bible 合并 | 是（资产卡隔离约束） |
| `app/services/asset_service.py` | 资产卡补全 | 否（已有隔离约束，已够） |
| `app/services/ai_novel.py` | 小说大纲 / 章节 / 续写 | 否（需求已覆盖） |
| `app/services/dialogue_planning_service.py` | 台词归属拆分 | 否 |
| `app/services/dialogue_review_service.py` | 台词一致性审核 | 否 |
| `app/services/story_consistency_service.py` | 剧情衔接审核 | 否 |
| `app/services/visual_review_service.py` | 视觉一致性审核 | 是（画风 + 多余文字检查） |
| `app/services/llm_json.py` | JSON 解析修复重试 | 否 |
| `app/services/adapters/*.py` | 各 Provider 请求体 | 否（一致性靠参考图机制，适配器已就位） |

## 二、开源参考调研

### 1. c-wang-dev/storyboard-master（分镜大师）— 主要参考

- 地址：https://github.com/c-wang-dev/storyboard-master
- License：MIT
- 亮点：
  - **确定性决策引擎**：剧本片段 → 六维特征（内容类型/信息焦点/情绪/权力/空间/节奏）→ 五张决策表（景别/角度/运镜/光影/节奏）→ 冲突仲裁（情绪 > 信息 > 权力）。
  - **三档时长法**：5s（单一动作/反应）/ 10s（一组连贯动作或几句台词）/ 15s（完整对话/小高潮），按信息点数定档，档位 × 节奏定图数。
  - **表演一致性四层**：性格范式 → 角色锚定卡 → 禁止表演清单 → 远景降级。
  - **多帧一致性**：定妆照/三视图/场景设定图先行，参考图贯穿全片，首帧即身份；时间同义归一；一次只改一个变量。
  - **物理后果速查表**：所有含动作镜头强制注入重量/摩擦/环境反应，避免画面「飘」。
  - **负面词分层**：A 层进 negative prompt（deformed, text, watermark, oversaturated, overexposed, stiff expression, frozen face），B 层进设计决策。
  - **电影语言语法**：轴线与越轴、三匹配（位置/动作/视线）、切点在动作中段、对话场外反拍/内反拍/过肩。

### 2. neopen/story-shot-agent（PenShot）

- 地址：https://github.com/neopen/story-shot-agent
- LangGraph 分镜流水线，跨片段角色一致性，输出 Sora/Veo 提示词。本项目的分镜输出不是多智能体流水线，只吸收其「跨片段一致性锚点」思路（本项目已通过参考图机制实现）。

### 3. haya-hello/AI-real-person-short-drama-workflow

- 真人短剧工作流模板，连镜稳定/道具连续/表演节拍。真人域与本项目动漫域差异大，仅参考其「道具连续性」思路（本项目在 `_SHOTS_SYSTEM` 中要求道具唯一名称与状态连续）。

## 三、本次采纳的规则

### 分镜生成（`ai_script.py` `_SHOTS_SYSTEM`）

1. 景别按信息焦点决策（环境→远景/全景；关系→中景；情绪→近景/特写；细节→大特写）；整场至少 3 种景别，连续三镜不得同景别。
2. 角度按权力关系决策（仰/俯/平/POV/荷兰角），写入 camera 并标明机位高度与角度。
3. 运镜按运动目的决策（跟拍/推近/拉远/摇摄/手持/固定/升降/环绕/甩镜/航拍），相邻镜头禁止相同运镜。
4. 光影按情绪基调决策（低调冷色/高调暖色/硬侧光/逆光剪影/冷月光），写明光源与色温。
5. 时长三档 5/10/15 秒，同一场至少两种档位；一键生成视频时使用分镜自身时长（修复 `duration=5` 硬编码）。
6. 构图每镜选 1-2 种；对话场遵循外反拍/内反拍/过肩 + 反应镜头；保持轴线、禁止无动机越轴；三匹配。
7. 含动作镜头强制注入物理后果（重量/摩擦/环境反应）。
8. 角色/场景/道具必须用唯一名称，禁止代称；prompt 开头统一画风声明，角色跨镜头外观零漂移。
9. prompt 用中文电影行业术语，禁止 medium close 等英文混排，画面禁止文字/字幕/水印。

### 生图（`image_prompt_builder.py`）

1. 全局负面词扩充：`oversaturated, overexposed, stiff expression, frozen face, disfigured, duplicate, extra eyes, missing fingers`。
2. 分镜图追加画风锁定：`consistent art style, unified visual style across all shots, same art direction as references, cinematic film still`。
3. 角色三视图追加专项负面词：`inconsistent face between views, different outfits between views, smiling, exaggerated expression`。

### 生视频（`video_generation_service.py`）

- 图生视频提示词统一追加运动 + 一致性约束：动作自然连贯、符合重力物理、外观与首帧/参考图一致、画风统一、无文字字幕水印。

### 资产卡（`story_analysis.py` 合并阶段）

- 三类资产严格隔离：角色 reference_prompt 只能描述自身，严禁混入道具/地点/其他角色；地点与道具同理。

### 视觉审核（`visual_review_service.py`）

- 角色/场景/服装/连续性审核同时检查「画风是否统一」与「画面是否出现多余文字/字幕/水印」。

## 四、未采纳 / 边界

- 不做完整「决策引擎代码」（六维特征 → 五张决策表 → 仲裁），P1/Phase 17-18 Director Agent 之前保持 LLM 内联规则，避免提前引入新子系统。
- 不做「档位建议表 + 用户确认」交互（属于 Storyboard UI 层），当前用确定性 JSON 规则约束。
- 不引入角色锚定卡/性格范式库（需要独立数据实体与用户录入流程，超出本次提示词改造范围；现有 Story Bible reference_prompt 已承担锚定作用）。
- 视频时长归一化仅限 5 的倍数档位（5/10/15），模型侧限制（如智谱 >10s 截断到 10s）由 Adapter 负责，不在此层伪造。

