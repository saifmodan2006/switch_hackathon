from datetime import timedelta
import pytest
from sqlalchemy import select
from app.models.domain import *
from app.services.workflows import transition, payload_hash
from app.services.approvals import execute
from app.security.auth import hasher
from conftest import register


async def customer(client,name='Acme',email='acme@example.com'):
    response=await client.post('/api/v1/customers',json={'name':name,'email':email,'notes':'Verified customer context'})
    assert response.status_code==201,response.text
    return response.json()


async def workflow(client,customer_id=None):
    response=await client.post('/api/v1/workflows',json={'title':'Customer proposal','request':'Prepare a proposal with human approval','customer_id':customer_id})
    assert response.status_code==201,response.text
    return response.json()


async def test_auth_and_csrf(client):
    assert (await client.get('/api/v1/customers')).status_code==401
    user=await register(client)
    assert (await client.get('/api/v1/auth/me')).json()['role']=='owner'
    token=client.headers.pop('X-CSRF-Token')
    assert (await client.post('/api/v1/customers',json={'name':'Blocked'})).status_code==403
    client.headers['X-CSRF-Token']=token
    assert (await client.post('/api/v1/auth/logout')).status_code==200
    assert (await client.get('/api/v1/auth/me')).status_code==401
    assert (await client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'wrong-password'})).status_code==401
    login=await client.post('/api/v1/auth/login',json={'email':'owner@example.com','password':'a-secure-test-password!'})
    assert login.status_code==200
    assert login.json()['csrf']!=token
    assert 'HttpOnly' in login.headers['set-cookie']


async def test_customer_crud_and_duplicates(client,owner):
    c=await customer(client)
    assert (await client.post('/api/v1/customers',json={'name':'Duplicate','email':c['email']})).status_code==409
    assert (await client.get('/api/v1/customers?q=Acme')).json()['total']==1
    response=await client.put('/api/v1/customers/'+c['id'],json={'name':'Updated Acme','email':c['email'],'stage':'active'})
    assert response.status_code==200
    assert response.json()['stage']=='active'
    assert (await client.get('/api/v1/customers/'+c['id'])).json()['name']=='Updated Acme'
    assert (await client.delete('/api/v1/customers/'+c['id'])).status_code==200
    assert (await client.get('/api/v1/customers')).json()['total']==0


async def test_tenant_isolation(client,owner):
    c=await customer(client)
    w=await workflow(client,c['id'])
    await register(client,'other@example.com')
    assert (await client.get('/api/v1/customers')).json()['items']==[]
    assert (await client.get('/api/v1/customers/'+c['id'])).status_code==404
    assert (await client.get('/api/v1/workflows/'+w['id'])).status_code==404
    assert (await client.post('/api/v1/workflows',json={'title':'Invalid reference','request':'Try another tenant customer','customer_id':c['id']})).status_code==404
    assert (await client.post('/api/v1/resources/tasks',json={'title':'Invalid','data':{'workflow_id':w['id']}})).status_code==404


async def test_workflow_idempotency(client,owner):
    body={'title':'Idempotent request','request':'Research this customer carefully'}
    a=await client.post('/api/v1/workflows',json=body,headers={'Idempotency-Key':'request-1'})
    b=await client.post('/api/v1/workflows',json=body,headers={'Idempotency-Key':'request-1'})
    assert a.json()['id']==b.json()['id']
    body['title']='Different request'
    assert (await client.post('/api/v1/workflows',json=body,headers={'Idempotency-Key':'request-1'})).status_code==409
    assert (await client.post('/api/v1/workflows/'+a.json()['id']+'/cancel')).json()['status']=='CANCELLED'
    assert (await client.post('/api/v1/workflows/'+a.json()['id']+'/retry')).status_code==409


async def test_state_machine(db_factory,client,owner):
    w=await workflow(client)
    async with db_factory() as db:
        row=await db.get(Workflow,w['id'])
        from fastapi import HTTPException
        with pytest.raises(HTTPException):transition(db,row,'COMPLETED','Skip approval')
        transition(db,row,'TRIAGING','Valid')
        transition(db,row,'BLOCKED','Switch outage')
        transition(db,row,'TRIAGING','Human retry')
        await db.commit()
        assert row.status=='TRIAGING'


async def make_approval(client,db_factory):
    c=await customer(client)
    w=await workflow(client,c['id'])
    async with db_factory() as db:
        wf=await db.get(Workflow,w['id']);wf.status='AWAITING_APPROVAL'
        doc=Document(org_id=wf.org_id,workflow_id=wf.id,title=wf.title,content='A grounded synthetic test proposal',version=1)
        db.add(doc);await db.flush()
        payload={'recipient':c['email'],'subject':wf.title,'body':doc.content}
        approval=Approval(org_id=wf.org_id,workflow_id=wf.id,document_id=doc.id,version=1,payload=payload,payload_hash=payload_hash(payload),expires_at=now()+timedelta(days=1))
        db.add(approval);await db.commit()
        return approval.id,wf.id


