# AI Drama IDE Lite

> 面向个人创作者的桌面级 AI 漫剧创作 IDE。
>
> **用户是导演，AI 是制作团队。**

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

**Phase 0（项目初始化）进行中**。已完成：

- Git 仓库、基础目录结构（`apps/desktop` + `apps/backend`）
- Python FastAPI 后端：环境变量、日志、错误处理、健康检查、最小 Project 接口（JSON 文件存储，Phase 1 迁移 SQLite）
- React + TypeScript 前端：Vite 代理、统一 API 客户端、Project 页面（创建/保存/打开）、Settings 占位页
- 测试：后端 pytest 5 项、前端 Vitest 3 项；lint / build 通过；端到端验证通过
- Tauri 2 桌面壳：已初始化并通过编译验证（Rust GNU 工具链 + MinGW）
- **注意**：MinGW 工具链无法处理含空格的构建路径（`G:\Vibe Coding\AICV`），桌面构建必须通过无空格 junction 路径，见下方「桌面模式」。

**Phase 1（Project System）已完成**：

- SQLite 结构化存储（基线 schema 覆盖 Novel/Story/Characters/Locations/Props/Episodes/Scenes/Shots/Assets/Jobs/Versions）
- Project CRUD（软删除）+ 自动保存 + 重启恢复
- 项目导入 / 导出（zip + manifest，含 zip-slip 防护）
- Phase 0 JSON 项目自动迁移归档；Asset ID / Project ID 规范
- 测试：后端 pytest 16 项、前端 Vitest 5 项；lint / build 通过；端到端验证通过

## 快速开始

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

### 3. 桌面模式（Tauri）

环境要求：Rust（GNU 工具链）+ MinGW（`C:\Qt\Tools\mingw1310_64`）。

```powershell
# 在仓库根目录执行
.\scripts\tauri-dev.ps1
```

该脚本会自动创建无空格 junction 路径（`C:\Users\Administrator\ai-drama-ide` → 本项目）并从该路径启动 `tauri dev`，以绕过 MinGW 的路径空格问题。

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
