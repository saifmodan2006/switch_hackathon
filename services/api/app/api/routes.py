import asyncio
import csv
import io
import json
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, File, Header
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func, delete, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db, Session
from app.models.domain import *
from app.schemas.inputs import *
from app.security.auth import principal, Principal, require, can_write, new_session, hasher, encrypt, decrypt, digest
from app.services.workflows import transition, audit, payload_hash
from app.services.approvals import decide
from app.services.knowledge import extract, index_document, search as knowledge_search
from app.integrations.switch import SwitchClient, SwitchAgentRegistry, SwitchError
from app.integrations.model import ModelAdapter
from app.integrations.storage import put_private, delete_private
from app.core.config import settings
from agents.agents.definitions import AGENTS

router = APIRouter(prefix='/api/v1')
Db = Depends(get_db)
Auth = Depends(principal)


def serialize(row):
    excluded = {'password_hash', 'token_hash', 'encrypted_key', 'encrypted_secret', 'csrf'}
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in excluded}


async def owned(db, cls, id, org_id):
    row = await db.scalar(select(cls).where(cls.id == id, cls.org_id == org_id))
    if not row:
        raise HTTPException(404, 'Record not found')
    return row


@router.get('/health')
async def health(db: AsyncSession = Db):
    await db.execute(select(1))
    return {'status': 'ok', 'database': 'connected', 'version': '1.0.0'}


@router.post('/auth/register', status_code=201)
async def register(body: Register, response: Response, db: AsyncSession = Db):
    if await db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, 'Email already registered')
    org = Organization(name=body.organization)
    user = User(name=body.name, email=body.email.lower(), password_hash=hasher.hash(body.password))
    db.add_all([org, user])
    await db.flush()
    db.add(Membership(org_id=org.id, user_id=user.id, role='owner'))
    for slug, name, description, _ in AGENTS:
        db.add(Agent(org_id=org.id, slug=slug, name=name, description=description))
    audit(db, org.id, user.id, 'organization.created', org.id)
    return await new_session(db, user, org.id, response)


@router.post('/auth/login')
async def login(body: Login, response: Response, db: AsyncSession = Db):
    user = await db.scalar(select(User).where(User.email == body.email.lower()))
    try:
        if not user:
            hasher.verify('$argon2id$v=19$m=65536,t=3,p=4$c3dpdGNob3Bzc2FsdDEyMw$nuI7zwcCKHqhdZxfGdAWaw9DOHHGDQtmY0lWn6PBnfg', body.password)
            raise ValueError()
        hasher.verify(user.password_hash, body.password)
    except Exception:
        raise HTTPException(401, 'Email or password is incorrect')
    member = await db.scalar(select(Membership).where(Membership.user_id == user.id))
    return await new_session(db, user, member.org_id, response)


@router.get('/auth/me')
async def me(p: Principal = Auth, db: AsyncSession = Db):
    org = await db.get(Organization, p.org_id)
    return {**serialize(p.user), 'org_id': p.org_id, 'role': p.role, 'csrf': p.session.csrf,
            'organization': serialize(org)}


@router.post('/auth/logout')
async def logout(response: Response, p: Principal = Auth, db: AsyncSession = Db):
    await db.delete(p.session)
    await db.commit()
    response.delete_cookie('switchops_session')
    return {'ok': True}


@router.get('/organizations')
async def organizations(p: Principal = Auth, db: AsyncSession = Db):
    rows = (await db.execute(select(Organization, Membership.role).join(Membership).where(Membership.user_id == p.user.id))).all()
    return [{**serialize(org), 'role': role} for org, role in rows]


@router.post('/organizations/{id}/select')
async def select_org(id: str, response: Response, p: Principal = Auth, db: AsyncSession = Db):
    member = await db.scalar(select(Membership).where(Membership.org_id == id, Membership.user_id == p.user.id))
    if not member:
        raise HTTPException(403, 'Organization membership required')
    await db.delete(p.session)
    return await new_session(db, p.user, id, response)


@router.get('/customers')
async def customers(q: str = '', stage: str = '', offset: int = 0, limit: int = 50, p: Principal = Auth, db: AsyncSession = Db):
    query = select(Customer).where(Customer.org_id == p.org_id, Customer.archived == False)
    if q:
        query = query.where(or_(Customer.name.ilike(f'%{q}%'), Customer.company.ilike(f'%{q}%'), Customer.email.ilike(f'%{q}%')))
    if stage:
        query = query.where(Customer.stage == stage)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = (await db.scalars(query.order_by(Customer.created_at.desc()).offset(max(0, offset)).limit(min(max(1, limit), 200)))).all()
    return {'items': [serialize(x) for x in rows], 'total': total}


