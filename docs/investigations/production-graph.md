# 调研：Phase 11 — Production Graph（生产依赖图）设计依据

> 调研时间：2026-08-14。规则 75（Research Before Every Step）。

## 结论

Production Graph 的核心不是「自动重算」，而是「**精确知道每个产出依赖什么，改动后只提示受影响的下游节点，绝不自动重生成**」。
成熟工具的共同模式是：

1. 用**有向无环图（DAG）**表达生产链路（Novel → Story Bible → Script → Character → Storyboard → Image → Video）。
2. 节点用**稳定 ID** 作为跨环节锚点；边表达「产出 / 依赖」关系。
3. 改动时沿**出边**追溯受影响的下游节点（传递闭包），而不是全量重算。
4. 资产用**版本指针 + 快照**保证一致性；正在执行的任务锁定启动时的指针值。
5. 判断是否复用用**内容指纹 / 缓存键**（输入 + 上游祖先），上游未变则直接复用。

对本项目（AI Drama IDE Lite）而言，Phase 11 应只落地：

- 一个通用的**生产边表**（记录谁依赖谁的哪个版本）。
- **受影响节点检测**（下游传递闭包查询）。
- **重新生成计划**（列出受影响节点 + 状态，交给 UI 提示，**不自动重新生成**）。

边表的写入由后续 Phase 13/14 在生图/生视频时补齐；本轮先保证数据结构与查询能力不阻碍后续扩展。

## 1. 参考项目

### 1.1 DramaFlow（AI 短剧全链路，最直接参考）

文章：https://www.ctyun.cn/developer/article/836367719657541

关键设计：
- 结构化剧本单元赋予**稳定编号**，作为分镜 / 语音 / 字幕跨环节对齐的锚点。
- 把剧本转换为**任务依赖图**：人物设定 → 分镜绘制 → 关键帧插值，音轨时长反过来约束镜头时长；这些约束用有向边显式表达。
- 调度器按图做**拓扑排序**，识别可并行分支。
- 依赖图的核心价值：局部改动的影响面可精确圈定——某场台词改写，只沿出边追溯受影响下游节点，未波及镜头直接沿用，重算量可压到全量两成以内。
- **版本指针**：逻辑资产 → 指针 → 当前物理文件，历史版本链表保留；改人物设定后指针前移，所有引用该资产的镜头下次渲染自动用新版本；不满意可整体回退。
- **快照隔离**：正在执行的渲染锁定启动时的指针值，避免中途替换导致画面跳变。
- **增量重渲**：比对新旧依赖图、算差异集合，只重排受影响节点；差异计算必须覆盖间接依赖（台词变长 → 音轨时长 → 镜头时长 → 转场节奏）。

### 1.2 ComfyUI（图执行引擎 + 依赖感知缓存）

文档：https://deepwiki.com/Comfy-Org/ComfyUI/2.2-graph-execution-system

关键设计：
- `DynamicPrompt` 维护节点图；`ExecutionList` 做**拓扑排序 / 拓扑消解**，管理节点阻塞与执行状态。
- `add_strong_link(from, to)` 显式声明「to 依赖 from 的输出」。
- 缓存键 = 节点类型 + 输入值 + 连接输入的「**有序祖先链**」，据此判断节点是否需要重新执行；上游输入未变时直接跳过整条分支。
- 节点状态机：PENDING / IN_PROGRESS / COMPLETED / FAILED / CANCELLED。

### 1.3 Prism Pipeline DependencyViewer（资产依赖管理）

文档：https://prism-pipeline.com/docs/latest/api/api/core/scripts/dependency-viewer/

关键设计：
- 可视化场景 / 资产 / 产物之间的依赖图。
- 跟踪「哪些场景使用了哪些资产」。
- 更新引用到新版本、检测缺失依赖、批量更新引用、导出依赖报告。
- 递归处理「依赖的依赖」，形成依赖树。

### 1.4 Beatboard（创意流水线最小影响重算）

项目：https://devpost.com/software/beatboard

关键设计：
- 跟随依赖图确定「还有哪些受影响」，而不是盲目重生成整个项目。
- 显式建模关系（setup / punchline / escalation / callback），以确定受影响的最小部分。

## 2. 当前项目现状

### 2.1 已有实体（潜在节点）

- `projects`、`novels`、`chapters`
- `stories`（Story Bible JSON）
- `characters` / `locations` / `props`（从 Story Bible 同步）
- `assets`（角色/场景/道具资产卡，`asset_type + name` 映射到实体）
- `episodes` / `scenes` / `shots`
- `versions`（资产图片版本，`entity_type + entity_id` 通用引用）
- `jobs`（生成任务，`model_id / provider_id / capability / payload`）

### 2.2 已有的隐式边（表字段）

