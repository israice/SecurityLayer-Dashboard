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

echo "Rebuilding and restarting container..."
# Запускаем docker-compose в ОТДЕЛЬНОМ контейнере, который не будет убит
docker run -d --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /home/administrator/projects/SecurityLayer:/repo \
  -w /repo \
  docker/compose:latest \
  --project-name securitylayer \
  -f docker-compose.yml \
  up -d --build --force-recreate

echo "=== Deploy completed ==="
