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
        "PORT_STATUS", "PORT_NAME"
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
    raw_data: dict

    @staticmethod
    def _extract(pattern: str, text: str) -> str:
        """Extract text using regex pattern"""
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else ""

    @staticmethod
    def _is_valid(value: str) -> bool:
        """Check if value is valid (not empty, not '---')"""
        return bool(value and value.strip() not in ("", "---"))

    @staticmethod
    def from_text_block(summary_block: str, full_block: str) -> 'DeviceInfo':
        """Extract device information from text blocks with fallback chain"""
        patterns = {
            'manufacturer': (r'Manufacturer\s+String\s*:\s*"(.+?)"', summary_block),
            'product': (r'Product\s+String\s*:\s*"(.+?)"', summary_block),
            'first_seen': (r'First\s+Install\s+Date\s*:\s*(.+?)(?:\s|$)', full_block),
            'last_seen': (r'Last\s+Arrival\s+Date\s*:\s*(.+?)(?:\s|$)', full_block),
            'bus_reported_desc': (r'BusReported\s+Device\s+Desc\s*:\s*(.+?)(?:\n|$)', full_block),
            'device_description': (r'Device\s+Description\s*:\s*(.+?)(?:\n|$)', full_block),
            'friendly_name': (r'Friendly\s+Name\s*:\s*(.+?)(?:\n|$)', full_block),
            'vendor_id_desc': (r'Vendor\s+ID\s*:\s*0x[0-9A-F]+\s*\((.+?)\)', summary_block),
            'manufacturer_info': (r'Manufacturer\s+Info\s*:\s*(.+?)(?:\n|$)', full_block)
        }

        data = {k: DeviceInfo._extract(p, t) for k, (p, t) in patterns.items()}

        # Fallback logic for best product
        data['best_product'] = next((data[k] for k in ['product', 'bus_reported_desc', 'friendly_name', 'device_description']
                                    if DeviceInfo._is_valid(data.get(k, ''))), '')

        # Fallback logic for best manufacturer
        data['best_manufacturer'] = next((data[k] for k in ['manufacturer', 'vendor_id_desc', 'manufacturer_info']
                                         if DeviceInfo._is_valid(data.get(k, '')) and
                                            data.get(k, '') not in Config.GENERIC_MANUFACTURERS), '')

        return DeviceInfo(raw_data=data)

    def __getattr__(self, name: str) -> str:
        """Dynamic attribute access for raw_data fields"""
        return self.raw_data.get(name, '')


class USBPort:
    """Represents a USB port with its properties and connected device"""
    _PATTERNS = {
        'user_connectable': r'IsUserConnectable\s*:\s*(\w+)',
        'device_id': r'Device ID\s*:\s*(.+)',
        'usb2': r'Usb200\s*:\s*1\s*\(\s*yes',
        'usb3': r'Usb300\s*:\s*1\s*\(\s*yes',
        'companion': r'CompanionPortChain\s*:\s*\d+-\d+'
    }

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
        return f"Hub {parts[0]} Port {'/'.join(parts[1:])}" if len(parts) >= 2 else f"Port {self.chain}"

    @property
    def is_user_connectable(self) -> bool:
        """Check if port is physically accessible"""
        match = re.search(self._PATTERNS['user_connectable'], self.block)
        return match.group(1).lower() == "yes" if match else True

    @property
    def usb_type(self) -> str:
        """Extract USB type from SupportedUsbProtocols"""
        usb2 = bool(re.search(self._PATTERNS['usb2'], self.block, re.IGNORECASE))
        usb3 = bool(re.search(self._PATTERNS['usb3'], self.block, re.IGNORECASE))
        companion = bool(re.search(self._PATTERNS['companion'], self.block))
        if (usb3 or companion) and usb2: return "USB 2.0/3.0"
        if usb3 or companion: return "USB 3.0"
        return "USB 2.0" if usb2 else "USB 1.1"

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
    def create(chain: str, code: str = "00", status: str = "No device is connected",
              block: str = "", summary: str = "") -> 'USBPort':
        """Create a USB port (empty or occupied based on connection code)"""
        port = USBPort(chain, code, status, block, summary or block)
        if code != "00" and "No device" not in status:
            match = re.search(USBPort._PATTERNS['device_id'], block)
            port._device_id = match.group(1).strip() if match else f"UNKNOWN_{chain}"
            port.device_info = DeviceInfo.from_text_block(summary or block, block)
            name = port.device_info.best_product
            if name in Config.GENERIC_PRODUCTS and port.device_info.best_manufacturer:
                if port.device_info.best_manufacturer not in Config.GENERIC_MANUFACTURERS:
                    name = f"{port.device_info.best_manufacturer} {name}"
            port._device_name = name or port.device_info.best_manufacturer or ""
        return port

    def to_csv_row(self, org_id: str, pc_id: str) -> list:
        """Generate CSV row data"""
        if self.is_occupied and self.device_info:
            return [org_id, pc_id, self.port_id, self.formatted_location,
                   "Secured", self.device_name]
        return [org_id, pc_id, self.port_id, self.formatted_location, "Free", ""]


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
            summary_match = re.search(r'={20,}\s*Summary\s*={20,}(.+?)(?:={20,}|$)', block, re.DOTALL)
            summary_block = summary_match.group(1) if summary_match else block
            port = USBPort.create(chain, code, status_text, block, summary_block)
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
        if not self.org_id or not self.pc_id:
            print("Error: ORG_ID or PC_ID not found")
            return

        print("Parsing USB report...")
        ports = self.parse()

        if ports:
            print(f"Found {len(ports)} external ports")
            self.write_csv(ports)
        else:
            print("Error: No ports found")


if __name__ == "__main__":
    USBReportParser().run()
