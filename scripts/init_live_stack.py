"""Initialize ignored local deployment secrets once; never print credentials."""
from pathlib import Path
import secrets
from dotenv import dotenv_values, set_key

directory = Path('.data/live/switch')
directory.mkdir(parents=True, exist_ok=True)
env = directory/'.env'
if not env.exists():
    fixed = {'SWITCH_VERSION':'0.31.0','SWITCH_BIND_ADDR':'127.0.0.1','API_HOST_PORT':'8080',
             'GATEWAY_HOST_PORT':'3080','MATTERMOST_HOST_PORT':'8065','POSTGRES_HOST_PORT':'5433',
             'DB_USER':'switch_app','DB_OWNER_USER':'postgres','DB_NAME':'switch',
             'GATEWAY_ADMIN_EMAIL':'switchops.admin@example.com','FRONTEND_BASE_URL':'http://localhost:3080',
             'GATEWAY_PUBLIC_URL':'http://localhost:8080','MESSAGING_PUBLIC_URL':'',
             'MATTERMOST_ADMIN_USER':'switchops-admin','MATTERMOST_USER':'switchops-demo',
             'MATTERMOST_TEAM_NAME':'switchops','GATEWAY_COOKIE_SECURE':'false',
             'TELEMETRY_ENABLED':'false','THIRD_PARTY_AVATARS_ENABLED':'false'}
    for key in ['DB_PASSWORD','DB_OWNER_PASSWORD','AGENT_REGISTRATION_TOKEN','GATEWAY_ADMIN_PASSWORD',
                'MATTERMOST_ADMIN_PASSWORD','MATTERMOST_USER_PASSWORD']:
        fixed[key] = secrets.token_urlsafe(32)
    fixed['SECRET_KEYS'] = 'primary:' + secrets.token_urlsafe(48)
    env.write_text('\n'.join(f'{k}={v}' for k,v in fixed.items())+'\n',encoding='utf-8')
    print('Created private Switch/Mattermost deployment settings.')
else:
    print('Existing Switch deployment settings preserved.')

set_key('.env','MODEL_PROVIDER','gemini')
set_key('.env','MODEL_BASE_URL','https://generativelanguage.googleapis.com/v1beta')
set_key('.env','MODEL_NAME','gemini-3.5-flash-lite')
set_key('.env','DOCKER_MODEL_BASE_URL','https://generativelanguage.googleapis.com/v1beta')
set_key('.env','MODEL_ALLOW_EXTERNAL_PRIVATE_DATA','true')
set_key('.env','SWITCH_SERVER_URL','http://host.docker.internal:8080')
print('Selected Gemini and the genuine local Switch bridge; API key preserved.')