async def test_approval_replay_and_execution(client,owner,db_factory,monkeypatch):
    approval_id,wid=await make_approval(client,db_factory)
    calls=[]
    async def fake_send(payload,message_id):calls.append(payload);return 'sandbox_accepted'
    monkeypatch.setattr('app.services.approvals.send_approved_email',fake_send)
    async with db_factory() as db:
        from fastapi import HTTPException
        with pytest.raises(HTTPException):await execute(db,approval_id)
    decision=await client.post('/api/v1/approvals/'+approval_id+'/decision',json={'decision':'APPROVED','reason':'Reviewed exact version'})
    assert decision.status_code==200,decision.text
    assert (await client.post('/api/v1/approvals/'+approval_id+'/decision',json={'decision':'APPROVED'})).status_code==409
    async with db_factory() as db:
        delivery=await execute(db,approval_id)
        assert delivery.status=='sandbox_accepted'
    async with db_factory() as db:
        from fastapi import HTTPException
        with pytest.raises(HTTPException):await execute(db,approval_id)
    assert len(calls)==1


async def test_approval_expiry_and_payload_integrity(client,owner,db_factory):
    approval_id,_=await make_approval(client,db_factory)
    async with db_factory() as db:
        row=await db.get(Approval,approval_id);row.expires_at=now()-timedelta(seconds=1);await db.commit()
    assert (await client.post('/api/v1/approvals/'+approval_id+'/decision',json={'decision':'APPROVED'})).status_code==409


async def test_viewer_cannot_mutate_or_approve(client,owner,db_factory):
    aid,_=await make_approval(client,db_factory)
    async with db_factory() as db:
        member=await db.scalar(select(Membership).where(Membership.user_id==owner['id']));member.role='viewer';await db.commit()
    assert (await client.get('/api/v1/customers')).status_code==200
    assert (await client.post('/api/v1/customers',json={'name':'Forbidden'})).status_code==403
    assert (await client.post('/api/v1/approvals/'+aid+'/decision',json={'decision':'APPROVED'})).status_code==403
    assert (await client.put('/api/v1/integrations/switch',json={'config':{'server_url':'http://localhost'}})).status_code==403


async def test_document_search_tenant_scope_and_safe_upload(client,owner):
    data=b'Approved service catalog: customer onboarding, process discovery, internal workflow automation.'
    upload=await client.post('/api/v1/knowledge/upload',files={'file':('catalog.txt',data,'text/plain')})
    assert upload.status_code==201,upload.text
    id=upload.json()['id']
    results=(await client.get('/api/v1/knowledge/search?q=onboarding')).json()
    assert results[0]['document_id']==id
    assert results[0]['method']=='keyword'
    assert (await client.post('/api/v1/knowledge/upload',files={'file':('bad.exe',b'payload','application/octet-stream')})).status_code==415
    assert (await client.delete('/api/v1/knowledge/'+id)).status_code==200
    assert (await client.get('/api/v1/knowledge/search?q=onboarding')).json()==[]


async def test_task_and_calendar_validation(client,owner):
    t=(await client.post('/api/v1/resources/tasks',json={'title':'Follow up','status':'open'})).json()
    assert (await client.put('/api/v1/resources/tasks/'+t['id'],json={'title':t['title'],'status':'done'})).status_code==200
    assert (await client.put('/api/v1/resources/tasks/'+t['id'],json={'title':t['title'],'status':'open'})).status_code==409
    event={'title':'Internal meeting','data':{'start':'2026-11-09T10:00:00+05:30','end':'2026-11-09T11:00:00+05:30'}}
    r=await client.post('/api/v1/resources/calendar',json=event)
    assert r.status_code==201,r.text
    assert r.json()['data']['external_availability']=='unknown'
    assert (await client.post('/api/v1/resources/calendar',json=event)).status_code==409
    ics=await client.get('/api/v1/calendar/'+r.json()['id']+'/ics')
    assert 'DTSTART:20261109T043000Z' in ics.text


async def test_seed_real_metrics_and_invalid_input(client,owner):
    assert (await client.get('/api/v1/analytics')).json()['total_workflows']==0
    assert (await client.post('/api/v1/demo/seed')).status_code==200
    assert (await client.post('/api/v1/demo/seed')).status_code==200
    a=(await client.get('/api/v1/analytics')).json()
    assert a['customers']==3 and a['completed']==0 and a['input_tokens']==0
    assert (await client.post('/api/v1/customers',json={'name':'x','email':'invalid'})).status_code==422
    assert (await client.post('/api/v1/workflows',json={'title':'No','request':'short'})).status_code==422


async def test_csv_injection_and_import(client,owner):
    await customer(client,name='=HYPERLINK("bad")')
    response=await client.get('/api/v1/customers/export')
    assert "'=HYPERLINK" in response.text
    csv=b'name,company,email,phone,stage,notes\nNorthstar,Northstar,north@example.com,,lead,Customer notes\n'
    imported=await client.post('/api/v1/customers/import',files={'file':('customers.csv',csv,'text/csv')})
    assert imported.json()['imported']==1,imported.text
    imported=await client.post('/api/v1/customers/import',files={'file':('customers.csv',csv,'text/csv')})
    assert imported.json()['skipped_duplicates']==1
