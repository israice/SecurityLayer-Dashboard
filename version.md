
<details>
<summary>🧑‍💻 Developer Notes</summary>

```bash
# DEV
python DASHBOARD/AA_waiting_for_csv.py
python AGENT/AB_sending_to_server.py
python AGENT/AB_sending_to_server.py --local

# ZIP
python DASHBOARD\dashboard-page\download-zip\build_zip.py

# TOOLS
python TOOLS\check_files_size.py

# PROD
git pull
docker compose build 
docker compose up -d
docker compose up -d --build
docker compose up -d --build --force-recreate
docker compose down && docker compose up -d --build
docker logs security-layer-dashboard -f

docker compose down -v --rmi all
docker compose build --no-cache
docker compose up -d

```
</details>


# RECOVERY
git log --oneline -n 20

Copy-Item .env $env:TEMP\.env.backup
git reset --hard 80f714fc
git clean -fd
Copy-Item $env:TEMP\.env.backup .env -Force
git push origin master --force

# UPDATE
git add .
git commit -m "v0.1.12 - added updated TASKS list"
git push


# DEV
v0.1.0 - working version the proof of concept
v0.1.1 - added LICENSE and README.md as source-available note for transparency and security audits
v0.1.2 - added update by filter ORG_ID with PC_ID
v0.1.3 - added SSE filter ORG_ID
v0.1.4 - added red green to dashboard
v0.1.6 - removed other github versions and local folders
v0.1.7 - added AUDIT.md
v0.1.8 - large files refactoring
v0.1.9 - convert_report_to_csv upgrade
v0.1.10 - removed UsbTreeView logic 
v0.1.12 - added updated TASKS list 
