# 调研：下一步开发方向 — Phase 9 Asset Version vs Phase 10 Job System

> 调研时间：2026-08-14。规则 75（Research Before Every Step）。

## 结论

推荐下一步做 **Phase 10 — Generation Job System（持久化 Job 系统）**，而不是按
ROADMAP 顺序先做 Phase 9 Asset Version。

理由（详见 §3）：
1. Phase 13/14（图片/视频生成）、Phase 15（生成中心）、Phase 16（中断系统）全部依赖
   Job 系统；它是后续所有生成功能的地基。
2. 当前两类生成服务（`generation_service.py`、`asset_service.py` 的 AI 补全）都是
   **内存 Job，重启即清空**；切页面/重启后任务状态丢失是已知体验痛点，Phase 10 直接解决。
3. Phase 9 版本系统的主要写入方是「生成流程」（Phase 13 生图/生视频后保存版本）。
   在还没有真实生成流程前提前做，缺少实际写入场景，容易设计过度。
   `versions` 表已在 schema 占位，不会阻碍后续实现。

## 1. 当前进度盘点

- Phase 0-8 全部完成（项目系统 → 小说 → Provider/Model → 能力引擎 → Adapter →
  Story Bible → 剧本 → 资产引擎）。
- Phase 21 打包基本完成（NSIS 安装包 + GitHub Release v0.1.0）；自动更新已搁置。
- 遗留占位：`jobs` 表、`versions` 表已在 `schema.sql` 建好但**未被业务使用**。
- `GenerationService`（Phase 5）与 `AssetGenerationService`（Phase 8）均为内存注册表，
  文件头注释明确写着「Phase 10 再引入持久化 Job 系统」。

## 2. 参考项目调研

### 2.1 Jellyfish — AI 短剧工作室（与本产品定位几乎一致）

仓库：https://github.com/Forget-C/Jellyfish

关键设计：
- **统一异步任务中心**：文本/图片/视频任务走同一个异步任务系统，统一状态、结果、
  耗时追踪、取消；全局任务中心支持上下文导航回项目/章节/镜头。
- **任务即一等公民**：任务中心与生成工作区分离，用户从任务中心查看所有进行中的生成。
- **Shot 准备流**：脚本拆解 → shot 准备 → 候选确认 → shot ready → 生成工作区，
  用「prepared」状态区分「可生成」与「正在生成」。
- 资产一致性：角色/演员、场景、道具、服装共享实体模型，跨镜头复用。

对本项目的启示：Phase 10 不只是「把内存 Job 变成 DB Job」，还应提供
**统一任务中心 UI**（Phase 15 的雏形），让用户能看到所有任务的状态并可取消。

### 2.2 ComfyUI-GenAsset — 生成资产版本管理

仓库：https://github.com/steliosot/ComfyUI-GenAsset

关键设计（Phase 9 的直接参考）：
- 每次保存 = 图片 + **recipe**（prompt、negative prompt、model、seed、sampler、
  workflow JSON、metadata），保证可复现、可对比。
- 版本操作：加载精确版本、加载当前版本、**promote 某版本为 current**、删除版本、
  对比两个版本、分支/fork（parent lineage，属 P1/P2）。
- 拒绝保存无效结果（blank/near-black 帧），避免坏版本进入资产库。

对本项目的启示：Phase 9 的版本记录应包含「生成 recipe」——model_id、capability、
prompt、比例/画风、来源 Job ID、时间戳；而非只存图片本身。
分支/fork 属于 P1/P2，MVP 只需线性版本 + current + 删除未使用版本。

### 2.3 atomic-agent — SQLite 持久化任务队列（与我们的栈最贴近）

仓库：https://github.com/AtomicBot-ai/atomic-agent（commit dbf1f06）

关键设计：
- 状态机：`pending → running → completed / failed / blocked / cancelled`；
  可重试失败回到 pending，达到 maxAttempts 才 failed。
- **失败分类**：可重试（临时网络/5xx/rate limit）与永久失败（invalid key/
  不支持能力）分开，避免对无效请求无限重试（与 AGENTS.md 重试原则一致）。
- **指数退避**：`min(initialMs * 2^attempt, maxMs)`，退避在尝试之间，不阻塞队列。
- **stale recovery**：启动时一次性把 crash 残留的 `running` 翻回 `pending`
  （无后台 sweeper）；避免进程崩溃后任务永久卡死。
