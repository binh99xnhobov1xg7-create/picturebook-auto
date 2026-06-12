<#
  run_batch_awake.ps1 — 让批量出书在后台长跑、绝不因「电脑睡眠/黑屏」中断。

  原理：
    - 调用 Windows 内核 SetThreadExecutionState，告诉系统「我有任务在跑，别睡」。
    - 只设 ES_SYSTEM_REQUIRED（系统不睡眠）；不设 ES_DISPLAY_REQUIRED，
      所以【显示器可以照常黑屏省电】，但 CPU/进程继续跑——这正是你要的。
    - 脚本退出（正常结束 / Ctrl+C / 报错）时自动 ES_CONTINUOUS 复位，把睡眠策略还给系统。
    - 全程 stdout/stderr 同时写到 logs\batch_<时间>.log，关掉 Cursor 也能回看进度。

  用法（在仓库根目录 C:\Users\Jered\picturebook-auto 下）：
    powershell -ExecutionPolicy Bypass -File scripts\run_batch_awake.ps1 -Level 3 -Numbers "3,6,9,12"
    powershell -ExecutionPolicy Bypass -File scripts\run_batch_awake.ps1 -Level 3 -Numbers "3,6" -Mock
    # 自定义并发：
    powershell -ExecutionPolicy Bypass -File scripts\run_batch_awake.ps1 -Level 3 -Numbers "3,6,9,12" -BookConcurrency 2 -ImageConcurrency 4
#>
param(
    [Parameter(Mandatory = $true)][string]$Level,
    [Parameter(Mandatory = $true)][string]$Numbers,
    [int]$BookConcurrency = 2,
    [int]$ImageConcurrency = 4,
    [switch]$Mock
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

# 日志目录与文件
$LogDir = Join-Path $RepoRoot "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "batch_L${Level}_${Stamp}.log"

# ---- 注册 SetThreadExecutionState ----
Add-Type -Namespace Win32 -Name PowerState -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("kernel32.dll", SetLastError = true)]
public static extern uint SetThreadExecutionState(uint esFlags);
'@

$ES_CONTINUOUS       = [uint32]2147483648  # 0x80000000：持续生效，直到下次调用
$ES_SYSTEM_REQUIRED  = [uint32]1           # 0x00000001：系统保持唤醒（不睡眠）
# 注意：故意不加 ES_DISPLAY_REQUIRED(0x2)，让显示器可正常黑屏省电，进程照常跑。

function Enable-StayAwake {
    [void][Win32.PowerState]::SetThreadExecutionState($ES_CONTINUOUS -bor $ES_SYSTEM_REQUIRED)
}
function Disable-StayAwake {
    [void][Win32.PowerState]::SetThreadExecutionState($ES_CONTINUOUS)
}

Write-Host "============================================================"
Write-Host " 防睡眠批量出书   Level=$Level   Numbers=$Numbers"
Write-Host " 并发: 本=$BookConcurrency  出图=$ImageConcurrency   Mock=$($Mock.IsPresent)"
Write-Host " 日志: $LogFile"
Write-Host " 显示器可黑屏省电；系统不会睡眠，进程持续运行。"
Write-Host " 想中止：在本窗口按 Ctrl+C（会自动恢复睡眠策略）。"
Write-Host "============================================================"

# 组装 python 命令参数
$pyArgs = @(
    "scripts\run_syllabus_batch.py",
    "--level", $Level,
    "--numbers", $Numbers,
    "--book-concurrency", $BookConcurrency,
    "--image-concurrency", $ImageConcurrency
)
if ($Mock) { $pyArgs += "--mock" }

try {
    Enable-StayAwake
    # 用 py 启动器（项目约定）；stdout+stderr 实时 Tee 到日志，既显示又落盘。
    & py $pyArgs 2>&1 | Tee-Object -FilePath $LogFile
    $code = $LASTEXITCODE
    Write-Host "============================================================"
    Write-Host " 批量结束，python 退出码 = $code"
    Write-Host " 完整日志: $LogFile"
    Write-Host "============================================================"
    exit $code
}
finally {
    # 无论正常/异常/Ctrl+C，都恢复系统睡眠策略，绝不把电脑永久顶醒。
    Disable-StayAwake
    Write-Host "[stay-awake] 已恢复系统默认睡眠策略。"
}
