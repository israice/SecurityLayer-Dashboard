from flask import Flask, request, Response, send_file, jsonify, send_from_directory
import os
import yaml
import csv
import json
import threading
import queue
import time
import hmac
import hashlib
import subprocess
import re
import uuid

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, '..', 'config.yaml')

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

HOST = config['DASHBOARD']['HOST']
PORT = config['DASHBOARD']['PORT']
SAVE_FILE = config['DASHBOARD']['SAVE_FILE']
ENCODING = config['ENCODING']
ROUTE = config['ROUTES']['update_dashboard']
REPO_PATH = config['WEBHOOK']['REPO_PATH']  # "/repo" — примонтированный том (для Docker)
REPO_ROOT = os.path.normpath(os.path.join(script_dir, '..'))  # корень репозитория (для статики)

app = Flask(__name__, static_folder=None)

# SSE клиенты
sse_clients = []
sse_lock = threading.Lock()
file_lock = threading.Lock()

# ==================== Auth helpers ====================

USERS_CSV = os.path.join(REPO_ROOT, 'DATA', 'users.csv')

is_valid_email = lambda email: bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))
is_valid_password = lambda password: isinstance(password, str) and len(password) >= 3
is_valid_name = lambda name: isinstance(name, str) and len(name.strip()) >= 2

generate_id = lambda prefix: f'{prefix}_{uuid.uuid4().hex[:8]}'


def read_users():
    """Читает пользователей из DATA/users.csv"""
    users = []
    try:
        if os.path.exists(USERS_CSV):
            with open(USERS_CSV, 'r', encoding=ENCODING) as f:
                for row in csv.DictReader(f):
                    users.append(row)
    except Exception as e:
        print(f'Error reading users: {e}')
    return users


def write_user(user):
    """Добавляет нового пользователя в DATA/users.csv"""
    try:
        exists = os.path.exists(USERS_CSV)
        with open(USERS_CSV, 'a', newline='', encoding=ENCODING) as f:
            writer = csv.DictWriter(f, fieldnames=[
                'ORG_ID', 'ORG_NAME', 'USER_ID', 'USER_NAME', 'USER_MAIL', 'USER_PASSWORD'
            ])
            if not exists:
                writer.writeheader()
            writer.writerow(user)
        return True
    except Exception as e:
        print(f'Error writing user: {e}')
        return False


def read_csv_as_json():
    """Читает CSV и возвращает данные как JSON"""
    save_path = os.path.join(script_dir, SAVE_FILE)
    if not os.path.exists(save_path):
        return {'headers': [], 'rows': []}

    try:
        with file_lock:
            with open(save_path, 'r', encoding=ENCODING) as f:
                reader = csv.reader(f)
                rows = list(reader)
    except Exception:
        return {'headers': [], 'rows': []}

    if not rows:
        return {'headers': [], 'rows': []}

    headers = rows[0]
    data_rows = rows[1:]

    return {'headers': headers, 'rows': data_rows}


def notify_clients():
    """Отправляет обновление всем SSE клиентам"""
    data = read_csv_as_json()
    message = f"data: {json.dumps(data)}\n\n"

    with sse_lock:
        dead_clients = []
        for client in sse_clients:
            try:
                client.put_nowait(message)
            except (queue.Full, Exception):
                dead_clients.append(client)
        for client in dead_clients:
            sse_clients.remove(client)


def file_watcher():
    """Polling-based file watcher"""
    save_path = os.path.join(script_dir, SAVE_FILE)
    last_mtime = 0

    print(f'Watching for changes: {save_path}')

    while True:
        try:
            with file_lock:
                if os.path.exists(save_path):
                    mtime = os.path.getmtime(save_path)
                else:
                    mtime = 0
            if mtime > last_mtime:
                if last_mtime > 0:  # Не уведомлять при первом запуске
                    print(f'File changed: {save_path}')
                    notify_clients()
                last_mtime = mtime
        except Exception as e:
            print(f'Watcher error: {e}')

        time.sleep(0.5)  # Проверка каждые 0.5 сек


@app.route(ROUTE, methods=['POST'])
def update_dashboard():
    csv_content = request.get_data(as_text=True)
    save_path = os.path.join(script_dir, SAVE_FILE)
    tmp_path = save_path + '.tmp'

    with file_lock:
        with open(tmp_path, 'w', encoding=ENCODING) as f:
            f.write(csv_content)
        os.replace(tmp_path, save_path)

    print(f'CSV saved to {save_path}')
    notify_clients()
    return 'OK', 200


@app.route('/sse')
def sse():
    """SSE endpoint для получения обновлений"""
    client_queue = queue.Queue()

    with sse_lock:
        sse_clients.append(client_queue)

    def generate():
        # Отправляем начальные данные
        data = read_csv_as_json()
        yield f"data: {json.dumps(data)}\n\n"

        try:
            while True:
                try:
                    message = client_queue.get(timeout=30)
                    yield message
                except queue.Empty:
                    # Heartbeat для поддержания соединения
                    yield ": heartbeat\n\n"
        finally:
            with sse_lock:
                if client_queue in sse_clients:
                    sse_clients.remove(client_queue)

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