@router.post('/customers', status_code=201)
async def create_customer(body: CustomerInput, p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    if body.email and await db.scalar(select(Customer).where(Customer.org_id == p.org_id, Customer.email == body.email.lower(), Customer.archived == False)):
        raise HTTPException(409, 'A customer with this email already exists')
    values = body.model_dump()
    values['email'] = body.email.lower()
    row = Customer(org_id=p.org_id, **values)
    db.add(row)
    await db.flush()
    audit(db, p.org_id, p.user.id, 'customer.created', row.id)
    await db.commit()
    return serialize(row)


@router.get('/customers/export')
async def export_customers(p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin', 'manager')
    rows = (await db.scalars(select(Customer).where(Customer.org_id == p.org_id, Customer.archived == False))).all()
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['name', 'company', 'email', 'phone', 'stage', 'notes'])
    for row in rows:
        writer.writerow([("'" + v if v.startswith(('=', '+', '-', '@')) else v) for v in [row.name, row.company, row.email, row.phone, row.stage, row.notes]])
    audit(db, p.org_id, p.user.id, 'customers.exported', detail={'count': len(rows)})
    await db.commit()
    return Response(out.getvalue(), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=customers.csv'})


@router.post('/customers/import')
async def import_customers(file: UploadFile = File(), p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    data = await file.read(2_000_001)
    if len(data) > 2_000_000:
        raise HTTPException(413, 'CSV exceeds 2 MB')
    try:
        rows = list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
        if len(rows) > 2000:
            raise ValueError()
        inputs = [CustomerInput.model_validate(row) for row in rows]
    except Exception:
        raise HTTPException(422, 'CSV requires customer fields and at most 2000 valid rows')
    count, skipped = 0, 0
    for body in inputs:
        if body.email and await db.scalar(select(Customer.id).where(Customer.org_id == p.org_id, Customer.email == body.email.lower())):
            skipped += 1
            continue
        db.add(Customer(org_id=p.org_id, **{**body.model_dump(), 'email': body.email.lower()}))
        await db.flush()
        count += 1
    audit(db, p.org_id, p.user.id, 'customers.imported', count=count, skipped=skipped)
    await db.commit()
    return {'imported': count, 'skipped_duplicates': skipped}


@router.get('/customers/{id}')
async def customer_detail(id: str, p: Principal = Auth, db: AsyncSession = Db):
    row = await owned(db, Customer, id, p.org_id)
    workflows = (await db.scalars(select(Workflow).where(Workflow.customer_id == id, Workflow.org_id == p.org_id))).all()
    interactions = (await db.scalars(select(Record).where(Record.org_id == p.org_id, Record.kind == 'interactions'))).all()
    return {**serialize(row), 'workflows': [serialize(w) for w in workflows],
            'interactions': [serialize(x) for x in interactions if x.data.get('customer_id') == id]}


@router.put('/customers/{id}')
async def update_customer(id: str, body: CustomerInput, p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    row = await owned(db, Customer, id, p.org_id)
    if body.email and await db.scalar(select(Customer.id).where(Customer.org_id == p.org_id, Customer.email == body.email.lower(), Customer.id != id, Customer.archived == False)):
        raise HTTPException(409, 'Email already belongs to another customer')
    for k, v in body.model_dump().items():
        setattr(row, k, v.lower() if k == 'email' else v)
    audit(db, p.org_id, p.user.id, 'customer.updated', id)
    await db.commit()
    return serialize(row)


@router.delete('/customers/{id}')
async def archive_customer(id: str, p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    row = await owned(db, Customer, id, p.org_id)
    row.archived = True
    audit(db, p.org_id, p.user.id, 'customer.archived', id)
    await db.commit()
    return {'ok': True}


@router.post('/requests', status_code=201)
@router.post('/workflows', status_code=201)
async def create_workflow(body: WorkflowInput, p: Principal = Auth, db: AsyncSession = Db, idempotency_key: str | None = Header(default=None)):
    can_write(p)
    hashed = payload_hash(body.model_dump(mode='json'))
    if idempotency_key:
        if len(idempotency_key) > 180:
            raise HTTPException(422, 'Idempotency key is too long')
        previous = await db.scalar(select(Idempotency).where(Idempotency.org_id == p.org_id, Idempotency.key == idempotency_key))
        if previous:
            if previous.request_hash != hashed:
                raise HTTPException(409, 'Idempotency key was used with different content')
            return serialize(await owned(db, Workflow, previous.resource_id, p.org_id))
    if body.customer_id:
        await owned(db, Customer, body.customer_id, p.org_id)
    if body.room_id:
        rooms = (await db.scalars(select(Record).where(Record.org_id == p.org_id, Record.kind == 'rooms'))).all()
        if body.room_id not in [x.data.get('switch_room_id') for x in rooms]:
            raise HTTPException(422, 'Map the Switch room in this organization first')
    row = Workflow(org_id=p.org_id, owner_id=p.user.id, **body.model_dump())
    db.add(row)
    await db.flush()
    db.add(WorkflowEvent(org_id=p.org_id, workflow_id=row.id, kind='CREATED', message='Business request saved. Waiting for Switch dispatch.'))
    if idempotency_key:
        db.add(Idempotency(org_id=p.org_id, key=idempotency_key, request_hash=hashed, resource_id=row.id))
    audit(db, p.org_id, p.user.id, 'workflow.created', row.id)
    await db.commit()
    return serialize(row)


@router.get('/requests')
@router.get('/workflows')
async def workflows(status: str = '', q: str = '', p: Principal = Auth, db: AsyncSession = Db):
    query = select(Workflow).where(Workflow.org_id == p.org_id)
    if status:
        query = query.where(Workflow.status == status)
    if q:
        query = query.where(Workflow.title.ilike(f'%{q}%'))
    return [serialize(x) for x in (await db.scalars(query.order_by(Workflow.created_at.desc()).limit(200))).all()]


@router.get('/workflows/{id}')
async def workflow_detail(id: str, p: Principal = Auth, db: AsyncSession = Db):
    row = await owned(db, Workflow, id, p.org_id)
    events = (await db.scalars(select(WorkflowEvent).where(WorkflowEvent.workflow_id == id).order_by(WorkflowEvent.created_at))).all()
    documents = (await db.scalars(select(Document).where(Document.workflow_id == id).order_by(Document.version.desc()))).all()
    approvals = (await db.scalars(select(Approval).where(Approval.workflow_id == id))).all()
    return {**serialize(row), 'events': [serialize(x) for x in events], 'documents': [serialize(x) for x in documents], 'approvals': [serialize(x) for x in approvals]}


@router.post('/workflows/{id}/{action}')
async def workflow_action(id: str, action: str, p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    row = await owned(db, Workflow, id, p.org_id)
    if action == 'cancel':
        if row.status in {'APPROVED', 'EXECUTING'}:
            raise HTTPException(409, 'An authorized action may be executing; inspect delivery before cancellation')
        transition(db, row, 'CANCELLED', 'Cancelled by human')
        for approval in (await db.scalars(select(Approval).where(Approval.workflow_id == id, Approval.status == 'PENDING'))).all():
            approval.status = 'CANCELLED'
    elif action == 'retry':
        if row.status not in {'BLOCKED', 'FAILED', 'NEEDS_INFORMATION'}:
            raise HTTPException(409, 'Only blocked or failed workflows can be retried')
        deliveries = await db.scalar(select(Delivery.id).join(Approval).where(Approval.workflow_id == id))
        if deliveries:
            raise HTTPException(409, 'A delivery attempt exists. Manual provider reconciliation is required.')
        resume_revision = row.context.get('revision_pending') and row.context.get('revision_request')
        row.status = 'DRAFTING' if resume_revision else 'CREATED'
        row.error = ''
        if not resume_revision:
            row.context = {}
        for approval in (await db.scalars(select(Approval).where(Approval.workflow_id == id, Approval.status.in_(['PENDING','APPROVED']), Approval.executed_at.is_(None)))).all():
            approval.status = 'CANCELLED'
        db.add(WorkflowEvent(org_id=p.org_id, workflow_id=id, kind='RETRY', message='Human requested a fresh collaboration attempt'))
    else:
        raise HTTPException(404, 'Unknown workflow action')
    audit(db, p.org_id, p.user.id, 'workflow.' + action, id)
    await db.commit()
    return serialize(row)


@router.get('/approvals')
async def approvals(p: Principal = Auth, db: AsyncSession = Db):
    rows = (await db.scalars(select(Approval).where(Approval.org_id == p.org_id).order_by(Approval.created_at.desc()).limit(200))).all()
    return [serialize(x) for x in rows]


@router.post('/approvals/{id}/decision')
async def approval_decision(id: str, body: Decision, p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin', 'manager')
    approval = await owned(db, Approval, id, p.org_id)
    await decide(db, approval, body.decision, body.reason, p)
    await db.refresh(approval)
    return serialize(approval)


@router.get('/agents')
async def agents(p: Principal = Auth, db: AsyncSession = Db):
    rows = (await db.scalars(select(Agent).where(Agent.org_id == p.org_id))).all()
    values = []
    for row in rows:
        item = serialize(row)
        if row.last_seen is None or (now() - row.last_seen.replace(tzinfo=timezone.utc)).total_seconds() > 8:
            item['status'] = 'disconnected' if row.switch_id else 'unconfigured'
        item['credential_configured'] = bool(row.encrypted_key)
        values.append(item)
    return values


@router.post('/agents/{id}/register')
async def register_agent(id: str, p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin')
    agent = await owned(db, Agent, id, p.org_id)
    integration = await db.scalar(select(Integration).where(Integration.org_id == p.org_id, Integration.kind == 'switch'))
    base = integration.config.get('server_url', '') if integration else settings().switch_server_url
    key = decrypt(integration.encrypted_secret) if integration and integration.encrypted_secret else settings().switch_registration_key
    if not base or not key:
        raise HTTPException(503, 'Configure Switch server and registration key first')
    # Validate encryption before creating an irreversible remote identity.
    encrypt('configuration-check')
    await SwitchAgentRegistry.register(base, key, agent)
    audit(db, p.org_id, p.user.id, 'agent.registered', id)
    await db.commit()
    # Persist the one-time key before any follow-up remote operation can fail.
    client = SwitchClient(base, agent.switch_id, decrypt(agent.encrypted_key))
    try:
        await client.operation('update_agent_detail', {'agent_id': agent.switch_id, 'addressing': 'owner_and_owner_agents'})
    except SwitchError:
        agent.error = 'Identity registered and key preserved. Set addressing to owner_and_owner_agents in Switch Console.'
        await db.commit()
    finally:
        await client.close()
    return serialize(agent)


@router.put('/agents/{id}/mapping')
async def map_agent(id: str, body: IntegrationInput, p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin')
    agent = await owned(db, Agent, id, p.org_id)
    allowed = {'switch_id', 'participant_id', 'rooms', 'model'}
    if set(body.config) - allowed:
        raise HTTPException(422, 'Unsupported agent mapping field')
    for k, v in body.config.items():
        if k == 'rooms' and (not isinstance(v, list) or not all(isinstance(x, str) for x in v)):
            raise HTTPException(422, 'rooms must be a list of room IDs')
        setattr(agent, k, v)
    if body.secret:
        agent.encrypted_key = encrypt(body.secret)
    agent.error = ''
    agent.status = 'disconnected'
    audit(db, p.org_id, p.user.id, 'agent.mapping.updated', id)
    await db.commit()
    return serialize(agent)


@router.get('/integrations')
@router.get('/models')
async def integrations(p: Principal = Auth, db: AsyncSession = Db):
    rows = (await db.scalars(select(Integration).where(Integration.org_id == p.org_id))).all()
    return [{**serialize(x), 'has_secret': bool(x.encrypted_secret)} for x in rows]


@router.put('/integrations/{kind}')
async def save_integration(kind: str, body: IntegrationInput, p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin')
    if kind not in {'switch', 'model', 'google'}:
        raise HTTPException(422, 'Supported configurations: switch, model, google')
    allowed = {'switch': {'server_url'}, 'model': {'provider', 'base_url', 'model', 'timeout', 'allow_external_private_data'}, 'google': set()}[kind]
    if set(body.config) - allowed:
        raise HTTPException(422, 'Unsupported configuration field')
    # Endpoints are trusted administrator configuration only; agents and members cannot provide URLs.
    for key in ('server_url', 'base_url'):
        if key in body.config and not str(body.config[key]).startswith(('http://', 'https://')):
            raise HTTPException(422, 'Endpoint must use HTTP or HTTPS')
    row = await db.scalar(select(Integration).where(Integration.org_id == p.org_id, Integration.kind == kind))
    if not row:
        row = Integration(org_id=p.org_id, kind=kind)
        db.add(row)
    row.config = body.config
    if body.secret is not None:
        row.encrypted_secret = encrypt(body.secret) if body.secret else ''
    audit(db, p.org_id, p.user.id, 'integration.updated', kind)
    await db.commit()
    return {**serialize(row), 'has_secret': bool(row.encrypted_secret)}


@router.post('/integrations/{kind}/test')
async def test_integration(kind: str, p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin')
    row = await db.scalar(select(Integration).where(Integration.org_id == p.org_id, Integration.kind == kind))
    try:
        if kind == 'switch':
            client = SwitchClient(row.config.get('server_url', '') if row else settings().switch_server_url)
            try:
                return {'available': True, 'detail': await client.health()}
            finally:
                await client.close()
        if kind == 'model':
            return await ModelAdapter(row.config if row else {}, decrypt(row.encrypted_secret) if row and row.encrypted_secret else '').probe()
    except Exception as exc:
        raise HTTPException(503, f'Connection test failed: {type(exc).__name__}')
    raise HTTPException(422, 'Connection test is not supported for this integration')


@router.get('/switch/status')
async def switch_status(p: Principal = Auth, db: AsyncSession = Db):
    row = await db.scalar(select(Integration).where(Integration.org_id == p.org_id, Integration.kind == 'switch'))
    url = row.config.get('server_url', '') if row else settings().switch_server_url
    agents = (await db.scalars(select(Agent).where(Agent.org_id == p.org_id))).all()
    live = sum(1 for a in agents if a.status == 'connected' and a.last_seen and (now() - a.last_seen.replace(tzinfo=timezone.utc)).total_seconds() < 8)
    return {'configured': bool(url), 'connected_agents': live, 'status': 'connected' if live else 'disconnected',
            'server_url': url, 'message': 'Collaboration is live' if live else 'New handoffs pause until Switch and the agent runtime are connected'}


RESOURCE_KINDS = {'tasks', 'calendar', 'inbox', 'interactions', 'notifications', 'rooms', 'comments'}


async def validate_record(db, kind, body, p, existing=None):
    can_write(p)
    if kind == 'rooms':
        require(p, 'owner', 'admin')
        if not body.data.get('switch_room_id'):
            raise HTTPException(422, 'A genuine Switch room ID is required')
        url = body.data.get('url', '')
        if url and not url.startswith(('http://', 'https://')):
            raise HTTPException(422, 'Room link must use HTTP or HTTPS')
    if len(json.dumps(body.data)) > 100000:
        raise HTTPException(413, 'Record data exceeds limit')
    for field, cls in [('customer_id', Customer), ('workflow_id', Workflow)]:
        if body.data.get(field):
            await owned(db, cls, body.data[field], p.org_id)
    if kind == 'tasks':
        if body.status not in {'open', 'in_progress', 'blocked', 'done', 'cancelled'}:
            raise HTTPException(422, 'Invalid task status')
        if existing and existing.status in {'done', 'cancelled'} and body.status != existing.status:
            raise HTTPException(409, 'Completed or cancelled tasks cannot be reopened')
        for task_id in body.data.get('dependencies', []):
            dependency = await owned(db, Record, task_id, p.org_id)
            if dependency.kind != 'tasks' or (existing and dependency.id == existing.id):
                raise HTTPException(422, 'Invalid task dependency')
            if body.status == 'done' and dependency.status != 'done':
                raise HTTPException(409, 'Finish dependency tasks before completing this task')
    if kind == 'comments':
        if not body.data.get('task_id'):
            raise HTTPException(422, 'A task ID is required for a comment')
        task = await owned(db, Record, body.data['task_id'], p.org_id)
        if task.kind != 'tasks':
            raise HTTPException(422, 'Comments must reference a task')
        body.data['author_id'] = p.user.id
    if kind == 'calendar':
        try:
            start, end = [datetime.fromisoformat(body.data[k].replace('Z', '+00:00')) for k in ('start', 'end')]
            if start.tzinfo is None or end.tzinfo is None or end <= start:
                raise ValueError()
        except Exception:
            raise HTTPException(422, 'Calendar requires timezone-aware start and end, with end after start')
        rows = (await db.scalars(select(Record).where(Record.org_id == p.org_id, Record.kind == 'calendar', Record.status != 'cancelled'))).all()
        for row in rows:
            if existing and row.id == existing.id:
                continue
            if datetime.fromisoformat(row.data['start']) < end and datetime.fromisoformat(row.data['end']) > start:
                raise HTTPException(409, 'This time conflicts with an internal event')
        body.data['external_availability'] = 'unknown'
    return body


@router.get('/resources/{kind}')
async def list_records(kind: str, q: str = '', p: Principal = Auth, db: AsyncSession = Db):
    if kind not in RESOURCE_KINDS:
        raise HTTPException(404, 'Unknown resource')
    query = select(Record).where(Record.org_id == p.org_id, Record.kind == kind)
    if q:
        query = query.where(Record.title.ilike(f'%{q}%'))
    return [serialize(x) for x in (await db.scalars(query.order_by(Record.created_at.desc()).limit(500))).all()]


@router.post('/resources/{kind}', status_code=201)
async def create_record(kind: str, body: RecordInput, p: Principal = Auth, db: AsyncSession = Db):
    if kind not in RESOURCE_KINDS - {'notifications'}:
        raise HTTPException(404, 'Unknown resource')
    await validate_record(db, kind, body, p)
    row = Record(org_id=p.org_id, kind=kind, **body.model_dump())
    db.add(row)
    await db.flush()
    audit(db, p.org_id, p.user.id, kind + '.created', row.id)
    await db.commit()
    return serialize(row)


@router.put('/resources/{kind}/{id}')
async def update_record(kind: str, id: str, body: RecordInput, p: Principal = Auth, db: AsyncSession = Db):
    row = await owned(db, Record, id, p.org_id)
    if row.kind != kind or kind not in RESOURCE_KINDS:
        raise HTTPException(404, 'Record not found')
    if kind == 'notifications':
        if body.status != 'read' or body.title != row.title or body.data != row.data:
            raise HTTPException(422, 'Notifications may only be marked read')
    else:
        await validate_record(db, kind, body, p, row)
    row.title, row.status, row.data = body.title, body.status, body.data
    if kind == 'tasks' and body.status == 'done':
        row.data = {**row.data, 'completed_at': now().isoformat()}
    audit(db, p.org_id, p.user.id, kind + '.updated', id)
    await db.commit()
    return serialize(row)


@router.delete('/resources/{kind}/{id}')
async def delete_record(kind: str, id: str, p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    if kind == 'rooms':
        require(p, 'owner', 'admin')
    row = await owned(db, Record, id, p.org_id)
    if row.kind != kind or kind not in RESOURCE_KINDS:
        raise HTTPException(404, 'Record not found')
    row.status = 'cancelled'
    audit(db, p.org_id, p.user.id, kind + '.cancelled', id)
    await db.commit()
    return {'ok': True}


@router.get('/calendar/{id}/ics')
async def calendar_ics(id: str, p: Principal = Auth, db: AsyncSession = Db):
    row = await owned(db, Record, id, p.org_id)
    if row.kind != 'calendar':
        raise HTTPException(404, 'Event not found')
    def stamp(value):
        return datetime.fromisoformat(value).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    title = row.title.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '').replace(',', '\\,').replace(';', '\\;')
    content = '\r\n'.join(['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//SwitchOps AI//EN', 'BEGIN:VEVENT', f'UID:{row.id}@switchops',
        f'DTSTAMP:{stamp(now().isoformat())}', f'DTSTART:{stamp(row.data["start"])}', f'DTEND:{stamp(row.data["end"])}',
        f'SUMMARY:{title}', 'END:VEVENT', 'END:VCALENDAR', ''])
    return Response(content, media_type='text/calendar', headers={'Content-Disposition': 'attachment; filename=event.ics'})


@router.get('/documents')
async def documents(p: Principal = Auth, db: AsyncSession = Db):
    return [serialize(x) for x in (await db.scalars(select(Document).where(Document.org_id == p.org_id).order_by(Document.created_at.desc()).limit(200))).all()]


@router.put('/documents/{id}')
async def edit_document(id: str, body: DocumentEdit, p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    original = await owned(db, Document, id, p.org_id)
    workflow = await owned(db, Workflow, original.workflow_id, p.org_id)
    if workflow.status in {'APPROVED', 'EXECUTING', 'COMPLETED'}:
        raise HTTPException(409, 'Approved documents are immutable; start a new workflow for a new action')
    latest = await db.scalar(select(func.max(Document.version)).where(Document.workflow_id == workflow.id))
    doc = Document(org_id=p.org_id, workflow_id=workflow.id, title=original.title, content=body.content, version=latest+1)
    db.add(doc)
    for old in (await db.scalars(select(Approval).where(Approval.workflow_id == workflow.id, Approval.status == 'PENDING'))).all():
        old.status = 'CANCELLED'
    workflow.status = 'DRAFTING'
    workflow.context = {**workflow.context, 'manual_document': body.content, 'revision_pending': True}
    audit(db, p.org_id, p.user.id, 'document.version.created', id)
    await db.commit()
    return serialize(doc)


@router.get('/documents/{id}/download')
async def download_document(id: str, format: str = 'md', p: Principal = Auth, db: AsyncSession = Db):
    doc = await owned(db, Document, id, p.org_id)
    if format == 'md':
        return Response(doc.content, media_type='text/markdown', headers={'Content-Disposition': f'attachment; filename=proposal-v{doc.version}.md'})
    if format != 'pdf':
        raise HTTPException(422, 'Supported formats: md, pdf')
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib import colors
    from xml.sax.saxutils import escape
    out = io.BytesIO()
    styles = getSampleStyleSheet()
    styles['Title'].textColor = colors.HexColor('#155e49')
    story = [Paragraph('SWITCHOPS AI', styles['Title']), Paragraph(escape(doc.title), styles['Heading1']),
             Paragraph(f'Version {doc.version} · Generated {doc.created_at:%Y-%m-%d}', styles['Normal']), Spacer(1, 24)]
    for line in doc.content.splitlines():
        if line.strip():
            story.append(Paragraph(escape(line.lstrip('# ')), styles['Heading2'] if line.startswith('#') else styles['BodyText']))
            story.append(Spacer(1, 8))
    SimpleDocTemplate(out, title=doc.title, author='SwitchOps AI', rightMargin=50, leftMargin=50).build(story)
    return Response(out.getvalue(), media_type='application/pdf', headers={'Content-Disposition': f'attachment; filename=proposal-v{doc.version}.pdf'})


@router.get('/knowledge')
async def knowledge(p: Principal = Auth, db: AsyncSession = Db):
    rows = (await db.scalars(select(Knowledge).where(Knowledge.org_id == p.org_id))).all()
    return [{**serialize(x), 'characters': len(x.text), 'text': x.text[:500]} for x in rows]


@router.post('/knowledge/upload', status_code=201)
async def upload_knowledge(file: UploadFile = File(), p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    data = await file.read(settings().upload_max_bytes + 1)
    text = await asyncio.to_thread(extract, file.filename or '', data)
    doc = Knowledge(org_id=p.org_id, title=(file.filename or 'Document')[:200], filename=(file.filename or '')[:200], text=text)
    db.add(doc)
    await db.flush()
    doc.object_key = await put_private(f'{p.org_id}/knowledge/{doc.id}', data, 'application/octet-stream')
    await index_document(db, doc)
    audit(db, p.org_id, p.user.id, 'knowledge.uploaded', doc.id)
    await db.commit()
    return {**serialize(doc), 'text': doc.text[:500]}


@router.get('/knowledge/search')
async def search_knowledge(q: str, p: Principal = Auth, db: AsyncSession = Db):
    return await knowledge_search(db, p.org_id, q[:2000])


@router.delete('/knowledge/{id}')
async def delete_knowledge(id: str, p: Principal = Auth, db: AsyncSession = Db):
    can_write(p)
    row = await owned(db, Knowledge, id, p.org_id)
    await delete_private(row.object_key)
    await db.execute(delete(Chunk).where(Chunk.document_id == id, Chunk.org_id == p.org_id))
    await db.delete(row)
    audit(db, p.org_id, p.user.id, 'knowledge.deleted', id)
    await db.commit()
    return {'ok': True}


@router.get('/team')
@router.get('/users')
async def team(p: Principal = Auth, db: AsyncSession = Db):
    rows = (await db.execute(select(User, Membership).join(Membership, User.id == Membership.user_id).where(Membership.org_id == p.org_id))).all()
    return [{**serialize(user), 'role': member.role, 'membership_id': member.id} for user, member in rows]


@router.post('/team/invite')
async def invite(body: RecordInput, p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin')
    email = str(body.data.get('email', '')).lower()
    role = body.data.get('role', 'member')
    from pydantic import TypeAdapter
    try:
        TypeAdapter(EmailStr).validate_python(email)
    except ValueError:
        raise HTTPException(422, 'A valid invitee email is required')
    if role not in {'admin', 'manager', 'member', 'viewer'} or (p.role != 'owner' and role == 'admin'):
        raise HTTPException(403, 'Cannot assign this role')
    token = secrets.token_urlsafe(32)
    row = Record(org_id=p.org_id, kind='invitations', title=email, status='pending',
                 data={'email': email, 'role': role, 'token_hash': digest(token), 'expires_at': (now()+timedelta(days=7)).isoformat()})
    db.add(row)
    audit(db, p.org_id, p.user.id, 'team.invited', email)
    await db.commit()
    return {'invitation_token': token, 'expires_at': row.data['expires_at'], 'note': 'Share this one-time token securely. No email has been sent.'}


@router.post('/team/accept')
async def accept_invite(body: RecordInput, p: Principal = Auth, db: AsyncSession = Db):
    rows = (await db.scalars(select(Record).where(Record.kind == 'invitations', Record.status == 'pending', Record.title == p.user.email))).all()
    invite = next((x for x in rows if secrets.compare_digest(x.data['token_hash'], digest(body.data.get('token', '')))), None)
    if not invite or datetime.fromisoformat(invite.data['expires_at']) < now():
        raise HTTPException(404, 'Invitation is invalid or expired')
    if await db.scalar(select(Membership.id).where(Membership.org_id == invite.org_id, Membership.user_id == p.user.id)):
        raise HTTPException(409, 'Already a member')
    db.add(Membership(org_id=invite.org_id, user_id=p.user.id, role=invite.data['role']))
    invite.status = 'accepted'
    await db.commit()
    return {'org_id': invite.org_id}


@router.put('/team/{id}/role')
async def update_role(id: str, body: RecordInput, p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner')
    member = await owned(db, Membership, id, p.org_id)
    role = body.data.get('role')
    if role not in {'admin', 'manager', 'member', 'viewer'} or member.role == 'owner':
        raise HTTPException(422, 'Owner transfer is not supported; choose admin, manager, member or viewer')
    member.role = role
    await db.execute(delete(SessionToken).where(SessionToken.user_id == member.user_id, SessionToken.org_id == p.org_id))
    audit(db, p.org_id, p.user.id, 'team.role.changed', member.user_id, role=role)
    await db.commit()
    return {'ok': True}


@router.get('/settings')
async def get_settings(p: Principal = Auth, db: AsyncSession = Db):
    return serialize(await db.get(Organization, p.org_id))


@router.put('/settings')
async def save_settings(body: RecordInput, p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin')
    org = await db.get(Organization, p.org_id)
    allowed = {'timezone', 'retention_days', 'manual_minutes_per_workflow', 'human_identity_mappings', 'default_room_id'}
    if set(body.data) - allowed:
        raise HTTPException(422, 'Unsupported organization setting')
    if 'manual_minutes_per_workflow' in body.data and not 0 <= float(body.data['manual_minutes_per_workflow']) <= 1440:
        raise HTTPException(422, 'Manual time assumption must be between 0 and 1440 minutes')
    if 'retention_days' in body.data and not 7 <= int(body.data['retention_days']) <= 3650:
        raise HTTPException(422, 'Retention preference must be between 7 and 3650 days')
    org.name, org.settings = body.title, body.data
    audit(db, p.org_id, p.user.id, 'settings.updated', org.id)
    await db.commit()
    return serialize(org)


@router.get('/audit')
async def audit_log(p: Principal = Auth, db: AsyncSession = Db):
    return [serialize(x) for x in (await db.scalars(select(Audit).where(Audit.org_id == p.org_id).order_by(Audit.created_at.desc()).limit(250))).all()]


@router.get('/communications')
async def communications(p: Principal = Auth, db: AsyncSession = Db):
    return [serialize(x) for x in (await db.scalars(select(Delivery).where(Delivery.org_id == p.org_id).order_by(Delivery.created_at.desc()).limit(200))).all()]


@router.get('/analytics')
async def analytics(start: datetime | None = None, end: datetime | None = None, customer_id: str = '', agent: str = '', workflow_id: str = '', p: Principal = Auth, db: AsyncSession = Db):
    filters = [Workflow.org_id == p.org_id]
    if start: filters.append(Workflow.created_at >= start)
    if end: filters.append(Workflow.created_at <= end)
    if customer_id: filters.append(Workflow.customer_id == customer_id)
    if workflow_id: filters.append(Workflow.id == workflow_id)
    if agent:
        filters.append(Workflow.id.in_(select(Usage.workflow_id).where(Usage.org_id == p.org_id, Usage.agent == agent)))
    counts = dict((await db.execute(select(Workflow.status, func.count()).where(*filters).group_by(Workflow.status))).all())
    customers_count = await db.scalar(select(func.count()).select_from(Customer).where(Customer.org_id == p.org_id, Customer.archived == False))
    approvals_count = await db.scalar(select(func.count()).select_from(Approval).where(Approval.org_id == p.org_id, Approval.status == 'PENDING'))
    tasks = (await db.scalars(select(Record).where(Record.org_id == p.org_id, Record.kind == 'tasks'))).all()
    ids = select(Workflow.id).where(*filters)
    tokens = (await db.execute(select(func.coalesce(func.sum(Usage.input_tokens), 0), func.coalesce(func.sum(Usage.output_tokens), 0)).where(Usage.org_id == p.org_id, Usage.workflow_id.in_(ids)))).one()
    daily = (await db.execute(select(func.date(Workflow.created_at), Workflow.status, func.count()).where(*filters).group_by(func.date(Workflow.created_at), Workflow.status).order_by(func.date(Workflow.created_at)))).all()
    completed = (await db.scalars(select(Workflow).where(*filters, Workflow.status == 'COMPLETED'))).all()
    minutes = [(w.completed_at-w.created_at).total_seconds()/60 for w in completed if w.completed_at]
    decided = (await db.scalars(select(Approval).where(Approval.org_id == p.org_id, Approval.decided_at.is_not(None), Approval.workflow_id.in_(ids)))).all()
    turnarounds = [(a.decided_at-a.created_at).total_seconds()/60 for a in decided]
    org = await db.get(Organization, p.org_id)
    assumption = float(org.settings.get('manual_minutes_per_workflow', 30))
    agent_counts = (await db.execute(select(Usage.agent, func.count()).where(Usage.org_id == p.org_id, Usage.workflow_id.in_(ids)).group_by(Usage.agent))).all()
    overdue = 0
    for task in tasks:
        if task.status not in {'done','cancelled'} and task.data.get('due_at'):
            try:
                overdue += datetime.fromisoformat(task.data['due_at']).replace(tzinfo=timezone.utc) < now()
            except ValueError:
                pass
    return {'customers': customers_count, 'total_workflows': sum(counts.values()), 'completed': counts.get('COMPLETED', 0),
            'failed': counts.get('FAILED', 0), 'active_workflows': sum(n for s,n in counts.items() if s not in {'COMPLETED','FAILED','CANCELLED','REJECTED'}),
            'pending_approvals': approvals_count, 'tasks_in_progress': sum(x.status == 'in_progress' for x in tasks),
            'overdue_tasks': overdue, 'statuses': counts, 'input_tokens': tokens[0], 'output_tokens': tokens[1],
            'avg_completion_minutes': sum(minutes)/len(minutes) if minutes else None,
            'avg_approval_minutes': sum(turnarounds)/len(turnarounds) if turnarounds else None,
            'estimated_minutes_saved': max(0, len(completed)*assumption-sum(minutes)), 'time_saved_assumption_minutes': assumption,
            'estimated_cost': None, 'cost_note': 'No provider price configured; cost is not estimated.',
            'daily': [{'date': str(day), 'status': status, 'count': count} for day,status,count in daily],
            'agents': [{'agent': slug, 'executions': count} for slug,count in agent_counts]}


@router.get('/events')
async def events(request: Request, p: Principal = Auth):
    async def stream():
        last = ''
        for _ in range(360):
            if await request.is_disconnected(): break
            async with Session() as db:
                event = await db.scalar(select(Audit).where(Audit.org_id == p.org_id).order_by(Audit.created_at.desc()).limit(1))
                marker = event.id if event else ''
                if marker != last:
                    last = marker
                    yield 'event: update\ndata: ' + json.dumps({'audit_id': marker}) + '\n\n'
                else:
                    yield ': heartbeat\n\n'
            await asyncio.sleep(5)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@router.post('/demo/seed')
async def demo_seed(p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin')
    if await db.scalar(select(Customer.id).where(Customer.org_id == p.org_id, Customer.synthetic == True)):
        return {'ok': True, 'message': 'Synthetic dataset already exists'}
    for name, notes in [('Acme Solutions', 'Synthetic: Seeking customer onboarding automation. No pricing or delivery commitments approved.'),
                        ('Northstar Digital', 'Synthetic: Interested in coordinating client communications and project handoffs.'),
                        ('BrightPath Logistics', 'Synthetic: Needs a clearer internal follow-up process for customer requests.')]:
        customer = Customer(org_id=p.org_id, name=name, company=name, email=name.split()[0].lower()+'@example.test',
                            stage='qualified', tags=['Synthetic'], notes=notes, synthetic=True)
        db.add(customer)
    for title, status, priority in [('Review onboarding requirements', 'in_progress', 'high'), ('Prepare internal discovery questions', 'open', 'medium'), ('Confirm proposal review policy', 'done', 'medium')]:
        db.add(Record(org_id=p.org_id, kind='tasks', title=title, status=status, data={'synthetic': True, 'priority': priority, 'description': 'Synthetic planning task for exploring SwitchOps.'}))
    knowledge = Knowledge(org_id=p.org_id, title='Synthetic · Service capabilities', filename='synthetic-services.md',
        text='SYNTHETIC DEMO DATA. SwitchOps provides workflow discovery, customer process mapping, internal knowledge retrieval, proposal drafting and human approval controls. Pricing, scope and delivery dates require a separate signed agreement. Never promise a specific ROI without evidence.')
    db.add(knowledge)
    await db.flush()
    await index_document(db, knowledge)
    audit(db, p.org_id, p.user.id, 'demo.synthetic_data_seeded')
    await db.commit()
    return {'ok': True, 'message': 'Clearly labeled synthetic CRM, tasks and knowledge created. No simulated agent execution or analytics.'}


@router.get('/switch/events')
async def failed_switch_events(status: str = 'failed', p: Principal = Auth, db: AsyncSession = Db):
    require(p, 'owner', 'admin', 'manager')
    rows=(await db.scalars(select(SwitchReceipt).where(SwitchReceipt.org_id==p.org_id,SwitchReceipt.status==status)
                         .order_by(SwitchReceipt.created_at.desc()).limit(200))).all()
    return [{'id':r.id,'agent_id':r.agent_id,'sequence':r.sequence,'status':r.status,'attempts':r.attempts,
             'error':r.error,'created_at':r.created_at} for r in rows]


def mount_collection(kind):
    """Conventional route aliases share exactly the same validation and authorization."""
    async def listing(q: str = '', p: Principal = Auth, db: AsyncSession = Db):
        return await list_records(kind, q, p, db)
    async def creating(body: RecordInput, p: Principal = Auth, db: AsyncSession = Db):
        return await create_record(kind, body, p, db)
    async def updating(id: str, body: RecordInput, p: Principal = Auth, db: AsyncSession = Db):
        return await update_record(kind, id, body, p, db)
    async def deleting(id: str, p: Principal = Auth, db: AsyncSession = Db):
        return await delete_record(kind, id, p, db)
    router.add_api_route('/'+kind,listing,methods=['GET'],name=kind+'_list')
    if kind!='notifications':
        router.add_api_route('/'+kind,creating,methods=['POST'],status_code=201,name=kind+'_create')
        router.add_api_route('/'+kind+'/{id}',deleting,methods=['DELETE'],name=kind+'_cancel')
    router.add_api_route('/'+kind+'/{id}',updating,methods=['PUT'],name=kind+'_update')


for collection in ['tasks','calendar','rooms','inbox','interactions','notifications']:
    mount_collection(collection)
