# 调研：Tauri 2 自动更新（Phase 21 — Auto Update）

> 调研时间：2026-08-14。规则 75（Research Before Every Step）。
> 参考：https://v2.tauri.app/plugin/updater/

## 结论

用 **tauri-plugin-updater + 静态 JSON（托管在 GitHub Releases）**：
官方插件负责校验/下载/安装，GitHub Releases 当静态文件服务器，零自建后端。
Windows 走 NSIS 更新包（`nsis.zip` + `.sig`），默认 passive 安装模式（小进度窗、免交互）。

## 1. 强制要求：签名密钥

Updater **必须签名，不能跳过**（官方硬性要求）。

- 生成：`npx tauri signer generate -w ~/.tauri/ai-drama-ide.key`（同时给出公钥）。
- 公钥 → `tauri.conf.json` 的 `plugins.updater.pubkey`（可安全公开）。
- 私钥 → 构建时经环境变量提供：`TAURI_SIGNING_PRIVATE_KEY`（内容）+ `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`。
  `.env` 文件不生效（官方明确），需要进程环境变量或 CI secrets。
- **私钥丢失 = 现有用户永远无法再更新**，必须妥善保管（本机 `~/.tauri/` + 密码，CI 放 secrets）。

## 2. 配置（三处）

1. 依赖：`Cargo.toml` 加 `tauri-plugin-updater = "2"`；前端 `npm i @tauri-apps/plugin-updater`。
2. `lib.rs`：`.plugin(tauri_plugin_updater::Builder::new().build())`。
3. `tauri.conf.json`：
   - `bundle.createUpdaterArtifacts: true`（Windows 产出 `*-setup.exe.nsis.zip` + `.sig`）
   - `plugins.updater.pubkey`：公钥
   - `plugins.updater.endpoints`：静态 JSON URL 数组（TLS 强制；非 2XX 才切下一个）
4. `capabilities`：加 `updater:default`（check / download / install）。

## 3. 更新服务：静态 JSON（GitHub Releases）

端点 URL 形如：
`https://github.com/hfdsdfgr/ai-drama-ide-lite/releases/latest/download/latest.json`

JSON 结构（`platforms.windows-x86_64` 为当前目标）：

```json
{
  "version": "0.1.1",
  "notes": "更新说明",
  "pub_date": "2026-08-14T00:00:00Z",
  "platforms": {
    "windows-x86_64": {
      "url": "https://github.com/hfdsdfgr/ai-drama-ide-lite/releases/download/v0.1.1/AI.Drama.IDE.Lite_0.1.1_x64-setup.exe.nsis.zip",
      "signature": "<.sig 文件内容>"
    }
  }
}
```

必填：`version`、`platforms.<target>.url`、`platforms.<target>.signature`。

## 4. 前端触发

`@tauri-apps/plugin-updater` 的 `check()` → `update.downloadAndInstall()` → `relaunch()`。
建议：设置页「检查更新」按钮（手动）+ 启动时静默检查（可选，弹提示不自动装）。

## 5. 发布流程（每次发版）

1. `scripts/tauri-build.ps1`（带签名环境变量）→ 产出 `nsis.zip` + `.sig`
2. 组装 `latest.json`（版本 / notes / URL / signature）
3. `gh release create vX.Y.Z --assets nsis.zip,latest.json,...`

可写 `scripts/release.ps1` 一条命令完成：构建 → 签名产物 → latest.json → gh release。

## 6. 取舍与注意

- **v0.1.0 无签名**：刚发布没人用，从下一版（v0.1.1 起）启用 updater 即可，旧安装包不影响。
- **GitHub Releases 国内下载可能慢**：用户已接受（发布流程就是 GitHub）。
- **Windows 更新会自动退出 app 再安装**：插件行为，安装完可自动 relaunch。
- **passive 安装模式**：小进度窗、免交互，推荐；`quiet` 模式无法请求管理员权限（本应用 perUser 安装无影响，但仍推荐 passive）。
- 私钥密码不进仓库（本机环境变量 / CI secrets）。
