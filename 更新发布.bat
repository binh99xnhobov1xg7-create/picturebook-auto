@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  一键更新发布：重建课程级别介绍全部物料（Excel / 一页纸 / 长图）
echo  跑完后，同事网址下次刷新即为最新（无需重启网站）。
echo ============================================================
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" scripts\rebuild_curriculum.py
) else (
  echo 未找到 .venv 虚拟环境，请先用“启动网站.bat”跑一次完成环境初始化。
)
echo.
pause
