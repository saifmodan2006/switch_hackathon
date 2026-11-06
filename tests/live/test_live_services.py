"""Opt-in real services. Use dedicated test identities/rooms, never a production conversation."""
import asyncio
import os
from uuid import uuid4
import pytest
from app.integrations.switch import SwitchClient
from app.integrations.model import ModelAdapter

pytestmark=pytest.mark.live


@pytest.mark.skipif(os.getenv('RUN_LIVE_SWITCH')!='1',reason='Requires an explicitly configured real Switch test deployment')
async def test_real_two_identity_room_exchange():
    base=os.environ['LIVE_SWITCH_URL'];room=os.environ['LIVE_SWITCH_ROOM_ID']
    a=SwitchClient(base,os.environ['LIVE_SWITCH_AGENT_ID_1'],os.environ['LIVE_SWITCH_AGENT_KEY_1'],str(uuid4()))
    b=SwitchClient(base,os.environ['LIVE_SWITCH_AGENT_ID_2'],os.environ['LIVE_SWITCH_AGENT_KEY_2'],str(uuid4()))
    slug_b=os.environ['LIVE_SWITCH_AGENT_NAME_2'];slug_a=os.environ['LIVE_SWITCH_AGENT_NAME_1']
    ready_a,ready_b,got_a,got_b=[asyncio.Event() for _ in range(4)]
    marker='switchops-live-test-'+str(uuid4())
    async def state_a(kind,data):
        if kind=='connected':ready_a.set()
    async def state_b(kind,data):
        if kind=='connected':ready_b.set()
    async def event_a(seq,data):
        payload=data.get('payload',{})
        if payload.get('addressed') and marker+' reply' in payload.get('body',''):got_a.set()
    async def event_b(seq,data):
        payload=data.get('payload',{})
        if payload.get('addressed') and marker+' request' in payload.get('body',''):got_b.set()
    tasks=[asyncio.create_task(a.listen([room],0,None,state_a,event_a)),asyncio.create_task(b.listen([room],0,None,state_b,event_b))]
    try:
        await a.health();await b.health()
        await asyncio.wait_for(asyncio.gather(ready_a.wait(),ready_b.wait()),20)
        await a.post(room,f'@{slug_b} {marker} request — synthetic transport verification only')
        await asyncio.wait_for(got_b.wait(),20)
        await b.post(room,f'@{slug_a} {marker} reply — synthetic transport verification only')
        await asyncio.wait_for(got_a.wait(),20)
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await a.close();await b.close()


@pytest.mark.skipif(os.getenv('RUN_LIVE_MODEL')!='1',reason='Requires a configured real model endpoint')
async def test_real_model_structured_output():
    adapter=ModelAdapter()
    result,usage=await adapter.generate('Summarize the synthetic record. Cite customer:live-test. Never invent facts.',
        {'id':'live-test','name':'Synthetic Live Test Customer','request':'Internal workflow discovery'})
    assert result.summary and 0<=result.confidence<=1
