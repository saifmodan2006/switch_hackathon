"""Official Google OAuth 2.0 + Calendar v3. No availability fixtures in live code."""
import json
import secrets
from datetime import timedelta, timezone
from urllib.parse import urlencode
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.models.domain import Record, Integration, now
from app.security.auth import principal, Principal, encrypt, decrypt, digest, require
from app.core.config import settings
from app.schemas.inputs import Input
from pydantic import Field

router = APIRouter(prefix='/api/v1/integrations/google')


@router.get('/connect')
async def connect_google(p: Principal = Depends(principal), db: AsyncSession = Depends(get_db)):
    require(p, 'owner', 'admin')
    config = settings()
    if not config.google_client_id or not config.google_client_secret:
        raise HTTPException(503, 'Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in the server environment; internal calendar remains available')
    state = secrets.token_urlsafe(40)
    db.add(Record(org_id=p.org_id, kind='oauth_state', title=digest(state), data={'user_id':p.user.id,'expires':(now()+timedelta(minutes=10)).isoformat()}, status='pending'))
    await db.commit()
    return RedirectResponse('https://accounts.google.com/o/oauth2/v2/auth?'+urlencode({
        'client_id':config.google_client_id,'redirect_uri':config.google_redirect_uri,'response_type':'code',
        'scope':'https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/calendar.freebusy',
        'state':state,'access_type':'offline','prompt':'consent'}))


@router.get('/callback')
async def callback(code:str='',state:str='',error:str='',p:Principal=Depends(principal),db:AsyncSession=Depends(get_db)):
    if error: raise HTTPException(400,'Google authorization was declined')
    row=await db.scalar(select(Record).where(Record.org_id==p.org_id,Record.kind=='oauth_state',Record.title==digest(state),Record.status=='pending'))
    if not row or row.data['user_id']!=p.user.id or row.data['expires'] < now().isoformat():
        raise HTTPException(403,'OAuth state is invalid or expired')
    claim=await db.execute(update(Record).where(Record.id==row.id,Record.status=='pending').values(status='consumed'))
    if claim.rowcount!=1: raise HTTPException(409,'OAuth callback already consumed')
    await db.commit()
    config=settings()
    async with httpx.AsyncClient(timeout=20) as http:
        response=await http.post('https://oauth2.googleapis.com/token',data={'code':code,'client_id':config.google_client_id,
            'client_secret':config.google_client_secret,'redirect_uri':config.google_redirect_uri,'grant_type':'authorization_code'})
        if response.status_code!=200: raise HTTPException(502,'Google token exchange failed; reconnect your account')
        token=response.json()
    token['expires_at']=(now()+timedelta(seconds=token.get('expires_in',3600))).isoformat()
    row=await db.scalar(select(Integration).where(Integration.org_id==p.org_id,Integration.kind=='google'))
    if not row:
        row=Integration(org_id=p.org_id,kind='google',config={'connected':True})
        db.add(row)
    row.encrypted_secret=encrypt(json.dumps(token))
    await db.commit()
    return RedirectResponse(settings().frontend_url+'/integrations')


async def access_token(db,org_id):
    row=await db.scalar(select(Integration).where(Integration.org_id==org_id,Integration.kind=='google'))
    if not row or not row.encrypted_secret: raise HTTPException(503,'Google Calendar is not connected; external availability is unknown')
    token=json.loads(decrypt(row.encrypted_secret))
    if token['expires_at'] > now().isoformat(): return token['access_token']
    if not token.get('refresh_token'): raise HTTPException(503,'Google session expired; reconnect Calendar')
    config=settings()
    async with httpx.AsyncClient(timeout=20) as http:
        response=await http.post('https://oauth2.googleapis.com/token',data={'client_id':config.google_client_id,
            'client_secret':config.google_client_secret,'refresh_token':token['refresh_token'],'grant_type':'refresh_token'})
        if response.status_code!=200: raise HTTPException(502,'Google token refresh failed; reconnect Calendar')
        token.update(response.json())
    token['expires_at']=(now()+timedelta(seconds=token.get('expires_in',3600))).isoformat()
    row.encrypted_secret=encrypt(json.dumps(token))
    await db.commit()
    return token['access_token']


class Availability(Input):
    time_min: str = Field(max_length=60)
    time_max: str = Field(max_length=60)


@router.post('/availability')
async def availability(body:Availability,p:Principal=Depends(principal),db:AsyncSession=Depends(get_db)):
    token=await access_token(db,p.org_id)
    async with httpx.AsyncClient(timeout=20) as http:
        response=await http.post('https://www.googleapis.com/calendar/v3/freeBusy',headers={'Authorization':f'Bearer {token}'},
            json={'timeMin':body.time_min,'timeMax':body.time_max,'items':[{'id':'primary'}]})
        if response.status_code!=200: raise HTTPException(502,'Google free/busy request failed')
        return {'source':'google-calendar','data':response.json()}
