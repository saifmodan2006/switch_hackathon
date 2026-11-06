"""Create or inspect a separate dependency probe. Run create only while Switch is stopped."""
import json
import sys
from pathlib import Path
import httpx
from dotenv import dotenv_values, set_key

access = dotenv_values('.data/live/access.env')
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1', timeout=20) as app:
    login = app.post('/auth/login', json={'email': access['APP_EMAIL'], 'password': access['APP_PASSWORD']})
    login.raise_for_status()
    app.headers['X-CSRF-Token'] = login.json()['csrf']
    if sys.argv[1] == 'create':
        assert app.get('/switch/status').json()['connected_agents'] == 0
        row = app.post('/workflows', headers={'Idempotency-Key': 'live-switch-outage-probe'}, json={
            'title': 'Switch outage verification', 'request': 'Synthetic dependency probe: prepare a discovery draft; no external action authorized.'})
        row.raise_for_status()
        set_key('.data/live/access.env', 'OUTAGE_WORKFLOW_ID', row.json()['id'])
        print('Separate outage probe saved:', row.json()['id'])
    else:
        row = app.get('/workflows/' + access['OUTAGE_WORKFLOW_ID']).json()
        assert row['status'] == 'BLOCKED', row['status']
        assert row['model_calls'] == 0 and row['handoffs'] == 0
        evidence = {k: row[k] for k in ['id', 'status', 'error', 'model_calls', 'handoffs']}
        evidence['connected_agents'] = app.get('/switch/status').json()['connected_agents']
        Path('.data/live/outage-evidence.json').write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence, indent=2))
