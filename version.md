git log --oneline -n 10

Copy-Item .env $env:TEMP\.env.backup
git reset --hard b24c71c
git clean -fd
Copy-Item $env:TEMP\.env.backup .env -Force
git push origin master --force

git add .
git commit -m "v0.0.11 - deploy test"
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
