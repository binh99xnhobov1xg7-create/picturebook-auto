# ============================================================
#  绘本网站 · 服务器自动更新（由计划任务每 2 分钟调用一次）
#  逻辑：git fetch -> 有新提交才 git reset --hard + 重启网站。
#  无更新时几乎零开销、秒级返回。日志写入项目根目录 auto_update.log。
# ============================================================
$ErrorActionPreference = "Stop"
$ROOT = Split-Path $PSScriptRoot -Parent
Set-Location $ROOT

$log = Join-Path $ROOT "auto_update.log"
function Log($m) { "$(Get-Date -Format 'MM-dd HH:mm:ss')  $m" | Out-File -FilePath $log -Append -Encoding utf8 }

# 找 git：便携版优先，其次系统 PATH
$git = "git"
$portable = Join-Path $env:LOCALAPPDATA "PicturebookGit\cmd\git.exe"
if (Test-Path $portable) { $git = $portable }

try {
    & $git fetch origin master --quiet
    $local  = (& $git rev-parse HEAD).Trim()
    $remote = (& $git rev-parse origin/master).Trim()
    if ($local -eq $remote) { exit 0 }   # 没有新版本，直接退出

    Log "发现新版本 $($remote.Substring(0,7))，开始更新 ..."
    $reqBefore = (Get-FileHash requirements.txt -ErrorAction SilentlyContinue).Hash
    & $git reset --hard origin/master --quiet
    $reqAfter  = (Get-FileHash requirements.txt -ErrorAction SilentlyContinue).Hash

    $venvPy = Join-Path $ROOT ".venv\Scripts\python.exe"

    # 依赖文件变了才重装，省时间
    if ($reqBefore -ne $reqAfter -and (Test-Path $venvPy)) {
        Log "requirements.txt 有变化，安装依赖 ..."
        & $venvPy -m pip install -r requirements.txt -q
    }

    # 重启网站，确保跑的是最新代码
    Get-CimInstance Win32_Process -Filter "name='python.exe'" |
        Where-Object { $_.CommandLine -like '*streamlit*' } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep 2
    if (Test-Path $venvPy) {
        Start-Process $venvPy -ArgumentList '-m', 'streamlit', 'run', 'scripts\web_app.py', `
            '--server.address', '0.0.0.0', '--server.port', '8501', '--server.headless', 'true' `
            -WorkingDirectory $ROOT -WindowStyle Hidden
    }
    Log "更新完成并已重启网站 -> $($remote.Substring(0,7))"
}
catch {
    Log "更新出错: $_"
}
