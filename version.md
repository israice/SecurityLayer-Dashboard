git log --oneline -n 10

Copy-Item .env $env:TEMP\.env.backup
git reset --hard 80f714fc
git clean -fd
Copy-Item $env:TEMP\.env.backup .env -Force
git push origin master --force

git add .
git commit -m "v0.0.22 - yaml removed from usbSecurity"
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

