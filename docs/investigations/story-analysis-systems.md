# 调研：LLM Story Engine 设计依据（Phase 6）

> 调研时间：2026-08-13。规则 75（Research Before Every Step）。
> 目的：确定「小说 → 结构化故事数据 → Story Bible」的实现方式。

## 结论摘要

1. **长篇小说不能一次塞给 LLM，主流做法是「分章提取 + 滚动摘要 + 合并」**
   （map-reduce）：
   - Omniscient-Novel-Reader（开源）：Pass1 逐章节提取角色，携带
     `rolling_summary`（前文摘要）和已积累的 characters JSON，最后 Consolidation
     合并去重。来源：https://huggingface.co/spaces/build-small-hackathon/Omniscient-Novel-Reader
   - Text2Dialog（开源）：长文本分块 → LLM 抽取 → **Schema 校验** → 合并；
     带断点续传。来源：https://github.com/zw-zhtlab/Text2Dialog
2. **Story Bible 是「结构化实体 + 持续更新」**：
   - NovelCrafter Codex：自动索引文本中角色/地点/物品的每次提及，动态更新旧 lore。
     其基准（nc-bench）就是「从散文提取结构化的 characters/locations/objects/lore」。
     来源：https://www.novelcrafter.com/features/codex
   - Sudowrite Story Bible 六段：Characters / Worldbuilding / Style / Outline /
     Synopsis / Braindump，角色卡含性格、语癖、跨章节演变。来源：
     https://sudowrite.com/blog/story-bible-template-how-to-build-one-and-how-sudowrite-does-it-for-you/
3. **LLM 输出必须走「结构化 Schema + 校验 + 修复/人工兜底」**：
   - 抽取结果用 Pydantic/JSON Schema 解析校验（hackathon 项目结论：Pydantic 比裸 JSON
     更适合 LLM 适配）。来源：https://github.com/IsPHao/hackathon/issues/59
   - 校验失败 → 有限重试（把错误喂回模型修复）→ 仍失败则标记部分结果，交给人工。
4. **冲突/情节线/伏笔属于全书级分析**：单章只做实体与事件抽取，冲突分析、
   情节线、伏笔放在 Consolidation（全书视角）阶段，避免单章判断失真。

## 对 Phase 6 的影响

- 管线：逐章抽取（携带滚动摘要 + 已抽实体）→ 全书合并（实体去重 + 冲突/情节线/伏笔）
- LLM 输出：Pydantic Schema 校验，失败重试一次，仍失败标记「部分完成」交人工
- 存储：复用 Phase 1 预留的 stories / characters / locations / props 表
- 任务：整本分析耗时数分钟，用 Job 思维（真实进度「分析第 N/M 章」）；
  持久化 Job 系统属 Phase 10，本轮沿用内存任务 + 可重跑
- 单模型顺序调用（符合产品「单模型生成」约束；不并行）
