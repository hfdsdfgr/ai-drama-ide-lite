# ADR-003: Phase 2 小说工作室（Novel Studio）

## Context

Phase 2 需要让用户把「故事」放进系统：新建或导入小说（TXT / Markdown / DOCX），章节管理，编辑与保存，搜索（ROADMAP.md Phase 2）。

## Decision

- **小说内容以 SQLite 为唯一事实源**（`novels.content` / `chapters.content` 文本字段），暂不做项目目录下的文件镜像：MVP 阶段小说体量适合入库，搜索与导入导出更简单，避免双写不一致。
- **章节结构化**：新增 `chapters` 表（project_id / novel_id / title / content / order_index / deleted_at），旧库通过幂等 `ALTER TABLE` 迁移补 `deleted_at`。
- **导入**：TXT / Markdown 先做编码探测（utf-8-sig → utf-8 → gb18030，见 DEVELOPMENT_PITFALLS.md），按 Markdown 标题（`#`/`##`/`###`）切分章节，无标题则整篇一章；DOCX 用 python-docx 按 Heading 样式切分。
- **搜索**：SQL LIKE 匹配小说标题 + 章节标题 + 章节内容（MVP 够用，后续可换 FTS5）。
- **AI 创作**：续写 / 扩写 / 重写仅在 UI 放置明确标注的占位入口，不造假实现（DEVELOPMENT_RULES 第 53 条），等待 Phase 3 Provider 系统。
- **项目导入导出升级到 manifest v2**：携带 novels + chapters 结构化数据，导入时重建（生成新 ID），避免「导出的小说在导入后丢失」。

## Alternatives

- 小说原文镜像到项目目录文件：增加双写一致性与导入复杂度，MVP 阶段收益低。
- 自由文本整体编辑（不分章）：与「Chapter Management」任务冲突。
- 导入时就做复杂章节探测（如识别「第X章」模式）：脆弱且不可靠，改为只按 Markdown 标题这种确定性规则分章。

## Reason

满足 Phase 2 完成标准（新建 / 导入 → 编辑 → 保存）并保持数据一致性；遵循「不做脆弱解析、不造假、不过早复杂化」的开发规则。

## Consequences

- 大文本小说后期可迁移到文件存储 + FTS5 搜索（届时走幂等迁移）。
- manifest v2 与 v1 兼容：导入 v1 包不报错（无小说数据）。
