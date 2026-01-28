"""
Security Layer - Uninstaller
Removes USB monitoring system from target machine
(Logical cleanup only - file deletion handled by stop.bat)
"""

import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# =========================
# CONFIGURATION
# =========================

SCRIPT_DIR = Path(__file__).parent.absolute()
PID_FILE = SCRIPT_DIR / "watcher.pid"

AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "SecurityLayerAgent"
TASK_NAME = "SecurityLayer_USB_Monitor"

# =========================
# LOGGING
# =========================

def log_message(message, level="INFO"):
    """Print timestamped message to console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

# =========================
# PROCESS MANAGEMENT
# =========================

def kill_all_securitylayer_processes():
    """Kill ALL running SecurityLayer Python processes (except ourselves)"""
    killed_count = 0
    my_pid = os.getpid()

    try:
        import psutil # type: ignore
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                # Skip ourselves
                if proc.pid == my_pid:
                    continue

                cmdline = proc.info.get('cmdline') or []
                cmdline_str = ' '.join(cmdline)

                # Kill any Python process from SecurityLayer folder
                if 'SecurityLayer' in cmdline_str and proc.name() in ('python.exe', 'pythonw.exe'):
                    log_message(f"Killing process PID {proc.pid}")
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    killed_count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    except ImportError:
        log_message("psutil not available for process scan", "WARNING")

    if killed_count > 0:
        log_message(f"Killed {killed_count} SecurityLayer process")
    else:
        log_message("No SecurityLayer processes found")

    return killed_count


def stop_watcher_process():
    """Stop all background USB watcher processes"""

    # First: kill ALL watchers by cmdline (handles multiple instances)
    kill_all_securitylayer_processes()

    # Then: clean up PID file if exists
    if PID_FILE.exists():
        try:
            PID_FILE.unlink()
        except Exception as e:
            log_message(f"Failed to remove PID file: {e}", "WARNING")

    return True


# =========================
# REGISTRY AUTOSTART
# =========================

def remove_autostart():
    """Remove autostart entry from Windows Registry"""
    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTOSTART_KEY,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.DeleteValue(key, AUTOSTART_NAME)
        winreg.CloseKey(key)
        return True

    except FileNotFoundError:
        return True
    except Exception as e:
        log_message(f"Error removing autostart: {e}", "ERROR")
        return False


# =========================
# TASK SCHEDULER
# =========================

def remove_startup_task():
    """Remove Task Scheduler task"""
    try:
        subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True,
            check=False
        )
        return True
    except Exception as e:
        log_message(f"Error removing Task Scheduler task: {e}", "WARNING")
        return False





# =========================
# MAIN
# =========================

def main():
    stop_watcher_process()
    remove_autostart()
    remove_startup_task()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log_message("Uninstallation cancelled by user", "WARNING")
        sys.exit(130)
    except Exception as e:
        log_message(f"Unexpected error: {e}", "ERROR")
        import traceback
        log_message(traceback.format_exc(), "ERROR")
        sys.exit(1)
