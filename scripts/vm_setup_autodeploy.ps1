# ============================================================
#  绘本网站 · 服务器「自动部署」一次性配置（只需在服务器上跑一次）
#  做的事：
#    1) 确保有 git（没有就下载便携版 MinGit 到用户目录，免管理员）
#    2) 把现有部署目录原地变成 git 仓库（保留 .venv / .env / outputs）
#    3) 补装依赖
#    4) 注册计划任务：每 2 分钟自动拉取最新代码并重启网站
#    5) 立即重启一次网站，确保跑的是最新代码
#
#  之后：本地双击「发布更新.bat」-> 约 2 分钟后本机自动更新，无需再手动操作。
# ============================================================
param(
    [string]$Dst    = "C:\Users\suqianxue\Desktop\绘本网站_部署包",
    [string]$Repo   = "https://github.com/jeredithia-ai/picturebook-auto.git",
    [string]$Branch = "master"
)
$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

Write-Host "=== 绘本网站 · 自动部署一次性配置 ===" -ForegroundColor Cyan
Write-Host "部署目录: $Dst"

# ---------- 1) 确保有 git ----------
function Get-GitPath {
    try { $null = & git --version 2>$null; if ($LASTEXITCODE -eq 0) { return "git" } } catch {}
    $p = Join-Path $env:LOCALAPPDATA "PicturebookGit\cmd\git.exe"
    if (Test-Path $p) { return $p }
    return $null
}
$git = Get-GitPath
if (-not $git) {
    Write-Host "未发现 Git，下载便携版 MinGit（免安装、免管理员）..." -ForegroundColor Yellow
    $rel   = Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest" -UseBasicParsing
    $asset = $rel.assets | Where-Object { $_.name -like "MinGit-*-64-bit.zip" } | Select-Object -First 1
    if (-not $asset) { throw "未能在 git-for-windows 最新发布里找到 MinGit 安装包。" }
    $zip = Join-Path $env:TEMP "mingit.zip"
    Write-Host "下载: $($asset.name)" -ForegroundColor Yellow
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip -UseBasicParsing
    $gitDir = Join-Path $env:LOCALAPPDATA "PicturebookGit"
    if (Test-Path $gitDir) { Remove-Item $gitDir -Recurse -Force }
    Expand-Archive $zip $gitDir -Force
    $git = Join-Path $gitDir "cmd\git.exe"
    Write-Host "便携版 Git 就位: $git" -ForegroundColor Green
}
& $git --version

# ---------- 2) 把部署目录原地变成 git 仓库 ----------
if (-not (Test-Path $Dst)) { New-Item -ItemType Directory -Path $Dst | Out-Null }
Set-Location $Dst
if (-not (Test-Path (Join-Path $Dst ".git"))) {
    Write-Host "初始化 git 仓库并关联远程 ..." -ForegroundColor Yellow
    & $git init -q
    & $git remote add origin $Repo
} else {
    & $git remote set-url origin $Repo
}
& $git config core.autocrlf false
Write-Host "拉取最新代码（首次拉全量，之后增量秒级）..." -ForegroundColor Yellow
& $git fetch origin $Branch
& $git reset --hard "origin/$Branch"
Write-Host "代码已同步到最新（.venv/.env/outputs 已保留）。" -ForegroundColor Green

# ---------- 3) 补装依赖 ----------
$venvPy = Join-Path $Dst ".venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    Write-Host "检查并安装依赖 ..." -ForegroundColor Yellow
    & $venvPy -m pip install -r requirements.txt -q
    Write-Host "依赖就绪。" -ForegroundColor Green
} else {
    Write-Host "警告：未找到 .venv，请先用 启动网站.bat 初始化一次环境再重跑本脚本。" -ForegroundColor Red
}

# ---------- 4) 注册每 2 分钟自动更新的计划任务 ----------
$ps1 = Join-Path $Dst "scripts\vm_auto_update.ps1"
$tr  = "powershell -NoProfile -ExecutionPolicy Bypass -File `"$ps1`""
schtasks /Create /TN "PicturebookAutoUpdate" /TR $tr /SC MINUTE /MO 2 /F | Out-Null
Write-Host "已注册计划任务 PicturebookAutoUpdate（每 2 分钟检查一次更新）。" -ForegroundColor Green

# ---------- 5) 立即重启一次网站 ----------
Get-CimInstance Win32_Process -Filter "name='python.exe'" |
    Where-Object { $_.CommandLine -like '*streamlit*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep 2
if (Test-Path $venvPy) {
    Start-Process $venvPy -ArgumentList '-m', 'streamlit', 'run', 'scripts\web_app.py', `
        '--server.address', '0.0.0.0', '--server.port', '8501', '--server.headless', 'true' `
        -WorkingDirectory $Dst -WindowStyle Hidden
    Start-Sleep 8
    $up = [bool](Get-NetTCPConnection -LocalPort 8501 -State Listen -ErrorAction SilentlyContinue)
    if ($up) {
        Write-Host "网站运行状态: 已启动 ✔" -ForegroundColor Green
    } else {
        Write-Host "网站运行状态: 未检测到监听，请查看 $Dst\auto_update.log" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " 配置完成！以后流程：本地双击「发布更新.bat」" -ForegroundColor Cyan
Write-Host " -> 约 2 分钟后本服务器自动拉取并重启，无需再手动操作。" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
