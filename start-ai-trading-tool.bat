@echo off
setlocal

set DISTRO=Ubuntu
set PROJECT=/home/ywh/projects/ai-trading-assistant
set DOCKER_DESKTOP=C:\Program Files\Docker\Docker\Docker Desktop.exe

where wsl.exe >nul 2>nul
if errorlevel 1 goto fail_wsl

call :ensure_docker
if errorlevel 1 goto fail_docker

echo [1/3] Starting Journedge...
wsl.exe -d %DISTRO% -e bash -lc "cd %PROJECT% && ./scripts/start-journedge.sh"
if errorlevel 1 goto fail

echo [2/3] Starting paper trading service...
wsl.exe -d %DISTRO% -e bash -lc "cd %PROJECT% && ./scripts/start-open-paper-trading.sh"
if errorlevel 1 goto fail

echo [3/3] Starting shell UI...
wsl.exe -d %DISTRO% -e bash -lc "cd %PROJECT% && ./scripts/collect-all-snapshots.sh && ./scripts/start-app-shell.sh"
if errorlevel 1 goto fail

start "" http://127.0.0.1:8090/
exit /b 0

:ensure_docker
docker version >nul 2>nul
if not errorlevel 1 exit /b 0

if exist "%DOCKER_DESKTOP%" (
  echo Docker Desktop is not running. Starting it now...
  start "Docker Desktop" "%DOCKER_DESKTOP%"
) else (
  echo Docker Desktop executable not found: %DOCKER_DESKTOP%
  exit /b 1
)

for /L %%i in (1,1,45) do (
  timeout /t 2 >nul
  docker version >nul 2>nul
  if not errorlevel 1 (
    echo Docker is ready.
    exit /b 0
  )
)

echo Docker did not become ready in time.
exit /b 1

:fail_wsl
echo WSL not found. Please install WSL and Ubuntu first.
pause
exit /b 1

:fail_docker
echo Docker Desktop is required for the paper trading service.
pause
exit /b 1

:fail
echo Startup failed. Check the output above.
pause
exit /b 1
