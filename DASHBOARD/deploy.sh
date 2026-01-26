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
docker compose -f docker-compose.yml up -d --build --force-recreate

echo "=== Deploy completed ==="
