# 调研：Phase 12 — Storyboard UI（分镜板界面）设计依据

> 调研时间：2026-08-14。规则 75（Research Before Every Step）。

## 结论

Storyboard UI 不是「把镜头列表换个样式」，而是把「分集 → 场景 → 镜头」变成**可视化分镜板**：
场景作为横向区块/泳道，镜头作为可拖拽排序的卡片；点击卡片进入详情编辑；每张卡片明确显示
景别、运镜、时长和生成状态。核心原则：

1. **场景即板块**：一个场景一段，镜头按 `order_index` 排列，视觉上像电影分镜板。
2. **镜头即卡片**：卡片显示画面占位框 + 镜头号 + 景别 + 时长 + 运镜 + 状态徽标。
3. **拖拽排序**：改变 `order_index`，但不重写现有 shot CRUD 业务逻辑。
4. **卡片点击 → 详情编辑**：不要把所有字段塞进卡片（信息过载），编辑细节放右侧面板或弹层。
5. **生成状态可见**：卡片显示「待生成 / 生成中 / 已生成 / 失败」，为 Phase 13 生图预留状态位。

本轮**只改 UI / 交互 / 信息架构**，不重新实现 shot 业务逻辑、不新增生图功能、不破坏现有脚本生成流程。

## 1. 参考项目

### 1.1 StudioBinder（影视分镜板，最直接参考）

页面：https://www.studiobinder.com/storyboard-software/

关键设计：
- 每个场景链接到自己的 board，保持与剧本流程对齐。
- Shot Specs：镜头规格（相机运动、构图、景别）模板化选择。
- 支持 aspect ratio、列布局（几列）、镜头编号规则、颜色标注特殊镜头。
- 图片编辑 / 注释箭头 / 草图扫描。
- 按地点 / 场景 / 拍摄日分组组织 board。

### 1.2 Milanote（自由画布 + 卡片拖拽）

页面：https://milanote.com/product/storyboarding

关键设计：
- 无限画布 + 简单拖拽，卡片可自由重排。
- 卡片承载图片 / 视频 / 笔记，支持模板。
- 强调「几秒内重排，专注创作」。

### 1.3 Kanban / Trello 式看板（拖拽排序模式）

参考：https://www.npmjs.com/package/kanban-dnd 、 https://github.com/FelipeBattistotti/react-ui-kanban

关键设计：
- 泳道（lane）+ 卡片，卡片可在泳道内排序或跨泳道移动。
- 支持 pointer + keyboard 传感器（无障碍）。
- headless 库（自带样式少，便于接入项目自定义 CSS）。
- 内联编辑 / 编辑态切换，而非把所有编辑塞进卡片。

### 1.4 行业分镜工具的通用视觉

Dribbble：https://dribbble.com/shots/27239096-Instant-Live-Storyboard-Workspace-UI

共性：
- 深色沉浸 UI，结构化分镜卡片。
- 卡片统一规格（画面比例一致），信息密度适中。
- 明确区分「画面预览」与「镜头元数据」。

## 2. 当前项目现状

### 2.1 已有数据模型（足够支撑分镜板）

`shots` 表字段已包含分镜所需信息：

- `scene_id`、`shot_number`、`order_index`
- `shot_type`（景别）、`camera`（运镜）、`characters`、`action`、`lighting`、`dialogue`
- `duration`（秒）、`prompt`（视觉提示词）

### 2.2 当前 ScriptPage 的问题

现在的镜头展示是 `<ol className="shot-list">` 的**纵向列表 + 内联编辑**：

- 不像分镜板，更像剧本续写表单。
- 镜头信息全部展开，视觉密度低、层级不清。
- 没有「画面框」，用户无法形成「这是分镜」的认知。
- 编辑态直接把一堆 input/textarea 塞进卡片，卡片被撑得又长又乱。
- 没有拖拽排序，也没有生成状态可视化。

### 2.3 需要保留的现有功能

- 生成剧本 / 生成分镜（AI 向导，右侧面板）。
- 场景编辑、镜头编辑、镜头删除（两步确认）。
- 分集 / 场景 / 镜头数据流与后端 API。

Phase 12 只重排 UI，不动这些业务逻辑和 API。

## 3. 建议设计（Phase 12 MVP）

### 3.1 布局

沿用项目三栏结构，但中间工作区改成「场景分镜板」：

```text
Scene 01 — 室内·日
┌────────┐ ┌────────┐ ┌────────┐
│ Shot 1 │ │ Shot 2 │ │ Shot 3 │
│ wide   │ │ medium │ │ close  │
│ 3.0s   │ │ 2.0s   │ │ 1.5s   │
│ ○ 待生成│ │ ● 已生成│ │ ○ 待生成│
└────────┘ └────────┘ └────────┘

Scene 02 — 室外·夜
┌────────┐ ┌────────┐
│ Shot 4 │ │ Shot 5 │
└────────┘ └────────┘
```

- 场景块标题：slugline + 生成分镜按钮 + 编辑/删除。
- 镜头卡片：横向 flex-wrap 排列，按 `order_index` 排序。
- 卡片点击打开右侧/弹层「镜头详情」。

### 3.2 镜头卡片内容（克制，不塞满）

```text
[画面占位框 16:9]
Shot 01 · wide
3.0s · 推镜
[状态徽标]
```

- 画面占位框：Phase 13 前显示空框（固定比例），后续显示生成图片。
- 状态徽标：待生成 / 生成中 / 已生成 / 失败；本轮可先展示「待生成」占位，Phase 13 接真实状态。

### 3.3 详情编辑

- 点击卡片 → 打开详情面板（右栏或弹层），编辑景别 / 运镜 / 角色 / 动作 / 光影 / 台词 / 时长 / 提示词。
- 详情面板用「保存 / 取消」，不内联展开撑破卡片。
- 删除保留两步确认。

### 3.4 拖拽排序

- 目标：在场景内重排镜头 `order_index`。
- 方案：引入 `@dnd-kit/sortable`（维护活跃、支持键盘、headless，贴合项目自定义 CSS）。
  备选：原生 HTML5 DnD（无依赖，但无障碍和跨浏览器体验差）。
- 排序保存后调用现有 `update_shot` / 或新增一个批量 `reorder_shots` 接口写回 `order_index`。
- 不新增重型看板框架，避免引入整套 Kanban 抽象。

### 3.5 生成状态

- 本轮只定义状态位并显示占位「待生成」，不接真实 Job。
- Phase 13 生图时把 `shots` 与 `production_edges` / `jobs` 关联，回填真实状态。

## 4. Phase 12 边界

- 只改 ScriptPage 的中栏展示与镜头编辑交互，不重写 shot CRUD / AI 生成逻辑。
- 新增依赖仅 `@dnd-kit/core` + `@dnd-kit/sortable`（若采用），先说明理由。
- 不提前实现图片生成；画面框先占位。
- 不实现跨场景拖拽（复杂且非 MVP），先做场景内排序。

## 5. 参考来源

- StudioBinder：https://www.studiobinder.com/storyboard-software/
- Milanote：https://milanote.com/product/storyboarding
- kanban-dnd：https://www.npmjs.com/package/kanban-dnd
- react-ui-kanban：https://github.com/FelipeBattistotti/react-ui-kanban
- Instant Live Storyboard（Dribbble）：https://dribbble.com/shots/27239096-Instant-Live-Storyboard-Workspace-UI
