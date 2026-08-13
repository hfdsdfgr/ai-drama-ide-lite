# 启动 Tauri 桌面开发模式。
#
# 背景：MinGW 的 windres/ld 无法处理含空格的路径（G:\Vibe Coding\AICV），
# 因此通过无空格 junction 路径构建（见 DEVELOPMENT_PITFALLS.md 第 9 节）。

$ErrorActionPreference = 'Stop'

$link = 'C:\Users\Administrator\ai-drama-ide'
$target = (Resolve-Path 'G:\Vibe Coding\AICV').Path

if (-not (Test-Path -LiteralPath $link)) {
  New-Item -ItemType Junction -Path $link -Target $target | Out-Null
  Write-Host "Created junction: $link -> $target"
}

$env:PATH = "C:\Qt\Tools\mingw1310_64\bin;$env:USERPROFILE\.cargo\bin;$env:PATH"

Push-Location (Join-Path $link 'apps\desktop')
try {
  npm run tauri dev
} finally {
  Pop-Location
}
