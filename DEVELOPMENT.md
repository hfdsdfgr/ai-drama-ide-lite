# AI Drama IDE Lite — Development Specification

> AI Drama IDE Lite 是一个面向个人创作者的桌面级 AI 漫剧创作工具。
>
> 核心理念：
>
> **用户负责导演与决策，AI 负责生产与重复劳动。**
>
> 产品不是一个“输入小说 → 黑箱生成视频”的工具，而是一个可观察、可干预、可暂停、可重做的 AI 漫剧生产 IDE。

> **UI 开发强制阅读**：所有界面改动前先读 `docs/development-notes/ui-guidelines.md`
> （设计 token、布局结构、组件规范、状态生命周期、响应式与验证方法）。

---

# 1. Product Positioning

## 1.1 产品定位

AI Drama IDE Lite 是一个 Story-to-Drama AI IDE。

核心流程：

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

用户负责：

故事方向
审核
修改
选择
审美判断
最终决策

AI 负责：

小说分析
故事整理
剧本生成
人物提取
场景提取
道具提取
视觉资产生成
分镜生成
图片生成
视频生成
重复性工作
2. Lite Version Scope

Lite 版本只解决核心生产链路。

MVP 核心范围
小说
 ↓
故事分析
 ↓
Story Bible
 ↓
剧本
 ↓
人物 / 场景 / 道具
 ↓
视觉资产
 ↓
分镜
 ↓
生图
 ↓
图生视频

暂不重点开发：

专业视频剪辑
专业音频工作站
多轨剪辑
本地大模型管理
GPU 集群
团队协作
企业级资产管理
完整 ComfyUI 编辑器

后续再考虑：

配音
BGM
音效
自动剪辑
视频合成
本地模型
ComfyUI
云 GPU
3. Core Product Concept
3.1 Director + AI Production Team

产品不是：

用户
 ↓
AI
 ↓
最终视频

而是：

用户 = 导演

AI = 制作团队

AI 负责执行，用户拥有最终决定权。

4. Core UX Principles
Principle 1 — AI 不能是黑箱

用户必须知道：

AI 正在做什么
已经完成什么
当前进度
下一步是什么
出现了什么问题
Principle 2 — 用户随时可以停止

所有耗时任务必须支持：

Pause
Cancel
Retry
Stop
Principle 3 — 已生成内容不能轻易丢失

每一个成功生成的资产必须立即持久化。

Principle 4 — 局部重做

一个镜头不满意：

Shot 03
 ↓
Redo

而不是整个项目重新生成。

Principle 5 — 修改必须考虑依赖

例如修改人物：

Character v2
 ↓
Affected Shots
 ↓
提示用户

不能偷偷覆盖所有旧内容。

Principle 6 — 用户最终拥有决定权

AI 可以：

推荐
分析
自动生成
自动判断

但不能未经用户允许覆盖重要资产。

5. Main Modules
AI Drama IDE Lite
│
├── Project
├── Novel Studio
├── Story Bible
├── Script Studio
├── Asset Studio
├── Storyboard
├── Generation Center
├── Production Graph
├── Job Manager
├── Provider Manager
├── Model Registry
├── Capability Engine
├── Settings
└── Director Agent
6. Project System

每一个漫剧都是独立 Project。

Project
├── Novel
├── Story Bible
├── Scripts
├── Characters
├── Locations
├── Props
├── Storyboards
├── Images
├── Videos
├── Jobs
└── Versions

项目必须支持：

新建
打开
保存
导入
导出
自动保存
项目恢复
版本管理

推荐项目结构：

project/
├── project.json
├── novel/
├── story/
├── scripts/
├── characters/
├── locations/
├── props/
├── storyboards/
├── generations/
├── jobs/
└── versions/
7. Novel Studio

Novel Studio 用于：

创建原创小说
导入用户拥有合法使用权的小说
7.1 小说导入

第一阶段支持：

TXT
Markdown
DOCX

后续：

PDF
EPUB
7.2 原创小说生成

不采用：

一句话
 ↓
直接生成十万字小说

而采用：

故事灵感
 ↓
故事概念
 ↓
世界观
 ↓
人物
 ↓
人物关系
 ↓
核心冲突
 ↓
故事主线
 ↓
章节大纲
 ↓
章节正文

