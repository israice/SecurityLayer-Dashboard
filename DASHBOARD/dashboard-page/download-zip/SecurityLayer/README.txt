━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 ██████╗ ███████╗ ██████╗██╗   ██╗██████╗ ██╗████████╗██╗   ██╗
██╔════╝ ██╔════╝██╔════╝██║   ██║██╔══██╗██║╚══██╔══╝╚██╗ ██╔╝
╚█████╗  █████╗  ██║     ██║   ██║██████╔╝██║   ██║    ╚████╔╝
 ╚═══██╗ ██╔══╝  ██║     ██║   ██║██╔══██╗██║   ██║     ╚██╔╝
██████╔╝ ███████╗╚██████╗╚██████╔╝██║  ██║██║   ██║      ██║
╚═════╝  ╚══════╝ ╚═════╝ ╚═════╝ ╚═╝  ╚═╝╚═╝   ╚═╝      ╚═╝

██╗      █████╗ ██╗   ██╗███████╗██████╗
██║     ██╔══██╗╚██╗ ██╔╝██╔════╝██╔══██╗
██║     ███████║ ╚████╔╝ █████╗  ██████╔╝
██║     ██╔══██║  ╚██╔╝  ██╔══╝  ██╔══██╗
███████╗██║  ██║   ██║   ███████╗██║  ██║
╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Security Layer - USB Monitoring System v0.0.1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

IMPORTANT
---------
This software uses WMI, System Hooks, and a third-party tool (UsbTreeView) to monitor USB activity.
These behaviors may trigger ANTIVIRUS ALERTS (False Positives).

Please configure EXCLUSIONS before installation to ensure stable operation.

INSTALLATION
------------
1. Edit "SecurityLayer\usbSecurity\A_org_id.csv" and enter your Organization ID.
2. Run "start.bat" as Administrator.
   (This will install dependencies, register startup tasks, and start the monitor).

UNINSTALLATION
--------------
1. Run "stop.bat" as Administrator.

REQUIRED ANTIVIRUS EXCLUSIONS
-----------------------------
The following paths SHOULD be excluded from Antivirus scanning.

1. Application Folder (Recursive):
   Path: C:\SecurityLayer\usbSecurity\

2. Specific Processes (If folder exclusion is insufficient):
   - C:\SecurityLayer\usbSecurity\python\python.exe
   - C:\SecurityLayer\usbSecurity\python\pythonw.exe
   - C:\SecurityLayer\usbSecurity\CBA_UsbTreeView.exe
   - C:\SecurityLayer\usbSecurity\BA_usb_watcher.py

CONFIGURATION EXAMPLES
----------------------

[Windows Defender]
Add-MpPreference -ExclusionPath "C:\SecurityLayer\usbSecurity"

[Kaspersky Endpoint Security]
Trusted Zone > Exclusions > Add: "C:\SecurityLayer\usbSecurity\*"

[ESET Endpoint Security]
Setup > Computer protection > Exclusions > Edit > Add: "C:\SecurityLayer\usbSecurity"

SUPPORT
-------
If files are quarantined:
1. Restore the file from quarantine.
2. Add the exclusion.
3. Re-run "start.bat" to repair.
