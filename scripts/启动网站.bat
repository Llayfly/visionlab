@echo off
chcp 65001 >nul
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [1/2] 创建 Python 虚拟环境...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo 创建环境失败，请先安装 Python 3.10 或 3.11，并勾选 Add Python to PATH。
    pause
    exit /b 1
  )
)
echo [2/2] 启动 VISIONLAB...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo 依赖安装失败，请检查网络或 Python 版本。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
