import pytest

from app.ws.ws_hub import WsHub


class FakeWebSocket:
    def __init__(self, fail_on_send: bool = False):
        self.accepted = False
        self.sent: list[dict] = []
        self._fail_on_send = fail_on_send

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, data: dict) -> None:
        if self._fail_on_send:
            raise RuntimeError("connection closed")
        self.sent.append(data)


@pytest.mark.asyncio
async def test_connect_accepts_and_sends_nothing_up_front():
    hub = WsHub()
    ws = FakeWebSocket()

    await hub.connect(ws)

    assert ws.accepted is True
    assert ws.sent == []  # no server-side history to replay


@pytest.mark.asyncio
async def test_broadcast_reaches_all_connected_clients():
    hub = WsHub()
    ws1, ws2 = FakeWebSocket(), FakeWebSocket()
    await hub.connect(ws1)
    await hub.connect(ws2)

    await hub.broadcast("call:ringing", {"call_id": "1", "number": "0312345678"})

    expected = {"type": "call:ringing", "call": {"call_id": "1", "number": "0312345678"}}
    assert ws1.sent[-1] == expected
    assert ws2.sent[-1] == expected


@pytest.mark.asyncio
async def test_disconnect_stops_future_broadcasts():
    hub = WsHub()
    ws = FakeWebSocket()
    await hub.connect(ws)

    hub.disconnect(ws)
    await hub.broadcast("call:ringing", {"call_id": "1"})

    assert ws.sent == []


@pytest.mark.asyncio
async def test_broadcast_prunes_stale_connection_without_affecting_others():
    hub = WsHub()
    healthy = FakeWebSocket()
    stale = FakeWebSocket()
    await hub.connect(healthy)
    await hub.connect(stale)
    stale._fail_on_send = True  # simulate the connection dropping after connect

    await hub.broadcast("call:ringing", {"call_id": "1"})

    assert hub.connection_count == 1
    assert healthy.sent[-1] == {"type": "call:ringing", "call": {"call_id": "1"}}


@pytest.mark.asyncio
async def test_connection_count_reflects_connects_and_disconnects():
    hub = WsHub()
    ws = FakeWebSocket()

    assert hub.connection_count == 0
    await hub.connect(ws)
    assert hub.connection_count == 1
    hub.disconnect(ws)
    assert hub.connection_count == 0
