"""
USB Device Change Watcher
Runs different scripts on USB connect and disconnect.
"""

import subprocess
import sys
import time
import logging
import os
from pathlib import Path

# Windows file locking
if sys.platform == 'win32':
    import msvcrt

# ==========================
# LOGGING
# ==========================

SCRIPT_DIR = Path(__file__).parent.absolute()
SCRIPT_ON_CONNECT = SCRIPT_DIR / "C_run.py"
SCRIPT_ON_DISCONNECT = SCRIPT_DIR / "C_run.py"
LOG_FILE = SCRIPT_DIR.parent / "history.log"
WATCHER_LOCK_FILE = SCRIPT_DIR / "watcher.lock"

# Configure logging for file-only output
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filemode='a',
    encoding='utf-8'
)

logging.raiseExceptions = False
logger = logging.getLogger('USBWatcher')

# =========================
# CONFIGURATION
# =========================


USB_PNP_FILTER = "USB%"
POLL_INTERVAL_SECONDS = 2
POST_EVENT_DELAY_SECONDS = 1


# =========================
# SINGLETON LOCK
# =========================

def acquire_watcher_lock():
    """
    Acquire exclusive lock to ensure only one watcher instance runs.
    Returns (fd, success). Lock is held for entire process lifetime.
    """
    if sys.platform != 'win32':
        return None, True  # Skip on non-Windows

    try:
        fd = os.open(str(WATCHER_LOCK_FILE), os.O_RDWR | os.O_CREAT)
        try:
            # Non-blocking exclusive lock
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            # Clear file and write PID for diagnostics
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, str(os.getpid()).encode())
            return fd, True
        except OSError:
            # Lock held by another process
            os.close(fd)
            return None, False
    except Exception as e:
        logger.error(f"Failed to acquire lock: {e}")
        return None, False


# =========================
# DEPENDENCIES
# =========================

def load_wmi():
    """Load WMI module and return WMI connection."""
    try:
        import wmi
        return wmi.WMI()
    except ImportError:
        logger.error("WMI module not found. Install with: pip install wmi")
        sys.exit(1)


# =========================
# USB LOGIC
# =========================

def extract_device_info(device):
    """Extract device info from WMI object (uses attributes, not dict)."""
    pnp = getattr(device, "PNPDeviceID", "") or ""
    info = {
        "name": getattr(device, "Name", None),
        "device_id": getattr(device, "DeviceID", None),
        "pnp_device_id": pnp,
        "description": getattr(device, "Description", None),
        "manufacturer": getattr(device, "Manufacturer", None),
        "status": getattr(device, "Status", None),
    }

    if "\\" in pnp:
        parts = pnp.split("\\")
        if len(parts) > 1:
            info["usb_ids"] = parts[1]

    return info


def is_parent_device(pnp_device_id):
    """Check if device is parent (not a child interface like MI_00, MI_01)"""
    if not pnp_device_id:
        return False
    # Child interfaces have &MI_XX in their ID
    return "&MI_" not in pnp_device_id.upper()


def query_usb_devices(wmi_conn):
    """Query USB devices using WMI connection (parent devices only)."""
    devices = {}
    query = (
        "SELECT * FROM Win32_PnPEntity "
        f"WHERE PNPDeviceID LIKE '{USB_PNP_FILTER}'"
    )

    for dev in wmi_conn.query(query):
        pnp_id = getattr(dev, "PNPDeviceID", None)
        # Skip child interfaces (MI_00, MI_01, etc.) - only track parent devices
        if pnp_id and is_parent_device(pnp_id):
            devices[pnp_id] = extract_device_info(dev)

    return devices


# =========================
# OUTPUT
# =========================

def print_device_event(event_type, info):
    logger.info("=" * 60)
    logger.info(f"USB DEVICE {event_type.upper()}")
    logger.info("=" * 60)
    logger.info(f"Name:         {info.get('name')}")
    logger.info(f"Description:  {info.get('description')}")
    logger.info(f"Manufacturer: {info.get('manufacturer')}")
    logger.info(f"Device ID:    {info.get('device_id')}")


# =========================
# ACTIONS
# =========================

def run_script(script_path):
    try:
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            creationflags=creationflags
        )

        if result.stdout.strip():
            logger.info(f"{result.stdout.strip()}")
        if result.stderr.strip():
            logger.warning(f"Script stderr: {result.stderr.strip()}")

    except Exception as e:
        logger.error(f"Failed to run script {script_path}: {e}")


# =========================
# MAIN LOOP
# =========================

def watch_usb_changes():
    wmi_conn = load_wmi()

    logger.info("Monitoring USB devices...")

    previous = query_usb_devices(wmi_conn)

    try:
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)

            current = query_usb_devices(wmi_conn)

            connected = []
            disconnected = []

            for pid, info in current.items():
                if pid not in previous:
                    connected.append(info)

            for pid, info in previous.items():
                if pid not in current:
                    disconnected.append(info)

            if connected:
                for info in connected:
                    print_device_event("connected", info)
                time.sleep(POST_EVENT_DELAY_SECONDS)
                run_script(SCRIPT_ON_CONNECT)

            if disconnected:
                for info in disconnected:
                    print_device_event("disconnected", info)
                time.sleep(POST_EVENT_DELAY_SECONDS)
                run_script(SCRIPT_ON_DISCONNECT)

            previous = current

    except KeyboardInterrupt:
        logger.info("USB watcher stopped")


# =========================
# ENTRY POINT
# =========================

def main():
    # Acquire exclusive lock - only one watcher can run
    lock_fd, got_lock = acquire_watcher_lock()
    if not got_lock:
        logger.info("Another watcher instance is already running, exiting")
        return 0  # Success - not an error

    try:
        watch_usb_changes()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        # Release lock (also released automatically when process exits)
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
