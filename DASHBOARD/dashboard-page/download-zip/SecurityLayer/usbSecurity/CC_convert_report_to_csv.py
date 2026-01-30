import os
import csv
import hashlib
import re
from dataclasses import dataclass
from typing import Optional


class Config:
    """Centralized configuration for USB port reporting"""
    ORG_ID_FILE = "A_org_id.csv"
    PC_ID_FILE = "CAA_get_pc_id.csv"
    REPORT_FILE = "CBB_USB_Ports_Report.txt"
    OUTPUT_FILE = "CCA_final_ports_list.csv"

    CSV_HEADERS = [
        "ORG_ID", "PC_ID", "PORT_ID", "PORT_MAP",
        "PORT_STATUS", "PORT_NAME", "MANUFACTURER"
    ]

    HASH_LEN = 8
    LOOKAHEAD = 30000

    GENERIC_PRODUCTS = {"Mass Storage Device", "USB Mass Storage Device", "USB Composite Device",
                       "USB Device", "USB Hub", "Wireless Device", "Input Device", "Disk drive"}

    GENERIC_MANUFACTURERS = {
        "Generic", "Standard", "Compatible",
        "(Standard USB Host Controller)",
        "(Standard USB HUBs)",
        "WinUsb Device"
    }


@dataclass
class DeviceInfo:
    """Device information extracted from USB report"""
    # Primary fields
    manufacturer: str = ""
    product: str = ""
    first_seen: str = ""
    last_seen: str = ""

    # Fallback fields
    bus_reported_desc: str = ""
    device_description: str = ""
    friendly_name: str = ""
    vendor_id_desc: str = ""
    manufacturer_info: str = ""

    # Best values after fallback logic
    best_manufacturer: str = ""
    best_product: str = ""

    @staticmethod
    def from_text_block(summary_block: str, full_block: str) -> 'DeviceInfo':
        """Extract device information from text blocks with fallback chain"""
        def find(pattern: str, text: str = summary_block) -> str:
            match = re.search(pattern, text, re.IGNORECASE)
            return match.group(1).strip() if match else ""

        # Extract primary fields
        manufacturer = find(r'Manufacturer\s+String\s*:\s*"(.+?)"')
        product = find(r'Product\s+String\s*:\s*"(.+?)"')
        first_seen = find(r'First\s+Install\s+Date\s*:\s*(.+?)(?:\s|$)', full_block)
        last_seen = find(r'Last\s+Arrival\s+Date\s*:\s*(.+?)(?:\s|$)', full_block)

        # Extract fallback fields
        bus_reported_desc = find(r'BusReported\s+Device\s+Desc\s*:\s*(.+?)(?:\n|$)', full_block)
        device_description = find(r'Device\s+Description\s*:\s*(.+?)(?:\n|$)', full_block)
        friendly_name = find(r'Friendly\s+Name\s*:\s*(.+?)(?:\n|$)', full_block)
        manufacturer_info = find(r'Manufacturer\s+Info\s*:\s*(.+?)(?:\n|$)', full_block)

        # Extract Vendor ID description from parentheses
        vendor_id_desc = ""
        vendor_match = re.search(r'Vendor\s+ID\s*:\s*0x[0-9A-F]+\s*\((.+?)\)',
                                 summary_block, re.IGNORECASE)
        if vendor_match:
            vendor_id_desc = vendor_match.group(1).strip()

        # Apply fallback logic for product
        best_product = ""
        if DeviceInfo._is_valid_value(product):
            best_product = product
        elif DeviceInfo._is_valid_value(bus_reported_desc):
            best_product = bus_reported_desc
        elif DeviceInfo._is_valid_value(friendly_name):
            best_product = friendly_name
        elif DeviceInfo._is_valid_value(device_description):
            best_product = device_description

        # Apply fallback logic for manufacturer
        best_manufacturer = ""
        if DeviceInfo._is_valid_value(manufacturer):
            best_manufacturer = manufacturer
        elif DeviceInfo._is_valid_value(vendor_id_desc):
            best_manufacturer = vendor_id_desc
        elif DeviceInfo._is_valid_value(manufacturer_info) and \
             manufacturer_info not in Config.GENERIC_MANUFACTURERS:
            best_manufacturer = manufacturer_info

        return DeviceInfo(
            manufacturer=manufacturer,
            product=product,
            first_seen=first_seen,
            last_seen=last_seen,
            bus_reported_desc=bus_reported_desc,
            device_description=device_description,
            friendly_name=friendly_name,
            vendor_id_desc=vendor_id_desc,
            manufacturer_info=manufacturer_info,
            best_manufacturer=best_manufacturer,
            best_product=best_product
        )

    @staticmethod
    def _is_valid_value(value: str) -> bool:
        """Check if extracted value is valid (not empty, not '---')"""
        if not value or value.strip() == "":
            return False
        if value.strip() == "---":
            return False
        return True


