@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "%LOCALAPPDATA%\Microsoft\WindowsApps\pwsh.exe" -NoExit -Command "py run.py"
