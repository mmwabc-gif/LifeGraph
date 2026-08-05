@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if not errorlevel 1 set "PYTHON_CMD=python"

if not defined PYTHON_CMD (
  py -3.10 -c "import sys" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3.10"
)

if not defined PYTHON_CMD (
  py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
  if not errorlevel 1 set "PYTHON_CMD=py -3"
)

if not defined PYTHON_CMD (
  echo.
  echo [LifeGraph] 未找到 Python 3.10 或更高版本。
  echo 请先安装 Python，并在安装时勾选 Add Python to PATH。
  echo 安装完成后重新打开本脚本。
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [LifeGraph] 正在使用 %PYTHON_CMD% 创建 Python 虚拟环境...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 goto :error
)

echo [LifeGraph] 正在安装/检查依赖...
".venv\Scripts\python.exe" -m pip install -U pip >nul
if errorlevel 1 goto :error

".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto :error

echo [LifeGraph] 启动地址：http://127.0.0.1:8765
".venv\Scripts\python.exe" scripts\run_dev.py
exit /b 0

:error
echo.
echo [LifeGraph] 启动失败。
echo 请在命令提示符中运行 python --version，确认 Python 版本为 3.10 或更高。
pause
exit /b 1
