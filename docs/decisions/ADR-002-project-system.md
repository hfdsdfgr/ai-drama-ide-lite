# ADR-002: Phase 1 项目系统（SQLite + 文件系统 + 导入导出）

## Context

Phase 1 需要建立整个项目的数据基础：结构化数据持久化、跨重启恢复、导入导出、自动保存与 ID 规范（ROADMAP.md Phase 1）。

## Decision

- **SQLite 为结构化数据唯一事实源**：数据库文件 `data/ai_drama_ide.db`，使用 Python 标准库 `sqlite3`（不引入 ORM）。
- **基线 schema 一次建齐全部实体表**（projects/novels/stories/characters/locations/props/episodes/scenes/shots/assets/jobs/versions），先放核心字段，后续阶段用幂等迁移加列。
- **大文件走文件系统**：每个项目一个目录 `data/projects/{project_id}/`，含 novel/story/scripts/characters/locations/props/storyboards/generations/jobs 子目录（DEVELOPMENT.md 第 48 节）。
- **软删除**：projects 表 `deleted_at` 标记，不物理删除用户数据。
- **导入导出**：zip 内含 `project.json` manifest + `files/` 文件树；导入生成新 Project ID；严格校验 zip 条目（拒绝绝对路径、盘符、`..`，防 zip-slip）。
- **旧数据迁移**：启动时把 Phase 0 遗留的 JSON 项目文件迁入 SQLite，成功后归档到 `data/projects/.archive/`。
- **ID 规范**：Project ID `proj_{hex}`；Asset ID `{asset_type}_{slug}_{seq:03d}`（如 `character_lin_fan_001`，中文名保留原文）。

## Alternatives

- 继续用 JSON 文件存储：无法支撑后续 Phase 的关联查询与一致性需求。
- SQLAlchemy / ORM：Phase 1 的访问模式简单，标准库 `sqlite3` 足够，避免过早抽象（DEVELOPMENT_RULES 第 28 条）。
- 按阶段逐个建表：与「建立整个项目的数据基础」目标不符，且幂等迁移机制已就绪。

## Reason

符合 DEVELOPMENT.md 第 48 节数据存储设计与 ROADMAP Phase 1 完成标准；保持 API 契约不变，前端可平滑升级。

## Consequences

- 后续阶段新增字段必须走幂等迁移（`ALTER TABLE ... ADD COLUMN` 包 try/except）。
- 导入失败可能留下部分写入的新项目（MVP 阶段接受，后续可加事务化导入）。
- 软删除项目不再出现在列表，但数据保留可恢复。
