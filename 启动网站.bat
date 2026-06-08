@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动绘本自动化网站，请稍候...
echo （首次运行会自动装 Python 和依赖，可能需要几分钟）
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy_server.ps1"
echo.
echo 网站已停止。按任意键关闭本窗口。
pause >nul
