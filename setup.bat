@echo off
REM ============================================
REM  OpenVINO Windows LLM - First-Time Setup
REM ============================================
REM Creates a Python venv, installs OpenVINO GenAI + server deps, and (optionally)
REM the model-conversion deps. Runs the PowerShell setup with execution-policy
REM bypass so no manual policy change is needed.
REM
REM   .\setup.bat                 Install runtime deps only
REM   .\setup.bat -WithConvert    Also install model-conversion deps
REM   .\setup.bat -SkipHardwareCheck

echo ==========================================
echo   OpenVINO Windows LLM - Setup
echo ==========================================
echo.

"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup\setup_all.ps1" %*

if errorlevel 1 (
    echo.
    echo Setup did not complete successfully.
    echo Review the messages above, fix any errors, then run setup.bat again.
    pause
    exit /b 1
)

pause
