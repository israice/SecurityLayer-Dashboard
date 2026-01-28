import asyncio
import subprocess
import sys
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Directory where this script is located
SCRIPT_DIR = Path(__file__).parent

# Scripts (just filenames - all in same folder as this script)
SCRIPTS = [
    "CA_get_pc_id.py",
    "CB_create_usb_report.py",
    "CC_convert_report_to_csv.py",
    "CD_send_final_csv_to_server.py",
]


async def run_script(script_name: str):
    script_path = SCRIPT_DIR / script_name
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    process = await asyncio.create_subprocess_exec(
        sys.executable, str(script_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        creationflags=creationflags
    )
    stdout, stderr = await process.communicate()
    if stdout.decode().strip():
        print(stdout.decode().strip())
    if stderr.decode().strip():
        print(stderr.decode().strip())


async def main():
    for script in SCRIPTS:
        await run_script(script)


if __name__ == "__main__":
    asyncio.run(main())