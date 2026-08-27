from __future__ import annotations

import time
import uuid

from app.sip.caller_id import parse_caller_id
from app.sip.raw_headers import extract_headers
from app.ws.ws_hub import WsHub


class CallPipeline:
    """Wires a raw SIP ringing/ended event to: header parsing -> WS broadcast.

    This pipeline keeps no server-side call log/history — each event is
    broadcast once and forgotten. Connected WS clients are responsible for
    assembling and persisting their own history from the broadcast events
    (see README's "WebSocketメッセージ仕様" section for the message contract).

    It does keep one small piece of *transient* state: a call_id -> id
    mapping for calls currently in flight (populated in handle_ringing,
    popped in handle_ended). This is not history — pjsua2 reuses small
    integer call_ids once a call ends, so without this a client could
    mistake a brand new call for an update to a previous, already-ended
    call that happened to reuse the same call_id. The generated `id` (a
    uuid, stable across ringing/ended for one call) is what clients should
    actually key their records on; `call_id` alone is not a safe key
    across a call's full lifetime.

    Constructed once at app startup and handed to SipBridge as its
    on_ringing/on_ended callbacks (see app/main.py).
    """

    def __init__(self, *, ws_hub: WsHub):
        self._ws_hub = ws_hub
        self._call_id_to_id: dict[str, str] = {}

    async def handle_ringing(self, raw_event: dict) -> None:
        headers = extract_headers(raw_event["whole_msg"])
        caller = parse_caller_id(headers)

        record_id = str(uuid.uuid4())
        self._call_id_to_id[raw_event["call_id"]] = record_id

        call = {
            "id": record_id,
            "call_id": raw_event["call_id"],
            "received_at": raw_event["timestamp"],
            "number": caller.number,
            "display_name": caller.display_name,
            "anonymous": caller.anonymous,
            "source": caller.source,
            "status": "ringing",
        }
        await self._ws_hub.broadcast("call:ringing", call)

    async def handle_ended(self, call_id: str, reason: str) -> None:
        record_id = self._call_id_to_id.pop(call_id, None)
        await self._ws_hub.broadcast(
            "call:ended",
            {"id": record_id, "call_id": call_id, "ended_at": time.time(), "end_reason": reason},
        )
