@echo off
setlocal enabledelayedexpansion
REM ============================================
REM   OpenVINO Windows LLM - Server Launcher
REM ============================================
REM Activates the local venv and starts the server. All arguments are passed
REM straight through to the Python CLI.
REM
REM Usage:
REM   start_server.bat                              Auto-load OV_LLM_MODEL (or none)
REM   start_server.bat --model tinyllama-1.1b-chat-fp16 --device NPU
REM   start_server.bat --model qwen2.5-1.5b-fp16 --device NPU
REM   start_server.bat --list                       List catalog models and exit
REM   start_server.bat --check-devices              Show OpenVINO devices and exit
REM   start_server.bat --port 8001
REM   start_server.bat --mock                       Force the mock engine (no OpenVINO)

echo ========================================
echo   OpenVINO Windows LLM
echo ========================================
echo.

set "VENV=%~dp0.venv"
if not exist "%VENV%\Scripts\activate.bat" (
    echo ERROR: virtual environment not found at "%VENV%".
    echo Run setup first:
    echo   .\setup.bat
    pause
    exit /b 1
)

call "%VENV%\Scripts\activate.bat"

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

REM Ensure runtime deps are present (cheap import check on the marker file).
if not exist "%~dp0.deps_installed" (
    echo Installing runtime dependencies ^(first run only^)...
    python -m pip install -r "%~dp0requirements.txt"
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies.
        pause
        exit /b 1
    )
    echo. > "%~dp0.deps_installed"
)

cd /d "%~dp0"
python -m app.server %*

endlocal
