"""
Security Layer - Installer
Sets up USB monitoring system on target machine
"""

import subprocess
import sys
import winreg
from datetime import datetime
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()
LOG_FILE = SCRIPT_DIR.parent / "history.log"
ORG_ID_FILE = SCRIPT_DIR / "A_org_id.csv"
A_RUN_SCRIPT = SCRIPT_DIR / "B_run.py"
TASK_NAME = "SecurityLayer_USB_Monitor"
AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "SecurityLayerAgent"


def log_message(message, level="INFO"):
    """Write timestamped message to log file and console"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] [INSTALL] {message}"
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry + '\n')
    except Exception:
        pass
    print(log_entry)


def check_python_version():
    """Check if Python version is >= 3.6"""
    if sys.version_info >= (3, 6):
        return True
    log_message(f"Python {sys.version_info.major}.{sys.version_info.minor} - TOO OLD (need 3.6+)", "ERROR")
    return False


def ensure_package(name, min_version):
    """Check if package exists, install if missing"""
    try:
        __import__(name)
        return True
    except ImportError:
        log_message(f"{name} package - NOT FOUND, installing...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", f"{name}>={min_version}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE
            )
            log_message(f"{name} package installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            log_message(f"Failed to install {name}: {e}", "ERROR")
            return False


def check_org_id_file():
    """Check if A_org_id.csv exists"""
    if ORG_ID_FILE.exists():
        return True
    log_message(f"{ORG_ID_FILE.name} - MISSING", "ERROR")
    return False


def register_autostart():
    """Register autostart via Windows Registry (no admin required)"""
    # Check if already exists
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, AUTOSTART_NAME)
        winreg.CloseKey(key)
        log_message(f"Registry autostart already exists: {AUTOSTART_NAME} - OK")
        return True
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # Create new entry
    pythonw = SCRIPT_DIR / "python" / "pythonw.exe"
    command = f'"{pythonw}" "{A_RUN_SCRIPT}"'

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)
        log_message(f"Registry autostart created: {AUTOSTART_NAME}")
        return True
    except Exception as e:
        log_message(f"Failed to register autostart: {e}", "ERROR")
        return False


def cleanup_old_task_scheduler():
    """Remove old Task Scheduler task if exists (migration cleanup)"""
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True
    )
    if result.returncode == 0:
        log_message(f"Removed old Task Scheduler task: {TASK_NAME}")


def run_agent():
    """Start the USB monitoring agent"""
    try:
        result = subprocess.run(
            [sys.executable, str(A_RUN_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            return True
        log_message(f"Agent failed to start (code {result.returncode})", "ERROR")
        if result.stderr:
            log_message(f"Error output: {result.stderr}", "ERROR")
        return False
    except subprocess.TimeoutExpired:
        # Timeout means agent is running in background - this is OK
        return True
    except Exception as e:
        log_message(f"Failed to start agent: {e}", "ERROR")
        return False


def main():
    """Main installation flow"""
    # Step 1: Check Python version
    if not check_python_version():
        print("\n[ERROR] Python 3.6 or newer is required!")
        return 1

    # Step 2: Check/Install required packages
    if not ensure_package("wmi", "1.5.1"):
        log_message("Installation aborted - WMI install failed", "ERROR")
        return 1

    if not ensure_package("psutil", "5.9.0"):
        log_message("Installation aborted - psutil install failed", "ERROR")
        return 1

    # Step 3: Check org ID file
    if not check_org_id_file():
        log_message("Installation aborted - A_org_id.csv missing", "ERROR")
        return 1

    # Step 4: Register autostart (Registry)
    if register_autostart():
        cleanup_old_task_scheduler()
    else:
        log_message("WARNING: Registry autostart failed - manual start required", "WARNING")

    # Step 5: Start agent
    if not run_agent():
        log_message("Installation failed - agent did not start", "ERROR")
        return 1

    log_message("Installation completed successfully")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main() or 0)
    except KeyboardInterrupt:
        log_message("Installation cancelled by user", "WARNING")
        print("\n[CANCELLED] Installation interrupted")
        sys.exit(130)
    except Exception as e:
        log_message(f"Unexpected error: {e}", "ERROR")
        import traceback
        log_message(traceback.format_exc(), "ERROR")
        print(f"\n[ERROR] {e}")
        sys.exit(1)
