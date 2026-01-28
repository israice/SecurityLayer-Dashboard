

```bash
# DEV
python DASHBOARD/AA_waiting_for_csv.py
python AGENT/AB_sending_to_server.py
python AGENT/AB_sending_to_server.py --local

# ZIP
python DASHBOARD\dashboard-page\download-zip\build_zip.py


# PROD
git pull
docker compose up -d
docker compose up -d --build
docker compose up -d --build --force-recreate
docker compose down && docker compose up -d --build
docker logs security-layer-dashboard -f
```
