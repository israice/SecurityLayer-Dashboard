FROM python:3.11-slim

# Установить git и docker-cli + docker-compose для автодеплоя
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-26.1.4.tgz \
       | tar xz -C /usr/local/bin --strip-components=1 docker/docker \
    && curl -fsSL "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-x86_64" \
       -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем приложение
COPY DASHBOARD/ ./DASHBOARD/
COPY config.yaml .

# Делаем deploy.sh исполняемым
RUN chmod +x ./DASHBOARD/deploy.sh

WORKDIR /app/DASHBOARD

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "AA_waiting_for_csv:app"]
