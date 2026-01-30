"""USB Port Enumeration to CSV via Direct IOCTL. No admin rights or external tools required."""

import ctypes, csv, hashlib, os, winreg
from ctypes import wintypes, Structure, Union, POINTER, byref, sizeof, c_ulong, c_ushort, c_ubyte, c_void_p, c_int, c_wchar

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ORG_ID_FILE, OUTPUT_FILE = "A_org_id.csv", "CCA_final_ports_list.csv"
CSV_HEADERS = ["ORG_ID", "PC_ID", "PORT_ID", "PORT_MAP", "PORT_STATUS", "PORT_NAME"]
HASH_LEN = 8

# Windows constants
GENERIC_READ, FILE_SHARE_RW, OPEN_EXISTING = 0x80000000, 0x03, 3
DIGCF_PRESENT_DEVICEINTERFACE = 0x12
IOCTL_USB_GET_NODE_INFORMATION = 0x220408
IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX = 0x220448
IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION = 0x220410
IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES = 0x220458
EXTERNAL_PORT_FLAGS = 0x0001

# ctypes structures
class GUID(Structure):
    _fields_ = [("Data1", c_ulong), ("Data2", c_ushort), ("Data3", c_ushort), ("Data4", c_ubyte * 8)]

GUID_USB_HUB = GUID(0xf18a0e88, 0xc30c, 0x11d0, (c_ubyte * 8)(0x88, 0x15, 0x00, 0xa0, 0xc9, 0x06, 0xbe, 0xd8))

class SP_DEVICE_INTERFACE_DATA(Structure):
    _fields_ = [("cbSize", c_ulong), ("InterfaceClassGuid", GUID), ("Flags", c_ulong), ("Reserved", POINTER(c_ulong))]

class SP_DEVICE_INTERFACE_DETAIL_DATA_W(Structure):
    _fields_ = [("cbSize", c_ulong), ("DevicePath", c_wchar * 1024)]

class USB_HUB_DESCRIPTOR(Structure):
    _fields_ = [("bDescriptorLength", c_ubyte), ("bDescriptorType", c_ubyte), ("bNumberOfPorts", c_ubyte),
                ("wHubCharacteristics", c_ushort), ("bPowerOnToPowerGood", c_ubyte), ("bHubControlCurrent", c_ubyte),
                ("bRemoveAndPowerMask", c_ubyte * 64)]

class USB_HUB_INFO(Structure):
    _fields_ = [("HubDescriptor", USB_HUB_DESCRIPTOR), ("HubIsBusPowered", c_ubyte)]

class USB_NODE_INFO_UNION(Union):
    _fields_ = [("HubInformation", USB_HUB_INFO)]

class USB_NODE_INFORMATION(Structure):
    _fields_ = [("NodeType", c_int), ("u", USB_NODE_INFO_UNION)]

class USB_DEVICE_DESCRIPTOR(Structure):
    _pack_ = 1
    _fields_ = [("bLength", c_ubyte), ("bDescriptorType", c_ubyte), ("bcdUSB", c_ushort), ("bDeviceClass", c_ubyte),
                ("bDeviceSubClass", c_ubyte), ("bDeviceProtocol", c_ubyte), ("bMaxPacketSize0", c_ubyte),
                ("idVendor", c_ushort), ("idProduct", c_ushort), ("bcdDevice", c_ushort), ("iManufacturer", c_ubyte),
                ("iProduct", c_ubyte), ("iSerialNumber", c_ubyte), ("bNumConfigurations", c_ubyte)]

class USB_CONN_INFO_EX(Structure):
    _pack_ = 1
    _fields_ = [("ConnectionIndex", c_ulong), ("DeviceDescriptor", USB_DEVICE_DESCRIPTOR),
                ("CurrentConfigurationValue", c_ubyte), ("Speed", c_ubyte), ("DeviceIsHub", c_ubyte),
                ("DeviceAddress", c_ushort), ("NumberOfOpenPipes", c_ulong), ("ConnectionStatus", c_int)]

class USB_SETUP_PACKET(Structure):
    _pack_ = 1
    _fields_ = [("bmRequest", c_ubyte), ("bRequest", c_ubyte), ("wValue", c_ushort), ("wIndex", c_ushort), ("wLength", c_ushort)]

