"""Capture the actual live workflow without credentials in the evidence output."""
import json
import sys
from pathlib import Path
import httpx
from dotenv import dotenv_values,set_key
sys.stdout.reconfigure(encoding='utf-8',errors='replace')

access=dotenv_values('.data/live/access.env')
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',timeout=20) as app:
    login=app.post('/auth/login',json={'email':access['APP_EMAIL'],'password':access['APP_PASSWORD']})
    login.raise_for_status()
    status=app.get('/switch/status').json()
    rows=app.get('/workflows').json()
    rows=[w for w in rows if access.get('LIVE_REQUEST_MARKER','no-marker') in w['request']]
    print('Actual connected agents:',status['connected_agents'])
    for row in rows:
        detail=app.get('/workflows/'+row['id']).json()
        Path('.data/live/latest-workflow.json').write_text(json.dumps(detail,indent=2),encoding='utf-8')
        set_key('.data/live/access.env','WORKFLOW_ID',row['id'])
        print('Workflow:',row['id'],row['status'],'models:',row['model_calls'],'handoffs:',row['handoffs'])
        if row['error']:print('Error:',row['error'])
        for event in detail['events'][-4:]:print(event['kind'],event['agent'],event['message'][:300])
        for doc in detail['documents'][:1]:
            Path(f'.data/live/proposal-v{doc["version"]}.md').write_text(doc['content'],encoding='utf-8')
            print('Actual proposal:',doc['id'],'version',doc['version'])
        for approval in detail['approvals']:
            print('Approval:',approval['id'],approval['status'],'recipient:',approval['payload']['recipient'])
    if not rows:print('Waiting for the genuine Mattermost message to create its durable workflow.')
    print('Mailpit actual captured messages:',httpx.get('http://localhost:8025/api/v1/messages').json().get('total',0))
