from flask import Flask, request, Response, send_file
import os
import yaml
import csv
import json
import threading
import queue
import time

script_dir = os.path.dirname(os.path.abspath(__file__))
config_path = os.path.join(script_dir, '..', 'config.yaml')

with open(config_path, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

HOST = config['DASHBOARD']['HOST']
PORT = config['DASHBOARD']['PORT']
SAVE_FILE = config['DASHBOARD']['SAVE_FILE']
ENCODING = config['ENCODING']
ROUTE = config['ROUTES']['update_dashboard']

app = Flask(__name__)

# SSE клиенты
sse_clients = []
sse_lock = threading.Lock()


def read_csv_as_json():
    """Читает CSV и возвращает данные как JSON"""
    save_path = os.path.join(script_dir, SAVE_FILE)
    if not os.path.exists(save_path):
        return {'headers': [], 'rows': []}

    try:
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
                client.put(message)
            except Exception:
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
            if os.path.exists(save_path):
                mtime = os.path.getmtime(save_path)
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

    with open(save_path, 'w', encoding=ENCODING) as f:
        f.write(csv_content)

    print(f'CSV saved to {save_path}')
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


@app.route('/')
def index():
    """Главная страница"""
    return send_file('index.html')


if __name__ == '__main__':
    # Запуск file watcher в отдельном потоке
    watcher_thread = threading.Thread(target=file_watcher, daemon=True)
    watcher_thread.start()

    print(f'Server running on http://{HOST}:{PORT}')
    print(f'Dashboard: http://localhost:{PORT}/')
    app.run(host=HOST, port=PORT, threaded=True)