class USBPort:
    """Represents a USB port with its properties and connected device"""

    def __init__(self, chain: str, connection_code: str, status_text: str,
                 block: str, summary_block: Optional[str] = None):
        self.chain = chain
        self.connection_code = connection_code
        self.status_text = status_text
        self.block = block
        self.summary_block = summary_block or block
        self.device_info: Optional[DeviceInfo] = None
        self._device_id = ""
        self._device_name = ""

    @property
    def port_id(self) -> str:
        """Generate hashed port ID"""
        return "PORT_" + hashlib.md5(self.device_id.encode()).hexdigest()[:Config.HASH_LEN]

    @property
    def formatted_location(self) -> str:
        """Convert chain like '1-2' to 'Hub 1 Port 2'"""
        parts = self.chain.split('-')
        if len(parts) == 2:
            return f"Hub {parts[0]} Port {parts[1]}"
        elif len(parts) >= 3:
            return f"Hub {parts[0]} Port {'/'.join(parts[1:])}"
        return f"Port {self.chain}"

    @property
    def is_user_connectable(self) -> bool:
        """Check if port is physically accessible"""
        match = re.search(r'IsUserConnectable\s*:\s*(\w+)', self.block)
        return match.group(1).strip().lower() == "yes" if match else True

    @property
    def usb_type(self) -> str:
        """Extract USB type from SupportedUsbProtocols"""
        usb2 = bool(re.search(r'Usb200\s*:\s*1\s*\(\s*yes', self.block, re.IGNORECASE))
        usb3 = bool(re.search(r'Usb300\s*:\s*1\s*\(\s*yes', self.block, re.IGNORECASE))
        has_companion = bool(re.search(r'CompanionPortChain\s*:\s*\d+-\d+', self.block))

        if (usb3 or has_companion) and usb2:
            return "USB 2.0/3.0"
        elif usb3 or has_companion:
            return "USB 3.0"
        elif usb2:
            return "USB 2.0"
        return "USB 1.1"

    @property
    def is_occupied(self) -> bool:
        """Check if port has a connected device"""
        return self.connection_code != "00" and "No device is connected" not in self.status_text

    @property
    def device_id(self) -> str:
        """Get or generate device ID"""
        return self._device_id or f"PORT_{self.chain.replace('-', '_')}_EMPTY"

    @property
    def device_name(self) -> str:
        """Get formatted device name"""
        return self._device_name

    @staticmethod
    def create_empty(chain: str, block: str) -> 'USBPort':
        """Create a free/empty port"""
        port = USBPort(chain, "00", "No device is connected", block)
        return port

    @staticmethod
    def create_occupied(chain: str, code: str, status: str, block: str, summary_block: str) -> 'USBPort':
        """Create an occupied port with device info"""
        port = USBPort(chain, code, status, block, summary_block)

        # Extract device ID
        device_id_match = re.search(r'Device ID\s*:\s*(.+)', block)
        port._device_id = device_id_match.group(1).strip() if device_id_match else f"UNKNOWN_{chain}"

        # Extract device info
        port.device_info = DeviceInfo.from_text_block(summary_block, block)

        # Extract device name using best available values
        name = port.device_info.best_product

        # Handle generic product names by prepending manufacturer
        if port.device_info.best_product in Config.GENERIC_PRODUCTS and \
           port.device_info.best_manufacturer not in Config.GENERIC_MANUFACTURERS:
            if port.device_info.best_manufacturer:
                name = f"{port.device_info.best_manufacturer} {port.device_info.best_product}"

        # If still empty, use manufacturer
        if not name:
            name = port.device_info.best_manufacturer or ""

        port._device_name = name
        return port

    def to_csv_row(self, org_id: str, pc_id: str) -> list:
        """Generate CSV row data"""
        if self.is_occupied and self.device_info:
            return [
                org_id, pc_id, self.port_id, self.formatted_location,
                "Secured", self.device_name, self.device_info.best_manufacturer
            ]
        else:
            return [
                org_id, pc_id, self.port_id, self.formatted_location,
                "Free", "", ""
            ]


