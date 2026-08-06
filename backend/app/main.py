import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import auth, config, items, people, receipt, sessions, summary
from app.ws import manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Capture the event loop so sync routes can trigger WS broadcasts.
    manager.set_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="Bill Splitter API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(config.router)
app.include_router(sessions.router)
app.include_router(people.router)
app.include_router(receipt.router)
app.include_router(items.router)
app.include_router(summary.router)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    # Telegram echoes back the secret_token passed to setWebhook on every
    # request — without checking it, anyone could POST a forged update here
    # (e.g. a fake successful_payment) and grant themselves a subscription.
    if request.headers.get("x-telegram-bot-api-secret-token") != settings.telegram_webhook_secret:
        raise HTTPException(403, "Forbidden")
    from app.bot import process_update
    data = await request.json()
    await process_update(data)
    return {"ok": True}


@app.websocket("/ws/sessions/{session_id}")
async def session_ws(websocket: WebSocket, session_id: str):
    """Live updates for a session: clients connect and receive an 'updated'
    signal whenever picks/items/status change, then refetch via REST."""
    await manager.connect(session_id, websocket)
    try:
        while True:
            # We don't need client messages; this just keeps the socket open
            # and detects disconnects.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(session_id, websocket)
    except Exception:
        manager.disconnect(session_id, websocket)


@app.get("/health")
async def health():
    return {"status": "ok"}
