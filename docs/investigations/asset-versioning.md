# 调研：Phase 9 — Asset Version System（资产版本系统）设计依据

> 调研时间：2026-08-14。规则 75（Research Before Every Step）。

## 结论

资产版本系统的核心是「**每次 AI 生成都是新版本，绝不覆盖已有版本**」。参考成熟做法，
版本记录应保存完整 recipe（生成参数）+ 图片文件路径，并提供
「当前版本 + 历史列表 + 恢复（promote）+ 删除未使用版本」的最小闭环。

数据模型建议：扩展现有占位 `versions` 表（Phase 1 已建但未使用），加
`file_path / model_id / job_id / is_current` 等列；文件落到
`data_dir/projects/{project_id}/assets/{asset_id}/v{n}.png`。删除版本用「删文件 + 删记录」，
但当前版本不允许删除（必须先 promote 其他版本）。

## 1. 参考项目

### 1.1 ComfyUI-GenAsset（生成结果版本管理，最直接参考）

仓库：https://github.com/steliosot/ComfyUI-GenAsset

关键设计：
- 每次保存 = 图片 + **recipe**（prompt、negative prompt、model、seed、sampler、
  workflow JSON、metadata），保证可复现、可对比。
- 版本操作：加载精确版本、加载当前版本、**promote 某版本为 current**、删除版本、
  对比两个版本、分支/fork（parent lineage）。
- 拒绝保存无效结果（blank/near-black 帧），避免坏版本进入资产库。

对本项目的启示：
- 版本记录保存 `model_id + prompt + 比例/画风 + 来源 job_id + 时间 + 文件路径`。
- 分支/fork 属 P1/P2，MVP 只需线性版本 + current + 删除未使用版本。
- 当前版本语义：`is_current` 唯一标记，promote 即切换。

### 1.2 ComfyUI Asset Management（SQLite 持久化文件索引）

文档：https://deepwiki.com/comfyanonymous/ComfyUI/2.6-asset-management-system

关键设计：
- SQLite 持久化媒体文件索引；逻辑指针（AssetReference）与内容（Asset）分离，
  同一内容不重复存储。
- 软删除（`deleted_at`），文件与数据库对账（missing / needs_verify）。

对本项目的启示：
- 版本记录用 SQLite 持久化（与项目现状一致），图片文件放项目目录。
- 删除版本时明确「删文件还是软删」；资产版本建议删文件 + 删记录（历史版本文件可回收），
  但删除前必须确认不是当前版本。

### 1.3 Krita AI Diffusion（生成历史）

仓库：https://github.com/Acly/krita-ai-diffusion

关键设计：生成历史可配置存储量，旧图 prune；历史 UI 更新与清理。

对本项目的启示：版本数量可配置上限/手动清理（Phase 9 Task「Delete Unused Version」）。

### 1.4 Stable Diffusion WebUI（生成历史记录）

仓库：https://github.com/AUTOMATIC1111/stable-diffusion-webui

关键设计：每次生成记录 prompt、seed、steps、采样器等参数，历史可回放。

对本项目的启示：生成参数即 recipe，必须随版本保存，才能「恢复/复用」。

## 2. 数据模型设计

### 2.1 现有基础

- `assets` 表已有 `version INTEGER DEFAULT 1`，但 `_sync_assets` 每次 `version = 1`，
  没有历史记录。
- `versions` 表占位：`id, project_id, entity_type, entity_id, version, payload, created_at`，
  业务未使用。
- 图片输出目前只有 `data_dir/generation_tests`（生图测试），资产图片还没有专属目录。

### 2.2 建议：扩展 `versions` 表

保留 `entity_type / entity_id` 通用性（未来角色/场景/道具版本都可复用），加列：

- `file_path TEXT NOT NULL DEFAULT ''`（图片文件路径）
- `model_id TEXT NOT NULL DEFAULT ''`
- `provider_id TEXT NOT NULL DEFAULT ''`
- `job_id TEXT NOT NULL DEFAULT ''`（来源生成 Job）
- `is_current INTEGER NOT NULL DEFAULT 0`（当前版本唯一标记）

`payload` 存 recipe JSON：

```json
{
  "prompt": "...",
  "negative_prompt": "",
  "aspect_ratio": "2:3",
  "art_style": "国风动漫",
  "width": 1024,
  "height": 1536
}
```

唯一约束：`(entity_type, entity_id, version)`。

### 2.3 文件布局

```text
data_dir/
└── projects/
    └── {project_id}/
        └── assets/
            └── {asset_id}/
                ├── v1.png
                ├── v2.png
                └── v3.png  ← current
```

好处：文件按项目/资产隔离，删除项目时随目录清理，版本文件天然按 id 定位。

## 3. 版本操作（MVP）

1. **新增版本**：生图成功后写 `versions` 行（version = 当前 max + 1），文件落
   `v{n}.png`，`is_current=1`（原 current 置 0），`assets.version` 同步为 n。
2. **历史列表**：`GET /api/projects/{pid}/assets/{asset_id}/versions`，
   返回每个版本的 recipe + 缩略图 URL + 是否 current + 时间。
3. **查看/下载**：`GET /api/.../versions/{version_id}/file`。
4. **恢复（promote）**：把选中版本置 current（`is_current` 切换 + `assets.version` 更新），
   不删除原文件。
5. **删除未使用版本**：仅非 current 版本可删（删记录 + 删文件）；当前版本不允许删除。

## 4. 与 Phase 13 生图的关系

Phase 9 单独做的边界：

- 本轮只实现「版本存储 + 历史列表 + 恢复 + 删除」的数据与接口，以及资产页的版本面板 UI。
- 生图写入版本的动作在 Phase 13 接入（生成后调用版本服务）；本轮先提供版本服务与
  手工导入/占位版本的基础测试，保证数据结构不阻碍后续生图。
- 不提前实现 Image Generation UI（Phase 13 的范围）。

## 5. 参考来源

- ComfyUI-GenAsset：https://github.com/steliosot/ComfyUI-GenAsset
- ComfyUI Asset Management：https://deepwiki.com/comfyanonymous/ComfyUI/2.6-asset-management-system
- Krita AI Diffusion：https://github.com/Acly/krita-ai-diffusion
- AUTOMATIC1111/stable-diffusion-webui：https://github.com/AUTOMATIC1111/stable-diffusion-webui
