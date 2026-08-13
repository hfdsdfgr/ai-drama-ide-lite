# AI Drama IDE Lite — Roadmap

> 目标：构建一个可运行、可中断、可扩展的 AI 漫剧生产 IDE。
>
> 核心原则：
> 1. 先跑通，再扩展
> 2. 先真实 API，再做复杂自动化
> 3. 所有长任务必须 Job 化
> 4. 所有 AI 模型必须通过 Provider / Adapter 接入
> 5. 用户始终拥有暂停、停止、修改、重做的权利
> 6. 新增功能前优先研究 GitHub、官方 SDK、成熟开源项目
> 7. 单模型生成：一次 Generation Job 只调用一个 Model / 一个 Provider，不做多模型并行

# 产品约束 — 单模型生成（用户需求 2026-08-13）

> AI Drama IDE Lite **不采用多模型并行生成**，以避免不必要的 API 成本。

- Model 是**独立数据实体**，Provider 与 Model 分离（Provider 1 → N Model）。
- 用户在 Settings 中可添加 / 编辑 / 删除任意数量的 Provider 与 Model。
- Image Model 与 Video Model 必须明确区分（type / capabilities）。
- 生图界面动态读取「已配置且通过能力检测」的 Image Model；生视频同理读取 Video Model。**Model 下拉列表不得写死具体模型名称**。
- 用户可设置默认 Image Model 与默认 Video Model；生成界面可临时切换模型，无需进入 Settings。
- 一次 Generation Job 只绑定一个 Model、只调用一个 Provider。
- **不实现多模型并行生成。**
- 不提前实现复杂的自动 Model Router；但保留 Provider → Model → Adapter 的扩展结构，以便未来增加模型。
- 当前阶段（Phase 2）只需保证数据结构不阻碍以上设计，不提前实现完整 UI。

---

# Phase 0 — 项目初始化

目标：

> 让项目拥有一个稳定的桌面应用基础。

## Tasks

- [x] 创建 Git Repository
- [x] 初始化 Tauri（Rust GNU 工具链 + MinGW，含构建路径 workaround）
- [x] 初始化 React + TypeScript
- [x] 初始化 Python Backend
- [x] 建立 Frontend / Backend 通信（Vite 代理 + 统一 API 客户端）
- [x] 建立基础目录结构（apps/desktop + apps/backend）
- [x] 配置 ESLint / Formatter（oxlint + Prettier）
- [x] 配置测试环境（pytest + Vitest）
- [x] 建立环境变量管理（pydantic-settings + .env.example）
- [x] 建立日志系统（控制台 + 轮转文件）
- [x] 建立 Error Handling（AppError + 统一异常处理器）
- [x] 创建基础 Settings 页面（占位）
- [x] 创建基础 Project 页面（创建 / 保存 / 打开）

## 完成标准

能够：

