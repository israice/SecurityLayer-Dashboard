import requests
import os
import sys

# ============== SETTINGS ==============
SERVER_URL = 'https://sec.weforks.org'
LOCAL_URL = 'http://localhost:5000'
ROUTE = '/update-dashboard'
CSV_FILE = 'CCA_final_ports_list.csv'
ENCODING = 'utf-8'
# ======================================

script_dir = os.path.dirname(os.path.abspath(__file__))

local = '--local' in sys.argv
BASE_URL = LOCAL_URL if local else SERVER_URL
API_URL = f"{BASE_URL}{ROUTE}"

csv_path = os.path.join(script_dir, CSV_FILE)

with open(csv_path, 'r', encoding=ENCODING) as f:
    csv_content = f.read()

try:
    response = requests.post(API_URL, data=csv_content)
    if response.status_code == 200:
        print(f'[OK] Admin Dashboard updated... ({API_URL})')
    else:
        print(f'Error: {response.status_code}')
except requests.exceptions.ConnectionError:
    print(f'Error: Server not available at {API_URL}')
