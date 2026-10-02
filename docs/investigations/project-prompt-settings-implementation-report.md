# 项目级提示词自定义实施报告

日期：2026-10-02。

## 使用路径与行为

选中项目 → 设置 → 项目提示词 → 选择创作环节 → 编辑创作规则 → 预览 / 保存。

22 个环节覆盖小说大纲、章节和续写 / 扩写 / 重写，故事抽取与合并，剧本、分镜、资产补全，四类图片、镜头视频及六类质量审核。保存后，新操作使用自定义规则替换默认创作规则；素材、参考描述与单次生成要求继续作为输入。用户可恢复当前环节默认配置。

JSON / 正文格式和素材指令隔离保持为不可编辑契约；小说动作编辑中的 Story Bible 原文由 system 移至 user，避免将素材提升为系统指令。结构化结果继续使用已有 Pydantic 校验，JSON 修复保留原规则与 Schema；审核结果要求 `consistent` 为布尔值、`issue` 为文本。

媒体规则允许留空。图片负向词支持默认、自定义和不使用；文本环节禁止空创作规则。预览是本地规则层预览，生成时才加入实际素材，不创建 Job、不调用 Provider。

## 实现边界

- `prompt_catalog.py` 集中保存默认规则、固定契约和媒体默认片段；各服务只负责加入当前业务素材。默认媒体路径保留原有条件组装行为。
- `project_prompt_settings` 新表仅保存项目覆盖值和修订号，通过幂等建表加入现有 SQLite；不清空或重建已有数据。
- 配置 API 位于 `/api/projects/{project_id}/prompt-settings`：GET 查询，PUT `/{stage_id}` 保存，POST `/{stage_id}/preview` 预览。严格类型、长度限制与修订号保护阻止非法配置和并发覆盖。
- `rules: null` 恢复该环节全部默认配置；媒体 `rules: ""` 清空创作约束。负向词省略保留当前值，`null` 恢复默认，`""` 明确不使用。
- 单次操作在启动时读取配置；后台任务及项目 / 剧集 Pipeline 保存有效配置快照，子任务复用同一份快照。同一任务恢复或重试不改用新配置；旧 Pipeline 首次恢复时补存快照。
- 项目导出 / 导入包含覆盖值，旧 manifest 1 / 2 / 3 无配置时使用内置默认。导入配置先校验，提示词文字不参与实体 ID 重映射。
- 前端保留项目草稿，阻止未保存时切换环节；并发冲突时保留编辑并提示刷新。切换项目不会混用草稿或保存结果。

未加入全局预设、角色 Prompt Patch、导演情绪 / Pose 控制、自动重新生成、额外 Provider 请求或应用依赖。内部修复提示词、厂商协议和旧音频台词归属工具不开放配置。

## 验证

- 后端全量：**447 passed**。覆盖配置边界、项目隔离、修订冲突、免费预览、旧数据库与项目包兼容、媒体规则实际进入请求、默认规则不重复追加、空值、文本消息隔离及两条 Pipeline 暂停恢复快照。最后将项目 Pipeline 的配置读取提前到状态重置前，防止配置损坏时覆盖原进度；此补充及两条 Pipeline 的定向回归 **16 passed**。
- 前端：**39 passed**；TypeScript、oxlint 和 Vite build 通过。
- 本地数据库只读检查：原有 3 个项目、4 本小说、181 个任务和 123 个版本保持原数量；新配置表尚无用户配置。
- 浏览器验收：`scripts/verify-prompt-settings-ui.mjs` 实际运行 **PASS**，通过外部临时 Playwright 与本地 Vite 挂载设置页，拦截 API。验证默认加载、草稿、规则预览、空媒体规则 / 负向词、保存与恢复、409 草稿保留、项目切换隔离及无项目入口；1440px / 900px 截图人工检查通过，无横向溢出或浏览器异常。只有刻意模拟的 HTTP 409 控制台记录。

后端仅有已有 Starlette/httpx 和 Python sqlite3 datetime adapter 弃用提示。未调用付费 API；真实模型生成质量和桌面安装包未在本轮验证。

## 复现

```powershell
cd apps/backend
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_tmp_prompt_verify

cd ../desktop
npm test
npm run lint
npm run build
```

浏览器验收先启动桌面前端 Vite，再从仓库根目录执行：

```powershell
node scripts/verify-prompt-settings-ui.mjs <Playwright模块目录> <ViteURL> <输出目录>
```

Playwright 仅用于本地验收，不加入应用依赖。所有验收请求使用 Mock。
