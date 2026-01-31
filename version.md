
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

# TASKS

🟠 HIGH — Ядро функционала
- delete computer from server csv when stop using API
- button users
- users table logic
- edit users table
- add user to table
- delete row from users table
- add notification icon
- add notification logic
- refactoring files and paths
- update config.yaml with more settings
- check what must be saved in localstorage

🟡 MEDIUM — Инфраструктура и данные
- create simple tables database hello world
- migrate all csv to database
- create registeration mail confirmation
- check antiviruses that no alarm logic involved
- user desktop app for local usb on/off
- create local hosting with hybrid connection
- create full local hosting version with no internet

🔵 NORMAL — UI/UX улучшения
- add 'ORG_NAME Secured'
- add "2 computers not saved"
- add computers tab
- change id="org-name" and Admin Dashboard fonts and color
- add SecurityLayer logo to dashboard
- fix same theme colors to all pages
- choose best way to show table in mobile
- table cell config with popup
- create button for class="version" to popup updates
- create live wallpaper in login page
- create live wallpaper in dashboard

🟢 LOW — Расширение платформ
- make android hello world
- create android SecurityLayer app
- create mobile android usbSecurity version
- create ios app hello world
- create ios SecurityLayer app
- create mobile ios usbSecurity version
- create multi linux usbSecurity version
- find Mac emulator
- create Mac hello world version
- create Type-C version and add it as on/off in settings
- create mobile notification with sound

⚪ FUTURE — Бизнес и маркетинг
- add cameras mapping csv
- add on/off the USERS/CAMERAS/DESKTOP tabs in Settings
- create language icon
- translate all project to 10 top languages
- add trial/premium column
- create premium types silver/gold/platinum
- create payment hello world
- add payment to project
- create PAYMENT_AUDIT.md
- create about team
- create contacts
- create social networks
- create startup websites accounts
- create flow for each account
- create full list of pin testing companies for marketing
- order 50 usb lockers
- research for grants in cyber security
- create step by step pitch
- find package for final software and hardware product 

# UPDATE
git add .
git commit -m "v0.1.11 - added TASKS list"
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
v0.1.11 - added TASKS list 
