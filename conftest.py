import os
from cryptography.fernet import Fernet
os.environ['DATABASE_URL']='sqlite+aiosqlite:///:memory:'
os.environ['APP_ENCRYPTION_KEY']=Fernet.generate_key().decode()
os.environ['ENVIRONMENT']='test'
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.domain import Base
from app.db.session import get_db
from app.main import app, _limits


@pytest_asyncio.fixture
async def db_factory():
    engine=create_async_engine('sqlite+aiosqlite:///:memory:',poolclass=StaticPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory=async_sessionmaker(engine,expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_factory):
    async def override():
        async with db_factory() as db:
            yield db
    app.dependency_overrides[get_db]=override
    _limits.clear()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        yield client
    app.dependency_overrides.clear()


async def register(client,email='owner@example.com',name='Alex Owner'):
    result=await client.post('/api/v1/auth/register',json={'name':name,'email':email,'password':'a-secure-test-password!','organization':'Test Workspace'})
    assert result.status_code==201,result.text
    user=result.json()
    client.headers['X-CSRF-Token']=user['csrf']
    return user


@pytest_asyncio.fixture
async def owner(client):
    return await register(client)
