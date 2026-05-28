@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    start "Claude History Viewer" cmd /k "py run.py"
) else (
    start "Claude History Viewer" cmd /k "python run.py"
)
