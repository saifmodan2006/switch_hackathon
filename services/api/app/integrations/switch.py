"""Released Switch WebSocket/HTTP contract, verified against official docs.

No substitute room bus exists. All cross-agent dispatches are room messages.
"""
import asyncio
import json
from urllib.parse import urlencode
from uuid import uuid4
import httpx
from websockets.asyncio.client import connect
from fastapi import HTTPException
from app.security.auth import decrypt, encrypt
from app.models.domain import Agent


class SwitchError(Exception):
    pass


class SwitchClient:
    def __init__(self, base_url: str, agent_id='', api_key='', connection_id='', transport=None):
        self.base_url = base_url.rstrip('/')
        self.agent_id = agent_id
        self.connection_id = connection_id
        self.http = httpx.AsyncClient(base_url=self.base_url or 'http://unconfigured.invalid',
                                     headers={'Authorization': f'Bearer {api_key}'}, timeout=20, transport=transport)
        self.api_key = api_key
        self.operations = {}

    async def close(self):
        await self.http.aclose()

    async def health(self):
        if not self.base_url:
            raise SwitchError('Switch server is not configured')
        try:
            response = await self.http.get('/health')
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SwitchError('Switch is unavailable; collaboration is paused') from exc

    async def discover(self):
        response = await self.http.get(f'/agents/{self.agent_id}/ops')
        self.check(response)
        self.operations = response.json()['operations']
        return self.operations

    @staticmethod
    def check(response):
        if response.status_code == 403:
            raise SwitchError('Switch denied permission; check owner, room membership and addressing rules')
        if response.status_code == 401:
            raise SwitchError('Switch agent credential is invalid; registration keys cannot authenticate agents')
        if response.status_code >= 400:
            raise SwitchError(f'Switch operation failed (HTTP {response.status_code})')

    async def operation(self, name, args):
        if not self.operations:
            await self.discover()
        if name not in self.operations:
            raise SwitchError(f'This Switch server does not expose {name}')
        schema = self.operations[name]['input_schema']
        missing = set(schema.get('required', [])) - set(args)
        if missing:
            raise SwitchError(f'{name} requires additional server-specific arguments: {sorted(missing)}')
        response = await self.http.post(f'/agents/{self.agent_id}/ops/{name}', json=args,
            headers={'X-Switch-Connection-Id': self.connection_id} if self.connection_id else {})
        self.check(response)
        return response.json().get('result')

    async def post(self, room_id, content):
        await self.health()
        response = await self.http.post(f'/agents/{self.agent_id}/message', json={'room_id': room_id, 'content': content})
        self.check(response)
        return response.json()

    def socket_url(self, rooms, cursor=0, generation=None):
        params = {'connection_id': self.connection_id, 'scope': 'all', 'filter': 'all',
                  'rooms': ','.join(rooms), 'start_from': cursor if cursor else 'head',
                  'client': 'switchops', 'client_version': '1.0.0'}
        if generation is not None:
            params['expected_generation'] = generation
        return self.base_url.replace('https://', 'wss://').replace('http://', 'ws://') + f'/agents/{self.agent_id}/connection/ws?' + urlencode(params)

    async def listen(self, rooms, cursor, generation, on_state, on_event):
        """Persist events before advancing cursor; model work never blocks heartbeat."""
        async with connect(self.socket_url(rooms, cursor, generation),
                           additional_headers={'Authorization': f'Bearer {self.api_key}'}, max_size=2**21) as socket:
            async for raw in socket:
                frame = json.loads(raw)
                kind = frame.get('event', frame.get('type'))
                data = frame.get('data', frame)
                if kind == 'ping':
                    await socket.send(json.dumps({'type': 'pong', 'cursor': cursor}))
                    await on_state('cursor', {'cursor': cursor})
                elif kind == 'connection_state':
                    cursor = data['cursor']
                    generation = data['generation']
                    rooms = data['rooms']
                    await on_state('connected', {**data, 'cursor': cursor})
                elif kind == 'gap':
                    # Fail closed: a human must inspect missed room history before resuming.
                    await on_state('gap', data)
                    raise SwitchError('Switch event gap: inspect room history and reconcile before reconnecting')
                elif kind == 'evicted':
                    if data.get('code') in ('taken_over', 'closed'):
                        await on_state('stopped', data)
                        return
                    raise SwitchError(f"Switch connection evicted: {data.get('code')}")
                elif kind == 'refused':
                    await on_state('refused', data)
                    raise SwitchError(f"Switch connection refused: {data.get('status')}")
                elif kind in ('subscription_changed', 'room_released'):
                    await on_state(kind, data)
                    if kind == 'room_released':
                        raise SwitchError('Room claim released; runtime stopped to avoid duplicate ownership')
                elif 'id' in frame:
                    sequence = int(frame['id'])
                    if sequence <= cursor:
                        continue
                    # on_event must only durably enqueue, never run a model.
                    await on_event(sequence, data)
                    cursor = sequence
                    await on_state('cursor', {'cursor': cursor})


class SwitchAgentRegistry:
    @staticmethod
    async def register(base_url, registration_key, agent: Agent):
        if agent.switch_id:
            raise HTTPException(409, 'Agent already registered. Existing credentials were preserved.')
        async with httpx.AsyncClient(timeout=20) as http:
            response = await http.post(base_url.rstrip('/') + '/agents',
                headers={'Authorization': f'Bearer {registration_key}'},
                json={'name': agent.slug, 'display_name': agent.name, 'description': agent.description,
                      'connector_type': 'switchops-python', 'integration_profile': {
                          'connection_model': 'always_on', 'message_exchange': True,
                          'pre_invocation_mediation': [], 'post_invocation_mediation': [], 'event_reporting': []}})
            SwitchClient.check(response)
            result = response.json()
        agent.switch_id = result['id']
        agent.encrypted_key = encrypt(result['api_key'])
        agent.status = 'disconnected'
        return agent
