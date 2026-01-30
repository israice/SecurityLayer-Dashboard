"""Security Layer - Main Launcher. Runs initial USB scan and starts background monitoring."""

import subprocess
import sys
import os
import logging
import time
from pathlib import Path

if sys.platform == 'win32':
    import msvcrt

# Configuration
SCRIPT_DIR = Path(__file__).parent.absolute()
WATCHER_SCRIPT = SCRIPT_DIR / "BA_usb_watcher.py"
C_RUN_SCRIPT = SCRIPT_DIR / "C_run.py"
LOG_FILE = SCRIPT_DIR.parent / "history.log"
PID_FILE = SCRIPT_DIR / "watcher.pid"
LOCK_FILE = SCRIPT_DIR / "startup.lock"
WATCHER_LOCK_FILE = SCRIPT_DIR / "watcher.lock"

# Logging
logging.basicConfig(
    filename=str(LOG_FILE), level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S', filemode='a', encoding='utf-8'
)
logging.raiseExceptions = False
logger = logging.getLogger('SecurityLayer')


def _check_stale_lock():
    """Check and remove stale lock file. Returns True if lock is held by active process."""
    if not LOCK_FILE.exists():
        return False
    try:
        import psutil # type: ignore
        with open(LOCK_FILE, 'r') as f:
            old_pid = int(f.read().strip())
        if psutil.pid_exists(old_pid):
            try:
                proc = psutil.Process(old_pid)
                if 'B_run.py' in ' '.join(proc.cmdline()):
                    logger.info(f"Another B_run.py instance running (PID {old_pid})")
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        LOCK_FILE.unlink()
    except (ValueError, IOError, ImportError):
        try:
            LOCK_FILE.unlink()
        except OSError:
            pass
    return False


def acquire_startup_lock():
    """Acquire startup lock. Returns (file_handle, success)."""
    if sys.platform != 'win32':
        return None, True

    try:
        if _check_stale_lock():
            return None, False

        fd = os.open(str(LOCK_FILE), os.O_RDWR | os.O_CREAT | os.O_EXCL)
        try:
            pid_bytes = str(os.getpid()).encode()
            os.write(fd, pid_bytes)
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, len(pid_bytes))
            return fd, True
        except OSError:
            os.close(fd)
            try:
                LOCK_FILE.unlink()
            except OSError:
                pass
            return None, False
    except FileExistsError:
        logger.info("Lock file created by another process")
        return None, False
    except Exception as e:
        logger.warning(f"Lock error: {e}, proceeding anyway")
        return None, True


def release_startup_lock(fd):
    """Release the startup lock."""
    if fd is not None:
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            os.close(fd)
        except Exception:
            pass


def run_initial_scan():
    """Run C_run.py for initial USB port scan."""
    try:
        result = subprocess.run(
            [sys.executable, str(C_RUN_SCRIPT)],
            capture_output=True, text=True, timeout=300
        )
        if result.stdout:
            logger.info(f"{result.stdout}")
        if result.stderr:
            logger.warning(f"C_run.py stderr:\n{result.stderr}")
        if result.returncode != 0:
            logger.error(f"Initial USB scan failed with code {result.returncode}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Initial USB scan timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error(f"Failed to run initial scan: {e}")
        return False


def is_watcher_running():
    """Check if watcher is running via lock file."""
    if sys.platform != 'win32' or not WATCHER_LOCK_FILE.exists():
        return False
    try:
        fd = os.open(str(WATCHER_LOCK_FILE), os.O_RDWR)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            os.close(fd)
            return False
        except OSError:
            os.close(fd)
            return True
    except Exception:
        return False


def start_background_watcher():
    """Start watcher if not already running."""
    try:
        if is_watcher_running():
            logger.info("USB watcher already running (lock held)")
            return True

        process = subprocess.Popen(
            [sys.executable, str(WATCHER_SCRIPT)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        time.sleep(0.5)

        if is_watcher_running():
            with open(PID_FILE, 'w') as f:
                f.write(str(process.pid))
            return True
        logger.error("Watcher failed to start or acquire lock")
        return False
    except Exception as e:
        logger.error(f"Failed to start background watcher: {e}")
        return False


def main():
    """Main execution flow."""
    lock_fd, got_lock = acquire_startup_lock()
    if not got_lock:
        logger.info("Another instance is already running, exiting...")
        return 0

    try:
        if not C_RUN_SCRIPT.exists():
            logger.error(f"ERROR: {C_RUN_SCRIPT} not found")
            return 1
        if not WATCHER_SCRIPT.exists():
            logger.error(f"ERROR: {WATCHER_SCRIPT} not found")
            return 1

        if not run_initial_scan():
            logger.warning("Initial scan failed, but continuing with watcher...")

        if not start_background_watcher():
            logger.error("Failed to start background watcher")
            return 1
        return 0
    finally:
        release_startup_lock(lock_fd)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
