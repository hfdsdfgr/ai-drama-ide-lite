# 调研：Tauri 2 Windows 打包（Phase 21 前置）

> 调研时间：2026-08-14。规则 75（Research Before Every Step）。

## 结论

推荐 **NSIS（`-setup.exe`）单文件安装包**：多语言（含简体中文）、默认 perUser
免管理员安装、单文件分发，适合个人桌面用户；MSI（WiX）面向企业/GPO 部署，
对当前用户场景不必要。

## 1. 安装包类型对比（官方文档）

| 类型 | 产物 | 特点 | 适用 |
| --- | --- | --- | --- |
| NSIS | `*-setup.exe` | 单文件、多语言、默认 perUser（免管理员）、`/S` 静默 | 个人桌面分发（推荐） |
| MSI（WiX） | `*.msi` | 企业静默/组策略部署，需 WiX v3 工具 | 企业 IT 分发 |

- 默认安装模式为 perUser（装到 `%LOCALAPPDATA%`，免管理员）；`installMode: both`
  可让用户选择，但需管理员权限。
- NSIS 多语言可配 `bundle.windows.nsis.languages`，默认跟随系统语言。
- WebView2 默认 `downloadBootstrapper`（需联网，体积 +0）；离线环境可选
  `offlineInstaller`（+127MB）。

参考：https://v2.tauri.app/distribute/windows-installer/

## 2. Python 后端打包：PyInstaller + Sidecar（官方推荐）

官方文档明确：sidecar 常见用例就是「PyInstaller 打包的 Python API 服务器」。

- `bundle.externalBin: ["binaries/ai-drama-backend"]`，产物必须带 target triple
  后缀：`ai-drama-backend-x86_64-pc-windows-msvc.exe`。
- Rust 侧 `tauri_plugin_shell::ShellExt` + `shell().sidecar()` spawn；需新增
  `tauri-plugin-shell` 依赖并在 capabilities 里授权。
- 前端在 JS 侧也可 `Command.sidecar()`（需插件权限）。

参考：
- https://v2.tauri.app/develop/sidecar/
- https://github.com/dieharders/example-tauri-v2-python-server-sidecar（Tauri v2 + PyInstaller 后端示例）

## 3. 本项目打包前必须改造的点

1. **后端启动/停止**：当前后端是外部手动 uvicorn，打包版必须由 Tauri 壳
   spawn sidecar（启动时拉起、退出时 kill）。
2. **数据目录**：`config.py` 的 `data_dir = BACKEND_ROOT / "data"`，PyInstaller
   onefile 运行时 `__file__` 在临时解压目录，数据会丢。打包版必须改到
   `%APPDATA%\AI Drama IDE Lite\data`（frozen 检测）。
3. **前端 API 地址**：生产版前端由 Tauri asset protocol 加载，`fetch('/api')`
   不会到 `127.0.0.1:8000`。需要前端 base URL 改为绝对地址
   `http://127.0.0.1:8000`，后端 CORS 放行 Tauri origin（`tauri://localhost` / `http://tauri.localhost`）。
4. **端口冲突**：8000 可能被占用，sidecar 启动时动态找空闲端口（8000-8010），
   端口如何传给前端需定方案（如写本地文件 / Tauri event）。
5. **构建环境**：MinGW GNU 工具链 + 无空格 junction 路径（沿用
   `scripts/tauri-dev.ps1` 的思路写 build 脚本）。
6. **签名**：无代码签名证书，SmartScreen 会警告；正式分发需 OV/EV 证书
   （属 Phase 21 完整项，本地打包可先跳过）。
7. **WebView2**：默认联网下载 bootstrapper 即可（目标用户基本都有 Edge/WebView2）。

## 4. 预计产物与体积

- 安装包：`AI Drama IDE Lite_0.1.0_x64-setup.exe`
- 体积：Tauri 壳 ~10MB + PyInstaller onefile 后端（fastapi/uvicorn/keyring 等）
  约 60-100MB，合计预计 80-120MB。

## 5. 建议实施顺序

1. 后端 PyInstaller 打包脚本（onefile + frozen 数据目录迁移）
2. Tauri 壳集成 sidecar（spawn/stop + 动态端口）
3. 前端 API base URL 适配生产（+ CORS）
4. NSIS 配置（productName / languages / installMode）
5. 构建脚本（junction + MinGW PATH）→ 产出安装包 → 安装验证
