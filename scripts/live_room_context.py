"""Run inside the API container to verify exact Switch context and persist mappings.

Usage: Get-Content scripts/live_room_context.py -Raw | docker exec -i switchops-api-1 python -
"""
import asyncio
import json
import secrets
import httpx
from sqlalchemy import select
from app.db.session import Session
from app.models.domain import Agent, Record, Organization, User, Membership
from agents.runtime.engine import client_for


async def main():
    async with Session() as db:
        org=await db.scalar(select(Organization).where(Organization.name=='SwitchOps Live Demo'))
        room=await db.scalar(select(Record).where(Record.org_id==org.id,Record.kind=='rooms',Record.title=='operations-hub'))
        agents=(await db.scalars(select(Agent).where(Agent.org_id==org.id))).all()
        from datetime import datetime, timezone, timedelta
        if any(a.last_seen and a.last_seen.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc)-timedelta(seconds=15) for a in agents):
            raise RuntimeError('Stop the agent runtime before identity verification; a second socket would take over its connection.')
        coordinator=next(a for a in agents if a.slug=='ops-coordinator')
        client=await client_for(db,coordinator)
        ready=asyncio.Event()
        state={}
        expected={}
        observed={}
        async def on_state(kind,data):
            if kind in {'connected','cursor'}:state.update(data)
            if kind=='connected':ready.set()
        async def on_event(sequence,data):
            print('Observed actual event:',sequence,json.dumps(data)[:1600],flush=True)
            payload=data.get('payload',{})
            body=payload.get('body','')
            for nonce,slug in expected.items():
                if nonce in body:
                    if slug in observed and observed[slug]!=payload['sender']:
                        raise RuntimeError('Conflicting signed identity observation')
                    observed[slug]=payload['sender']
        listener=asyncio.create_task(client.listen([room.data['switch_room_id']],coordinator.cursor,coordinator.generation,on_state,on_event))
        peer=next(a for a in agents if a.slug=='customer-intelligence')
        peer_client=await client_for(db,peer)
        peer_ready=asyncio.Event();peer_state={}
        async def on_peer_state(kind,data):
            if kind in {'connected','cursor'}:peer_state.update(data)
            if kind=='connected':peer_ready.set()
        peer_listener=asyncio.create_task(peer_client.listen([room.data['switch_room_id']],peer.cursor,peer.generation,on_peer_state,on_event))
        try:
            await asyncio.wait_for(asyncio.gather(ready.wait(),peer_ready.wait()),20)
            context=await client.operation('connect_to_room',{'room_id':room.data['switch_room_id']})
            participants=await client.operation('list_participants',{})
            for agent in agents:
                nonce=secrets.token_urlsafe(24)
                expected[nonce]=agent.slug
                publisher=await client_for(db,agent)
                try:
                    result=await publisher.post(room.data['switch_room_id'],f'@ops-coordinator SwitchOps identity verification: {agent.slug} {nonce}')
                    print('Signed identity post:',agent.slug,json.dumps(result)[:500],flush=True)
                finally:await publisher.close()
            async with httpx.AsyncClient(base_url='http://host.docker.internal:8065',timeout=20) as mattermost:
                response=await mattermost.post('/api/v4/users/login',json={'login_id':LIVE_CONFIG['MATTERMOST_USER'],'password':LIVE_CONFIG['MATTERMOST_USER_PASSWORD']})
                response.raise_for_status()
                mattermost.headers['Authorization']='Bearer '+response.headers['Token']
                nonce=secrets.token_urlsafe(24);expected[nonce]='human-operator'
                response=await mattermost.post('/api/v4/posts',json={'channel_id':LIVE_CONFIG['MATTERMOST_CHANNEL_ID'],
                    'message':f'SwitchOps human account identity verification {nonce}'})
                response.raise_for_status()
            async def wait_observed():
                while len(observed)<7:await asyncio.sleep(.2)
            await asyncio.wait_for(wait_observed(),30)
            for agent in agents:
                agent.participant_id=observed[agent.slug]
                agent.rooms=[room.data['switch_room_id']]
                agent.status='disconnected';agent.error=''
            org.settings={**org.settings,'default_room_id':room.data['switch_room_id'],
                'human_identity_mappings':{observed['human-operator']:LIVE_CONFIG['APP_USER_ID']}}
            coordinator.cursor=state['cursor'];coordinator.generation=state['generation']
            coordinator.rooms=state['rooms']
            peer.cursor=peer_state['cursor'];peer.generation=peer_state['generation'];peer.rooms=peer_state['rooms']
            await db.commit()
            print(json.dumps({'verified_participant_ids':observed,'connection_generation':state['generation'],
                              'room_id':room.data['switch_room_id'],'source':'Actual signed Switch/Mattermost posts observed on real WebSocket'},indent=2),flush=True)
        finally:
            listener.cancel()
            peer_listener.cancel()
            await asyncio.gather(listener,peer_listener,return_exceptions=True)
            await client.close()
            await peer_client.close()
asyncio.run(main())
