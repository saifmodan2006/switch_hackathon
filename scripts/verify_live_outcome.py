"""Verify real saved business results and Mailpit capture; never sends mail."""
import hashlib
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values

access = dotenv_values('.data/live/access.env')
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1', timeout=30) as app:
    login = app.post('/auth/login', json={'email': access['APP_EMAIL'], 'password': access['APP_PASSWORD']})
    login.raise_for_status()
    detail = app.get('/workflows/' + access['WORKFLOW_ID']).json()
    assert detail['status'] == 'COMPLETED'
    approved = next(a for a in detail['approvals'] if a['status'] == 'APPROVED')
    expected = Path('.data/live/proposal-v2.md').read_text(encoding='utf-8')
    review = json.loads(Path('.data/live/human-approval-evidence.json').read_text())
    messages = httpx.get('http://localhost:8025/api/v1/messages').json()
    assert messages['total'] == 1, 'Expected exactly one sandbox message'
    captured = httpx.get('http://localhost:8025/api/v1/message/' + messages['messages'][0]['ID']).json()
    assert any(r['Address'] == 'acme@example.test' for r in captured['To'])
    assert expected.rstrip() == captured['Text'].replace('\r\n', '\n').rstrip(), 'Captured mail must contain exact approved proposal (SMTP line endings normalized)'
    records = {}
    for kind in ['tasks', 'calendar']:
        rows = app.get('/' + kind).json()
        if isinstance(rows, dict): rows = rows.get('items', [])
        records[kind] = [r for r in rows if r['data'].get('workflow_id') == detail['id']]
        assert len(records[kind]) == 1, f'Expected one {kind} follow-up'
    assert records['calendar'][0]['data']['invitation_sent'] is False
    evidence = {'workflow_id': detail['id'], 'status': detail['status'],
        'model_calls': detail['model_calls'], 'switch_handoffs': detail['handoffs'],
        'approved_version': 2, 'approval_id': approved['id'],
        'proposal_sha256': hashlib.sha256(expected.encode()).hexdigest(),
        'mailpit_message_id': captured['ID'], 'sandbox_recipient': 'acme@example.test',
        'exact_approved_content_captured': True, 'captured_messages': messages['total'],
        'followups': records, 'dashboard': app.get('/analytics').json()}
    Path('.data/live/outcome-evidence.json').write_text(json.dumps(evidence, indent=2))
    print(json.dumps({k: v for k, v in evidence.items() if k not in {'followups', 'dashboard'}}, indent=2))
