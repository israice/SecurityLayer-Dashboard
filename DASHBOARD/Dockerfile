FROM python:3.11-slim

# Установить git и docker-cli для автодеплоя
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-26.1.4.tgz \
       | tar xz -C /usr/local/bin --strip-components=1 docker/docker \
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

CMD ["python", "AA_waiting_for_csv.py"]
