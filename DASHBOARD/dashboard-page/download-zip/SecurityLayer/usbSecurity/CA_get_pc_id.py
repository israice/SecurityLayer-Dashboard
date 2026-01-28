"""Get unique PC ID based on UUID."""

import csv
import hashlib
import subprocess
import sys
from pathlib import Path

# Directory where this script is located
SCRIPT_DIR = Path(__file__).parent

# Paths
PC_ID_CSV = SCRIPT_DIR / "CAA_get_pc_id.csv"


def get_pc_uuid() -> str:
    """Get PC UUID via PowerShell (works on all Windows versions)."""
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    try:
        # Try PowerShell method (works on all modern Windows)
        result = subprocess.run(
            ["powershell", "-Command", "Get-CimInstance -ClassName Win32_ComputerSystemProduct | Select-Object -ExpandProperty UUID"],
            capture_output=True, text=True, check=True, timeout=10,
            creationflags=creationflags
        )
        uuid = result.stdout.strip()
        if uuid:
            return uuid
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback to wmic (for older Windows)
    try:
        result = subprocess.run(
            ["wmic", "csproduct", "get", "uuid"],
            capture_output=True, text=True, check=True, timeout=10,
            creationflags=creationflags
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and line.upper() != "UUID":
                return line
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    raise RuntimeError("Failed to get UUID via PowerShell or WMIC")


def get_pc_id(uuid: str) -> str:
    """Create short ID: PC_ + 8 chars of SHA256."""
    return f"PC_{hashlib.sha256(uuid.encode()).hexdigest()[:8]}"


def save_to_csv(pc_id: str, uuid: str, path: Path) -> bool:
    """Save to CSV. Returns True if file was updated."""
    if path.exists():
        with open(path, encoding="utf-8") as f:
            rows = list(csv.reader(f))
            if len(rows) > 1 and rows[1][0] == pc_id:
                return False

    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["PC_ID", "PC_UUID"], [pc_id, uuid]])
    return True


def main():
    uuid = get_pc_uuid()
    pc_id = get_pc_id(uuid)
    save_to_csv(pc_id, uuid, PC_ID_CSV)



if __name__ == "__main__":
    main()
