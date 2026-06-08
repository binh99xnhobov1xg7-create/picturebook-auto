@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 本操作会把网站注册为“开机自动启动”（需要管理员权限）。
echo.
:: 以管理员重新运行自身
net session >nul 2>&1
if %errorlevel% neq 0 (
  echo 正在请求管理员权限...
  powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
  exit /b
)

set "TASKNAME=PicturebookWeb"
set "PS1=%~dp0deploy_server.ps1"

schtasks /Create /TN "%TASKNAME%" /TR "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"%PS1%\"" /SC ONSTART /RU SYSTEM /RL HIGHEST /F
if %errorlevel%==0 (
  echo.
  echo 已设置开机自启（任务名：%TASKNAME%）。
  echo 现在立即启动一次...
  schtasks /Run /TN "%TASKNAME%"
  echo 完成。网站将在后台运行，重启服务器后也会自动启动。
) else (
  echo 设置失败，请确认以管理员身份运行。
)
echo.
pause
