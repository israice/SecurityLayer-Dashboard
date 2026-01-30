"""USB Port Diagnostic - collects extended port information for analysis."""

import ctypes, os, re, winreg
from ctypes import wintypes, Structure, Union, POINTER, byref, sizeof, c_ulong, c_ushort, c_ubyte, c_void_p, c_int, c_wchar

# Windows constants
GENERIC_READ, FILE_SHARE_RW, OPEN_EXISTING = 0x80000000, 0x03, 3
DIGCF_PRESENT_DEVICEINTERFACE = 0x12
IOCTL_USB_GET_NODE_INFORMATION = 0x220408
IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX = 0x220448
IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES = 0x220458

# Port connector types (from usbioctl.h)
CONNECTOR_TYPES = {
    0: "TypeA",
    1: "TypeMiniAB",
    2: "TypeExpressCard",
    3: "TypeProprietaryCharger",
    4: "TypeProprietaryDocking",
    5: "TypeC_USB2",
    6: "TypeC_USB2_SS",
    7: "TypeC_SS",
    8: "TypeC_SS_DirectMode",
}

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

class USB_PORT_CONNECTOR_PROPERTIES(Structure):
    _pack_ = 1
    _fields_ = [
        ("ConnectionIndex", c_ulong),
        ("ActualLength", c_ulong),
        ("UsbPortProperties", c_ulong),  # bit flags
        ("CompanionIndex", c_ushort),
        ("CompanionPortNumber", c_ushort),
        ("CompanionHubSymbolicLinkName", c_wchar * 256),
    ]

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

def get_port_connector_props(handle, port):
    """Get USB_PORT_CONNECTOR_PROPERTIES for a port."""
    props = USB_PORT_CONNECTOR_PROPERTIES()
    props.ConnectionIndex = port
    ret = wintypes.DWORD()
    if DeviceIoControl(handle, IOCTL_USB_GET_PORT_CONNECTOR_PROPERTIES, byref(props), sizeof(props), byref(props), sizeof(props), byref(ret), None):
        return props
    return None

def parse_port_properties(flags):
    """Parse UsbPortProperties bit flags."""
    result = []
    if flags & 0x01: result.append("IsUserConnectable")
    if flags & 0x02: result.append("IsDebugCapable")
    if flags & 0x04: result.append("HasMiniPortBDevice")
    if flags & 0x08: result.append("IsOnOTG")
    # Connector type is in bits 4-7
    connector_type = (flags >> 4) & 0x0F
    result.append(f"ConnectorType={CONNECTOR_TYPES.get(connector_type, f'Unknown({connector_type})')}")
    return result

def get_registry_location_info(hub_path):
    """Try to get LocationPaths from registry for hub."""
    # Extract VID/PID from hub path
    # Path looks like: \\?\usb#vid_8087&pid_0033#5&21389cc8&0&14#{...}
    match = re.search(r'usb#vid_([0-9a-f]+)&pid_([0-9a-f]+)#([^#]+)#', hub_path, re.I)
    if not match:
        return None

    vid, pid, serial = match.groups()
    device_id = f"VID_{vid.upper()}&PID_{pid.upper()}"

    try:
        usb_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Enum\USB")
        try:
            device_key = winreg.OpenKey(usb_key, device_id)
            try:
                instance_key = winreg.OpenKey(device_key, serial)
                try:
                    params_key = winreg.OpenKey(instance_key, "Device Parameters")
                    location_paths, _ = winreg.QueryValueEx(params_key, "LocationPaths")
                    winreg.CloseKey(params_key)
                    return location_paths
                except OSError:
                    pass
                finally:
                    winreg.CloseKey(instance_key)
            except OSError:
                pass
            finally:
                winreg.CloseKey(device_key)
        except OSError:
            pass
        finally:
            winreg.CloseKey(usb_key)
    except OSError:
        pass
    return None

def main():
    print("=" * 80)
    print("USB PORT DIAGNOSTIC")
    print("=" * 80)

    hub_paths = get_hub_paths()
    print(f"\nFound {len(hub_paths)} USB hub(s)\n")

    seen, hub_idx = set(), 0

    for hub_path in hub_paths:
        if (pl := hub_path.lower()) in seen: continue
        seen.add(pl)

        handle = CreateFileW(hub_path, GENERIC_READ, FILE_SHARE_RW, None, OPEN_EXISTING, 0, None)
        if handle in (-1, 0): continue

        hub_idx += 1
        print(f"\n{'='*80}")
        print(f"HUB {hub_idx}: {hub_path[:80]}...")

        # Get hub location info
        location = get_registry_location_info(hub_path)
        if location:
            print(f"  LocationPaths: {location}")

        node = USB_NODE_INFORMATION()
        ret = wintypes.DWORD()

        if DeviceIoControl(handle, IOCTL_USB_GET_NODE_INFORMATION, byref(node), sizeof(node), byref(node), sizeof(node), byref(ret), None):
            port_count = node.u.HubInformation.HubDescriptor.bNumberOfPorts
            print(f"  Ports: {port_count}")
            print()

            for pn in range(1, port_count + 1):
                chain = f"{hub_idx}-{pn}"

                # Get connection info
                conn = USB_CONN_INFO_EX()
                conn.ConnectionIndex = pn
                if not DeviceIoControl(handle, IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX, byref(conn), sizeof(conn), byref(conn), sizeof(conn), byref(ret), None):
                    continue

                connected = conn.ConnectionStatus == 1
                is_hub = bool(conn.DeviceIsHub) if connected else False

                # Get connector properties
                props = get_port_connector_props(handle, pn)

                # Print port info
                status = "CONNECTED" if connected else "empty"
                if is_hub:
                    status = "HUB"

                print(f"  PORT {chain:6} | {status:10}", end="")

                if props:
                    flags = props.UsbPortProperties
                    parsed = parse_port_properties(flags)
                    companion = props.CompanionPortNumber

                    print(f" | Flags=0x{flags:04X} ({', '.join(parsed)})", end="")
                    if companion:
                        print(f" | Companion={props.CompanionIndex}-{companion}", end="")

                if connected and not is_hub:
                    vid = conn.DeviceDescriptor.idVendor
                    pid = conn.DeviceDescriptor.idProduct
                    print(f" | VID:PID={vid:04X}:{pid:04X}", end="")

                print()

        CloseHandle(handle)

    print(f"\n{'='*80}")
    print("END OF DIAGNOSTIC")
    print("=" * 80)

if __name__ == "__main__":
    main()
