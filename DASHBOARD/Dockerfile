FROM python:3.11-slim

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
