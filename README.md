

```bash
python DASHBOARD/AA_waiting_for_csv.py
python AGENT/AB_sending_to_server.py
```
docker compose up -d
docker compose down && docker compose up -d --build


git pull
docker compose up -d --build --force-recreate

docker logs security-layer-dashboard -f