class USB_DESCRIPTOR_REQUEST(Structure):
    _pack_ = 1
    _fields_ = [("ConnectionIndex", c_ulong), ("SetupPacket", USB_SETUP_PACKET), ("Data", c_ubyte * 256)]

class USB_PORT_CONNECTOR_PROPERTIES(Structure):
    _pack_ = 1
    _fields_ = [("ConnectionIndex", c_ulong), ("ActualLength", c_ulong), ("UsbPortProperties", c_ulong),
                ("CompanionIndex", c_ushort), ("CompanionPortNumber", c_ushort), ("CompanionHubSymbolicLinkName", c_wchar * 256)]

# API setup
kernel32, setupapi = ctypes.windll.kernel32, ctypes.windll.setupapi
for fn, args, res in [
    (setupapi.SetupDiGetClassDevsW, [POINTER(GUID), ctypes.c_wchar_p, wintypes.HWND, c_ulong], wintypes.HANDLE),
    (setupapi.SetupDiEnumDeviceInterfaces, [wintypes.HANDLE, c_void_p, POINTER(GUID), c_ulong, POINTER(SP_DEVICE_INTERFACE_DATA)], wintypes.BOOL),
    (setupapi.SetupDiGetDeviceInterfaceDetailW, [wintypes.HANDLE, POINTER(SP_DEVICE_INTERFACE_DATA), POINTER(SP_DEVICE_INTERFACE_DETAIL_DATA_W), c_ulong, POINTER(c_ulong), c_void_p], wintypes.BOOL),
    (setupapi.SetupDiDestroyDeviceInfoList, [wintypes.HANDLE], wintypes.BOOL),
    (kernel32.CreateFileW, [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE], wintypes.HANDLE),
    (kernel32.DeviceIoControl, [wintypes.HANDLE, wintypes.DWORD, c_void_p, wintypes.DWORD, c_void_p, wintypes.DWORD, POINTER(wintypes.DWORD), c_void_p], wintypes.BOOL),
]: fn.argtypes, fn.restype = args, res

CreateFileW, DeviceIoControl, CloseHandle = kernel32.CreateFileW, kernel32.DeviceIoControl, kernel32.CloseHandle
SetupDiGetClassDevsW, SetupDiEnumDeviceInterfaces = setupapi.SetupDiGetClassDevsW, setupapi.SetupDiEnumDeviceInterfaces
SetupDiGetDeviceInterfaceDetailW, SetupDiDestroyDeviceInfoList = setupapi.SetupDiGetDeviceInterfaceDetailW, setupapi.SetupDiDestroyDeviceInfoList
GetLastError = kernel32.GetLastError

def get_hub_paths():
    paths = []
    dev_info = SetupDiGetClassDevsW(byref(GUID_USB_HUB), None, None, DIGCF_PRESENT_DEVICEINTERFACE)
    if dev_info == -1: return paths
    idx = 0
    while True:
        iface = SP_DEVICE_INTERFACE_DATA(); iface.cbSize = sizeof(SP_DEVICE_INTERFACE_DATA)
        if not SetupDiEnumDeviceInterfaces(dev_info, None, byref(GUID_USB_HUB), idx, byref(iface)):
            if GetLastError() == 259: break
            idx += 1; continue
        detail = SP_DEVICE_INTERFACE_DETAIL_DATA_W()
        detail.cbSize = 8 if sizeof(c_void_p) == 8 else 6
        if SetupDiGetDeviceInterfaceDetailW(dev_info, byref(iface), byref(detail), sizeof(detail), None, None):
            paths.append(detail.DevicePath)
        idx += 1
    SetupDiDestroyDeviceInfoList(dev_info)
    return paths

def get_string_descriptor(handle, port, idx):
    if idx == 0: return ""
    req = USB_DESCRIPTOR_REQUEST()
    req.ConnectionIndex, req.SetupPacket.bmRequest, req.SetupPacket.bRequest = port, 0x80, 0x06
    req.SetupPacket.wValue, req.SetupPacket.wIndex, req.SetupPacket.wLength = (3 << 8) | idx, 0x0409, 255
    ret = wintypes.DWORD()
    if DeviceIoControl(handle, IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION, byref(req), sizeof(req), byref(req), sizeof(req), byref(ret), None):
        if ret.value > sizeof(USB_SETUP_PACKET) + 6 and (length := req.Data[0]) > 2:
            try: return bytes(req.Data[2:length]).decode('utf-16-le').strip('\x00')
            except: pass
    return ""

