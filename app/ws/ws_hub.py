from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class WebSocketLike(Protocol):
    async def accept(self) -> None: ...
    async def send_json(self, data: object) -> None: ...


class WsHub:
    """Tracks connected WS clients and broadcasts call events to all of them.

    The server holds no call history — a client connecting mid-call simply
    starts receiving events from that point on. Each client (browser
    dashboard, Windows native app, ...) is responsible for keeping its own
    history from the events it receives; see README for the message
    contract this broadcasts.

    Kept transport-agnostic (anything satisfying WebSocketLike works —
    fastapi.WebSocket in production, a lightweight fake in tests) so the
    connection-management/broadcast logic is unit-testable without a real
    ASGI server.
    """

    def __init__(self) -> None:
        self._connections: set[WebSocketLike] = set()

    async def connect(self, websocket: WebSocketLike) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocketLike) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, event_type: str, call: dict) -> None:
        message = {"type": event_type, "call": call}
        stale: list[WebSocketLike] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(message)
            except Exception:
                logger.warning("dropping stale client connection", exc_info=True)
                stale.append(websocket)
        for websocket in stale:
            self._connections.discard(websocket)

    @property
    def connection_count(self) -> int:
        return len(self._connections)