class USBReportParser:
    """Parser for USB port reports with CSV generation"""

    def __init__(self):
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.org_id = self._read_csv_value(Config.ORG_ID_FILE)
        self.pc_id = self._read_csv_value(Config.PC_ID_FILE)

    def _read_csv_value(self, filename: str) -> Optional[str]:
        """Read single value from CSV file"""
        path = os.path.join(self.script_dir, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                rows = list(csv.reader(f))
                return rows[1][0].strip() if len(rows) >= 2 else None
        except:
            return None

    def parse(self) -> list[USBPort]:
        """Parse USB report file and return list of ports"""
        path = os.path.join(self.script_dir, Config.REPORT_FILE)
        with open(path, "r", encoding="utf-16-le") as f:
            content = f.read()

        pattern = re.compile(
            r'={20,}.*?USB Port\d+.*?={20,}.*?'
            r'Connection Status\s*:\s*0x(\d+)\s*\((.*?)\).*?'
            r'Port Chain\s*:\s*([\d\-\.]+)',
            re.DOTALL
        )

        ports = []
        for match in pattern.finditer(content):
            code, status_text, chain = match.groups()
            block = content[match.end():match.end() + Config.LOOKAHEAD]

            # Extract Summary block
            summary_match = re.search(r'={20,}\s*Summary\s*={20,}(.+?)(?:={20,}|$)', block, re.DOTALL)
            summary_block = summary_match.group(1) if summary_match else block

            # Create port based on connection status
            port = USBPort.create_occupied(chain, code, status_text, block, summary_block) \
                   if code != "00" and "No device is connected" not in status_text \
                   else USBPort.create_empty(chain, block)

            # Skip internal ports
            if port.is_user_connectable:
                ports.append(port)

        return ports

    def write_csv(self, ports: list[USBPort]):
        """Write ports to CSV file"""
        if not self.org_id or not self.pc_id:
            raise ValueError("ORG_ID and PC_ID must be set before writing CSV")

        path = os.path.join(self.script_dir, Config.OUTPUT_FILE)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(Config.CSV_HEADERS)
            for port in ports:
                writer.writerow(port.to_csv_row(self.org_id, self.pc_id))

        print(f"Enhanced CSV created: {Config.OUTPUT_FILE}")
        print(f"Total ports: {len(ports)}")

    def run(self):
        """Execute the full parsing and CSV generation process"""
        if not self.org_id:
            print(f"Error: ORG_ID not found in {Config.ORG_ID_FILE}")
            return

        if not self.pc_id:
            print(f"Error: PC_ID not found in {Config.PC_ID_FILE}")
            return

        print("Parsing USB report...")
        ports = self.parse()

        if not ports:
            print("Error: No ports found")
            return

        print(f"Found {len(ports)} external ports")
        self.write_csv(ports)


if __name__ == "__main__":
    USBReportParser().run()
