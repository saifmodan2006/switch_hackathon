"""Real TCP/WebSocket transport against a controlled protocol fixture, not a Switch server."""
import json
from websockets.asyncio.server import serve
from app.integrations.switch import SwitchClient


async def test_real_websocket_auth_frames_and_pong():
    received=[];states=[];events=[]
    async def handler(socket):
        assert socket.request.headers['Authorization']=='Bearer agent-only-key'
        assert 'connection_id=stable-connection' in socket.request.path
        assert 'rooms=real-room' in socket.request.path
        await socket.send(json.dumps({'event':'connection_state','data':{'cursor':7,'generation':3,'rooms':['real-room']}}))
        await socket.send(json.dumps({'event':'message','id':8,'data':{'type':'message','room_id':'real-room','sequence':8,'payload':{'addressed':True,'body':'Test fixture only'}}}))
        await socket.send(json.dumps({'event':'ping','data':{}}))
        received.append(json.loads(await socket.recv()))
        await socket.send(json.dumps({'event':'evicted','data':{'code':'taken_over'}}))
    async def state(kind,data):states.append((kind,data))
    async def event(sequence,data):events.append((sequence,data))
    async with serve(handler,'127.0.0.1',0) as server:
        port=server.sockets[0].getsockname()[1]
        client=SwitchClient(f'http://127.0.0.1:{port}','agent-id','agent-only-key','stable-connection')
        try:await client.listen(['real-room'],5,2,state,event)
        finally:await client.close()
    assert received==[{'type':'pong','cursor':8}]
    assert events[0][0]==8
    assert states[-1][0]=='stopped'
