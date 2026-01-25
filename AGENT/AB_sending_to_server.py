import requests
import os
import yaml

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, '..', 'config.yaml')

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

BASE_URL = config['AGENT']['SERVER_URL'].rstrip('/')
ROUTE = config['ROUTES']['update_dashboard']
SERVER_URL = f"{BASE_URL}{ROUTE}"
CSV_FILE = config['AGENT']['CSV_FILE']
ENCODING = config['ENCODING']

csv_path = os.path.join(script_dir, CSV_FILE)

with open(csv_path, 'r', encoding=ENCODING) as f:
    csv_content = f.read()

try:
    response = requests.post(SERVER_URL, data=csv_content)
    if response.status_code == 200:
        print('CSV sent successfully')
    else:
        print(f'Error: {response.status_code}')
except requests.exceptions.ConnectionError:
    print(f'Error: Server not available at {SERVER_URL}')
