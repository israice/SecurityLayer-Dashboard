import shutil
from pathlib import Path

# Directory where this script is located
SCRIPT_DIR = Path(__file__).parent

# Paths
source_file = SCRIPT_DIR / "CCA_final_ports_list.csv"
destination_file = SCRIPT_DIR / "CDA_server_temp.csv"

# Copy file
shutil.copyfile(str(source_file), str(destination_file))
print(f"[OK] Admin Dashboard updated...\n")


