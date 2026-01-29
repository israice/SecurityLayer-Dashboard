# Gevent monkey patching — ДОЛЖЕН быть первым!
from gevent import monkey
monkey.patch_all()

from flask import Flask, request, Response, send_file, jsonify, send_from_directory
import os
import yaml
import csv
import json
import threading
from gevent.queue import Queue, Empty, Full
import hmac
import hashlib
import subprocess
import sys
import re
import zipfile
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
CSV_HEADERS = ['ORG_ID', 'PC_ID', 'PORT_ID', 'PORT_MAP', 'PORT_STATUS', 'PORT_NAME']

app = Flask(__name__, static_folder=None)


@app.after_request
def add_no_cache_headers(response):
    """Отключить кеширование для статики и HTML — после деплоя браузер получит свежие файлы"""
    if response.content_type and ('text/html' in response.content_type
                                   or 'text/css' in response.content_type
                                   or 'javascript' in response.content_type):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# SSE клиенты по организациям
sse_clients_by_org = {}  # {'ORG_xxx': [queue1, queue2], ...}
sse_lock = threading.Lock()
file_lock = threading.Lock()


def _add_sse_client(org_id: str, client_queue: Queue) -> None:
    with sse_lock:
        if org_id not in sse_clients_by_org:
            sse_clients_by_org[org_id] = []
        sse_clients_by_org[org_id].append(client_queue)


def _remove_sse_client(org_id: str, client_queue: Queue) -> None:
    with sse_lock:
        if org_id in sse_clients_by_org:
            if client_queue in sse_clients_by_org[org_id]:
                sse_clients_by_org[org_id].remove(client_queue)
            if not sse_clients_by_org[org_id]:
                del sse_clients_by_org[org_id]

# ==================== Auth helpers ====================

USERS_CSV = os.path.join(REPO_ROOT, 'DATA', 'users.csv')