用户可以在每一步修改 AI 输出。

7.3 AI 创作能力

支持：

故事构思
世界观
人物设计
人物关系
剧情冲突
大纲生成
章节生成
续写
扩写
精简
重写
剧情检查

避免直接复制现有作品或模仿具体作者的独特表达。

8. Story Bible

Story Bible 是项目中的稳定事实层。

Story Bible
│
├── World
│   ├── Rules
│   ├── Geography
│   ├── History
│   └── Factions
│
├── Characters
│   ├── Identity
│   ├── Appearance
│   ├── Personality
│   ├── Relationships
│   └── Current State
│
├── Locations
├── Props
├── Timeline
├── Plotlines
├── Foreshadowing
└── Important Events

所有后续 Agent 都必须优先读取 Story Bible。

目的：

防止人物设定漂移
防止世界观漂移
防止服装漂移
防止地点漂移
防止剧情事实冲突
9. Script Engine

小说：

Novel
 ↓
Story Analysis
 ↓
Episode Planning
 ↓
Script
 ↓
Scene
 ↓
Shot
9.1 Episode
Episode
├── Information
├── Summary
├── Scenes
└── Ending
9.2 Scene
Scene
├── Location
├── Characters
├── Time
├── Action
├── Dialogue
├── Emotion
└── Camera
9.3 Shot
Shot
├── Shot ID
├── Scene ID
├── Characters
├── Location
├── Action
├── Dialogue
├── Camera
├── Composition
├── Lighting
├── Emotion
├── Duration
└── Reference Assets
10. Asset System

资产类型：

Character
Location
Prop
Costume
Creature
Vehicle
Other
10.1 Character Asset
Character
├── Basic Information
├── Appearance
├── Personality
├── Costume
├── Face Reference
├── Front View
├── Side View
├── Back View
├── Expressions
├── Poses
├── Prompt
├── Negative Prompt
└── Versions

每个资产必须拥有唯一 Asset ID。

例如：

character_lin_fan_001

分镜引用 Asset ID，而不是每次重新描述角色。

11. Asset Versioning

所有重要 AI 资产必须支持版本。

Lin Fan
├── v1
├── v2
└── v3 ← Current

每个版本记录：

Prompt
Model
Provider
Parameters
Reference Images
Creation Time
User Instruction
Generated Result

用户可以：

接受
重做
恢复旧版本
删除未使用版本
修改 Prompt
12. Visual Consistency

视觉一致性是系统核心目标之一。

错误方式：

Shot 01 → AI 自己描述人物
Shot 02 → AI 自己描述人物
Shot 03 → AI 自己描述人物

正确方式：

Story Bible
 ↓
Asset Specification
 ↓
Reference Asset
 ↓
Shot
 ↓
Generation

所有视觉生成任务优先使用项目中的 Reference Assets。

13. Storyboard System

Storyboard 是剧本与视觉生成之间的核心桥梁。

每个 Shot 至少保存：

Shot ID
Scene ID
Characters
Location
Action
Dialogue
Camera
Composition
Lighting
Emotion
Duration
Reference Assets
Generation Status

Storyboard UI 必须允许用户：

查看
编辑
删除
重排
重做
修改镜头
修改 Camera
修改角色动作
修改视觉描述
14. Production Graph

所有生产过程基于 Production Graph。

Novel
 ↓
Story Bible
 ↓
Script
 ↓
Assets
 ↓
Storyboard
 ↓
Image
 ↓
Video

每个节点都是独立任务。

例如：

Character
 ↓
Storyboard
 ↓
Shot Image
 ↓
Video

如果 Character 修改：

Character v2
 ↓
Affected Storyboards
 ↓
Affected Images
 ↓
Affected Videos

系统自动检测依赖并提示用户。

15. Generation Center

Generation Center 是 AI 工作过程的可视化中心。

点击：

生成漫剧

不能出现：

Loading...

然后黑箱运行。

必须显示：

✓ 小说分析
✓ Story Bible
✓ 人物提取
● 剧本生成
○ 人物资产
○ 场景资产
○ 分镜
○ 生图
○ 图生视频
16. Generation Status

统一任务状态：

Queued
Running
Paused
Completed
Failed
Cancelled

用户实时看到：

人物资产

✓ 林凡
✓ 苏璃
● 赵无极
○ 墨大夫
○ 陈玄

