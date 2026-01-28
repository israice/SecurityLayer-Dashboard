"""Security Layer - Package Builder. Creates portable deployment package with embedded Python."""

import urllib.request
import zipfile
import shutil
import subprocess
import sys
from pathlib import Path
import hashlib
import json

# Configuration
PYTHON_VERSION = "3.11.9"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
USBTREEVIEW_URL = "https://www.uwe-sieber.de/files/UsbTreeView_x64.zip"
DEPENDENCIES = ["PyMI>=1.0.8", "psutil>=5.9.0", "requests>=2.31.0"]
EXCLUDE_PATTERNS = ["__pycache__", ".pyc"]
USBTREEVIEW_EXE = "CBA_UsbTreeView.exe"

# Paths
PROJECT_ROOT = Path(__file__).parent.absolute()
SECURITY_LAYER_DIR = PROJECT_ROOT / "SecurityLayer"
USB_SECURITY_DIR = SECURITY_LAYER_DIR / "usbSecurity"
PYTHON_DIR = USB_SECURITY_DIR / "python"
DIST_DIR = PROJECT_ROOT / "ZIP"
OUTPUT_ZIP = DIST_DIR / "SecurityLayer_USB_Monitor.zip"
MANIFEST_FILE = USB_SECURITY_DIR / ".build_manifest.json"


def download_file(url, dest_path, description="file"):
    print(f"  Downloading {description}...")
    try:
        with urllib.request.urlopen(url) as response:
            dest_path.write_bytes(response.read())
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def extract_zip(zip_path, extract_to):
    print(f"  Extracting {zip_path.name}...")
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_to)
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def load_manifest() -> dict:
    if MANIFEST_FILE.exists():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def save_manifest(manifest: dict):
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def get_folder_size(folder: Path, exclude_dirs: list | None = None) -> int:
    """Calculate total size of all files in folder."""
    exclude_dirs = exclude_dirs or []
    total = 0
    for f in folder.rglob('*'):
        if f.is_file():
            # Skip excluded directories
            if any(excl in str(f) for excl in exclude_dirs + ['__pycache__']):
                continue
            total += f.stat().st_size
    return total


def get_python_hash() -> str:
    """Hash for Python folder based on size + config."""
    size = get_folder_size(PYTHON_DIR) if PYTHON_DIR.exists() else 0
    config = f"{PYTHON_VERSION}|{size}|{'|'.join(sorted(DEPENDENCIES))}"
    return hashlib.sha256(config.encode()).hexdigest()[:16]


def get_project_hash() -> str:
    """Hash for project files (excluding python/ folder)."""
    size = get_folder_size(SECURITY_LAYER_DIR, exclude_dirs=['python', '.build_manifest.json'])
    return hashlib.sha256(str(size).encode()).hexdigest()[:16]


def is_python_valid(manifest: dict) -> bool:
    """Check if Python folder exists and matches saved size hash."""
    if not PYTHON_DIR.exists() or not (PYTHON_DIR / "python.exe").exists():
        return False
    
    saved_hash = manifest.get("python_hash", "")
    current_hash = get_python_hash()
    
    if saved_hash != current_hash:
        print(f"  Python folder changed: {saved_hash} -> {current_hash}")
        return False
    
    if not (PYTHON_DIR / "Lib" / "site-packages").exists():
        return False
    
    return True


def is_zip_valid(manifest: dict) -> bool:
    """Check if ZIP exists and project files haven't changed."""
    if not OUTPUT_ZIP.exists():
        return False
    
    saved_hash = manifest.get("project_hash", "")
    current_hash = get_project_hash()
    
    if saved_hash != current_hash:
        print(f"  Project files changed: {saved_hash} -> {current_hash}")
        return False
    
    return True


