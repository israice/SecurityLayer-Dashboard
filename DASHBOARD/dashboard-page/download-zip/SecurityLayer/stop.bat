@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion

REM ============================================
REM Security Layer - Combined Stop & Uninstall
REM (stop.bat + uninstall.bat + AA_uninstaller.py)
REM Uses EXACTLY the same methods as originals
REM ============================================

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%usbSecurity\python\python.exe"
set "PID_FILE=%SCRIPT_DIR%usbSecurity\watcher.pid"
set "LOCK_FILE=%SCRIPT_DIR%usbSecurity\startup.lock"
set "WATCHER_LOCK=%SCRIPT_DIR%usbSecurity\watcher.lock"
set "BANNER_FILE=%SCRIPT_DIR%usbSecurity\banner.txt"

cd /d "%SCRIPT_DIR%"

if exist "%BANNER_FILE%" (
    type "%BANNER_FILE%"
    echo.
)

REM ============================================
REM PART 1: Kill ALL watcher processes
REM (handles multiple instances from race conditions)
REM ============================================

REM Kill ALL Python processes from SecurityLayer folder (watcher, B_run, C_run, etc.)
for /f "tokens=2 delims==" %%a in ('wmic process where "commandline like '%%SecurityLayer%%' and (name = 'python.exe' or name = 'pythonw.exe')" get processid /value 2^>nul ^| findstr /r "ProcessId="') do (
    taskkill /PID %%a /F >nul 2>&1
)

REM Remove PID file and lock file
if exist "%PID_FILE%" (
    del "%PID_FILE%" >nul 2>&1
)
if exist "%LOCK_FILE%" (
    del "%LOCK_FILE%" >nul 2>&1
)
if exist "%WATCHER_LOCK%" (
    del "%WATCHER_LOCK%" >nul 2>&1
)

REM ============================================
REM PART 2: Remove autostart entries
REM ============================================

set "AUTOSTART_KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
set "AUTOSTART_NAME=SecurityLayerAgent"
set "TASK_NAME=SecurityLayer_USB_Monitor"

REG DELETE "%AUTOSTART_KEY%" /v "%AUTOSTART_NAME%" /f >nul 2>&1

schtasks /Delete /TN "%TASK_NAME%" /F >nul 2>&1

REM ============================================
REM PART 3: Run Python uninstaller for cleanup
REM ============================================

if not exist "%PYTHON_EXE%" (
    echo [WARNING] python.exe not found, skipping Python cleanup
    pause
    exit /b 0
)

REM Run AA_uninstaller.py for logical cleanup (processes, registry, scheduled tasks)
"%PYTHON_EXE%" "%SCRIPT_DIR%usbSecurity\AA_uninstaller.py"

REM Wait for python.exe to fully release files
timeout /t 2 /nobreak >nul

echo.
echo Security Layer was stopped and successfully removed.

REM Remove trailing backslash from SCRIPT_DIR for rd command
set "FOLDER_TO_DELETE=%SCRIPT_DIR:~0,-1%"

REM Change to parent directory so we can delete SecurityLayer folder
cd /d "%SCRIPT_DIR%.."

REM Delete folder in background using PowerShell (no window, 3 second delay)
start /b "" powershell -WindowStyle Hidden -Command "Start-Sleep 3; Remove-Item '%FOLDER_TO_DELETE%' -Recurse -Force -EA SilentlyContinue"

echo Press any key to exit...
pause >nul
exit /b 0