3 / 5
17. User Interrupt System
17.1 Stop Current Job

只取消当前任务：

停止赵无极三视图

其他任务继续。

17.2 Pause Stage
暂停人物资产生成

已经完成的内容保留。

17.3 Stop Project
停止整个项目

取消所有可取消任务。

17.4 Cancel Must Be Real

UI 的停止按钮必须真正终止后台 Job。

必须提供：

cancel(jobId)
pause(jobId)
resume(jobId)
retry(jobId)
18. Job Manager

所有耗时操作必须 Job 化。

Job
├── id
├── type
├── status
├── progress
├── input
├── output
├── error
├── createdAt
├── startedAt
└── completedAt

任务类型：

STORY_ANALYSIS
STORY_BIBLE
SCRIPT_GENERATION
CHARACTER_EXTRACTION
SCENE_EXTRACTION
PROP_EXTRACTION
CHARACTER_GENERATION
SCENE_GENERATION
STORYBOARD_GENERATION
IMAGE_GENERATION
VIDEO_GENERATION

Job Manager 负责：

排队
调度
取消
暂停
恢复
重试
错误处理
状态持久化
19. Event System

前端需要实时获取任务状态。

事件：

JOB_CREATED
JOB_STARTED
JOB_PROGRESS
ASSET_CREATED
ASSET_UPDATED
JOB_FAILED
JOB_COMPLETED
JOB_CANCELLED
PROJECT_PAUSED
PROJECT_RESUMED

优先使用：

WebSocket

或：

Server-Sent Events

具体实现根据开发阶段决定。

20. AI Provider Architecture

这是项目的核心架构之一。

20.1 基本原则

模型是基础设施，不是业务逻辑。

业务代码不能直接绑定某一个 AI 模型。

错误：

generateShot()
 ↓
直接调用某模型 API

正确：

Generation Engine
 ↓
Model Router
 ↓
Capability Engine
 ↓
Provider Manager
 ↓
Model Adapter
 ↓
API
21. User-defined API

用户可以自行配置自己的：

LLM API
图片生成 API
视频生成 API

用户不应该被限制只能使用开发者提供的模型。

22. API Configuration

用户添加模型：

名称
类型
Provider
API Base URL
API Key
Model ID

例如：

名称：
My Image API

类型：
Image Generation

Base URL：
https://example.com/v1

API Key：
********

Model：
my-image-model
23. API Validation

添加 API 后必须允许用户测试。

不能只检查：

API Key 不为空

必须提供至少三个级别的检测。

Level 1 — Connection Test

检测：

Base URL
Network
Endpoint
Level 2 — Authentication / Model Test

检测：

API Key
Model ID
Model Availability
Level 3 — Generation Test

真正发起一次低成本测试任务。

例如：

Image:
低分辨率测试图

Video:
短时长测试视频

第三层必须由用户主动触发，避免无意产生 API 费用。

24. API Test Result

成功：

✓ Connection
✓ Authentication
✓ Model
✓ Capability

失败：

✕ API Key Invalid

或者：

⚠ Model Not Found

或者：

⚠ Endpoint Available
✕ Image Generation Unsupported

错误信息必须尽可能明确。

25. Provider Manager

Provider Manager 负责管理用户配置的 Provider。

Provider Manager
├── Add Provider
├── Remove Provider
├── Enable / Disable
├── Test Provider
├── Update Provider
└── List Providers

Provider 类型：

LLM
Image
Video
26. Model Registry

Model Registry 保存用户可用模型的信息。

Model
├── id
├── providerId
├── name
├── type
├── capabilities
├── parameters
├── limits
├── pricing
└── enabled

例如：

Model A

Type:
Image

Capabilities:
✓ Text → Image
✓ Image → Image
✓ Reference Image
✕ Image → Video

另一个：

Model B

Type:
Video

Capabilities:
✓ Image → Video
✓ Text → Video
✓ First Frame
✕ Last Frame
27. Capability Engine

不同模型的能力完全不同。

因此系统不能只判断：

model.type === "image"

必须判断具体 Capability。

标准 Capability：

text_to_image
image_to_image
reference_image
character_reference
style_reference
inpainting
outpainting

text_to_video
image_to_video
video_to_video
first_frame
last_frame
first_last_frame
camera_control
motion_control

