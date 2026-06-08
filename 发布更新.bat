@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  一键发布：重建物料 + 提交 + 推送到 GitHub
echo  推送后约 2 分钟，同事服务器(172.23.250.145:8501)会自动更新。
echo ============================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo [X] 未找到 .venv 虚拟环境，请先用 "启动网站.bat" 初始化一次环境。
  pause
  exit /b 1
)

echo [1/4] 重建课程物料（Excel / 一页纸 / 长图）...
".venv\Scripts\python.exe" scripts\rebuild_curriculum.py
if errorlevel 1 (
  echo [X] 物料重建失败，已中止发布。请把上面的报错发我。
  pause
  exit /b 1
)
echo.

echo [2/4] 暂存所有改动 ...
git add -A
echo.

echo [3/4] 生成提交 ...
git commit -m "发布更新 %date% %time%"
echo （若提示 nothing to commit 表示没有新改动，可忽略，会继续推送。）
echo.

echo [4/4] 推送到 GitHub（master）...
git push origin master
if errorlevel 1 (
  echo [X] 推送失败：请检查网络，或是否已登录 GitHub（git 凭据）。
  pause
  exit /b 1
)
echo.

echo ============================================================
echo  [OK] 发布完成！约 2 分钟后同事服务器自动更新。
echo       网址：http://172.23.250.145:8501
echo       让同事按 Ctrl+F5 强制刷新即可看到最新。
echo ============================================================
echo.
pause
