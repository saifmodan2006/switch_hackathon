"""ARQ handles administrative reminders, never cross-agent routing."""
from datetime import datetime, timezone
from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import select
from app.core.config import settings
from app.db.session import Session
from app.models.domain import Record, now


async def reminders(ctx):
    async with Session() as db:
        tasks = (await db.scalars(select(Record).where(Record.kind == 'tasks', Record.status.in_(['open','in_progress'])))).all()
        for task in tasks:
            if not task.data.get('due_at') or task.data.get('reminded'):
                continue
            due = datetime.fromisoformat(task.data['due_at']).replace(tzinfo=timezone.utc)
            if due <= now():
                db.add(Record(org_id=task.org_id, kind='notifications', title='Overdue: ' + task.title[:150], data={'task_id': task.id}))
                task.data = {**task.data, 'reminded': True}
        await db.commit()


class WorkerSettings:
    functions = [reminders]
    cron_jobs = [cron(reminders, minute=set(range(60)), unique=True)]
    redis_settings = RedisSettings.from_dsn(settings().redis_url)
    max_tries = 3
    job_timeout = 60
