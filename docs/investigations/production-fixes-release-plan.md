# 生产修复与发布计划

日期：2026-10-03。目标版本：0.2.62（兼容历史 0.2.61 的版本比较）。

用户路径：按集 / 项目开始制作 → 生成子任务正常执行 → 暂停、恢复或取消 → 镜头配音 → 合成场景 / 分集 → 下载修复版安装包。

## 范围与方案

- 修复单 Worker 被流水线等待子任务阻塞的问题。向 PipelineService 注入执行子任务的回调，等待 queued 子任务时复用 Worker 的领取 / 执行逻辑；仍顺序执行，不增加线程或应用依赖。
- 统一覆盖项目与按集流水线，保留暂停、取消、已提交远程任务 ID、失败分类及阶段确认。停止 Worker 时结束本地等待，将父 / 子任务保留为可恢复状态。
- 场景合成优先采用匹配当前源视频的配音版本；无配音时沿用源视频。新配音记录精确源视频版本，旧记录按生成顺序保持兼容。过期配音不用于新镜头；记录合成实际选用版本。
- 不增加自动配音、字幕、批量并发、制作向导或数据库迁移。
- 更新后端 / Tauri / Cargo 版本与 README，提交并推送修复，使用现有标签触发 Windows / macOS CI 发布，核验安装包、签名和 updater 清单。

## 关键文件

`job_worker.py`、`pipeline_service.py`、`main.py`、`audio_dubbing_service.py`、`video_sequence_service.py`，相关后端测试，以及版本文件 / 发布文档。

## 风险与验证

- 子任务重复领取、暂停 / 取消期间继续生成、恢复重复收费：使用真实持久化 Job + 模拟 Adapter 验证排队、失败、暂停、取消及已提交远程 ID 恢复，禁止调用付费 API。
- 配音与旧画面错配：验证源版本匹配、旧记录兼容、重做镜头后排除过期配音，以及真实 FFmpeg 输出中的音轨。
- 发布范围包括此前已推送的项目提示词和离线教程，发布说明列出这些功能。
- 后端全量测试、前端测试 / lint / type check / build；核对 diff、清理测试临时数据；按照用户已授权的「修复后发布」继续执行。
- 本地调试后端用 lifespan off 验证，避免启动用户已有排队付费任务；Release 采用原有正式启动方式。

## 调研依据

[Python 官方文档](https://docs.python.org/3/library/concurrent.futures.html#threadpoolexecutor) 明确展示单 Worker 等待同一执行器中的子任务会阻塞。保留当前顺序执行的约束，复用现有执行器，比增加池和调度线程更符合本次修复范围。

发布沿用 `.github/workflows/release.yml` 的标签构建和 [GitHub Release 流程](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。只有安装包和 updater 元数据齐全并核验后，才报告发布完成。

## 本地验证结果

- 后端全量：459 passed，5 条已有依赖 / SQLite 弃用警告。
- 前端：42 passed；lint、TypeScript 检查与生产构建通过。
- 真实排队回归：项目 / 按集父子任务顺序完成，失败不自动重试，暂停恢复复用远程 ID；取消与 Worker 停止结束本地轮询。
- 真实 FFmpeg：原视频无声时使用配音版，场景与分集成片均有音轨；旧配音记录兼容，新镜头与旧配音错配被拒绝。
- HTTP 冒烟：独立临时数据库启动新版后端（lifespan off）；health、version、OpenAPI 均返回 200 / 0.2.62。
- 四处应用版本一致，0.2.62 高于历史 0.2.61；远程不存在 v0.2.62 标签。
- 初次 pytest 被已有 `.pytest_tmp` 的权限阻止，改用独立目录后全量通过；验证脚本显式使用 UTF-8。
- 本轮三个 pytest 临时目录与 HTTP 冒烟数据库已删除，冒烟后端已停止；未改动用户项目、旧测试目录或凭据，未调用付费 AI API。

CI 发布与安装包核验在标签推送后进行，本节的本地验证不替代双平台打包结果。

## 发布结果

- 标签 `v0.2.62` 对应 `15c5687`；修复提交分别为 `3e03fac`（流水线）、`e546e47`（有声合成）。
- [Build & Release #37130113387](https://github.com/hfdsdfgr/ai-drama-ide-lite/actions/runs/37130113387) 的双平台后端、桌面端与 Release 作业全部成功。
- [正式 Release](https://github.com/hfdsdfgr/ai-drama-ide-lite/releases/tag/v0.2.62) 已于 2026-10-03 14:42:37 UTC 发布，并成为 latest。发布说明已采用 `docs/releases/v0.2.62.md`。
- 六项发布资产齐全：Windows 安装包及签名、macOS Apple Silicon DMG、macOS 更新包及签名、`latest.json`。
- 更新清单版本为 0.2.62，包含 `windows-x86_64` 与 `darwin-aarch64`；更新地址与 Release 下载地址一致，清单签名与 `.sig` 文件相同。
- 下载两个完整更新包，用 Node 内置 crypto 按 [Minisign 官方格式](https://jedisct1.github.io/minisign/) 验证应用内置公钥的 Ed25519 文件签名和 trusted comment，均通过；大小与 SHA-256 也与 GitHub Release 记录一致。
  - Windows：66,384,896 bytes；`a56bca9054804b461d5961fb8055b5243a0856c26a10f85f5d6b79bd17317233`。
  - macOS 更新包：53,021,990 bytes；`eef985ae82fd864b8c08e3ee9b2cc35e20106e4cb44fb161750797b329fb9cdc`。
- 首次 Node 下载未使用本机代理而超时，使用已配置代理后验证通过；未改变系统代理或应用配置。
- 校验工具及下载临时文件已清理；没有安装到用户设备，没有实机安装 / 升级测试，也没有真实服务商的付费生成实测。
