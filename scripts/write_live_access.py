"""Create a local-only access note for the project owner. Never print passwords."""
from pathlib import Path
from dotenv import dotenv_values
app=dotenv_values('.data/live/access.env')
switch=dotenv_values('.data/live/switch/.env')
Path('.data/live/ACCESS.md').write_text(f'''# Private local demo access

This file contains local test account passwords. Do not commit or share it.

## SwitchOps
URL: http://localhost:3000
Email: {app['APP_EMAIL']}
Password: {app['APP_PASSWORD']}

## Mattermost
URL: http://localhost:8065/switchops/channels/operations-hub
Username: {switch['MATTERMOST_USER']}
Password: {switch['MATTERMOST_USER_PASSWORD']}

## Official Switch Gateway
URL: http://localhost:3080
Email: {switch['GATEWAY_ADMIN_EMAIL']}
Password: {switch['GATEWAY_ADMIN_PASSWORD']}
Bridge server for Switch Console: http://localhost:8080

## Mailpit
URL: http://localhost:8025
No password is required on this loopback-only sandbox.

All business data in this organization is explicitly fictional. Email goes only to Mailpit.
''',encoding='utf-8')
print('Private local access note written to .data/live/ACCESS.md; no password printed.')
