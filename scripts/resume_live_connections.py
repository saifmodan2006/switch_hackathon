"""Explicit operator recovery after our deliberate Switch stop, preserving cursors."""
import httpx
from dotenv import dotenv_values
access=dotenv_values('.data/live/access.env')
with httpx.Client(base_url='http://127.0.0.1:8000/api/v1',timeout=30) as app:
    login=app.post('/auth/login',json={'email':access['APP_EMAIL'],'password':access['APP_PASSWORD']})
    login.raise_for_status()
    app.headers['X-CSRF-Token']=login.json()['csrf']
    for agent in app.get('/agents').json():
        # The supported mapping endpoint clears terminal state, without changing
        # verified identity, key, rooms, generation or durable event cursor.
        response=app.put('/agents/'+agent['id']+'/mapping',json={'config':{}})
        response.raise_for_status()
        print('Operator resumed verified identity:',agent['slug'])
