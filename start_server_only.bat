@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title LifeGraph FastAPI Manual Start

if not exist ".venv\Scripts\python.exe" (
  echo 未找到 .venv\Scripts\python.exe
  echo 请先运行 start.bat 创建虚拟环境。
  pause
  exit /b 1
)

echo Python:
".venv\Scripts\python.exe" --version
echo.
echo 正在直接启动 FastAPI...
echo 地址：http://127.0.0.1:8765
echo API 文档：http://127.0.0.1:8765/docs
echo.
".venv\Scripts\python.exe" scripts\run_dev.py

echo.
echo FastAPI 已停止，退出代码：%ERRORLEVEL%
pause
