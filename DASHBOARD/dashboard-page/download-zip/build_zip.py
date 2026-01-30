"""Security Layer - Package Builder. Creates portable deployment package with embedded Python."""

import urllib.request, zipfile, shutil, subprocess, sys, hashlib, json, tempfile
from pathlib import Path

# Configuration
PYTHON_VERSION = "3.11.9"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"
USBTREEVIEW_URL = "https://www.uwe-sieber.de/files/UsbTreeView_x64.zip"
DEPENDENCIES = ["PyMI>=1.0.8", "psutil>=5.9.0", "requests>=2.31.0"]
USBTREEVIEW_EXE = "CBA_UsbTreeView.exe"

# Paths
PROJECT_ROOT = Path(__file__).parent.absolute()
SECURITY_LAYER_DIR = PROJECT_ROOT / "SecurityLayer"
USB_SECURITY_DIR = SECURITY_LAYER_DIR / "usbSecurity"
PYTHON_DIR = USB_SECURITY_DIR / "python"
DIST_DIR = PROJECT_ROOT / "ZIP"
OUTPUT_ZIP = DIST_DIR / "SecurityLayer_USB_Monitor.zip"
MANIFEST_FILE = USB_SECURITY_DIR / ".build_manifest.json"


def download_and_extract(url, extract_to, description):
    print(f"  Downloading {description}...")
    try:
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
            tmp.write(urllib.request.urlopen(url).read())
            tmp_path = Path(tmp.name)
        with zipfile.ZipFile(tmp_path, 'r') as zf:
            zf.extractall(extract_to)
        tmp_path.unlink()
        return True
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def load_manifest():
    try:
        return json.loads(MANIFEST_FILE.read_text(encoding='utf-8')) if MANIFEST_FILE.exists() else {}
    except (json.JSONDecodeError, IOError):
        return {}


def save_manifest(manifest):
    MANIFEST_FILE.write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def get_folder_size(folder, exclude=None):
    exclude = exclude or []
    return sum(f.stat().st_size for f in folder.rglob('*')
               if f.is_file() and not any(x in str(f) for x in exclude + ['__pycache__']))


def get_hash(hash_type):
    if hash_type == "python":
        size = get_folder_size(PYTHON_DIR) if PYTHON_DIR.exists() else 0
        config = f"{PYTHON_VERSION}|{size}|{'|'.join(sorted(DEPENDENCIES))}"
    else:
        size = get_folder_size(SECURITY_LAYER_DIR, ['python', '.build_manifest.json'])
        config = str(size)
    return hashlib.sha256(config.encode()).hexdigest()[:16]


def is_valid(check_type, manifest):
    if check_type == "python":
        if not PYTHON_DIR.exists() or not (PYTHON_DIR / "python.exe").exists():
            return False
        if not (PYTHON_DIR / "Lib" / "site-packages").exists():
            return False
    else:
        if not OUTPUT_ZIP.exists():
            return False

    saved = manifest.get(f"{check_type}_hash", "")
    current = get_hash(check_type)
    if saved != current:
        print(f"  {check_type} changed: {saved[:8]}... -> {current[:8]}...")
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


def ensure_python_ready(manifest):
    if is_valid("python", manifest):
        print("  Python + dependencies: OK")
        return True, manifest

    print("  Setting up Python environment...")
    shutil.rmtree(PYTHON_DIR, ignore_errors=True)
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)

        if not download_and_extract(PYTHON_URL, PYTHON_DIR, f"Python {PYTHON_VERSION}"):
            return False, manifest

        for pth in PYTHON_DIR.glob("python*._pth"):
            pth.write_text(pth.read_text().replace("#import site", "import site"))

        print("  Installing pip...")
        get_pip = temp / "get-pip.py"
        get_pip.write_bytes(urllib.request.urlopen(GET_PIP_URL).read())

        python_exe = PYTHON_DIR / "python.exe"
        if not run_python(python_exe, [str(get_pip), "--no-warn-script-location"], "pip install failed"):
            return False, manifest

        print("  Installing dependencies...")
        if not run_python(python_exe, ["-m", "pip", "install"] + DEPENDENCIES + ["--no-warn-script-location"],
                          "Dependencies install failed"):
            return False, manifest

        manifest["python_hash"] = get_hash("python")
        manifest["python_version"] = PYTHON_VERSION
        save_manifest(manifest)
        print("  Python environment ready!")
        return True, manifest


def ensure_usbtreeview_ready():
    usbtreeview_path = USB_SECURITY_DIR / USBTREEVIEW_EXE
    if usbtreeview_path.exists():
        print("  UsbTreeView: OK")
        return True

    print("  Downloading UsbTreeView...")
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        if not download_and_extract(USBTREEVIEW_URL, temp, "UsbTreeView"):
            return False

        exe = next(temp.rglob("UsbTreeView.exe"), None)
        if not exe:
            print("  ERROR: UsbTreeView.exe not found")
            return False

        shutil.copy2(exe, usbtreeview_path)
        print("  UsbTreeView ready!")
        return True


def create_zip(manifest):
    if is_valid("project", manifest):
        print(f"  ZIP up to date: {OUTPUT_ZIP.name}")
        return True, manifest

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_ZIP.unlink(missing_ok=True)

    print("  Creating ZIP archive...")
    try:
        with zipfile.ZipFile(OUTPUT_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
            for p in SECURITY_LAYER_DIR.rglob('*'):
                if p.is_file() and '__pycache__' not in str(p) and '.pyc' not in str(p) and p != MANIFEST_FILE:
                    zf.write(p, Path("SecurityLayer") / p.relative_to(SECURITY_LAYER_DIR))

        manifest["project_hash"] = get_hash("project")
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

        steps = [
            ("[1/3] Checking Python environment", lambda m: ensure_python_ready(m)),
            ("[2/3] Checking UsbTreeView", lambda m: (ensure_usbtreeview_ready(), m)),
            ("[3/3] Checking distribution package", lambda m: create_zip(m)),
        ]

        for name, func in steps:
            print(f"\n{name}")
            result = func(manifest)
            ok, manifest = result if isinstance(result[0], bool) else result
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
        return 1


if __name__ == "__main__":
    if "-f" in sys.argv or "--force" in sys.argv:
        print("Force rebuild...")
        shutil.rmtree(PYTHON_DIR, ignore_errors=True)
        MANIFEST_FILE.unlink(missing_ok=True)
        OUTPUT_ZIP.unlink(missing_ok=True)
    sys.exit(main())
