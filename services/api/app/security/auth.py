import hashlib
import secrets
from datetime import timedelta, timezone
from dataclasses import dataclass
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.db.session import get_db
from app.models.domain import SessionToken, Membership, User, now

hasher = PasswordHasher()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def encrypt(value: str) -> str:
    if not settings().app_encryption_key:
        raise HTTPException(503, 'APP_ENCRYPTION_KEY must be configured before storing credentials')
    return Fernet(settings().app_encryption_key.encode()).encrypt(value.encode()).decode()


def decrypt(value: str) -> str:
    return Fernet(settings().app_encryption_key.encode()).decrypt(value.encode()).decode()


@dataclass
class Principal:
    user: User
    org_id: str
    role: str
    session: SessionToken


async def principal(request: Request, db: AsyncSession = Depends(get_db)) -> Principal:
    token = request.cookies.get('switchops_session', '')
    session = await db.scalar(select(SessionToken).where(SessionToken.token_hash == digest(token)))
    if not session or session.expires_at.replace(tzinfo=timezone.utc) < now():
        raise HTTPException(401, 'Sign in to your workspace')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not secrets.compare_digest(request.headers.get('x-csrf-token', ''), session.csrf):
            raise HTTPException(403, 'Invalid CSRF token; refresh your session')
    membership = await db.scalar(select(Membership).where(Membership.org_id == session.org_id, Membership.user_id == session.user_id))
    if not membership:
        raise HTTPException(403, 'Organization membership required')
    user = await db.get(User, session.user_id)
    return Principal(user, session.org_id, membership.role, session)


def require(p: Principal, *roles: str):
    if p.role not in roles:
        raise HTTPException(403, 'Your role does not permit this action')


def can_write(p: Principal):
    require(p, 'owner', 'admin', 'manager', 'member')


async def new_session(db, user, org_id, response):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    session = SessionToken(user_id=user.id, org_id=org_id, token_hash=digest(token), csrf=csrf,
                           expires_at=now() + timedelta(hours=settings().session_hours))
    db.add(session)
    await db.commit()
    response.set_cookie('switchops_session', token, httponly=True, secure=settings().environment == 'production',
                        samesite='lax', max_age=settings().session_hours * 3600, path='/')
    return {'id': user.id, 'name': user.name, 'email': user.email, 'org_id': org_id, 'csrf': csrf}
