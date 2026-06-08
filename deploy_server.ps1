# ============================================================
#  绘本自动化 · 一键部署脚本（Windows 服务器）
#  用法：在服务器上把整个项目文件夹拷好后，右键“启动网站.bat”即可（它会调用本脚本）。
#  本脚本做：找/装 Python → 建虚拟环境 → 装依赖 → 开防火墙 8501 → 启动 Streamlit 网站。
# ============================================================
$ErrorActionPreference = "Stop"
$PORT = 8501

# 切到脚本所在目录（= 项目根目录）
Set-Location -Path $PSScriptRoot
Write-Host "=== 项目目录: $PSScriptRoot ===" -ForegroundColor Cyan

# ---------- 1) 找 Python，没有就自动下载安装 ----------
function Find-Python {
    foreach ($c in @("py -3", "python")) {
        try {
            $v = & cmd /c "$c --version" 2>$null
            if ($LASTEXITCODE -eq 0 -and $v -match "Python 3") { return $c }
        } catch {}
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    Write-Host "未发现 Python，正在下载并静默安装 Python 3.12 ..." -ForegroundColor Yellow
    $installer = Join-Path $env:TEMP "python-3.12.8-amd64.exe"
    $url = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-amd64.exe"
    Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
    Start-Process -FilePath $installer -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1" -Wait
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    $py = Find-Python
    if (-not $py) { Write-Host "Python 安装后仍未找到，请手动安装后重试。" -ForegroundColor Red; Read-Host "按回车退出"; exit 1 }
}
Write-Host "使用 Python: $py" -ForegroundColor Green

# ---------- 2) 建虚拟环境 ----------
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "创建虚拟环境 .venv ..." -ForegroundColor Yellow
    & cmd /c "$py -m venv .venv"
}
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# ---------- 3) 装依赖 ----------
Write-Host "安装依赖（首次较慢，请耐心等待）..." -ForegroundColor Yellow
& $venvPy -m pip install --upgrade pip -q
& $venvPy -m pip install -r requirements.txt -q
Write-Host "依赖安装完成。" -ForegroundColor Green

# ---------- 4) 检查 .env（API 密钥）----------
if (-not (Test-Path ".env")) {
    Write-Host "警告：未找到 .env（缺少 API 密钥），网站能开但生图/AI 功能不可用。" -ForegroundColor Red
    Write-Host "      请把本地的 .env 一并拷到本目录后重跑。" -ForegroundColor Red
} else {
    Write-Host ".env 已就位。" -ForegroundColor Green
}

# ---------- 5) 开防火墙 8501（需管理员；失败不致命）----------
try {
    netsh advfirewall firewall add rule name="Streamlit-$PORT" dir=in action=allow protocol=TCP localport=$PORT | Out-Null
    Write-Host "已开放防火墙端口 $PORT。" -ForegroundColor Green
} catch {
    Write-Host "未能自动开放防火墙端口（可能非管理员）。如同事访问不了，请管理员放行 TCP $PORT。" -ForegroundColor Yellow
}

# ---------- 6) 启动网站 ----------
$ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.*" } | Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " 网站即将启动。同事用浏览器访问：" -ForegroundColor Cyan
Write-Host "   http://$ip`:$PORT" -ForegroundColor Green
Write-Host "   （或 http://172.23.250.145:$PORT）" -ForegroundColor Green
Write-Host " 本窗口不要关闭——关了网站就停。要常驻请用“设为开机自启.bat”。" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

& $venvPy -m streamlit run scripts\web_app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