系统根据任务需求匹配模型。

28. Capability Matching

例如：

任务：

Image → Video

需要：
image_to_video

系统扫描：

Model A
✕

Model B
✓

Model C
✓

然后推荐：

Model B ★
Model C

如果没有模型支持：

当前没有可用的 Image → Video 模型。
请添加支持 image_to_video 的模型。
29. Common Request Schema

不同模型的 API 参数不能直接暴露给业务层。

统一内部请求。

例如：

interface ImageGenerationRequest {
  prompt: string;
  negativePrompt?: string;
  width?: number;
  height?: number;
  aspectRatio?: string;
  seed?: number;
  referenceImages?: string[];
  model: string;
  providerOptions?: Record<string, unknown>;
}

视频：

interface VideoGenerationRequest {
  prompt?: string;
  image?: string;
  firstFrame?: string;
  lastFrame?: string;
  duration?: number;
  aspectRatio?: string;
  model: string;
  providerOptions?: Record<string, unknown>;
}
30. Provider-specific Parameters

不能强迫所有模型使用完全一样的参数。

统一参数：

prompt
image
duration
aspectRatio
seed

Provider 专属参数：

providerOptions

例如：

{
  "prompt": "...",
  "duration": 5,
  "providerOptions": {
    "motion_strength": 0.7,
    "camera_motion": "dolly_in"
  }
}
31. Model Adapter System

Adapter 负责把统一请求转换为具体 API 请求。

Generation Request
 ↓
Model Adapter
 ↓
Provider-specific Request
 ↓
API

例如内部统一：

duration = 5

API A：

duration_seconds = 5

API B：

video_length = 5

API C：

seconds = 5

这些差异全部由 Adapter 处理。

业务层不允许出现：

if model === "ModelA"
if model === "ModelB"
if model === "ModelC"
32. Image Adapter

图片模型统一接口：

interface ImageGenerationProvider {
  generate(
    request: ImageGenerationRequest
  ): Promise<GenerationJob>;

  getStatus(
    jobId: string
  ): Promise<GenerationStatus>;

  cancel(
    jobId: string
  ): Promise<void>;
}

支持：

Text → Image
Image → Image
Reference Image
Character Reference
Style Reference

具体能力由 Capability Engine 决定。

33. Video Adapter

视频模型统一接口：

interface VideoGenerationProvider {
  generate(
    request: VideoGenerationRequest
  ): Promise<GenerationJob>;

  getStatus(
    jobId: string
  ): Promise<GenerationStatus>;

  cancel(
    jobId: string
  ): Promise<void>;
}

支持：

Text → Video
Image → Video
Video → Video
First Frame
Last Frame
First + Last Frame

具体能力由 Model Registry 和 Capability Engine 决定。

34. Model Selection

用户可以：

自动选择

或者：

手动选择模型

自动选择：

Task
 ↓
Required Capabilities
 ↓
Capability Engine
 ↓
Available Models
 ↓
Model Router
 ↓
Recommended Model
35. Model Router

Model Router 根据：

Task Type
Capabilities
Quality
Speed
Cost
Resolution
Duration
Provider Availability

选择模型。

例如：

Quality:
Best

优先高质量模型。

Quality:
Fast

优先速度快、成本低的模型。

36. Dynamic UI Based on Capabilities

UI 不能把所有参数全部显示出来。

例如模型支持：

✓ Image → Video
✓ First Frame
✕ Last Frame

UI 只显示：

First Frame
Duration
Aspect Ratio

不显示：

Last Frame

如果用户切换模型：

Model B

UI 自动根据 Capability 更新。

37. Custom API / Developer Mode

由于不可能预先支持世界上所有 AI API，需要支持 Custom Provider。

普通用户：

Provider
Model
API Key

高级用户：

Developer Mode

允许配置：

Endpoint
Method
Headers
Request Template
Response Mapping
Polling Endpoint

例如：

Request:

{
  "prompt": "{{prompt}}",
  "image": "{{image}}",
  "duration": "{{duration}}"
}

Response：

{
  "task_id": "{{data.id}}"
}

Result：

{
  "video_url": "{{data.output.url}}"
}

Custom Provider 必须经过测试才能启用。

38. Async API Handling

AI 生图和视频 API 经常不是同步返回。

