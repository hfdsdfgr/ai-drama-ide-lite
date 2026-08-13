# 打包 Python 后端为 PyInstaller onefile exe，并复制为 Tauri sidecar。
#
# 用法：powershell -ExecutionPolicy Bypass -File scripts\build-backend.ps1
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'apps\backend'
$distExe = Join-Path $backend 'dist-bundle\ai-drama-backend.exe'
$sidecarDir = Join-Path $root 'apps\desktop\src-tauri\binaries'
# 运行时按 Rust 目标 triple（GNU）解析，Tauri bundler 按 Windows 默认 triple（MSVC）解析：两个后缀都要有。
$sidecarNames = @('ai-drama-backend-x86_64-pc-windows-gnu.exe','ai-drama-backend-x86_64-pc-windows-msvc.exe')

Push-Location $backend
try {
  .\.venv\Scripts\python.exe -m PyInstaller `
    --noconfirm --clean `
    --onefile `
    --name ai-drama-backend `
    --collect-data docx `
    --add-data "$backend\app\db\schema.sql;app\db" `
    --add-data "$backend\app\services\vendor_models.json;app\services" `
    --hidden-import keyring.backends.Windows `
    --distpath dist-bundle `
    --workpath build\pyinstaller `
    --specpath build `
    server_entry.py
} finally {
  Pop-Location
}

if (-not (Test-Path -LiteralPath $distExe)) {
  throw "PyInstaller 输出缺失: $distExe"
}

New-Item -ItemType Directory -Path $sidecarDir -Force | Out-Null
foreach ($name in $sidecarNames) {
  $sidecarExe = Join-Path $sidecarDir $name
  Copy-Item -LiteralPath $distExe -Destination $sidecarExe -Force
  Write-Output "Backend bundled: $sidecarExe"
}
