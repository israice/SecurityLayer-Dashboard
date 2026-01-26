FROM python:3.11-slim

# Установить git и docker-cli для автодеплоя
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем приложение
COPY DASHBOARD/ ./DASHBOARD/
COPY config.yaml .

WORKDIR /app/DASHBOARD

EXPOSE 5000

CMD ["python", "AA_waiting_for_csv.py"]
