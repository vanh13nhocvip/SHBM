@echo off
setlocal enabledelayedexpansion

REM Silently clean up __pycache__
del /s /q "%~dp0\src\__pycache__\*" >nul 2>&1
rmdir /s /q "%~dp0\src\__pycache__" >nul 2>&1

set "PROJECT_DIR=%~dp0"
cd /d "%PROJECT_DIR%"

set "PYTHONPATH=%PROJECT_DIR%"
set PYTHONUTF8=1

REM Detect pythonw (silent executable)
if exist "%PROJECT_DIR%venv\Scripts\pythonw.exe" (
    set "PW=%PROJECT_DIR%venv\Scripts\pythonw.exe"
) else (
    set "PW=pythonw.exe"
)

REM Launch GUI silently
start "" "%PW%" -m src.pdf_metadata_gui
exit