"""Explicit CI fixture. Never imported by the application and never called in live mode."""
import asyncio
import sys
from datetime import timedelta
from sqlalchemy import select
from app.db.session import Session
from app.models.domain import User,Membership,Customer,Workflow,Document,Approval,WorkflowEvent,now
from app.services.workflows import payload_hash


async def main():
    if '.data/e2e.db' not in __import__('os').environ.get('DATABASE_URL',''):
        raise RuntimeError('E2E fixtures are restricted to the isolated E2E database')
    async with Session() as db:
        user=await db.scalar(select(User).where(User.email==sys.argv[1]))
        member=await db.scalar(select(Membership).where(Membership.user_id==user.id))
        customer=Customer(org_id=member.org_id,name='Synthetic approval fixture',email='fixture@example.test',synthetic=True)
        db.add(customer);await db.flush()
        w=Workflow(org_id=member.org_id,owner_id=user.id,customer_id=customer.id,title='Synthetic · Approval review fixture',request='Deterministic test data, not live agent output',status='AWAITING_APPROVAL')
        db.add(w);await db.flush()
        doc=Document(org_id=member.org_id,workflow_id=w.id,title=w.title,content='SYNTHETIC TEST FIXTURE. Proposal for internal workflow discovery. No price or delivery commitment. Requires authorized review.',version=1)
        db.add(doc);await db.flush()
        payload={'recipient':customer.email,'subject':doc.title,'body':doc.content}
        approval=Approval(org_id=member.org_id,workflow_id=w.id,document_id=doc.id,version=1,payload=payload,payload_hash=payload_hash(payload),expires_at=now()+timedelta(days=1))
        db.add(approval);await db.commit()
asyncio.run(main())