统一处理：

Create Task
 ↓
Task ID
 ↓
Queued
 ↓
Running
 ↓
Polling / Webhook
 ↓
Completed
 ↓
Download Result

Provider Adapter 负责处理具体 API 的：

Polling
Webhook
Streaming
Task ID
Result URL

上层 Job Manager 不关心具体实现。

39. Asset Storage

API 返回的 URL 不能直接作为永久资产。

错误：

API
 ↓
Temporary URL
 ↓
保存 URL

正确：

API
 ↓
Temporary URL
 ↓
Download
 ↓
Local Asset Storage
 ↓
Asset ID

图片：

assets/
└── characters/
    └── lin_fan/
        ├── v1/
        │   ├── front.png
        │   ├── side.png
        │   └── back.png
        └── v2/

视频：

assets/
└── videos/
    └── episode_01/
        └── shot_03/
            └── v1.mp4
40. API Key Security

API Key 不能保存到：

project.json

也不能进入：

Git

也不能随项目导出。

项目只保存：

providerId
modelId

API Key 使用系统安全存储。

Windows：

Windows Credential Manager

macOS：

Keychain

Linux：

Secret Service
41. Generation Flow
Image Generation
Storyboard
 ↓
Read Character Assets
 ↓
Read Scene Assets
 ↓
Build Prompt
 ↓
Required Capabilities
 ↓
Model Router
 ↓
Image Adapter
 ↓
API
 ↓
Job Manager
 ↓
Download Result
 ↓
Asset Version
 ↓
UI Preview
Image-to-Video
Shot Image
 ↓
Video Request
 ↓
Required Capability:
image_to_video
 ↓
Capability Engine
 ↓
Model Router
 ↓
Video Adapter
 ↓
API
 ↓
Job Manager
 ↓
Download Video
 ↓
Video Asset
 ↓
UI Preview
42. Generation Center UI
┌─────────────────────────────────────────────────────────┐
│ Generation Center                         [■ STOP ALL]  │
├──────────────┬──────────────────────────────────────────┤
│ PIPELINE     │ PREVIEW                                  │
│              │                                          │
│ ✓ Story      │             Current Result               │
│ ✓ Script     │                                          │
│ ✓ Assets     │               [Preview]                  │
│ ● Storyboard │                                          │
│ ○ Image      │                                          │
│ ○ Video      │       [Accept] [Redo] [Edit]             │
├──────────────┴──────────────────────────────────────────┤
│ AI Activity                                             │
│ ✓ Loaded Character: Lin Fan                             │
│ ✓ Loaded Location: Qingyun Gate                         │
│ ● Generating Shot 03                                    │
│                                                          │
│ [Pause] [Stop Current] [Stop All]                       │
└─────────────────────────────────────────────────────────┘
43. Asset Browser
Characters

┌─────────┐ ┌─────────┐ ┌─────────┐
│ Preview │ │ Preview │ │ Preview │
│ 林凡    │ │ 苏璃    │ │ 赵无极  │
│ ✓ Ready │ │ ✓ Ready │ │ ● Gen   │
└─────────┘ └─────────┘ └─────────┘

Asset Detail：

Overview
References
Versions
Prompt
Generation
Related Shots
44. Director Agent

用户可以自然语言修改项目。

例如：

林凡的服装太现代了，
换成深蓝色古风长袍。

系统：

User Instruction
 ↓
Director Agent
 ↓
Identify Asset
 ↓
Modify Asset Specification
 ↓
Generate New Version
 ↓
Check Dependencies

如果产生影响：

林凡服装发生变化

受影响：

Character Asset
Scene 03
Shot 12
Shot 18
Shot 25

用户选择：

只修改人物
重新生成受影响镜头
全部不处理
45. Quality Agent

后续加入 Quality Agent。

检查：

Character Consistency
Scene Consistency
Story Consistency
Shot Continuity
Prompt Completeness
Visual Quality

例如：

⚠ Shot 18

角色服装与 Character v3 不一致。

[重新生成]
[接受]
[忽略]

Quality Agent 不得未经用户允许自动覆盖资产。

46. Copyright-aware Design

系统支持：

Original
Imported
Licensed
Public Domain

不提供：

抓取付费小说
绕过版权限制
批量复制网络小说

原创项目记录：

