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

echo "Rebuilding container..."
docker-compose -f /repo/docker-compose.yml up -d --build --force-recreate

echo "=== Deploy completed ==="
