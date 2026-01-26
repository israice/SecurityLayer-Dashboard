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

echo "Stopping old container..."
docker stop security-layer-dashboard 2>/dev/null || true
docker rm security-layer-dashboard 2>/dev/null || true

echo "Rebuilding and restarting container..."
docker-compose -f docker-compose.yml up -d --build

echo "=== Deploy completed ==="
