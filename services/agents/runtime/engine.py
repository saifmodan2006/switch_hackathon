"""Business work runs only from an authenticated Switch event or a durable human request.
The only way one specialist wakes the next is an addressed Switch room message.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from app.db.session import Session
from app.models.domain import *
from app.security.auth import decrypt
from app.core.config import settings
from app.integrations.switch import SwitchClient, SwitchError
from app.integrations.model import ModelAdapter
from app.services.workflows import transition, audit, payload_hash
from app.services.knowledge import search
from app.services.approvals import execute
from app.integrations.storage import put_private
from agents.agents.definitions import AGENT_MAP, COMMON_POLICY, PIPELINE, ALLOWED_PREDECESSOR

log = logging.getLogger('switchops.runtime')
PREFIX = 'SWITCHOPS_HANDOFF '


async def integration(db, org_id, kind):
    return await db.scalar(select(Integration).where(Integration.org_id == org_id, Integration.kind == kind))


async def client_for(db, agent):
    config = await integration(db, agent.org_id, 'switch')
    url = config.config.get('server_url', '') if config else settings().switch_server_url
    if not url or not agent.switch_id or not agent.encrypted_key:
        raise SwitchError('Configure Switch endpoint and register or map this agent')
    return SwitchClient(url, agent.switch_id, decrypt(agent.encrypted_key), agent.connection_id)


async def model_for(db, agent):
    config = await integration(db, agent.org_id, 'model')
    values = dict(config.config) if config else {}
    if agent.model:
        values['model'] = agent.model
    return ModelAdapter(values, decrypt(config.encrypted_secret) if config and config.encrypted_secret else '')


async def handoff(db, workflow, sender, target_slug, purpose):
    if workflow.handoffs >= settings().max_handoffs:
        raise RuntimeError('Handoff budget exhausted; human review required')
    target = await db.scalar(select(Agent).where(Agent.org_id == workflow.org_id, Agent.slug == target_slug))
    if not target or workflow.room_id not in target.rooms:
        raise SwitchError(f'{target_slug} is not mapped to this Switch room')
    await db.refresh(target)
    if target.status != 'connected' or not target.last_seen or (now()-target.last_seen.replace(tzinfo=timezone.utc)).total_seconds()>8:
        raise SwitchError(f'{target_slug} is disconnected; the handoff is paused rather than sent into an unclaimed room')
    if not target.participant_id or not sender.participant_id:
        raise SwitchError('Map verified Switch participant IDs for both agents before allowing handoffs')
    client = await client_for(db, sender)
    envelope = {'workflow_id': workflow.id, 'target': target_slug, 'purpose': purpose,
                'handoff': workflow.handoffs + 1}
    try:
        result = await client.post(workflow.room_id, f'@{target.slug} {purpose}\n{PREFIX}{json.dumps(envelope)}')
    finally:
        await client.close()
    workflow.handoffs += 1
    workflow.context = {**workflow.context, 'expected_agent': target_slug, 'expected_handoff': workflow.handoffs,
                        'expected_sender': sender.slug,
                        'awaiting_since': now().isoformat()}
    db.add(WorkflowEvent(org_id=workflow.org_id, workflow_id=workflow.id, kind='HANDOFF', agent=sender.slug,
                         message=f'{sender.slug} → {target_slug}: {purpose}', data={'switch_response': result, 'handoff': workflow.handoffs}))
    audit(db, workflow.org_id, sender.slug, 'switch.handoff', workflow.id, target=target_slug)


async def context_for(db, workflow, agent):
    context = {'workflow_id': workflow.id, 'request': workflow.request, 'prior_findings': workflow.context.get('findings', {}),
               'revision_request': workflow.context.get('revision_request', ''), 'manual_document': workflow.context.get('manual_document', '')}
    if agent.slug in {'ops-coordinator', 'customer-intelligence', 'quality-reviewer'} and workflow.customer_id:
        customer = await db.get(Customer, workflow.customer_id)
        context['customer'] = {'id': customer.id, 'name': customer.name, 'company': customer.company, 'notes': customer.notes,
                               'stage': customer.stage, 'synthetic': customer.synthetic}
        interactions = (await db.scalars(select(Record).where(Record.org_id == workflow.org_id, Record.kind == 'interactions'))).all()
        context['interactions'] = [{'id': r.id, 'title': r.title, 'data': r.data} for r in interactions if r.data.get('customer_id') == customer.id]
    if agent.slug in {'research-specialist','quality-reviewer'}:
        context['knowledge'] = await search(db, workflow.org_id, workflow.request)
        context['external_research'] = 'Unavailable: no public research integration configured'
    if agent.slug in {'communications-specialist','quality-reviewer'}:
        proposal=await db.scalar(select(Document).where(Document.workflow_id==workflow.id,Document.org_id==workflow.org_id).order_by(Document.version.desc()).limit(1))
        if proposal:
            context['actual_saved_proposal']={'id':proposal.id,'version':proposal.version,'content':proposal.content}
    switch=await client_for(db,agent)
    try:
        room=await switch.operation('get_room_detail',{'room_id':workflow.room_id})
        context['shared_switch_room']={'id':workflow.room_id,'name':room.get('name'),'instructions':room.get('instructions','')}
    finally:
        await switch.close()
    if agent.slug == 'scheduling-specialist':
        context['external_availability'] = 'Unknown; internal scheduling only'
    return context


async def run_specialist(db, workflow, agent):
    if workflow.status in {'COMPLETED','CANCELLED','REJECTED','FAILED','BLOCKED'}:
        return
    if workflow.model_calls >= settings().max_model_calls:
        raise RuntimeError('Model-call budget exhausted')
    model = await model_for(db, agent)
    context = await context_for(db, workflow, agent)
    workflow.model_calls += 1
    # Budget persists before inference, including failed calls.
    await db.commit()
    output, usage = await model.generate(COMMON_POLICY + '\n' + AGENT_MAP[agent.slug][2], context)
    await db.refresh(workflow)  # Observe cancellation while inference was running.
    if workflow.status in {'CANCELLED', 'REJECTED'}:
        return
    db.add(Usage(org_id=workflow.org_id, workflow_id=workflow.id, agent=agent.slug, model=model.model, **usage))
    findings = {**workflow.context.get('findings', {}), agent.slug: output.model_dump()}
    workflow.context = {**workflow.context, 'findings': findings}
    client = await client_for(db, agent)
    try:
        await client.post(workflow.room_id, f'Workflow {workflow.id}\n{output.summary}\nSources: {", ".join(output.citations) or "No cited sources"}')
    finally:
        await client.close()
    db.add(WorkflowEvent(org_id=workflow.org_id, workflow_id=workflow.id, kind='FINDING', agent=agent.slug,
                         message=output.summary, data={'citations': output.citations, 'confidence': output.confidence}))
    if output.needs_information or output.confidence < 0.5:
        transition(db, workflow, 'NEEDS_INFORMATION', 'Specialist needs human clarification: ' + output.summary, agent.slug)
        return
    slug = agent.slug
    if slug == 'ops-coordinator':
        if workflow.context.get('finalizing'):
            transition(db, workflow, 'COMPLETED', 'Approved proposal accepted by SMTP; internal follow-up saved. External delivery is not confirmed.', slug)
        else:
            transition(db, workflow, 'RESEARCHING', 'Coordinator triaged the request', slug)
            await handoff(db, workflow, agent, 'customer-intelligence', 'Retrieve authorized customer context')
    elif slug == 'customer-intelligence':
        await handoff(db, workflow, agent, 'research-specialist', 'Research internal evidence and cite documents')
    elif slug == 'research-specialist':
        transition(db, workflow, 'DRAFTING', 'Research is ready for proposal drafting', slug)
        await handoff(db, workflow, agent, 'communications-specialist', 'Draft a grounded proposal for human review')
    elif slug == 'communications-specialist':
        if not output.content:
            raise RuntimeError('Communications returned no proposal content')
        version = ((await db.scalar(select(func.max(Document.version)).where(Document.workflow_id == workflow.id))) or 0) + 1
        content = workflow.context.get('manual_document') or output.content
        doc = Document(org_id=workflow.org_id, workflow_id=workflow.id, title=workflow.title, content=content, version=version)
        db.add(doc)
        await db.flush()
        doc.object_key = await put_private(f'{workflow.org_id}/proposals/{workflow.id}/v{version}.md', content.encode(), 'text/markdown')
        workflow.context = {**workflow.context, 'proposal_id': doc.id, 'revision_pending': False}
        transition(db, workflow, 'REVIEWING', f'Proposal v{version} saved for quality review', slug)
        await handoff(db, workflow, agent, 'quality-reviewer', 'Check proposal claims against supplied evidence')
    elif slug == 'quality-reviewer':
        if output.issues:
            rounds=workflow.context.get('quality_revision_rounds',0)
            if rounds<2:
                workflow.context={**workflow.context,'quality_revision_rounds':rounds+1,
                    'revision_request':'Quality review requires corrections: '+'; '.join(output.issues),'revision_pending':False,'manual_document':''}
                transition(db,workflow,'DRAFTING','Quality requested a grounded revision: '+'; '.join(output.issues),slug)
                await handoff(db,workflow,agent,'communications-specialist','Revise the saved proposal to resolve quality findings')
            else:
                transition(db, workflow, 'NEEDS_INFORMATION', 'Quality revision budget exhausted: ' + '; '.join(output.issues), slug)
            return
        doc = await db.get(Document, workflow.context['proposal_id'])
        customer = await db.get(Customer, workflow.customer_id) if workflow.customer_id else None
        if not customer or not customer.email or customer.opted_out:
            transition(db, workflow, 'NEEDS_INFORMATION', 'Set a permitted customer recipient before requesting send approval', slug)
            return
        payload = {'recipient': customer.email, 'subject': workflow.title, 'body': doc.content}
        approval = Approval(org_id=workflow.org_id, workflow_id=workflow.id, document_id=doc.id, version=doc.version,
                            payload=payload, payload_hash=payload_hash(payload), expires_at=now()+timedelta(days=3))
        db.add(approval)
        await db.flush()
        transition(db, workflow, 'AWAITING_APPROVAL', 'Quality review passed. Authorized human approval required.', slug)
        db.add(Record(org_id=workflow.org_id, kind='notifications', title='Proposal ready for review',
                      data={'workflow_id': workflow.id, 'approval_id': approval.id}))
        client = await client_for(db, agent)
        try:
            await client.post(workflow.room_id, f'Human approval required: {settings().frontend_url}/approvals\nWorkflow {workflow.id}; proposal version {doc.version}. Nothing has been sent.')
            approval_rooms=(await db.scalars(select(Record).where(Record.org_id==workflow.org_id,Record.kind=='rooms',Record.title=='approvals',Record.status!='cancelled'))).all()
            for room in approval_rooms:
                room_id=room.data.get('switch_room_id')
                if room_id in agent.rooms and room_id!=workflow.room_id:
                    await client.post(room_id,f'Human review requested for workflow {workflow.id}, proposal v{doc.version}: {settings().frontend_url}/approvals')
        finally:
            await client.close()
    elif slug == 'scheduling-specialist':
        due = now()+timedelta(days=3)
        db.add(Record(org_id=workflow.org_id, kind='tasks', title='Follow up: ' + workflow.title[:150],
            data={'workflow_id': workflow.id, 'customer_id': workflow.customer_id, 'due_at': due.isoformat(),
                  'assigned_agent': slug, 'description': output.summary, 'external_availability': 'unknown'}))
        db.add(Record(org_id=workflow.org_id, kind='calendar', title='Internal follow-up: ' + workflow.title[:140],
            data={'workflow_id': workflow.id, 'start': due.isoformat(), 'end': (due+timedelta(minutes=15)).isoformat(),
                  'external_availability': 'unknown', 'invitation_sent': False}))
        workflow.context = {**workflow.context, 'finalizing': True}
        await handoff(db, workflow, agent, 'ops-coordinator', 'Summarize the persisted outcome and internal follow-up')
    audit(db, workflow.org_id, slug, 'agent.completed', workflow.id)


async def process_receipt(receipt_id):
    async with Session() as db:
        receipt = await db.get(SwitchReceipt, receipt_id)
        if not receipt or receipt.status != 'pending': return
        agent = await db.get(Agent, receipt.agent_id)
        agent_org_id, agent_slug = agent.org_id, agent.slug
        event = receipt.payload
        payload = event.get('payload', {})
        if event.get('type') != 'message' or payload.get('addressed') is not True or event.get('room_id') not in agent.rooms:
            receipt.status = 'ignored'
            await db.commit()
            return
        body, sender = payload.get('body', ''), payload.get('sender', '')
        workflow = None
        workflow_id = None
        try:
            if PREFIX in body:
                envelope = json.loads(body.split(PREFIX, 1)[1].split('\n',1)[0])
                workflow = await db.scalar(select(Workflow).where(Workflow.id == envelope['workflow_id'], Workflow.org_id == agent.org_id))
                workflow_id = workflow.id if workflow else None
                predecessor_slug = ALLOWED_PREDECESSOR[agent.slug]
                expected_sender=workflow.context.get('expected_sender') if workflow else None
                allowed={predecessor_slug}
                if agent.slug=='communications-specialist':allowed.update({'ops-coordinator','quality-reviewer'})
                if expected_sender in allowed:predecessor_slug=expected_sender
                predecessor = await db.scalar(select(Agent).where(Agent.org_id == agent.org_id, Agent.slug == predecessor_slug))
                if not workflow or not predecessor or not predecessor.participant_id or sender != predecessor.participant_id:
                    raise PermissionError('Unverified agent sender')
                if workflow.room_id != event['room_id'] or envelope.get('target') != agent.slug:
                    raise PermissionError('Room or recipient mismatch')
                if workflow.context.get('expected_agent') != agent.slug or envelope.get('handoff') != workflow.context.get('expected_handoff'):
                    receipt.status = 'ignored'
                    await db.commit()
                    return
                await run_specialist(db, workflow, agent)
            elif agent.slug == 'ops-coordinator':
                org = await db.get(Organization, agent.org_id)
                user_id = org.settings.get('human_identity_mappings', {}).get(sender)
                member = await db.scalar(select(Membership).where(Membership.user_id == user_id, Membership.org_id == agent.org_id)) if user_id else None
                if not member or member.role == 'viewer':
                    raise PermissionError('Human Switch identity has no authorized application mapping')
                candidates = (await db.scalars(select(Customer).where(Customer.org_id == agent.org_id, Customer.archived == False))).all()
                matches = [c for c in candidates if c.name.casefold() in body.casefold() or (c.company and c.company.casefold() in body.casefold())]
                customer = matches[0] if len(matches) == 1 else None
                workflow = Workflow(org_id=agent.org_id, owner_id=user_id, title=body[:120], request=body,
                                    room_id=event['room_id'], customer_id=customer.id if customer else None,
                                    status='CREATED' if customer else 'NEEDS_INFORMATION',
                                    error='' if customer else 'No unambiguous CRM customer matched. Create a dashboard request with the selected customer.')
                db.add(workflow)
                await db.flush()
                db.add(WorkflowEvent(org_id=agent.org_id, workflow_id=workflow.id, kind='SWITCH_REQUEST',
                    message=body, switch_event_id=str(receipt.sequence), agent=agent.slug))
                audit(db, agent.org_id, user_id, 'switch.human_request_received', workflow.id)
            receipt.status = 'processed'
            receipt.error = ''
            await db.commit()
        except Exception as exc:
            await db.rollback()
            receipt = await db.get(SwitchReceipt, receipt_id)
            receipt.status = 'failed'
            receipt.error = f'{type(exc).__name__}: {exc}'[:1000]
            receipt.attempts += 1
            if workflow_id and not isinstance(exc, PermissionError):
                persisted = await db.get(Workflow, workflow_id)
                if persisted and persisted.status not in {'COMPLETED','CANCELLED','REJECTED','BLOCKED'}:
                    persisted.error = receipt.error
                    transition(db, persisted, 'BLOCKED', receipt.error, agent_slug)
            audit(db, agent_org_id, agent_slug, 'agent.event_failed', receipt.id, error=receipt.error)
            await db.commit()
            log.exception('Agent event failed', extra={'receipt_id': receipt_id})


async def listen_agent(agent_id):
    delay = 1
    while True:
        async with Session() as db:
            agent = await db.get(Agent, agent_id)
            if not agent or not agent.rooms or agent.status in {'gap','stopped','refused'}: return
            try:
                client = await client_for(db, agent)
            except SwitchError:
                return
            rooms, cursor, generation = agent.rooms, agent.cursor, agent.generation

        async def on_state(kind, data):
            async with Session() as db:
                row = await db.get(Agent, agent_id)
                if kind in {'connected','cursor'}:
                    row.status, row.last_seen = 'connected', now()
                    row.cursor = data.get('cursor', row.cursor)
                    row.generation = data.get('generation', row.generation)
                    if kind == 'connected': row.rooms = data['rooms']
                    row.error = ''
                elif kind in {'gap','stopped','refused'}:
                    row.status, row.error = kind, json.dumps(data)
                elif kind == 'subscription_changed': row.rooms = data['rooms']
                await db.commit()

        async def on_event(sequence, data):
            async with Session() as db:
                existing = await db.scalar(select(SwitchReceipt.id).where(SwitchReceipt.agent_id == agent_id, SwitchReceipt.sequence == sequence))
                if not existing:
                    db.add(SwitchReceipt(org_id=agent.org_id, agent_id=agent_id, sequence=sequence, payload=data))
                    await db.commit()

        # Ping handling updates liveness even with no room messages.
        original_state = on_state
        async def state_with_heartbeat(kind, data):
            await original_state(kind, data)
        try:
            await client.listen(rooms, cursor, generation, state_with_heartbeat, on_event)
            return
        except Exception as exc:
            async with Session() as db:
                row = await db.get(Agent, agent_id)
                if row.status in {'gap','stopped','refused'}: return
                close = getattr(exc, 'rcvd', None)
                if close and close.code in {4401,4403,4409}:
                    row.status, row.error = 'refused', f'Switch refused connection ({close.code}); inspect credentials, room access or generation fencing'
                    await db.commit()
                    return
                row.status, row.error = 'disconnected', f'{type(exc).__name__}: {exc}'[:500]
                await db.commit()
            await asyncio.sleep(delay)
            delay = min(delay*2, 60)
        finally:
            await client.close()


async def dispatch_pending():
    async with Session() as db:
        rows = (await db.scalars(select(Workflow).where(Workflow.status.in_(['CREATED', 'APPROVED', 'DRAFTING'])))).all()
        for workflow in rows:
            workflow_id = workflow.id
            if workflow.status == 'DRAFTING' and not workflow.context.get('revision_pending'): continue
            slug = 'communications-specialist' if workflow.status in {'APPROVED','DRAFTING'} else 'ops-coordinator'
            agent = await db.scalar(select(Agent).where(Agent.org_id == workflow.org_id, Agent.slug == slug))
            try:
                if not agent or agent.status != 'connected' or not agent.last_seen or (now()-agent.last_seen.replace(tzinfo=timezone.utc)).total_seconds() > 8:
                    raise SwitchError('Switch agent is disconnected. Collaboration is paused.')
                if not workflow.room_id:
                    org = await db.get(Organization, workflow.org_id)
                    workflow.room_id = org.settings.get('default_room_id', '')
                if not workflow.room_id or workflow.room_id not in agent.rooms:
                    raise SwitchError('Choose a mapped Switch room shared by the workflow agents')
                if workflow.status == 'CREATED':
                    client = await client_for(db, agent)
                    try:
                        await client.post(workflow.room_id, f'Business request {workflow.id}: {workflow.request}')
                    finally:
                        await client.close()
                    transition(db, workflow, 'TRIAGING', 'Request posted to genuine Switch room', agent.slug)
                    await run_specialist(db, workflow, agent)
                elif workflow.status == 'DRAFTING':
                    coordinator = await db.scalar(select(Agent).where(Agent.org_id == workflow.org_id, Agent.slug == 'ops-coordinator'))
                    await handoff(db, workflow, coordinator, slug, 'Revise proposal based on human feedback')
                    workflow.context = {**workflow.context, 'revision_pending': False}
                elif workflow.status == 'APPROVED':
                    approval = await db.scalar(select(Approval).where(Approval.workflow_id == workflow.id, Approval.status == 'APPROVED'))
                    # Communications execution is independent I/O, but all scheduling handoffs require live Switch.
                    delivery = await execute(db, approval.id)
                    if delivery.status in {'sandbox_accepted','smtp_accepted'}:
                        await handoff(db, workflow, agent, 'scheduling-specialist', 'Create an internal follow-up after the approved send attempt')
                await db.commit()
            except Exception as exc:
                await db.rollback()
                row = await db.get(Workflow, workflow_id)
                if row.status not in {'COMPLETED','CANCELLED','REJECTED','BLOCKED'}:
                    row.error = f'{type(exc).__name__}: {exc}'[:1000]
                    transition(db, row, 'BLOCKED', row.error, slug)
                    audit(db, row.org_id, slug, 'workflow.blocked', row.id, error=row.error)
                    await db.commit()


async def run_loop():
    logging.basicConfig(level=logging.INFO)
    import time
    started=time.monotonic()
    listeners = {}
    while True:
        async with Session() as db:
            agents = (await db.scalars(select(Agent).where(Agent.switch_id != '', Agent.encrypted_key != ''))).all()
            for agent in agents:
                if agent.id not in listeners or (listeners[agent.id].done() and agent.status not in {'gap','stopped','refused'}):
                    listeners[agent.id] = asyncio.create_task(listen_agent(agent.id))
            pending = (await db.scalars(select(SwitchReceipt.id).where(SwitchReceipt.status == 'pending').order_by(SwitchReceipt.created_at).limit(20))).all()
        for id in pending:
            await process_receipt(id)
        await maintenance()
        # Restore real sockets before dispatching durable work after a process restart.
        if time.monotonic()-started>10:
            await dispatch_pending()
        await asyncio.sleep(2)


async def maintenance():
    async with Session() as db:
        approvals=(await db.scalars(select(Approval).where(Approval.status.in_(['PENDING','APPROVED']),Approval.executed_at.is_(None),Approval.expires_at<now()))).all()
        for approval in approvals:
            approval.status='EXPIRED'
            workflow=await db.get(Workflow,approval.workflow_id)
            if workflow.status in {'AWAITING_APPROVAL','APPROVED'}:
                transition(db,workflow,'BLOCKED','Human authorization expired. Retry to obtain a fresh reviewed version.')
            audit(db,approval.org_id,'runtime','approval.expired',approval.id)
        active=(await db.scalars(select(Workflow).where(Workflow.status.in_(['RESEARCHING','DRAFTING','REVIEWING','EXECUTING'])))).all()
        for workflow in active:
            since=workflow.context.get('awaiting_since')
            if since and (now()-datetime.fromisoformat(since)).total_seconds()>settings().handoff_timeout_seconds:
                workflow.error='Switch handoff timed out. Inspect the actual room and failed events before an explicit retry.'
                transition(db,workflow,'BLOCKED',workflow.error)
                audit(db,workflow.org_id,'runtime','workflow.handoff_timed_out',workflow.id)
        await db.commit()


async def main():
    """One runtime leader per business database prevents concurrent duplicate work."""
    from app.db.session import engine
    from sqlalchemy import text
    if settings().database_url.startswith('postgresql'):
        async with engine.connect() as connection:
            locked = await connection.scalar(text('SELECT pg_try_advisory_lock(724390615)'))
            if not locked:
                raise RuntimeError('Another SwitchOps runtime already owns this database')
            try:
                await run_loop()
            finally:
                await connection.execute(text('SELECT pg_advisory_unlock(724390615)'))
    else:
        from filelock import FileLock
        from pathlib import Path
        Path('.data').mkdir(exist_ok=True)
        with FileLock('.data/runtime.lock', timeout=0):
            await run_loop()


if __name__ == '__main__':
    asyncio.run(main())
