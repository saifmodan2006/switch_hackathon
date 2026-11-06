import json
from fastapi import HTTPException
from app.models.domain import Workflow, WorkflowEvent, Audit, now
from app.security.auth import digest

STATES = ['CREATED', 'TRIAGING', 'RESEARCHING', 'DRAFTING', 'REVIEWING', 'AWAITING_APPROVAL', 'APPROVED', 'EXECUTING', 'COMPLETED']
EXCEPTIONAL = {'BLOCKED', 'FAILED', 'CANCELLED', 'REJECTED', 'NEEDS_INFORMATION'}
TERMINAL = {'COMPLETED', 'CANCELLED', 'REJECTED'}


def payload_hash(payload):
    return digest(json.dumps(payload, sort_keys=True, separators=(',', ':')))


def transition(db, workflow: Workflow, target: str, message: str, agent='', switch_event_id=''):
    current = workflow.status
    allowed = target in EXCEPTIONAL and current not in TERMINAL
    if current in STATES and target in STATES:
        allowed = STATES.index(target) == STATES.index(current) + 1
    if current in {'BLOCKED', 'FAILED', 'NEEDS_INFORMATION'} and target == 'TRIAGING':
        allowed = True
    if current == 'AWAITING_APPROVAL' and target == 'DRAFTING':
        allowed = True
    if not allowed:
        raise HTTPException(409, f'Invalid workflow transition: {current} → {target}')
    workflow.status = target
    if target == 'COMPLETED':
        workflow.completed_at = now()
    db.add(WorkflowEvent(org_id=workflow.org_id, workflow_id=workflow.id, kind=target, message=message,
                         agent=agent, switch_event_id=switch_event_id))


def audit(db, org_id, actor, action, resource_id='', **detail):
    db.add(Audit(org_id=org_id, actor=actor, action=action, resource_id=resource_id, detail=detail))
