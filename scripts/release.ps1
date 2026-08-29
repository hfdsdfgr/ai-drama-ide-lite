# 一键发布（Phase 21 Auto Update）：
# 构建（带签名 updater 产物）-> 生成 latest.json -> gh release 上传。
#
# 用法：
#   powershell -ExecutionPolicy Bypass -File scripts\release.ps1 -Notes "更新说明"
# 可选：-Version 0.1.2（默认读取 tauri.conf.json 的版本）
param(
  [string]$Version = "",
  [string]$Notes = ""
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

# 签名密钥（本机生成，不入仓库；丢失则无法再发更新）
$keyDir = Join-Path $env:USERPROFILE '.tauri'
$keyFile = Join-Path $keyDir 'ai-drama-ide.key'
$passFile = Join-Path $keyDir 'ai-drama-ide.key.pass'
if (-not (Test-Path -LiteralPath $keyFile) -or -not (Test-Path -LiteralPath $passFile)) {
  throw "签名密钥缺失：$keyFile / $passFile（请先运行 npx tauri signer generate）"
}
$env:TAURI_SIGNING_PRIVATE_KEY_PATH = $keyFile
$env:TAURI_SIGNING_PRIVATE_KEY_PASSWORD = (Get-Content -LiteralPath $passFile -Raw).Trim()

# 1) 构建（PyInstaller 后端 + Tauri release，含 updater artifacts）
& (Join-Path $PSScriptRoot 'tauri-build.ps1')

# 2) 定位产物
$bundle = Join-Path $root 'apps\desktop\src-tauri\target\release\bundle'
$nsisZip = Get-ChildItem -Path $bundle -Recurse -Filter '*.nsis.zip' -ErrorAction Stop | Select-Object -First 1
$sig = Get-ChildItem -Path $bundle -Recurse -Filter '*.sig' -ErrorAction Stop | Select-Object -First 1
$installer = Get-ChildItem -Path (Join-Path $bundle 'nsis') -Filter '*.exe' -ErrorAction Stop | Select-Object -First 1

if (-not $Version) {
  $conf = Get-Content -Raw (Join-Path $root 'apps\desktop\src-tauri\tauri.conf.json') | ConvertFrom-Json
  $Version = $conf.version
}

# 3) latest.json（updater 静态清单，托管在 GitHub Releases）
$sigContent = (Get-Content -LiteralPath $sig.FullName -Raw).Trim()
$fileName = Split-Path -Leaf $nsisZip.Name
$downloadUrl = "https://github.com/hfdsdfgr/ai-drama-ide-lite/releases/download/v$Version/$fileName"
$latest = @{
  version = $Version
  notes   = $Notes
  pub_date = (Get-Date).ToUniversalTime().ToString('o')
  platforms = @{
    'windows-x86_64' = @{
      url       = $downloadUrl
      signature = $sigContent
    }
  }
} | ConvertTo-Json -Depth 5
$latestFile = Join-Path $root 'latest.json'
Set-Content -LiteralPath $latestFile -Value $latest -Encoding utf8
Write-Output "latest.json: $latestFile"

# 4) 发布 GitHub Release
if (Get-Command gh -ErrorAction SilentlyContinue) {
  gh release create "v$Version" `
    $nsisZip.FullName `
    $sig.FullName `
    $installer.FullName `
    $latestFile `
    --title "v$Version" `
    --notes $Notes
  Write-Output "Released v$Version"
} else {
  Write-Output "未安装 gh，跳过发布。产物与 latest.json 已就绪，可手动上传："
  Write-Output "  $($nsisZip.FullName)"
  Write-Output "  $($sig.FullName)"
  Write-Output "  $($installer.FullName)"
  Write-Output "  $latestFile"
}
