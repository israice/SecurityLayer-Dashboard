# Gevent monkey patching — ДОЛЖЕН быть первым (только для production)
try:
    from gevent import monkey
    monkey.patch_all()
    from gevent.queue import Queue, Empty, Full
    USE_GEVENT = True
except ImportError:
    from queue import Queue, Empty, Full
    USE_GEVENT = False
    print('⚠ gevent not found — running in dev mode (no async)')

from flask import Flask, request, Response, send_file, send_from_directory
import os
import yaml
import csv
import json
import threading
import signal
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, '..', 'config.yaml')

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

HOST = config['DASHBOARD']['HOST']
PORT = config['DASHBOARD']['PORT']
SAVE_FILE = config['DASHBOARD']['SAVE_FILE']
ENCODING = config['ENCODING']
ROUTE = config['ROUTES']['update_dashboard']
REPO_ROOT = os.path.normpath(os.path.join(script_dir, '..'))
CSV_HEADERS = ['ORG_ID', 'PC_ID', 'PORT_ID', 'PORT_MAP', 'PORT_STATUS', 'PORT_NAME', 'MANUFACTURER']

app = Flask(__name__, static_folder=None)

# Register blueprints
from modules.auth import auth_bp
from modules.zip_builder import zip_bp
from modules.webhook import webhook_bp
app.register_blueprint(auth_bp)
app.register_blueprint(zip_bp)
app.register_blueprint(webhook_bp)

@app.after_request
def add_no_cache_headers(response):
    if response.content_type and ('text/html' in response.content_type
                                   or 'text/css' in response.content_type
                                   or 'javascript' in response.content_type):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

# SSE clients by organization
sse_clients_by_org = {}
sse_lock = threading.Lock()
file_lock = threading.Lock()

def _add_sse_client(org_id: str, client_queue) -> None:
    with sse_lock:
        if org_id not in sse_clients_by_org:
            sse_clients_by_org[org_id] = []
        sse_clients_by_org[org_id].append(client_queue)

def _remove_sse_client(org_id: str, client_queue) -> None:
    with sse_lock:
        if org_id in sse_clients_by_org:
            if client_queue in sse_clients_by_org[org_id]:
                sse_clients_by_org[org_id].remove(client_queue)
            if not sse_clients_by_org[org_id]:
                del sse_clients_by_org[org_id]

def read_csv_as_json(org_id: str | None = None) -> dict:
    save_path = os.path.join(REPO_ROOT, 'DATA', SAVE_FILE)
    if not os.path.exists(save_path):
        return {'headers': [], 'rows': []}
    try:
        with file_lock:
            with open(save_path, 'r', encoding=ENCODING) as f:
                rows = list(csv.reader(f))
    except Exception:
        return {'headers': [], 'rows': []}
    if not rows:
        return {'headers': [], 'rows': []}
    headers, data_rows = rows[0], rows[1:]
    if org_id:
        data_rows = [row for row in data_rows if row and row[0] == org_id]
    return {'headers': headers, 'rows': data_rows}

def notify_clients(changed_org_ids: set[str]) -> None:
    with sse_lock:
        for org_id in changed_org_ids:
            if org_id not in sse_clients_by_org:
                continue
            data = read_csv_as_json(org_id)
            message = f"data: {json.dumps(data)}\n\n"
            dead_clients = []
            for client in sse_clients_by_org[org_id]:
                try:
                    client.put_nowait(message)
                except (Full, Exception):
                    dead_clients.append(client)
            for client in dead_clients:
                sse_clients_by_org[org_id].remove(client)

@app.route(ROUTE, methods=['POST'])
def update_dashboard():
    csv_content = request.get_data(as_text=True)
    save_path = os.path.join(REPO_ROOT, 'DATA', SAVE_FILE)
    tmp_path = save_path + '.tmp'
    lines = csv_content.strip().split('\n')
    if not lines:
        return 'Empty data', 400
    reader = csv.DictReader(lines)
    new_rows = list(reader)
    if not new_rows:
        return 'No data rows', 400
    new_keys = set((row['ORG_ID'], row['PC_ID']) for row in new_rows)
    with file_lock:
        existing_rows = []
        if os.path.exists(save_path):
            with open(save_path, 'r', encoding=ENCODING) as f:
                existing_rows = list(csv.DictReader(f))
        kept_rows = [row for row in existing_rows if (row['ORG_ID'], row['PC_ID']) not in new_keys]
        merged_rows = kept_rows + new_rows
        with open(tmp_path, 'w', newline='', encoding=ENCODING) as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(merged_rows)
        os.replace(tmp_path, save_path)
    print(f'CSV merged: kept {len(kept_rows)} rows, added {len(new_rows)} rows')
    notify_clients(set(row['ORG_ID'] for row in new_rows))
    return 'OK', 200

@app.route('/sse')
def sse():
    org_id = request.args.get('org_id', '').strip()
    if not org_id:
        return 'org_id required', 400
    client_queue = Queue()
    _add_sse_client(org_id, client_queue)

    def generate():
        data = read_csv_as_json(org_id)
        yield f"data: {json.dumps(data)}\n\n"
        try:
            while True:
                try:
                    message = client_queue.get(timeout=5)
                    yield message
                except Empty:
                    yield ": heartbeat\n\n"
        finally:
            _remove_sse_client(org_id, client_queue)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'X-Accel-Buffering': 'no'})

# Static routes
@app.route('/static/<path:subpath>')
def serve_static(subpath):
    return send_from_directory(os.path.join(REPO_ROOT, 'DASHBOARD'), subpath)

@app.route('/')
def index():
    return send_file(os.path.join(REPO_ROOT, 'DASHBOARD', 'index.html'))

@app.route('/version-check.js')
def version_check_js():
    return send_file(os.path.join(REPO_ROOT, 'DASHBOARD', 'version-check.js'))

@app.route('/version.md')
def version_md():
    return send_file(os.path.join(REPO_ROOT, 'version.md'))

@app.route('/favicon.ico')
def favicon():
    return send_file(os.path.join(REPO_ROOT, 'DASHBOARD', 'favicon.ico'))

@app.route('/robots.txt')
def robots():
    return send_file(os.path.join(REPO_ROOT, 'DASHBOARD', 'robots.txt'))

if __name__ == '__main__':
    def _shutdown():
        print('\nServer stopped by user')
        sys.exit(0)

    if USE_GEVENT:
        from gevent import signal_handler as gevent_signal
        gevent_signal(signal.SIGINT, _shutdown)
    else:
        signal.signal(signal.SIGINT, lambda _s, _f: _shutdown())

    print(f'Server running on http://{HOST}:{PORT}')
    print(f'Dashboard: http://localhost:{PORT}/')
    app.run(host=HOST, port=PORT, threaded=True)
