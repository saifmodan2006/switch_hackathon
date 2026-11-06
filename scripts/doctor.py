import asyncio
import json
import httpx
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine


async def main():
    cfg=settings()
    result={'python':__import__('platform').python_version(),'encryption_configured':bool(cfg.app_encryption_key),
            'switch_configured_in_environment':bool(cfg.switch_server_url),'smtp_configured':bool(cfg.smtp_host),
            'note':'Per-organization integrations may override environment settings. No secrets are printed.'}
    try:
        async with engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
            result['database']='connected'
            result['migration']=await conn.scalar(text('SELECT version_num FROM alembic_version'))
    except Exception as exc:result['database']=type(exc).__name__
    async with httpx.AsyncClient(timeout=15) as http:
        for name,url in [('frontend',cfg.frontend_url),('backend',cfg.backend_url+'/api/v1/health'),
                         ('switch',cfg.switch_server_url+'/health' if cfg.switch_server_url else ''),
                         ('model',cfg.model_base_url+('/api/tags' if cfg.model_provider=='ollama' else '/models'))]:
            if not url:result[name]='unconfigured';continue
            try:result[name]=(await http.get(url)).status_code
            except Exception as exc:result[name]=type(exc).__name__
    print(json.dumps(result,indent=2))
    await engine.dispose()
asyncio.run(main())