- `novels.project_id`、`chapters.novel_id`
- `stories.project_id`
- `episodes.novel_id`、`episodes.source_chapter_index`
- `scenes.episode_id`、`scenes.novel_id`
- `shots.scene_id`
- `assets.project_id + asset_type + name` ↔ `characters / locations / props`
- `versions.entity_type + entity_id` ↔ `assets`
- `versions.job_id` ↔ `jobs`

### 2.3 缺失的显式生成依赖

- `shots.characters` 是**自由文本**（`TEXT`），不是到 `assets` 的外键；目前无法回答「这个镜头用了哪个角色资产的哪个版本」。
- 资产图片生成后，没有「资产版本 → 镜头图片」的边。
- 没有「镜头图片 → 视频」的边（Phase 14 才会产生）。
- 没有统一的生产边表，只能靠各表字段拼凑，无法做统一的受影响节点检测。

## 3. 建议设计（Phase 11 MVP）

### 3.1 通用生产边表

沿用项目已存在的 `versions` 表「`entity_type + entity_id` 通用引用」模式，新增一张 `production_edges`：

```sql
CREATE TABLE IF NOT EXISTS production_edges (
    id               TEXT PRIMARY KEY,
    project_id       TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    upstream_type    TEXT NOT NULL,
    upstream_id      TEXT NOT NULL,
    upstream_version INTEGER,
    downstream_type  TEXT NOT NULL,
    downstream_id    TEXT NOT NULL,
    relation         TEXT NOT NULL,
    created_at       TEXT NOT NULL
);
```

字段说明：

- `upstream_type / upstream_id`：上游节点（生产者，例如 `asset` + `character_赵明_001`）。
- `upstream_version`：上游版本号，可空；版本化资产用它锁定「用了哪个版本」。
- `downstream_type / downstream_id`：下游节点（消费者，例如 `shot` + `shot_xxx`）。
- `relation`：关系类型，例如 `shot_references_asset` / `image_generated_from_asset` / `video_generated_from_image`。

索引：

```sql
CREATE INDEX idx_production_edges_project ON production_edges(project_id);
CREATE INDEX idx_production_edges_upstream ON production_edges(upstream_type, upstream_id, upstream_version);
CREATE INDEX idx_production_edges_downstream ON production_edges(downstream_type, downstream_id);
```

### 3.2 节点类型（枚举，建议常量而非 DB 表）

```text
novel
chapter
story_bible
character
location
prop
asset
episode
scene
shot
image_version
video_version
```

本轮不建节点表（避免重复已有实体表），节点身份直接由 `(type, id)` 表达，与 `versions` 表一致。

### 3.3 关键边示例

```text
asset(character_赵明_001, v3)
   └── relation: image_generated_from_asset
        └── image_version(v2)

asset(character_赵明_001, v3)
   └── relation: shot_references_asset
        └── shot(shot_03)

shot(shot_03)
   └── relation: image_generated_from_shot
        └── image_version(v2)

image_version(v2)
   └── relation: video_generated_from_image
        └── video_version(v1)
```

### 3.4 受影响节点检测

给定一个变更节点 `(type, id)`，沿 `upstream_type/upstream_id` 为起点的出边做 BFS，得到下游传递闭包。返回时：

- 按 `downstream_type` 分组（asset / shot / image_version / video_version）。
- 附带每个节点的状态（是否已有产物、当前版本）。
- **只提示，不自动重新生成**（规则 37：不自动重生成昂贵资产）。

### 3.5 重新生成计划

返回结构化结果供 UI 展示：

```json
{
  "changed_node": {"type": "asset", "id": "character_赵明_001", "version": 4},
  "affected": [
    {"type": "shot", "id": "shot_03", "relation": "shot_references_asset"},
    {"type": "image_version", "id": "ver_xxx", "relation": "image_generated_from_asset"}
  ]
}
```

UI 据此展示「可能受影响：Shot 03、Image v2」，并提供 `[重新生成] [保留当前] [查看]`，由用户决策。

## 4. Phase 11 边界

- 本轮只实现 `production_edges` 表 + 受影响节点查询服务 +（可选）简单的受影响结果 API。
- 边的**写入时机**在后续阶段：Phase 13 生图成功后写 `asset → image_version`、`shot → image_version`；Phase 14 写 `image_version → video_version`。
- 不提前实现完整 UI；不实现自动 Model Router；不自动重新生成。
- 先把 `shots.characters` 的「自由文本 → 结构化引用」问题留到 Phase 12/13 一起处理，本轮不在脚本层大改。

## 5. 参考来源

- DramaFlow：https://www.ctyun.cn/developer/article/836367719657541
- ComfyUI Graph Execution System：https://deepwiki.com/Comfy-Org/ComfyUI/2.2-graph-execution-system
- Prism Pipeline DependencyViewer：https://prism-pipeline.com/docs/latest/api/api/core/scripts/dependency-viewer/
- Beatboard：https://devpost.com/software/beatboard
