"""
USB Port Report to CSV Converter

Converts UsbTreeView reports to CSV format with port status information.
Uses section-based parsing for stability and reliability.
"""

import os
import csv
import hashlib
import re
from dataclasses import dataclass
from typing import Optional


# =========================
# CONFIG
# =========================

ORG_ID_FILE = "A_org_id.csv"
PC_ID_FILE = "CAA_get_pc_id.csv"
REPORT_FILE = "CBB_USB_Ports_Report.txt"
OUTPUT_FILE = "CCA_final_ports_list.csv"

CSV_HEADERS = ["ORG_ID", "PC_ID", "PORT_ID", "PORT_MAP", "PORT_STATUS", "PORT_NAME"]
HASH_LEN = 8

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# =========================
# DATA STRUCTURES
# =========================

@dataclass
class USBPort:
    """Represents a USB port with its properties."""
    port_number: int
    chain: str                          # "1-1", "1-3"
    connected: bool                     # Device connected
    user_connectable: bool              # External port (accessible to user)
    is_type_c: bool                     # USB Type-C connector
    companion_chain: Optional[str]      # USB 2.0/3.0 companion pair
    device_name: Optional[str]          # Device name if connected
    is_internal: bool                   # Internally connected device


# =========================
# FILE READING
# =========================

def read_file_with_bom_detection(path: str) -> str:
    """Read file with automatic BOM detection for encoding."""
    with open(path, "rb") as f:
        raw = f.read()

    # Detect BOM
    if raw.startswith(b'\xff\xfe'):
        return raw.decode("utf-16-le")
    elif raw.startswith(b'\xfe\xff'):
        return raw.decode("utf-16-be")
    elif raw.startswith(b'\xef\xbb\xbf'):
        return raw.decode("utf-8-sig")
    else:
        # Try UTF-8, fallback to latin-1
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return raw.decode("latin-1")


def normalize_wide_spacing(content: str) -> str:
    """
    Normalize wide-spacing text from UsbTreeView UTF-16 output.

    UsbTreeView sometimes outputs text with spaces between each character
    like "U S B   P o r t". This normalizes it to "USB Port".
    """
    lines = content.split('\n')
    normalized = []

    for line in lines:
        # Check if line has wide-spacing pattern (alternating char-space)
        if len(line) > 4:
            # Sample: check if odd positions are mostly spaces
            odd_chars = line[1::2]
            if odd_chars and odd_chars.count(' ') > len(odd_chars) * 0.7:
                # Remove every other character (the spaces)
                line = line[::2]
        normalized.append(line)

    return '\n'.join(normalized)


# =========================
# ID READING
# =========================

