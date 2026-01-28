"""
Security Layer - Main Launcher
Runs initial USB scan and starts background monitoring
"""

import subprocess
import sys
import os
import logging
import time
from pathlib import Path

# Windows file locking (built-in, no extra packages)
if sys.platform == 'win32':
    import msvcrt

# =========================
# CONFIGURATION
# =========================

SCRIPT_DIR = Path(__file__).parent.absolute()
WATCHER_SCRIPT = SCRIPT_DIR / "BA_usb_watcher.py"
B_RUN_SCRIPT = SCRIPT_DIR / "C_run.py"

LOG_FILE = SCRIPT_DIR.parent / "history.log"
PID_FILE = SCRIPT_DIR / "watcher.pid"
LOCK_FILE = SCRIPT_DIR / "startup.lock"
WATCHER_LOCK_FILE = SCRIPT_DIR / "watcher.lock"

# =========================
# LOGGING
# =========================

# Configure logging BEFORE any other code
logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    filemode='a',
    encoding='utf-8'
)

# Disable console exceptions for pythonw.exe compatibility
logging.raiseExceptions = False

logger = logging.getLogger('SecurityLayer')


# =========================
# FILE LOCK (prevents race condition)
# =========================

def acquire_startup_lock():
    """
    Robust lock that survives hard reboots.
    Lock file contains PID - if PID is dead, lock is stale and can be taken.
    Returns (file_handle, success).
    """
    if sys.platform != 'win32':
        return None, True  # Skip on non-Windows

    try:
        import psutil  # type: ignore

        # Check for stale lock BEFORE trying to acquire
        if LOCK_FILE.exists():
            try:
                with open(LOCK_FILE, 'r') as f:
                    old_pid = int(f.read().strip())

                # Check if process with this PID is alive
                if psutil.pid_exists(old_pid):
                    try:
                        proc = psutil.Process(old_pid)
                        cmdline = ' '.join(proc.cmdline())
                        if 'B_run.py' in cmdline:
                            # Process is alive and it's ours - lock is valid
                            logger.info(f"Another B_run.py instance running (PID {old_pid})")
                            return None, False
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # PID is dead or not our process - remove stale lock
                LOCK_FILE.unlink()

            except (ValueError, IOError):
                # File is corrupted - remove it
                logger.info("Removing corrupted lock file")
                LOCK_FILE.unlink()

        # Create new lock with our PID using O_EXCL for atomicity
        fd = os.open(str(LOCK_FILE), os.O_RDWR | os.O_CREAT | os.O_EXCL)
        try:
            # Write our PID
            pid_bytes = str(os.getpid()).encode()
            os.write(fd, pid_bytes)
            os.lseek(fd, 0, os.SEEK_SET)
            # Acquire lock
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
        # O_EXCL failed - another process created file between check and create
        logger.info("Lock file created by another process")
        return None, False
    except ImportError:
        # psutil not available - fall back to simple lock
        logger.warning("psutil not available, using simple lock")
        return _acquire_simple_lock()
    except Exception as e:
        logger.warning(f"Lock acquisition error: {e}, proceeding anyway")
        return None, True  # On error, proceed (better to run than not)


def _acquire_simple_lock():
    """Fallback simple lock without PID check."""
    try:
        fd = os.open(str(LOCK_FILE), os.O_RDWR | os.O_CREAT)
        try:
            os.write(fd, b'L')
            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            return fd, True
        except OSError:
            os.close(fd)
            return None, False
    except Exception:
        return None, True


def release_startup_lock(fd):
    """Release the lock."""
    if fd is not None:
        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            os.close(fd)
        except Exception:
            pass


# =========================
# SCRIPT EXECUTION
# =========================

def run_initial_scan():
    """Run B_run.py for initial USB port scan"""

    try:
        result = subprocess.run(
            [sys.executable, str(B_RUN_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutes timeout
        )

        if result.stdout:
            logger.info(f"{result.stdout}")

        if result.stderr:
            logger.warning(f"B_run.py stderr:\n{result.stderr}")

        if result.returncode == 0:
            return True
        else:
            logger.error(f"Initial USB scan failed with code {result.returncode}")
            return False

    except subprocess.TimeoutExpired:
        logger.error("Initial USB scan timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error(f"Failed to run initial scan: {e}")
        return False


def is_watcher_running():
    """Check if watcher is running by trying to acquire its lock (100% reliable)."""
    if sys.platform != 'win32':
        return False

    if not WATCHER_LOCK_FILE.exists():
        return False

    try:
        fd = os.open(str(WATCHER_LOCK_FILE), os.O_RDWR)
        try:
            # Try non-blocking lock
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            # Success = watcher is NOT running, release lock
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            os.close(fd)
            return False
        except OSError:
            # Failed to lock = watcher IS running
            os.close(fd)
            return True
    except Exception:
        return False


def start_background_watcher():
    """Start watcher if not already running (uses lock-based check)."""

    try:
        # Check via lock (100% reliable)
        if is_watcher_running():
            logger.info("USB watcher already running (lock held)")
            return True

        # Start watcher process
        process = subprocess.Popen(
            [sys.executable, str(WATCHER_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )

        # Give watcher time to acquire lock
        time.sleep(0.5)

        # Verify watcher started and acquired lock
        if is_watcher_running():
            # Save PID for diagnostics (optional)
            with open(PID_FILE, 'w') as f:
                f.write(str(process.pid))
            return True
        else:
            logger.error("Watcher failed to start or acquire lock")
            return False

    except Exception as e:
        logger.error(f"Failed to start background watcher: {e}")
        return False


# =========================
# MAIN
# =========================

def main():
    """Main execution flow"""

    # Acquire lock to prevent parallel execution (Registry + Task Scheduler)
    lock_fd, got_lock = acquire_startup_lock()
    if not got_lock:
        logger.info("Another instance is already running, exiting...")
        return 0

    try:
        # Check if required scripts exist
        if not B_RUN_SCRIPT.exists():
            logger.error(f"ERROR: {B_RUN_SCRIPT} not found")
            return 1

        if not WATCHER_SCRIPT.exists():
            logger.error(f"ERROR: {WATCHER_SCRIPT} not found")
            return 1

        # Run initial scan
        if not run_initial_scan():
            logger.warning("Initial scan failed, but continuing with watcher...")

        # Start background watcher
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
