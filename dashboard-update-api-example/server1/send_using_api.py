# ============== SETTINGS ==============
API_PROTOCOL = 'http'
API_HOST = 'localhost'
API_PORT = 5000
API_ENDPOINT = '/update-dashboard'
CSV_FILE = 'before.csv'
JSON_KEY = 'csv_content'
ENCODING = 'utf-8'
CONTENT_TYPE = 'application/json'
# ======================================

import requests
import os

csv_path = os.path.join(os.path.dirname(__file__), CSV_FILE)
API_URL = f'{API_PROTOCOL}://{API_HOST}:{API_PORT}{API_ENDPOINT}'


def send_csv():
    with open(csv_path, 'r', encoding=ENCODING) as f:
        csv_content = f.read()

    response = requests.post(
        API_URL,
        json={JSON_KEY: csv_content},
        headers={'Content-Type': CONTENT_TYPE}
    )

    print(f'Status: {response.status_code}')
    print(f'Response: {response.json()}')


if __name__ == '__main__':
    send_csv()
