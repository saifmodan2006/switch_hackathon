"""Provision a real local demo through authenticated public application/Gateway APIs.

No fixture output, room imitation or bypass of the runtime. No approval is granted here.
"""
import json
import secrets
from pathlib import Path
import httpx
from dotenv import dotenv_values, set_key
from live_diagnostics import redact

private=Path('.data/live/access.env')
if not private.exists():
    private.write_text('APP_EMAIL=demo.operator@example.com\nAPP_PASSWORD='+secrets.token_urlsafe(28)+'\n',encoding='utf-8')
access=dict(dotenv_values(private))
switch=dict(dotenv_values('.data/live/switch/.env'))
config=dict(dotenv_values('.env'))


def checked(response):
    if not response.is_success:
        raise RuntimeError(redact(f'{response.request.method} {response.request.url.path} HTTP {response.status_code}: {response.text[:1200]}'))
    return response.json()


with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',timeout=90,trust_env=False) as app, \
     httpx.Client(base_url='http://127.0.0.1:8080',timeout=90,trust_env=False) as gateway:
    checked(gateway.post('/gateway/auth/login',json={'email':switch['GATEWAY_ADMIN_EMAIL'],'password':switch['GATEWAY_ADMIN_PASSWORD']}))
    response=app.post('/auth/login',json={'email':access['APP_EMAIL'],'password':access['APP_PASSWORD']})
    if response.status_code==401:
        response=app.post('/auth/register',json={'name':'Demo Operator','email':access['APP_EMAIL'],'password':access['APP_PASSWORD'],'organization':'SwitchOps Live Demo'})
    user=checked(response)
    app.headers['X-CSRF-Token']=user['csrf']
    me=checked(app.get('/auth/me'))
    print('Authenticated real demo workspace:',me['org_id'],flush=True)
    if not access.get('SWITCH_REGISTRATION_KEY'):
        key=checked(gateway.post('/gateway/api-keys',json={'label':'SwitchOps six specialist runtime'}))
        set_key(private,'SWITCH_REGISTRATION_KEY',key['key'])
        access['SWITCH_REGISTRATION_KEY']=key['key']
    checked(app.put('/integrations/switch',json={'config':{'server_url':'http://host.docker.internal:8080'},'secret':access['SWITCH_REGISTRATION_KEY']}))
    checked(app.put('/integrations/model',json={'config':{'provider':'gemini','base_url':config['MODEL_BASE_URL'],
        'model':config['MODEL_NAME'],'timeout':120,'allow_external_private_data':True},'secret':config['MODEL_API_KEY']}))
    print('Gemini availability:',checked(app.post('/integrations/model/test'))['available'],flush=True)
    agents=checked(app.get('/agents'))
    for agent in agents:
        if not agent['switch_id']:
            response=app.post('/agents/'+agent['id']+'/register')
            if response.status_code!=503:
                checked(response)
            else:
                current=next(a for a in checked(app.get('/agents')) if a['id']==agent['id'])
                if not current['switch_id']:
                    checked(response)
        print('Real Switch identity registered/preserved:',agent['slug'],flush=True)
    agents=checked(app.get('/agents'))
    for agent in agents:
        checked(gateway.put('/gateway/agents/'+agent['switch_id']+'/addressing-policy',json={'policy':{'rules':[
            {'rooms':'*','room_groups':'*','users':[],'agents':[],'owner':True,'owner_agents':True,'platform':False}]}}))
    print('Owner-authorized peer addressing policies configured.',flush=True)
    rooms=checked(gateway.get('/gateway/rooms'))
    if not any(r['name']=='operations-hub' for r in rooms):
        response=gateway.post('/gateway/rooms/from-yaml',json={'yaml':Path('switch/templates/business-workspace.yaml').read_text(encoding='utf-8'),
            'inputs':{'bridge':'Mattermost'},'template_name':'SwitchOps live business workspace'})
        result=checked(response)
        Path('.data/live/room-provision-result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    rooms=checked(gateway.get('/gateway/rooms'))
    mapped=checked(app.get('/resources/rooms'))
    for room in rooms:
        detail=checked(gateway.get('/gateway/rooms/'+room['id']))
        url=f'http://localhost:8065/{switch["MATTERMOST_TEAM_NAME"]}/channels/{detail.get("linked_channel_name") or room["name"]}'
        if not any(r['data'].get('switch_room_id')==room['id'] for r in mapped):
            checked(app.post('/resources/rooms',json={'title':room['name'],'data':{'switch_room_id':room['id'],'description':room['description'],'url':url}}))
        if room['name']=='operations-hub':
            Path('.data/live/room-detail.json').write_text(json.dumps(detail,indent=2),encoding='utf-8')
            set_key(private,'ROOM_ID',room['id'])
            set_key(private,'MATTERMOST_CHANNEL_ID',detail['external_channel_id'])
            set_key(private,'APP_ORG_ID',me['org_id'])
            set_key(private,'APP_USER_ID',me['id'])
    checked(app.post('/demo/seed'))
    print('Real rooms created/mapped and explicitly synthetic CRM/knowledge seeded.',flush=True)
