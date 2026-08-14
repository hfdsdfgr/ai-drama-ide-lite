# 依赖清单

> AI Drama IDE Lite 开发/构建所需依赖汇总。
> 版本以各包清单文件为准（`package.json` / `requirements.txt` / `Cargo.toml`），本文档用于快速查阅。

## 1. 环境要求

- Windows 10/11（当前开发环境为 Windows）
- Python 3.12+（使用 `apps/backend/.venv`）
- Node.js 20+（含 npm）
- Git
- Rust GNU 工具链（`stable-x86_64-pc-windows-gnu`，rust 1.77.2+）
- MinGW 13.1（本机：`C:\Qt\Tools\mingw1310_64`）
- WebView2 Runtime（安装包通过 `embedBootstrapper` 自动补齐）

> 说明：本项目使用 MinGW + Rust GNU 工具链构建 Tauri，不能使用 MSVC 工具链；项目路径含空格，编译需通过无空格 junction 路径（见 `DEVELOPMENT_PITFALLS.md`）。

## 2. 前端 `apps/desktop`

安装：`cd apps/desktop && npm install`

### dependencies

- @dnd-kit/core `^6.3.1`
- @dnd-kit/sortable `^10.0.0`
- @dnd-kit/utilities `^3.2.2`
- @tauri-apps/api `^2.11.1`
- react `^19.2.8`
- react-dom `^19.2.8`

### devDependencies

- @tauri-apps/cli `^2.11.4`
- @types/node `^24.13.3`
- @types/react `^19.2.17`
- @types/react-dom `^19.2.3`
- @vitejs/plugin-react `^6.0.4`
- oxlint `^1.75.0`
- prettier `^3.9.6`
- typescript `~6.0.2`
- vite `^8.2.0`
- vitest `^4.1.10`

## 3. 后端 `apps/backend`

安装：`cd apps/backend && .venv\Scripts\python.exe -m pip install -r requirements-dev.txt`

### requirements.txt

- fastapi `>=0.115`
- uvicorn[standard] `>=0.30`
- pydantic-settings `>=2.5`
- python-docx `>=1.1`
- httpx `>=0.27`
- keyring `>=25.0`

### requirements-dev.txt（开发额外）

- pytest `>=8.0`
- httpx `>=0.27`

## 4. Tauri / Rust `apps/desktop/src-tauri`

依赖由 `Cargo.toml` 声明：

- tauri `2.11.3`
- tauri-plugin-log `2`
- serde `1.0`（features: derive）
- serde_json `1.0`
- log `0.4`
- tauri-build `2.6.3`（build-dependency）

## 5. 一键安装

```powershell
# 后端
cd apps/backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

# 前端
cd ..\desktop
npm install

# Rust GNU 工具链（如未安装）
rustup toolchain install stable-x86_64-pc-windows-gnu --profile minimal
rustup default stable-x86_64-pc-windows-gnu
```
