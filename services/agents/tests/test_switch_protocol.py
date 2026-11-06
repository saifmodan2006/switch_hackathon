import json
import pytest
import httpx
from app.integrations.switch import SwitchClient, SwitchError, SwitchAgentRegistry
from app.models.domain import Agent


async def test_registration_and_key_preservation(monkeypatch):
    seen=[]
    async def handler(request):
        seen.append(request)
        if request.url.path=='/agents':
            body=json.loads(request.content)
            assert 'overwrite' not in body
            assert body['integration_profile']['connection_model']=='always_on'
            assert request.headers['Authorization']=='Bearer registration-only'
            return httpx.Response(200,json={'id':'opaque-agent','api_key':'secret-key'})
        if request.method=='GET':
            return httpx.Response(200,json={'operations':{'update_agent_detail':{'input_schema':{'required':['agent_id','addressing']}}}})
        assert request.headers['Authorization']=='Bearer secret-key'
        return httpx.Response(200,json={'result':{}})
    original=httpx.AsyncClient
    def mocked_client(**kw):
        kw['transport']=httpx.MockTransport(handler)
        return original(**kw)
    monkeypatch.setattr(httpx,'AsyncClient',mocked_client)
    agent=Agent(org_id='tenant',slug='ops-coordinator',name='Ops',description='Triage',switch_id='')
    await SwitchAgentRegistry.register('http://switch','registration-only',agent)
    assert agent.switch_id=='opaque-agent'
    assert agent.encrypted_key!='secret-key'
    from fastapi import HTTPException
    with pytest.raises(HTTPException):await SwitchAgentRegistry.register('http://switch','registration-only',agent)
    assert len([r for r in seen if r.url.path=='/agents'])==1


async def test_operations_discovery_and_permission_denied():
    async def handler(request):
        if request.method=='GET':return httpx.Response(200,json={'operations':{'post_message':{'input_schema':{'required':['room_id','content']}}}})
        return httpx.Response(403,json={'detail':'denied'})
    client=SwitchClient('http://switch','id','key','connection',httpx.MockTransport(handler))
    with pytest.raises(SwitchError,match='requires additional'):await client.operation('post_message',{'content':'hello'})
    with pytest.raises(SwitchError,match='denied permission'):await client.operation('post_message',{'room_id':'room','content':'hello'})
    with pytest.raises(SwitchError,match='does not expose'):await client.operation('invented_endpoint',{})
    await client.close()


async def test_websocket_cursor_heartbeat_filter_and_takeover(monkeypatch):
    frames=[{'event':'connection_state','data':{'cursor':10,'generation':2,'rooms':['actual-room']}},
            {'event':'message','id':11,'data':{'type':'message','room_id':'actual-room','sequence':11,'payload':{'addressed':True}}},
            {'event':'message','id':11,'data':{}},{'event':'ping','data':{}},
            {'event':'evicted','data':{'code':'taken_over'}}]
    sent=[];events=[];states=[]
    class Socket:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def __aiter__(self):self.iterator=iter(frames);return self
        async def __anext__(self):
            try:return json.dumps(next(self.iterator))
            except StopIteration:raise StopAsyncIteration
        async def send(self,content):sent.append(json.loads(content))
    monkeypatch.setattr('app.integrations.switch.connect',lambda *a,**k:Socket())
    async def state(kind,data):states.append((kind,data))
    async def event(seq,data):events.append((seq,data))
    client=SwitchClient('https://switch','a','key','stable-id')
    await client.listen(['requested-room'],5,1,state,event)
    assert events[0][0]==11 and len(events)==1
    assert sent==[{'type':'pong','cursor':11}]
    assert states[0][1]['rooms']==['actual-room']
    assert states[-1][0]=='stopped'
    url=client.socket_url(['room'],11,2)
    assert 'wss://' in url and 'expected_generation=2' in url and 'start_from=11' in url
    await client.close()


async def test_gap_fails_closed(monkeypatch):
    class Socket:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        def __aiter__(self):return self
        async def __anext__(self):return json.dumps({'event':'gap','data':{'resumed_at':50}})
    monkeypatch.setattr('app.integrations.switch.connect',lambda *a,**k:Socket())
    async def state(*args):pass
    async def event(*args):raise AssertionError('No event may be dispatched after gap')
    client=SwitchClient('http://switch','a','k','c')
    with pytest.raises(SwitchError,match='event gap'):await client.listen(['room'],1,None,state,event)
    await client.close()