def is_valid_email(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


def is_valid_password(password: str) -> bool:
    return isinstance(password, str) and len(password) >= 3


def is_valid_name(name: str) -> bool:
    return isinstance(name, str) and len(name.strip()) >= 2


def generate_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'

# Маппинг полей формы → колонок CSV
_FIELD_TO_COLUMN = {
    'email': 'USER_MAIL',
    'orgName': 'ORG_NAME',
    'userName': 'USER_NAME',
}

_REGISTER_VALIDATORS = [
    ('email',    is_valid_email,    'Invalid email format'),
    ('password', is_valid_password, 'Password must be at least 3 characters'),
    ('orgName',  is_valid_name,     'Organization name must be at least 2 characters'),
    ('userName', is_valid_name,     'User name must be at least 2 characters'),
]

_UNIQUENESS_RULES = [
    ('email',    'Email is taken, try another'),
    ('orgName',  'Organization name is taken, try another'),
    ('userName', 'User name is taken, try another'),
]


def _validate_registration(data: dict) -> tuple[dict, str | None]:
    """Валидация полей регистрации. Возвращает (fields, error_msg|None)."""
    fields = {
        'email':    data.get('email', '').strip(),
        'password': data.get('password', ''),
        'orgName':  data.get('orgName', '').strip(),
        'userName': data.get('userName', '').strip(),
    }
    for field, validator, error_msg in _REGISTER_VALIDATORS:
        if not validator(fields[field]):
            return fields, error_msg
    return fields, None


def _check_field_exists(users: list[dict], field: str, value: str) -> bool:
    """Проверяет, существует ли значение поля среди пользователей."""
    column = _FIELD_TO_COLUMN.get(field)
    if not column:
        return False
    return any(u[column].lower() == value.lower() for u in users)


def read_users() -> list[dict]:
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


def write_user(user: dict) -> bool:
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


def read_csv_as_json(org_id: str | None = None) -> dict:
    """Читает CSV и возвращает данные как JSON, опционально фильтруя по ORG_ID"""
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

    if org_id:
        # ORG_ID в колонке 0
        data_rows = [row for row in data_rows if row and row[0] == org_id]

    return {'headers': headers, 'rows': data_rows}


def notify_clients(changed_org_ids: set[str]) -> None:
    """Отправляет обновление только клиентам измененных организаций"""
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
    save_path = os.path.join(script_dir, SAVE_FILE)
    tmp_path = save_path + '.tmp'

    # Парсим входящие данные
    lines = csv_content.strip().split('\n')
    if not lines:
        return 'Empty data', 400

    reader = csv.DictReader(lines)
    new_rows = list(reader)
    if not new_rows:
        return 'No data rows', 400

    # Определяем ключи (ORG_ID, PC_ID) из новых данных
    new_keys = set((row['ORG_ID'], row['PC_ID']) for row in new_rows)

    with file_lock:
        # Читаем существующие данные
        existing_rows = []
        if os.path.exists(save_path):
            with open(save_path, 'r', encoding=ENCODING) as f:
                existing_reader = csv.DictReader(f)
                existing_rows = list(existing_reader)

        # Оставляем только записи с другими (ORG_ID, PC_ID)
        kept_rows = [
            row for row in existing_rows
            if (row['ORG_ID'], row['PC_ID']) not in new_keys
        ]

        # Объединяем: старые (других PC) + новые
        merged_rows = kept_rows + new_rows

        # Записываем результат
        with open(tmp_path, 'w', newline='', encoding=ENCODING) as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            writer.writeheader()
            writer.writerows(merged_rows)
        os.replace(tmp_path, save_path)

    print(f'CSV merged: kept {len(kept_rows)} rows, added {len(new_rows)} rows')
    changed_org_ids = set(row['ORG_ID'] for row in new_rows)
    notify_clients(changed_org_ids)
    return 'OK', 200


@app.route('/sse')
def sse():
    """SSE endpoint для получения обновлений (требует org_id)"""
    org_id = request.args.get('org_id', '').strip()
    if not org_id:
        return 'org_id required', 400

    client_queue = Queue()
    _add_sse_client(org_id, client_queue)

    def generate():
        # Отправляем начальные данные — только для этой организации
        data = read_csv_as_json(org_id)
        yield f"data: {json.dumps(data)}\n\n"

        try:
            while True:
                try:
                    message = client_queue.get(timeout=5)  # 5 сек — быстрее освобождает thread при disconnect
                    yield message
                except Empty:
                    # Heartbeat для поддержания соединения
                    yield ": heartbeat\n\n"
        finally:
            _remove_sse_client(org_id, client_queue)

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
    fields, error = _validate_registration(data)
    if error:
        return jsonify(ok=False, error=error), 400

    users = read_users()
    for field, error_msg in _UNIQUENESS_RULES:
        if _check_field_exists(users, field, fields[field]):
            return jsonify(ok=False, error=error_msg), 400

    user = {
        'ORG_ID': generate_id('ORG'),
        'ORG_NAME': fields['orgName'],
        'USER_ID': generate_id('USER'),
        'USER_NAME': fields['userName'],
        'USER_MAIL': fields['email'],
        'USER_PASSWORD': fields['password']
    }

    if write_user(user):
        print(f'Register success: {fields["email"]}')
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
    exists = _check_field_exists(users, field, value)
    return jsonify(ok=True, exists=exists)


# ==================== ZIP Builder ====================

zip_lock = threading.Lock()

@app.route('/api/build-zip', methods=['POST'])
def api_build_zip():
    data = request.get_json()
    org_name = (data.get('org_name') or '').strip()

    if not org_name:
        return jsonify(ok=False, error='Organization name is required'), 400

    users = read_users()
    user = next((u for u in users if u['ORG_NAME'] == org_name), None)
    if not user:
        return jsonify(ok=False, error='Organization not found'), 404

    org_id = user['ORG_ID']

    download_zip_dir = os.path.join(
        REPO_ROOT, 'DASHBOARD', 'dashboard-page', 'download-zip'
    )
    org_id_csv = os.path.join(
        download_zip_dir, 'SecurityLayer', 'usbSecurity', 'A_org_id.csv'
    )
    security_layer_dir = os.path.join(download_zip_dir, 'SecurityLayer')
    zip_dir = os.path.join(download_zip_dir, 'ZIP')
    output_zip = os.path.join(zip_dir, 'SecurityLayer_USB_Monitor.zip')

    acquired = zip_lock.acquire(timeout=5)
    if not acquired:
        return jsonify(ok=False, error='Another build is in progress'), 429

    try:
        with open(org_id_csv, 'w', newline='', encoding=ENCODING) as f:
            writer = csv.writer(f)
            writer.writerow(['ORG_ID'])
            writer.writerow([org_id])

        os.makedirs(zip_dir, exist_ok=True)
        exclude = {'__pycache__', '.pyc', '.build_manifest.json'}

        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(security_layer_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if any(ex in fpath for ex in exclude):
                        continue
                    arcname = os.path.join(
                        'SecurityLayer',
                        os.path.relpath(fpath, security_layer_dir)
                    )
                    zf.write(fpath, arcname)

        return send_file(
            output_zip,
            mimetype='application/zip',
            as_attachment=True,
            download_name='SecurityLayer_USB_Monitor.zip'
        )

    except Exception as e:
        print(f'build_zip error: {e}')
        return jsonify(ok=False, error='Internal server error'), 500

    finally:
        zip_lock.release()


# ==================== Pages ====================

@app.route('/static/<path:subpath>')
def serve_static(subpath):
    """Статические файлы (CSS/JS) для страниц"""
    return send_from_directory(os.path.join(REPO_ROOT, 'DASHBOARD'), subpath)


@app.route('/')
def index():
    """Роутер — загружает страницы через loadPage() на клиенте"""
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

def verify_github_signature(payload: bytes, signature: str | None) -> bool:
    """Проверка HMAC-SHA256 подписи от GitHub"""
    if not signature:
        return False
    # Секрет из переменной окружения (безопаснее чем в config)
    secret = os.environ['GITHUB_WEBHOOK_SECRET'].encode()
    expected = 'sha256=' + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def run_deploy() -> None:
    """Выполняет деплой в фоне"""
    repo_path = config['WEBHOOK']['REPO_PATH']
    deploy_script = '/app/DASHBOARD/deploy.sh'
    print(f'Starting deploy from {repo_path}...')
    try:
        result = subprocess.run(
            ['bash', deploy_script],
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


if __name__ == '__main__':
    print(f'Server running on http://{HOST}:{PORT}')
    print(f'Dashboard: http://localhost:{PORT}/')
    app.run(host=HOST, port=PORT, threaded=True)