```text
启动应用
 ↓
显示主界面
 ↓
创建 Project
 ↓
保存 Project
 ↓
重新打开 Project
Phase 1 — Project System

目标：

建立整个项目的数据基础。

Tasks
- [x] SQLite（基线 schema：projects/novels/stories/characters/locations/props/episodes/scenes/shots/assets/jobs/versions）
- [x] Project Model
- [x] Project CRUD（含软删除）
- [x] Local File Storage（项目目录 + 子目录结构）
- [x] Asset ID（asset_type_slug_seq 规范）
- [x] Project ID（proj_ 前缀）
- [x] 自动保存（前端 800ms 防抖）
- [x] 项目恢复（重启后数据完整；Phase 0 JSON 自动迁移归档）
- [x] Project Import（zip + manifest，防 zip-slip）
- [x] Project Export（zip）
数据结构
Project
├── Novel
├── Story
├── Characters
├── Locations
├── Props
├── Episodes
├── Scenes
├── Shots
├── Assets
├── Jobs
└── Versions
完成标准

能够：

新建项目
 ↓
关闭程序
 ↓
重新打开
 ↓
项目数据完整恢复
Phase 2 — Novel Studio

目标：

首先让用户可以把“故事”放进系统。

Tasks
- [x] TXT 导入（UTF-8 / GBK 编码探测）
- [x] Markdown 导入（按标题自动分章）
- [x] DOCX 导入（python-docx，按 Heading 分章）
- [x] Novel Editor（章节编辑器 + 自动保存）
- [x] Chapter Management（新增 / 重命名 / 编辑 / 删除）
- [x] 搜索（标题 + 章节内容）
- [x] 文本编辑
- [x] AI 创作入口（占位，明确标注 Phase 3 后可用）
- [ ] AI 续写 / 扩写 / 重写（依赖 Phase 3 — AI Provider 基础系统）
完成标准

用户可以：

新建小说
        或
导入小说
        ↓
编辑
        ↓
保存
Phase 3 — AI Provider 基础系统

这是第一个非常重要的阶段。

目标：

让用户能够自己填写 AI API。

Tasks
- [ ] Provider 数据结构（providers 表）
- [ ] Model 独立数据实体（models 表，Provider 一对多，含 type: llm/image/video）
- [ ] Provider Manager（添加 / 编辑 / 删除 / 启用 / 禁用）
- [ ] Model Registry（添加 / 编辑 / 删除 / 启用 / 禁用）
- [ ] Image Model 与 Video Model 明确区分
- [ ] API Key Storage（系统安全存储，不落项目文件）
- [ ] API Base URL / Model ID
- [ ] 默认 Image Model / 默认 Video Model（可配置，生成界面默认选中）
- [ ] Settings UI：Provider → Model 分层管理

> 本阶段**不实现自动 Model Router**（属 P1 / Phase 17）；MVP 生成流程由用户手动选择单一模型。
API 类型

第一阶段：

LLM
Image
Video
完成标准

用户可以：

Settings
 ↓
Add Provider
 ↓
填写 API
 ↓
保存
 ↓
重新打开应用
 ↓
API 配置仍然存在
Phase 4 — API Validation & Capability Engine

这是整个项目的第二个核心阶段。

目标：

不只是“保存 API”，而是真正判断它能不能工作。

API Test
Level 1
 Connection Test
 Endpoint Test
 Network Error Handling
Level 2
 API Key Test
 Authentication Test
 Model Test
Level 3
 Image Generation Test
 Video Generation Test
 User Confirmation Before Paid Test
Capability Engine

建立：

text_to_image
image_to_image
reference_image
character_reference

text_to_video
image_to_video
video_to_video
first_frame
last_frame
first_last_frame
Tasks
 Capability Schema
 Capability Registry
 Capability Detection
 Manual Capability Override
 Capability Validation
完成标准

用户添加模型后可以看到：

Model X

Image
✓ Text → Image
✓ Image → Image
✓ Reference Image

Video
✕ Text → Video
✓ Image → Video
✕ First / Last Frame
Phase 5 — Provider Adapter System

目标：

解决不同 AI API 的调用方式完全不同的问题。

Tasks
 Provider Interface
 Image Provider Interface
 Video Provider Interface
 LLM Provider Interface
 Adapter Interface
 Request Normalization
 Response Normalization
 Error Normalization
 Polling
 Webhook
 Async Job Support
核心结构
Generation Request
        ↓
Provider Manager
        ↓
Model Adapter
        ↓
Specific API

禁止：

业务代码
 ↓
if model == xxx
 ↓
API
完成标准

至少接入：

2 个不同 API / Provider

并证明：

更换模型不需要修改业务层代码。

Phase 6 — LLM Story Engine

目标：

让小说真正变成结构化故事。

Tasks
 Story Analysis
 Character Extraction
 Location Extraction
 Prop Extraction
 Event Extraction
 Timeline
 Story Bible
 Conflict Analysis
 Plotline
 Foreshadowing
Pipeline
Novel
 ↓
LLM
 ↓
Structured Story Data
 ↓
Story Bible
Phase 7 — Script Engine

目标：

把小说变成真正可以制作漫剧的剧本。

Tasks
 Episode Planning
 Scene Generation
 Dialogue Generation
 Action Description
 Camera Description
 Shot Generation
 Shot Duration
 Shot Ordering
Pipeline
Novel
 ↓
Story Bible
 ↓
Episode
 ↓
Scene
 ↓
Shot
完成标准

输入：

一章小说

输出：

Episode
 ├── Scene 01
 │    ├── Shot 01
 │    ├── Shot 02
 │    └── Shot 03
 │
 └── Scene 02
      ├── Shot 04
      └── Shot 05
Phase 8 — Asset Engine

目标：

把故事中的所有视觉元素结构化。

Tasks
Character
 Character Extraction
 Character Profile
 Appearance Specification
 Costume
 Personality
 Reference Prompt
Location
 Location Extraction
 Environment Description
 Time
 Lighting
 Style
Props
 Prop Extraction
 Prop Description
 Reference
完成标准

系统能够自动生成：

Characters
Locations
Props

并建立 Asset ID。

Phase 9 — Asset Version System

目标：

AI 生成结果不能覆盖用户作品。

Tasks
 Asset Version
 Prompt History
 Model History
 Reference History
 Version Compare
 Version Restore
 Current Version
 Delete Unused Version
示例
Lin Fan
├── v1
├── v2
└── v3 ← Current
Phase 10 — Generation Job System

这是整个项目最重要的基础设施之一。

目标：

所有耗时 AI 操作都必须变成 Job。

Tasks
- [ ] Job Model
- [ ] Job Queue
- [ ] Job Worker
- [ ] Job Status
- [ ] Progress
- [ ] Retry
- [ ] Cancel
- [ ] Pause
- [ ] Resume
- [ ] Error Handling
- [ ] Job Persistence
- [ ] Job 绑定单个 Model + 单个 Provider（一次生成只调用一个模型）

> 产品约束：不做多模型并行生成；并发只用于不同 Job 之间的调度，不用于同一生成任务的模型并行。
状态
Queued
Running
Paused
Completed
Failed
Cancelled
Phase 11 — Production Graph

目标：

让系统知道每个结果是怎么来的。

Graph
Novel
 ↓
Story Bible
 ↓
Script
 ↓
Character
 ↓
Storyboard
 ↓
Image
 ↓
Video
Tasks
 Dependency Graph
 Asset Dependency
 Shot Dependency
 Affected Node Detection
 Regeneration Planning
示例
Character v3
 ↓
Shot 03
 ↓
Image v2
 ↓
Video v1

如果 Character v3 修改：

检测受影响节点
 ↓
提示用户
Phase 12 — Storyboard UI

目标：

用户真正开始“导演”。

Tasks
 Storyboard Board
 Shot Card
 Shot Detail
 Drag & Drop
 Shot Edit
 Character Reference
 Scene Reference
 Camera
 Duration
 Prompt
 Generation Status
UI
Scene 01

[Shot 01] [Shot 02] [Shot 03]

Scene 02

[Shot 04] [Shot 05]
Phase 13 — Image Generation

目标：

跑通第一条真正的视觉生产链。

Pipeline
Shot
 ↓
Character Assets
 ↓
Location Assets
 ↓
Prompt Builder
 ↓
用户选择 Model（默认 / 临时切换，仅一个）
 ↓
Capability Engine（确认所选模型具备所需能力）
 ↓
Image Adapter
 ↓
API
 ↓
Job（绑定单一 Model + Provider）
 ↓
Image
 ↓
Asset Version
Tasks
 Text → Image
 Image → Image
 Reference Image
 Character Reference
 Batch Generation
 Image Preview
 Image Version
 Retry
 Cancel

> 单模型生成：一次 Job 只用一个 Model / 一个 Provider；不做多模型并行。自动 Model Router 留到 Phase 17（P1）。
Phase 14 — Video Generation

目标：

跑通 Image → Video。

Pipeline
Shot Image
 ↓
Video Prompt
 ↓
用户选择 Model（默认 / 临时切换，仅一个）
 ↓
Capability Engine（确认 image_to_video 能力）
 ↓
Video Adapter
 ↓
API
 ↓
Job（绑定单一 Model + Provider）
 ↓
Download
 ↓
Video Asset
Tasks
 Image → Video
 Duration
 Aspect Ratio
 Motion
 Camera Motion
 Video Preview
 Video Version
 Retry
 Cancel

第一阶段不要急着做：

Text → Video
First / Last Frame
Video → Video

先把：

Image → Video

跑通。

> 单模型生成：一次 Job 只用一个 Model / 一个 Provider；不做多模型并行。自动 Model Router 留到 Phase 17（P1）。

Phase 15 — Generation Center

目标：

把整个生产过程可视化。

UI
Generation Center

✓ Story Analysis
✓ Story Bible
✓ Script
✓ Characters

● Scenes
  3 / 8

○ Storyboard
○ Images
○ Videos

每个 Job：

● Generating Shot 08

Progress: 64%

[Pause]
[Stop]
Phase 16 — Interrupt System

目标：

用户随时可以叫停。

Tasks
 Stop Current Job
 Cancel Stage
 Pause Project
 Resume Project
 Stop All
 Preserve Completed Assets
 Recover Interrupted Jobs
必须验证

例如：

正在生成：

Shot 01 ✓
Shot 02 ✓
Shot 03 ●
Shot 04 ○
Shot 05 ○

点击：

Stop

结果必须：

Shot 01 ✓
Shot 02 ✓
Shot 03 Cancelled
Shot 04 Not Started
Shot 05 Not Started

而不是整个项目丢失。

Phase 17 — Model Router

目标：

系统能够根据任务自动选择合适模型。

> 自动 Model Router 属于 **P1（MVP 后）**。MVP 阶段不做自动路由：由用户在生成界面手动选择**单一**模型（默认或临时切换），本阶段保留该设计供后续实现。

Input
Task
+
Required Capability
+
Quality
+
Speed
+
Cost
Output
Recommended Model

例如：

Image → Video

Recommended:
Video Model A ★

Alternative:
Video Model B
Phase 18 — Director Agent

目标：

用户可以用自然语言控制制作流程。

例如：

“林凡的衣服换成黑色。”

“这个镜头不要近景。”

“第三幕节奏太慢，压缩两个镜头。”

“重新生成 Shot 08。”
Pipeline
User Command
 ↓
Director Agent
 ↓
Identify Target
 ↓
Modify
 ↓
Dependency Analysis
 ↓
Ask User
 ↓
Regenerate
Phase 19 — Quality Agent

目标：

在生成后自动检查。

检查：
Character Consistency
Scene Consistency
Costume Consistency
Story Consistency
Shot Continuity

例如：

⚠ Shot 18

林凡服装与 Character v3 不一致。

[Accept]
[Regenerate]
[Ignore]
Phase 20 — End-to-End Pipeline

这是第一个真正意义上的产品 Demo。

目标：

一键完成完整漫剧生产流程，但每一步都可以干预。

Demo
输入：

一章小说

点击：

Generate Drama

系统：

Novel Analysis
 ↓
Story Bible
 ↓
Script
 ↓
Characters
 ↓
Locations
 ↓
Props
 ↓
Storyboard
 ↓
Images
 ↓
Videos

用户可以随时：

Pause
Stop
Edit
Redo
Resume
Phase 21 — Packaging

目标：

打包成真正可以安装的软件。

Tasks
 Windows Build
 Installer
 Auto Update
 Crash Logging
 Settings Migration
 Project Migration
 API Key Migration
 Version Check

最终：

AI-Drama-IDE-Lite.exe
Phase 22 — MVP Release

MVP 必须满足：

✓ 桌面应用
✓ 项目管理
✓ 小说导入
✓ AI 小说创作
✓ Story Bible
✓ 剧本生成
✓ 人物 / 场景 / 道具提取
✓ API 自定义
✓ API 检测
✓ Model Registry
✓ Capability Engine
✓ Provider Adapter
✓ Job Manager
✓ Storyboard
✓ 图片生成
✓ 图生视频
✓ 实时进度
✓ Pause
✓ Cancel
✓ Retry
✓ Asset Version
Phase 23 — MVP Demo

最终 Demo 不需要追求十几分钟完整成片。

推荐：

1 章小说
 ↓
5~10 个 Scene
 ↓
20~40 个 Shot
 ↓
角色资产
 ↓
场景资产
 ↓
Storyboard
 ↓
生成关键帧
 ↓
生成部分视频

重点展示：

“从小说到漫剧生产流程”

而不是：

“AI 一次生成完整电影”
Development Priority

优先级必须遵循：

P0 — 必须存在

Project
Novel
Story Bible
Script
Asset
Provider
Model（独立实体，含默认 Image / Video Model）
Capability
Adapter
Job
Storyboard
Image
Video
Interrupt

> 单模型生成约束：一次 Generation Job 只绑定一个 Model / 一个 Provider，不实现多模型并行生成。
P1 — MVP 后

Model Router（自动路由，MVP 后；MVP 阶段由用户手动选择单一模型）
Director Agent
Quality Agent
Advanced Asset Control
P2 — 后续

Voice
Music
Sound Effects
Timeline
Auto Editing
Local Models
ComfyUI
Cloud GPU
Golden Path

开发过程中始终维护一条“黄金路径”：

Create Project
 ↓
Input Novel
 ↓
Analyze Novel
 ↓
Generate Story Bible
 ↓
Generate Script
 ↓
Extract Character
 ↓
Add Image API
 ↓
Test API
 ↓
Detect Capability
 ↓
Generate Character Image
 ↓
Generate Storyboard
 ↓
Generate Shot Image
 ↓
Add Video API
 ↓
Test API
 ↓
Detect image_to_video
 ↓
Generate Video
 ↓
Preview

任何时候这条路径都必须保持可运行。

Definition of Done

一个模块只有满足以下条件才算完成：

 功能可运行
 有错误处理
 有 Loading / Progress
 有 Cancel / Retry（适用时）
 数据可以持久化
 不会破坏已有项目
 有基础测试
 不存在 Fake API
 不存在 Fake Progress
 不存在未声明的 Mock
 UI 能明确告诉用户当前状态
 失败时给出可理解的错误信息
Core Architecture

最终架构：

                         USER
                           │
                           ▼
                    DIRECTOR UI
                           │
                           ▼
                   PRODUCTION GRAPH
                           │
                           ▼
                   GENERATION ENGINE
                           │
                           ▼
                     MODEL ROUTER
                           │
                           ▼
                  CAPABILITY ENGINE
                           │
                           ▼
                    MODEL REGISTRY
                           │
                           ▼
                   PROVIDER MANAGER
                           │
                           ▼
                     MODEL ADAPTER
                           │
                           ▼
                          API
                           │
                           ▼
                      JOB MANAGER
                           │
                           ▼
                     LOCAL ASSETS

核心原则：

模型可以换，Provider 可以换，API 可以换，但业务逻辑不能跟着模型改变。

Final Goal

AI Drama IDE Lite 最终应该做到：

用户：

“我想把这个故事做成 AI 漫剧。”

                ↓

AI Drama IDE Lite

                ↓

分析故事
                ↓
建立 Story Bible
                ↓
生成剧本
                ↓
整理角色
                ↓
整理场景
                ↓
整理道具
                ↓
建立分镜
                ↓
选择用户自己的 AI 模型
                ↓
生成视觉资产
                ↓
生成关键帧
                ↓
图生视频
                ↓
用户实时监督
                ↓
随时停止 / 修改 / 重做
                ↓
得到漫剧素材

产品的核心不是：

“AI 帮你生成视频。”

而是：

“AI Drama IDE 帮你管理从故事到漫剧的整个 AI 生产过程。”