def get_port_props(handle, port):
    """Get port properties (flags, companion_port)."""
    props = USB_PORT_CONNECTOR_PROPERTIES()
    props.ConnectionIndex = port
    ret = wintypes.DWORD()
    if DeviceIoControl(handle, IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES, byref(props), sizeof(props), byref(props), sizeof(props), byref(ret), None):
        return (props.UsbPortProperties, props.CompanionPortNumber)
    return None

def is_real_port(port_number, flags, companion_port):
    """
    Check if port is a real external USB2 port.

    Rules:
    1. Flags must be exactly 0x0001 (IsUserConnectable only)
    2. Either has companion OR port number < 10
    3. NOT a USB3 companion (companion points to lower port number = USB3 version of USB2 port)
    """
    if flags != EXTERNAL_PORT_FLAGS:
        return False
    # Skip USB3 companion ports (they reference USB2 port with LOWER number)
    if companion_port > 0 and companion_port < port_number:
        return False
    return companion_port > 0 or port_number < 10

def enumerate_ports():
    ports, seen, hub_idx = [], set(), 0
    for path in get_hub_paths():
        if (pl := path.lower()) in seen: continue
        seen.add(pl)
        handle = CreateFileW(path, GENERIC_READ, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
        if handle in (-1, 0): continue
        hub_idx += 1
        node = USB_NODE_INFORMATION(); ret = wintypes.DWORD()
        if DeviceIoControl(handle, IOCTL_USB_GET_NODE_INFORMATION, byref(node), sizeof(node), byref(node), sizeof(node), byref(ret), None):
            for pn in range(1, node.u.HubInformation.HubDescriptor.bNumberOfPorts + 1):
                props = get_port_props(handle, pn)
                if props is None:
                    continue
                flags, companion = props
                if not is_real_port(pn, flags, companion):
                    continue
                conn = USB_CONN_INFO_EX(); conn.ConnectionIndex = pn
                if not DeviceIoControl(handle, IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX, byref(conn), sizeof(conn), byref(conn), sizeof(conn), byref(ret), None):
                    continue
                connected = conn.ConnectionStatus == 1
                is_hub = bool(conn.DeviceIsHub) if connected else False
                if is_hub: continue
                name = ""
                if connected:
                    vid = conn.DeviceDescriptor.idVendor
                    if conn.DeviceDescriptor.iProduct:
                        name = get_string_descriptor(handle, pn, conn.DeviceDescriptor.iProduct)
                    if not name:
                        name = f"USB Device {vid:04X}:{conn.DeviceDescriptor.idProduct:04X}"
                ports.append({"hub": hub_idx, "port": pn, "chain": f"{hub_idx}-{pn}", "connected": connected, "name": name})
        CloseHandle(handle)
    return ports

def read_org_id():
    try:
        with open(os.path.join(SCRIPT_DIR, ORG_ID_FILE), "r", encoding="utf-8") as f:
            rows = list(csv.reader(f))
            return rows[1][0].strip() if len(rows) >= 2 else None
    except: return None

def get_pc_id():
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
        guid, _ = winreg.QueryValueEx(key, "MachineGuid"); winreg.CloseKey(key)
        return f"PC_{hashlib.sha256(guid.encode()).hexdigest()[:HASH_LEN]}"
    except: return None

def main():
    if not (org_id := read_org_id()): print(f"Error: ORG_ID not found in {ORG_ID_FILE}"); return
    if not (pc_id := get_pc_id()): print("Error: Could not get PC_ID"); return
    if not (ports := enumerate_ports()): print("Error: No USB ports found"); return

    path = os.path.join(SCRIPT_DIR, OUTPUT_FILE)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(CSV_HEADERS)
        for p in ports:
            port_id = "PORT_" + hashlib.md5(f"{pc_id}_{p['chain']}".encode()).hexdigest()[:HASH_LEN]
            status = "Secured" if p["connected"] else "Free"
            name = p["name"] or "Empty USB Port"
            w.writerow([org_id, pc_id, port_id, p["chain"], status, name])

    connected = sum(1 for p in ports if p["connected"])
    print(f"Success: {len(ports)} ports exported to {OUTPUT_FILE}")
    print(f"  - Secured (with device): {connected}")
    print(f"  - Free (empty): {len(ports) - connected}")

if __name__ == "__main__":
    main()
