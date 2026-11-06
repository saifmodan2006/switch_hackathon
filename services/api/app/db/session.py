from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from app.core.config import settings

engine = create_async_engine(settings().database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)
if settings().database_url.startswith('sqlite'):
    @event.listens_for(engine.sync_engine, 'connect')
    def sqlite_foreign_keys(connection, _):
        connection.execute('PRAGMA foreign_keys=ON')
        connection.execute('PRAGMA busy_timeout=10000')


async def get_db():
    async with Session() as db:
        yield db
