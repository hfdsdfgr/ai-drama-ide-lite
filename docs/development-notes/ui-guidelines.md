# UI / UX 开发规范（AI Drama IDE Lite）

> 来源：2026-08-13 系统性界面优化（Step 1-6）沉淀的经验。
> 后续所有 UI 改动必须遵守本规范；开发时先读本文件。

## 1. 设计基调

- 目标是「专业 AI 创作 IDE」，不是管理后台。深色 + 紫蓝主色，克制使用强调色。
- 参考方向：Scrivener / NovelCrafter / Linear / shadcn two-pane shell（布局结构、信息层级、视觉密度、交互方式），不机械复制视觉元素。

## 2. 布局结构

- **顶部**：品牌 + 模块导航（数组化模块表，active 实心高亮，未就绪模块显示「待建」）+ 右侧设置。
- **应用壳固定视口**（`height: 100svh; overflow: hidden`），页面/分区内部滚动，禁止页面整体滚动叠加多栏滚动。
- **三栏工作台**（小说页）：左栏项目结构（固定 250px）+ 中央工作区（flex）+ 右栏辅助面板（410px，含步骤条等紧凑组件时至少 410px）。
- **主从布局**（主页）：左列表 + 右详情/编辑，选中即编辑，避免「点编辑后卡片出现在页面底部」。
- 一个页面一个主滚动区；局部滚动（左栏树、右栏面板）用 `min-height: 0; overflow-y: auto`。

## 3. 设计 Token（index.css）

颜色、状态色、圆角、间距全部用 CSS 变量，禁止硬编码十六进制：

- `--bg / --bg-panel / --bg-elevated`（背景三级：深 → 面板 → 输入框凹陷）
- `--accent`（紫蓝主色）、`--success / --warning / --danger`
- `--border / --border-strong`、`--text / --text-h / --text-secondary / --text-faint`
- `--radius-sm (6px) / --radius-md (8px)`、`--space-1..6（4/8/12/16/24/32px）`
- 深色主题用 `@media (prefers-color-scheme: dark)` 覆盖同一组变量。

## 4. 组件规范

- **按钮层级**：默认按钮 = 次要（透明 + 描边）；主操作用 `.btn-primary`（实心主色，每页最多一个）；危险操作 `.button-danger`（浅红底红字）+ 默认态 `.button-ghost`（透明红字），确认态才醒目。删除按钮必须两步确认。
- **卡片 / 面板**：`.card` 用 `--bg-panel` + 边框 + `--radius-md`；右栏面板头（`.panel-head`）不是卡片，是面板标题 + 职责说明。
- **步骤条（Stepper）**：当前步骤实心圆高亮、完成绿色对勾、未开始空心圆；`flex: 0 1 auto`（步骤按内容宽），连接线 `flex: 1 0 auto` 填充剩余——**不要给步骤和连接线都用 `flex: 1`（basis 0），否则文字被均分裁切**。
- **文本域**：`textarea { resize: vertical }`，禁止横向拖拽破坏布局。
- **工具栏**：`.toolbar` 必须 `flex-wrap: wrap`，长说明文字不放进按钮行，单独 `<p className="muted">`。
- **信息层级**：模块职责清晰分离（小说页=创作，故事圣经=设定），同功能不重复出现（导航里有的模块，页面内不放第二个入口）。

## 5. 状态与生命周期

- **视图切换用常驻挂载 + display 显隐**（`.view-pane`），不要条件卸载——否则向导/选中项/章节状态在切换后全部丢失。
- 常驻页面需要「切回时刷新数据」：接收 `active: boolean` prop，`useEffect(..., [active])` 在激活时重新拉取（如模型列表）。
- **全局配置（模型/Provider）与项目无关**，页面挂载即加载，不依赖 projectId。
- 向导类长流程状态尽量持久化（如 AI 参数存小说 `ai_brief`），刷新/切换视图都可恢复。

## 6. 响应式与滚动

- 窗口最小 1080×700（Tauri 配置），1440×900 默认；1280/1440/1920 都要验证。
- 三栏 grid 用 `grid-template-columns: 250px minmax(0, 1fr) 410px` + `grid-template-rows: minmax(0, 1fr)` + `align-items: stretch`，保证各栏等高、不横向溢出。
- 避免多层滚动：应用不滚 → 每栏内滚。

## 7. 验证方法

- 无头浏览器截图 + 读图技能（see）检查：`msedge --headless=new --disable-gpu --virtual-time-budget=12000 --screenshot=...`（必须带 virtual-time-budget，否则异步请求未完成，截图会误报「没有可用模型」等假状态）。
- 每次 UI 改动跑：`npx tsc -b --force` + `npm run lint` + `npm test`。
- 布局问题优先截图确认再修，不要凭猜测改 CSS。

## 8. 本优化踩过的坑（快速索引）

1. 条件卸载 → 向导状态丢失（改常驻挂载）。
2. 项目选择入口放在「选中项目才渲染」的容器内 → 未选项目时整页空白（入口必须无条件渲染）。
3. 模型加载依赖 projectId → 未选项目时模型列表为空（全局数据挂载即加载）。
4. Stepper 步骤与连接线都 flex:1 → 文字被裁（步骤 flex:0 1 auto）。
5. 右栏 340/380px → 步骤条溢出（至少 410px + 紧凑间距）。
6. headless 截图不带 virtual-time-budget → 异步状态误报。
7. textarea 默认 resize:both → 横向拖拽破坏布局。
8. grid 自动放置顺序（input/textarea/button）→ 删除按钮落到摘要下方全宽（把按钮放标题后，摘要显式 grid-column 1/-1）。
