"""
Security Layer - Installer
Sets up USB monitoring system on target machine
"""

import subprocess
import sys
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
LOG_FILE = SCRIPT_DIR.parent / "history.log"
ORG_ID_FILE = SCRIPT_DIR / "A_org_id.csv"
USBTREEVIEW_EXE = SCRIPT_DIR / "CBA_UsbTreeView.exe"
A_RUN_SCRIPT = SCRIPT_DIR / "B_run.py"
TASK_NAME = "SecurityLayer_USB_Monitor"

# =========================
# LOGGING
# =========================

def log_message(message, level="INFO"):
    """Write timestamped message to log file"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] [INSTALL] {message}"

    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[ERROR] Failed to write to log: {e}")

    print(log_entry.strip())


def confirm(prompt, default_yes=True):
    """Ask user for Y/n confirmation"""
    hint = "Y/n" if default_yes else "y/N"
    choice = input(f"{prompt} ({hint}): ").strip().lower()
    return choice != 'n' if default_yes else choice == 'y'


# =========================
# VALIDATION
# =========================

def check_python_version():
    """Check if Python version is >= 3.6"""

    version = sys.version_info
    if version.major >= 3 and version.minor >= 6:
        return True
    else:
        log_message(f"Python {version.major}.{version.minor} - TOO OLD (need 3.6+)", "ERROR")
        return False


def check_wmi_package():
    """Check if WMI package is installed"""

    try:
        import wmi
        return True
    except ImportError:
        log_message("WMI package - NOT FOUND", "WARNING")
        return False


def install_wmi_package():
    """Install WMI package via pip"""
    log_message("Installing WMI package...")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "WMI>=1.5.1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        log_message("WMI package installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        log_message(f"Failed to install WMI: {e}", "ERROR")
        return False


def check_psutil_package():
    """Check if psutil package is installed"""

    try:
        import psutil # type: ignore
        return True
    except ImportError:
        log_message("psutil package - NOT FOUND", "WARNING")
        return False


def install_psutil_package():
    """Install psutil package via pip"""
    log_message("Installing psutil package...")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "psutil>=5.9.0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )
        return True
    except subprocess.CalledProcessError as e:
        log_message(f"Failed to install psutil: {e}", "ERROR")
        return False


# =========================
# CONFIGURATION SETUP
# =========================

def check_org_id_file():
    """Check if A_org_id.csv exists"""
    if ORG_ID_FILE.exists():
        return True
    else:
        log_message(f"{ORG_ID_FILE.name} - MISSING", "ERROR")
        return False


# =========================
# AUTOSTART (REGISTRY)
# =========================

AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "SecurityLayerAgent"


def is_registry_exists():
    """Check if Registry autostart entry already exists"""
    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTOSTART_KEY,
            0,
            winreg.KEY_READ
        )
        winreg.QueryValueEx(key, AUTOSTART_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def register_autostart():
    """Register autostart via Windows Registry (no admin required)"""
    import winreg

    # Check if already exists
    if is_registry_exists():
        log_message(f"Registry autostart already exists: {AUTOSTART_NAME} - OK")
        return True

    pythonw = SCRIPT_DIR / "python" / "pythonw.exe"
    command = f'"{pythonw}" "{A_RUN_SCRIPT}"'

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            AUTOSTART_KEY,
            0,
            winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)

        return True

    except Exception as e:
        log_message(f"Failed to register autostart: {e}", "ERROR")
        return False


# =========================
# AUTOSTART (TASK SCHEDULER)
# =========================

def is_task_exists():
    """Check if Task Scheduler task already exists"""
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True
    )
    return result.returncode == 0


def create_startup_task():
    """Create Task Scheduler task with IgnoreNew policy (prevents duplicate instances)"""
    # Check if already exists
    if is_task_exists():
        log_message(f"Task Scheduler task already exists: {TASK_NAME} - OK")
        return True

    log_message("Setting up Task Scheduler (IgnoreNew protection)...")

    pythonw = SCRIPT_DIR / "python" / "pythonw.exe"
    script_path = str(A_RUN_SCRIPT)

    xml_content = f'''<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Security Layer USB Monitoring System</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <RunOnlyIfIdle>false</RunOnlyIfIdle>
    <WakeToRun>false</WakeToRun>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>"{pythonw}"</Command>
      <Arguments>"{script_path}"</Arguments>
      <WorkingDirectory>{SCRIPT_DIR}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>'''

    xml_file = SCRIPT_DIR / "task_temp.xml"

    try:
        with open(xml_file, 'w', encoding='utf-16') as f:
            f.write(xml_content)

        subprocess.check_call(
            ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_file), "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE
        )

        xml_file.unlink()
        log_message(f"Task Scheduler task '{TASK_NAME}' created (IgnoreNew enabled)")
        return True

    except subprocess.CalledProcessError as e:
        log_message(f"Failed to create Task Scheduler task: {e}", "WARNING")
        if xml_file.exists():
            xml_file.unlink()
        return False
    except Exception as e:
        log_message(f"Task Scheduler error: {e}", "WARNING")
        if xml_file.exists():
            xml_file.unlink()
        return False


def cleanup_old_task_scheduler():
    """Remove old Task Scheduler task (always try, ignore errors)"""
    # Always try to delete - don't rely on is_task_exists() which can be unreliable
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True
    )
    if result.returncode == 0:
        log_message(f"Removed old Task Scheduler task: {TASK_NAME}")


# =========================
# RUN AGENT
# =========================

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
        else:
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


# =========================
# MAIN
# =========================

def main():
    """Main installation flow"""

    # Step 1: Check Python version
    if not check_python_version():
        print("\n[ERROR] Python 3.6 or newer is required!")
        return 1

    # Step 2: Check/Install WMI
    if not check_wmi_package():
        print("[INFO] WMI package not found. Installing...")
        if not install_wmi_package():
            log_message("Installation aborted - WMI install failed", "ERROR")
            return 1

    # Step 3: Check/Install psutil
    if not check_psutil_package():
        print("[INFO] psutil package not found. Installing...")
        if not install_psutil_package():
            log_message("Installation aborted - psutil install failed", "ERROR")
            return 1

    # Step 4: Check org ID file
    if not check_org_id_file():
        log_message("Installation aborted - A_org_id.csv missing", "ERROR")
        return 1

    # Step 5: Register autostart (Registry only - no Task Scheduler fallback)
    if register_autostart():
        # Remove old Task Scheduler task if exists (migration cleanup)
        cleanup_old_task_scheduler()
    else:
        log_message("WARNING: Registry autostart failed - manual start required", "WARNING")

    # Step 6: Start agent
    if not run_agent():
        log_message("Installation failed - agent did not start", "ERROR")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
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