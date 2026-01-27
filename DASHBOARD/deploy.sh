#!/bin/bash
set -e

echo "=== Deploy started ==="
cd /repo

# Разрешить git работать с репозиторием другого владельца
git config --global --add safe.directory /repo

echo "Fetching latest changes..."
git fetch origin master

echo "Resetting to origin/master..."
git reset --hard origin/master

# Вернуть владельца репозитория (контейнер работает как root)
REPO_OWNER=$(stat -c '%u:%g' /repo)
chown -R "$REPO_OWNER" /repo

# Установить новые зависимости (если requirements.txt изменился)
pip install -r /app/requirements.txt --quiet

# Перезагрузить gunicorn (PID 1) — workers подхватят новый код
echo "Reloading gunicorn..."
kill -HUP 1

echo "=== Deploy completed ==="
