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


# =========================
# FUNCTIONS
# =========================
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


def create_port_id(device_id):
    return "PORT_" + hashlib.md5(device_id.encode()).hexdigest()[:HASH_LEN]


def is_companion_port(chain):
    try:
        hub, port = map(int, chain.split("-"))
        return (hub == 1 and port >= 11) or (hub >= 2 and port >= 13)
    except:
        return False


def is_user_connectable(block):
    """Check if port is physically accessible (not virtual/internal)"""
    match = re.search(r'IsUserConnectable\s*:\s*(\w+)', block)
    if match:
        return match.group(1).strip().lower() == "yes"
    return True  # Default to True if property not found


def parse_usb_report():
    path = os.path.join(SCRIPT_DIR, REPORT_FILE)
    ports = []

    with open(path, "r", encoding="utf-16-le") as f:
        content = f.read()

    pattern = re.compile(
        r'={20,}.*?USB Port\d+.*?={20,}.*?'
        r'Connection Status\s*:\s*0x(\d+)\s*\((.*?)\).*?'
        r'Port Chain\s*:\s*([\d\-\.]+)',
        re.DOTALL
    )

    for m in pattern.finditer(content):
        code, text, chain = m.groups()

        if is_companion_port(chain):
            continue

        block = content[m.end():m.end() + LOOKAHEAD]

        # Skip virtual/internal ports (not user-connectable)
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
            "status": "Used",
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
                create_port_id(p["device"]),
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

if __name__ == "__main__":
    main()
