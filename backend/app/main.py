from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, config, items, receipt, sessions, summary


@asynccontextmanager
async def lifespan(app: FastAPI):
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
app.include_router(receipt.router)
app.include_router(items.router)
app.include_router(summary.router)


@app.post("/webhook")
async def telegram_webhook(request: Request):
    from app.bot import process_update
    data = await request.json()
    await process_update(data)
    return {"ok": True}


@app.get("/health")
async def health():
    return {"status": "ok"}