User Idea
 ↓
AI Suggestions
 ↓
User Selection
 ↓
User Modification
 ↓
Final Content

记录：

用户输入
AI 输出
用户修改
版本
最终内容
47. Desktop Architecture

推荐：

Desktop
│
├── Tauri 2
│
├── React
│
├── TypeScript
│
└── Python Backend
       │
       ├── FastAPI
       ├── Story Engine
       ├── Script Engine
       ├── Asset Engine
       ├── Generation Engine
       ├── Provider Manager
       ├── Model Registry
       ├── Capability Engine
       ├── Model Router
       └── Job Manager

Frontend：

UI
Project Explorer
Novel Editor
Story Bible
Asset Browser
Storyboard
Generation Center
Model Settings

Backend：

AI 调用
Agent
文件系统
Provider
Adapter
Job Manager
Asset Manager
Production Graph
48. Data Storage

Lite 版本：

SQLite
+
Local File System

SQLite：

Projects
Characters
Locations
Props
Episodes
Scenes
Shots
Jobs
Versions
Providers
Models
Capabilities

大型文件：

Images
Videos
Novel Files
Reference Files

保存在项目目录。

49. Recommended Project Structure
ai-drama-ide/
│
├── apps/
│   ├── desktop/
│   └── backend/
│
├── packages/
│   ├── story-engine/
│   ├── script-engine/
│   ├── asset-engine/
│   ├── storyboard-engine/
│   ├── generation-engine/
│   ├── provider-core/
│   ├── model-registry/
│   ├── capability-engine/
│   ├── model-router/
│   └── shared/
│
├── agents/
│   ├── director/
│   ├── story/
│   ├── script/
│   ├── asset/
│   ├── character/
│   ├── scene/
│   ├── storyboard/
│   └── quality/
│
├── providers/
│   ├── llm/
│   ├── image/
│   └── video/
│
├── adapters/
│   ├── llm/
│   ├── image/
│   └── video/
│
├── workflows/
│   ├── character/
│   ├── scene/
│   ├── storyboard/
│   ├── image/
│   └── video/
│
├── docs/
├── tests/
└── README.md
50. Development Principles
50.1 Do Not Reinvent the Wheel

新增任何功能或模块之前：

检索 GitHub
检索成熟开源项目
查看官方文档
分析成熟实现
判断是否可以直接使用
如果不能直接使用，提取优秀设计
适配和优化
再实现

优先参考：

GitHub
Official SDK
Official API
Mature Open Source Libraries
Mature Open Source Projects

不要为了证明自己能写而重新实现成熟基础设施。

51. Model Integration Principles

新增模型时：

禁止：

if model == "xxx":
    ...

把大量模型逻辑写入业务层。

必须：

Model Registry
 ↓
Capability
 ↓
Adapter
 ↓
Provider

新增模型原则：

New Model
 ↓
Register Model
 ↓
Declare Capabilities
 ↓
Implement Adapter
 ↓
API Test
 ↓
Generation Test
 ↓
Enable
52. Codex Development Rules

Codex 是开发 Agent，不是产品运行时 AI。

Codex 负责：

编写代码
修改代码
重构
Debug
测试
检查依赖
检查项目结构
检索开源项目
分析官方 SDK
编写文档

产品运行时 Agent 与 Codex 必须保持架构隔离。

53. No Fake Implementation

禁止：

Fake API
Fake Generation
Fake Progress
Fake Job
Fake Cancel
Fake AI Output

如果功能未实现：

TODO
Not Implemented
Coming Soon

必须明确标记。

54. Development Workflow

每个功能必须：

Research
 ↓
Design
 ↓
Implement
 ↓
Run
 ↓
Test
 ↓
Fix
 ↓
Commit

项目必须尽可能保持：

