@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%usbSecurity\python\python.exe"
set "BANNER_FILE=%SCRIPT_DIR%usbSecurity\banner.txt"

cd /d "%SCRIPT_DIR%"

if exist "%BANNER_FILE%" (
    type "%BANNER_FILE%"
    echo.
)

REM ============================================
REM Check Python exists
REM ============================================

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Portable Python not found!
    echo Expected: python\python.exe
    pause
    exit /b 1
)

REM ============================================
REM Run installer (handles everything)
REM - Checks dependencies
REM - Registers autostart (Registry + Task Scheduler)
REM - Starts agent
REM ============================================

"%PYTHON_EXE%" "%SCRIPT_DIR%usbSecurity\AA_installer.py"
if !errorlevel! neq 0 (
    echo [ERROR] Installation/startup failed!
    pause
    exit /b 1
)

echo.
echo [OK] Security Layer for USB Ports started successfully.
pause
exit /b 0
