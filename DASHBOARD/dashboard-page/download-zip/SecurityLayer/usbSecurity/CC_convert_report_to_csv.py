import os
import csv
import hashlib
import re

# =========================
# CONFIG
# =========================

ORG_ID_FILE = "A_org_id.csv"
PC_ID_FILE = "CAA_get_pc_id.csv"

REPORT_FILE = "CBB_USB_Ports_Report.txt"
OUTPUT_FILE = "CCA_final_ports_list.csv"

CSV_HEADERS = ["ORG_ID", "PC_ID", "PORT_ID", "PORT_MAP", "PORT_STATUS", "PORT_NAME"]
HASH_LEN = 8
LOOKAHEAD = 30000

GENERIC_PRODUCTS = [
    "Mass Storage Device", "USB Mass Storage Device",
    "USB Composite Device", "USB Device", "USB Hub",
    "Wireless Device", "Input Device", "Disk drive"
]

GENERIC_MANUFACTURERS = [
    "Generic", "Standard", "Compatible", "(Standard USB Host Controller)"
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Encodings to try (in order of priority)
ENCODINGS = ["utf-16-le", "utf-16-be", "utf-8-sig", "utf-8", "cp1251", "latin-1"]


# =========================
# FUNCTIONS
# =========================
def read_file_with_encoding(path):
    """Try multiple encodings to read the file."""
    for encoding in ENCODINGS:
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
                # Verify content looks valid (contains expected markers)
                if "USB" in content and "Port" in content:
                    return content
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise ValueError(f"Could not read file {path} with any known encoding")


def read_org_id():
    """Read ORG_ID from A_org_id.csv"""
    path = os.path.join(SCRIPT_DIR, ORG_ID_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            if len(rows) >= 2:
                return rows[1][0].strip()
    except:
        pass
    return None


def read_pc_id():
    """Read PC_ID from A_get_pc_id.csv"""
    path = os.path.join(SCRIPT_DIR, PC_ID_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            if len(rows) >= 2:
                return rows[1][0].strip()
    except:
        pass
    return None


def create_port_id(pc_id, chain):
    combined = f"{pc_id}_{chain}"
    return "PORT_" + hashlib.md5(combined.encode()).hexdigest()[:HASH_LEN]


def is_user_connectable(block):
    """Check if port is physically accessible (not virtual/internal)"""
    match = re.search(r'IsUserConnectable\s*:\s*(\w+)', block)
    if match:
        return match.group(1).strip().lower() == "yes"
    return True


def parse_physical_controllers(content):
    """Parse USB Host Controllers and return set of physical controller indices.

    Physical controllers have Enumerator: PCI
    Virtual controllers have Enumerator: ROOT (e.g., Parsec, VirtualBox)
    """
    physical_controllers = set()

    # Split content by controller sections
    controller_pattern = re.compile(
        r'={20,}\s*USB\s+Host\s+Controller\s*={20,}',
        re.DOTALL
    )

    # Find all controller section start positions
    controller_starts = [m.start() for m in controller_pattern.finditer(content)]

    for idx, start in enumerate(controller_starts):
        controller_idx = idx + 1

        # Get text until next controller or end of file
        if idx + 1 < len(controller_starts):
            end = controller_starts[idx + 1]
        else:
            end = len(content)

        block = content[start:end]

        # Check Enumerator type
        enumerator_match = re.search(r'Enumerator\s*:\s*(\w+)', block)
        if enumerator_match:
            enumerator = enumerator_match.group(1).strip().upper()
            if enumerator == "PCI":
                physical_controllers.add(controller_idx)

    return physical_controllers


def get_controller_index_from_chain(chain):
    """Extract controller index from port chain (first number)."""
    parts = chain.split('-')
    if parts:
        try:
            return int(parts[0])
        except ValueError:
            pass
    return 0


def parse_usb_report():
    path = os.path.join(SCRIPT_DIR, REPORT_FILE)
    ports = []

    content = read_file_with_encoding(path)

    physical_controllers = parse_physical_controllers(content)

    pattern = re.compile(
        r'={20,}.*?USB Port\d+.*?={20,}.*?'
        r'Connection Status\s*:\s*0x(\d+)\s*\((.*?)\).*?'
        r'Port Chain\s*:\s*([\d\-\.]+)',
        re.DOTALL
    )

    for m in pattern.finditer(content):
        code, text, chain = m.groups()

        controller_idx = get_controller_index_from_chain(chain)
        if controller_idx not in physical_controllers:
            continue

        block = content[m.end():m.end() + LOOKAHEAD]

        if not is_user_connectable(block):
            continue

        if code == "00" or "No device is connected" in text:
            ports.append({
                "chain": chain,
                "device": f"PORT_{chain.replace('-', '_')}_EMPTY",
                "status": "Free",
                "name": "Empty USB Port"
            })
            continue

        def find(rx):
            r = re.search(rx, block)
            return r.group(1).strip() if r else None

        manufacturer = find(r'Manufacturer String\s*:\s*"(.+?)"')
        product = find(r'Product String\s*:\s*"(.+?)"')

        name = (
            find(r'Friendly\s+Name\s*:\s*(.+)') or
            find(r'BusReported\s+Device\s+Desc\s*:\s*(.+)') or
            product or
            find(r'Device Description\s*:\s*(.+)') or
            f"USB Device at {chain}"
        )

        if product in GENERIC_PRODUCTS and manufacturer not in GENERIC_MANUFACTURERS:
            name = f"{manufacturer} {product}"

        device = find(r'Device ID\s*:\s*(.+)') or f"UNKNOWN_{chain}"

        ports.append({
            "chain": chain,
            "device": device,
            "status": "Secured",
            "name": name
        })

    return ports


def write_ports_csv(ports, org_id, pc_id):
    path = os.path.join(SCRIPT_DIR, OUTPUT_FILE)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADERS)
        for p in ports:
            w.writerow([
                org_id,
                pc_id,
                create_port_id(pc_id, p["chain"]),
                p["chain"],
                p["status"],
                p["name"]
            ])


# =========================
# MAIN
# =========================
def main():
    org_id = read_org_id()
    pc_id = read_pc_id()

    if not org_id:
        print("Error: ORG_ID not found in A_org_id.csv")
        return

    if not pc_id:
        print("Error: PC_ID not found in A_get_pc_id.csv")
        return

    ports = parse_usb_report()
    if not ports:
        print("Error: No ports found")
        return

    write_ports_csv(ports, org_id, pc_id)
    print(f"Success: {len(ports)} ports exported to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
