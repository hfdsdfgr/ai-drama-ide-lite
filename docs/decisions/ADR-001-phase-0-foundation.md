# ADR-001: Phase 0 基础技术栈与目录结构

## Context

ROADMAP.md Phase 0 要求建立可运行的桌面应用基础：Git 仓库、前后端骨架、通信、测试、日志、错误处理，以及基础的 Settings / Project 页面。

## Decision

- 采用 monorepo 布局：`apps/desktop`（React + TypeScript + Vite）+ `apps/backend`（Python FastAPI）。
- 开发阶段前端直接通过 Vite 代理（`/api` → `127.0.0.1:8000`）访问后端，避免开发期 CORS/IPC 复杂度；Tauri 壳在 Rust 工具链就绪后初始化。
- Phase 0 的 Project 持久化使用项目目录下 JSON 文件（`ProjectStore`），满足「创建 / 保存 / 重新打开」完成标准；Phase 1 迁移到 SQLite。
- 前端 lint 使用 Vite 模板自带的 oxlint，格式化使用 Prettier；后端测试使用 pytest，前端测试使用 Vitest。

## Alternatives

- Electron：包体积与内存占用更大，对个人创作者工具不友好。
- 直接初始化 Tauri：本机尚无 Rust 工具链，先让前后端跑通黄金路径，再补桌面壳，降低初期复杂度。
- SQLite 一步到位：Phase 1 才需要完整数据模型，Phase 0 引入会过早扩大范围。

## Reason

先跑通、再扩展（ROADMAP 核心原则 1）；避免过早抽象与过早依赖（DEVELOPMENT_RULES 第 28、29、30 条）。

## Consequences

- 浏览器开发模式可用，Tauri 打包前需要额外安装 Rust 并初始化 `src-tauri`。
- Phase 1 需要将 `ProjectStore` 从 JSON 文件替换为 SQLite，并保持既有 API 契约不变。