def run_python(python_exe, args, error_msg):
    try:
        result = subprocess.run([str(python_exe)] + args, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  ERROR: {error_msg}\n{result.stderr}")
            return False
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def ensure_python_ready(manifest: dict) -> tuple:
    """Ensure Python folder exists with all dependencies. Download if needed."""
    if is_python_valid(manifest):
        print("  Python + dependencies: OK")
        return True, manifest

    print("  Setting up Python environment...")
    
    # Clean existing python folder if any
    if PYTHON_DIR.exists():
        print("  Removing old Python folder...")
        shutil.rmtree(PYTHON_DIR)
    
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = USB_SECURITY_DIR / "_temp_setup"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Download and extract Python
        python_zip = temp_dir / "python-embed.zip"
        if not download_file(PYTHON_URL, python_zip, f"Python {PYTHON_VERSION}"):
            return False, manifest
        if not extract_zip(python_zip, PYTHON_DIR):
            return False, manifest
        python_zip.unlink()

        # Enable site-packages
        for pth in PYTHON_DIR.glob("python*._pth"):
            pth.write_text(pth.read_text().replace("#import site", "import site"))
            print(f"  Modified {pth.name}")

        # Install pip
        print("  Installing pip...")
        get_pip = temp_dir / "get-pip.py"
        if not download_file(GET_PIP_URL, get_pip, "get-pip.py"):
            return False, manifest

        python_exe = PYTHON_DIR / "python.exe"
        if not run_python(python_exe, [str(get_pip), "--no-warn-script-location"], "pip installation failed"):
            return False, manifest

        # Install dependencies
        print("  Installing dependencies...")
        if not run_python(python_exe, ["-m", "pip", "install"] + DEPENDENCIES + ["--no-warn-script-location"],
                          "Dependency installation failed"):
            return False, manifest

        # Update manifest with python hash
        manifest["python_hash"] = get_python_hash()
        manifest["python_version"] = PYTHON_VERSION
        save_manifest(manifest)
        
        print("  Python environment ready!")
        return True, manifest
    
    finally:
        # Cleanup temp
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def ensure_usbtreeview_ready() -> bool:
    """Ensure UsbTreeView.exe exists. Download if needed."""
    usbtreeview_path = USB_SECURITY_DIR / USBTREEVIEW_EXE
    
    if usbtreeview_path.exists():
        print("  UsbTreeView: OK")
        return True

    print("  Downloading UsbTreeView...")
    temp_dir = USB_SECURITY_DIR / "_temp_usbtree"
    temp_dir.mkdir(exist_ok=True)

    try:
        usbtree_zip = temp_dir / "UsbTreeView.zip"
        if not download_file(USBTREEVIEW_URL, usbtree_zip, "UsbTreeView"):
            return False

        if not extract_zip(usbtree_zip, temp_dir):
            return False

        exe = next(temp_dir.rglob("UsbTreeView.exe"), None)
        if not exe:
            print("  ERROR: UsbTreeView.exe not found")
            return False

        shutil.copy2(exe, usbtreeview_path)
        print("  UsbTreeView ready!")
        return True
    
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def create_zip(manifest: dict) -> tuple:
    """Create final ZIP from SecurityLayer folder if needed."""
    if is_zip_valid(manifest):
        print(f"  ZIP up to date: {OUTPUT_ZIP.name}")
        return True, manifest
    
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()
    
    print("  Creating ZIP archive...")
    try:
        with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in SECURITY_LAYER_DIR.rglob('*'):
                if p.is_file():
                    # Skip excluded patterns
                    if any(x in str(p) for x in EXCLUDE_PATTERNS):
                        continue
                    # Skip manifest file (not needed in distribution)
                    if p == MANIFEST_FILE:
                        continue
                    
                    arcname = Path("SecurityLayer") / p.relative_to(SECURITY_LAYER_DIR)
                    zf.write(p, arcname)
        
        # Update manifest with project hash
        manifest["project_hash"] = get_project_hash()
        save_manifest(manifest)
        
        print(f"  Package: {OUTPUT_ZIP} ({OUTPUT_ZIP.stat().st_size:,} bytes)")
        return True, manifest
    except Exception as e:
        print(f"  ERROR: {e}")
        return False, manifest


def main():
    print("=" * 50)
    print("Security Layer - Package Builder")
    print("=" * 50)

    try:
        manifest = load_manifest()
        
        # Step 1: Ensure Python is ready
        print("\n[1/3] Checking Python environment")
        ok, manifest = ensure_python_ready(manifest)
        if not ok:
            return 1

        # Step 2: Ensure UsbTreeView is ready
        print("\n[2/3] Checking UsbTreeView")
        if not ensure_usbtreeview_ready():
            return 1

        # Step 3: Create ZIP (only if changed)
        print("\n[3/3] Checking distribution package")
        ok, manifest = create_zip(manifest)
        if not ok:
            return 1

        print("\n" + "=" * 50)
        print("BUILD SUCCESSFUL!")
        print("=" * 50)
        return 0

    except KeyboardInterrupt:
        print("\n[CANCELLED]")
        return 130
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    if "-f" in sys.argv or "--force" in sys.argv:
        print("Force rebuild: removing Python folder and manifest...")
        if PYTHON_DIR.exists():
            shutil.rmtree(PYTHON_DIR)
        if MANIFEST_FILE.exists():
            MANIFEST_FILE.unlink()
        if OUTPUT_ZIP.exists():
            OUTPUT_ZIP.unlink()
    sys.exit(main())
