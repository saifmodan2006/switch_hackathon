from datetime import timedelta
from sqlalchemy import select
from app.models.domain import Workflow, WorkflowEvent, now
from agents.runtime import engine as runtime


async def test_stalled_switch_handoff_blocks_visibly(client,owner,db_factory,monkeypatch):
    monkeypatch.setattr(runtime,'Session',db_factory)
    w=(await client.post('/api/v1/workflows',json={'title':'Stalled research','request':'Research should visibly time out'})).json()
    async with db_factory() as db:
        wf=await db.get(Workflow,w['id']);wf.status='RESEARCHING'
        wf.context={'expected_agent':'research-specialist','awaiting_since':(now()-timedelta(hours=1)).isoformat()}
        await db.commit()
    await runtime.maintenance()
    result=(await client.get('/api/v1/workflows/'+w['id'])).json()
    assert result['status']=='BLOCKED' and 'timed out' in result['error']
    assert result['model_calls']==0
