# AI Drama IDE Lite

> 面向个人创作者的桌面级 AI 漫剧创作 IDE。
>
> **用户是导演，AI 是制作团队。**

## 下载与安装

**最新版本：v0.2.4**（Windows x64 + macOS Apple Silicon）

下载地址：[GitHub Releases](https://github.com/hfdsdfgr/ai-drama-ide-lite/releases)

### Windows

1. 下载 `ai-drama-ide-lite-windows-x86_64-setup.exe`；
2. 双击安装（按当前用户安装，无需管理员权限；缺少 WebView2 时会自动引导安装）；
3. 从开始菜单或桌面快捷方式启动。

### macOS

1. 下载 `ai-drama-ide-lite-macos-aarch64.dmg`；
2. 打开 dmg，把 `AI Drama IDE Lite` 拖入「应用程序」；
3. 首次打开若提示「无法验证开发者」，请在「应用程序」中**右键 → 打开**，并在弹窗中确认；
4. 若仍提示「应用已损坏」，打开「终端」执行以下命令后重新打开即可：

   ```bash
   xattr -dr com.apple.quarantine "/Applications/AI Drama IDE Lite.app"
   ```

> 当前 macOS 版使用 ad-hoc 签名（未做 Apple 开发者公证），Windows 版未做代码签名，杀毒软件/系统可能提示未知发布者，属正常现象。

### 自动更新

应用内置自动更新（设置 → 检查更新）。Windows 与 macOS 都支持，更新包同样来自 GitHub Releases。

### 系统要求

- Windows 10/11 x64（需 WebView2 运行时，安装包会自动处理）
- macOS 12+（Apple Silicon，即 M1/M2/M3 及更新机型；Intel Mac 暂未提供）
- 需要可访问互联网（调用 AI Provider API 与自动更新）
- 需要至少一个 AI 模型提供商的 API Key（OpenAI 兼容、阿里云百炼、智谱、火山方舟、硅基流动等）

---

## 快速上手（使用教程）

整个产品遵循一条流水线：**小说 → Story Bible → 剧本 → 资产 → 分镜 → 图片 → 视频**。每一步都由 AI 生成、用户审核后确认进入下一步，随时可以重做。

### 第 1 步：配置 AI 模型（设置）

首次使用先到「设置」添加模型提供商：

1. 点击「添加 Provider」，选择一个预设（如 OpenAI、阿里云百炼、智谱、火山方舟、硅基流动、Ollama 等），或自定义 Base URL；
2. 填入 API Key（自动保存到系统凭据管理器，不落盘到项目文件）；
3. 「拉取模型」获取该提供商的模型列表，按需启用文本 / 图片 / 视频模型；
4. 建议分别设置一个默认「图片模型」和默认「视频模型」，生成界面会自动读取已启用且通过能力检测的模型。

> 提示：不同用途需要不同模型——写小说/生成剧本用**文本模型**，生成角色/场景/道具图用**图片模型**，分镜视频用支持图生视频的**视频模型**。界面上的信息图标会提示 API Key 在哪里申请。

### 第 2 步：创建项目

在「项目」页新建项目（如「我的第一部动画」），之后的小说、剧本、资产、视频都挂在项目下。

### 第 3 步：创作小说

在「小说工作室」中：

- **新建小说**：设置题材、受众、情节复杂度（1–10，越简单越接近爽文），输入初步想法，由 AI 撰写完整章节；
- **导入小说**：支持 TXT / Markdown / DOCX，自动按标题分章；
- 章节支持 AI 续写 / 扩写 / 重写，正文可随时手动编辑，预览时可将当前章节导出为 TXT。

### 第 4 步：生成 Story Bible（故事圣经）

对小说运行「分析故事」，AI 会整理出世界观、角色、地点、道具等设定。这些是后续所有生成的"事实依据"，可以手动修正。

### 第 5 步：生成剧本

按章节生成分集剧本（场景 + 对白 + 分镜描述），可逐场景生成分镜（镜头类型、景别、运镜、人物、动作、光线）。

### 第 6 步：生成资产

在资产页为角色 / 场景 / 道具生成参考图：

- 角色设定图为**三视图**（正面 / 侧面 / 背面），保证后续镜头里形象一致；
- 可切换画风（动漫、3D、国风、写实等），建议动漫风可避免真人风控问题；
- 每张图都有版本历史，可对比、可回退。

### 第 7 步：分镜与视频

在分镜页：

1. 选中镜头 → 选择图片模型 → 「生成分镜图」（自动引用场景中出现的资产）；
2. 选中视频模型 → 可勾选「带台词/对白生成」→ 「生成视频」；
3. 生成的视频可直接预览，不满意可换模型或改提示词后重做当前镜头。

### 第 8 步：生成中心一键生成

在「生成中心」可以一键跑完整流水线（分析 → 剧本 → 资产 → 分镜 → 图片 → 可选视频），每阶段默认暂停等您确认；也可单独运行质量审查（视觉一致性 / 剧情一致性 / 台词审核）与场景、分集视频合成。

### 常用提示

- **费用**：所有 AI 生成都调用您自己的 API，按服务商计费。生成前界面会明确列出阶段与模型，视频生成默认不勾选，避免误触发费用。
- **真人风控**：若视频模型提示"画面含真实人脸"，把画风改成动漫 / 3D 后重新生成角色和分镜图即可。
- **形象一致性**：保持角色一致的要点是先生成三视图设定图，再让分镜图引用它。
- **数据安全**：项目数据保存在本机（Windows：`%LOCALAPPDATA%\AI Drama IDE Lite\data`；macOS：`~/Library/Application Support/AI Drama IDE Lite/data`），API Key 存系统凭据管理器。

---

## 这是什么

AI Drama IDE Lite 是一个 Story-to-Drama 的 AI 生产 IDE，把「小说 → 漫剧」的完整生产过程放进一个可观察、可干预、可暂停、可重做的桌面应用。

它不是「输入小说 → 黑箱生成视频」的工具，而是一条用户可以全程监督、随时叫停的生产流水线。

```text
灵感
 ↓
原创小说 / 导入小说
 ↓
Story Bible
 ↓
剧本
 ↓
人物 / 场景 / 道具资产
 ↓
分镜
 ↓
分镜图片
 ↓
图生视频
```

分工：

- **用户负责**：故事方向、审核、修改、选择、审美判断、最终决策
- **AI 负责**：小说分析、故事整理、剧本生成、资产提取、分镜生成、生图、图生视频等重复性生产

## 核心设计原则

1. **AI 不能是黑箱**：用户始终知道 AI 在做什么、已完成什么、当前进度、下一步是什么。
2. **用户随时可以停止**：所有耗时任务支持 Pause / Cancel / Retry / Stop，取消必须真实终止后台 Job。
3. **已生成内容不丢失**：每个成功生成的资产立即持久化，且全部版本化。
4. **局部重做**：一个镜头不满意就重做这个镜头，而不是整个项目重新生成。
5. **修改必须考虑依赖**：资产变更沿 Production Graph 自动检测受影响镜头并提示用户，不偷偷覆盖旧内容。
6. **用户拥有最终决定权**：AI 可以推荐、分析、生成、判断，但不能未经允许覆盖重要资产。

## 技术栈

| 层 | 选型 |
| --- | --- |
| 桌面壳 | Tauri 2 |
| 前端 | React + TypeScript |
| 后端 | Python + FastAPI |
| 数据 | SQLite + 本地文件系统 |
| 实时通信 | WebSocket / SSE |

## 核心架构

最核心的架构原则：**模型是基础设施，不是业务逻辑。** 任何 AI 模型都不能直接穿透分层进入业务逻辑。

```text
USER
 ↓
DIRECTOR UI
 ↓
PRODUCTION GRAPH
 ↓
GENERATION ENGINE
 ↓
MODEL ROUTER
 ↓
CAPABILITY ENGINE
 ↓
MODEL REGISTRY
 ↓
PROVIDER MANAGER
 ↓
MODEL ADAPTER
 ↓
API
 ↓
JOB MANAGER
 ↓
LOCAL ASSETS
```

要点：

- **Provider 抽象**：LLM / Image / Video 三类 Provider，通过 Adapter 归一化请求、响应与错误；业务代码禁止出现 `if model == "xxx"`。
- **Capability 优先**：任务按能力（`text_to_image`、`image_to_video` 等）匹配模型，UI 也按能力动态显示参数。
- **Job 化**：所有耗时操作统一为 Job（Queued / Running / Paused / Completed / Failed / Cancelled），支持排队、进度、重试、取消、持久化。
- **版本化资产**：人物、场景、道具、分镜图、视频都有版本历史，可对比、可恢复。
- **API Key 安全**：密钥存入系统安全存储（Windows Credential Manager / Keychain / Secret Service），绝不进项目文件、Git 或日志。

## 项目结构（规划）

```text
ai-drama-ide/
├── apps/
│   ├── desktop/        # Tauri 2 + React + TypeScript
│   └── backend/        # Python FastAPI
├── packages/           # story / script / asset / storyboard / generation 等引擎
├── agents/             # director / story / script / asset / quality
├── providers/          # llm / image / video
├── adapters/           # llm / image / video
├── workflows/          # character / scene / storyboard / image / video
├── docs/               # 决策记录与开发笔记
└── tests/
```

## 开发路线

完整计划见 [ROADMAP.md](ROADMAP.md)（Phase 0–23，从项目初始化到 MVP 发布）。摘要：

- **Phase 0–2**：桌面应用骨架、Project 系统、Novel Studio
- **Phase 3–5**：Provider 基础系统、API 三级验证 + Capability Engine、Adapter 系统（第一、第二核心阶段）
- **Phase 6–9**：Story Engine、Script Engine、Asset Engine、资产版本系统
- **Phase 10–14**：Job 系统、Production Graph、Storyboard UI、生图、图生视频
- **Phase 15–19**：Generation Center、中断系统、Model Router、Director Agent、Quality Agent
- **Phase 20–23**：端到端 Demo、打包、MVP Release、MVP Demo

优先级：

- **P0（MVP 必须存在）**：Project / Novel / Story Bible / Script / Asset / Provider / Capability / Adapter / Job / Storyboard / Image / Video / Interrupt
- **P1（MVP 后）**：Model Router / Director Agent / Quality Agent
- **P2（后续）**：配音、BGM、音效、时间线、自动剪辑、本地模型、ComfyUI、云 GPU

## 黄金路径

开发过程中始终维护一条**任何时候都必须可运行**的完整链路：

```text
Create Project
 → Input Novel
 → Analyze Novel
 → Generate Story Bible
 → Generate Script
 → Extract Character
 → Add Image API → Test API → Detect Capability
 → Generate Character Image
 → Generate Storyboard
 → Generate Shot Image
 → Add Video API → Test API → Detect image_to_video
 → Generate Video
 → Preview
```

任何新功能若破坏这条路径，必须先修复回归再继续。

## 开发规则

所有编码工作必须遵守：

- [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) — 74 条强制开发规则（先读后写、先计划后实现、不 Fake、不猜架构、不扩大范围、测试边界、密钥安全等）
- [DEVELOPMENT_PITFALLS.md](DEVELOPMENT_PITFALLS.md) — 同类型工程的踩坑记录（环境、网络、构建、打包、编码）

## 当前状态

**当前进度：MVP 功能已完成并发布 v0.2.4（Windows + macOS 双平台）**，完整计划见 [ROADMAP.md](ROADMAP.md)。

已完成的核心能力：

- **桌面应用**：Tauri 2 + React + FastAPI，Windows NSIS 安装包 / macOS dmg，内置自动更新
- **项目管理**：创建 / 导入 / 导出 / 软删除，自动保存与重启恢复
- **小说**：AI 创作（题材 / 受众 / 情节复杂度）+ TXT / MD / DOCX 导入 + 章节 AI 续写 / 扩写 / 重写
- **Story Bible**：AI 分析故事，整理世界观 / 角色 / 地点 / 道具设定
- **剧本引擎**：分集剧本、场景、分镜（镜头类型 / 景别 / 运镜 / 光线）
- **资产系统**：角色三视图设定图 / 场景 / 道具参考图，画风可选，版本历史可回退
- **分镜与视频**：分镜图生成（自动引用资产）、图生视频（支持带原生对白/音效的模型）
- **Provider / Adapter**：OpenAI 兼容 + 阿里云百炼 + 智谱 + 火山方舟（Seedance）+ 硅基流动等；能力检测驱动模型下拉，不做多模型并行
- **生成中心**：一键流水线（每阶段可暂停确认）、质量审查（视觉一致性 / 剧情一致性 / 台词审核）、场景 / 分集视频合成
- **Job 系统**：所有耗时任务持久化（排队 / 运行 / 暂停 / 完成 / 失败 / 取消），可中断可恢复
- **API Key 安全**：系统凭据管理器存储，不落项目文件 / 日志 / Git

已发布版本：

- **v0.2.4**：修复 macOS 后端无法启动（sidecar 丢失可执行权限）
- **v0.2.3**：修复 macOS 启动闪退（sidecar 路径查错导致 panic）
- **v0.2.2**：macOS 改用 ad-hoc 签名，修复「应用已损坏」无法打开的问题
- **v0.2.1**：Windows x64 + macOS Apple Silicon，CI 自动构建发布（见 [Releases](https://github.com/hfdsdfgr/ai-drama-ide-lite/releases)）
- **v0.2.0**：完整 AI 漫剧生产流水线（一键生成 + 质量审查 + 分镜合成 + 自动更新）

## 开发模式

环境要求：Python 3.12+、Node.js 20+、Git。

### 1. 启动后端

```powershell
cd apps/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. 启动前端（浏览器开发模式）

```powershell
cd apps/desktop
npm install
npm run dev
```

打开 http://localhost:5173 即可使用。

### 3. 桌面模式（Tauri，仅 Windows 开发环境）

环境要求：Rust（GNU 工具链）+ MinGW（`C:\Qt\Tools\mingw1310_64`）。

```powershell
# 在仓库根目录执行
.\scripts\tauri-dev.ps1
```

该脚本会自动创建无空格 junction 路径（`C:\Users\Administrator\ai-drama-ide` → 本项目）并从该路径启动 `tauri dev`，以绕过 MinGW 的路径空格问题。

macOS / Linux 开发环境直接在本机安装 Rust 工具链后执行 `npm run tauri dev` 即可（需先启动后端）。

### 4. 运行测试

```powershell
# 后端
cd apps/backend
.\.venv\Scripts\python.exe -m pytest

# 前端
cd apps/desktop
npm test
```

## 文档索引

- [DEVELOPMENT.md](DEVELOPMENT.md) — 产品规格（需求与设计）
- [ROADMAP.md](ROADMAP.md) — 开发路线图（阶段计划与完成标准）
- [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) — 开发规则（强制，编码前必读）
- [DEVELOPMENT_PITFALLS.md](DEVELOPMENT_PITFALLS.md) — 工程踩坑记录（参考经验）
