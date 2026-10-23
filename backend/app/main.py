from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI, Depends, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from .config import settings
from .db import get_db
from .routers import auth, assets, projects, tracks, catalog, ai, community, admin, chat, support, wechat, route_notes
from .routers import web_auth, runtime_config, admin_content
from .runtime_config import ReadMap
from .jobs import development_recovery_loop


@asynccontextmanager
async def lifespan(app):
    settings().validate_runtime()
    recovery = asyncio.create_task(development_recovery_loop()) if settings().queue_backend == 'inline' else None
    try:
        yield
    finally:
        if recovery:
            recovery.cancel()
            try:
                await recovery
            except asyncio.CancelledError:
                pass


app = FastAPI(title="自然记 Nature Note", version="1.0.0", lifespan=lifespan)

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={'detail': {'code': 'validation_error', 'message': '输入参数无效', 'fields': [{'path': '.'.join(map(str, e['loc'])), 'message': e['msg']} for e in exc.errors()]}})


@app.exception_handler(IntegrityError)
async def conflict_error(request, exc):
    return JSONResponse(status_code=409, content={'detail': {'code': 'write_conflict', 'message': '重复提交或记录已更新，请刷新后重试'}})


@app.get('/health')
def health():
    return {'status': 'ok', 'service': 'nature-note', 'ai_mode': settings().ai_mode}


@app.get('/ready')
def ready(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ready'}


for router in (auth.api, assets.api, projects.api, tracks.api, catalog.api, ai.api, community.api, admin.api, chat.api, support.api, wechat.api, route_notes.api):
    app.include_router(router)

app.include_router(web_auth.api)
app.include_router(runtime_config.api)
app.include_router(admin_content.api)


@app.get('/api/v1/web-config')
def WebConfig(response: Response, db=Depends(get_db)):
    response.headers['Cache-Control'] = 'no-store'
    return {'map_key': ReadMap(db)['map_key']}
