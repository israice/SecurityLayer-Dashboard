import requests
import os
import sys
import yaml

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.normpath(os.path.join(script_dir, '..', '..', '..', '..', '..', 'config.yaml'))

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

local = '--local' in sys.argv
if local:
    BASE_URL = config['AGENT']['LOCAL_URL'].rstrip('/')
else:
    BASE_URL = config['AGENT']['SERVER_URL'].rstrip('/')

ROUTE = config['ROUTES']['update_dashboard']
SERVER_URL = f"{BASE_URL}{ROUTE}"
CSV_FILE = 'CCA_final_ports_list.csv'
ENCODING = config['ENCODING']

csv_path = os.path.join(script_dir, CSV_FILE)

with open(csv_path, 'r', encoding=ENCODING) as f:
    csv_content = f.read()

try:
    response = requests.post(SERVER_URL, data=csv_content)
    if response.status_code == 200:
        print(f'[OK] Admin Dashboard updated... ({SERVER_URL})')
    else:
        print(f'Error: {response.status_code}')
except requests.exceptions.ConnectionError:
    print(f'Error: Server not available at {SERVER_URL}')
