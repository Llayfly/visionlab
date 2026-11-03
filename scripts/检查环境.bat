@echo off
chcp 65001 >nul
cd /d "%~dp0.."
py -3 --version
if errorlevel 1 echo 未检测到 Python，请安装 Python 3.10 或 3.11。
pause
