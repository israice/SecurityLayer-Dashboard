"""USB Device Change Watcher - runs scripts on USB connect/disconnect."""

import subprocess
import sys
import time
import logging
import os
from pathlib import Path

if sys.platform == 'win32':
    import msvcrt

# Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()
SCRIPT_ON_CONNECT = SCRIPT_DIR / "C_run.py"
SCRIPT_ON_DISCONNECT = SCRIPT_DIR / "C_run.py"
LOG_FILE = SCRIPT_DIR.parent / "history.log"
WATCHER_LOCK_FILE = SCRIPT_DIR / "watcher.lock"
USB_PNP_FILTER = "USB%"
POLL_INTERVAL_SECONDS = 2
POST_EVENT_DELAY_SECONDS = 1

# Logging setup
logging.basicConfig(
    filename=str(LOG_FILE), level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S', filemode='a', encoding='utf-8'
)
logging.raiseExceptions = False
logger = logging.getLogger('USBWatcher')


def acquire_watcher_lock():
    """Acquire exclusive lock to ensure only one watcher instance runs."""
    if sys.platform != 'win32':
        return None, True
    try:
        fd = os.open(str(WATCHER_LOCK_FILE), os.O_RDWR | os.O_CREAT)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, str(os.getpid()).encode())
            return fd, True
        except OSError:
            os.close(fd)
            return None, False
    except Exception as e:
        logger.error(f"Failed to acquire lock: {e}")
        return None, False


def load_wmi():
    """Load WMI module and return WMI connection."""
    try:
        import wmi
        return wmi.WMI()
    except ImportError:
        logger.error("WMI module not found. Install with: pip install wmi")
        sys.exit(1)


def extract_device_info(device):
    """Extract device info from WMI object."""
    pnp = getattr(device, "PNPDeviceID", "") or ""
    info = {
        "name": getattr(device, "Name", None),
        "device_id": getattr(device, "DeviceID", None),
        "pnp_device_id": pnp,
        "description": getattr(device, "Description", None),
        "manufacturer": getattr(device, "Manufacturer", None),
        "status": getattr(device, "Status", None),
    }
    if "\\" in pnp and len(pnp.split("\\")) > 1:
        info["usb_ids"] = pnp.split("\\")[1]
    return info


def query_usb_devices(wmi_conn):
    """Query USB devices using WMI connection (all USB interfaces)."""
    devices = {}
    query = f"SELECT * FROM Win32_PnPEntity WHERE PNPDeviceID LIKE '{USB_PNP_FILTER}'"
    for dev in wmi_conn.query(query):
        pnp_id = getattr(dev, "PNPDeviceID", None)
        if pnp_id:
            devices[pnp_id] = extract_device_info(dev)
    return devices


def log_device_event(event_type, info):
    """Log USB device event."""
    logger.info(f"USB {event_type.upper()}: {info.get('name')} | "
                f"{info.get('description')} | {info.get('manufacturer')}")


def run_script(script_path):
    """Run external Python script."""
    try:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True, text=True, creationflags=flags
        )
        if result.stdout.strip():
            logger.info(result.stdout.strip())
        if result.stderr.strip():
            logger.warning(f"Script stderr: {result.stderr.strip()}")
    except Exception as e:
        logger.error(f"Failed to run script {script_path}: {e}")


def watch_usb_changes():
    """Main USB monitoring loop."""
    wmi_conn = load_wmi()
    logger.info("Monitoring USB devices...")
    previous = query_usb_devices(wmi_conn)

    try:
        while True:
            time.sleep(POLL_INTERVAL_SECONDS)
            current = query_usb_devices(wmi_conn)

            connected = [info for pid, info in current.items() if pid not in previous]
            disconnected = [info for pid, info in previous.items() if pid not in current]

            if connected:
                for info in connected:
                    log_device_event("connected", info)
                time.sleep(POST_EVENT_DELAY_SECONDS)
                run_script(SCRIPT_ON_CONNECT)

            if disconnected:
                for info in disconnected:
                    log_device_event("disconnected", info)
                time.sleep(POST_EVENT_DELAY_SECONDS)
                run_script(SCRIPT_ON_DISCONNECT)

            previous = current
    except KeyboardInterrupt:
        logger.info("USB watcher stopped")


def main():
    """Entry point with singleton lock."""
    lock_fd, got_lock = acquire_watcher_lock()
    if not got_lock:
        logger.info("Another watcher instance is already running, exiting")
        return 0

    try:
        watch_usb_changes()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