# ==================== Auth API ====================

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')

    if not email or not password:
        return jsonify(ok=False, error='Email and password required'), 400

    users = read_users()
    user = next((u for u in users if u['USER_MAIL'] == email and u['USER_PASSWORD'] == password), None)

    if user:
        print(f'Login success: {email}')
        return jsonify(ok=True, user=user)
    else:
        print(f'Login failed: {email}')
        return jsonify(ok=False, error='Invalid credentials'), 401


@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    org_name = data.get('orgName', '').strip()
    user_name = data.get('userName', '').strip()

    if not is_valid_email(email):
        return jsonify(ok=False, error='Invalid email format'), 400
    if not is_valid_password(password):
        return jsonify(ok=False, error='Password must be at least 3 characters'), 400
    if not is_valid_name(org_name):
        return jsonify(ok=False, error='Organization name must be at least 2 characters'), 400
    if not is_valid_name(user_name):
        return jsonify(ok=False, error='User name must be at least 2 characters'), 400

    users = read_users()
    if any(u['USER_MAIL'].lower() == email.lower() for u in users):
        return jsonify(ok=False, error='Email is taken, try another'), 400
    if any(u['ORG_NAME'].lower() == org_name.lower() for u in users):
        return jsonify(ok=False, error='Organization name is taken, try another'), 400
    if any(u['USER_NAME'].lower() == user_name.lower() for u in users):
        return jsonify(ok=False, error='User name is taken, try another'), 400

    user = {
        'ORG_ID': generate_id('ORG'),
        'ORG_NAME': org_name,
        'USER_ID': generate_id('USER'),
        'USER_NAME': user_name,
        'USER_MAIL': email,
        'USER_PASSWORD': password
    }

    if write_user(user):
        print(f'Register success: {email}')
        return jsonify(ok=True, user=user)
    else:
        return jsonify(ok=False, error='Failed to save user'), 500


@app.route('/api/check', methods=['POST'])
def api_check():
    data = request.get_json()
    field = data.get('field', '')
    value = data.get('value', '').strip()

    if not value:
        return jsonify(ok=True, exists=False)

    users = read_users()
    exists = False

    if field == 'email':
        exists = any(u['USER_MAIL'].lower() == value.lower() for u in users)
    elif field == 'orgName':
        exists = any(u['ORG_NAME'].lower() == value.lower() for u in users)
    elif field == 'userName':
        exists = any(u['USER_NAME'].lower() == value.lower() for u in users)

    return jsonify(ok=True, exists=exists)


# ==================== Pages ====================

@app.route('/static/<path:subpath>')
def serve_static(subpath):
    """Статические файлы (CSS/JS) для страниц"""
    return send_from_directory(os.path.join(REPO_ROOT, 'DASHBOARD'), subpath)


@app.route('/')
def index():
    """Главная страница (SPA)"""
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


# ==================== GitHub Webhook ====================

def verify_github_signature(payload, signature):
    """Проверка HMAC-SHA256 подписи от GitHub"""
    if not signature:
        return False
    # Секрет из переменной окружения (безопаснее чем в config)
    secret = os.environ['GITHUB_WEBHOOK_SECRET'].encode()
    expected = 'sha256=' + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def run_deploy():
    """Выполняет деплой в фоне"""
    repo_path = config['WEBHOOK']['REPO_PATH']
    deploy_script = '/app/DASHBOARD/deploy.sh'
    print(f'Starting deploy from {repo_path}...')
    try:
        result = subprocess.run(
            [deploy_script],
            cwd=repo_path,
            capture_output=True,
            text=True
        )
        print(f'Deploy stdout: {result.stdout}')
        if result.stderr:
            print(f'Deploy stderr: {result.stderr}')
        print(f'Deploy finished with code {result.returncode}')
    except Exception as e:
        print(f'Deploy error: {e}')


@app.route('/webhook/github', methods=['POST'])
def github_webhook():
    """Endpoint для GitHub webhook - автодеплой при push"""
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_github_signature(request.data, signature):
        print('Webhook: Invalid signature')
        return 'Invalid signature', 401

    payload = request.json
    ref = payload['ref']
    allowed_branch = config['WEBHOOK']['ALLOWED_BRANCH']

    if ref != allowed_branch:
        print(f'Webhook: Ignored branch {ref}')
        return f'Ignored: {ref}', 200

    print(f'Webhook: Push to {ref} - starting deploy')
    # Запуск в фоновом потоке чтобы вернуть 200 до перезапуска контейнера
    threading.Thread(target=run_deploy, daemon=True).start()
    return 'Deploy started', 200


# Запуск file watcher в отдельном потоке (работает и с gunicorn, и напрямую)
watcher_thread = threading.Thread(target=file_watcher, daemon=True)
watcher_thread.start()

if __name__ == '__main__':
    print(f'Server running on http://{HOST}:{PORT}')
    print(f'Dashboard: http://localhost:{PORT}/')
    app.run(host=HOST, port=PORT, threaded=True)
