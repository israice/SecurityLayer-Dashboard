
---

<details>
<summary>🧑‍💻 Developer Notes</summary>

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


</details>

- remove other github versions nad local folders
- fix minimizing when agent stops
- sort csv by ORG_ID
- free usb its red
- in use usb is green
- file size
    DASHBOARD\AA_waiting_for_csv.py : 495
    DASHBOARD\landing-page\index.html : 509
    DASHBOARD\landing-page\landing.css : 327
    DASHBOARD\login-page\auth.css : 379
    DASHBOARD\dashboard-page\download-zip\build_zip.py : 318
    DASHBOARD\dashboard-page\download-zip\SecurityLayer\usbSecurity\AA_installer.py : 382
    DASHBOARD\dashboard-page\download-zip\SecurityLayer\usbSecurity\BA_usb_watcher.py : 254
    DASHBOARD\dashboard-page\download-zip\SecurityLayer\usbSecurity\B_run.py : 290
    DASHBOARD\dashboard-page\download-zip\SecurityLayer\usbSecurity\CBA_UsbTreeView.exe : 10666
- 


git log --oneline -n 10

Copy-Item .env $env:TEMP\.env.backup
git reset --hard 80f714fc
git clean -fd
Copy-Item $env:TEMP\.env.backup .env -Force
git push origin master --force

git add .
git commit -m "v0.1.2 - test 2"
git push

v0.0.1 - dashboard SSE
v0.0.2 - server update via webhook github
v0.0.3 - testing server webhook
v0.0.4 - working dashboard on server with auto update
v0.0.5 - top panel with icons and update time
v0.0.6 - added dev localhost for agent
v0.0.7 - added version update to page
v0.0.8 - server test
v0.0.9 - added auth and landing page 
v0.0.10 - deploy fixed 
v0.0.11 - deploy test
v0.0.12 - version test
v0.0.13 - added no-cache to fix deploy
v0.0.14 - removed not in use code
v0.0.15 - added ZIP button with no logic
v0.0.16 - added ZIP files
v0.0.17 - added ZIP logic to button
v0.0.18 - added python folder and zip to github
v0.0.19 - fixed ui center for mobile view in landing page
v0.0.20 - added dashboard-update-api-example
v0.0.21 - testing update dashboard table using API
v0.0.22 - yaml removed from usbSecurity
v0.1.0 - working version the proof of concept
v0.1.1 - added LICENSE and README.md as source-available note for transparency and security audits
v0.1.2 - added update by filter ORG_ID with PC_ID
