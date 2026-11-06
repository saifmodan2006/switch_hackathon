"""Submit the project owner's explicit approval of the reviewed v2 sandbox proposal.

This is never called by the model/runtime. It requires a deliberate operator invocation
after human authorization and verifies the exact reviewed file before authorizing I/O.
"""
import json
from pathlib import Path
import httpx
from dotenv import dotenv_values
access=dotenv_values('.data/live/access.env')
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',timeout=30) as app:
    login=app.post('/auth/login',json={'email':access['APP_EMAIL'],'password':access['APP_PASSWORD']})
    login.raise_for_status();app.headers['X-CSRF-Token']=login.json()['csrf']
    response=app.get('/workflows/'+access['WORKFLOW_ID']);response.raise_for_status();workflow=response.json()
    approval=next(a for a in workflow['approvals'] if a['version']==2 and a['status']=='PENDING')
    assert approval['payload']['recipient']=='acme@example.test'
    assert approval['payload']['body']==Path('.data/live/proposal-v2.md').read_text(encoding='utf-8')
    reason=('Explicit project-owner authorization in the Codex conversation on 2026-11-07 Asia/Kolkata: '
            'Approve proposal v2 for Mailpit. Exact recipient acme@example.test. '
            'Assistant submits this authenticated application decision as delegated demo operator; no real customer delivery authorized.')
    response=app.post('/approvals/'+approval['id']+'/decision',json={'decision':'APPROVED','reason':reason})
    response.raise_for_status()
    Path('.data/live/human-approval-evidence.json').write_text(json.dumps({'approval_id':approval['id'],'workflow_id':workflow['id'],
        'document_id':approval['document_id'],'version':2,'recipient':approval['payload']['recipient'],
        'payload_hash':approval['payload_hash'],'authorization':reason,'decision':response.json()['status']},indent=2),encoding='utf-8')
    print('Explicit human authorization committed:',approval['id'],'version 2, Mailpit only.')
