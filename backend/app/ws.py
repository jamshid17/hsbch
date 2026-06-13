"""In-process WebSocket pub/sub for live session updates.

A single uvicorn worker holds the connections in memory and broadcasts a tiny
"updated" signal to everyone watching a session whenever its picks/items/status
change. Clients then refetch via the REST API. (Multi-worker would need Redis.)
"""

import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, session_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._rooms[session_id].add(ws)

    def disconnect(self, session_id: str, ws: WebSocket) -> None:
        room = self._rooms.get(session_id)
        if room:
            room.discard(ws)
            if not room:
                self._rooms.pop(session_id, None)

    async def broadcast(self, session_id: str, message: dict) -> None:
        payload = json.dumps(message)
        for ws in list(self._rooms.get(session_id, ())):
            try:
                await ws.send_text(payload)
            except Exception:
                self.disconnect(session_id, ws)

    def notify(self, session_id: str, message: dict) -> None:
        """Thread-safe broadcast trigger — safe to call from sync routes."""
        if self._loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(session_id, message), self._loop
            )
        except Exception:
            logger.warning("ws notify failed", exc_info=True)


manager = ConnectionManager()
