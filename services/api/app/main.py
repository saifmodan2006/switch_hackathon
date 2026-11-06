import json
import logging
import time
from collections import defaultdict, deque
from uuid import uuid4
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from app.api.routes import router
from app.integrations.google import router as google_router
from app.api.inbox import router as inbox_router
from app.core.config import settings
from app.integrations.switch import SwitchError

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger('switchops')
app = FastAPI(title='SwitchOps AI', version='1.0.0', description='Business state in SQL; all agent collaboration through genuine Switch rooms.')
app.add_middleware(CORSMiddleware, allow_origins=[settings().frontend_url], allow_credentials=True,
                   allow_methods=['GET','POST','PUT','DELETE','OPTIONS'], allow_headers=['Content-Type','X-CSRF-Token','Idempotency-Key'])
app.include_router(router)
app.include_router(google_router)
app.include_router(inbox_router)
_limits = defaultdict(deque)


@app.middleware('http')
async def security(request: Request, call_next):
    correlation = str(uuid4())
    request.state.correlation_id = correlation
    key = (request.client.host if request.client else 'unknown', 'auth' if request.url.path.startswith('/api/v1/auth/') else 'api')
    queue = _limits[key]
    current = time.monotonic()
    while queue and queue[0] < current-60:
        queue.popleft()
    maximum = 30 if key[1] == 'auth' else 300
    if len(queue) >= maximum:
        response = JSONResponse({'detail': 'Rate limit exceeded. Try again shortly.'}, status_code=429, headers={'Retry-After': '60'})
    elif request.headers.get('content-length', '0').isdigit() and int(request.headers.get('content-length', '0')) > settings().upload_max_bytes + 10000:
        response = JSONResponse({'detail': 'Request exceeds upload size limit'}, status_code=413)
    elif request.method not in {'GET','HEAD','OPTIONS'} and request.headers.get('origin') and request.headers['origin'] not in {settings().frontend_url, settings().backend_url}:
        response = JSONResponse({'detail': 'Untrusted request origin'}, status_code=403)
    else:
        queue.append(current)
        response = await call_next(request)
    response.headers['X-Request-ID'] = correlation
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Cache-Control'] = 'no-store'
    log.info(json.dumps({'event': 'http', 'method': request.method, 'path': request.url.path, 'status': response.status_code, 'correlation_id': correlation}))
    return response


@app.exception_handler(SwitchError)
async def switch_error(request, exc):
    return JSONResponse({'detail': str(exc), 'correlation_id': request.state.correlation_id}, status_code=503)


@app.exception_handler(IntegrityError)
async def conflict(request, exc):
    return JSONResponse({'detail': 'Concurrent or duplicate change conflicted. Refresh and retry.', 'correlation_id': request.state.correlation_id}, status_code=409)
