from datetime import timezone
from email.utils import make_msgid
from fastapi import HTTPException
from sqlalchemy import select, update
from app.models.domain import Approval, Delivery, Customer, Workflow, Document, now
from app.services.workflows import transition, payload_hash, audit
from app.integrations.email import send_approved_email


async def decide(db, approval, decision, reason, principal):
    if approval.status != 'PENDING':
        raise HTTPException(409, 'This approval has already been decided')
    if approval.expires_at.replace(tzinfo=timezone.utc) <= now():
        raise HTTPException(409, 'Approval expired; request a new version')
    result = await db.execute(update(Approval).where(Approval.id == approval.id, Approval.status == 'PENDING')
        .values(status=decision, decided_by=principal.user.id, decided_at=now(), reason=reason))
    if result.rowcount != 1:
        raise HTTPException(409, 'Another approver already decided this action')
    workflow = await db.get(Workflow, approval.workflow_id)
    if decision == 'APPROVED':
        transition(db, workflow, 'APPROVED', 'Human approved the exact proposal and recipient')
    elif decision == 'REJECTED':
        transition(db, workflow, 'REJECTED', reason or 'Human rejected the action')
    else:
        transition(db, workflow, 'DRAFTING', reason or 'Human requested changes')
        workflow.context = {**workflow.context, 'revision_request': reason, 'revision_pending': True}
    audit(db, principal.org_id, principal.user.id, 'approval.' + decision.lower(), approval.id, reason=reason,
          payload_hash=approval.payload_hash)
    await db.commit()


async def execute(db, approval_id):
    approval = await db.get(Approval, approval_id)
    if not approval or approval.status != 'APPROVED' or approval.executed_at:
        raise HTTPException(409, 'A current unexecuted human approval is required')
    if approval.expires_at.replace(tzinfo=timezone.utc) <= now():
        raise HTTPException(409, 'Approval has expired')
    if payload_hash(approval.payload) != approval.payload_hash:
        raise HTTPException(409, 'Approved action payload was modified')
    document = await db.get(Document, approval.document_id)
    workflow = await db.get(Workflow, approval.workflow_id)
    if document.version != approval.version or document.content != approval.payload['body']:
        raise HTTPException(409, 'Document does not match approved version')
    customer = await db.get(Customer, workflow.customer_id) if workflow.customer_id else None
    if not customer or customer.opted_out or customer.archived or customer.email != approval.payload['recipient']:
        raise HTTPException(409, 'Recipient is missing, changed, archived or opted out')
    existing = await db.scalar(select(Delivery).where(Delivery.approval_id == approval.id))
    if existing:
        return existing
    # Persist one-time claim before external I/O. A crash becomes inspectable, never an automatic resend.
    delivery = Delivery(org_id=approval.org_id, approval_id=approval.id, recipient=approval.payload['recipient'], message_id=make_msgid(domain='switchops.local'))
    db.add(delivery)
    transition(db, workflow, 'EXECUTING', 'Approved communication execution claimed', 'communications-specialist')
    await db.commit()
    try:
        delivery.status = await send_approved_email(approval.payload, delivery.message_id)
        approval.executed_at = now()
        audit(db, approval.org_id, 'communications-specialist', 'email.' + delivery.status, delivery.id)
    except Exception as exc:
        delivery.status = 'unknown_or_failed'
        delivery.error = f'{type(exc).__name__}: {exc}'[:500]
        workflow.error = 'Email attempt failed or outcome is unknown. Inspect provider before any manual recovery.'
        transition(db, workflow, 'BLOCKED', workflow.error)
    await db.commit()
    return delivery
