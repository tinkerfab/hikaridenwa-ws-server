import copy

import pytest

from app.pipeline import CallPipeline
from app.ws.ws_hub import WsHub
from tests.fixtures.sip_messages import INVITE_ANONYMOUS_CALLER, INVITE_DISCLOSED_CALLER


class FakeWebSocket:
    """Deep-copies sent payloads to mimic real WebSocket.send_json(), which
    serializes to a JSON string immediately (a snapshot) rather than holding
    a live reference to a mutable dict.
    """

    def __init__(self):
        self.sent: list[dict] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.sent.append(copy.deepcopy(data))


def _build_pipeline() -> tuple[CallPipeline, WsHub]:
    ws_hub = WsHub()
    pipeline = CallPipeline(ws_hub=ws_hub)
    return pipeline, ws_hub


@pytest.mark.asyncio
async def test_handle_ringing_broadcasts_call_ringing():
    pipeline, ws_hub = _build_pipeline()
    ws = FakeWebSocket()
    await ws_hub.connect(ws)

    await pipeline.handle_ringing(
        {"call_id": "call-1", "timestamp": 123.0, "whole_msg": INVITE_DISCLOSED_CALLER}
    )

    types = [msg["type"] for msg in ws.sent]
    assert types == ["call:ringing"]

    ringing_msg = ws.sent[0]["call"]
    assert ringing_msg["number"] == "0312345678"
    assert ringing_msg["status"] == "ringing"


@pytest.mark.asyncio
async def test_handle_ringing_for_anonymous_caller():
    pipeline, ws_hub = _build_pipeline()
    ws = FakeWebSocket()
    await ws_hub.connect(ws)

    await pipeline.handle_ringing(
        {"call_id": "call-2", "timestamp": 123.0, "whole_msg": INVITE_ANONYMOUS_CALLER}
    )

    ringing_msg = ws.sent[-1]["call"]
    assert ringing_msg["anonymous"] is True
    assert ringing_msg["number"] is None


@pytest.mark.asyncio
async def test_handle_ended_broadcasts_call_ended_with_reason():
    pipeline, ws_hub = _build_pipeline()
    ws = FakeWebSocket()
    await ws_hub.connect(ws)

    await pipeline.handle_ended("call-1", "disconnected")

    assert ws.sent[-1] == {
        "type": "call:ended",
        "call": {
            "id": None,  # no matching in-flight call — never rang through this pipeline instance
            "call_id": "call-1",
            "ended_at": ws.sent[-1]["call"]["ended_at"],
            "end_reason": "disconnected",
        },
    }


@pytest.mark.asyncio
async def test_ringing_and_ended_share_the_same_stable_id():
    pipeline, ws_hub = _build_pipeline()
    ws = FakeWebSocket()
    await ws_hub.connect(ws)

    await pipeline.handle_ringing(
        {"call_id": "0", "timestamp": 123.0, "whole_msg": INVITE_DISCLOSED_CALLER}
    )
    await pipeline.handle_ended("0", "disconnected")

    ringing_id = ws.sent[0]["call"]["id"]
    ended_id = ws.sent[1]["call"]["id"]
    assert ringing_id and ringing_id == ended_id


@pytest.mark.asyncio
async def test_call_id_reuse_after_end_gets_a_fresh_id_for_the_next_call():
    # pjsua2 reuses small integer call_ids once a call ends — a client must
    # be able to tell a reused call_id apart from the previous, already-
    # ended call that happened to use the same one. The stable `id` field
    # is what makes that possible.
    pipeline, ws_hub = _build_pipeline()
    ws = FakeWebSocket()
    await ws_hub.connect(ws)

    await pipeline.handle_ringing({"call_id": "0", "timestamp": 1.0, "whole_msg": INVITE_DISCLOSED_CALLER})
    first_id = ws.sent[0]["call"]["id"]
    await pipeline.handle_ended("0", "disconnected")

    await pipeline.handle_ringing({"call_id": "0", "timestamp": 2.0, "whole_msg": INVITE_DISCLOSED_CALLER})
    second_id = ws.sent[-1]["call"]["id"]

    assert second_id != first_id