Always Runnable
55. MVP Roadmap
Phase 0 — Foundation
[ ] Repository
[ ] Desktop Shell
[ ] Frontend
[ ] Backend
[ ] Project System
[ ] SQLite
[ ] Basic UI
Phase 1 — Novel
[ ] Novel Import
[ ] Novel Editor
[ ] AI Story Creation
[ ] Chapter System
[ ] Story Bible
Phase 2 — Script
[ ] Story Analysis
[ ] Episode Planning
[ ] Script Generation
[ ] Scene Generation
[ ] Shot Generation
Phase 3 — Assets
[ ] Character Extraction
[ ] Location Extraction
[ ] Prop Extraction
[ ] Asset Browser
[ ] Asset Versioning
[ ] Character Generation
[ ] Scene Generation
Phase 4 — Provider System
[ ] Provider Manager
[ ] User API Configuration
[ ] API Connection Test
[ ] Authentication Test
[ ] Model Test
[ ] Generation Test
[ ] Model Registry
[ ] Capability Engine
[ ] Model Adapter
[ ] Image Adapter
[ ] Video Adapter
[ ] Custom Provider
[ ] API Key Secure Storage
Phase 5 — Production Engine
[ ] Production Graph
[ ] Job Manager
[ ] Queue
[ ] Progress
[ ] Pause
[ ] Cancel
[ ] Retry
[ ] Event Stream
Phase 6 — Storyboard
[ ] Storyboard UI
[ ] Shot Preview
[ ] Camera Information
[ ] Asset References
[ ] Shot Editing
Phase 7 — Image Generation
[ ] Image Provider
[ ] Character Generation
[ ] Scene Generation
[ ] Storyboard Image Generation
[ ] Batch Generation
[ ] Version Control
Phase 8 — Video Generation
[ ] Video Provider
[ ] Image-to-Video
[ ] Video Job
[ ] Video Preview
[ ] Video Versioning
[ ] Video Model Selection
[ ] Capability Matching
Phase 9 — Director Agent
[ ] Natural Language Commands
[ ] Asset Modification
[ ] Dependency Detection
[ ] Affected Shot Detection
[ ] Intelligent Regeneration
Phase 10 — Quality
[ ] Quality Agent
[ ] Character Consistency
[ ] Scene Consistency
[ ] Story Consistency
[ ] Shot Continuity
56. Future Roadmap
[ ] Text-to-Video
[ ] Video-to-Video
[ ] First/Last Frame
[ ] Voice Generation
[ ] Character Voice
[ ] BGM
[ ] Sound Effects
[ ] Timeline
[ ] Automatic Editing
[ ] Complete Episode Rendering
[ ] Local Model Support
[ ] ComfyUI Integration
[ ] Cloud GPU
[ ] Advanced Workflow Editor
57. Final Product Vision

最终用户流程：

打开 AI Drama IDE Lite
        ↓
新建项目
        ↓
添加自己的 AI API
        ↓
测试 API
        ↓
检测模型能力
        ↓
选择模型
        ↓
输入故事 / 导入小说
        ↓
AI 分析
        ↓
Story Bible
        ↓
生成剧本
        ↓
生成角色 / 场景 / 道具
        ↓
生成分镜
        ↓
生成图片
        ↓
图片 → 视频
        ↓
用户实时观察
        ↓
不满意
 ↓
停止 / 修改 / 重做
        ↓
满意
 ↓
继续生产

最终产品定位：

不是“一个自动生成漫剧的网站”。

而是一个真正的 AI 漫剧生产 IDE。

用户是导演。

AI 是制作团队。

模型是可替换的基础设施。

用户可以使用自己的 API。

系统负责检测 API、识别模型能力、适配不同模型的调用方式，并将所有模型统一到同一个生产流程中。

用户始终能够看到 AI 在做什么，并且可以随时暂停、停止、修改、重做和回滚。

58. Core Architecture Principle

整个项目最重要的架构原则：

                USER
                  │
                  ↓
             DIRECTOR UI
                  │
                  ↓
          PRODUCTION GRAPH
                  │
                  ↓
          GENERATION ENGINE
                  │
                  ↓
            MODEL ROUTER
                  │
                  ↓
          CAPABILITY ENGINE
                  │
                  ↓
           MODEL REGISTRY
                  │
                  ↓
          PROVIDER MANAGER
                  │
                  ↓
            MODEL ADAPTER
                  │
                  ↓
                API
                  │
                  ↓
            JOB MANAGER
                  │
                  ↓
            LOCAL ASSETS

任何 AI 模型都不能直接穿透这一层架构进入业务逻辑。

模型可以更换，Provider 可以更换，API 可以更换，但 Project、Story、Asset、Storyboard、Production Graph 和用户工作流不能因此被重写。

这条原则必须贯穿整个项目生命周期。
