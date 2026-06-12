<#
  keep_awake.ps1 — 通用「防睡眠」长跑包装器：运行任意 python 脚本，
  期间系统绝不睡眠（显示器可正常黑屏省电），结束/报错/Ctrl+C 自动恢复睡眠策略。

  原理同 run_batch_awake.ps1：SetThreadExecutionState 只设 ES_SYSTEM_REQUIRED
  （系统不睡眠），不设 ES_DISPLAY_REQUIRED（显示器照常黑屏省电，进程继续跑）。
  全程输出同时写到 logs\<标签>_<时间>.log，关掉 Cursor 也能回看。

  用法（仓库根目录）：
    powershell -ExecutionPolicy Bypass -File scripts\keep_awake.ps1 -PyFile scripts\_run_l4_ic_batch.py -Label L4_IC
    # 带参数透传：
    powershell -ExecutionPolicy Bypass -File scripts\keep_awake.ps1 -PyFile scripts\xxx.py -Label foo -PyArgs "--a","1"
#>
param(
    [Parameter(Mandatory = $true)][string]$PyFile,
    [string]$Label = "run",
    [string[]]$PyArgs = @()
)

$ErrorActionPreference = "Stop"

# 让控制台用 UTF-8 显示中文（否则实时输出会乱码；日志文件本就是 UTF-8）
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch { }

# 切到仓库根目录（脚本在 scripts\ 下，根目录是其父目录）
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "${Label}_${Stamp}.log"

Add-Type -Namespace Win32 -Name PowerState -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@

$ES_CONTINUOUS      = [uint32]2147483648  # 0x80000000
$ES_SYSTEM_REQUIRED = [uint32]1           # 0x00000001（系统保持唤醒；不锁显示器）

function Enable-StayAwake  { [void][Win32.PowerState]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED) }
function Disable-StayAwake { [void][Win32.PowerState]::SetThreadExecutionState($ES_CONTINUOUS) }

Write-Host "============================================================"
Write-Host " 防睡眠长跑  PyFile=$PyFile  Label=$Label"
Write-Host " 日志: $LogFile"
Write-Host " 显示器可黑屏省电；系统不会睡眠，进程持续运行。Ctrl+C 中止（会自动恢复睡眠策略）。"
Write-Host "============================================================"

$allArgs = @($PyFile) + $PyArgs

try {
    Enable-StayAwake
    & py $allArgs 2>&1 | Tee-Object -FilePath $LogFile
    $code = $LASTEXITCODE
    Write-Host "============================================================"
    Write-Host " 结束，python 退出码 = $code   日志: $LogFile"
    Write-Host "============================================================"
    exit $code
}
finally {
    Disable-StayAwake
    Write-Host "[stay-awake] 已恢复系统默认睡眠策略。"
}