- **cancel 幂等**：对已终态的行重复 cancel 返回原记录。
- 状态记录：attempts / maxAttempts / lastError / lastErrorCategory / 各时间戳。

对本项目的启示：Phase 10 应采用同样的状态机 + 失败分类 + 指数退避 + 启动恢复，
并用 SQLite 持久化（表已存在，需扩展字段）。

## 3. Phase 10 优先的论证

### 依赖关系

```text
Phase 10 Job System
  ├── Phase 13 Image Generation（Job 化生图）
  ├── Phase 14 Video Generation（Job 化生视频）
  ├── Phase 15 Generation Center（任务中心 UI）
  └── Phase 16 Interrupt System（Pause/Cancel/Recover）
```

Phase 9 版本系统的「产生版本」动作发生在生成流程中；先做 Job 系统，
Phase 13 生图时再接入版本保存，顺序自然。

### 现有痛点

1. 资产补全 Job 和生成 Job 都是内存态，**应用重启即消失**。
2. 用户切换页面再回来，任务状态重置（小说 AI 撰写已踩过同类坑）。
3. 无统一任务中心，用户不知道后台在生成什么。

### 风险对比

| 方案 | 优点 | 缺点 |
| --- | --- | --- |
| 先 Phase 10 | 解锁后续所有生成功能；解决状态丢失 | 体量较大，需拆子任务 |
| 先 Phase 9 | 体量小、独立 | 无真实写入方，容易过度设计；不解决现有痛点 |

## 4. Phase 10 设计要点（建议）

1. **扩展 `jobs` 表**（现有占位 schema 字段不够）：
   - 增加：`model_id`、`provider_id`（Job 只绑定一个 Model / Provider，产品约束）、
     `capability`、`attempts`、`max_attempts`、`last_error`、`last_error_category`、
     `cancelled_at`、`paused_at`、`input_payload`、`result_payload`、`output_files`。
   - 状态枚举：`queued / running / paused / completed / failed / cancelled`。
2. **Job Store**：SQLite CRUD + 状态迁移 + 幂等 cancel + 启动 stale recovery。
3. **Job Worker**：单 worker 顺序执行（单模型生成，不做同任务并行）；显式 drain，
   可加轻量后台循环（低频，仅轮询 queued/running，不做假进度）。
4. **失败分类 + 指数退避重试**：沿用 AGENTS.md 原则——临时网络/5xx/rate limit 可重试；
   invalid key / unsupported capability / invalid model 直接 failed。
5. **Pause / Resume**：本地暂停（停止轮询、标记 paused）；远程无法暂停时如实告知
   「远程任务可能仍在执行」（AGENTS.md 取消任务原则）。
6. **API**：`POST /api/jobs`、`GET /api/jobs`、`GET /api/jobs/{id}`、
   `POST /api/jobs/{id}/cancel`、`POST /api/jobs/{id}/pause`、`POST /api/jobs/{id}/resume`、
   `POST /api/jobs/{id}/retry`。
7. **统一任务中心 UI（轻量）**：设置页或全局栏可查看任务列表 + 状态 + 取消；
   Phase 15 再升级为完整 Generation Center。
8. **现有服务迁移**：`generation_service.py` 与 `asset_service.py` 改为通过 Job Store
   持久化，保持对外 API 兼容（前端无需大改）。

## 5. Phase 9 的时机与设计要点（后续再做）

- 时机：Phase 13（Image Generation）接入时实现最合理，或作为 Phase 10 之后
  的独立小阶段。
- 版本记录内容（参考 GenAsset）：`model_id`、`capability`、`prompt`、
  `aspect_ratio`、`art_style`、`job_id`、`file_path`、`created_at`、`version_no`。
- 操作：版本列表、加载精确版本、promote current、删除未使用版本；
  分支/fork 留 P1/P2。
- `versions` 表已存在，Phase 9 只需加字段/索引。

## 6. 参考来源

- Jellyfish（AI 短剧生产工作区）：https://github.com/Forget-C/Jellyfish
- ComfyUI-GenAsset（生成资产版本管理）：https://github.com/steliosot/ComfyUI-GenAsset
- atomic-agent durable task queue（SQLite 任务队列）：
  https://github.com/AtomicBot-ai/atomic-agent/commit/dbf1f06