def read_org_id() -> Optional[str]:
    """Read ORG_ID from A_org_id.csv"""
    path = os.path.join(SCRIPT_DIR, ORG_ID_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            if len(rows) >= 2:
                return rows[1][0].strip()
    except Exception:
        pass
    return None


def read_pc_id() -> Optional[str]:
    """Read PC_ID from CAA_get_pc_id.csv"""
    path = os.path.join(SCRIPT_DIR, PC_ID_FILE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            if len(rows) >= 2:
                return rows[1][0].strip()
    except Exception:
        pass
    return None


def create_port_id(pc_id: str, chain: str) -> str:
    """Generate unique PORT_ID from PC_ID and chain."""
    combined = f"{pc_id}_{chain}"
    return "PORT_" + hashlib.md5(combined.encode()).hexdigest()[:HASH_LEN]


# =========================
# SECTION PARSING
# =========================

def split_into_port_sections(content: str) -> dict[int, str]:
    """
    Split content into sections by USB Port headers.

    Returns dict mapping port_number -> section_text (until next port or EOF).
    """
    pattern = re.compile(r'={10,}\s*USB\s+Port(\d+)\s*={10,}', re.IGNORECASE)

    matches = list(pattern.finditer(content))
    sections = {}

    for i, match in enumerate(matches):
        port_num = int(match.group(1))
        start = match.end()

        # Section ends at next port header or end of content
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)

        sections[port_num] = content[start:end]

    return sections


def extract_value(section: str, key: str) -> Optional[str]:
    """Extract value for a key from section using line-by-line search."""
    pattern = re.compile(rf'{re.escape(key)}\s*:\s*(.+?)(?:\n|$)', re.IGNORECASE)
    match = pattern.search(section)
    if match:
        return match.group(1).strip()
    return None


def extract_yes_no(section: str, key: str) -> bool:
    """Extract yes/no boolean value for a key."""
    value = extract_value(section, key)
    if value:
        return value.lower() in ('yes', 'true', '1')
    return False


def extract_connection_status(section: str) -> tuple[bool, str]:
    """
    Extract connection status.

    Returns (is_connected, raw_status_text).
    """
    value = extract_value(section, "Connection Status")
    if value:
        # Format: "0x01 (Device is connected)" or "0x00 (No device is connected)"
        is_connected = "0x01" in value or "Device is connected" in value
        return (is_connected, value)
    return (False, "")


def find_device_name(section: str) -> Optional[str]:
    """
    Find the best device name from section.

    Priority: Product String > BusReported Device Desc > Friendly Name > Device Description
    """
    # Try Product String first (quoted)
    match = re.search(r'Product\s+String\s*:\s*"([^"]+)"', section, re.IGNORECASE)
    if match and match.group(1).strip() != "---":
        return match.group(1).strip()

    # Try BusReported Device Desc
    value = extract_value(section, "BusReported Device Desc")
    if value and value != "---":
        return value

    # Try Friendly Name
    value = extract_value(section, "Friendly Name")
    if value and value != "---":
        return value

    # Try Device Description
    value = extract_value(section, "Device Description")
    if value and value != "---":
        return value

    return None


def has_internal_container(section: str) -> bool:
    """Check if device has internal container ID (built-in device)."""
    return "INTERNALLY_CONNECTED" in section.upper()


def get_companion_chain(section: str) -> Optional[str]:
    """Extract companion port chain if exists."""
    match = re.search(r'->\s*CompanionPortChain\s*:\s*([\d\-]+)', section, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


# =========================
# PORT PARSING
# =========================

def parse_port_section(port_number: int, section: str) -> USBPort:
    """Parse a port section into USBPort dataclass."""
    connected, _ = extract_connection_status(section)
    chain = extract_value(section, "Port Chain") or f"1-{port_number}"
    user_connectable = extract_yes_no(section, "IsUserConnectable")
    is_type_c = extract_yes_no(section, "PortConnectorIsTypeC")
    companion_chain = get_companion_chain(section)

    device_name = None
    is_internal = False

    if connected:
        device_name = find_device_name(section)
        is_internal = has_internal_container(section)

    return USBPort(
        port_number=port_number,
        chain=chain,
        connected=connected,
        user_connectable=user_connectable,
        is_type_c=is_type_c,
        companion_chain=companion_chain,
        device_name=device_name,
        is_internal=is_internal
    )


# =========================
# FILTERING
# =========================

def chain_to_tuple(chain: str) -> tuple[int, ...]:
    """Convert chain string to tuple for comparison (e.g., '1-13' -> (1, 13))."""
    try:
        return tuple(int(x) for x in chain.split('-'))
    except ValueError:
        return (999, 999)


def filter_ports(ports: list[USBPort]) -> list[USBPort]:
    """
    Filter ports according to rules:

    Include:
    - External ports (user_connectable=yes) - both empty and with devices
    - Both USB 2.0 and USB 3.0 logical ports shown separately

    Exclude:
    - Internal devices (webcam, bluetooth)
    - Internal empty ports
    """
    filtered = []
    for port in ports:
        # Skip internal devices
        if port.connected and port.is_internal:
            continue

        # Skip empty internal ports
        if not port.connected and not port.user_connectable:
            continue

        filtered.append(port)

    return filtered


# =========================
# OUTPUT
# =========================

def port_to_csv_row(port: USBPort, org_id: str, pc_id: str) -> list[str]:
    """Convert USBPort to CSV row."""
    port_id = create_port_id(pc_id, port.chain)

    if port.connected:
        status = "Secured"
        name = port.device_name or f"USB Device at {port.chain}"
    else:
        status = "Free"
        name = "Empty USB Port"

    return [org_id, pc_id, port_id, port.chain, status, name]


def write_csv(ports: list[USBPort], org_id: str, pc_id: str) -> None:
    """Write filtered ports to CSV file."""
    path = os.path.join(SCRIPT_DIR, OUTPUT_FILE)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)

        for port in ports:
            row = port_to_csv_row(port, org_id, pc_id)
            writer.writerow(row)


# =========================
# MAIN
# =========================

def parse_usb_report() -> list[USBPort]:
    """Parse USB report and return list of ports."""
    path = os.path.join(SCRIPT_DIR, REPORT_FILE)

    # Read and normalize content
    content = read_file_with_bom_detection(path)
    content = normalize_wide_spacing(content)

    # Split into sections and parse
    sections = split_into_port_sections(content)
    ports = [parse_port_section(num, section) for num, section in sections.items()]

    # Sort by chain for consistent output
    ports.sort(key=lambda p: chain_to_tuple(p.chain))

    return ports


def main():
    """Main entry point."""
    org_id = read_org_id()
    pc_id = read_pc_id()

    if not org_id:
        print("Error: ORG_ID not found in A_org_id.csv")
        return

    if not pc_id:
        print("Error: PC_ID not found in CAA_get_pc_id.csv")
        return

    # Parse and filter ports
    all_ports = parse_usb_report()
    filtered_ports = filter_ports(all_ports)

    if not filtered_ports:
        print("Warning: No external ports found")

    # Write output
    write_csv(filtered_ports, org_id, pc_id)

    # Summary
    connected = sum(1 for p in filtered_ports if p.connected)
    empty = len(filtered_ports) - connected
    print(f"Success: {len(filtered_ports)} ports exported to {OUTPUT_FILE}")
    print(f"  - Secured (with device): {connected}")
    print(f"  - Free (empty): {empty}")


if __name__ == "__main__":
    main()
