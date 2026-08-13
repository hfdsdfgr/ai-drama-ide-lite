# 一键打包安装包：Python 后端（PyInstaller sidecar） + Tauri release + NSIS。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts\tauri-build.ps1
$ErrorActionPreference = 'Stop'

# 1) 先打包后端 sidecar
& (Join-Path $PSScriptRoot 'build-backend.ps1')

# 2) 无空格 junction（MinGW windres/ld 无法处理含空格路径）
$link = 'C:\Users\Administrator\ai-drama-ide'
$target = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not (Test-Path -LiteralPath $link)) {
  New-Item -ItemType Junction -Path $link -Target $target | Out-Null
  Write-Output "Created junction: $link -> $target"
}

$env:PATH = "C:\Qt\Tools\mingw1310_64\bin;$env:USERPROFILE\.cargo\bin;$env:PATH"

# crates.io 下载走本机代理（构建机环境依赖）
$env:HTTP_PROXY = 'http://127.0.0.1:10808'
$env:HTTPS_PROXY = 'http://127.0.0.1:10808'

Push-Location (Join-Path $link 'apps\desktop')
try {
  npm run tauri build
} finally {
  Pop-Location
}

$installer = Get-ChildItem -Path (Join-Path $link 'apps\desktop\src-tauri\target\release\bundle\nsis') -Filter '*.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($installer) {
  Write-Output "INSTALLER: $($installer.FullName)"
} else {
  throw 'NSIS installer not found'
}
