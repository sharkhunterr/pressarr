"""WebSocket connection manager for real-time updates."""

import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["WebSocket"])
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manage WebSocket connections and broadcasts."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.debug("WebSocket connected (%d active)", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        self.active_connections.remove(websocket)
        logger.debug("WebSocket disconnected (%d active)", len(self.active_connections))

    async def broadcast(self, message_type: str, data: dict | list) -> None:
        """Broadcast a typed message to all connected clients."""
        message = json.dumps({"type": message_type, "data": data})
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    apikey: str | None = Query(None),
) -> None:
    """WebSocket endpoint for real-time updates."""
    # Auth check if enabled
    from app.dependencies import get_config

    config = get_config()
    if config.auth_enabled and config.api_key:
        if apikey != config.api_key:
            await websocket.close(code=4001, reason="Invalid API key")
            return

    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive by waiting for messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
