import subprocess
import os
import sys
import time

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# =========================
# CONFIGURATION
# =========================

WAIT_TIMEOUT_SECONDS = 10
TARGET_EXE_NAME = "CBA_UsbTreeView.exe"
REPORT_FILENAME = "CBB_USB_Ports_Report.txt"
MIN_EXE_SIZE_BYTES = 500_000  # Valid UsbTreeView.exe should be > 500KB

# =========================
# HELPERS
# =========================

def get_script_dir():
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def wait_for_file(path, timeout):
    for _ in range(timeout):
        if os.path.exists(path):
            return True
        time.sleep(1)
    return False


# =========================
# MAIN LOGIC
# =========================

def ensure_usbtreeview(script_dir):
    """
    Verify UsbTreeView.exe exists in the package.
    Requires BD_UsbTreeView.exe to be pre-packaged in agent.zip during build.
    """
    target_exe_path = os.path.join(script_dir, TARGET_EXE_NAME)

    if not os.path.exists(target_exe_path):
        raise RuntimeError(
            f"{TARGET_EXE_NAME} not found. "
            "The agent.zip package was built incorrectly"
            "Please rebuild using: python package_builder.py --force"
        )

    file_size = os.path.getsize(target_exe_path)
    if file_size < MIN_EXE_SIZE_BYTES:
        raise RuntimeError(
            f"{TARGET_EXE_NAME} is corrupted ({file_size} bytes, expected > {MIN_EXE_SIZE_BYTES}). "
            "Please rebuild using: python package_builder.py --force"
        )

    return target_exe_path


def run_usbtreeview(exe_path, report_path, workdir):
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    subprocess.run(
        [exe_path, f"/R={report_path}"],
        cwd=workdir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        creationflags=creationflags
    )


def main():
    base_dir = get_script_dir()

    exe_path = ensure_usbtreeview(base_dir)
    report_path = os.path.join(base_dir, REPORT_FILENAME)

    run_usbtreeview(exe_path, report_path, base_dir)

    wait_for_file(report_path, WAIT_TIMEOUT_SECONDS)
    

if __name__ == "__main__":
    main()
