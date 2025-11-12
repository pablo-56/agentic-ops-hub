# backend/app/routers/streaming.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set

router = APIRouter()

class ConnectionManager:
    def __init__(self) -> None:
        self.active: Set[WebSocket] = set()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.add(ws)

    def disconnect(self, ws: WebSocket):
        self.active.discard(ws)

    async def broadcast_text(self, message: str):
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def broadcast_json(self, data):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

manager = ConnectionManager()

@router.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    """Minimal pub/sub: every client gets every broadcast (filter client-side for now)."""
    await manager.connect(websocket)
    try:
        # (Optional) read client 'subscribe' messages; we just echo for now
        while True:
            msg = await websocket.receive_text()
            await websocket.send_text(f"subscribed: {msg}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
