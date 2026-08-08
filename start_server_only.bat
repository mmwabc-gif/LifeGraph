@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
title LifeGraph FastAPI Server

rem 可通过环境变量覆盖，默认与 scripts\run_dev.py 保持一致
if not defined LIFEGRAPH_HOST set "LIFEGRAPH_HOST=127.0.0.1"
if not defined LIFEGRAPH_PORT set "LIFEGRAPH_PORT=8765"

if not exist ".venv\Scripts\python.exe" (
  echo 未找到 .venv\Scripts\python.exe
  echo 请先运行 start.bat 创建虚拟环境。
  pause
  exit /b 1
)

echo ========================================
echo LifeGraph FastAPI 自动重启
echo ========================================
echo.
echo 正在检查端口 %LIFEGRAPH_PORT% 上的旧服务...

powershell -NoProfile -ExecutionPolicy Bypass -Command "$port=[int]$env:LIFEGRAPH_PORT; $connections=@(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue); $pids=@($connections | Select-Object -ExpandProperty OwningProcess -Unique); if($pids.Count -eq 0){Write-Host '未检测到正在运行的旧服务。'; exit 0}; foreach($processId in $pids){Write-Host ('正在停止旧服务，PID: ' + $processId); & taskkill.exe /PID $processId /T /F 2>$null | Out-Null}; for($i=0; $i -lt 30; $i++){if(-not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)){break}; Start-Sleep -Milliseconds 100}; if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){Write-Error ('端口 ' + $port + ' 仍被占用，无法重新启动。'); exit 1}; Write-Host '旧服务已停止。'"

if errorlevel 1 (
  echo.
  echo 无法释放端口 %LIFEGRAPH_PORT%，请检查是否有其他程序占用该端口。
  pause
  exit /b 1
)

echo.
echo Python:
".venv\Scripts\python.exe" --version
if errorlevel 1 (
  echo Python 启动失败。
  pause
  exit /b 1
)

echo.
echo 正在启动 FastAPI...
echo 地址：http://%LIFEGRAPH_HOST%:%LIFEGRAPH_PORT%
echo API 文档：http://%LIFEGRAPH_HOST%:%LIFEGRAPH_PORT%/api/docs
echo.
echo 提示：以后重新运行本文件，会先停止旧服务，再自动启动新服务。
echo ========================================
echo.

".venv\Scripts\python.exe" scripts\run_dev.py
set "SERVER_EXIT_CODE=%ERRORLEVEL%"

echo.
echo FastAPI 已停止，退出代码：%SERVER_EXIT_CODE%
echo 当前窗口将在 2 秒后关闭。
timeout /t 2 /nobreak >nul
exit /b %SERVER_EXIT_CODE%
