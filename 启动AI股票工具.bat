@echo off
setlocal
chcp 65001 >nul

set DISTRO=Ubuntu
set PROJECT=/home/ywh/projects/ai-trading-assistant

where wsl.exe >nul 2>nul
if errorlevel 1 (
  echo 未找到 WSL，请先安装 WSL 和 Ubuntu。
  pause
  exit /b 1
)

echo [1/3] 启动 Journedge...
wsl.exe -d %DISTRO% -e bash -lc "cd %PROJECT% && ./scripts/start-journedge.sh"
if errorlevel 1 goto :fail

echo [2/3] 启动模拟盘服务...
wsl.exe -d %DISTRO% -e bash -lc "cd %PROJECT% && ./scripts/start-open-paper-trading.sh"
if errorlevel 1 goto :fail

echo [3/3] 启动整合壳...
wsl.exe -d %DISTRO% -e bash -lc "cd %PROJECT% && ./scripts/collect-all-snapshots.sh && ./scripts/start-app-shell.sh"
if errorlevel 1 goto :fail

echo 打开浏览器...
start http://localhost:8090/
exit /b 0

:fail
echo 启动失败，请检查 WSL 里的脚本输出。
pause
exit /b 1
