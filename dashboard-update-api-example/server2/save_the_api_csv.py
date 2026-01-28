# ============== SETTINGS ==============
HOST = '0.0.0.0'
PORT = 5000
DEBUG = True
CSV_FILE = 'after.csv'
ENDPOINT = '/update-dashboard'
METHOD = 'POST'
JSON_KEY = 'csv_content'
ENCODING = 'utf-8'
MSG_SUCCESS = 'CSV saved successfully'
MSG_ERROR = 'No {key} provided'
# ======================================

from flask import Flask, request, jsonify
import os

app = Flask(__name__)

csv_path = os.path.join(os.path.dirname(__file__), CSV_FILE)


@app.route(ENDPOINT, methods=[METHOD])
def upload_csv():
    data = request.get_json()

    if not data or JSON_KEY not in data:
        return jsonify({'error': MSG_ERROR.format(key=JSON_KEY)}), 400

    csv_content = data[JSON_KEY]

    with open(csv_path, 'w', encoding=ENCODING) as f:
        f.write(csv_content)

    return jsonify({'message': MSG_SUCCESS}), 200


if __name__ == '__main__':
    app.run(host=HOST, port=PORT, debug=DEBUG)
