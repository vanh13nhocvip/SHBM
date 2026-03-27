@echo off
REM SHBM - Unified Setup Wrapper
REM This script initializes the Python environment and installs dependencies
REM Usage: .\tools\setup.bat [/install]

setlocal enabledelayedexpansion
cd /d "%~dp0.."
set PROJECT_DIR=%CD%
set VENV_DIR=%PROJECT_DIR%\venv
set VENV_PY=%VENV_DIR%\Scripts\python.exe
set PIP=%VENV_DIR%\Scripts\pip.exe

echo === SHBM Environment Setup ===
echo Project root: %PROJECT_DIR%

REM Check if venv exists
if exist "%VENV_PY%" (
    echo ✓ Virtual environment found at %VENV_DIR%
) else (
    echo ✗ Virtual environment not found
    echo To create it, run: python -m venv "%VENV_DIR%"
    exit /b 1
)

REM If /install flag is given, install dependencies
if "%1"=="/install" (
    echo.
    echo Installing Python dependencies from requirements.txt...
    "%VENV_PY%" -m pip install --upgrade pip setuptools wheel
    "%VENV_PY%" -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo Warning: Some packages may have failed to install
    ) else (
        echo ✓ Installation complete
    )
)

echo.
echo Setup complete. Next steps:
echo.
echo 1) To activate the virtual environment in PowerShell:
echo    ^& "!VENV_DIR!\Scripts\Activate.ps1"
echo.
echo 2) To run the GUI:
echo    .\Run.bat
echo.
echo 3) To use CLI metadata extraction:
echo    ^$env:PYTHONPATH = ^"^$PWD^"
echo    .\venv\Scripts\python.exe -m src.cli_metadata --input "path\to\pdfs" --output out.xlsx --format excel --recursive
echo.
echo 4) For Poppler/Tesseract setup, see:
echo    .\tools\INSTALL_TESSERACT.md
echo    .\tools\download_and_install_poppler.ps1
echo.
pause
















pauseecho Setup wrapper finished.)    echo tools\clean_and_rebuild.bat not found; skipping.) else (    call "%PROJECT_DIR%\tools\clean_and_rebuild.bat"    echo Calling tools\clean_and_rebuild.bat...echo 2) Run tools\clean_and_rebuild.bat if present (will upgrade pip and install editable package)
if exist "%PROJECT_DIR%\tools\clean_and_rebuild.bat" ()    echo install_env.bat not found; skipping.) else (    call "%PROJECT_DIR%\install_env.bat"    echo Calling install_env.bat...if exist "%PROJECT_DIR%\install_env.bat" (