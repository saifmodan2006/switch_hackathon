"""Post an authorized fictional test request through a real Mattermost user account.

This runner does not impersonate a personal human review and never grants approval.
"""
import json
import secrets
from pathlib import Path
import httpx
from dotenv import dotenv_values,set_key
from live_diagnostics import redact

access=dotenv_values('.data/live/access.env')
switch=dotenv_values('.data/live/switch/.env')

def checked(r):
    if not r.is_success:raise RuntimeError(redact(f'HTTP {r.status_code} {r.request.url.path}: {r.text[:700]}'))
    return r.json()

with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',timeout=45) as app, httpx.Client(base_url='http://127.0.0.1:8065',timeout=30) as mm:
    user=checked(app.post('/auth/login',json={'email':access['APP_EMAIL'],'password':access['APP_PASSWORD']}))
    app.headers['X-CSRF-Token']=user['csrf']
    state=checked(app.get('/switch/status'))
    if state['connected_agents']!=6:raise RuntimeError(f'Wait for all six actual Switch heartbeats; connected={state["connected_agents"]}')
    if access.get('LIVE_POST_ID'):
        print('Existing actual Mattermost request preserved:',access['LIVE_POST_ID'])
        raise SystemExit(0)
    customers=checked(app.get('/customers'))['items']
    acme=next(c for c in customers if c['name']=='Acme Solutions' and c['synthetic'])
    checked(app.put('/customers/'+acme['id'],json={k:acme[k] for k in ['name','company','email','phone','stage','tags','notes','owner','opted_out']}))
    source=('SYNTHETIC LIVE DEMO SOURCE. Acme Solutions is a fictional organization testing internal customer onboarding. '
        'The requested discovery scope is: map incoming requests, record customer context, identify an owner, draft a proposal, '
        'require an authorized human review before sending, and create an internal follow-up. '
        'Available service capabilities: workflow discovery, customer process mapping, internal knowledge retrieval, '
        'proposal drafting, human approval controls and internal follow-up scheduling. '
        'Suggested discovery outputs are a process map, requirements checklist and draft pilot scope. '
        'Commercial pricing, implementation deadlines, ROI and service guarantees are not approved and must not be invented. '
        'This is a nonbinding discovery proposal, not a contract or promise. External calendar availability is unknown.')
    checked(app.post('/knowledge/upload',files={'file':('acme-live-discovery-scope.txt',source.encode(),'text/plain')}))
    login=mm.post('/api/v4/users/login',json={'login_id':switch['MATTERMOST_USER'],'password':switch['MATTERMOST_USER_PASSWORD']})
    checked(login);mm.headers['Authorization']='Bearer '+login.headers['Token']
    marker='LIVE-ACME-'+secrets.token_hex(4)
    request=(f'@ops-coordinator {marker}: Prepare a nonbinding workflow discovery proposal for fictional Acme Solutions. '
        'Use the saved CRM notes and internal acme-live-discovery-scope.txt knowledge source. Research only those authorized records. '
        'Describe the discovery scope, proposed process map, requirements checklist, human review controls and internal follow-up. '
        'Cite the actual record and document IDs. Mark unknown pricing, delivery dates and ROI as open questions, not promises. '
        'Those commercial questions should not prevent drafting this nonbinding discovery scope. '
        'Ask the authorized human to review the exact proposal before sending it to the Mailpit sandbox. '
        'After approval and sandbox acceptance, create an internal follow-up; do not invite external attendees.')
    post=checked(mm.post('/api/v4/posts',json={'channel_id':access['MATTERMOST_CHANNEL_ID'],'message':request}))
    set_key('.data/live/access.env','LIVE_POST_ID',post['id'])
    set_key('.data/live/access.env','LIVE_REQUEST_MARKER',marker)
    Path('.data/live/request.json').write_text(json.dumps({'marker':marker,'mattermost_post_id':post['id'],'customer_id':acme['id'],
        'channel_id':access['MATTERMOST_CHANNEL_ID'],'request':request,'posted_by':'Authorized live verification runner using a real Mattermost human-role account; not a claim of manual typing'},indent=2))
    print('Actual Mattermost request posted:',post['id'],marker)
